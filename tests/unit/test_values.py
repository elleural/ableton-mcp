"""Unit tests for the Remote Script's unit conversions (values.py)."""
import pytest

from AbletonMCP_Remote_Script import values
from AbletonMCP_Remote_Script.errors import CommandError
from tests.unit import parameter_fakes as fakes


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


@pytest.mark.parametrize("text, number", [
    ("-6.0 dB", -6.0), ("-inf dB", float("-inf")), ("800 Hz", 800.0), ("1.20 kHz", 1200.0), ("25L", -25.0), ("50R", 50.0),
    ("C", 0.0), ("35 %", 35.0), ("2.50 s", 2500.0), ("35 ms", 35.0), ("2 s", 2000.0), ("+12 st", 12.0), ("0.50 ", 0.5),
    ("1 sec", 1000.0), (" 4 bars", 4.0), ("inf s", float("inf")), ("22.0k", 22000.0), (" 30", 30.0),
    # ratios read as their side other than 1, like display_value: Compressor Ratio and Expansion Ratio
    ("4.00 : 1", 4.0), ("1.00 : 1", 1.0), ("inf : 1", float("inf")), ("1 : 1.15", 1.15), ("1 : 2.00", 2.0), ("4:1", 4.0),
])
def test_parse_display_number(text, number):
    assert values.parse_display_number(text) == number


@pytest.mark.parametrize("text", ["Off", "", None, "Sine"])
def test_parse_display_number_without_number(text):
    assert values.parse_display_number(text) is None


def test_close_tolerates_display_rounding():
    assert values._close(2500.0, 2500.0)
    assert values._close(1198.0, 1200.0)          # "1.20 s" shows 3 significant digits
    assert values._close(0.0, 0.0)
    assert not values._close(200.0, 2000.0)
    assert values._close(float("-inf"), float("-inf"))
    assert not values._close(-70.0, float("-inf"))
    assert not values._close(None, 1.0)


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


# ---------------------------------------------------------------------------
# set_parameter, with fakes shaped like Live 12.4.6's parameters (parameter_fakes.py)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("make, text, number", [
    (FakeParameter, "-6 dB", -6.0),                            # a dB fader that ignores display_value: bisection
    (FakeParameter, "-inf dB", float("-inf")),                 # its minimum shows -inf
    (fakes.frequency, "800 Hz", 800.0),
    (fakes.frequency, "1.2 kHz", 1200.0),
    (fakes.frequency, "19.8 Hz", 20.0),                        # a hair below the end that shows 20 Hz: the end
    (fakes.percent, "30 %", 30.0),
    (fakes.compressor_output, "-6 dB", -6.0),                  # raw in dB, with numeric step labels
    (fakes.compressor_output, "-6.0 dB", -6.0),                # ... one of which matches exactly
    (fakes.compressor_ratio, "4 : 1", 4.0),
    (fakes.compressor_ratio, "inf : 1", float("inf")),
    (fakes.compressor_expansion_ratio, "1 : 1.5", 1.5),
    (fakes.compressor_expansion_ratio, "2", 2.0),
    (fakes.drum_buss_transients, "0.25", 0.25),
    (fakes.drum_buss_transients, "1", 1.0),
    (fakes.drum_buss_transients, "1.004", 1.0),                # within display rounding of the end: the end
    (fakes.pan, "25L", -25.0),
    (fakes.roar_blend, "70 / 30", 70.0),                       # a crossfade's fraction is a display value
    (fakes.auto_filter_lfo_16th, "8", 8.0),                    # numbers still work on numeric step labels
])
def test_display_values_land_where_asked(make, text, number):
    parameter = make()
    out = values.set_parameter(parameter, text)
    assert out["display"] == parameter.str_for_value(parameter.value)  # the echo is what Live shows now
    assert values._close(values.parse_display_number(out["display"]), number), out


@pytest.mark.parametrize("make", [fakes.TimeParameter, lambda: fakes.TimeParameter(unit_ms=1000.0), lambda: fakes.TimeParameter(accepts_display=False)])
@pytest.mark.parametrize("text, milliseconds", [("2.5 s", 2500.0), ("2500 ms", 2500.0), ("250 ms", 250.0), ("1 s", 1000.0), ("40 s", 40000.0), ("60 s", 60000.0)])
def test_display_strings_in_any_time_unit(make, text, milliseconds):
    out = values.set_parameter(make(), text)
    assert values._close(values.parse_display_number(out["display"]), milliseconds), out


@pytest.mark.parametrize("make, text, shown", [
    (fakes.drum_buss_transients, "25 %", "-1.00 .. 1.00"),     # Transients shows a fraction: 25 % reads 25, not 0.25
    (fakes.drum_buss_transients, "-1.5", "-1.00 .. 1.00"),
    (fakes.frequency, "25 kHz", "20 Hz .. 20.00 kHz"),
    (fakes.compressor_output, "-inf dB", "-36.0 dB .. 36.0 dB"),  # this Output never reaches -inf
    (fakes.compressor_expansion_ratio, "3", "1 : 1.00 .. 1 : 2.00"),
    (fakes.TimeParameter, "100 s", "1.0 ms .. 60.00 s"),
    (lambda: fakes.TimeParameter(accepts_display=False), "0.1 ms", "1.0 ms .. 60.00 s"),
])
def test_display_values_outside_the_range_are_errors(make, text, shown):
    parameter = make()
    before = parameter.value
    with pytest.raises(CommandError) as error:
        values.set_parameter(parameter, text)
    assert error.value.code == "invalid_argument"
    assert "{0} (now {1})".format(shown, parameter.str_for_value(before)) in error.value.message
    assert parameter.value == before                           # nothing was written


@pytest.mark.parametrize("make, text, raw, shown", [
    (fakes.echo_l_synced, "1/8", -3, "1/8"),
    (fakes.echo_l_synced, "1/16", -4, "1/16"),
    (fakes.echo_l_synced, " 1/64 ", -6, "1/64"),
    (fakes.echo_l_synced, "1", 0, "1"),
    (fakes.roar_fb_synced, "1/16", -4, "1 / 16"),             # Roar puts spaces around the slash
    (fakes.roar_fb_synced, "1 / 128", -7, "1 / 128"),
    (fakes.auto_filter_lfo_rate, "3/16", 13, "3/16"),
    (fakes.auto_filter_lfo_rate, "1.5", 5, "1.5"),            # a label, not the number 1.5
    (fakes.auto_filter_lfo_rate, "3", 3, "3"),
    (fakes.auto_filter_lfo_16th, "4/16", 4, "4  / 16"),
    (fakes.hybrid_ti_rate, "1/8T", 11, "1/8 T"),
    (fakes.analog_lfo_rate, "1/8T", 17, "1/8t"),
    (fakes.roar_fb_note, "a0", 33, "A0"),
    (fakes.roar_fb_note, "C#1", 37, "C#1"),
    (fakes.hybrid_vintage, "older", 3, "Older"),
])
def test_step_labels_select_their_step(make, text, raw, shown):
    parameter = make()
    out = values.set_parameter(parameter, text)
    assert parameter.value == raw and out["display"] == shown


@pytest.mark.parametrize("make, text, listed", [
    (fakes.echo_l_synced, "1/5", "Values: 1/64, 1/32, 1/16, 1/8, 1/4, 1/2, 1"),
    (fakes.echo_l_synced, "1/8 dotted", "1/64, 1/32, 1/16, 1/8, 1/4, 1/2, 1"),
    (fakes.echo_l_synced, "2", "1/64, 1/32, 1/16, 1/8, 1/4, 1/2, 1"),      # a number is not a note value
    (fakes.roar_fb_synced, "3/16", "1 / 128, 1 / 64, 1 / 32"),
    (fakes.auto_filter_lfo_rate, "1 bar", "8, 6, 4, 3, 2, 1.5, 1, 3/4, 1/2"),
    (fakes.auto_filter_lfo_16th, "1/4", "Values: 1 / 16 .. 64 / 16"),      # sixteenths: the quarter is '4/16'
    (fakes.roar_fb_note, "Bb0", "A0, A#0, B0"),                            # Live names notes with sharps
    (fakes.hybrid_vintage, "Medium", "Off, Subtle, Old, Older, Extreme"),
    (fakes.drum_buss_transients, "1/4", "Values: -1.00 .. 1.00"),
    (fakes.compressor_output, "1/2", "Values: -36.0 dB .. 36.0 dB"),
])
def test_strings_that_match_no_step_label_are_errors(make, text, listed):
    parameter = make()
    before = parameter.value
    with pytest.raises(CommandError) as error:
        values.set_parameter(parameter, text)
    assert error.value.code == "invalid_argument"
    assert listed in error.value.message and "(now {0})".format(parameter.str_for_value(before)) in error.value.message
    assert parameter.value == before


def test_fractions_on_parameters_without_note_values_are_errors():
    parameter = fakes.TimeParameter()                          # Echo's L Time, say, rather than L Synced
    with pytest.raises(CommandError) as error:
        values.set_parameter(parameter, "1/8")
    assert error.value.code == "invalid_argument"
    assert "'1/8' is a fraction, but 'Decay Time' shows 1.0 ms .. 60.00 s (now 244.9 ms)" in error.value.message
    assert parameter.value == 0.5


def test_step_labels_only_for_whole_number_ranges():
    assert values.step_labels(fakes.percent()) == []                       # the usual 0..1
    assert values.step_labels(fakes.compressor_expansion_ratio()) == []    # 1..2: one step apart
    assert values.step_labels(fakes.Quantized()) == []
    assert values.step_labels(fakes.drum_buss_transients()) == [(-1.0, "-1.00"), (0.0, "0.00"), (1.0, "1.00")]
    assert len(values.step_labels(fakes.auto_filter_lfo_16th())) == 64
    glide = fakes.Parameter("Glide", 0, 2000, 10, "{0:.1f} ms".format, lambda ms: ms)
    assert values.step_labels(glide) == []                                 # beyond STEP_LIMIT steps: not scanned
    assert values.set_parameter(glide, "250 ms")["display"] == "250.0 ms"


def test_quantized_items_by_name():
    parameter = fakes.Quantized()
    assert values.set_parameter(parameter, "fast")["display"] == "Fast"
    with pytest.raises(CommandError) as error:
        values.set_parameter(parameter, "Medium")
    assert "None, Slow, Fast" in error.value.message


def test_numbers_are_raw_values():
    parameter = fakes.TimeParameter()
    assert values.set_parameter(parameter, 0.25)["value"] == 0.25
    with pytest.raises(CommandError) as error:                 # out of the raw range: an error, never a silent clamp
        values.set_parameter(parameter, 7)
    assert "raw range" in error.value.message
    synced = fakes.echo_l_synced()
    assert values.set_parameter(synced, -4)["display"] == "1/16"   # a raw step number


def test_set_parameter_rejects_text_without_number():
    with pytest.raises(CommandError) as error:
        values.set_parameter(fakes.TimeParameter(), "long")
    assert error.value.code == "invalid_argument"


def test_set_parameter_rejects_disabled_parameter():
    parameter = fakes.TimeParameter()
    parameter.is_enabled = False
    with pytest.raises(CommandError) as error:
        values.set_parameter(parameter, "1 s")
    assert error.value.code == "unsupported"


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
