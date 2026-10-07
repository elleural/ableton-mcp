"""Live tests for WS-A: status, overview, undo, song settings, transport, scenes, locators, grooves,
selection, messages and the project lifecycle.

    uv run pytest tests/live/test_song.py

Only "[test:song]" scratch tracks, scenes and locators are changed; global settings are restored.
These tests never create, open or save sets, never press a Live dialog and never run osascript.
The project-lifecycle test replaces the open set, so it only runs with ABLETON_MCP_TEST_UI=1: use that
only on a Live instance whose set you do not need.
"""
import json
import os
import tempfile
import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server import ui_automation
from MCP_Server.tools import project, song as song_tools, status as status_tools
from tests.live.conftest import lom_value, scene_names, track_names

UI = os.environ.get("ABLETON_MCP_TEST_UI") == "1"
PREFIX = "[test:song]"
EXTRA_STATE = (("live_set view", "follow_song"), ("live_set", "session_record"), ("live_set", "is_ableton_link_enabled"),
               ("live_set", "tempo_follower_enabled"))


@pytest.fixture(autouse=True)
def no_ui_probe(monkeypatch):
    """Without ABLETON_MCP_TEST_UI, UI automation is reported from passive checks only: no osascript."""
    if not UI:
        ui_automation.reset()
        monkeypatch.setattr(ui_automation, "_probe", lambda host: ui_automation._result(False, "not probed in live tests", "", "skipped"))
    yield
    if not UI:
        ui_automation.reset()


@pytest.fixture
def extra_state(live):
    """Snapshot the settings song_state does not cover (follow, session record, Link, selection, view)."""
    saved = dict(((path, prop), lom_value(live, path, prop)) for path, prop in EXTRA_STATE)
    selection = song_tools.select()
    yield saved
    for (path, prop), value in saved.items():
        try:
            live.send_command("lom_set", {"path": path, "property": prop, "value": value})
        except Exception:
            pass
    track = (selection.get("track") or {}).get("name")
    try:
        song_tools.select(track=track if track in track_names(live) else None, view=selection.get("view") or "Session")
    except ToolError:
        pass


def index_of(names, name):
    return names.index(name)


def wait_for(predicate, timeout=3.0, step=0.1):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return predicate()


def add_clip(live, track_name, slot=0, length=4.0, name=None):
    path = "live_set tracks {0} clip_slots {1}".format(index_of(track_names(live), track_name), slot)
    live.send_command("lom_call", {"path": path, "method": "create_clip", "args": [length]})
    if name:
        live.send_command("lom_set", {"path": path + " clip", "property": "name", "value": name})
    return path


def cleanup_locators():
    for locator in reversed(status_tools.get_song_overview()["locators"]):
        if locator["name"].startswith(PREFIX):
            try:
                song_tools.delete_locator(locator["name"])
            except ToolError:
                pass


# ---------------------------------------------------------------------------
# Status and overview
# ---------------------------------------------------------------------------


def test_get_status(live):
    out = status_tools.get_status()
    assert out["connected"] is True and out["live"]["version"].startswith("12")
    assert out["script"]["commands"] >= 19 and isinstance(out["script"]["handlers_failed"], list)
    assert out["set"]["document"] and "path" in out["set"]
    transport = out["transport"]
    assert {"playing", "position", "start_marker", "tempo", "time_signature", "loop", "record"} <= set(transport)
    assert transport["position"]["bar"].count(".") >= 2
    assert isinstance(out["jobs"], list) and "dialog" in out
    assert set(out["capabilities"]) == {"ffmpeg", "ffprobe", "ui_automation"}
    assert set(out["capabilities"]["ui_automation"]) == {"available", "detail", "fix"}
    json.dumps(out)


def test_get_song_overview(live, scratch):
    track = scratch.track("overview", "midi")
    add_clip(live, track, 0, 4.0, "Hook")
    index = index_of(track_names(live), track)
    live.send_command("lom_call", {"path": "live_set tracks {0}".format(index), "method": "create_midi_clip", "args": [8.0, 4.0]})
    scene = scratch.scene("section")
    out = status_tools.get_song_overview()
    entry = [item for item in out["tracks"] if item["name"] == track][0]
    assert entry["track"] == index and entry["kind"] == "midi" and entry["color"].startswith("#")
    assert entry["clips"] == [{"slot": 0, "name": "Hook", "length": 4.0}]
    assert entry["arrangement"] == {"clips": 1, "start": {"beats": 8.0, "bar": "3.1.1"}, "end": {"beats": 12.0, "bar": "4.1.1"}}
    assert all(item["track"].startswith("return:") for item in out["returns"]) and out["master"]["kind"] == "master"
    assert {"scene": index_of(scene_names(live), scene), "name": scene, "empty": True} in out["scenes"]
    assert {"tempo", "time_signature", "key", "scale", "loop", "length"} <= set(out["song"])
    detail = status_tools.get_song_overview(detail=True)
    entry = [item for item in detail["tracks"] if item["name"] == track][0]
    assert "volume_db" in entry and "pan" in entry and len(entry["arrangement"]["items"]) == 1
    assert "launch_quantization" in detail["song"]["state"]


# ---------------------------------------------------------------------------
# Undo and redo
# ---------------------------------------------------------------------------


def test_undo_redo(live, scratch):
    scene = scratch.scene("undo")
    renamed = scene + " renamed"
    song_tools.set_scene(scene, name=renamed)
    assert renamed in scene_names(live)
    out = status_tools.undo()
    assert out["undone"] == 1 and out["can_redo"] is True
    assert scene in scene_names(live) and renamed not in scene_names(live)
    out = status_tools.redo()
    assert out["redone"] == 1 and renamed in scene_names(live)
    with pytest.raises(ToolError):
        status_tools.undo(steps=0)


# ---------------------------------------------------------------------------
# Song settings
# ---------------------------------------------------------------------------


def test_set_song(live, song_state, extra_state):
    out = song_tools.set_song(
        tempo=97.5, time_signature="3/4", key="D dorian", swing=0.2, groove_amount=0.5, loop=True, loop_start="2.1.1",
        loop_length="2 bars", punch_in=True, punch_out=True, launch_quantization="1/4", record_quantization="1/16",
        follow=False, metronome=False, arrangement_overdub=True, scale_mode=True, record_mode=False, link=False,
    )
    assert out["tempo"] == 97.5 and out["time_signature"] == "3/4" and (out["key"], out["scale"]) == ("D", "Dorian")
    assert out["loop"] is True and out["loop_start"] == {"beats": 3.0, "bar": "2.1.1"} and out["loop_length"] == 6.0
    assert out["punch_in"] is True and out["punch_out"] is True  # read back on the next tick
    assert out["launch_quantization"] == "1/4" and out["record_quantization"] == "1/16" and out["follow"] is False
    assert out["swing"] == 0.2 and out["groove_amount"] == 0.5 and "warnings" not in out
    assert lom_value(live, "live_set", "loop_length") == 6.0
    out = song_tools.set_song(loop_end="5.1.1")
    assert out["loop_length"] == 9.0
    assert song_tools.set_song()["tempo"] == 97.5
    for bad in ({"scale": "Bogus"}, {"time_signature": "5/3"}, {"loop_length": 4, "loop_end": 8}, {"tempo": 5}, {"key": "H"}):
        with pytest.raises(ToolError):
            song_tools.set_song(**bad)
    with pytest.raises(ToolError) as error:
        song_tools.set_song(scale="Bogus")
    assert "Dorian" in str(error.value)


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def test_transport(live, scratch, song_state, extra_state):
    song_tools.set_song(launch_quantization="none", loop=False)
    out = song_tools.transport("play", position="5.1.1")
    assert out["action"] == "play" and out["transport"]["playing"] is True and out["transport"]["position"]["beats"] >= 16.0
    out = song_tools.transport("jump", position=1)
    assert out["transport"]["position"]["beats"] < 12.0
    assert song_tools.transport("stop")["transport"]["playing"] is False
    assert song_tools.transport("continue")["transport"]["playing"] is True
    song_tools.transport("stop")
    out = song_tools.transport("jump", position="3.1.1")
    assert out["transport"]["start_marker"]["beats"] == 8.0 and out["transport"]["playing"] is False
    song_tools.transport("play_selection")
    song_tools.transport("stop_all_clips")
    song_tools.transport("stop")
    song_tools.transport("tap_tempo")
    try:
        song_tools.transport("capture_midi")
    except ToolError as error:
        assert "no recently played MIDI" in str(error)
    with pytest.raises(ToolError):
        song_tools.transport("dance")
    with pytest.raises(ToolError):
        song_tools.transport("jump")

    # capture_scene inserts a scene after the selected one
    scene = scratch.scene("capture")
    song_tools.select(scene=scene)
    out = song_tools.transport("capture_scene")
    assert out["scene"]["scene"] == index_of(scene_names(live), scene) + 1
    song_tools.set_scene(out["scene"]["scene"], name=PREFIX + " captured")

    # back_to_arrangement: a Session clip overrides the arrangement until we go back to it
    track = scratch.track("bta", "midi")
    slot = add_clip(live, track, 0, 4.0)
    live.send_command("lom_set", {"path": slot.rsplit(" clip_slots", 1)[0], "property": "arm", "value": False})
    song_tools.transport("play", position=0)
    live.send_command("lom_call", {"path": slot, "method": "fire", "args": []})
    assert wait_for(lambda: status_tools.get_status()["transport"]["back_to_arranger"]) is True
    out = song_tools.transport("back_to_arrangement")
    assert out["transport"]["back_to_arranger"] is False and out["transport"]["playing"] is True
    assert wait_for(lambda: not lom_value(live, slot, "is_playing")) is True
    song_tools.transport("stop")


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------


def test_scene_lifecycle(live, scratch):
    """Fires only after the scene tempo is switched off, so the song tempo never changes."""
    created = song_tools.create_scene(name=PREFIX + " A", color="#FF0000", tempo=100, time_signature="7/8")
    assert created["name"] == PREFIX + " A" and created["tempo"] == 100.0 and created["time_signature"] == "7/8"
    assert created["scene"] == len(scene_names(live)) - 1 and created["color"].startswith("#")
    out = song_tools.set_scene(PREFIX + " A", tempo="off", time_signature="off", color=5)
    assert "tempo" not in out and "time_signature" not in out
    duplicate = song_tools.duplicate_scene(PREFIX + " A")
    assert duplicate["scene"] == created["scene"] + 1 and duplicate["source"] == created["scene"]
    song_tools.set_scene(duplicate["scene"], name=PREFIX + " B")
    out = song_tools.fire_scene(PREFIX + " A")
    assert out["fired"] is True
    song_tools.transport("stop")
    out = song_tools.delete_scene(PREFIX + " B")
    assert out["deleted"]["name"] == PREFIX + " B" and PREFIX + " B" not in scene_names(live)
    with pytest.raises(ToolError) as error:
        song_tools.delete_scene(PREFIX + " no such scene")
    assert "not found" in str(error.value)
    with pytest.raises(ToolError):
        song_tools.create_scene(index=10000)
    with pytest.raises(ToolError):
        song_tools.set_scene(PREFIX + " A", time_signature="3/3")


# ---------------------------------------------------------------------------
# Locators
# ---------------------------------------------------------------------------


def free_time(live):
    """A bar start with no locator within a bar of it, inside the song length."""
    taken = [locator["time"]["beats"] for locator in status_tools.get_song_overview()["locators"]]
    length = lom_value(live, "live_set", "song_length")
    for bar in range(2, 64):
        beats = (bar - 1) * 4.0
        if beats < length - 4 and all(abs(beats - other) >= 4.0 for other in taken):
            return beats
    pytest.skip("no free arrangement position for a scratch locator")


def test_locators(live, song_state, extra_state):
    song_tools.transport("stop")
    cleanup_locators()
    try:
        when = free_time(live)
        song_tools.transport("jump", position=1)
        before = status_tools.get_status()["transport"]["position"]["beats"]
        out = song_tools.create_locator(when, PREFIX + " Verse")
        assert out["name"] == PREFIX + " Verse" and out["time"]["beats"] == when
        assert abs(status_tools.get_status()["transport"]["position"]["beats"] - before) < 0.01  # playhead restored
        with pytest.raises(ToolError) as error:
            song_tools.create_locator(when, "duplicate")
        assert "already exists" in str(error.value)
        out = song_tools.set_locator(PREFIX + " Verse", PREFIX + " Chorus")
        assert out["name"] == PREFIX + " Chorus"
        assert any(item["name"] == PREFIX + " Chorus" for item in status_tools.get_song_overview()["locators"])
        out = song_tools.transport("jump", position=PREFIX + " Chorus")
        assert out["transport"]["start_marker"]["beats"] == when
        start = max(when - 4.0, 0.0)
        song_tools.transport("jump", position=start)
        out = song_tools.transport("jump_to_next_locator")  # Live also stops at loop-brace edges
        assert start < out["transport"]["position"]["beats"] <= when
        try:
            song_tools.transport("jump_to_prev_locator")
        except ToolError as error:
            assert "No locator before" in str(error)
        song_tools.transport("play", position=0)
        with pytest.raises(ToolError) as error:
            song_tools.create_locator(when + 4.0, "while playing")
        assert "Stop the transport" in str(error.value)
        song_tools.transport("stop")
        out = song_tools.delete_locator(PREFIX + " Chorus")
        assert out["deleted"]["name"] == PREFIX + " Chorus"
        assert all(item["name"] != PREFIX + " Chorus" for item in status_tools.get_song_overview()["locators"])
        with pytest.raises(ToolError):
            song_tools.delete_locator(PREFIX + " no such locator")
    finally:
        song_tools.transport("stop")
        cleanup_locators()


# ---------------------------------------------------------------------------
# Grooves (the groove pool is the user's: written back unchanged)
# ---------------------------------------------------------------------------


def test_grooves(live):
    out = song_tools.get_grooves()
    assert isinstance(out["grooves"], list) and "groove_amount" in out
    with pytest.raises(ToolError):
        song_tools.set_groove(PREFIX + " no such groove", timing=10)
    if not out["grooves"]:
        pytest.skip("the groove pool is empty")
    groove = out["grooves"][0]
    with pytest.raises(ToolError):
        song_tools.set_groove(0, timing=150)
    same = song_tools.set_groove(0, name=groove["name"], base=groove["base"], quantize=groove["quantize"], random=groove["random"],
                                 timing=groove["timing"], velocity=groove["velocity"])
    assert same == groove
    assert song_tools.get_grooves()["grooves"][0] == groove


# ---------------------------------------------------------------------------
# Selection, messages, dialogs
# ---------------------------------------------------------------------------


def test_select(live, scratch, extra_state):
    audio = scratch.track("select audio", "audio")
    live.send_command("lom_call", {"path": "live_set tracks {0}".format(index_of(track_names(live), audio)), "method": "insert_device", "args": ["Utility"]})
    midi = scratch.track("select midi", "midi")
    add_clip(live, midi, 1, 4.0, "Selected clip")
    scene = scratch.scene("select")
    out = song_tools.select(track=audio, device="Utility", view="Devices")
    assert out["track"]["name"] == audio and out["device"]["name"] == "Utility" and "Detail/DeviceChain" in out["visible_views"]
    out = song_tools.select(track=midi, slot=1, view="Session")
    assert out["detail_clip"]["name"] == "Selected clip" and out["slot"]["slot"] == 1 and out["view"] == "Session"
    out = song_tools.select(scene=scene)
    assert out["scene"]["name"] == scene
    assert song_tools.select()["scene"]["name"] == scene
    for bad in ({"slot": 0}, {"view": "Mixer"}, {"track": midi, "slot": 0, "scene": 0}, {"track": midi, "device": "No Such Device"}):
        with pytest.raises(ToolError):
            song_tools.select(**bad)


def test_show_message(live):
    assert song_tools.show_message("AbletonMCP: live test") == {"shown": "AbletonMCP: live test"}


def test_respond_to_dialog_without_a_dialog(live):
    if status_tools.get_status()["dialog"]:
        pytest.skip("Live is showing a dialog; these tests never press dialog buttons")
    with pytest.raises(ToolError) as error:
        status_tools.respond_to_dialog(0)
    assert "No dialog is open" in str(error.value)


# ---------------------------------------------------------------------------
# Project lifecycle
# ---------------------------------------------------------------------------


def test_project_tools_fail_safely_without_ui_automation(live, monkeypatch, tmp_path):
    """Validation and permission errors happen before anything reaches Live's menus."""
    monkeypatch.setattr(ui_automation, "require", lambda: (_ for _ in ()).throw(ui_automation.UIAutomationError("unsupported", "UI automation is unavailable: test", "grant it")))
    document = status_tools.get_status()["set"]["document"]
    with pytest.raises(ToolError):
        project.open_set(str(tmp_path / "missing.als"))
    with pytest.raises(ToolError) as error:
        project.new_set()
    assert "grant it" in str(error.value) or "dialog" in str(error.value)
    with pytest.raises(ToolError):
        project.save_set(str(tmp_path / "Never Saved.als"))
    with pytest.raises(ToolError):
        project.export_audio(str(tmp_path / "mix.wav"), 0, 4)
    assert not os.listdir(str(tmp_path))
    assert status_tools.get_status()["set"]["document"] == document


@pytest.mark.skipif(not UI, reason="replaces the open set; set ABLETON_MCP_TEST_UI=1 on a Live whose set you do not need")
def test_project_lifecycle(live):
    """Spike and regression test for new/save/open/export and Live's save prompt (docs/spikes.md)."""
    if not ui_automation.status()["available"]:
        pytest.skip("UI automation unavailable: " + ui_automation.status()["detail"])
    folder = tempfile.mkdtemp(prefix="ableton-mcp-ui-")
    created = project.new_set(discard_unsaved=True)
    assert created["created"] and created["set"]["path"] is None
    song_tools.set_song(tempo=101)
    first = project.save_set(os.path.join(folder, "AbletonMCP UI Test.als"))["path"]
    assert os.path.isfile(first) and status_tools.get_status()["set"]["path"] == first
    song_tools.set_song(tempo=102)
    assert project.save_set() == {"saved": True, "path": first}
    assert project.open_set(first)["already_open"] is True
    second = project.save_set(os.path.join(folder, "AbletonMCP UI Test 2.als"))["path"]
    song_tools.set_song(tempo=103)  # unsaved change in the second set
    document = status_tools.get_status()["set"]["document"]
    with pytest.raises(ToolError) as error:
        project.open_set(first)  # refused: Live's save prompt is left open
    assert "unsaved changes" in str(error.value)
    dialog = status_tools.get_status()["dialog"]
    assert dialog and dialog["buttons"] == 3, dialog
    status_tools.respond_to_dialog("cancel")  # verifies the button order: the set must stay open, unsaved
    after = status_tools.get_status()
    assert after["dialog"] is None and after["set"]["document"] == document and after["set"]["path"] == second
    assert lom_value(live, "live_set", "tempo") == 103.0
    opened = project.open_set(first, discard_unsaved=True)
    assert opened["opened"] and opened["set"]["path"] == first
    assert lom_value(live, "live_set", "tempo") == 102.0
    exported = project.export_audio(os.path.join(folder, "mix.wav"), 0, 8)
    assert os.path.getsize(exported["path"]) > 0
