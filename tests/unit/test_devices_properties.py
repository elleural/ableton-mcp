"""Unit tests for WS-D type-specific properties, rack descriptions and the device-action whitelist
(handlers/devices.py), with fake devices standing in for Live's classes."""
import sys

import pytest

from AbletonMCP_Remote_Script import core
from AbletonMCP_Remote_Script.errors import CommandError

core.load_handlers()  # the full registry, so this module never leaves a partial one for other tests
from AbletonMCP_Remote_Script.handlers import devices  # noqa: E402


def rw(name):
    return property(lambda self: getattr(self, "_" + name), lambda self, value: setattr(self, "_" + name, value))


def ro(name):
    return property(lambda self: getattr(self, "_" + name))


class RoutingType(object):
    def __init__(self, display_name):
        self.display_name = display_name


class CompressorDevice(object):
    """Sidechain routing (RoutingType values with an available_* list) plus a few scalar properties."""
    name = "Compressor"
    input_routing_type = rw("input_routing_type")
    available_input_routing_types = ro("available")
    voice_mode_index = rw("voice_mode_index")
    voice_mode_list = ro("voice_mode_list")
    preset_index = rw("preset_index")
    preset_index_list = ro("presets")
    gain = rw("gain")
    oversample = rw("oversample")
    loop_length = ro("loop_length")
    count = rw("count")

    def __init__(self):
        self._available = [RoutingType("No Input"), RoutingType("1-Kick"), RoutingType("Main")]
        self._input_routing_type = self._available[0]
        self._voice_mode_index, self._voice_mode_list = 0, ["Poly", "Mono", "Stereo", "Unison"]
        self._preset_index, self._presets = 0, ["Preset {0}".format(number) for number in range(100)]
        self._gain, self._oversample, self._loop_length, self._count = 0.5, False, 4.0, 3


def available(device):
    return devices._class_properties(device)


def test_property_out_option_list():
    device = CompressorDevice()
    entry = devices.property_out(device, "voice_mode_index", available(device)["voice_mode_index"], available(device))
    assert entry == {"value": 0, "item": "Poly", "options": ["Poly", "Mono", "Stereo", "Unison"]}


def test_property_out_routing_and_read_only():
    device = CompressorDevice()
    props = available(device)
    assert devices.property_out(device, "input_routing_type", props["input_routing_type"], props) == {"value": "No Input", "options": ["No Input", "1-Kick", "Main"]}
    assert devices.property_out(device, "loop_length", props["loop_length"], props) == {"value": 4.0, "read_only": True}


def test_property_out_bounds_long_option_lists():
    device = CompressorDevice()
    props = available(device)
    entry = devices.property_out(device, "preset_index", props["preset_index"], props)
    assert len(entry["options"]) == 64 and entry["option_count"] == 100 and entry["item"] == "Preset 0"
    assert len(devices.property_out(device, "preset_index", props["preset_index"], props, detail=True)["options"]) == 100


def test_set_property_parses_names_aliases_and_types():
    device = CompressorDevice()
    assert devices.set_property(device, "voice_mode", "mono")[0] == "voice_mode_index"
    assert device._voice_mode_index == 1
    devices.set_property(device, "voice_mode_index", 3)
    assert device._voice_mode_index == 3
    name, entry = devices.set_property(device, "input_routing_type", "1-kick")
    assert entry["value"] == "1-Kick" and device._input_routing_type is device._available[1]
    devices.set_property(device, "oversample", "on")
    devices.set_property(device, "gain", "0.25")
    devices.set_property(device, "count", 7.0)
    assert device._oversample is True and device._gain == 0.25 and device._count == 7 and isinstance(device._count, int)


def test_set_property_errors():
    device = CompressorDevice()
    with pytest.raises(CommandError) as error:
        devices.set_property(device, "loop_length", 8)
    assert error.value.code == "unsupported"
    with pytest.raises(CommandError) as error:
        devices.set_property(device, "bogus", 1)
    assert error.value.code == "not_found" and "voice_mode_index" in error.value.message
    with pytest.raises(CommandError):
        devices.set_property(device, "input_routing_type", "Nowhere")
    with pytest.raises(CommandError):
        devices.set_property(device, "gain", "loud")


class MeldDevice(object):
    """Integer and boolean codes documented without enum classes (devices._STATIC_OPTIONS)."""
    name = "Meld"
    selected_engine = rw("selected_engine")
    poly_voices = rw("poly_voices")

    def __init__(self):
        self._selected_engine, self._poly_voices = False, 5


def test_static_options_for_ints_and_bools():
    device = MeldDevice()
    props = available(device)
    assert devices.property_out(device, "selected_engine", props["selected_engine"], props) == {"value": False, "item": "A", "options": ["A", "B"]}
    assert devices.property_out(device, "poly_voices", props["poly_voices"], props)["item"] == "8"
    devices.set_property(device, "selected_engine", "B")
    assert device._selected_engine is True
    devices.set_property(device, "poly_voices", 12)
    assert device._poly_voices == 6


class FakeEnumValue(int):
    def __new__(cls, number, name):
        value = int.__new__(cls, number)
        value.name = name
        return value


class FakeEnum(object):
    values = {0: FakeEnumValue(0, "classic"), 1: FakeEnumValue(1, "one_shot"), 2: FakeEnumValue(2, "slicing")}


class SimplerDevice(object):
    name = "Simpler"
    playback_mode = rw("playback_mode")
    sample = ro("sample")
    view = ro("view")

    def __init__(self, sample=None):
        self._playback_mode, self._sample, self._view = 0, sample, None


@pytest.fixture
def playback_mode_enum(monkeypatch):
    live = sys.modules["Live"]
    monkeypatch.setattr(live.SimplerDevice, "PlaybackMode", FakeEnum, raising=False)
    return FakeEnum


def test_enum_properties_by_name(playback_mode_enum):
    device = SimplerDevice()
    props = available(device)
    entry = devices.property_out(device, "playback_mode", props["playback_mode"], props)
    assert entry == {"value": 0, "item": "classic", "options": ["classic", "one_shot", "slicing"]}
    devices.set_property(device, "playback_mode", "one shot")
    assert device._playback_mode == 1 and device._playback_mode.name == "one_shot"
    devices.set_property(device, "playback_mode", 2)
    assert device._playback_mode.name == "slicing"


def test_flatten_and_property_owner():
    flat = devices._flatten_properties({"playback_mode": "slicing", "sample": {"warping": True}, "sample.gain": 0.5, "view.selected_slice": 0})
    assert flat == [("playback_mode", "slicing"), ("sample.warping", True), ("sample.gain", 0.5), ("view.selected_slice", 0)]
    sample = object()
    simpler = SimplerDevice(sample)
    assert devices._property_owner(simpler, "sample.warping") == (sample, "warping")
    assert devices._property_owner(simpler, "playback_mode") == (simpler, "playback_mode")
    with pytest.raises(CommandError):
        devices._property_owner(SimplerDevice(None), "sample.warping")  # no sample loaded
    with pytest.raises(CommandError):
        devices._property_owner(CompressorDevice(), "sample.gain")  # only Simpler has a sample
    with pytest.raises(CommandError):
        devices._property_owner(simpler, "chains.0")


class Parameter(object):
    def __init__(self, name, original_name=None, value=0.0):
        self.name, self.original_name, self.value = name, original_name or name, value

    def str_for_value(self, value):
        return "{0:g}".format(value)


class Chain(object):
    def __init__(self, name, in_note=None):
        self.name = name
        if in_note is not None:
            self.in_note = in_note


class Pad(object):
    def __init__(self, note, chains=(), name=None):
        self.note, self.chains, self.mute, self.solo = note, list(chains), False, False
        self.name = name or (chains[0].name if chains else "pad")


class RackDevice(object):
    def __init__(self, drum=False, pads=(), chains=()):
        self.name = "Drum Rack" if drum else "Instrument Rack"
        self.can_have_chains, self.can_have_drum_pads, self.can_compare_ab = True, drum, False
        self.parameters = [Parameter("Device On", value=1.0)] + [Parameter("Cutoff" if number == 2 else "Macro {0}".format(number), "Macro {0}".format(number), number / 10.0) for number in range(1, 17)]
        self.macros_mapped = [number == 2 for number in range(1, 17)]
        self.visible_macro_count = 4
        self.drum_pads = list(pads)
        self.chains = list(chains)


def test_macros_out_visible_and_mapped():
    macros = devices.macros_out(RackDevice())
    assert [macro["macro"] for macro in macros] == [1, 2, 3, 4]
    assert macros[1] == {"index": 2, "macro": 2, "name": "Cutoff", "value": 0.2, "display": "0.2", "mapped": True}
    assert len(devices.macros_out(RackDevice(), include_hidden=True)) == 16


def test_pads_out_lists_non_empty_pads():
    kick, snare = Chain("Kick", 36), Chain("Snare", 38)
    rack = RackDevice(drum=True, pads=[Pad(35), Pad(36, [kick]), Pad(38, [snare]), Pad(39)])
    assert devices.pads_out(rack) == [
        {"note": 36, "note_name": "C1", "name": "Kick", "chains": ["Kick"]},
        {"note": 38, "note_name": "D1", "name": "Snare", "chains": ["Snare"]},
    ]


def test_pads_out_of_nested_drum_rack_groups_chains_by_note():
    rack = RackDevice(drum=True, pads=[], chains=[Chain("Hat", 42), Chain("Kick A", 36), Chain("Kick B", 36)])
    assert devices.pads_out(rack) == [
        {"note": 36, "note_name": "C1", "name": "Kick A", "chains": ["Kick A", "Kick B"]},
        {"note": 42, "note_name": "F#1", "name": "Hat", "chains": ["Hat"]},
    ]


def test_drum_pad_by_note_or_name():
    kick = Chain("Kick", 36)
    rack = RackDevice(drum=True, pads=[Pad(note, [kick] if note == 36 else []) for note in range(128)])
    assert devices.drum_pad(rack, "C1").note == 36
    assert devices.drum_pad(rack, 37).note == 37
    assert devices.drum_pad(rack, "38").note == 38
    assert devices.drum_pad(rack, "kick").note == 36
    with pytest.raises(CommandError) as error:
        devices.drum_pad(rack, "Snare")
    assert "C1 Kick" in error.value.message
    with pytest.raises(CommandError):
        devices.drum_pad(RackDevice(drum=True, pads=[]), "C1")  # nested Drum Rack: no pads of its own


class LooperDevice(object):
    can_have_chains = can_have_drum_pads = can_compare_ab = False


class WavetableDevice(LooperDevice):
    can_compare_ab = True


class PluginDevice(LooperDevice):
    pass


def test_available_actions_per_class():
    rack_actions = devices.available_actions(RackDevice())
    assert "insert_chain" in rack_actions and "store_variation" in rack_actions and "copy_pad" not in rack_actions
    assert {"copy_pad", "delete_chains", "to_midi_track", "insert_chain"} <= set(devices.available_actions(RackDevice(drum=True)))
    simpler = SimplerDevice()
    simpler.can_have_chains = simpler.can_have_drum_pads = False
    simpler.can_compare_ab = True
    assert {"crop", "reverse", "warp_as", "to_drum_rack", "insert_slice", "save_ab_slot"} <= set(devices.available_actions(simpler))
    assert {"record", "overdub", "export_to_clip_slot"} <= set(devices.available_actions(LooperDevice()))
    assert {"get_modulation", "set_modulation", "add_parameter_to_modulation_matrix", "save_ab_slot"} == set(devices.available_actions(WavetableDevice()))
    assert devices.available_actions(PluginDevice()) == ["parameter_names"]


def test_every_action_belongs_to_a_known_kind():
    assert set(kind for kind, _ in devices.ACTIONS.values()) <= set(devices._KINDS)
    expected = {
        "insert_chain", "add_macro", "remove_macro", "randomize_macros", "store_variation", "recall_variation",
        "recall_last_variation", "delete_variation", "copy_pad", "delete_chains", "to_midi_track", "crop", "reverse",
        "warp_as", "warp_double", "warp_half", "replace_sample", "guess_playback_length", "insert_slice", "move_slice",
        "remove_slice", "clear_slices", "reset_slices", "to_drum_rack", "record", "overdub", "play", "stop", "clear",
        "undo", "double_length", "half_length", "double_speed", "half_speed", "export_to_clip_slot", "save_ab_slot",
        "get_modulation", "set_modulation", "add_parameter_to_modulation_matrix", "parameter_names",
    }
    assert set(devices.ACTIONS) == expected


def test_modulation_source_aliases(monkeypatch):
    names = ["amp_envelope", "envelope_2", "envelope_3", "lfo_1", "lfo_2", "midi_velocity", "midi_note",
             "midi_pitch_bend", "midi_channel_pressure", "midi_mod_wheel", "midi_random"]

    class ModulationSource(object):
        values = dict((number, FakeEnumValue(number, name)) for number, name in enumerate(names))

    monkeypatch.setattr(sys.modules["Live"].WavetableDevice, "ModulationSource", ModulationSource, raising=False)
    assert devices._modulation_source("lfo1") == 3
    assert devices._modulation_source("LFO 2") == 4
    assert devices._modulation_source("Env 1") == 0
    assert devices._modulation_source("mod wheel") == 9
    assert devices._modulation_source("midi_velocity") == 5
    assert devices._modulation_source(7) == 7
    with pytest.raises(CommandError):
        devices._modulation_source("sidechain")
