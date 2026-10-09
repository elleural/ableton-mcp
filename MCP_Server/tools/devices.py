"""WS-D: devices, parameters, racks and chains (docs/PRD.md section 7.4). Owned by workstream D."""
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

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


@tool(destructive=True)
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


# Item names of the Compressor's Model and S/C EQ Type choosers (Live 12.4.6).
COMPRESSOR_MODELS = ("Peak", "RMS", "Expand")
SIDECHAIN_EQ_TYPES = ("Low Shelf", "Bell", "High Shelf", "Low pass", "Peak", "High pass")
# What a Compressor that set_sidechain adds gets for the settings a call leaves out, chosen for ducking to a kick.
# An existing Compressor keeps them as found, so these defaults never change what the call did not add. Live's own
# defaults (RMS, sidechain EQ on as an 80 Hz high-pass) filter the kick's fundamental (about 40-65 Hz in Live's kick
# presets) out of the trigger and follow its average level, not its attack, so the duck comes out weak. Peak follows
# the attack (it ducks deeper than RMS at the same threshold); a 120 Hz low-pass keeps the fundamental and drops hats
# and claps, so a whole drum track works as the source too. For a trigger that is not a kick, sidechain_eq="off".
KICK_DUCKING = {"Model": "Peak", "S/C EQ On": "On", "S/C EQ Type": "Low pass", "S/C EQ Freq": "120 Hz"}
_EQ_NUMBERS = (("freq", "S/C EQ Freq", "Hz"), ("q", "S/C EQ Q", ""), ("gain", "S/C EQ Gain", "dB"))


def _option(value, options, what):
    """`value` spelled as in `options` (case-insensitive), else a ToolError that lists them."""
    if isinstance(value, str):
        for option in options:
            if value.strip().lower() == option.lower():
                return option
    raise ToolError("{0} must be one of {1}; got {2!r}.".format(what, ", ".join(options), value))


def _display(value, unit, what):
    """A display string for set_device_parameters: a number gets `unit`, a string ("1.2 kHz") is kept."""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "{0:g} {1}".format(value, unit).strip()
    raise ToolError("{0} must be a number or a display string such as '120 Hz'; got {1!r}.".format(what, value))


def _sidechain_eq_values(sidechain_eq):
    """Compressor parameter values for sidechain_eq: {} for None, "off", or {type, freq, q, gain} (None = not given)."""
    if sidechain_eq is None:
        return {}
    if isinstance(sidechain_eq, str) and sidechain_eq.strip().lower() == "off":
        return {"S/C EQ On": "Off"}
    if not isinstance(sidechain_eq, dict):
        raise ToolError('sidechain_eq must be "off" or an object such as {"type": "Low pass", "freq": 120}; got '
                        + repr(sidechain_eq) + ".")
    unknown = sorted(str(key) for key in sidechain_eq if key not in ("type", "freq", "q", "gain"))
    if unknown:
        raise ToolError("sidechain_eq takes type, freq, q and gain; got {0}.".format(", ".join(unknown)))
    given = dict((key, value) for key, value in sidechain_eq.items() if value is not None)
    values = {"S/C EQ On": "On"}
    if "type" in given:
        values["S/C EQ Type"] = _option(given["type"], SIDECHAIN_EQ_TYPES, "sidechain_eq type")
    for key, name, unit in _EQ_NUMBERS:
        if key in given:
            values[name] = _display(given[key], unit, "sidechain_eq " + key)
    return values


def _with_kick_ducking(values):
    """`values` (Model and sidechain EQ) over KICK_DUCKING, for a Compressor this call added. With the EQ
    switched off, its type and frequency are left alone."""
    merged = dict(KICK_DUCKING)
    if values.get("S/C EQ On") == "Off":
        del merged["S/C EQ Type"], merged["S/C EQ Freq"]
    merged.update(values)
    return merged


def _as_found(track, path, values):
    """Display values of the KICK_DUCKING settings that writing `values` leaves untouched, read back (the EQ's
    type and frequency only while the EQ is on); {} without a read when nothing is left."""
    names = [name for name in KICK_DUCKING if name not in values]
    if values.get("S/C EQ On") == "Off":
        names = [name for name in names if name == "Model"]
    if not names:
        return {}
    parameters = call("get_device", track=track, device=path).get("parameters", [])
    shown = dict((item["name"], item["display"]) for item in parameters)
    if str(shown.get("S/C EQ On")).lower() == "off":
        names = [name for name in names if name in ("Model", "S/C EQ On")]
    return dict((name, shown[name]) for name in names if name in shown)


def _compressor_path(track, device, create=True):
    """(path, added): `device`, else the first Compressor on the track, else (with create) a newly added one."""
    if device is not None:
        return device, False
    for entry in call("get_devices", track=track).get("devices", []):
        if entry.get("class_name") == "Compressor2" or entry.get("class") == "Compressor":
            return entry.get("path", entry.get("index")), False
    if not create:
        raise ToolError("Track {0!r} has no Compressor, so there is no sidechain to turn off (for one inside a rack, "
                        "pass its path as device).".format(track))
    added = call("add_device", track=track, name="Compressor")
    entry = added.get("device", added)
    return entry.get("path", entry.get("index")), True


@tool()
def set_sidechain(track: int | str, source: int | str | None = None, channel: str = "Post FX", threshold_db: float = -24.0,
                  ratio: float = 4.0, attack_ms: float = 1.0, release_ms: float = 120.0, enabled: bool = True,
                  device: int | str | list[int | str] | None = None, model: str | None = None,
                  sidechain_eq: str | dict[str, Any] | None = None) -> dict:
    """Duck `track` whenever `source` plays: sidechain compression, e.g. a bass or pad pumping to the kick.

    Uses `device`, else the track's first Compressor (only its sidechain is routable), else a new one at the end.
    source: the trigger track, with audio output (for a kick in a drum track, that track). channel: "Post FX"
    (default), "Pre FX" or "Post Mixer". Sets S/C On, threshold (dB), ratio, attack and release (ms);
    enabled=False turns it off. model: "Peak", "RMS" or "Expand". sidechain_eq filters the trigger: "off", or
    {"type", "freq" (Hz), "q", "gain" (dB)}; types: Low pass, High pass, Bell, Peak, Low Shelf, High Shelf.
    A Compressor this adds gets Peak and a 120 Hz low pass, for a kick (other triggers: "off"); an existing one
    keeps what you omit.
    Example: set_sidechain("Bass", "Drums", threshold_db=-30, ratio=6, release_ms=150).
    """
    detector = {"Model": _option(model, COMPRESSOR_MODELS, "model")} if model is not None else {}
    detector.update(_sidechain_eq_values(sidechain_eq))
    if enabled and source is None:
        raise ToolError("set_sidechain needs source (the track that triggers the ducking).")
    source_name = call("get_track", track=source)["name"] if enabled else None
    path, added = _compressor_path(track, device, create=enabled)
    out = {"track": track, "device": path}
    if enabled:
        routing = call("set_device", track=track, device=path,
                       properties={"input_routing_type": source_name, "input_routing_channel": channel})
        out.update(added_compressor=added, source=source_name, channel=channel,
                   routing=routing.get("properties", routing))
        values = {
            "S/C On": "On",
            "Threshold": "{0:g} dB".format(threshold_db),
            "Ratio": "{0:g}".format(ratio),
            "Attack": "{0:g} ms".format(attack_ms),
            "Release": "{0:g} ms".format(release_ms),
        }
    else:
        out["enabled"] = False
        values = {"S/C On": "Off"}
    values.update(_with_kick_ducking(detector) if added else detector)
    result = call("set_device_parameters", track=track, device=path, values=values)
    out["parameters"] = result.get("parameters", result)
    if result.get("errors"):
        out["errors"] = result["errors"]
    found = _as_found(track, path, values) if enabled and not added else {}
    if found:
        out["as_found"] = found
    return out
