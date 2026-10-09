"""Unit tests for generic object-model access: lists of Live objects are windows of names, explicitly truncated.

On 2026-10-08 an agent's cleanup looked scratch tracks up with `name in items` on a 36-track set; lom_get showed
only the first 32 names, so the tracks past index 31 were never deleted. These fakes stand in for Live objects.
"""
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from AbletonMCP_Remote_Script import lom
from AbletonMCP_Remote_Script.errors import CommandError
from AbletonMCP_Remote_Script.handlers import lom as handlers
from MCP_Server.tools import listening, lom as lom_tools


class Named(object):
    """A Live object as lom recognises one (it has a canonical_parent), with a name."""
    canonical_parent = None

    def __init__(self, name):
        self.name = name


class Unnamed(object):
    canonical_parent = None

    @property
    def name(self):
        raise RuntimeError("no name")


class Song(object):
    canonical_parent = None

    def __init__(self, count):
        self._tracks = tracks(count)

    @property
    def tracks(self):
        return self._tracks

    @property
    def return_tracks(self):
        return []

    @property
    def scenes(self):
        return []

    @property
    def tempo(self):
        return 120.0

    def delete_track(self, index):
        del self._tracks[index]


class Context(object):
    def __init__(self, song):
        self.song = song
        self.app = None


class Connection(object):
    """A connection to Live answered by the real lom handlers, on a fake song."""

    def __init__(self, song):
        self.ctx = Context(song)
        self.log = []

    def send_command(self, command, params=None, timeout=None):
        self.log.append((command, params))
        return {"lom_get": handlers.lom_get, "lom_call": handlers.lom_call}[command](self.ctx, **(params or {}))


def tracks(count):
    return [Named("Track {0}".format(index)) for index in range(count)]


def names(first, stop):
    return ["Track {0}".format(index) for index in range(first, stop)]


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------


def test_a_short_list_is_complete():
    assert lom.summarize(tracks(3)) == {"count": 3, "items": names(0, 3)}


def test_a_list_as_long_as_the_limit_is_complete():
    assert lom.summarize(tracks(32)) == {"count": 32, "items": names(0, 32)}
    assert lom.summarize(tracks(36), limit=36) == {"count": 36, "items": names(0, 36)}


def test_a_longer_list_says_it_is_truncated():
    summary = lom.summarize(tracks(36))
    assert summary == {"count": 36, "items": names(0, 32), "truncated": True, "offset": 0, "shown": 32}
    assert "Track 35" not in summary["items"]  # it exists all the same, which `truncated` says


def test_offset_and_limit_choose_the_window():
    assert lom.summarize(tracks(36), offset=32) == {"count": 36, "items": names(32, 36), "truncated": True, "offset": 32, "shown": 4}
    assert lom.summarize(tracks(36), offset=4, limit=2) == {"count": 36, "items": names(4, 6), "truncated": True, "offset": 4, "shown": 2}


def test_an_offset_past_the_end_gives_an_empty_window():
    assert lom.summarize(tracks(36), offset=40) == {"count": 36, "items": [], "truncated": True, "offset": 40, "shown": 0}


def test_pages_cover_every_item_once():
    found = []
    while True:
        summary = lom.summarize(tracks(100), offset=len(found), limit=32)
        found += summary["items"]
        if len(found) >= summary["count"]:
            break
    assert found == names(0, 100)


def test_an_unreadable_name_shows_the_type():
    assert lom.summarize([Named("Bass"), Unnamed()]) == {"count": 2, "items": ["Bass", "Unnamed"]}


def test_values_and_single_objects_are_not_windowed():
    assert lom.summarize(list(range(40))) == {"value": list(range(40))}
    assert lom.summarize([]) == {"value": []}
    assert lom.summarize(Named("Bass")) == {"object": "Named", "name": "Bass"}
    assert lom.summarize(120.0) == {"value": 120.0}


# ---------------------------------------------------------------------------
# check_window, describe and the lom_get handler
# ---------------------------------------------------------------------------


def test_check_window_fills_in_the_defaults():
    assert lom.check_window() == (0, 32)
    assert lom.check_window(None, None) == (0, 32)
    assert lom.check_window(40, 1000) == (40, 1000)


@pytest.mark.parametrize("offset, limit", [(-1, 32), (0, 0), (0, 1001), (True, 32), (0, True), (1.0, 32), (0, "32")])
def test_check_window_rejects(offset, limit):
    with pytest.raises(CommandError) as error:
        lom.check_window(offset, limit)
    assert error.value.code == "invalid_argument"
    assert "offset must be an integer >= 0 and limit an integer from 1 to 1000" in error.value.message


def test_describe_windows_every_list_property():
    properties = lom.describe(Song(36), "live_set", offset=30, limit=4)["properties"]
    assert properties["tracks"] == {"settable": False, "count": 36, "items": names(30, 34), "truncated": True, "offset": 30, "shown": 4}
    assert properties["tempo"] == {"settable": False, "value": 120.0}


def test_lom_get_windows_list_properties():
    ctx = Context(Song(36))
    assert handlers.lom_get(ctx, "live_set", ["tracks"])["values"]["tracks"]["truncated"] is True
    page = handlers.lom_get(ctx, "live_set", ["tracks", "tempo"], offset=32)
    assert page == {"path": "live_set", "values": {
        "tracks": {"count": 36, "items": names(32, 36), "truncated": True, "offset": 32, "shown": 4},
        "tempo": {"value": 120.0},
    }}
    assert handlers.lom_get(ctx, "live_set", ["tracks"], limit=1000)["values"]["tracks"] == {"count": 36, "items": names(0, 36)}


def test_lom_get_windows_a_path_that_is_a_list():
    ctx = Context(Song(36))
    assert handlers.lom_get(ctx, "live_set tracks", offset=34) == {
        "path": "live_set tracks", "count": 36, "items": names(34, 36), "truncated": True, "offset": 34, "shown": 2}
    assert handlers.lom_get(ctx, "live_set tracks 35", ["name"])["values"]["name"] == {"value": "Track 35"}
    assert handlers.lom_get(ctx, "live_set tempo") == {"path": "live_set tempo", "value": 120.0}


def test_lom_get_rejects_a_bad_window_before_reading():
    with pytest.raises(CommandError) as error:
        handlers.lom_get(Context(Song(3)), "live_set nowhere", ["tracks"], limit=0)
    assert error.value.code == "invalid_argument"


# ---------------------------------------------------------------------------
# Callers that look names up: the live tests' scratch cleanup, lom_names, takes()
# ---------------------------------------------------------------------------


def test_scratch_cleanup_deletes_tracks_past_the_first_32():
    from tests.live.conftest import Scratch, track_names
    song = Song(34)
    song.tracks.extend([Named("[test:x] a"), Named("[test:x] b")])  # indices 34 and 35 of 36
    live = Connection(song)
    assert track_names(live) == names(0, 34) + ["[test:x] a", "[test:x] b"]
    Scratch(live, "x").cleanup()
    assert [track.name for track in song.tracks] == names(0, 34)


def fake_live(song):
    """A call() answered by the real lom handlers on a fake song; bounce_song_info gives `song_info`."""
    connection = Connection(song)

    def call(command, timeout=None, **params):
        if command == "bounce_song_info":
            return call.song_info
        return connection.send_command(command, params)
    call.log, call.song_info = connection.log, {}
    return call


def test_the_tool_passes_the_window_on(monkeypatch):
    live = fake_live(Song(36))
    monkeypatch.setattr(lom_tools, "call", live)
    assert lom_tools.lom_get("live_set", ["tracks"], offset=32, limit=10)["values"]["tracks"]["items"] == names(32, 36)
    assert live.log == [("lom_get", {"path": "live_set", "properties": ["tracks"], "offset": 32, "limit": 10})]


def test_lom_names_pages_through_every_name(monkeypatch):
    live = fake_live(Song(2345))
    monkeypatch.setattr(lom_tools, "call", live)
    assert lom_tools.lom_names("live_set", "tracks") == names(0, 2345)
    assert [params["offset"] for _, params in live.log] == [0, 1000, 2000]


def test_lom_names_of_an_empty_list(monkeypatch):
    monkeypatch.setattr(lom_tools, "call", fake_live(Song(0)))
    assert lom_tools.lom_names("live_set", "tracks") == []


def test_lom_names_raises_when_the_list_cannot_be_read(monkeypatch):
    monkeypatch.setattr(lom_tools, "call", fake_live(Song(3)))
    with pytest.raises(ToolError, match="Cannot read 'live_set cue_points'"):
        lom_tools.lom_names("live_set", "cue_points")


def test_takes_finds_left_behind_takes_by_tracks_past_the_first_32(tmp_path, monkeypatch):
    import ears
    monkeypatch.delenv("EARS_HOME", raising=False)
    monkeypatch.setattr(ears, "DEFAULT_ROOT", tmp_path / "Ears")
    untitled = tmp_path / "Ears" / "untitled"
    (untitled / "takes" / "nova-120-A-0001").mkdir(parents=True)
    (untitled / "ledger.jsonl").write_text("{}\n")
    # The untitled take recorded the set's last tracks, which sit past the first window of 32 names.
    snapshot = {"tracks": [{"name": name} for name in names(33, 40)]}
    (untitled / "takes" / "nova-120-A-0001" / "snapshot.json").write_text(json.dumps(snapshot))
    live = fake_live(Song(40))
    live.song_info = {"set_path": str(tmp_path / "NOVA Project" / "NOVA.als"), "set_name": "NOVA"}
    monkeypatch.setattr(listening, "call", live)
    monkeypatch.setattr(lom_tools, "call", live)
    out = listening.takes()
    assert out["takes"] == [] and str(untitled) in out["hint"]
