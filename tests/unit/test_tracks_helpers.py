"""Unit tests for WS-B's pure helpers (meter scale, routing name matching, validation)."""
import pytest

from AbletonMCP_Remote_Script.errors import CommandError
from AbletonMCP_Remote_Script.handlers import tracks


# Meter scale, measured on Live 12.4.6 with a sine of known peak level: dBFS = 76 * raw - 70.
@pytest.mark.parametrize("raw, db", [
    (1.0, 6.0), (70 / 76.0, 0.0), (64 / 76.0, -6.0), (0.5, -32.0), (0.39474, -40.0), (0.01316, -69.0),
    (1.2, 6.0),
])
def test_meter_db_scale(raw, db):
    assert tracks.meter_db(raw) == pytest.approx(db, abs=0.05)


@pytest.mark.parametrize("raw", [0, 0.0, -0.1])
def test_meter_db_silence(raw):
    assert tracks.meter_db(raw) == "-inf"


def test_meter_db_unreadable():
    assert tracks.meter_db(None) is None
    assert tracks.meter_db("x") is None


@pytest.mark.parametrize("name, bare", [("5-Drum Bus", "Drum Bus"), ("12-Audio", "Audio"), ("Drum Bus", "Drum Bus"),
                                        ("A-Reverb", "A-Reverb"), ("3D-Synth", "3D-Synth")])
def test_strip_track_number(name, bare):
    assert tracks.strip_track_number(name) == bare


@pytest.mark.parametrize("name, letter, result", [
    ("C-Verb", "C", "Verb"), ("c-Verb", "C", "Verb"), ("Verb", "C", "Verb"), ("A-Verb", "C", "A-Verb"), ("C-", "C", "C-"),
])
def test_strip_own_letter(name, letter, result):
    assert tracks.strip_own_letter(name, letter) == result


@pytest.mark.parametrize("good", [0, 69, "#FF8800", "ff8800"])
def test_check_color_accepts(good):
    assert tracks.check_color(good) == good


@pytest.mark.parametrize("bad", [70, -1, True, "red", "#FF88", None, 3.5])
def test_check_color_rejects(bad):
    with pytest.raises(CommandError) as error:
        tracks.check_color(bad)
    assert error.value.code == "invalid_argument"


def test_check_bool():
    assert tracks.check_bool(True, "arm") is True
    assert tracks.check_bool(0, "arm") is False
    for bad in ("yes", 2, None):
        with pytest.raises(CommandError):
            tracks.check_bool(bad, "arm")


OUTPUTS = ["Ext. Out", "Main", "3-Audio", "4-Audio", "Drum Bus", "Sends Only"]


@pytest.mark.parametrize("ref, expected", [
    ("Main", "Main"), ("main", "Main"), ("  SENDS ONLY ", "Sends Only"), ("Drum Bus", "Drum Bus"),
    ("5-Drum Bus", "Drum Bus"),  # a track-number prefix on the caller's side
    ("3-audio", "3-Audio"),
    ("master", "Main"), ("sends", "Sends Only"), ("none", "No Output"), ("ext", "Ext. Out"),  # aliases
    ("drum", "Drum Bus"),  # unique substring
])
def test_match_option_outputs(ref, expected):
    names = OUTPUTS + ["No Output"]
    position = tracks.match_option(names, ref, "Output", tracks.routing_aliases("output"))
    assert names[position] == expected


def test_match_option_strips_track_number_on_the_option_side():
    assert tracks.match_option(["Ext. In", "5-Drum Bus", "No Input"], "Drum Bus", "Input") == 1


def test_match_option_ambiguous_lists_the_matches():
    with pytest.raises(CommandError) as error:
        tracks.match_option(OUTPUTS, "Audio", "Output")
    assert error.value.code == "invalid_argument"
    assert "3-Audio" in error.value.message and "4-Audio" in error.value.message
    assert "Drum Bus" not in error.value.message


def test_match_option_duplicate_display_names_are_ambiguous():
    with pytest.raises(CommandError) as error:
        tracks.match_option(["Main", "Pad", "Pad"], "Pad", "Output")
    assert "index" in error.value.message


def test_match_option_unknown_lists_options():
    with pytest.raises(CommandError) as error:
        tracks.match_option(OUTPUTS, "Nowhere", "Output routing for track 'Bass'")
    assert error.value.code == "not_found"
    assert "Available: Ext. Out, Main, 3-Audio, 4-Audio, Drum Bus, Sends Only" in error.value.message


def test_match_option_short_substrings_do_not_guess():
    with pytest.raises(CommandError) as error:
        tracks.match_option(OUTPUTS, "ma", "Output")
    assert error.value.code == "not_found"


def test_match_option_ignores_empty_options():
    with pytest.raises(CommandError) as error:
        tracks.match_option([""], "Main", "Output")
    assert "(none)" in error.value.message


AUDIO_CHANNELS = ["1/2", "1", "2", "3/4"]
MIDI_CHANNELS = ["All Channels", "Ch. 1", "Ch. 2", "Ch. 10"]
TRACK_TAPS = ["Pre FX", "Post FX", "Post Mixer"]


@pytest.mark.parametrize("names, ref, expected", [
    (AUDIO_CHANNELS, "1/2", "1/2"), (AUDIO_CHANNELS, 1, "1"), (AUDIO_CHANNELS, "2", "2"),
    (MIDI_CHANNELS, 1, "Ch. 1"), (MIDI_CHANNELS, "10", "Ch. 10"), (MIDI_CHANNELS, "ch. 2", "Ch. 2"),
    (MIDI_CHANNELS, "all", "All Channels"), (TRACK_TAPS, "post fx", "Post FX"), (TRACK_TAPS, "mixer", "Post Mixer"),
])
def test_match_channel(names, ref, expected):
    assert names[tracks.match_channel(names, ref, "Channel")] == expected


@pytest.mark.parametrize("names, ref", [(TRACK_TAPS, "post"), (AUDIO_CHANNELS, "9"), (MIDI_CHANNELS, True)])
def test_match_channel_rejects(names, ref):
    with pytest.raises(CommandError):
        tracks.match_channel(names, ref, "Channel")


@pytest.mark.parametrize("value, expected", [
    (-6, -6.0), ("-6", -6.0), ("-6 dB", -6.0), ("-6dB", -6.0), (6, 6.0), (0, 0.0),
    ("-inf", "-inf"), ("-INF", "-inf"), (-70, "-inf"), (-120, "-inf"),
])
def test_check_db(value, expected):
    assert tracks.check_db(value, "volume_db", 6.0) == expected


@pytest.mark.parametrize("value, maximum", [(6.5, 6.0), (1, 0.0), ("loud", 6.0), (True, 6.0), (float("nan"), 6.0)])
def test_check_db_rejects(value, maximum):
    with pytest.raises(CommandError) as error:
        tracks.check_db(value, "volume_db", maximum)
    assert error.value.code == "invalid_argument"


@pytest.mark.parametrize("value, expected", [(-1, -1.0), (0.5, 0.5), ("50A", -1.0), ("25B", 0.5), ("0", 0.0), ("c", 0.0)])
def test_parse_crossfader(value, expected):
    assert tracks._parse_crossfader(value) == pytest.approx(expected)


@pytest.mark.parametrize("bad", [1.5, "60A", "left", True])
def test_parse_crossfader_rejects(bad):
    with pytest.raises(CommandError):
        tracks._parse_crossfader(bad)
