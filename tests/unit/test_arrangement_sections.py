"""Unit tests for WS-F arrangement logic: section math, clip resizing and locator orchestration."""
import pytest

from AbletonMCP_Remote_Script.errors import CommandError
from AbletonMCP_Remote_Script.handlers import arrangement
from MCP_Server.tools import arrangement as arrangement_tools


class Song(object):
    def __init__(self, numerator=4, denominator=4):
        self.signature_numerator = numerator
        self.signature_denominator = denominator


# ---------------------------------------------------------------------------
# Section math
# ---------------------------------------------------------------------------


def test_section_bounds_are_consecutive():
    assert arrangement.section_bounds(0.0, [8.0, 6.0, 16.0]) == [(0.0, 8.0), (8.0, 14.0), (14.0, 30.0)]
    assert arrangement.section_bounds(64.0, [4.0]) == [(64.0, 68.0)]


@pytest.mark.parametrize("section, beats", [
    ({"scene": 0, "bars": 2}, 8.0),
    ({"scene": 0, "bars": 1.5}, 6.0),
    ({"scene": 0, "length": 6}, 6.0),
    ({"scene": 0, "length": "3 bars"}, 12.0),
    ({"scene": 0, "length": "5 beats"}, 5.0),
])
def test_section_length_four_four(section, beats):
    assert arrangement.section_length(Song(), section, 0) == beats


def test_section_length_follows_the_meter():
    assert arrangement.section_length(Song(6, 8), {"scene": 0, "bars": 2}, 0) == 6.0
    assert arrangement.section_length(Song(3, 4), {"scene": 0, "bars": 4}, 0) == 12.0


@pytest.mark.parametrize("section", [
    {"scene": 0},
    {"scene": 0, "bars": 2, "length": 8},
    {"scene": 0, "bars": 0},
    {"scene": 0, "bars": -1},
    {"scene": 0, "bars": True},
    {"scene": 0, "length": "lots"},
    "verse",
])
def test_section_length_rejects(section):
    with pytest.raises(CommandError) as error:
        arrangement.section_length(Song(), section, 3)
    assert error.value.code == "invalid_argument"


def test_overlap_and_inside_tests_use_half_open_ranges():
    assert arrangement.overlaps(0.0, 4.0, 2.0, 6.0)
    assert not arrangement.overlaps(0.0, 4.0, 4.0, 8.0)      # touching edges do not overlap
    assert not arrangement.overlaps(8.0, 12.0, 4.0, 8.0)
    assert arrangement.inside(4.0, 8.0, 4.0, 8.0)
    assert not arrangement.inside(3.0, 8.0, 4.0, 8.0)


# ---------------------------------------------------------------------------
# set_extent against a model of Live's arrangement clip (verified behaviour, docs/spikes.md)
# ---------------------------------------------------------------------------


class FakeClip(object):
    """Arrangement clip model of the verified behaviour: unlooped, the extent spans loop_start..loop_end
    in clip units (beats, or seconds for unwarped audio) and loop_end moves the end; looping again
    restores the loop region and keeps the extent; looped, loop edits never change the extent."""

    def __init__(self, start, loop_start, loop_end, looping=True, units_per_beat=1.0, start_marker=None):
        self.start_time = start
        self.units = units_per_beat
        self.saved_loop = (loop_start, loop_end)
        self.start_marker = loop_start if start_marker is None else start_marker
        self.end_marker = loop_end
        self._looping = looping
        self.loop_start, self._loop_end = (loop_start, loop_end) if looping else (self.start_marker, loop_end)
        self.end_time = start + (loop_end - loop_start) / units_per_beat
        self.history = []

    @property
    def loop_end(self):
        return self._loop_end

    @loop_end.setter
    def loop_end(self, value):
        self.history.append(("loop_end", value))
        self._loop_end = value
        if not self._looping:
            self.end_time = self.start_time + (value - self.loop_start) / self.units

    @property
    def looping(self):
        return self._looping

    @looping.setter
    def looping(self, value):
        self.history.append(("looping", value))
        if value and not self._looping:
            self.end_marker = self._loop_end
            self._looping = True
            self.loop_start, self._loop_end = self.saved_loop
        elif not value and self._looping:
            self._looping = False
            self.loop_start = self.start_marker
            self.end_time = self.start_time + (self._loop_end - self.loop_start) / self.units


def test_set_extent_extends_and_restores_the_loop():
    clip = FakeClip(400.0, 0.0, 4.0)
    assert arrangement.set_extent(clip, 10.0) == pytest.approx(10.0)
    assert clip.looping and (clip.loop_start, clip.loop_end) == (0.0, 4.0)
    assert clip.end_time == pytest.approx(410.0)


def test_set_extent_shrinks():
    clip = FakeClip(0.0, 0.0, 4.0)
    assert arrangement.set_extent(clip, 2.5) == pytest.approx(2.5)
    assert clip.looping


def test_set_extent_with_a_start_marker_offset():
    clip = FakeClip(400.0, 0.0, 4.0, start_marker=1.0)
    assert arrangement.set_extent(clip, 10.0) == pytest.approx(10.0)
    assert clip.start_marker == 1.0


def test_set_extent_converts_seconds_for_unwarped_audio():
    clip = FakeClip(0.0, 0.0, 4.0, looping=False, units_per_beat=0.5)  # 120 BPM: 0.5 s per beat
    assert clip.end_time == pytest.approx(8.0)
    assert arrangement.set_extent(clip, 2.0) == pytest.approx(2.0)
    assert clip.loop_end == pytest.approx(1.0)
    assert ("looping", True) not in clip.history


def test_set_extent_no_change_is_a_no_op():
    clip = FakeClip(0.0, 0.0, 4.0)
    assert arrangement.set_extent(clip, 4.0) == 4.0
    assert clip.history == []


# ---------------------------------------------------------------------------
# Locator orchestration in the MCP tool (one call per locator, then restore the playhead)
# ---------------------------------------------------------------------------


def test_add_locators_retries_pending_and_chains_the_playhead(monkeypatch):
    calls = []
    answers = iter([
        {"status": "pending", "time": 0.0},
        {"status": "done", "created": True, "locator": {"name": "Intro", "time": {"beats": 0.0}}},
        {"status": "done", "created": False, "renamed_from": "old", "locator": {"name": "Verse", "time": {"beats": 16.0}}},
    ])

    def fake_call(command, timeout=None, **params):
        calls.append((command, params))
        return next(answers)

    monkeypatch.setattr(arrangement_tools, "call", fake_call)
    created, errors = arrangement_tools._add_locators([{"time": 0.0, "name": "Intro"}, {"time": 16.0, "name": "Verse"}], 3.5)
    assert errors == []
    assert [item["name"] for item in created] == ["Intro", "Verse"]
    assert created[1]["existing"] is True and created[1]["renamed_from"] == "old"
    assert [params["then"] for _, params in calls] == [16.0, 16.0, 3.5]


def test_add_locators_reports_errors_and_stops_when_playing(monkeypatch):
    from MCP_Server.app import LiveToolError
    from MCP_Server.connection import AbletonError

    def fake_call(command, timeout=None, **params):
        raise LiveToolError(AbletonError("busy", "Live is playing; locators are created at the playhead"))

    monkeypatch.setattr(arrangement_tools, "call", fake_call)
    created, errors = arrangement_tools._add_locators([{"time": 0.0, "name": "A"}, {"time": 8.0, "name": "B"}], 0.0)
    assert created == [] and len(errors) == 1 and "playing" in errors[0]["error"]


def test_arrange_tool_turns_pending_locators_into_results(monkeypatch):
    def fake_call(command, timeout=None, **params):
        if command == "arrange_from_scenes":
            assert timeout and params["start"] == "1.1.1"
            return {"sections": [], "locators_pending": [{"time": 0.0, "name": "A"}], "playhead_restore": 2.0}
        return {"status": "done", "created": True, "locator": {"name": "A", "time": {"beats": 0.0}}}

    monkeypatch.setattr(arrangement_tools, "call", fake_call)
    result = arrangement_tools.arrange_from_scenes([{"scene": 0, "bars": 1}])
    assert "locators_pending" not in result and "playhead_restore" not in result
    assert result["locators"] == [{"name": "A", "time": {"beats": 0.0}}]


def test_arrange_tool_resumes_and_merges_partial_calls(monkeypatch):
    sections = [{"index": 0, "name": "A"}, {"index": 1, "name": "B"}]
    replies = iter([
        {"sections": [dict(s) for s in sections], "placed": [{"section": 0, "track": "Drums", "automated": True}],
         "cleared": {"deleted": 3, "trimmed": 1}, "resume": 1},
        {"sections": [dict(s) for s in sections], "placed": [{"section": 0, "track": "Bass", "automated": False},
                                                              {"section": 1, "track": "Drums", "automated": False}],
         "cleared": {"deleted": 0, "trimmed": 0}, "warnings": ["w"]},
    ])
    resumes = []

    def fake_call(command, timeout=None, **params):
        assert command == "arrange_from_scenes"
        resumes.append(params["resume"])
        return next(replies)

    monkeypatch.setattr(arrangement_tools, "call", fake_call)
    result = arrangement_tools.arrange_from_scenes([{"scene": 0, "bars": 1}, {"scene": 1, "bars": 1}], clear=True, locators=False)
    assert resumes == [0, 1]
    assert result["sections"][0]["tracks"] == ["Drums", "Bass"] and result["sections"][0]["automated"] == ["Drums"]
    assert result["sections"][1]["tracks"] == ["Drums"] and "automated" not in result["sections"][1]
    assert result["clips_placed"] == 3 and result["cleared"] == {"deleted": 3, "trimmed": 1}
    assert result["warnings"] == ["w"] and result["undo_steps"] == 2 and "resume" not in result


def test_clear_tool_resumes_and_sums(monkeypatch):
    replies = iter([
        {"mode": "trim", "deleted": 2, "trimmed": 1, "tracks": [{"name": "A", "deleted": 2, "trimmed": 1, "remaining": 3}], "resume": 1},
        {"mode": "trim", "deleted": 5, "trimmed": 1, "tracks": [{"name": "A", "deleted": 0, "trimmed": 1, "remaining": 4},
                                                                {"name": "B", "deleted": 5, "trimmed": 0, "remaining": 0}]},
    ])
    monkeypatch.setattr(arrangement_tools, "call", lambda command, timeout=None, **params: next(replies))
    result = arrangement_tools.clear_arrangement(tracks=["A", "B"])
    assert result["deleted"] == 7 and result["trimmed"] == 2
    assert result["tracks"] == [{"name": "A", "deleted": 2, "trimmed": 2, "remaining": 4}, {"name": "B", "deleted": 5, "trimmed": 0, "remaining": 0}]
    assert result["undo_steps"] == 2 and "resume" not in result


def test_resume_index_validation():
    assert arrangement.resume_index(0, 0) == 0 and arrangement.resume_index(3, 5) == 3
    for bad in (-1, 6, 1.5, True, "2"):
        with pytest.raises(CommandError):
            arrangement.resume_index(bad, 5)


class Bounds(object):
    def __init__(self, loop_start, loop_end, start_marker, end_marker, audio=False, warping=True):
        self.loop_start, self.loop_end, self.start_marker, self.end_marker = loop_start, loop_end, start_marker, end_marker
        self.is_audio_clip, self.warping = audio, warping


def test_natural_bound_covers_the_spiked_extents():
    # spikes: loop 0..4 -> 4 beats; start marker 1 in loop 0..4 -> 4; pre-roll start 0, loop 2..6 -> 6
    assert arrangement.natural_bound(Bounds(0.0, 4.0, 0.0, 4.0)) >= 4.0
    assert arrangement.natural_bound(Bounds(0.0, 4.0, 1.0, 4.0)) >= 4.0
    assert arrangement.natural_bound(Bounds(2.0, 6.0, 0.0, 4.0)) >= 6.0
    assert arrangement.natural_bound(Bounds(0.0, 4.0, 0.0, 8.0, audio=True)) == 8.0
    assert arrangement.natural_bound(Bounds(0.0, 4.0, 0.0, 8.0, audio=True, warping=False)) is None
