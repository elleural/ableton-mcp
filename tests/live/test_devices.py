"""Live tests for WS-D devices: insertion, device trees, parameters in display units, type-specific
properties, racks, drum pads, chains, device actions, moves (run against the running Live).

Every track these tests create is a "[test:devices] ..." scratch track, removed afterwards. Only native
Live devices and Core Library content are relied on, so packs installed mid-run do not matter.
"""
import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server.tools.browser import load_from_browser, search_browser
from MCP_Server.tools.devices import (add_device, delete_device, device_action, duplicate_device, get_device, get_devices,
                                      move_device, set_chain, set_device, set_device_parameters)


def error_of(function, *args, **kwargs):
    with pytest.raises(ToolError) as caught:
        function(*args, **kwargs)
    return str(caught.value)


def names(track):
    return [device["name"] for device in get_devices(track)["devices"]]


def a_sample(query="kick", category="drums"):
    """A sample from the browser (searched, never hard-coded, so content changes do not matter)."""
    for _ in range(40):
        found = search_browser(query, category, limit=50)
        samples = [item for item in found["results"] if item["kind"] == "sample"]
        if samples:
            return samples[0]
        time.sleep(0.5)  # The index may still be building in the background.
    pytest.fail("No sample found in the browser for {0!r}".format(query))


def test_add_and_read_devices(scratch):
    midi = scratch.track("synth", "midi")
    audio = scratch.track("fx", "audio")
    assert add_device(midi, "operator")["device"]["class"] == "Operator"
    assert add_device(midi, "Arpeggiator", position=0)["device"]["index"] == 0
    added = add_device(midi, "REVERB")
    assert added["device"] == dict(added["device"], index=2, path="2", name="Reverb", type="audio_effect", enabled=True)
    assert [item["name"] for item in added["devices"]] == ["Arpeggiator", "Operator", "Reverb"]
    sampler = add_device(scratch.track("drum sampler", "midi"), "drum sampler")  # inserts by its internal name
    assert sampler["device"]["class"] == "Drum Sampler"

    tree = get_devices(midi)
    assert tree["track"]["name"] == midi and [item["path"] for item in tree["devices"]] == ["0", "1", "2"]
    detail = get_device(midi, "Operator")
    assert detail["path"] == "1" and detail["track"]["name"] == midi and detail["collapsed"] is False
    assert detail["parameters"][0]["name"] == "Device On" and detail["parameters"][0]["items"] == ["Off", "On"]
    brief = get_device(midi, 1, parameters=False)
    assert "parameters" not in brief and brief["parameter_count"] == len(detail["parameters"])
    rich = get_device(midi, "Reverb", detail=True)
    assert "is_quantized" in rich["parameters"][1]

    assert "only go on MIDI tracks" in error_of(add_device, audio, "Operator")
    assert "only go on MIDI tracks" in error_of(add_device, "master", "Arpeggiator")
    assert "more than one instrument" in error_of(add_device, midi, "Wavetable")
    assert "MIDI effects before instruments" in error_of(add_device, midi, "Chord", position=3)
    assert "not found" in error_of(add_device, midi, "Operatorr")
    assert "not found" in error_of(get_device, midi, "Nope")
    assert names(audio) == []


def test_parameters_in_display_units(scratch):
    track = scratch.track("params", "audio")
    add_device(track, "Reverb")
    out = set_device_parameters(track, "Reverb", {
        "Decay Time": "2.5 s", "Dry/Wet": "30 %", "Predelay": "10 ms", "Diff. Hi Freq": "2 kHz",
        "Size Smoothing": "slow", "Reflect Level": "-3 dB", "4": 0.5, "Bogus": 1,
    })
    shown = dict((item["name"], item["display"]) for item in out["parameters"])
    assert shown["Decay Time"] == "2.50 s" and shown["Dry/Wet"] == "30 %" and shown["Predelay"] == "10.0 ms"
    assert shown["Diff. Hi Freq"] == "2.00 kHz" and shown["Size Smoothing"] == "Slow" and shown["Reflect Level"] == "-3.0 dB"
    assert [item["value"] for item in out["parameters"] if item["index"] == 4] == [0.5]
    assert [item["parameter"] for item in out["errors"]] == ["Bogus"]
    assert "No parameter was set" in error_of(set_device_parameters, track, "Reverb", {"Bogus": 1, "Dry/Wet": "loud"})
    assert "Options: None, Slow, Fast" in error_of(set_device_parameters, track, "Reverb", {"Size Smoothing": "Medium"})
    add_device(track, "Auto Filter")
    frequency = set_device_parameters(track, "Auto Filter", {"Frequency": "800 Hz"})["parameters"][0]
    assert frequency["display"].startswith("800")


def test_note_values_and_display_ranges(scratch):
    """Note values select their step on stepped parameters Live does not quantize, ratios read like
    display_value, and a display value outside the display range is an error instead of a clamp."""
    track = scratch.track("steps", "audio")
    for name in ("Echo", "Drum Buss", "Roar", "Compressor", "Auto Filter"):
        add_device(track, name)
    shown = dict((item["name"], item["display"]) for item in set_device_parameters(
        track, "Echo", {"L Synced": "1/16", "Mod Rate": "3/16", "L 16th": "6"})["parameters"])
    assert shown == {"L Synced": "1/16", "Mod Rate": "3/16", "L 16th": "6 "}, shown
    assert "Values: 1/64, 1/32, 1/16, 1/8, 1/4, 1/2, 1" in error_of(set_device_parameters, track, "Echo", {"L Synced": "1/5"})
    assert set_device_parameters(track, "Roar", {"FB Synced": "1/8"})["parameters"][0]["display"] == "1 / 8"
    shown = dict((item["name"], item["display"]) for item in set_device_parameters(
        track, "Auto Filter", {"LFO Rate": "1.5", "LFO 16th": "4/16"})["parameters"])
    assert shown == {"LFO Rate": "1.5", "LFO 16th": "4  / 16"}, shown
    message = error_of(set_device_parameters, track, "Drum Buss", {"Transients": "25 %"})
    assert "outside the display range of 'Transients': -1.00 .. 1.00" in message, message
    assert set_device_parameters(track, "Drum Buss", {"Transients": "0.25"})["parameters"][0]["display"] == "0.25"
    shown = dict((item["name"], item["display"]) for item in set_device_parameters(
        track, "Compressor", {"Ratio": "2.5 : 1", "Expansion Ratio": "1 : 1.5"})["parameters"])
    assert shown == {"Ratio": "2.50 : 1", "Expansion Ratio": "1 : 1.50"}, shown


def test_set_device_and_type_specific_properties(scratch):
    synth = scratch.track("wavetable", "midi")
    side = scratch.track("sidechain", "audio")
    add_device(synth, "Wavetable")
    out = set_device(synth, "Wavetable", enabled=False, name="Pad", collapsed=True, properties={
        "oscillator_1_wavetable_category": "Retro", "oscillator_1_wavetable_index": 1, "unison_mode": "classic",
        "poly_voices": "sixteen", "mono_poly": "mono", "bogus": 1,
    })
    assert out["enabled"] is False and out["name"] == "Pad" and out["collapsed"] is True
    props = out["properties"]
    assert props["oscillator_1_wavetable_category"]["item"] == "Retro" and props["unison_mode"]["item"] == "classic"
    assert props["poly_voices"]["item"] == "sixteen" and props["mono_poly"] == {"value": 0, "item": "mono"}
    assert [item["property"] for item in out["errors"]] == ["bogus"]
    detail = get_device(synth, "Pad", parameters=False)
    assert detail["enabled"] is False and "Retro" in detail["properties"]["oscillator_1_wavetable_category"]["options"]
    assert detail["properties"]["visible_modulation_target_names"]["read_only"] is True
    assert "read-only" in error_of(set_device, synth, "Pad", properties={"visible_modulation_target_names": []})
    assert set_device(synth, "Pad", compare_b=True)["compare_b"] is True
    restored = set_device(synth, "Pad", compare_b=False, enabled=True, collapsed=False)
    assert restored["compare_b"] is False and restored["enabled"] is True

    add_device(side, "Compressor")
    routing = get_device(side, "Compressor", parameters=False)["properties"]["input_routing_type"]
    assert synth in routing["options"]
    assert set_device(side, "Compressor", properties={"input_routing_type": synth})["properties"]["input_routing_type"]["value"] == synth
    channels = get_device(side, "Compressor", parameters=False)["properties"]["input_routing_channel"]
    assert channels["value"] in channels["options"] and len(channels["options"]) > 1
    set_device(side, "Compressor", properties={"input_routing_type": "No Input"})

    rack_track = scratch.track("ab", "midi")
    add_device(rack_track, "Instrument Rack")
    assert "does not support A/B compare" in error_of(set_device, rack_track, "Instrument Rack", compare_b=True)


def test_racks_chains_macros_and_variations(scratch):
    track = scratch.track("rack", "midi")
    add_device(track, "Instrument Rack")
    first = add_device(track, "Operator", chain="Instrument Rack/new")
    assert first["device"]["path"] == "0/0/0" and first["chain"]["index"] == 0
    assert add_device(track, "Reverb", chain="Instrument Rack/0")["device"]["name_path"] == "Instrument Rack/Operator/Reverb"
    add_device(track, "Drift", chain=["Instrument Rack", "new"])
    tree = get_devices(track)["devices"][0]
    assert [chain["name"] for chain in tree["chains"]] == ["Operator", "Drift"]
    assert [item["path"] for item in tree["chains"][0]["devices"]] == ["0/0/0", "0/0/1"]
    assert len(tree["macros"]) == 8 and tree["variation_count"] == 0
    assert get_device(track, "Instrument Rack/Operator/Reverb", parameters=False)["path"] == "0/0/1"
    assert get_device(track, [0, 1, 0], parameters=False)["name"] == "Drift"

    chain = set_chain(track, "Instrument Rack", "Drift", name="Lead", volume_db=-6, pan="25L", mute=True, color=5)
    assert (chain["name"], chain["volume_db"], chain["pan"], chain["mute"], chain["color_index"]) == ("Lead", -6.0, -0.5, True, 5)
    assert set_chain(track, "Instrument Rack", 1, volume_db="-inf", mute=False)["volume_db"] == "-inf"
    assert "only to Drum Rack chains" in error_of(set_chain, track, "Instrument Rack", "Lead", choke_group=1)
    assert "not a rack" in error_of(set_chain, track, "Instrument Rack/Operator/Operator", 0)

    def act(action, **args):
        return device_action(track, "Instrument Rack", action, args or None)

    assert act("add_macro")["visible_macro_count"] == 10 and act("remove_macro")["visible_macro_count"] == 8
    assert act("store_variation")["variations"]["count"] == 1
    assert act("recall_variation", index=0)["variations"]["selected"] == 0
    assert len(act("recall_last_variation")["macros"]) == 8 and len(act("randomize_macros")["macros"]) == 8
    assert "does not exist" in error_of(act, "recall_variation", index=3)
    assert act("delete_variation", index=0)["variations"]["count"] == 0
    assert "no stored variations" in error_of(act, "recall_variation")
    inserted = act("insert_chain", index=0, name="Empty")["chain"]
    assert (inserted["index"], inserted["name"], inserted["volume_db"]) == (0, "Empty", 0.0)
    detail = get_device(track, "Instrument Rack", parameters=False)
    assert [chain["name"] for chain in detail["chains"]][:3] == ["Empty", "Operator", "Lead"]
    assert detail["chain_selector"]["name"] == "Chain Selector" and detail["variations"] == {"count": 0, "selected": -1}
    assert "Actions for this device" in error_of(act, "crop")
    assert "Arguments: index, name, note" in error_of(act, "insert_chain", bogus=1)
    assert "chain" in error_of(add_device, track, "Saturator", chain="Instrument Rack")


def test_drum_rack_pads_and_drum_chains(scratch):
    track = scratch.track("drums", "midi")
    add_device(track, "Drum Rack")
    kick = add_device(track, "Simpler", chain="Drum Rack/C1")
    assert kick["chain"]["in_note"] == 36 and kick["device"]["path"] == "0/0/0"
    add_device(track, "Saturator", chain="Drum Rack/D1")
    assert "Max for Live" in error_of(add_device, track, "DS Kick", chain="Drum Rack/F1")
    rack = get_devices(track)["devices"][0]
    assert [(pad["note"], pad["note_name"]) for pad in rack["pads"]] == [(36, "C1"), (38, "D1")]  # F1 got no chain
    assert [chain["note_name"] for chain in rack["chains"]] == ["C1", "D1"]

    chain = set_chain(track, "Drum Rack", "D1", name="Snare", in_note="D#1", out_note="C3", choke_group=2, solo=True)
    assert (chain["in_note"], chain["note_name"], chain["out_note"], chain["choke_group"], chain["solo"]) == (39, "D#1", 60, 2, True)
    assert "All Notes" in error_of(set_chain, track, "Drum Rack", "Snare", in_note="all", solo=False)
    assert get_device(track, "Drum Rack", parameters=False)["chains"][1]["solo"] is True  # nothing changed
    moved = set_chain(track, "Drum Rack", "Snare", solo=False, choke_group="none", in_note=38)
    assert (moved["note_name"], moved["choke_group"], moved["solo"]) == ("D1", 0, False)
    assert get_device(track, "Drum Rack/C1/Simpler", parameters=False)["class"] == "Simpler"
    assert get_device(track, "Drum Rack/Snare/0", parameters=False)["name"] == "Saturator"
    detail = get_device(track, "Drum Rack", parameters=False)
    assert "chain_selector" not in detail and [pad["name"] for pad in detail["pads"]] == ["Simpler", "Snare"]

    pads = device_action(track, "Drum Rack", "copy_pad", {"source": "C1", "destination": "G1"})["pads"]
    assert 43 in [pad["note"] for pad in pads]
    pads = device_action(track, "Drum Rack", "delete_chains", {"pad": "G1"})["pads"]
    assert 43 not in [pad["note"] for pad in pads]
    created = device_action(track, "Drum Rack", "to_midi_track", {"pad": "C1", "name": scratch.name("from pad")})["created_tracks"]
    assert [item["name"] for item in created] == [scratch.name("from pad")]
    assert names(scratch.name("from pad"))
    assert "empty" in error_of(device_action, track, "Drum Rack", "copy_pad", {"source": "A1", "destination": "B1"})
    assert "C1 Simpler" in error_of(device_action, track, "Drum Rack", "delete_chains", {"pad": "Clap"})
    assert "0 (none) .. 16" in error_of(set_chain, track, "Drum Rack", "Snare", choke_group=17)


def test_move_duplicate_and_delete(scratch):
    midi = scratch.track("move src", "midi")
    audio = scratch.track("move dst", "audio")
    for name in ("Operator", "Reverb", "Saturator"):
        add_device(midi, name)
    assert duplicate_device(midi, "Reverb")["device"]["index"] == 2
    assert names(midi) == ["Operator", "Reverb", "Reverb", "Saturator"]
    assert "one instrument" in error_of(duplicate_device, midi, "Operator")
    assert move_device(midi, "Saturator", to_position=1)["device"]["index"] == 1
    assert names(midi) == ["Operator", "Saturator", "Reverb", "Reverb"]
    across = move_device(midi, 3, to_track=audio, to_position=0)
    assert across["device"]["path"] == "0" and names(audio) == ["Reverb"] and len(across["source_devices"]) == 3
    assert "only go on MIDI tracks" in error_of(move_device, midi, "Operator", to_track=audio)
    add_device(audio, "Audio Effect Rack")
    into = move_device(audio, "Reverb", to_chain="Audio Effect Rack/new")
    assert into["device"]["name_path"] == "Audio Effect Rack/Reverb/Reverb"
    out = move_device(audio, "Audio Effect Rack/0/0", to_position=-1)
    assert out["device"]["path"] == "1" and names(audio) == ["Audio Effect Rack", "Reverb"]
    assert "own chain" in error_of(move_device, audio, "Audio Effect Rack", to_chain="Audio Effect Rack/0")
    assert "out of range" in error_of(move_device, midi, "Reverb", to_position=9)
    deleted = delete_device(midi, "Saturator")
    assert deleted["deleted"]["name"] == "Saturator" and names(midi) == ["Operator", "Reverb"]
    assert [item["name"] for item in delete_device(audio, 0)["devices"]] == ["Reverb"]
    assert "not found" in error_of(delete_device, midi, "Saturator")


def test_simpler_sample_actions(scratch):
    sample = a_sample()
    track = scratch.track("simpler", "midi")
    simpler = load_from_browser(track, uri=sample["uri"])["devices"][0]
    assert simpler["class"] == "Simpler"
    detail = get_device(track, 0, parameters=False)
    file_path, rate = detail["sample"]["file_path"], detail["sample"]["sample_rate"]
    assert detail["sample"]["duration_s"] > 0 and detail["properties"]["playback_mode"]["options"] == ["classic", "one_shot", "slicing"]
    assert device_action(track, 0, "guess_playback_length")["beats"] > 0

    out = set_device(track, 0, properties={"sample.warping": True, "sample": {"warp_mode": "beats"}, "playback_mode": "slicing",
                                           "sample.slicing_style": "manual"})
    assert out["properties"]["sample.warping"]["value"] is True and out["properties"]["sample.warp_mode"]["item"] == "beats"
    assert out["properties"]["playback_mode"]["item"] == "slicing" and out["properties"]["sample.slicing_style"]["item"] == "manual"
    assert device_action(track, 0, "warp_as", {"beats": "1 bars"})["sample"]["warping"] is True
    flags = get_device(track, 0, parameters=False)["properties"]
    for action in ("warp_double", "warp_half"):  # Live offers them only while the result stays in tempo range.
        if flags["can_" + action]["value"]:
            assert device_action(track, 0, action)["sample"]["warping"] is True
        else:
            assert "not available" in error_of(device_action, track, 0, action)
    frame = int(round(0.1 * rate))
    assert frame in device_action(track, 0, "insert_slice", {"seconds": 0.1})["slices"]
    assert device_action(track, 0, "move_slice", {"time": frame, "to": frame + 100})["moved_to"] == frame + 100
    assert frame + 100 not in device_action(track, 0, "remove_slice", {"time": frame + 100})["slices"]
    device_action(track, 0, "insert_slice", {"time": frame})
    device_action(track, 0, "reset_slices")
    device_action(track, 0, "clear_slices")
    device_action(track, 0, "insert_slice", {"seconds": 0.05})
    converted = device_action(track, 0, "to_drum_rack")
    assert converted["device"]["class"] == "Drum Rack" and get_devices(track)["devices"][0]["pads"]

    other = scratch.track("simpler edit", "midi")
    load_from_browser(other, uri=sample["uri"])
    assert device_action(other, 0, "reverse")["sample"]["file_path"] != file_path
    device_action(other, 0, "crop")
    assert device_action(other, 0, "replace_sample", {"file_path": file_path})["sample"]["file_path"] == file_path
    assert "does not exist" in error_of(device_action, other, 0, "replace_sample", {"file_path": "/nonexistent/kick.wav"})
    assert "exactly one of time" in error_of(device_action, other, 0, "insert_slice", {})
    assert "slicing mode" in error_of(device_action, other, 0, "to_drum_rack")
    empty = scratch.track("empty simpler", "midi")
    add_device(empty, "Simpler")
    assert "no sample loaded" in error_of(device_action, empty, "Simpler", "crop")
    assert "no sample loaded" in error_of(set_device, empty, "Simpler", properties={"sample.warping": True})


def test_looper_actions(scratch, song_state):
    track = scratch.track("looper", "audio")
    add_device(track, "Looper")
    lengths = get_device(track, "Looper", parameters=False)["properties"]["record_length_index"]["options"]
    assert any("4 bars" in item for item in lengths)
    for action in ("record", "stop", "play", "overdub", "stop", "undo", "clear", "double_length", "half_length", "double_speed", "half_speed"):
        assert "loop_length" in device_action(track, "Looper", action)
    assert "export" in error_of(device_action, track, "Looper", "export_to_clip_slot", {"track": track, "slot": 0})
    out = set_device(track, "Looper", properties={"record_length": "4 bars", "overdub_after_record": False})
    assert out["properties"]["record_length_index"]["item"].strip() == "4 bars"


def test_wavetable_modulation_and_ab_slot(scratch):
    track = scratch.track("modulation", "midi")
    add_device(track, "Wavetable")
    matrix = device_action(track, "Wavetable", "get_modulation")
    assert "Osc 1 Pos" in matrix["targets"] and "lfo_1" in matrix["sources"]
    changed = device_action(track, "Wavetable", "set_modulation", {"target": "Osc 1 Pos", "source": "LFO 1", "value": 0.5})
    assert (changed["source"], changed["value"]) == ("lfo_1", 0.5)
    assert device_action(track, "Wavetable", "get_modulation", {"target": "osc 1 pos", "source": "lfo1"})["value"] == 0.5
    assert device_action(track, "Wavetable", "get_modulation", {"target": "Osc 1 Pos"})["amounts"]["lfo_1"] == 0.5
    added = device_action(track, "Wavetable", "add_parameter_to_modulation_matrix", {"parameter": "Osc 2 Pos"})
    assert len(added["targets"]) > len(matrix["targets"]) and 0 <= added["target_index"] < len(added["targets"])
    assert "compare_b" in device_action(track, "Wavetable", "save_ab_slot")
    assert "It is for plug-ins" in error_of(device_action, track, "Wavetable", "parameter_names")
    assert "Modulation target" in error_of(device_action, track, "Wavetable", "set_modulation", {"target": "Nope", "source": 0, "value": 1})
