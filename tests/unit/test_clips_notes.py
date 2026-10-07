"""Unit tests for the pure logic of the clips handler: units, note input, filters, transforms, gain, drums."""
import math

import pytest

from AbletonMCP_Remote_Script import core
from AbletonMCP_Remote_Script.errors import CommandError

# Load every handler module (idempotent) rather than importing only this one, so core.COMMANDS stays
# complete for any test that inspects the registry.
core.load_handlers()
from AbletonMCP_Remote_Script.handlers import clips  # noqa: E402


class Meter(object):
    def __init__(self, numerator=4, denominator=4):
        self.signature_numerator = numerator
        self.signature_denominator = denominator


def note(note_id, pitch, start, duration=1.0, velocity=100.0):
    return {"note_id": note_id, "pitch": pitch, "start": float(start), "duration": float(duration), "velocity": float(velocity),
            "probability": 1.0, "velocity_deviation": 0.0, "release_velocity": 64.0, "mute": False}


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text, beats", [("1/16", 0.25), ("1/8", 0.5), ("1/4", 1.0), ("1/2", 2.0), ("1/1", 4.0), ("3/8", 1.5),
                                         ("1/4.", 1.5), ("1/8T", 1 / 3.0), ("1/16t", 1 / 6.0), (" 1 / 16 ", 0.25)])
def test_note_value_beats(text, beats):
    assert clips.note_value_beats(text) == pytest.approx(beats)


@pytest.mark.parametrize("text", ["1/0", "0/4", "x", "1.5", "2 bars", None, 4])
def test_note_value_beats_rejects(text):
    assert clips.note_value_beats(text) is None


def test_parse_length_units():
    assert clips.parse_length(Meter(), 3) == 3.0
    assert clips.parse_length(Meter(), "2 bars") == 8.0
    assert clips.parse_length(Meter(3, 4), "2 bars") == 6.0
    assert clips.parse_length(Meter(6, 8), "1 bar") == 3.0
    assert clips.parse_length(Meter(), "1/8") == 0.5
    assert clips.parse_length(Meter(), "3 beats") == 3.0
    for bad in ("soon", 0, -1, True):
        with pytest.raises(CommandError):
            clips.parse_length(Meter(), bad)


def test_parse_grid():
    assert clips.parse_grid(Meter(), "1/16") == 0.25
    assert clips.parse_grid(Meter(), "1/8T") == pytest.approx(1 / 3.0)
    assert clips.parse_grid(Meter(), "1 bar") == 4.0
    assert clips.parse_grid(Meter(), 0.5) == 0.5
    with pytest.raises(CommandError):
        clips.parse_grid(Meter(), None)


def test_parse_clip_time_uses_clip_meter():
    assert clips.parse_clip_time(Meter(), "2.1.1", "start") == 4.0
    assert clips.parse_clip_time(Meter(3, 4), "2.1.1", "start") == 3.0
    assert clips.parse_clip_time(Meter(), "1.2.3", "start") == 1.5
    assert clips.parse_clip_time(Meter(), 2.5, "start") == 2.5


@pytest.mark.parametrize("value, tempo, beats", [("10ms", 120, 0.02), ("20 ms", 90, 0.03), ("500MS", 60, 0.5), (0.05, 120, 0.05),
                                                 ("0.1", 120, 0.1), ("0.1 beats", 120, 0.1)])
def test_parse_timing(value, tempo, beats):
    assert clips.parse_timing(value, tempo) == pytest.approx(beats)


@pytest.mark.parametrize("bad", ["10 sec", "fast", -0.1, True])
def test_parse_timing_rejects(bad):
    with pytest.raises(CommandError):
        clips.parse_timing(bad, 120)


@pytest.mark.parametrize("signature, parsed", [("3/4", (3, 4)), (" 7 / 8 ", (7, 8)), ([5, 4], (5, 4)), ("12/16", (12, 16))])
def test_parse_signature(signature, parsed):
    assert clips._parse_signature(signature) == parsed


@pytest.mark.parametrize("bad", ["3:4", "3/5", "0/4", "4/0", 34, "100/4"])
def test_parse_signature_rejects(bad):
    with pytest.raises(CommandError):
        clips._parse_signature(bad)


def test_number_and_flag_validators():
    assert clips._number("2.5", "x") == 2.5
    assert clips._number(3.0, "x", integer=True) == 3
    for bad in (True, "abc", float("nan"), float("inf"), None):
        with pytest.raises(CommandError):
            clips._number(bad, "x")
    with pytest.raises(CommandError, match="within 0..1"):
        clips._number(2, "x", 0, 1)
    with pytest.raises(CommandError, match="whole number"):
        clips._number(2.5, "x", integer=True)
    assert clips._flag(True, "f") is True and clips._flag(0, "f") is False and clips._flag("on", "f") is True
    with pytest.raises(CommandError):
        clips._flag("maybe", "f")


# ---------------------------------------------------------------------------
# Note input
# ---------------------------------------------------------------------------


def test_normalize_notes_defaults_names_and_bar_times():
    out = clips.normalize_notes(Meter(), [{"pitch": "C3", "start": "1.2.1", "duration": "1/8"}, {"pitch": 64, "start": 2, "duration": 1, "velocity": 90.5}])
    assert out[0] == {"pitch": 60, "start": 1.0, "duration": 0.5, "velocity": 100.0, "probability": 1.0, "velocity_deviation": 0.0,
                      "release_velocity": 64.0, "mute": False}
    assert out[1]["velocity"] == 90.5 and out[1]["pitch"] == 64


def test_normalize_notes_chords_and_get_notes_passthrough():
    out = clips.normalize_notes(Meter(), [{"pitches": ["C3", "E3", 67], "start": 0, "duration": 4, "mute": True}])
    assert [item["pitch"] for item in out] == [60, 64, 67] and all(item["mute"] for item in out)
    read_back = {"note_id": 7, "pitch": 62, "name": "D3", "start": 0.5, "duration": 0.25, "velocity": 80, "probability": 0.5,
                 "velocity_deviation": -10, "release_velocity": 30, "mute": False}
    copied = clips.normalize_notes(Meter(), [read_back])[0]
    assert copied == {"pitch": 62, "start": 0.5, "duration": 0.25, "velocity": 80.0, "probability": 0.5, "velocity_deviation": -10.0,
                      "release_velocity": 30.0, "mute": False}
    assert clips.normalize_notes(Meter(), [{"name": "A2", "start": 0, "duration": 1}])[0]["pitch"] == 57


def test_normalize_notes_uses_clip_meter_for_bar_times():
    assert clips.normalize_notes(Meter(3, 4), [{"pitch": 60, "start": "2.1.1", "duration": "1 bar"}])[0]["start"] == 3.0
    assert clips.normalize_notes(Meter(3, 4), [{"pitch": 60, "start": "2.1.1", "duration": "1 bar"}])[0]["duration"] == 3.0


@pytest.mark.parametrize("bad, message", [
    ([], "non-empty"),
    ("C3", "non-empty"),
    ([5], "must be an object"),
    ([{"pitch": 60, "start": 0, "duration": 1, "colour": 3}], "unknown keys colour"),
    ([{"pitch": 60, "duration": 1}], "needs start"),
    ([{"pitch": 60, "start": 0}], "needs duration"),
    ([{"start": 0, "duration": 1}], "needs pitch"),
    ([{"pitch": 60, "pitches": [62], "start": 0, "duration": 1}], "not both"),
    ([{"pitches": [], "start": 0, "duration": 1}], "non-empty list"),
    ([{"pitch": 60, "start": 0, "duration": 1, "velocity": 0}], "velocity"),
    ([{"pitch": 60, "start": 0, "duration": 1, "velocity": 128}], "velocity"),
    ([{"pitch": 60, "start": 0, "duration": 1, "probability": 1.5}], "probability"),
    ([{"pitch": 60, "start": 0, "duration": 1, "velocity_deviation": -200}], "velocity_deviation"),
    ([{"pitch": 60, "start": -1, "duration": 1}], "before the clip start"),
    ([{"pitch": 60, "start": 0, "duration": 0}], "positive"),
    ([{"pitch": 128, "start": 0, "duration": 1}], "MIDI range"),
    ([{"pitch": "H3", "start": 0, "duration": 1}], "note name"),
    ([{"pitch": 60, "start": "1.5.1", "duration": 1}], "bar.beat.sixteenth"),
    ([{"pitch": 60, "start": 0, "duration": 1, "mute": "perhaps"}], "mute"),
])
def test_normalize_notes_errors(bad, message):
    with pytest.raises(CommandError, match=message):
        clips.normalize_notes(Meter(), bad)


def test_note_fields_partial_for_edits():
    assert clips._note_fields(Meter(), {"note_id": 3, "velocity": 70}, "edits[0]", partial=True) == {"velocity": 70.0}
    assert clips._note_fields(Meter(), {"start": "1.1.3", "mute": 1}, "edits[0]", partial=True) == {"start": 0.5, "mute": True}


def test_note_out_is_compact():
    out = clips.note_out(note(4, 61, 1.0, 0.5, 99.5))
    assert out == {"note_id": 4, "pitch": 61, "name": "C#3", "start": 1, "duration": 0.5, "velocity": 99.5, "probability": 1,
                   "velocity_deviation": 0, "release_velocity": 64, "mute": False}


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

NOTES = [note(1, 36, 0.0), note(2, 38, 1.0), note(3, 42, 1.5), note(4, 60, 2.0), note(5, 64, 3.99), note(6, 67, 4.0)]


def _select(**kwargs):
    selector = clips.NoteFilter(Meter(), **kwargs)
    return [item["note_id"] for item in NOTES if selector(item)]


def test_filters_select_and_combine():
    assert _select() == [1, 2, 3, 4, 5, 6]
    assert _select(note_ids=[2, 5]) == [2, 5]
    assert _select(note_ids=3) == [3]
    assert _select(pitches=["C1", 42]) == [1, 3]
    assert _select(pitches="E3") == [5]
    assert _select(pitch_min="C3") == [4, 5, 6]
    assert _select(pitch_max=42) == [1, 2, 3]
    assert _select(pitch_min=38, pitch_max="C3") == [2, 3, 4]
    assert _select(start=1, end=4) == [2, 3, 4, 5]
    assert _select(start="1.2.1", end="2.1.1") == [2, 3, 4, 5]
    assert _select(end=1.5) == [1, 2]
    assert _select(pitch_min=40, start=2) == [4, 5, 6]


def test_filter_validation_and_missing_ids():
    assert clips.NoteFilter(Meter()).empty
    assert not clips.NoteFilter(Meter(), start=0).empty
    with pytest.raises(CommandError, match="above pitch_max"):
        clips.NoteFilter(Meter(), pitch_min=60, pitch_max=50)
    with pytest.raises(CommandError, match="before end"):
        clips.NoteFilter(Meter(), start=4, end=4)
    assert clips.NoteFilter(Meter(), note_ids=[1, 99, 100]).missing_ids(NOTES) == [99, 100]


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

C_MAJOR = [0, 2, 4, 5, 7, 9, 11]
A_MINOR_ROOT = 9
MINOR = [0, 2, 3, 5, 7, 8, 10]


@pytest.mark.parametrize("pitch, steps, root, intervals, expected", [
    (60, 2, 0, C_MAJOR, 64), (60, 7, 0, C_MAJOR, 72), (71, 1, 0, C_MAJOR, 72), (60, -1, 0, C_MAJOR, 59), (65, -3, 0, C_MAJOR, 60),
    (61, 1, 0, C_MAJOR, 63), (60, 0, 0, C_MAJOR, 60), (57, 2, A_MINOR_ROOT, MINOR, 60), (60, 1, A_MINOR_ROOT, MINOR, 62),
    (69, -1, A_MINOR_ROOT, MINOR, 67), (66, 1, 0, [0, 3, 5, 7, 10], 68), (62, 3, 2, [0, 2, 3, 5, 7, 9, 10], 67),
])
def test_scale_step(pitch, steps, root, intervals, expected):
    assert clips.scale_step(pitch, steps, root, intervals) == expected


def test_transpose():
    assert [item["pitch"] for item in clips.transpose_notes(NOTES[:2], semitones=12)] == [48, 50]
    assert [item["pitch"] for item in clips.transpose_notes([note(1, 60, 0), note(2, 64, 1)], steps=2, root=0, intervals=C_MAJOR)] == [64, 67]
    with pytest.raises(CommandError, match="outside 0..127"):
        clips.transpose_notes([note(1, 120, 0)], semitones=12)
    with pytest.raises(CommandError, match="semitones"):
        clips.transpose_notes(NOTES, semitones=1, steps=1)
    assert clips.transpose_notes([note(1, 60, 0)], semitones=0)[0]["note_id"] == 1


def test_quantize_amount_and_origin():
    notes = [note(1, 60, 0.1), note(2, 60, 0.9), note(3, 60, 1.3)]
    assert [item["start"] for item in clips.quantize_notes(notes, 0.5)] == [0.0, 1.0, 1.5]
    assert [round(item["start"], 6) for item in clips.quantize_notes(notes, 0.5, amount=0.5)] == [0.05, 0.95, 1.4]
    assert [item["start"] for item in clips.quantize_notes(notes, 0.5, amount=0)] == [0.1, 0.9, 1.3]
    assert [item["start"] for item in clips.quantize_notes([note(1, 60, 0.3)], 0.5, origin=0.25)] == [0.25]


def test_quantize_swing_delays_every_second_grid_line():
    notes = [note(1, 60, 0.0), note(2, 60, 0.27), note(3, 60, 0.49), note(4, 60, 0.76)]
    starts = [item["start"] for item in clips.quantize_notes(notes, 0.25, swing=0.5)]
    assert starts == pytest.approx([0.0, 0.3125, 0.5, 0.8125])


def test_quantize_keeps_other_fields():
    out = clips.quantize_notes([note(9, 61, 0.2, 0.7, 88)], 0.25)[0]
    assert out == dict(note(9, 61, 0.25, 0.7, 88))


def test_humanize_is_seeded_and_bounded():
    notes = [note(index, 60, index, 1.0, 100) for index in range(50)]
    first = clips.humanize_notes(notes, timing=0.05, velocity=10, seed=7)
    second = clips.humanize_notes(notes, timing=0.05, velocity=10, seed=7)
    assert first == second
    assert first != clips.humanize_notes(notes, timing=0.05, velocity=10, seed=8)
    for before, after in zip(notes, first):
        assert abs(after["start"] - before["start"]) <= 0.05 + 1e-9
        assert 90 <= after["velocity"] <= 110 and after["velocity"] == int(after["velocity"])
    assert clips.humanize_notes([note(1, 60, 0.0)], timing=0.5, seed=1)[0]["start"] >= 0.0
    untouched = clips.humanize_notes([note(1, 60, 1.0, 1.0, 99.5)], timing=0.1, seed=1)[0]
    assert untouched["velocity"] == 99.5


def test_velocity_operations():
    notes = [note(1, 60, 0, velocity=100), note(2, 60, 1, velocity=40)]
    assert [item["velocity"] for item in clips.velocity_notes(notes, factor=0.5)] == [50, 20]
    assert [item["velocity"] for item in clips.velocity_notes(notes, offset=30)] == [127, 70]
    assert [item["velocity"] for item in clips.velocity_notes(notes, factor=0.5, offset=-30)] == [20, 1]
    assert [item["velocity"] for item in clips.velocity_notes(notes, value=64)] == [64, 64]
    spread = clips.velocity_notes([note(index, 60, index) for index in range(40)], spread=10, seed=3)
    assert all(90 <= item["velocity"] <= 110 for item in spread)
    assert spread == clips.velocity_notes([note(index, 60, index) for index in range(40)], spread=10, seed=3)
    with pytest.raises(CommandError, match="value"):
        clips.velocity_notes(notes, value=64, factor=2)
    with pytest.raises(CommandError):
        clips.velocity_notes(notes)


def test_legato_moves_chords_together():
    notes = [note(1, 60, 0, 0.5), note(2, 64, 0, 0.25), note(3, 67, 1, 0.5), note(4, 72, 2.5, 0.25)]
    assert [item["duration"] for item in clips.legato_notes(notes)] == [1.0, 1.0, 1.5, 0.25]


def test_reverse_mirrors_within_region():
    notes = [note(1, 60, 0, 1), note(2, 62, 1, 0.5), note(3, 64, 3, 1)]
    assert [item["start"] for item in clips.reverse_notes(notes, 0, 4)] == [3.0, 2.5, 0.0]
    assert [item["start"] for item in clips.reverse_notes([note(1, 60, 4.5, 0.5)], 4, 8)] == [7.0]
    assert clips.reverse_notes([note(1, 60, 3.5, 2)], 0, 4)[0]["start"] == 0.0


def test_stretch_and_shift():
    notes = [note(1, 60, 0, 1), note(2, 62, 1, 0.5), note(3, 64, 2, 1)]
    assert [(item["start"], item["duration"]) for item in clips.stretch_notes(notes, 2)] == [(0, 2), (2, 1), (4, 2)]
    assert [item["start"] for item in clips.stretch_notes(notes, 0.5, anchor=1)] == [0.5, 1, 1.5]
    assert [item["start"] for item in clips.shift_notes(notes, 4)] == [4, 5, 6]
    assert [item["start"] for item in clips.shift_notes(notes[1:], -1)] == [0, 1]
    with pytest.raises(CommandError, match="before the clip start"):
        clips.shift_notes(notes, -0.5)


# ---------------------------------------------------------------------------
# Clip gain mapping (measured on Live 12.4.6)
# ---------------------------------------------------------------------------

# (raw gain, dB shown by Live's gain_display_string)
MEASURED_GAIN = [(1.0, 24.0), (0.7, 12.0), (0.5, 4.0), (0.41, 0.4), (0.4, 0.0), (0.39, -0.44), (0.35, -2.6), (0.3, -6.2),
                 (0.25, -10.8), (0.2, -16.4), (0.15, -23.0), (0.1, -30.6), (0.05, -39.2), (0.04, -41.0), (0.03, -42.9)]


@pytest.mark.parametrize("gain, db", MEASURED_GAIN)
def test_gain_model_matches_live_display(gain, db):
    assert clips.gain_to_db(gain) == pytest.approx(db, abs=0.05)
    assert clips.db_to_gain(db) == pytest.approx(gain, abs=0.002)


def test_gain_model_round_trip_and_bounds():
    for db in [-42.0, -30.0, -12.5, -6.0, -0.1, 0.0, 0.1, 6.0, 23.9, 24.0]:
        assert clips.gain_to_db(clips.db_to_gain(db)) == pytest.approx(db, abs=1e-9)
    assert clips.db_to_gain(30) == 1.0
    assert clips.db_to_gain(-50) is None
    assert clips.gain_to_db(0.0) == float("-inf")
    assert clips.gain_to_db(0.01) is None


class GainClip(object):
    """Stands in for an audio clip: gain is clamped to 0..1 and displayed like Live (2 decimals near 0 dB)."""

    def __init__(self):
        self.gain = 0.4

    @property
    def gain_display_string(self):
        if self.gain <= 0.0001:
            return "-inf dB"
        db = clips.gain_to_db(self.gain)
        if db is None:  # the steep low segment: roughly 10 dB per decade below -43 dB
            db = -42.9 + 10.0 * math.log10(self.gain / 0.03)
        return "{0:.1f} dB".format(db) if abs(db) >= 10 else "{0:.2f} dB".format(db)


def test_set_gain_db():
    clip = GainClip()
    clips.set_gain_db(clip, -6)
    assert clips.gain_to_db(clip.gain) == pytest.approx(-6.0) and clip.gain == pytest.approx(0.30245, abs=1e-5)
    clips.set_gain_db(clip, -6.2)
    assert clip.gain == pytest.approx(0.3)
    clips.set_gain_db(clip, "24")
    assert clip.gain == pytest.approx(1.0)
    clips.set_gain_db(clip, "-inf")
    assert clip.gain == 0.0
    clips.set_gain_db(clip, -55)
    assert float(clip.gain_display_string.split()[0]) == pytest.approx(-55, abs=0.1)
    with pytest.raises(CommandError, match="24"):
        clips.set_gain_db(clip, 25)
    with pytest.raises(CommandError):
        clips.set_gain_db(clip, "loud")


# ---------------------------------------------------------------------------
# Loop and marker ordering
# ---------------------------------------------------------------------------


class RegionClip(object):
    """Refuses start >= end like Live, and only honours loop/marker edits while looping (docs/spikes.md)."""

    is_audio_clip = False
    warping = True

    def __init__(self, loop=(0.0, 4.0), markers=(0.0, 4.0), looping=True):
        self.__dict__["_loop"] = list(loop)
        self.__dict__["_markers"] = list(markers)
        self.__dict__["looping"] = looping
        self.__dict__["log"] = []

    def __getattr__(self, name):
        table = {"loop_start": ("_loop", 0), "loop_end": ("_loop", 1), "start_marker": ("_markers", 0), "end_marker": ("_markers", 1)}
        if name in table:
            store, index = table[name]
            return self.__dict__[store][index]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        table = {"loop_start": ("_loop", 0), "loop_end": ("_loop", 1), "start_marker": ("_markers", 0), "end_marker": ("_markers", 1)}
        self.__dict__["log"].append((name, value))
        if name == "looping":
            self.__dict__["looping"] = value
            return
        store, index = table[name]
        if not self.__dict__["looping"]:
            raise AssertionError("set {0} while not looping".format(name))
        pair = list(self.__dict__[store])
        pair[index] = value
        if pair[0] >= pair[1]:
            raise RuntimeError("Cannot set {0}".format(name))
        self.__dict__[store] = pair


def test_set_pair_orders_moves_in_both_directions():
    clip = RegionClip(loop=(0.0, 4.0))
    clips.apply_region(clip, loop_start=8.0, loop_end=12.0)
    assert (clip.loop_start, clip.loop_end) == (8.0, 12.0)
    clips.apply_region(clip, loop_start=1.0, loop_end=2.0)
    assert (clip.loop_start, clip.loop_end) == (1.0, 2.0)
    with pytest.raises(CommandError, match="before"):
        clips.apply_region(clip, loop_start=3.0)


def test_apply_region_loops_temporarily_for_unlooped_clips():
    clip = RegionClip(markers=(0.0, 8.0), looping=False)
    clips.apply_region(clip, start_marker=1.0, end_marker=3.0, loop_end=2.0)
    assert clip.looping is False
    assert (clip.start_marker, clip.end_marker, clip.loop_end) == (1.0, 3.0, 2.0)
    assert clip.log[0] == ("looping", True) and clip.log[-1] == ("looping", False)
    clips.apply_region(clip, looping=True)
    assert clip.looping is True


def test_apply_region_restores_looping_on_error():
    clip = RegionClip(looping=False)
    with pytest.raises(CommandError):
        clips.apply_region(clip, loop_start=5.0, loop_end=4.0)
    assert clip.looping is False


class PlayClip(object):
    def __init__(self, looping=True, loop=(0.0, 4.0), markers=(0.0, 8.0)):
        self.looping = looping
        self.loop_start, self.loop_end = loop
        self.start_marker, self.end_marker = markers


def test_play_region_and_warnings():
    assert clips.play_region(PlayClip()) == (0.0, 4.0)
    assert clips.play_region(PlayClip(looping=False)) == (0.0, 8.0)
    warnings = clips.region_warnings(PlayClip(loop=(1.0, 4.0)), [note(1, 60, 0.5), note(2, 60, 2), note(3, 60, 4), note(4, 60, 5)])
    assert len(warnings) == 2 and "2 note(s) start at or after the clip end" in warnings[0] and "loop start" in warnings[1]
    assert clips.region_warnings(PlayClip(), [note(1, 60, 0)]) == []


# ---------------------------------------------------------------------------
# Drums
# ---------------------------------------------------------------------------

CHAINS = [("Kick 808", 36), ("Snare Tight", 38), ("Closed Hat", 42), ("Open Hat", 46), ("Clap", 39), ("Clap Layer", 39)]


@pytest.mark.parametrize("name, gm, pitch, source", [
    ("Kick", 36, 36, "pad 'Kick 808'"),
    ("kick 808", 36, 36, "pad 'Kick 808'"),
    ("SNARE", 38, 38, "pad 'Snare Tight'"),
    ("Hat", 42, 42, "pad 'Closed Hat'"),
    ("open-hat", 46, 46, "pad 'Open Hat'"),
    ("Clap", 39, 39, "pad 'Clap'"),
    ("Crash", 49, 49, "gm"),
    ("C1", None, 36, "note"),
    ("37", None, 37, "note"),
    ("F#1", None, 42, "note"),
])
def test_resolve_drum(name, gm, pitch, source):
    assert clips.resolve_drum(name, gm, CHAINS) == (pitch, source)


def test_resolve_drum_errors():
    with pytest.raises(CommandError, match="several pads"):
        clips.resolve_drum("hat", None, CHAINS)
    with pytest.raises(CommandError, match="Kick 808 \\(C1\\)"):
        clips.resolve_drum("Theremin", None, CHAINS)
    with pytest.raises(CommandError, match="no Drum Rack pads"):
        clips.resolve_drum("Theremin", None, [])
    assert clips.resolve_drum("Kick", 36, []) == (36, "gm")


class Device(object):
    def __init__(self, name, chains=None, drum=False):
        self.name = name
        self.can_have_drum_pads = drum
        self.can_have_chains = chains is not None
        self.chains = chains or []


class Chain(object):
    def __init__(self, name, devices=(), in_note=-1):
        self.name = name
        self.devices = list(devices)
        self.in_note = in_note


def test_find_drum_rack_searches_inside_racks():
    drums = Device("Drums", chains=[Chain("Kick", in_note=36), Chain("All", in_note=-1), Chain("Snare", in_note=38)], drum=True)
    track = Chain("track", devices=[Device("EQ"), Device("Instrument Rack", chains=[Chain("Layer", devices=[drums])])])
    assert clips.find_drum_rack(track) is drums
    assert clips.drum_chains(drums) == [("Kick", 36), ("Snare", 38)]
    assert clips.find_drum_rack(Chain("empty", devices=[Device("Operator")])) is None
    assert clips.drum_chains(None) == []


def test_validate_lanes_and_tiling():
    lanes = clips._validate_lanes([{"drum": "Kick", "gm": 36, "cycle": 1.0, "hits": [[0, 0.25, 100], [0.5, 0.25, 90]]}])
    assert lanes[0]["hits"] == [(0, 0.25, 100.0), (0.5, 0.25, 90.0)]
    tiled = clips.tile_hits(lanes[0]["hits"], 1.0, 0.0, 2.75)
    assert [start for start, _, _ in tiled] == [0, 0.5, 1.0, 1.5, 2.0, 2.5]
    assert [start for start, _, _ in clips.tile_hits([(0.0, 0.25, 100.0)], 4.0, 2.0, 6.0)] == [2.0]
    assert [start for start, _, _ in clips.tile_hits([(0.0, 0.25, 100.0), (3.0, 0.25, 100.0)], 4.0, 0.0, 2.0)] == [0.0]
    for bad in ([], "x", [{"drum": "Kick"}], [{"drum": "Kick", "cycle": 1, "hits": [[0, 1]]}],
                [{"drum": "Kick", "cycle": 1, "hits": [[1.5, 0.25, 100]]}], [{"drum": "Kick", "cycle": 1, "hits": [[0, 0.25, 0]]}],
                [{"drum": "Kick", "cycle": 0, "hits": []}]):
        with pytest.raises(CommandError):
            clips._validate_lanes(bad)
