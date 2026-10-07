"""Fixtures for live tests against the running Ableton Live.

Several builders share one Live instance, so every live test session holds an exclusive file lock
(see docs/PLAN.md, shared-Live protocol). Tests create scratch tracks and scenes named
"[test:<ws>] ..." and delete them afterwards; they never modify pre-existing material.
"""
import contextlib
import fcntl
from pathlib import Path

import pytest

from MCP_Server.connection import AbletonConnection, AbletonError

LOCK_PATH = Path(__file__).resolve().parents[2] / ".live-test.lock"

# Song properties tests may change; snapshotted before and restored after each test using `song_state`.
SONG_STATE = [
    "tempo", "signature_numerator", "signature_denominator", "loop", "loop_start", "loop_length", "metronome",
    "record_mode", "arrangement_overdub", "session_automation_record", "clip_trigger_quantization",
    "midi_recording_quantization", "swing_amount", "groove_amount", "root_note", "scale_name", "scale_mode",
    "punch_in", "punch_out", "start_time", "current_song_time",
]


@contextlib.contextmanager
def live_lock():
    """Exclusive access to the shared Live instance (blocks until other builders finish)."""
    with open(LOCK_PATH, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.live)


@pytest.fixture(scope="session", autouse=True)
def _exclusive_live():
    with live_lock():
        yield


@pytest.fixture(scope="session")
def live():
    """A connection to Live; skips the session when Live is not reachable."""
    connection = AbletonConnection()
    try:
        connection.send_command("ping", timeout=5)
    except AbletonError as error:
        pytest.skip("Ableton Live is not reachable: {0}".format(error))
    yield connection
    connection.close()


def lom_value(live, path, prop):
    return live.send_command("lom_get", {"path": path, "properties": [prop]})["values"][prop].get("value")


def track_names(live):
    return live.send_command("lom_get", {"path": "live_set", "properties": ["tracks"]})["values"]["tracks"].get("items", [])


def scene_names(live):
    return live.send_command("lom_get", {"path": "live_set", "properties": ["scenes"]})["values"]["scenes"].get("items", [])


class Scratch(object):
    """Creates "[test:<ws>] <name>" tracks and scenes through the generic LOM commands and removes them."""

    def __init__(self, live, workstream):
        self.live = live
        self.prefix = "[test:{0}]".format(workstream)

    def name(self, label):
        return "{0} {1}".format(self.prefix, label).strip()

    def track(self, label="track", kind="midi"):
        """Create a scratch track at the end of the set; returns its name (address tracks by name)."""
        method = {"midi": "create_midi_track", "audio": "create_audio_track"}[kind]
        created = self.live.send_command("lom_call", {"path": "live_set", "method": method, "args": [-1]})
        name = self.name(label)
        self.live.send_command("lom_set", {"path": created["result"]["path"], "property": "name", "value": name})
        return name

    def return_track(self, label="return"):
        created = self.live.send_command("lom_call", {"path": "live_set", "method": "create_return_track", "args": []})
        name = self.name(label)
        self.live.send_command("lom_set", {"path": created["result"]["path"], "property": "name", "value": name})
        return name

    def scene(self, label="scene"):
        created = self.live.send_command("lom_call", {"path": "live_set", "method": "create_scene", "args": [-1]})
        name = self.name(label)
        self.live.send_command("lom_set", {"path": created["result"]["path"], "property": "name", "value": name})
        return name

    def cleanup(self):
        """Delete every track, return track and scene whose name starts with this scratch prefix.

        One read and one batched delete (a single round trip to Live's main thread).
        """
        collections = ("tracks", "return_tracks", "scenes")
        found = self.live.send_command("lom_get", {"path": "live_set", "properties": list(collections)})["values"]
        commands = []
        for collection, method in zip(collections, ("delete_track", "delete_return_track", "delete_scene")):
            names = found[collection].get("items", [])
            for index in reversed(range(len(names))):
                if names[index].startswith(self.prefix):
                    commands.append({"type": "lom_call", "params": {"path": "live_set", "method": method, "args": [index]}})
        if commands:
            self.live.send_command("batch", {"commands": commands, "stop_on_error": False})


@pytest.fixture
def scratch(live, request):
    """Scratch factory for the test's workstream, cleaned up even when the test fails.

    The workstream comes from the test module name: tests/live/test_tracks.py -> "tracks".
    """
    workstream = request.module.__name__.rsplit(".", 1)[-1].replace("test_", "")
    helper = Scratch(live, workstream)
    helper.cleanup()
    try:
        yield helper
    finally:
        try:
            live.send_command("lom_call", {"path": "live_set", "method": "stop_playing", "args": []})
        except AbletonError:
            pass
        helper.cleanup()


@pytest.fixture
def song_state(live):
    """Snapshot global song settings and restore them after the test."""
    values = live.send_command("lom_get", {"path": "live_set", "properties": SONG_STATE})["values"]
    snapshot = dict((name, entry["value"]) for name, entry in values.items() if "value" in entry)
    yield snapshot
    # Restore in one batched round trip: stop first, then every snapshotted property.
    commands = [{"type": "lom_call", "params": {"path": "live_set", "method": "stop_playing", "args": []}}]
    commands += [{"type": "lom_set", "params": {"path": "live_set", "property": name, "value": snapshot[name]}} for name in SONG_STATE if name in snapshot]
    try:
        live.send_command("batch", {"commands": commands, "stop_on_error": False})
    except AbletonError:
        pass
