"""Unit tests for drum step patterns (MCP_Server/theory.py) and the clip tools' local preprocessing."""
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server import theory
from MCP_Server.theory import TheoryError
from MCP_Server.tools import clips as clip_tools


def lane(lanes, drum):
    return next(item for item in lanes if item["drum"] == drum)


# ---------------------------------------------------------------------------
# Step patterns
# ---------------------------------------------------------------------------


def test_four_on_the_floor_sixteenths():
    lanes = theory.drum_lanes({"Kick": "x---x---x---x---", "Snare": "----x-------x---"})
    kick = lane(lanes, "Kick")
    assert kick["steps"] == 16 and kick["cycle"] == 4.0 and kick["gm"] == 36
    assert kick["hits"] == [[0.0, 0.25, 100], [1.0, 0.25, 100], [2.0, 0.25, 100], [3.0, 0.25, 100]]
    assert [hit[0] for hit in lane(lanes, "Snare")["hits"]] == [1.0, 3.0]


def test_accents_ghosts_and_rests():
    hits = theory.drum_lanes({"Snare": "X.o-x_"})[0]["hits"]
    assert [(hit[0], hit[2]) for hit in hits] == [(0.0, 127), (0.5, 60), (1.0, 100)]


def test_custom_velocities_and_aliases():
    hits = theory.drum_lanes({"Hat": "xXo"}, velocities={"normal": 80, "accent": 110, "o": 30})[0]["hits"]
    assert [hit[2] for hit in hits] == [80, 110, 30]
    assert [hit[2] for hit in theory.drum_lanes({"Hat": "x"}, velocities={"x": 64})[0]["hits"]] == [64]


def test_separators_are_ignored():
    lanes = theory.drum_lanes({"Kick": "x--- x---|x--- x---", "Hat": "x.x.\nx.x."})
    assert lane(lanes, "Kick")["steps"] == 16 and len(lane(lanes, "Kick")["hits"]) == 4
    assert lane(lanes, "Hat")["steps"] == 8 and lane(lanes, "Hat")["cycle"] == 2.0


def test_swing_delays_odd_steps_and_shortens_notes():
    hits = theory.drum_lanes({"Hat": "xxxx"}, swing=0.5)[0]["hits"]
    assert [hit[0] for hit in hits] == [0.0, 0.3125, 0.5, 0.8125]
    assert all(hit[1] == 0.1875 for hit in hits)
    assert theory.drum_lanes({"Hat": "xxxx"}, swing=0)[0]["hits"][1][0] == 0.25


def test_steps_per_beat_and_per_lane_cycles():
    lanes = theory.drum_lanes({"Triplet": "xxx", "Eighths": "x-x-x-"}, steps_per_beat=3)
    assert [hit[0] for hit in lane(lanes, "Triplet")["hits"]] == [0.0, 0.333333, 0.666667]
    assert lane(lanes, "Triplet")["cycle"] == 1.0 and lane(lanes, "Eighths")["cycle"] == 2.0
    poly = theory.drum_lanes({"Kick": "x---", "Perc": "x--"})
    assert lane(poly, "Kick")["cycle"] == 1.0 and lane(poly, "Perc")["cycle"] == 0.75


def test_numbers_and_note_names_have_no_gm_entry():
    lanes = theory.drum_lanes({"36": "x", "C#1": "x", "Kick 808": "x"})
    assert [item["gm"] for item in lanes] == [None, None, None]


@pytest.mark.parametrize("pattern, kwargs, message", [
    ({}, {}, "pattern must map"),
    ("x---", {}, "pattern must map"),
    ({"Kick": "x-y-"}, {}, "'y' at step 3"),
    ({"Kick": ""}, {}, "empty"),
    ({"Kick": " | "}, {}, "empty"),
    ({"Kick": ["x", "-"]}, {}, "must be a string"),
    ({"": "x"}, {}, "must not be empty"),
    ({"Kick": "x"}, {"swing": 1.5}, "swing"),
    ({"Kick": "x"}, {"swing": True}, "swing"),
    ({"Kick": "x"}, {"steps_per_beat": 0}, "steps_per_beat"),
    ({"Kick": "x"}, {"steps_per_beat": 2.5}, "steps_per_beat"),
    ({"Kick": "x"}, {"velocities": {"loud": 120}}, "velocities keys"),
    ({"Kick": "x"}, {"velocities": {"x": 0}}, "1..127"),
    ({"Kick": "x"}, {"velocities": {"X": 200}}, "1..127"),
])
def test_pattern_errors(pattern, kwargs, message):
    with pytest.raises(TheoryError, match=message):
        theory.drum_lanes(pattern, **kwargs)


@pytest.mark.parametrize("name, pitch", [
    ("kick", 36), ("Kick", 36), ("BD", 36), ("bass drum", 36), ("kicks", 36), ("snare", 38), ("Clap", 39), ("claps", 39),
    ("rim", 37), ("closed hat", 42), ("Closed-HiHat", 42), ("hi hat", 42), ("hh", 42), ("hats", 42), ("pedal hat", 44),
    ("open hat", 46), ("OH", 46), ("low tom", 45), ("mid tom", 47), ("high tom", 50), ("floor tom", 41), ("crash", 49),
    ("ride", 51), ("ride bell", 53), ("tambourine", 54), ("cowbell", 56), ("shaker", 70), ("triangle", 81), ("conga", 63),
])
def test_gm_drum_names(name, pitch):
    assert theory.gm_drum(name) == pitch


def test_gm_drum_unknown_and_complete_map():
    assert theory.gm_drum("theremin") is None
    assert sorted(theory.GM_DRUMS) == list(range(35, 82))


# ---------------------------------------------------------------------------
# Tool preprocessing (no Live: call() is replaced)
# ---------------------------------------------------------------------------


class Calls(list):
    """call() stand-in: records (command, params without None) and replies from `responses`."""

    def __init__(self):
        list.__init__(self)
        self.responses = []

    def __call__(self, command, timeout=None, **params):
        self.append((command, dict((key, value) for key, value in params.items() if value is not None)))
        return self.responses.pop(0) if self.responses else {"ok": True}


@pytest.fixture
def calls(monkeypatch):
    recorded = Calls()
    monkeypatch.setattr(clip_tools, "call", recorded)
    return recorded


def test_write_drum_pattern_sends_parsed_lanes(calls):
    clip_tools.write_drum_pattern(track="Drums", slot=0, pattern={"Kick": "x---"}, swing=0.2, mode="add")
    command, params = calls[0]
    assert command == "write_drum_pattern" and params["mode"] == "add" and params["track"] == "Drums" and params["slot"] == 0
    assert params["lanes"][0]["drum"] == "Kick" and params["lanes"][0]["gm"] == 36 and params["lanes"][0]["hits"][0][0] == 0.0


def test_write_drum_pattern_rejects_bad_steps_without_calling_live(calls):
    with pytest.raises(ToolError, match="step 2"):
        clip_tools.write_drum_pattern(track="Drums", slot=0, pattern={"Kick": "xz"})
    assert calls == []


def test_write_notes_expands_chord_shorthand(calls):
    clip_tools.write_notes(track="Keys", slot=1, notes=[{"chord": "Dm7", "start": 0, "duration": 4, "octave": 2},
                                                        {"pitch": "A3", "start": 4, "duration": 1}], mode="replace")
    command, params = calls[0]
    assert command == "write_notes" and params["mode"] == "replace"
    assert params["notes"][0] == {"start": 0, "duration": 4, "pitches": [50, 53, 57, 60]}
    assert params["notes"][1] == {"pitch": "A3", "start": 4, "duration": 1}
    with pytest.raises(ToolError):
        clip_tools.write_notes(track="Keys", slot=1, notes=[{"chord": "Hm7", "start": 0, "duration": 1}])
    assert len(calls) == 1


def test_progression_notes_feed_write_notes(calls):
    progression = theory.progression_info("A minor", "i-iv-V7-i", octave=2)
    clip_tools.write_notes(track="Keys", slot=0, notes=progression["notes"])
    sent = calls[0][1]["notes"]
    assert sent == progression["notes"] and sent[2] == {"pitches": [52, 56, 59, 62], "start": 8.0, "duration": 4.0}


def test_clip_action_waits_for_conversions(calls, monkeypatch):
    monkeypatch.setattr(clip_tools.time, "sleep", lambda seconds: None)
    calls.responses = [
        {"action": "audio_to_midi", "pending": True, "job": 4, "clip": {"track": 2}},
        {"done": False, "seconds": 0.1},
        {"done": True, "new_tracks": [{"track": 3, "name": "Melody", "kind": "midi"}], "seconds": 0.3},
    ]
    out = clip_tools.clip_action(track="Vox", slot=0, action="audio_to_midi", args={"type": "melody"})
    assert out == {"action": "audio_to_midi", "clip": {"track": 2}, "new_tracks": [{"track": 3, "name": "Melody", "kind": "midi"}], "seconds": 0.3}
    assert [command for command, _ in calls] == ["clip_action", "clips_conversion_status", "clips_conversion_status"]
    assert calls[1][1] == {"job": 4}


def test_clip_action_passes_plain_results_through(calls):
    calls.responses = [{"action": "crop", "clip": {"name": "A"}}]
    assert clip_tools.clip_action(track=0, slot=0, action="crop") == {"action": "crop", "clip": {"name": "A"}}
    assert calls[0] == ("clip_action", {"track": 0, "slot": 0, "action": "crop"})
