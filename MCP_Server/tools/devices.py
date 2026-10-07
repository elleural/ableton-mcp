"""WS-D: devices, parameters, racks and chains (docs/PRD.md section 7.4). Owned by workstream D."""
from typing import Any

from ..app import call, tool


@tool()
def add_device(track: int | str, name: str, position: int = -1, chain: str | list[int | str] | None = None) -> dict:
    """Insert a native Live device by name on a track, or into a rack chain.

    name: case-insensitive ("Operator", "eq eight", "Drum Rack"). position: device index (-1 = end).
    chain: a path to a rack chain alternating device and chain segments: "Instrument Rack/0",
    "Drum Rack/C1" (a drum note gets a new chain if the pad is empty) or "Audio Effect Rack/new".
    Instruments and MIDI effects need a MIDI track or MIDI rack chain. Max for Live devices listed with
    Live's devices (LFO, DS Kick, ...) load through the browser. Presets and packs: load_from_browser.
    Example: add_device("Bass", "Saturator").
    """
    return call("add_device", track=track, name=name, position=position, chain=chain)


@tool(read_only=True)
def get_devices(track: int | str) -> dict:
    """Device tree of a track: every device with path ("1/0/0"), name_path ("Drum Rack/Kick/Simpler"),
    class, type and on/off; racks with chains (recursively), visible macros and variation count; Drum Racks
    with their non-empty pads (note, note name, pad and chain names). Pass a path as `device` to other tools.
    """
    return call("get_devices", track=track)


@tool(read_only=True)
def get_device(track: int | str, device: int | str | list[int | str], parameters: bool = True,
               detail: bool = False) -> dict:
    """One device in detail: parameters (index, value, display, range, items), type-specific properties
    with their options (Simpler mode, Wavetable oscillators, Compressor sidechain routing, plug-in presets,
    ...), rack chains with mixer, pads, macros, variations and chain selector, and Simpler's sample
    (file, markers, warping, slices).

    device: index, name or path ("Drum Rack/C1/Simpler", "1/0/0"). parameters=False skips the parameter
    list; detail=True adds parameter metadata, hidden macros, full option lists and sample detail.
    """
    return call("get_device", track=track, device=device, parameters=parameters, detail=detail)


@tool(idempotent=True)
def set_device_parameters(track: int | str, device: int | str | list[int | str], values: dict[str, Any]) -> dict:
    """Set several device parameters in one call; returns each new value and display string.

    values: {parameter name or index: value}. Numbers are raw values (min/max from get_device). Strings are
    display values with units ("-6 dB", "800 Hz", "1.2 kHz", "250 ms", "2.5 s", "30 %", "25L") or item
    names of switches and choosers ("Sine", "On"). Names match exactly, then by original name, then a
    unique substring. Failures are listed in "errors" without stopping the others.
    Example: set_device_parameters("Bass", "Auto Filter", {"Frequency": "800 Hz", "Resonance": 0.4}).
    """
    return call("set_device_parameters", track=track, device=device, values=values)


@tool(idempotent=True)
def set_device(track: int | str, device: int | str | list[int | str], enabled: bool | None = None,
               name: str | None = None, collapsed: bool | None = None, compare_b: bool | None = None,
               properties: dict[str, Any] | None = None) -> dict:
    """Change a device: enabled (on/off), name, collapsed, compare_b (A/B compare slot B) and the
    type-specific properties get_device lists.

    properties: {name: value}; option properties take an option name or index ("playback_mode":
    "one_shot", "voice_mode": "Mono", "selected_preset_index": "Init"); routing properties take display
    names ("input_routing_type": "Kick" for a Compressor sidechain). "sample.<name>" sets Simpler's sample
    ("sample.warping": true, "sample.warp_mode": "complex"); "view.<name>" sets view properties.
    Failures are listed per property.
    """
    return call("set_device", track=track, device=device, enabled=enabled, name=name, collapsed=collapsed,
                compare_b=compare_b, properties=properties)


@tool()
def device_action(track: int | str, device: int | str | list[int | str], action: str,
                  args: dict[str, Any] | None = None) -> dict:
    """Run a type-specific device function; args holds its named arguments.

    Racks: insert_chain(index, name, note), add_macro, remove_macro, randomize_macros, store_variation,
    recall_variation(index), recall_last_variation, delete_variation(index). Drum Racks: copy_pad(source,
    destination), delete_chains(pad), to_midi_track(pad, name). Simpler: crop, reverse, warp_as(beats),
    warp_double, warp_half, replace_sample(file_path), guess_playback_length, insert_slice/remove_slice
    (time in frames or seconds), move_slice(time, to), clear_slices, reset_slices, to_drum_rack.
    Looper: record, overdub, play, stop, clear, undo, double_length, half_length, double_speed, half_speed,
    export_to_clip_slot(track, slot). Wavetable: get_modulation(target, source), set_modulation(target,
    source, value), add_parameter_to_modulation_matrix(parameter). Plug-ins: parameter_names(begin, end).
    A/B devices: save_ab_slot.
    """
    return call("device_action", track=track, device=device, action=action, args=args)


@tool(destructive=True)
def delete_device(track: int | str, device: int | str | list[int | str]) -> dict:
    """Delete a device (a rack with everything in it) from its track or chain; returns what remains.

    Destructive: confirm with the user before deleting their own work (undo reverts it).
    """
    return call("delete_device", track=track, device=device)


@tool()
def duplicate_device(track: int | str, device: int | str | list[int | str]) -> dict:
    """Duplicate a device (racks with their contents) right after itself in its track or chain.

    Live will not duplicate a track's instrument: use duplicate_track, or another Instrument Rack chain.
    """
    return call("duplicate_device", track=track, device=device)


@tool()
def move_device(track: int | str, device: int | str | list[int | str], to_track: int | str | None = None,
                to_position: int | None = None, to_chain: str | list[int | str] | None = None) -> dict:
    """Move a device within its chain, to another track, or into a rack chain.

    to_track: destination track (default: the same track). to_position: index in the destination
    (omitted or -1 = end). to_chain: a chain path in the destination track ("Drum Rack/C1",
    "Audio Effect Rack/0", "Instrument Rack/new"). Live picks the nearest valid position (MIDI effects stay
    before the instrument); instruments and MIDI effects cannot go onto audio tracks.
    """
    return call("move_device", track=track, device=device, to_track=to_track, to_position=to_position, to_chain=to_chain)


@tool(idempotent=True)
def set_chain(track: int | str, device: int | str | list[int | str], chain: int | str, name: str | None = None,
              color: int | str | None = None, mute: bool | None = None, solo: bool | None = None,
              volume_db: float | str | None = None, pan: float | str | None = None, in_note: int | str | None = None,
              out_note: int | str | None = None, choke_group: int | None = None) -> dict:
    """Change a rack chain: name, colour, mute, solo, volume_db ("-inf" allowed), pan (-1..1 or "25L"), and
    for Drum Rack chains in_note (the pad that plays it, as a note name or number: this moves the chain to
    another pad), out_note and choke_group (0 = none, 1..16).

    device: the rack (index, name or path). chain: index, name, drum note ("C1") or "return:0" for a
    return chain. Example: set_chain("Drums", "Drum Rack", "C1", volume_db=-3, choke_group=1).
    """
    return call("set_chain", track=track, device=device, chain=chain, name=name, color=color, mute=mute, solo=solo,
                volume_db=volume_db, pan=pan, in_note=in_note, out_note=out_note, choke_group=choke_group)
