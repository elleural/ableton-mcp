"""Unit tests for WS-D parameter and reference parsing (handlers/devices.py): set_device_parameters, option
matching, booleans, chain paths and drum notes. Live is replaced by small fakes; display units and step labels
are values.set_parameter's, tested in test_values.py."""
import types

import pytest

from AbletonMCP_Remote_Script import core
from AbletonMCP_Remote_Script.errors import CommandError

core.load_handlers()  # the full registry, so this module never leaves a partial one for other tests
from AbletonMCP_Remote_Script.handlers import devices  # noqa: E402
from tests.unit import parameter_fakes as fakes  # noqa: E402


class Device(object):
    name = "Echo"

    def __init__(self, *parameters):
        self.parameters = list(parameters)


def test_set_device_parameters_sets_through_values_and_lists_each_failure(monkeypatch):
    """Display strings go through values.set_parameter: a note value lands on its step, and a display value
    outside the range is listed in errors (never clamped) while the other parameters are still set."""
    device = Device(fakes.echo_l_synced(), fakes.drum_buss_transients(), fakes.percent("Dry Wet"))
    monkeypatch.setattr(devices.refs, "device", lambda song, track, ref: (device, None, 1))
    monkeypatch.setattr(devices, "summary", lambda target, index: {"index": index, "name": target.name})
    out = devices.set_device_parameters(types.SimpleNamespace(song=None), "Lead", "Echo",
                                        {"L Synced": "1/16", "Transients": "25 %", "Dry Wet": "30 %"})
    assert [(item["index"], item["name"], item["display"]) for item in out["parameters"]] == [(0, "L Synced", "1/16"), (2, "Dry Wet", "30 %")]
    assert [(item["parameter"], item["code"]) for item in out["errors"]] == [("Transients", "invalid_argument")]
    assert "-1.00 .. 1.00 (now 0.15)" in out["errors"][0]["error"]
    assert device.parameters[1].value == 0.15


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
