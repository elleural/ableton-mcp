"""Unit tests for WS-D parameter and reference parsing (handlers/devices.py): display units, option
matching, booleans, chain paths and drum notes. Live is replaced by small fakes."""
import math

import pytest

from AbletonMCP_Remote_Script import core
from AbletonMCP_Remote_Script.errors import CommandError

core.load_handlers()  # the full registry, so this module never leaves a partial one for other tests
from AbletonMCP_Remote_Script.handlers import devices  # noqa: E402


@pytest.mark.parametrize("text, number", [
    ("-6.0 dB", -6.0), ("800 Hz", 800.0), ("1.20 kHz", 1200.0), ("2.50 s", 2500.0), ("35.0 ms", 35.0),
    ("30 %", 30.0), ("25L", -25.0), ("50R", 50.0), ("C", 0.0), ("-inf dB", float("-inf")), ("+12 st", 12.0),
    ("0.50 ", 0.5), ("1 sec", 1000.0), (" 4 bars", 4.0),
])
def test_normalized_display_units(text, number):
    assert devices.normalized_display(text) == number


@pytest.mark.parametrize("text", ["Off", "", None, "Sine"])
def test_normalized_display_without_number(text):
    assert devices.normalized_display(text) is None


def test_close_tolerates_display_rounding():
    assert devices._close(2500.0, 2500.0)
    assert devices._close(1198.0, 1200.0)          # "1.20 s" shows 3 significant digits
    assert devices._close(0.0, 0.0)
    assert not devices._close(200.0, 2000.0)
    assert devices._close(float("-inf"), float("-inf"))
    assert not devices._close(None, 1.0)


class TimeParameter(object):
    """A continuous time parameter like Reverb's Decay Time: raw 0..1 maps to 1 ms .. 60 s.

    It shows "xx.x ms" below one second and "x.xx s" above. display_value is in `unit_ms` milliseconds
    (1 = ms like Live; 1000 = a parameter whose display_value were seconds).
    """

    def __init__(self, unit_ms=1.0, accepts_display=True):
        self.min, self.max, self.value = 0.0, 1.0, 0.5
        self.name = self.original_name = "Decay Time"
        self.is_quantized, self.is_enabled = False, True
        self.unit_ms, self.accepts_display = unit_ms, accepts_display

    @staticmethod
    def ms(raw):
        return 60000.0 ** raw

    def str_for_value(self, raw):
        ms = self.ms(raw)
        return "{0:.1f} ms".format(ms) if ms < 1000 else "{0:.2f} s".format(ms / 1000.0)

    @property
    def display_value(self):
        return self.ms(self.value) / self.unit_ms

    @display_value.setter
    def display_value(self, target):
        if not self.accepts_display:
            raise RuntimeError("display_value is not settable")
        self.value = min(max(math.log(max(target * self.unit_ms, 1.0)) / math.log(60000.0), 0.0), 1.0)


@pytest.mark.parametrize("make", [TimeParameter, lambda: TimeParameter(unit_ms=1000.0), lambda: TimeParameter(accepts_display=False)])
@pytest.mark.parametrize("text, milliseconds", [("2.5 s", 2500.0), ("2500 ms", 2500.0), ("250 ms", 250.0), ("1 s", 1000.0), ("40 s", 40000.0)])
def test_set_parameter_display_strings_in_any_unit(make, text, milliseconds):
    out = devices.set_parameter(make(), text)
    assert devices._close(devices.normalized_display(out["display"]), milliseconds), out


def test_set_parameter_clamps_beyond_range():
    assert devices.set_parameter(TimeParameter(accepts_display=False), "100 s")["value"] == 1.0
    assert devices.set_parameter(TimeParameter(accepts_display=False), "0.1 ms")["value"] == 0.0


def test_set_parameter_numbers_are_raw():
    parameter = TimeParameter()
    assert devices.set_parameter(parameter, 0.25)["value"] == 0.25
    assert devices.set_parameter(parameter, 7)["value"] == 1.0  # clamped to max


def test_set_parameter_rejects_text_without_number():
    with pytest.raises(CommandError) as error:
        devices.set_parameter(TimeParameter(), "long")
    assert error.value.code == "invalid_argument"


def test_set_parameter_rejects_disabled_parameter():
    parameter = TimeParameter()
    parameter.is_enabled = False
    with pytest.raises(CommandError) as error:
        devices.set_parameter(parameter, "1 s")
    assert error.value.code == "unsupported"


class Quantized(object):
    min, max, value = 0.0, 2.0, 0.0
    name = original_name = "Size Smoothing"
    is_quantized, is_enabled = True, True
    value_items = ["None", "Slow", "Fast"]

    def str_for_value(self, raw):
        return self.value_items[int(raw)]


def test_set_parameter_quantized_items_by_name():
    parameter = Quantized()
    assert devices.set_parameter(parameter, "fast")["display"] == "Fast"
    with pytest.raises(CommandError) as error:
        devices.set_parameter(parameter, "Medium")
    assert "None, Slow, Fast" in error.value.message


OPTIONS = ["Poly", "Mono", "Stereo", "Unison"]


@pytest.mark.parametrize("value, index", [(1, 1), ("Mono", 1), ("mono", 1), ("UNISON", 3), ("ster", 2), ("2", 2), (2.0, 2)])
def test_match_option(value, index):
    assert devices.match_option(OPTIONS, value, "voice_mode") == index


def test_match_option_punctuation_and_numeric_labels():
    assert devices.match_option(["Early_Reflections", "Real_Places"], "real places", "ir") == 1
    voices = ["2", "3", "4", "5", "6", "8", "12"]
    assert devices.match_option(voices, 12, "poly_voices") == 6      # not an index: the label "12"
    assert devices.match_option(voices, "12", "poly_voices") == 6
    assert devices.match_option(voices, 3, "poly_voices") == 3       # ints are indices first
    assert devices.match_option([" 1 bar", " 4 bars"], "4 Bars", "length") == 1


@pytest.mark.parametrize("value", [9, "Quad", True, "o"])
def test_match_option_errors_list_options(value):
    with pytest.raises(CommandError) as error:
        devices.match_option(OPTIONS, value, "voice_mode")
    assert error.value.code in ("not_found", "invalid_argument")


@pytest.mark.parametrize("value, result", [(True, True), (0, False), ("on", True), ("Off", False), ("yes", True), ("false", False)])
def test_parse_bool(value, result):
    assert devices.parse_bool(value) is result


@pytest.mark.parametrize("value", ["maybe", 2, None])
def test_parse_bool_rejects(value):
    with pytest.raises(CommandError):
        devices.parse_bool(value, "enabled")


@pytest.mark.parametrize("ref, parts", [
    ("Drum Rack/Kick/Simpler", ["Drum Rack", "Kick", "Simpler"]), ("1/0/2", ["1", "0", "2"]), ([0, "C1", 0], [0, "C1", 0]),
    ("Operator", ["Operator"]), (3, [3]), (" Rack / 0 ", ["Rack", "0"]),
])
def test_segments(ref, parts):
    assert devices.segments(ref) == parts


@pytest.mark.parametrize("text, note", [("C1", 36), ("D#1", 39), ("note:38", 38), ("Eb1", 39), ("Kick", None), ("0", None), (36, None)])
def test_drum_note(text, note):
    assert devices.drum_note(text) == note


def test_note_name():
    assert devices.note_name(36) == "C1"
    assert devices.note_name(-1) == "all"


@pytest.mark.parametrize("name, available, companion", [
    ("voice_mode_index", {"voice_mode_index", "voice_mode_list"}, "voice_mode_list"),
    ("pitch_mode", {"pitch_mode", "pitch_mode_list"}, "pitch_mode_list"),
    ("custom_float_target_3", {"custom_float_target_3", "custom_float_target_3_list"}, "custom_float_target_3_list"),
    ("input_routing_type", {"input_routing_type", "available_input_routing_types"}, "available_input_routing_types"),
    ("selected_preset_index", {"selected_preset_index", "presets"}, "presets"),
    ("oscillator_1_wavetable_index", {"oscillator_1_wavetable_index", "oscillator_1_wavetables"}, "oscillator_1_wavetables"),
    ("oscillator_2_wavetable_category", {"oscillator_2_wavetable_category", "oscillator_wavetable_categories"}, "oscillator_wavetable_categories"),
    ("voices", {"voices"}, None),
])
def test_companion_name(name, available, companion):
    assert devices.companion_name(name, available) == companion
