"""WS-D: devices, parameters, racks, chains and device actions (docs/PRD.md section 7.4).

Devices are addressed through refs.device: an index, a name, or a path through racks that alternates
device and chain segments ("Drum Rack/Kick/Simpler", "1/0/0" or [1, "C1", 0]). Chain segments take an
index, a chain name or a drum note. Every device in an output carries `path` and `name_path`.

Type-specific properties (Simpler mode, Wavetable oscillators, Compressor sidechain, plug-in presets, ...)
are discovered generically: the properties a device's class defines beyond the base Device, with their
option lists ("<x>_list", "available_<x>s", plug-in presets, ...) resolved to names.
"""
import math
import re

from .. import refs
from .. import values as units
from ..core import command
from ..errors import CommandError, not_found

# ---------------------------------------------------------------------------
# Introspection tables
# ---------------------------------------------------------------------------

# Members that are objects or lists of objects; dedicated sections cover them (chains, sample, ...).
_OBJECT_MEMBERS = frozenset((
    "canonical_parent", "view", "sample", "chains", "return_chains", "drum_pads", "visible_drum_pads",
    "chain_selector", "audio_inputs", "audio_outputs", "midi_inputs", "midi_outputs", "parameters",
))
# Rack scalars reported in the rack section ("macros", "variations") instead of "properties".
_RACK_SECTION = frozenset(("variation_count", "selected_variation_index", "visible_macro_count", "macros_mapped", "has_macro_mappings"))
# Option lists whose names do not follow the "<x>_index" -> "<x>_list" or "<x>" -> "<x>_list" pattern.
_COMPANIONS = {
    "selected_preset_index": "presets",
    "oscillator_1_wavetable_index": "oscillator_1_wavetables",
    "oscillator_2_wavetable_index": "oscillator_2_wavetables",
    "oscillator_1_wavetable_category": "oscillator_wavetable_categories",
    "oscillator_2_wavetable_category": "oscillator_wavetable_categories",
}
# Integer properties whose meaning is one of Live's enums: (class, property) -> (Live module, enum).
_ENUM_PROPERTIES = {
    ("SimplerDevice", "playback_mode"): ("SimplerDevice", "PlaybackMode"),
    ("SimplerDevice", "slicing_playback_mode"): ("SimplerDevice", "SlicingPlaybackMode"),
    ("WavetableDevice", "filter_routing"): ("WavetableDevice", "FilterRouting"),
    ("WavetableDevice", "mono_poly"): ("WavetableDevice", "Voicing"),
    ("WavetableDevice", "oscillator_1_effect_mode"): ("WavetableDevice", "EffectMode"),
    ("WavetableDevice", "oscillator_2_effect_mode"): ("WavetableDevice", "EffectMode"),
    ("WavetableDevice", "poly_voices"): ("WavetableDevice", "VoiceCount"),
    ("WavetableDevice", "unison_mode"): ("WavetableDevice", "UnisonMode"),
    ("Eq8Device", "edit_mode"): ("Eq8Device", "EditMode"),
    ("Eq8Device", "global_mode"): ("Eq8Device", "GlobalMode"),
    ("Sample", "slicing_style"): ("Sample", "SlicingStyle"),
    ("Sample", "slicing_beat_division"): ("Sample", "SlicingBeatDivision"),
    ("Sample", "beats_transient_loop_mode"): ("Sample", "TransientLoopMode"),
}
# Integer properties documented with fixed meanings but no enum class (lom_docs_12.4.5.md).
_STATIC_OPTIONS = {
    ("MeldDevice", "selected_engine"): ["A", "B"],
    ("MeldDevice", "unison_voices"): ["off", "2", "3", "4"],
    ("MeldDevice", "mono_poly"): ["mono", "poly"],
    ("MeldDevice", "poly_voices"): ["2", "3", "4", "5", "6", "8", "12"],
    ("Sample", "warp_mode"): ["beats", "tones", "texture", "repitch", "complex", "rex", "complex_pro"],
    ("Sample", "beats_granulation_resolution"): ["1 bar", "1/2", "1/4", "1/8", "1/16", "1/32", "transients"],
}
_SAMPLE_PROPERTIES = (
    "start_marker", "end_marker", "warping", "warp_mode", "gain", "slicing_style", "slicing_beat_division",
    "slicing_region_count", "slicing_sensitivity", "beats_granulation_resolution", "beats_transient_envelope",
    "beats_transient_loop_mode", "complex_pro_envelope", "complex_pro_formants", "texture_flux",
    "texture_grain_size", "tones_grain_size",
)
_OPTION_LIMIT = 64
_MACRO = re.compile(r"^Macro (\d+)$")
_BASE_MEMBERS = []


def _base_device_members():
    if not _BASE_MEMBERS:
        import Live
        _BASE_MEMBERS.append(frozenset(dir(Live.Device.Device)))
    return _BASE_MEMBERS[0]


def _class_name(obj):
    return type(obj).__name__


_PROPERTIES_BY_CLASS = {}


def _class_properties(obj):
    """{name: property} of obj's class, inherited properties included (cached per class)."""
    cls = type(obj)
    found = _PROPERTIES_BY_CLASS.get(cls)
    if found is None:
        found = {}
        for name in dir(cls):
            if name.startswith("_"):
                continue
            attribute = getattr(cls, name, None)
            if isinstance(attribute, property):
                found[name] = attribute
        _PROPERTIES_BY_CLASS[cls] = found
    return found


def companion_name(name, available):
    """The option list that names the values of property `name` ("voice_mode_index" -> "voice_mode_list")."""
    candidates = [_COMPANIONS.get(name)]
    if name.endswith("_index"):
        candidates.append(name[:-len("_index")] + "_list")
    candidates.append(name + "_list")
    candidates.append("available_" + name + "s")
    for candidate in candidates:
        if candidate and candidate != name and candidate in available:
            return candidate
    return None


def _routing_name(item):
    name = getattr(item, "display_name", None)
    return str(name) if name is not None else str(item)


def _enum_class(owner, name, value):
    if isinstance(value, int) and hasattr(type(value), "values") and hasattr(value, "name"):
        return type(value)
    spec = _ENUM_PROPERTIES.get((_class_name(owner), name))
    if spec is None:
        return None
    import Live
    return getattr(getattr(Live, spec[0], None), spec[1], None)


def _enum_options(owner, name, value):
    """[(number, name)] when the property holds one of Live's enums (or documented codes), else None."""
    enum = None if isinstance(value, bool) else _enum_class(owner, name, value)
    if enum is not None and hasattr(enum, "values"):
        return sorted((int(number), str(item.name)) for number, item in enum.values.items() if str(item.name) != "count")
    static = _STATIC_OPTIONS.get((_class_name(owner), name))
    if static:
        return list(enumerate(static))
    return None


def _limit(options, detail):
    return options if detail or len(options) <= _OPTION_LIMIT else options[:_OPTION_LIMIT]


def property_out(owner, name, descriptor, available, detail=False):
    """{"value", "item"?, "options"?, "option_count"?, "read_only"?} for one type-specific property."""
    value = getattr(owner, name)
    entry = {}
    options = None
    companion = companion_name(name, available)
    if companion and companion.startswith("available_"):
        options = [_routing_name(option) for option in getattr(owner, companion)]
        entry["value"] = _routing_name(value)
    elif companion:
        options = [str(option) for option in getattr(owner, companion)]
        entry["value"] = units.jsonable(value)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(options):
            entry["item"] = options[value]
    else:
        enum = _enum_options(owner, name, value) if isinstance(value, int) else None
        if enum:
            entry["value"] = value if isinstance(value, bool) else int(value)
            entry["item"] = dict(enum).get(int(value))
            options = [label for _, label in enum]
        else:
            entry["value"] = _json_number(units.jsonable(value))
    if options is not None:
        entry["options"] = _limit(options, detail)
        if len(entry["options"]) < len(options):
            entry["option_count"] = len(options)
    if descriptor.fset is None:
        entry["read_only"] = True
    return entry


def _json_number(value):
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return str(value)
        return round(value, 6)
    return value


def specific_property_names(device):
    """Names of the properties device's class defines beyond the base Device (option lists folded in)."""
    available = _class_properties(device)
    base = _base_device_members()
    companions = set(filter(None, (companion_name(name, available) for name in available)))
    return available, [
        name for name in sorted(available)
        if name not in base and name not in _OBJECT_MEMBERS and name not in companions and name not in _RACK_SECTION
    ]


def properties_out(owner, names, available, detail=False):
    out = {}
    for name in names:
        try:
            out[name] = property_out(owner, name, available[name], available, detail)
        except Exception:
            continue  # Properties that do not apply in the current state raise (e.g. Simpler without a sample).
    return out


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------


def _norm(text):
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def match_option(options, value, what):
    """Index of `value` in options: an index (int), or a name (str) matched exactly, case- and
    punctuation-insensitively, then as a unique partial name. An int that is not a valid index but
    names an option ("12" voices) selects that option."""
    if isinstance(value, bool):
        raise CommandError("invalid_argument", "{0} expects an option name or index, got {1!r}".format(what, value))
    if isinstance(value, (int, float)) and float(value).is_integer():
        index = int(value)
        if 0 <= index < len(options):
            return index
        named = [position for position, option in enumerate(options) if _norm(option) == str(index)]
        if len(named) == 1:
            return named[0]
        raise CommandError("invalid_argument", "{0} index {1} is out of range (0..{2}). Options: {3}".format(what, index, len(options) - 1, ", ".join(options[:_OPTION_LIMIT])))
    text = str(value).strip()
    for test in (lambda option: option.lower() == text.lower(), lambda option: _norm(option) == _norm(text)):
        hits = [index for index, option in enumerate(options) if test(option)]
        if hits:
            return hits[0]
    if re.match(r"^\d+$", text):
        return match_option(options, int(text), what)
    partial = [index for index, option in enumerate(options) if _norm(text) and _norm(text) in _norm(option)]
    if len(partial) == 1:
        return partial[0]
    prefixed = [index for index, option in enumerate(options) if _norm(option).startswith(_norm(text))]
    if len(prefixed) == 1:
        return prefixed[0]
    raise not_found(what, value, options)


def parse_bool(value, what="value"):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ("on", "true", "yes", "1", "enabled"):
        return True
    if isinstance(value, str) and value.strip().lower() in ("off", "false", "no", "0", "disabled"):
        return False
    raise CommandError("invalid_argument", "{0} must be true or false, got {1!r}".format(what, value))


def _number(value, what):
    if isinstance(value, bool):
        raise CommandError("invalid_argument", "{0} must be a number, got {1!r}".format(what, value))
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).strip())
    except ValueError:
        raise CommandError("invalid_argument", "{0} must be a number, got {1!r}".format(what, value))


def set_property(owner, key, value):
    """Set a writable property by name, parsing option names, routing names and enum names.

    Returns (property name, new value description).
    """
    available = _class_properties(owner)
    name = key
    if name not in available and name + "_index" in available:
        name = name + "_index"
    descriptor = available.get(name)
    if descriptor is None or name in _OBJECT_MEMBERS:
        writable = sorted(item for item, prop in available.items() if prop.fset is not None and item not in _OBJECT_MEMBERS)
        raise not_found("Property of {0}".format(_label(owner)), key, writable)
    if descriptor.fset is None:
        raise CommandError("unsupported", "Property '{0}' of {1} is read-only".format(name, _label(owner)))
    current = getattr(owner, name)
    companion = companion_name(name, available)
    what = "{0} of {1}".format(name, _label(owner))
    if companion and companion.startswith("available_"):
        options = list(getattr(owner, companion))
        setattr(owner, name, options[match_option([_routing_name(option) for option in options], value, what)])
    elif companion:
        setattr(owner, name, match_option([str(option) for option in getattr(owner, companion)], value, what))
    else:
        enum = _enum_options(owner, name, current) if isinstance(current, int) else None
        if enum:
            if isinstance(value, bool) and isinstance(current, bool):
                number = int(value)
            elif isinstance(value, int) and not isinstance(value, bool) and value in dict(enum):
                number = int(value)
            else:
                number = enum[match_option([label for _, label in enum], value, what)][0]
            enum_class = _enum_class(owner, name, current)
            if isinstance(current, bool):
                setattr(owner, name, bool(number))
            elif enum_class is not None and hasattr(enum_class, "values"):
                setattr(owner, name, enum_class.values[number])
            else:
                setattr(owner, name, number)
        elif isinstance(current, bool):
            setattr(owner, name, parse_bool(value, what))
        elif isinstance(current, int):
            setattr(owner, name, int(_number(value, what)))
        elif isinstance(current, float):
            setattr(owner, name, float(_number(value, what)))
        else:
            setattr(owner, name, value)
    return name, property_out(owner, name, descriptor, available)


def _label(owner):
    try:
        return "'{0}'".format(owner.name)
    except Exception:
        return _class_name(owner)


# ---------------------------------------------------------------------------
# Device, chain and rack descriptions
# ---------------------------------------------------------------------------


def device_type(device):
    try:
        return units.DEVICE_TYPE.name(device.type)
    except Exception:
        return "undefined"


def on_parameter(device):
    """The "Device On" parameter: index 0 for every device Live makes (Meld names it "Device On" but
    its original name is "On")."""
    parameters = list(device.parameters)
    for parameter in parameters[:1] + parameters:
        if parameter.name == "Device On" or parameter.original_name == "Device On":
            return parameter
    return None


def summary(device, index=None, path=None):
    """Compact description of a device: index, path, name, class, type and on/off."""
    location = path or refs.device_path(device)
    out = {
        "index": index,
        "path": location["path"],
        "name_path": location["name_path"],
        "name": device.name,
        "class": device.class_display_name,
        "class_name": device.class_name,
        "type": device_type(device),
    }
    switch = on_parameter(device)
    if switch is not None:
        out["enabled"] = switch.value >= 0.5
    try:
        if not device.is_active and out.get("enabled", True):
            out["active"] = False
    except Exception:
        pass
    return out


def _db(parameter):
    """Volume in dB from the parameter's display ("-inf" when silent)."""
    value = units.parse_display_number(parameter.str_for_value(parameter.value))
    if value is None:
        value = units.volume_db(parameter)
    if value is None:
        return None
    if math.isinf(value):
        return "-inf"
    return round(value, 2)


def note_name(note):
    return "all" if note is None or note < 0 else units.pitch_name(note)


def chain_out(chain, index, mixer=False):
    out = {"index": index, "name": chain.name, "mute": bool(chain.mute), "solo": bool(chain.solo)}
    in_note = getattr(chain, "in_note", None) if _class_name(chain) == "DrumChain" else None
    if in_note is not None:
        out["in_note"] = in_note
        out["note_name"] = note_name(in_note)
    if mixer:
        if in_note is not None:
            out["out_note"] = chain.out_note
            out["choke_group"] = chain.choke_group
        try:
            mixer_device = chain.mixer_device
            out["volume_db"] = _db(mixer_device.volume)
            out["pan"] = round(float(mixer_device.panning.value), 3)
        except Exception:
            pass
        out.update(units.color_out(chain))
    return out


def macros_out(rack, include_hidden=False):
    try:
        mapped = list(rack.macros_mapped)
        visible = rack.visible_macro_count
    except Exception:
        return []
    out = []
    for index, parameter in enumerate(rack.parameters):
        match = _MACRO.match(parameter.original_name)
        if not match:
            continue
        number = int(match.group(1))
        if number > visible and not include_hidden:
            continue
        out.append({
            "index": index, "macro": number, "name": parameter.name, "value": round(float(parameter.value), 4),
            "display": parameter.str_for_value(parameter.value), "mapped": bool(mapped[number - 1]) if number <= len(mapped) else False,
        })
    return out


def pads_out(rack):
    """Non-empty drum pads: note, note name, pad name and chain names."""
    pads = []
    try:
        drum_pads = list(rack.drum_pads)
    except Exception:
        drum_pads = []
    if drum_pads:
        for pad in drum_pads:
            chains = list(pad.chains)
            if not chains:
                continue
            entry = {"note": pad.note, "note_name": note_name(pad.note), "name": pad.name, "chains": [chain.name for chain in chains]}
            if pad.mute:
                entry["mute"] = True
            if pad.solo:
                entry["solo"] = True
            pads.append(entry)
        return pads
    by_note = {}
    for chain in rack.chains:  # Nested drum racks have no pads of their own; group chains by note.
        by_note.setdefault(getattr(chain, "in_note", -1), []).append(chain.name)
    for note in sorted(by_note):
        names = by_note[note]
        pads.append({"note": note, "note_name": note_name(note), "name": names[0], "chains": names})
    return pads


def _join(path, names):
    return {"path": "/".join(str(item) for item in path), "name_path": "/".join(names)}


def device_tree(device, index, path=(), names=()):
    """Device summary plus, for racks, chains (recursively), pads, macros and variations."""
    path = list(path) + [index]
    names = list(names) + [device.name]
    node = summary(device, index, _join(path, names))
    if device.can_have_chains:
        chains = []
        for chain_index, chain in enumerate(rack_chains(device)):
            entry = chain_out(chain, chain_index)
            entry["devices"] = [
                device_tree(inner, inner_index, path + [chain_index], names + [chain.name])
                for inner_index, inner in enumerate(chain.devices)
            ]
            chains.append(entry)
        node["chains"] = chains
        returns = list(device.return_chains)
        if returns:
            node["return_chains"] = [
                dict(chain_out(chain, chain_index), devices=[inner.name for inner in chain.devices])
                for chain_index, chain in enumerate(returns)
            ]
        if device.can_have_drum_pads:
            node["pads"] = pads_out(device)
        node["macros"] = macros_out(device)
        node["variation_count"] = device.variation_count
    return node


def rack_chains(rack):
    return list(rack.chains)


def rack_out(rack, detail=False):
    """Rack section of get_device: chains with mixer, return chains, pads, macros, variations, selector."""
    out = {"chains": []}
    for index, chain in enumerate(rack.chains):
        entry = chain_out(chain, index, mixer=True)
        entry["devices"] = [{"index": position, "name": inner.name, "class": inner.class_display_name} for position, inner in enumerate(chain.devices)]
        out["chains"].append(entry)
    returns = list(rack.return_chains)
    if returns:
        out["return_chains"] = [
            dict(chain_out(chain, index, mixer=True), devices=[inner.name for inner in chain.devices])
            for index, chain in enumerate(returns)
        ]
    if rack.can_have_drum_pads:
        out["pads"] = pads_out(rack)
        try:
            selected = rack.view.selected_drum_pad
            if selected is not None:
                out["selected_pad"] = {"note": selected.note, "note_name": note_name(selected.note), "name": selected.name}
        except Exception:
            pass
    else:
        try:
            out["chain_selector"] = units.parameter_out(rack.chain_selector)
        except Exception:
            pass
    out["macros"] = macros_out(rack, include_hidden=detail)
    out["visible_macro_count"] = rack.visible_macro_count
    out["variations"] = {"count": rack.variation_count, "selected": rack.selected_variation_index}
    return out


def sample_out(simpler, detail=False):
    sample = simpler.sample
    if sample is None:
        return None
    out = {"file_path": sample.file_path}
    try:
        rate = sample.sample_rate
        out["length"] = sample.length
        out["sample_rate"] = rate
        out["duration_s"] = round(sample.length / float(rate), 4) if rate else None
    except Exception:
        pass
    available = _class_properties(sample)
    names = _SAMPLE_PROPERTIES if detail else ("start_marker", "end_marker", "warping", "warp_mode", "gain", "slicing_style", "slicing_beat_division", "slicing_region_count", "slicing_sensitivity")
    for name in names:
        if name in available:
            try:
                entry = property_out(sample, name, available[name], available, detail)
            except Exception:
                continue
            out[name] = entry["value"] if "item" not in entry else entry["item"]
    try:
        out["gain_display"] = sample.gain_display_string()
    except Exception:
        pass
    try:
        slices = [int(item) for item in sample.slices]
        out["slice_count"] = len(slices)
        out["slices"] = slices if detail or len(slices) <= _OPTION_LIMIT else slices[:_OPTION_LIMIT]
    except Exception:
        pass
    if detail:
        try:
            out["warp_markers"] = [{"sample_time": round(marker.sample_time, 6), "beat_time": round(marker.beat_time, 6)} for marker in sample.warp_markers]
        except Exception:
            pass
        view = simpler.view
        for name in ("selected_slice", "sample_start", "sample_end", "sample_loop_start", "sample_loop_end"):
            try:
                out["view_" + name] = getattr(view, name)
            except Exception:
                pass
    return out


def device_out(song, device, index, detail=False, parameters=True):
    """Full get_device description."""
    owner = owning_track(device)
    out = summary(device, index)
    if owner is not None:
        out["track"] = refs.track_label(song, owner)
    out["collapsed"] = bool(device.view.is_collapsed)
    if device.can_compare_ab:
        out["compare_b"] = bool(device.is_using_compare_preset_b)
    available, names = specific_property_names(device)
    props = properties_out(device, names, available, detail)
    if props:
        out["properties"] = props
    if device.can_have_chains:
        out.update(rack_out(device, detail))
    if _class_name(device) == "SimplerDevice":
        out["sample"] = sample_out(device, detail)
    if parameters:
        out["parameters"] = [units.parameter_out(parameter, position, detail) for position, parameter in enumerate(device.parameters)]
    else:
        out["parameter_count"] = len(device.parameters)
    return out


def owning_track(obj):
    node = obj
    for _ in range(32):
        if node is None:
            return None
        if hasattr(node, "clip_slots"):
            return node
        node = node.canonical_parent
    return None


def brief_list(container):
    return [{"index": index, "name": item.name, "class": item.class_display_name} for index, item in enumerate(container.devices)]


# ---------------------------------------------------------------------------
# Chain resolution
# ---------------------------------------------------------------------------


def segments(ref):
    if isinstance(ref, (list, tuple)):
        return list(ref)
    if isinstance(ref, str) and "/" in ref:
        return [segment.strip() for segment in ref.split("/")]
    return [ref]


def drum_note(text):
    """MIDI note for a drum-note chain reference ('C1', 'note:36'), else None."""
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if stripped.lower().startswith("note:"):
        return units.parse_pitch(stripped[5:], "drum note")
    if units._NOTE.match(stripped):
        return units.parse_pitch(stripped, "drum note")
    return None


def chain_or_return(rack, ref):
    """A rack chain by index, name or drum note; 'return:<index|name>' selects a return chain."""
    if isinstance(ref, str) and ref.strip().lower().startswith("return:"):
        text = ref.strip()[len("return:"):].strip()
        returns = list(rack.return_chains)
        if re.match(r"^\d+$", text):
            position = int(text)
            if position < len(returns):
                return returns[position]
        elif len(text) == 1 and text.isalpha() and ord(text.upper()) - ord("A") < len(returns):
            return returns[ord(text.upper()) - ord("A")]
        else:
            for item in returns:
                if item.name.strip().lower() == text.lower():
                    return item
        raise not_found("Return chain", ref, ["return:{0} {1}".format(index, item.name) for index, item in enumerate(returns)])
    return refs.chain(rack, ref)


# ---------------------------------------------------------------------------
# Commands: reading
# ---------------------------------------------------------------------------


@command("get_devices", readonly=True)
def get_devices(ctx, track):
    """Device tree of a track: racks with chains (recursively), drum pads, macros and variations."""
    song = ctx.song
    owner = refs.track(song, track)
    return {
        "track": refs.track_label(song, owner),
        "devices": [device_tree(device, index) for index, device in enumerate(owner.devices)],
    }


@command("get_device", readonly=True)
def get_device(ctx, track, device, parameters=True, detail=False):
    """One device: parameters, type-specific properties, rack chains/pads/macros, Simpler sample."""
    target, _, index = refs.device(ctx.song, track, device)
    return device_out(ctx.song, target, index, detail=bool(detail), parameters=bool(parameters))


# ---------------------------------------------------------------------------
# Commands: adding, editing and arranging devices
# ---------------------------------------------------------------------------

_KIND_LABEL = {"instruments": "an instrument", "midi_effects": "a MIDI effect", "audio_effects": "an audio effect"}
# Browser devices that insert_device rejects because they are Max for Live devices (probed on Live 12.4.6);
# failures found at runtime are added. They load through the browser instead.
NOT_INSERTABLE = set((
    "Align Delay", "Envelope Follower", "LFO", "Shaper", "Envelope MIDI", "Expression Control", "MIDI Monitor",
    "MPE Control", "Note Echo", "Shaper MIDI", "DS Clang", "DS Clap", "DS Cymbal", "DS FM", "DS HH", "DS Kick",
    "DS Snare", "DS Tom",
))


def native_category(app, exact):
    for category, names in refs.native_device_names(app).items():
        if exact in names:
            return category
    return None


def _position(value, what="position"):
    if value is None:
        return -1
    if isinstance(value, bool) or not isinstance(value, (int, float, str)) or not re.match(r"^\s*-?\d+\s*$", str(value)):
        raise CommandError("invalid_argument", "{0} must be a device index (-1 = end), got {1!r}".format(what, value))
    return int(str(value).strip())


def chain_in_rack(rack, ref, create):
    """(chain, created): a chain of `rack`. With create, 'new' inserts a chain and a drum note that
    has no chain yet gets a new chain on that pad."""
    if create:
        if isinstance(ref, str) and ref.strip().lower() in ("new", "+"):
            return rack.insert_chain(), True
        note = drum_note(ref) if rack.can_have_drum_pads else None
        if note is not None and not any(getattr(item, "in_note", None) == note for item in rack.chains):
            created = rack.insert_chain()
            created.in_note = note
            return created, True
    return chain_or_return(rack, ref), False


def _drop_created_chain(rack, chain):
    """Remove a chain this call created on a Drum Rack pad (other racks have no API to delete chains)."""
    try:
        if rack.can_have_drum_pads:
            for pad in rack.drum_pads:
                if pad.note == chain.in_note and len(pad.chains) == 1:
                    pad.delete_all_chains()
                    return True
    except Exception:
        pass
    return False


def rack_for_chain_path(song, track_ref, chain_ref):
    """(rack, last segment) for a chain path such as 'Instrument Rack/0' or [0, 'C1']."""
    parts = segments(chain_ref)
    if len(parts) < 2 or len(parts) % 2:
        raise CommandError(
            "invalid_argument",
            "chain {0!r} must be a path that alternates device and chain segments and ends with a chain, "
            "e.g. 'Instrument Rack/0', 'Drum Rack/C1', 'Audio Effect Rack/new' or [0, 1]".format(chain_ref),
        )
    rack, _, _ = refs.device(song, track_ref, parts[:-1])
    if not rack.can_have_chains:
        raise CommandError("invalid_argument", "Device '{0}' is not a rack, so it has no chains".format(rack.name))
    return rack, parts[-1]


@command("add_device")
def add_device(ctx, track, name, position=-1, chain=None):
    """Insert a native Live device by name on a track or into a rack chain."""
    song = ctx.song
    owner = refs.track(song, track)
    exact = refs.native_device_name(ctx.app, name)
    category = native_category(ctx.app, exact)
    index = _position(position)
    rack = None
    if chain is None:
        accepts_midi = bool(owner.has_midi_input)
        where = "{0} track '{1}'".format(refs.track_kind(song, owner), owner.name)
    else:
        rack, last = rack_for_chain_path(song, track, chain)
        accepts_midi = rack.type != 2  # Audio Effect Rack chains are audio; the other racks' chains take MIDI.
        where = "a chain of '{0}'".format(rack.name)
    if category in ("instruments", "midi_effects") and not accepts_midi:
        raise CommandError(
            "unsupported",
            "Cannot add '{0}' to {1}: '{0}' is {2}, and instruments and MIDI effects only go on MIDI tracks "
            "(or in Instrument, Drum and MIDI Effect Rack chains). Only audio effects go on audio, return and "
            "master tracks.".format(exact, where, _KIND_LABEL[category]),
            hint="Use a MIDI track (create_track(kind='midi')), or choose an audio effect.",
        )
    if rack is not None and exact in NOT_INSERTABLE:
        raise CommandError(
            "unsupported",
            "'{0}' cannot be inserted into a rack chain by name: it is a Max for Live device, not a native one".format(exact),
            hint="Load it onto the track with load_from_browser(track, query='{0}'), then move_device it into the chain.".format(exact),
        )
    created = False
    if rack is None:
        if exact in NOT_INSERTABLE:
            return _add_through_browser(ctx, owner, category, exact, index)
        container = owner
    else:
        container, created = chain_in_rack(rack, last, create=True)
        if created and index > 0:
            index = -1  # A new chain is empty: the only position is the start.
    inserted, error = _insert(container, exact, index)
    if inserted is None and "not found" in error.lower() and " " in exact:
        inserted, _ = _insert(container, exact.replace(" ", ""), index)  # "Drum Sampler" inserts as "DrumSampler".
    if inserted is None and "not found" in error.lower():
        NOT_INSERTABLE.add(exact)
        if rack is None:
            return _add_through_browser(ctx, owner, category, exact, index)
    if inserted is None:
        dropped = created and _drop_created_chain(rack, container)
        message = "Cannot insert '{0}' into {1}: {2}".format(exact, where, error)
        if created and not dropped:
            message += " (the new empty chain remains; undo removes it)"
        raise CommandError("invalid_argument" if "not found" not in error.lower() else "unsupported", message)
    position_now = refs.index_of(container.devices, inserted)
    out = {"device": summary(inserted, position_now), "devices": brief_list(container)}
    if rack is not None:
        out["chain"] = chain_out(container, refs.index_of(rack.chains, container))
    return out


def _insert(container, name, index):
    """(device, "") on success, (None, Live's error message) on failure."""
    try:
        return (container.insert_device(name) if index == -1 else container.insert_device(name, index)), ""
    except Exception as error:
        return None, str(error) or error.__class__.__name__


def _add_through_browser(ctx, owner, category, exact, index):
    """Max for Live devices listed among Live's devices (LFO, DS Kick, ...) load through the browser."""
    from . import browser as browser_handlers
    item = None
    if category is not None:
        item = next((child for child in getattr(ctx.app.browser, category).children if child.name == exact), None)
    if item is None or not item.is_loadable:
        raise CommandError("not_found", "'{0}' cannot be inserted and was not found in the browser".format(exact), hint="Use search_browser and load_from_browser.")
    added, _, _ = browser_handlers.load_item_on_track(ctx, owner, item, None if index == -1 else index)
    if not added:
        raise CommandError("live_error", "Loading '{0}' from the browser added no device to '{1}'".format(exact, owner.name))
    position, device = added[0]
    return {"device": summary(device, position), "devices": brief_list(owner), "loaded_via": "browser (Max for Live device)"}


@command("delete_device")
def delete_device(ctx, track, device):
    """Delete a device (or a whole rack) from its track or chain."""
    target, container, index = refs.device(ctx.song, track, device)
    deleted = summary(target, index)
    container.delete_device(index)
    return {"deleted": {key: deleted[key] for key in ("index", "path", "name_path", "name", "class")}, "devices": brief_list(container)}


@command("duplicate_device")
def duplicate_device(ctx, track, device):
    """Duplicate a device right after itself in its track or chain."""
    target, container, index = refs.device(ctx.song, track, device)
    try:
        container.duplicate_device(index)
    except Exception as error:
        message = str(error)
        if "instrument" in message.lower():
            raise CommandError(
                "unsupported",
                "Cannot duplicate '{0}': a track or chain holds one instrument ({1})".format(target.name, message),
                hint="Duplicate the track, or put the instrument in an Instrument Rack and add another chain.",
            )
        raise CommandError("live_error", "Cannot duplicate '{0}': {1}".format(target.name, message))
    copy = list(container.devices)[index + 1]
    return {"device": summary(copy, index + 1), "devices": brief_list(container)}


@command("move_device")
def move_device(ctx, track, device, to_track=None, to_position=None, to_chain=None):
    """Move a device within its chain, to another track, or into a rack chain (Song.move_device)."""
    song = ctx.song
    target, container, index = refs.device(song, track, device)
    destination_track = track if to_track is None else to_track
    if to_chain is not None:
        rack, last = rack_for_chain_path(song, destination_track, to_chain)
        if refs.same(rack, target):
            raise CommandError("invalid_argument", "Cannot move rack '{0}' into its own chain".format(target.name))
        destination, _ = chain_in_rack(rack, last, create=True)
    else:
        destination = refs.track(song, destination_track)
    if target.type in (1, 4) and not getattr(destination, "has_midi_input", True):
        raise CommandError(
            "unsupported",
            "Cannot move '{0}' ({1}) onto {2}: instruments and MIDI effects only go on MIDI tracks or in MIDI "
            "rack chains".format(target.name, device_type(target).replace("_", " "), _label(destination)),
        )
    count = len(destination.devices)
    position = _position(to_position, "to_position")
    if position == -1:
        position = count
    if not 0 <= position <= count:
        raise CommandError("invalid_argument", "to_position {0} is out of range (0..{1}; -1 = end)".format(position, count))
    try:
        placed = song.move_device(target, destination, position)
    except Exception as error:
        raise CommandError("invalid_argument", "Cannot move '{0}' there: {1}".format(target.name, error))
    devices = list(destination.devices)
    moved = devices[placed] if 0 <= placed < len(devices) else target
    out = {"device": summary(moved, placed), "devices": brief_list(destination)}
    if placed != position and not (refs.same(destination, container) and placed == position - 1):
        out["note"] = "Live placed the device at index {0}, the closest valid position to {1}".format(placed, position)
    if not refs.same(destination, container):
        out["source_devices"] = brief_list(container)
    return out


@command("set_chain")
def set_chain(ctx, track, device, chain, name=None, color=None, mute=None, solo=None, volume_db=None, pan=None,
              in_note=None, out_note=None, choke_group=None):
    """Rack or drum chain: name, colour, mute, solo, volume (dB), pan, and drum in/out note and choke group."""
    rack, _, _ = refs.device(ctx.song, track, device)
    if not rack.can_have_chains:
        raise CommandError("invalid_argument", "Device '{0}' is not a rack, so it has no chains".format(rack.name))
    target = chain_or_return(rack, chain)
    is_drum = _class_name(target) == "DrumChain"
    if not is_drum and any(item is not None for item in (in_note, out_note, choke_group)):
        raise CommandError("unsupported", "in_note, out_note and choke_group apply only to Drum Rack chains; '{0}' is not one".format(target.name))
    note_in = None
    if in_note is not None:
        if str(in_note).strip().lower() in ("all", "-1", "all notes"):
            raise CommandError("unsupported", "Live 12.4 does not accept 'All Notes' as in_note through its API; pass a note 0..127 such as 'C1'")
        note_in = units.parse_pitch(in_note, "in_note")
    note_out = None if out_note is None else units.parse_pitch(out_note, "out_note")
    choke = None
    if choke_group is not None:
        choke = 0 if str(choke_group).strip().lower() in ("none", "off") else int(_number(choke_group, "choke_group"))
        if not 0 <= choke <= 16:
            raise CommandError("invalid_argument", "choke_group must be 0 (none) .. 16, got {0!r}".format(choke_group))
    pan_value = None if pan is None else units.parse_pan(pan)
    if note_in is not None:  # Drum settings first: Live validates notes itself, so fail before other changes.
        target.in_note = note_in
    if note_out is not None:
        target.out_note = note_out
    if choke is not None:
        target.choke_group = choke
    if name is not None:
        target.name = str(name)
    if color is not None:
        units.apply_color(target, color)
    if mute is not None:
        target.mute = parse_bool(mute, "mute")
    if solo is not None:
        target.solo = parse_bool(solo, "solo")
    if volume_db is not None:
        units.set_volume_db(target.mixer_device.volume, volume_db)
    if pan_value is not None:
        target.mixer_device.panning.value = pan_value
    position = refs.index_of(rack.chains, target)
    out = chain_out(target, position if position is not None else refs.index_of(rack.return_chains, target), mixer=True)
    if position is None:
        out["return_chain"] = True
    out["rack"] = summary(rack)["path"]
    return out


# ---------------------------------------------------------------------------
# Parameters and properties
# ---------------------------------------------------------------------------


@command("set_device_parameters")
def set_device_parameters(ctx, track, device, values):
    """Set several parameters by name or index: numbers are raw, strings are display values or items."""
    if not isinstance(values, dict) or not values:
        raise CommandError("invalid_argument", "values must be a non-empty object such as {\"Frequency\": \"800 Hz\", \"Dry/Wet\": 0.5}")
    target, _, index = refs.device(ctx.song, track, device)
    parameters = list(target.parameters)
    results, errors = [], []
    for key, value in values.items():
        try:
            parameter = refs.parameter(target, key)
            entry = units.set_parameter(parameter, value)
            position = refs.index_of(parameters, parameter)
            results.append(dict({"index": position}, **entry))
        except CommandError as error:
            errors.append({"parameter": key, "code": error.code, "error": error.message})
        except Exception as error:
            errors.append({"parameter": key, "code": "live_error", "error": str(error) or error.__class__.__name__})
    if not results:
        first = errors[0]
        raise CommandError(first["code"], "No parameter was set. " + "; ".join("{0}: {1}".format(item["parameter"], item["error"]) for item in errors))
    out = {"device": summary(target, index), "parameters": results}
    if errors:
        out["errors"] = errors
    return out


def _flatten_properties(properties, prefix=""):
    flat = []
    for key, value in properties.items():
        if isinstance(value, dict) and key in ("sample", "view"):
            flat.extend(_flatten_properties(value, prefix + key + "."))
        else:
            flat.append((prefix + str(key), value))
    return flat


def _property_owner(device, key):
    """(object, property) for 'name', 'sample.name' (Simpler's sample) or 'view.name' (device view)."""
    if "." not in key:
        return device, key
    head, rest = key.split(".", 1)
    if head == "sample":
        if _class_name(device) != "SimplerDevice":
            raise CommandError("unsupported", "'{0}': only Simpler has a sample".format(key))
        if device.sample is None:
            raise CommandError("unsupported", "Simpler '{0}' has no sample loaded".format(device.name), hint="Load one with load_from_browser or device_action('replace_sample').")
        return device.sample, rest
    if head == "view":
        return device.view, rest
    raise CommandError("invalid_argument", "Property '{0}': prefixes are 'sample.' and 'view.'".format(key))


@command("set_device")
def set_device(ctx, track, device, enabled=None, name=None, collapsed=None, compare_b=None, properties=None):
    """On/off, name, collapsed, A/B compare and type-specific properties of a device."""
    target, _, index = refs.device(ctx.song, track, device)
    switch = None
    if enabled is not None:
        switch = on_parameter(target)
        if switch is None:
            raise CommandError("unsupported", "Device '{0}' has no 'Device On' parameter".format(target.name))
    if compare_b is not None and not target.can_compare_ab:
        raise CommandError("unsupported", "Device '{0}' does not support A/B compare".format(target.name))
    if properties is not None and not isinstance(properties, dict):
        raise CommandError("invalid_argument", "properties must be an object such as {\"playback_mode\": \"one_shot\"}")
    if compare_b is not None:  # First: switching the A/B slot swaps the device's whole state.
        target.is_using_compare_preset_b = parse_bool(compare_b, "compare_b")
    if switch is not None:
        switch.value = switch.max if parse_bool(enabled, "enabled") else switch.min
    if name is not None:
        target.name = str(name)
    if collapsed is not None:
        target.view.is_collapsed = parse_bool(collapsed, "collapsed")
    changed, errors = {}, []
    for key, value in _flatten_properties(properties or {}):
        try:
            owner, prop = _property_owner(target, key)
            resolved, entry = set_property(owner, prop, value)
            entry.pop("options", None)
            entry.pop("option_count", None)
            changed[key if resolved == prop else key[:len(key) - len(prop)] + resolved] = entry
        except CommandError as error:
            errors.append({"property": key, "code": error.code, "error": error.message})
        except Exception as error:
            errors.append({"property": key, "code": "live_error", "error": str(error) or error.__class__.__name__})
    if errors and not changed and all(item is None for item in (enabled, name, collapsed, compare_b)):
        raise CommandError(errors[0]["code"], "No property was set. " + "; ".join("{0}: {1}".format(item["property"], item["error"]) for item in errors))
    out = summary(target, index)
    out["collapsed"] = bool(target.view.is_collapsed)
    if target.can_compare_ab:
        out["compare_b"] = bool(target.is_using_compare_preset_b)
    if changed:
        out["properties"] = changed
    if errors:
        out["errors"] = errors
    return out


# ---------------------------------------------------------------------------
# Device actions (whitelisted per device class)
# ---------------------------------------------------------------------------

ACTIONS = {}

_KINDS = {
    "rack": ("racks", lambda device: bool(device.can_have_chains)),
    "drum_rack": ("Drum Racks", lambda device: bool(device.can_have_drum_pads)),
    "simpler": ("Simpler", lambda device: _class_name(device) == "SimplerDevice"),
    "looper": ("Looper", lambda device: _class_name(device) == "LooperDevice"),
    "wavetable": ("Wavetable", lambda device: _class_name(device) == "WavetableDevice"),
    "plugin": ("plug-ins", lambda device: _class_name(device) == "PluginDevice"),
    "compare_ab": ("devices with A/B compare", lambda device: bool(device.can_compare_ab)),
}


def _action(name, kind):
    def register(func):
        ACTIONS[name] = (kind, func)
        return func
    return register


def available_actions(device):
    return sorted(name for name, (kind, _) in ACTIONS.items() if _KINDS[kind][1](device))


def _int_arg(value, what):
    number = _number(value, what)
    if float(number) != int(number):
        raise CommandError("invalid_argument", "{0} must be a whole number, got {1!r}".format(what, value))
    return int(number)


# -- racks -------------------------------------------------------------------


@_action("insert_chain", "rack")
def _insert_chain(ctx, device, index=None, name=None, note=None):
    pitch = None
    if note is not None:
        if not device.can_have_drum_pads:
            raise CommandError("invalid_argument", "note applies only to Drum Rack chains")
        pitch = units.parse_pitch(note, "note")
    chain = device.insert_chain() if index is None else device.insert_chain(_int_arg(index, "index"))
    if name is not None:
        chain.name = str(name)
    if pitch is not None:
        chain.in_note = pitch
    return {"chain": chain_out(chain, refs.index_of(device.chains, chain), mixer=True)}


@_action("add_macro", "rack")
def _add_macro(ctx, device):
    device.add_macro()
    return {"visible_macro_count": device.visible_macro_count}


@_action("remove_macro", "rack")
def _remove_macro(ctx, device):
    device.remove_macro()
    return {"visible_macro_count": device.visible_macro_count}


@_action("randomize_macros", "rack")
def _randomize_macros(ctx, device):
    device.randomize_macros()
    return {"macros": macros_out(device)}


def _variations(device):
    return {"count": device.variation_count, "selected": device.selected_variation_index}


def _select_variation(device, index):
    if index is None:
        return
    count = device.variation_count
    position = _int_arg(index, "index")
    if not 0 <= position < count:
        raise CommandError(
            "not_found",
            "Variation {0} does not exist: '{1}' has {2} stored variation(s){3}".format(
                position, device.name, count, " (0..{0})".format(count - 1) if count else ""),
            hint="Store one with device_action(action='store_variation')." if not count else None,
        )
    device.selected_variation_index = position


@_action("store_variation", "rack")
def _store_variation(ctx, device):
    device.store_variation()
    return {"variations": _variations(device)}


@_action("recall_variation", "rack")
def _recall_variation(ctx, device, index=None):
    if not device.variation_count:
        raise CommandError("not_found", "'{0}' has no stored variations".format(device.name), hint="Store one with device_action(action='store_variation').")
    _select_variation(device, index)
    device.recall_selected_variation()
    return {"variations": _variations(device), "macros": macros_out(device)}


@_action("recall_last_variation", "rack")
def _recall_last_variation(ctx, device):
    device.recall_last_used_variation()
    return {"variations": _variations(device), "macros": macros_out(device)}


@_action("delete_variation", "rack")
def _delete_variation(ctx, device, index=None):
    if not device.variation_count:
        raise CommandError("not_found", "'{0}' has no stored variations".format(device.name))
    _select_variation(device, index)
    device.delete_selected_variation()
    return {"variations": _variations(device)}


def drum_pad(device, ref):
    """A pad of a Drum Rack by note (36, 'C1') or by the name of a non-empty pad."""
    pads = list(device.drum_pads)
    if not pads:
        raise CommandError("unsupported", "'{0}' is a nested Drum Rack; address the top-level Drum Rack's pads".format(device.name))
    note = None
    if isinstance(ref, (int, float)) and not isinstance(ref, bool):
        note = units.parse_pitch(ref, "pad")
    elif isinstance(ref, str):
        note = drum_note(ref)
        if note is None and re.match(r"^\s*\d+\s*$", ref):
            note = units.parse_pitch(ref, "pad")
    if note is not None:
        for pad in pads:
            if pad.note == note:
                return pad
    filled = [pad for pad in pads if len(pad.chains)]
    for pad in filled:
        if str(pad.name).strip().lower() == str(ref).strip().lower():
            return pad
    raise not_found("Drum pad", ref, ["{0} {1}".format(note_name(pad.note), pad.name) for pad in filled])


@_action("copy_pad", "drum_rack")
def _copy_pad(ctx, device, source, destination):
    source_pad = drum_pad(device, source)
    target_pad = drum_pad(device, destination)
    if not len(source_pad.chains):
        raise CommandError("invalid_argument", "Pad {0} is empty; nothing to copy".format(note_name(source_pad.note)))
    device.copy_pad(source_pad.note, target_pad.note)
    return {"pads": pads_out(device)}


@_action("delete_chains", "drum_rack")
def _delete_chains(ctx, device, pad):
    target = drum_pad(device, pad)
    target.delete_all_chains()
    return {"pads": pads_out(device)}


@_action("to_midi_track", "drum_rack")
def _to_midi_track(ctx, device, pad, name=None):
    import Live
    song = ctx.song
    target = drum_pad(device, pad)
    if not len(target.chains):
        raise CommandError("invalid_argument", "Pad {0} is empty".format(note_name(target.note)))
    before = [getattr(item, "_live_ptr", None) for item in song.tracks]
    Live.Conversions.create_midi_track_from_drum_pad(song, target)
    created = [item for item in song.tracks if getattr(item, "_live_ptr", None) not in before]
    if name is not None:
        for item in created:
            item.name = str(name)
    return {"created_tracks": [refs.track_label(song, item) for item in created]}


# -- Simpler -----------------------------------------------------------------


def _sample(device):
    sample = device.sample
    if sample is None:
        raise CommandError("unsupported", "Simpler '{0}' has no sample loaded".format(device.name), hint="Load one with load_from_browser or device_action(action='replace_sample').")
    return sample


def _simpler_state(device, detail=False):
    return {"playback_mode": property_out(device, "playback_mode", _class_properties(device)["playback_mode"], {}).get("item"), "sample": sample_out(device, detail)}


def _simple_simpler_action(name, method):
    def run(ctx, device):
        _sample(device)
        getattr(device, method)()
        return _simpler_state(device)
    run.__name__ = "_simpler_" + name
    _action(name, "simpler")(run)


for _name in ("crop", "reverse"):
    _simple_simpler_action(_name, _name)


@_action("warp_as", "simpler")
def _warp_as(ctx, device, beats):
    _sample(device)
    length = units.parse_length(ctx.song, beats, "beats")
    if not device.can_warp_as:
        raise CommandError("unsupported", "warp_as is not available for '{0}' right now (it needs a warped sample)".format(device.name), hint="Set properties={'sample.warping': true} first.")
    device.warp_as(length)
    return _simpler_state(device)


@_action("warp_double", "simpler")
def _warp_double(ctx, device):
    _sample(device)
    if not device.can_warp_double:
        raise CommandError("unsupported", "warp_double is not available for '{0}' right now".format(device.name))
    device.warp_double()
    return _simpler_state(device)


@_action("warp_half", "simpler")
def _warp_half(ctx, device):
    _sample(device)
    if not device.can_warp_half:
        raise CommandError("unsupported", "warp_half is not available for '{0}' right now".format(device.name))
    device.warp_half()
    return _simpler_state(device)


@_action("guess_playback_length", "simpler")
def _guess_playback_length(ctx, device):
    _sample(device)
    return {"beats": round(float(device.guess_playback_length()), 6)}


@_action("replace_sample", "simpler")
def _replace_sample(ctx, device, file_path):
    import os
    path = os.path.expanduser(str(file_path))
    if not os.path.isfile(path):
        raise CommandError("not_found", "Audio file {0!r} does not exist".format(file_path))
    device.replace_sample(path)
    return _simpler_state(device)


def _frames(sample, time=None, seconds=None, what="time"):
    if (time is None) == (seconds is None):
        raise CommandError("invalid_argument", "Pass exactly one of {0} (sample frames) or seconds".format(what))
    if seconds is not None:
        return int(round(float(_number(seconds, "seconds")) * sample.sample_rate))
    return _int_arg(time, what)


@_action("insert_slice", "simpler")
def _insert_slice(ctx, device, time=None, seconds=None):
    sample = _sample(device)
    sample.insert_slice(_frames(sample, time, seconds))
    return {"slices": [int(item) for item in sample.slices]}


@_action("move_slice", "simpler")
def _move_slice(ctx, device, time=None, to=None, seconds=None, to_seconds=None):
    sample = _sample(device)
    source = _frames(sample, time, seconds)
    target = _frames(sample, to, to_seconds, "to")
    moved = sample.move_slice(source, target)
    return {"moved_to": int(moved), "slices": [int(item) for item in sample.slices]}


@_action("remove_slice", "simpler")
def _remove_slice(ctx, device, time=None, seconds=None):
    sample = _sample(device)
    sample.remove_slice(_frames(sample, time, seconds))
    return {"slices": [int(item) for item in sample.slices]}


@_action("clear_slices", "simpler")
def _clear_slices(ctx, device):
    sample = _sample(device)
    sample.clear_slices()
    return {"slices": [int(item) for item in sample.slices]}


@_action("reset_slices", "simpler")
def _reset_slices(ctx, device):
    sample = _sample(device)
    sample.reset_slices()
    return {"slices": [int(item) for item in sample.slices]}


@_action("to_drum_rack", "simpler")
def _to_drum_rack(ctx, device):
    import Live
    _sample(device)
    if int(device.playback_mode) != 2:
        raise CommandError("unsupported", "to_drum_rack needs Simpler in slicing mode", hint="set_device(properties={'playback_mode': 'slicing'}) first.")
    container = device.canonical_parent
    index = refs.index_of(container.devices, device)
    Live.Conversions.sliced_simpler_to_drum_rack(ctx.song, device)
    devices = list(container.devices)
    out = {"devices": brief_list(container)}
    if index is not None and index < len(devices):
        out["device"] = summary(devices[index], index)
    return out


# -- Looper ------------------------------------------------------------------


def _looper_state(device):
    return {"loop_length": device.loop_length, "tempo": round(float(device.tempo), 3)}


def _simple_looper_action(name):
    def run(ctx, device):
        getattr(device, name)()
        return _looper_state(device)
    run.__name__ = "_looper_" + name
    _action(name, "looper")(run)


for _name in ("record", "overdub", "play", "stop", "clear", "undo", "double_length", "half_length", "double_speed", "half_speed"):
    _simple_looper_action(_name)


@_action("export_to_clip_slot", "looper")
def _export_to_clip_slot(ctx, device, track, slot):
    holder = refs.clip_slot(ctx.song, track, slot)
    if holder.has_clip:
        raise CommandError("invalid_argument", "Slot {0} of track '{1}' is not empty".format(slot, refs.track(ctx.song, track).name))
    device.export_to_clip_slot(holder)
    return {"slot": slot, "has_clip": bool(holder.has_clip)}


# -- Device ------------------------------------------------------------------


@_action("save_ab_slot", "compare_ab")
def _save_ab_slot(ctx, device):
    device.save_preset_to_compare_ab_slot()
    return {"compare_b": bool(device.is_using_compare_preset_b)}


# -- Wavetable ---------------------------------------------------------------

_MODULATION_ALIASES = {
    "env1": 0, "ampenv": 0, "ampenvelope": 0, "envelope1": 0, "env2": 1, "envelope2": 1, "env3": 2, "envelope3": 2,
    "lfo1": 3, "lfo2": 4, "velocity": 5, "vel": 5, "note": 6, "key": 6, "pitchbend": 7, "pb": 7,
    "pressure": 8, "aftertouch": 8, "modwheel": 9, "mw": 9, "random": 10, "rand": 10,
}


def _modulation_sources():
    import Live
    return sorted((int(number), str(item.name)) for number, item in Live.WavetableDevice.ModulationSource.values.items() if str(item.name) != "count")


def _modulation_source(ref):
    sources = _modulation_sources()
    numbers = dict(sources)
    if isinstance(ref, (int, float)) and not isinstance(ref, bool) and int(ref) in numbers:
        return int(ref)
    key = _norm(ref)
    if key in _MODULATION_ALIASES:
        return _MODULATION_ALIASES[key]
    labels = [label for _, label in sources]
    return sources[match_option(labels, ref, "Modulation source")][0]


def _modulation_target(device, ref):
    names = [str(item) for item in device.visible_modulation_target_names]
    return match_option(names, ref, "Modulation target"), names


def _modulation_row(device, target, sources):
    row = {}
    for number, label in sources:
        value = float(device.get_modulation_value(target, number))
        if value:
            row[label] = round(value, 4)
    return row


@_action("get_modulation", "wavetable")
def _get_modulation(ctx, device, target=None, source=None):
    sources = _modulation_sources()
    if target is not None:
        index, names = _modulation_target(device, target)
        if source is not None:
            number = _modulation_source(source)
            return {"target": names[index], "source": dict(sources)[number], "value": round(float(device.get_modulation_value(index, number)), 4)}
        return {"target": names[index], "amounts": _modulation_row(device, index, sources)}
    names = [str(item) for item in device.visible_modulation_target_names]
    matrix = {}
    for index, name in enumerate(names):
        row = _modulation_row(device, index, sources)
        if row:
            matrix[name] = row
    return {"targets": names, "sources": [label for _, label in sources], "matrix": matrix}


@_action("set_modulation", "wavetable")
def _set_modulation(ctx, device, target, source, value):
    index, names = _modulation_target(device, target)
    number = _modulation_source(source)
    device.set_modulation_value(index, number, float(_number(value, "value")))
    return {"target": names[index], "source": dict(_modulation_sources())[number], "value": round(float(device.get_modulation_value(index, number)), 4)}


@_action("add_parameter_to_modulation_matrix", "wavetable")
def _add_parameter_to_modulation_matrix(ctx, device, parameter):
    target = refs.parameter(device, parameter)
    if not device.is_parameter_modulatable(target):
        raise CommandError("unsupported", "Parameter '{0}' cannot be modulated in Wavetable's matrix".format(target.name))
    index = device.add_parameter_to_modulation_matrix(target)
    return {"target_index": int(index), "targets": [str(item) for item in device.visible_modulation_target_names]}


# -- Plug-ins ----------------------------------------------------------------


@_action("parameter_names", "plugin")
def _parameter_names(ctx, device, begin=0, end=-1):
    return {"names": [str(item) for item in device.get_parameter_names(_int_arg(begin, "begin"), _int_arg(end, "end"))]}


@command("device_action", timeout=20.0)
def device_action(ctx, track, device, action, args=None):
    """Run a type-specific device function from the whitelist (racks, Simpler, Looper, Wavetable, ...)."""
    import inspect
    target, _, index = refs.device(ctx.song, track, device)
    allowed = available_actions(target)
    entry = ACTIONS.get(str(action))
    if entry is None or str(action) not in allowed:
        message = "Action {0!r} does not apply to '{1}' ({2}).".format(action, target.name, target.class_display_name)
        if entry is not None:
            message += " It is for {0}.".format(_KINDS[entry[0]][0])
        raise CommandError("invalid_argument", message + " Actions for this device: {0}".format(", ".join(allowed) or "none"))
    func = entry[1]
    arguments = args or {}
    if not isinstance(arguments, dict):
        raise CommandError("invalid_argument", "args must be an object of named arguments, got {0!r}".format(args))
    signature = inspect.signature(func)
    try:
        signature.bind(ctx, target, **arguments)
    except TypeError as error:
        accepted = [name for name in list(signature.parameters)[2:]]
        raise CommandError("invalid_argument", "{0}: {1}. Arguments: {2}".format(action, error, ", ".join(accepted) or "none"))
    try:
        result = func(ctx, target, **arguments)
    except CommandError:
        raise
    except Exception as error:
        raise CommandError("live_error", "{0} on '{1}' failed: {2}".format(action, target.name, str(error) or error.__class__.__name__))
    out = {"action": str(action), "device": summary(target, index) if _alive(target) else None}
    out.update(result or {})
    return out


def _alive(device):
    try:
        device.name
        return device.canonical_parent is not None
    except Exception:
        return False
