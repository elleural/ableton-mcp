"""Unit tests for the Remote Script's unit conversions (values.py)."""
import pytest

from AbletonMCP_Remote_Script import values
from AbletonMCP_Remote_Script.errors import CommandError


class Song(object):
    def __init__(self, numerator=4, denominator=4):
        self.signature_numerator = numerator
        self.signature_denominator = denominator


@pytest.mark.parametrize("text, beats", [("1.1.1", 0.0), ("2.1.1", 4.0), ("17.1.1", 64.0), ("1.2.1", 1.0), ("1.1.2", 0.25), ("3.3", 10.0), (6.5, 6.5), ("8", 8.0)])
def test_parse_time_four_four(text, beats):
    assert values.parse_time(Song(), text) == beats


def test_parse_time_six_eight():
    assert values.parse_time(Song(6, 8), "2.1.1") == 3.0
    assert values.parse_time(Song(6, 8), "1.2.1") == 0.5


@pytest.mark.parametrize("beats, text", [(0.0, "1.1.1"), (64.0, "17.1.1"), (1.25, "1.2.2"), (4.125, "2.1.1.5")])
def test_format_time(beats, text):
    assert values.format_time(Song(), beats) == text


@pytest.mark.parametrize("bad", ["0.1.1", "x", True, None, "2.5", "1.1.5"])
def test_parse_time_rejects(bad):
    with pytest.raises(CommandError):
        values.parse_time(Song(), bad)


def test_parse_length():
    assert values.parse_length(Song(), "8 bars") == 32.0
    assert values.parse_length(Song(3, 4), "2 bars") == 6.0
    assert values.parse_length(Song(), "6 beats") == 6.0
    assert values.parse_length(Song(), 2) == 2.0
    with pytest.raises(CommandError):
        values.parse_length(Song(), 0)


@pytest.mark.parametrize("name, pitch", [("C3", 60), ("c3", 60), ("C-2", 0), ("G8", 127), ("F#2", 54), ("Bb3", 70), ("A3", 69), (61, 61), ("64", 64)])
def test_parse_pitch(name, pitch):
    assert values.parse_pitch(name) == pitch


@pytest.mark.parametrize("bad", ["H3", "C9", 128, -1, "C"])
def test_parse_pitch_rejects(bad):
    with pytest.raises(CommandError):
        values.parse_pitch(bad)


def test_pitch_name_round_trip():
    for pitch in range(128):
        assert values.parse_pitch(values.pitch_name(pitch)) == pitch
    assert values.pitch_name(70, flats=True) == "Bb3"


def test_parse_root_note():
    assert values.parse_root_note("C") == 0
    assert values.parse_root_note("F#") == 6
    assert values.parse_root_note("Bb") == 10
    assert values.parse_root_note(11) == 11


@pytest.mark.parametrize("text, number", [("-6.0 dB", -6.0), ("-inf dB", float("-inf")), ("800 Hz", 800.0), ("1.20 kHz", 1200.0), ("25L", -25.0), ("50R", 50.0), ("C", 0.0), ("35 %", 35.0), ("2.50 s", 2500.0), ("35 ms", 35.0), ("2 s", 2000.0)])
def test_parse_display_number(text, number):
    assert values.parse_display_number(text) == number


def test_parse_pan():
    assert values.parse_pan(-0.5) == -0.5
    assert values.parse_pan("25L") == -0.5
    assert values.parse_pan("50R") == 1.0
    assert values.parse_pan("C") == 0.0
    with pytest.raises(CommandError):
        values.parse_pan(2)


class FakeParameter(object):
    """A dB fader whose display is 40*log10(value/0.85) like Live's, monotonic in value."""

    name = "Volume"
    min = 0.0
    max = 1.0
    is_quantized = False
    is_enabled = True

    def __init__(self):
        self.value = 0.85

    def str_for_value(self, value):
        import math
        if value <= 0:
            return "-inf dB"
        return "{0:.2f} dB".format(40 * math.log10(value / 0.85))


def test_value_for_display_number_bisects():
    parameter = FakeParameter()
    raw = values.value_for_display_number(parameter, -6.0)
    assert abs(values.display_number(parameter, raw) - -6.0) < 0.01
    values.set_volume_db(parameter, "-inf")
    assert parameter.value == 0.0


def test_enum_parsing():
    assert values.CLIP_LAUNCH_QUANTIZATION.parse("1/16") == 12
    assert values.CLIP_LAUNCH_QUANTIZATION.parse("1 bar") == 5
    assert values.SONG_QUANTIZATION.name(4) == "1 bar"
    assert values.WARP_MODE.parse("Complex Pro") == 6
    with pytest.raises(CommandError):
        values.LAUNCH_MODE.parse("sometimes")


def test_jsonable_handles_infinities_and_nesting():
    assert values.jsonable(float("-inf")) == "-inf"
    assert values.jsonable((1, [2.5, "x"])) == [1, [2.5, "x"]]
