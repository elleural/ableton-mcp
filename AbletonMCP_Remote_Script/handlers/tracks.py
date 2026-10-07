"""WS-B: tracks, mixer, routing, meters and buses (docs/PRD.md section 7.3). Owned by workstream B.

Live behaviour this module relies on (verified on Live 12.4.6, see docs/spikes.md):
- A new track does not appear in *other* tracks' routing lists until the next main-thread tick, and a
  track created later in the same tick can have empty own lists ([""]). Routing therefore happens in a
  separate command; a list that is not ready raises a "busy" error the caller may retry.
- Routing display names are the track names ("Drum Bus"); Live's default names carry a track-number
  prefix ("5-Audio"). Routing types of tracks expose the Track as attached_object.
- Return tracks are always named "<letter>-<name>": Live adds the letter itself, so a name passed with
  the track's own letter is stripped first ("C-Verb" would otherwise become "C-C-Verb").
- Track meters (input and output, left/right/level) are linear in dB: dBFS = 76 * raw - 70, so raw 0
  means -70 dBFS or less and raw 1 means +6 dBFS or more. output_meter_level holds the peak for 1 s.
- A volume or send parameter at its minimum reports display_value -70 while Live shows "-inf dB".
- An audio track only passes audio routed into it from other tracks when its monitoring is "In".
"""
import math
import re

from .. import refs, values
from ..core import command
from ..errors import CommandError, not_found

KINDS = ("midi", "audio", "return")
MAX_SLOTS = 32  # non-empty Session slots listed by get_track without detail
METER_FLOOR_DB = -70.0
METER_SPAN_DB = 76.0  # raw 0..1 spans -70..+6 dBFS
VOLUME_MAX_DB = 6.0
SEND_MAX_DB = 0.0

_TRACK_NUMBER = re.compile(r"^\s*\d+-")
_HEX_COLOR = re.compile(r"^#?[0-9a-fA-F]{6}$")


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested offline)
# ---------------------------------------------------------------------------


def meter_db(raw):
    """dBFS estimate of a Live meter value: '-inf' at 0 (-70 dBFS or less), 6.0 at the top (+6 or more)."""
    try:
        raw = float(raw)
    except (TypeError, ValueError):
        return None
    if raw <= 0.0:
        return "-inf"
    return round(min(raw, 1.0) * METER_SPAN_DB + METER_FLOOR_DB, 1)


def strip_track_number(name):
    """'5-Drum Bus' -> 'Drum Bus' (Live's default track names carry the track number)."""
    return _TRACK_NUMBER.sub("", str(name), count=1)


def strip_own_letter(name, letter):
    """Drop a return track's own '<letter>-' prefix, which Live adds back by itself."""
    text = str(name)
    prefix = "{0}-".format(letter)
    if letter and text[:len(prefix)].upper() == prefix.upper() and len(text) > len(prefix):
        return text[len(prefix):]
    return text


def check_color(value):
    """Validate a colour (Live colour index 0..69 or '#RRGGBB') before anything is created."""
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 69:
        return value
    if isinstance(value, str) and _HEX_COLOR.match(value.strip()):
        return value
    raise CommandError("invalid_argument", "color must be a Live colour index (0..69) or '#RRGGBB', got {0!r}".format(value))


def check_bool(value, name):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise CommandError("invalid_argument", "{0} must be true or false, got {1!r}".format(name, value))


def _key(text):
    return str(text).strip().lower()


def match_option(names, ref, what, aliases=None):
    """Index of the option whose display name matches ref.

    Order: exact (case-insensitive) display name; alias; display name without Live's 'N-' track-number
    prefix (on either side); unique substring of at least 3 characters. Ambiguous or unknown names raise
    with the options.
    """
    key = _key(ref)
    labelled = [(position, str(name)) for position, name in enumerate(names) if str(name)]
    options = [name for _, name in labelled]

    def pick(matches):
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise CommandError(
                "invalid_argument",
                "{0} {1!r} is ambiguous: it matches {2}. Rename a track, or pass a track index instead.".format(
                    what, ref, ", ".join(str(names[position]) for position in matches)),
            )
        return None

    found = pick([position for position, name in labelled if _key(name) == key])
    if found is not None:
        return found
    alias = (aliases or {}).get(key)
    if alias:
        found = pick([position for position, name in labelled if _key(name) == alias])
        if found is not None:
            return found
    bare = _key(strip_track_number(ref))
    found = pick([position for position, name in labelled if _key(strip_track_number(name)) in (key, bare)])
    if found is not None:
        return found
    if len(key) >= 3:
        found = pick([position for position, name in labelled if key in _key(name)])
        if found is not None:
            return found
    raise not_found(what, ref, options)


def match_channel(names, ref, what):
    """Index of a routing channel by display name; numbers also match MIDI 'Ch. N' channels."""
    text = str(ref).strip()
    if isinstance(ref, bool):
        raise CommandError("invalid_argument", "{0} must be a channel name such as '1/2' or 'Ch. 1', got {1!r}".format(what, ref))
    if isinstance(ref, (int, float)) and float(ref).is_integer():
        text = str(int(ref))
    labelled = [(position, str(name)) for position, name in enumerate(names) if str(name)]
    for candidates in ([text], ["ch. " + text, "ch " + text]):
        matches = [position for position, name in labelled if _key(name) in [_key(item) for item in candidates]]
        if len(matches) == 1:
            return matches[0]
    matches = [position for position, name in labelled if _key(text) and _key(text) in _key(name)]
    if len(matches) == 1:
        return matches[0]
    raise not_found(what, ref, [name for _, name in labelled])


def check_db(value, name, maximum):
    """Validate a dB amount: a number up to maximum, or '-inf'. Returns a float or '-inf'."""
    if isinstance(value, str) and value.strip().lower() in ("-inf", "-infinity", "inf", "off", "-∞"):
        return "-inf"
    if isinstance(value, bool) or value is None:
        raise CommandError("invalid_argument", "{0} must be a number of dB or '-inf', got {1!r}".format(name, value))
    try:
        number = float(str(value).lower().replace("db", "").strip()) if isinstance(value, str) else float(value)
    except ValueError:
        raise CommandError("invalid_argument", "{0} must be a number of dB or '-inf', got {1!r}".format(name, value))
    if math.isnan(number):
        raise CommandError("invalid_argument", "{0} must be a number of dB, got NaN".format(name))
    if number > maximum + 1e-9:
        raise CommandError("invalid_argument", "{0} {1:g} dB is above the maximum of {2:+g} dB".format(name, number, maximum))
    if number <= METER_FLOOR_DB:
        return "-inf"
    return number


# ---------------------------------------------------------------------------
# Reading Live objects
# ---------------------------------------------------------------------------


def _safe(read, default=None):
    try:
        return read()
    except Exception:
        return default


def _db(param):
    """dB of a volume/send parameter, with '-inf' at the minimum (Live reports -70 there)."""
    if float(param.value) <= float(param.min) + 1e-9:
        return "-inf"
    number = values.display_number(param)
    if number is None or math.isinf(number) or number <= METER_FLOOR_DB:
        return "-inf"
    return round(number, 2)


def _label(song, track):
    return refs.track_label(song, track)


def _kind(song, track):
    return refs.track_kind(song, track)


def _all_tracks(song):
    return list(song.tracks) + list(song.return_tracks) + [song.master_track]


def _selected_tracks(song, tracks):
    if tracks is None:
        return _all_tracks(song)
    return refs.tracks(song, tracks)


def _device_out(position, device, detail=False):
    out = {"index": position, "name": device.name, "class": device.class_display_name}
    parameters = _safe(lambda: list(device.parameters), [])
    if parameters and _safe(lambda: parameters[0].original_name) == "Device On":
        out["on"] = parameters[0].value >= 0.5
    else:
        out["on"] = bool(_safe(lambda: device.is_active, True))
    if detail:
        out["class_name"] = device.class_name
        out["type"] = values.DEVICE_TYPE.name(_safe(lambda: device.type, 0))
        out["parameter_count"] = len(parameters)
        if _safe(lambda: device.can_have_chains, False):
            out["chain_count"] = len(_safe(lambda: device.chains, []))
    return out


def _routing_name(item):
    name = _safe(lambda: item.display_name, "")
    return name or None


def _has_input_routing(kind):
    return kind in ("midi", "audio")


def _routing_state(song, track, kind=None):
    kind = kind or _kind(song, track)
    out = {}
    if _has_input_routing(kind):
        out["input"] = {"type": _routing_name(_safe(lambda: track.input_routing_type)),
                        "channel": _routing_name(_safe(lambda: track.input_routing_channel))}
    out["output"] = {"type": _routing_name(_safe(lambda: track.output_routing_type)),
                     "channel": _routing_name(_safe(lambda: track.output_routing_channel))}
    return out


def send_is_active(send):
    """False for sends Live marks irrelevant (return-to-return sends are off until enabled in Live)."""
    return _safe(lambda: int(send.state), 0) == 0


def _sends_out(song, track, out):
    """Adds 'sends' {letter: dB} and, when some are inactive, 'inactive_sends' [letters] to out."""
    sends, inactive = {}, []
    for position, send in enumerate(_safe(lambda: list(track.mixer_device.sends), [])):
        letter = refs.return_letter(position)
        if send_is_active(send):
            sends[letter] = _db(send)
        else:
            inactive.append(letter)
    out["sends"] = sends
    if inactive:
        out["inactive_sends"] = inactive
    return out


def _pan_out(param):
    return round(float(param.value), 3), param.str_for_value(param.value)


def mixer_state(song, track):
    """Every mixer value of one track (the get_mixer / set_mixer shape)."""
    kind = _kind(song, track)
    mixer = track.mixer_device
    out = _label(song, track)
    out["volume_db"] = _db(mixer.volume)
    out["pan"], out["pan_display"] = _pan_out(mixer.panning)
    if kind != "master":
        _sends_out(song, track, out)
        out["mute"] = bool(track.mute)
        out["solo"] = bool(track.solo)
        out["crossfade"] = values.CROSSFADE_ASSIGN.name(mixer.crossfade_assign)
    if _safe(lambda: track.can_be_armed, False):
        out["arm"] = bool(track.arm)
    out["active"] = float(mixer.track_activator.value) >= 0.5
    out["pan_mode"] = values.PANNING_MODE.name(mixer.panning_mode)
    if out["pan_mode"] == "split":
        out["left_pan"] = round(float(mixer.left_split_stereo.value), 3)
        out["right_pan"] = round(float(mixer.right_split_stereo.value), 3)
    if kind == "master":
        out["crossfader"] = round(float(mixer.crossfader.value), 3)
        out["crossfader_display"] = mixer.crossfader.str_for_value(mixer.crossfader.value)
        out["cue_volume_db"] = _db(mixer.cue_volume)
    return out


def _mixer_brief(song, track, kind):
    mixer = track.mixer_device
    out = {"volume_db": _db(mixer.volume)}
    out["pan"], out["pan_display"] = _pan_out(mixer.panning)
    if kind != "master":
        _sends_out(song, track, out)
    return out


def meters_state(song, track):
    """Output (and audio input) meter levels of one track, as dBFS estimates plus Live's raw values."""
    kind = _kind(song, track)
    out = _label(song, track)
    if _safe(lambda: track.has_audio_output, False):
        left = float(track.output_meter_left)
        right = float(track.output_meter_right)
        level = float(track.output_meter_level)
        out["output"] = {"peak_db": meter_db(level), "left_db": meter_db(left), "right_db": meter_db(right),
                         "raw": [round(left, 4), round(right, 4), round(level, 4)]}
        if level >= (0.0 - METER_FLOOR_DB) / METER_SPAN_DB:
            out["output"]["over_0db"] = True
    else:
        out["output"] = {"midi": round(float(_safe(lambda: track.output_meter_level, 0.0)), 3)}
    if kind == "audio":
        left = float(_safe(lambda: track.input_meter_left, 0.0))
        right = float(_safe(lambda: track.input_meter_right, 0.0))
        out["input"] = {"left_db": meter_db(left), "right_db": meter_db(right), "raw": [round(left, 4), round(right, 4)]}
    elif kind == "midi":
        out["input"] = {"midi": round(float(_safe(lambda: track.input_meter_level, 0.0)), 3)}
    return out


def _slot_out(song, position, slot, detail=False):
    clip = slot.clip
    out = {"slot": position, "name": clip.name, "length": round(float(clip.length), 6)}
    if _safe(lambda: slot.is_recording, False):
        out["state"] = "recording"
    elif _safe(lambda: clip.is_playing, False):
        out["state"] = "playing"
    elif _safe(lambda: slot.is_triggered, False):
        out["state"] = "triggered"
    if detail:
        out.update(values.color_out(clip))
        out["is_audio"] = bool(_safe(lambda: clip.is_audio_clip, False))
        out["looping"] = bool(_safe(lambda: clip.looping, False))
        out["muted"] = bool(_safe(lambda: clip.muted, False))
    return out


def _clip_span(song, clip, position=None):
    out = {} if position is None else {"index": position}
    out["name"] = clip.name
    out["start"] = values.time_out(song, clip.start_time)
    out["end"] = values.time_out(song, clip.end_time)
    return out


def _track_brief(song, track):
    """Identity, colour, switches and routing of a track: what create_track / set_track return."""
    kind = _kind(song, track)
    out = _label(song, track)
    out.update(values.color_out(track))
    if kind != "master":
        out["mute"] = bool(track.mute)
        out["solo"] = bool(track.solo)
    if _safe(lambda: track.can_be_armed, False):
        out["arm"] = bool(track.arm)
        if _safe(lambda: track.implicit_arm, False):
            out["implicit_arm"] = True
    if kind in ("midi", "audio"):
        out["monitoring"] = values.MONITORING.name(track.current_monitoring_state)
    if _safe(lambda: track.is_foldable, False):
        out["folded"] = bool(track.fold_state)
    if _safe(lambda: track.is_grouped, False):
        group = track.group_track
        out["group_track"] = {"track": refs.track_ref(song, group), "name": group.name}
    collapsed = _safe(lambda: track.view.is_collapsed)
    if collapsed is not None:
        out["collapsed"] = bool(collapsed)
    if _safe(lambda: track.can_show_chains, False):
        out["showing_chains"] = bool(track.is_showing_chains)
    out.update(_routing_state(song, track, kind))
    return out


def track_state(song, track, detail=False):
    """get_track output: bounded by default, everything with detail."""
    kind = _kind(song, track)
    out = _track_brief(song, track)
    out["frozen"] = bool(_safe(lambda: track.is_frozen, False))
    out["mixer"] = mixer_state(song, track) if detail else _mixer_brief(song, track, kind)
    if detail:
        for key in ("track", "name", "kind"):
            out["mixer"].pop(key, None)
    out["devices"] = [_device_out(position, device, detail) for position, device in enumerate(track.devices)]
    slots = list(_safe(lambda: track.clip_slots, []) or [])
    if slots:
        filled = [(position, slot) for position, slot in enumerate(slots) if _safe(lambda: slot.has_clip, False)]
        shown = filled if detail else filled[:MAX_SLOTS]
        out["slots"] = [_slot_out(song, position, slot, detail) for position, slot in shown]
        out["slot_count"] = len(slots)
        if len(filled) > len(shown):
            out["slots_truncated"] = len(filled) - len(shown)
    if kind in ("midi", "audio"):
        clips = refs.arrangement_clips(track)
        arrangement = {"clip_count": len(clips)}
        if clips:
            arrangement["start"] = values.time_out(song, min(clip.start_time for clip in clips))
            arrangement["end"] = values.time_out(song, max(clip.end_time for clip in clips))
            if detail:
                arrangement["clips"] = [_clip_span(song, clip, position) for position, clip in enumerate(clips)]
        out["arrangement"] = arrangement
    lanes = list(_safe(lambda: track.take_lanes, []) or [])
    if lanes:
        out["take_lanes"] = []
        for position, lane in enumerate(lanes):
            lane_clips = sorted(list(_safe(lambda: lane.arrangement_clips, []) or []), key=lambda clip: clip.start_time)
            entry = {"index": position, "name": lane.name, "clip_count": len(lane_clips)}
            if detail:
                entry["clips"] = [_clip_span(song, clip) for clip in lane_clips]
            out["take_lanes"].append(entry)
    if detail:
        out["meters"] = dict((key, item) for key, item in meters_state(song, track).items() if key in ("output", "input"))
        extra = {}
        for name in ("muted_via_solo", "is_visible", "can_be_frozen", "can_show_chains", "has_audio_input",
                     "has_audio_output", "has_midi_input", "has_midi_output", "playing_slot_index", "fired_slot_index"):
            value = _safe(lambda: getattr(track, name))
            if value is not None:
                extra[name] = values.jsonable(value)
        impact = _safe(lambda: track.performance_impact)
        if impact is not None:
            extra["performance_impact"] = round(float(impact), 4)
        out["state"] = extra
    return out


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

_DIRECTIONS = {
    "input": ("available_input_routing_types", "available_input_routing_channels", "input_routing_type", "input_routing_channel", "No Input"),
    "output": ("available_output_routing_types", "available_output_routing_channels", "output_routing_type", "output_routing_channel", "No Output"),
}


def routing_aliases(direction):
    """Friendly names for routing types: 'master' -> 'Main', 'none' -> 'No Input' / 'No Output', ..."""
    external = "ext. in" if direction == "input" else "ext. out"
    nothing = "no input" if direction == "input" else "no output"
    return {"master": "main", "main out": "main", "sends": "sends only", "none": nothing, "off": nothing,
            "no": nothing, "external": external, "ext": external, "ext in": external, "ext out": external}


def _routing_items(track, attribute):
    return list(_safe(lambda: getattr(track, attribute), []) or [])


def _ready(items):
    return any(_routing_name(item) for item in items)


def _not_ready(track, direction):
    return CommandError(
        "busy",
        "Routing options of track '{0}' are not ready yet: Live fills them on the tick after tracks are created. "
        "Retry the call.".format(track.name),
        hint="not ready yet",
    )


def resolve_routing_type(song, track, direction, ref):
    """The RoutingType of track's input or output whose display name (or attached track) matches ref."""
    types_attr = _DIRECTIONS[direction][0]
    items = _routing_items(track, types_attr)
    if not _ready(items):
        raise _not_ready(track, direction)
    names = [_routing_name(item) or "" for item in items]
    what = "{0} routing for track '{1}'".format(direction.capitalize(), track.name)
    if isinstance(ref, str) and ref.strip():
        try:
            return items[match_option(names, ref, what, routing_aliases(direction))]
        except CommandError as error:
            if error.code != "not_found":
                raise
            target = _safe(lambda: refs.track(song, ref))
            if target is None:
                raise
    elif isinstance(ref, int) and not isinstance(ref, bool):
        target = refs.track(song, ref)
    else:
        raise CommandError("invalid_argument", "{0} must be a routing name or a track, got {1!r}".format(direction, ref))
    for item in items:
        if refs.same(_safe(lambda: item.attached_object), target):
            return item
    raise not_found(what + " to track", target.name, [name for name in names if name])


def resolve_routing_channel(track, direction, ref):
    _, channels_attr, _, _, _ = _DIRECTIONS[direction]
    items = _routing_items(track, channels_attr)
    names = [_routing_name(item) or "" for item in items]
    if not any(names):
        raise CommandError("invalid_argument", "The current {0} routing of track '{1}' has no channels to choose".format(direction, track.name))
    return items[match_channel(names, ref, "{0} channel for track '{1}'".format(direction.capitalize(), track.name))]


def _apply_routing(song, track, direction, type_ref, channel_ref):
    """Set a routing type and/or channel; restores the previous type if the channel cannot be set."""
    _, _, type_attr, channel_attr, _ = _DIRECTIONS[direction]
    previous = _safe(lambda: getattr(track, type_attr))
    if type_ref is not None:
        setattr(track, type_attr, resolve_routing_type(song, track, direction, type_ref))
    if channel_ref is not None:
        try:
            setattr(track, channel_attr, resolve_routing_channel(track, direction, channel_ref))
        except Exception:
            if type_ref is not None and previous is not None:
                _safe(lambda: setattr(track, type_attr, previous))
            raise


def routing_options(song, track):
    kind = _kind(song, track)
    out = _label(song, track)
    for direction in ("input", "output"):
        if direction == "input" and not _has_input_routing(kind):
            continue
        types_attr, channels_attr, type_attr, channel_attr, _ = _DIRECTIONS[direction]
        types = _routing_items(track, types_attr)
        out[direction] = {
            "type": _routing_name(_safe(lambda: getattr(track, type_attr))),
            "channel": _routing_name(_safe(lambda: getattr(track, channel_attr))),
            "types": [name for name in (_routing_name(item) for item in types) if name],
            "channels": [name for name in (_routing_name(item) for item in _routing_items(track, channels_attr)) if name],
        }
        if not _ready(types):
            out[direction]["note"] = "Not ready yet (track created this tick); read again."
    if kind == "master":
        out["note"] = "The master has output routing only."
    elif not _has_input_routing(kind):
        out["note"] = "Return and group tracks have output routing only."
    return out


# ---------------------------------------------------------------------------
# Commands: tracks
# ---------------------------------------------------------------------------


def _native_category(app, device_name):
    for category, names in refs.native_device_names(app).items():
        if device_name in names:
            return category
    return None


def _require_unique_name(song, name, ignore=None):
    """Refuse a name another track already has: duplicate names make every later name lookup ambiguous."""
    if name is None:
        return
    key = str(name).strip().lower()
    for candidate in list(song.tracks) + list(song.return_tracks):
        if ignore is not None and refs.same(candidate, ignore):
            continue
        if key in (str(candidate.name).strip().lower(), refs.return_bare_name(candidate.name).strip().lower()):
            raise CommandError("invalid_argument", "A track named '{0}' already exists ({1}); pick another name or use that track".format(
                candidate.name, refs.track_ref(song, candidate)))


def _set_name(song, track, name):
    if name is None:
        return
    text = str(name)
    if not text.strip():
        raise CommandError("invalid_argument", "name must not be empty")
    position = refs.index_of(song.return_tracks, track)
    if position is not None:
        text = strip_own_letter(text, refs.return_letter(position))
    track.name = text


@command("create_track")
def create_track(ctx, kind, name=None, index=-1, color=None, device=None):
    """Create a MIDI, audio or return track, optionally named, coloured and with a native device."""
    song = ctx.song
    kind_key = _key(kind)
    if kind_key not in KINDS:
        raise CommandError("invalid_argument", "kind must be one of: {0} (got {1!r})".format(", ".join(KINDS), kind))
    if color is not None:
        check_color(color)
    if name is not None and not str(name).strip():
        raise CommandError("invalid_argument", "name must not be empty")
    position = -1 if index is None else index
    if isinstance(position, bool) or not isinstance(position, int):
        raise CommandError("invalid_argument", "index must be an integer (-1 = end), got {0!r}".format(index))
    count = len(song.tracks)
    if kind_key == "return":
        if position != -1:
            raise CommandError("invalid_argument", "Return tracks are always added after the existing returns; omit index")
    elif not -1 <= position <= count:
        raise CommandError("invalid_argument", "index {0} is out of range: use 0..{1}, or -1 for the end".format(position, count))
    _require_unique_name(song, name)
    device_name = None
    if device is not None:
        device_name = refs.native_device_name(ctx.app, device)
        category = _native_category(ctx.app, device_name)
        if category in ("instruments", "midi_effects") and kind_key != "midi":
            raise CommandError("invalid_argument", "'{0}' is {1}; it can only go on a MIDI track".format(
                device_name, "an instrument" if category == "instruments" else "a MIDI effect"))
    if kind_key == "midi":
        track = song.create_midi_track(position)
    elif kind_key == "audio":
        track = song.create_audio_track(position)
    else:
        track = song.create_return_track()
    _set_name(song, track, name)
    if color is not None:
        values.apply_color(track, color)
    inserted = None
    if device_name is not None:
        try:
            inserted = track.insert_device(device_name)
        except Exception as error:
            _delete(song, track)
            raise CommandError(
                "live_error",
                "Could not insert '{0}' on the new {1} track, so it was not created: {2}".format(device_name, kind_key, error),
                hint="Pack and Max for Live devices (e.g. Granulator III, Poli) cannot be inserted by name: create the "
                     "track without a device, then use load_from_browser.",
            )
    out = _track_brief(song, track)
    for direction in ("input", "output"):
        if direction in out and out[direction]["type"] is None:
            del out[direction]  # Live has not resolved it yet in this tick
    if inserted is not None:
        out["device"] = _device_out(refs.index_of(track.devices, inserted), inserted)
    out["note"] = "Routing of the new track, and the track as a routing target, are available from the next call."
    return out


@command("get_track", readonly=True)
def get_track(ctx, track, detail=False):
    """Mixer, routing, devices, clip slots, arrangement extent, take lanes and freeze state of a track."""
    song = ctx.song
    return track_state(song, refs.track(song, track), bool(detail))


@command("set_track")
def set_track(ctx, track, name=None, color=None, arm=None, monitoring=None, fold=None, collapsed=None,
              input=None, input_channel=None, output=None, output_channel=None, show_chains=None):
    """Rename, colour, arm, monitor, fold or collapse a track, set its routing, or show rack chains."""
    song = ctx.song
    owner = refs.track(song, track)
    kind = _kind(song, owner)
    changes = dict((key, value) for key, value in (
        ("name", name), ("color", color), ("arm", arm), ("monitoring", monitoring), ("fold", fold),
        ("collapsed", collapsed), ("input", input), ("input_channel", input_channel), ("output", output),
        ("output_channel", output_channel), ("show_chains", show_chains)) if value is not None)
    if not changes:
        raise CommandError("invalid_argument", "Nothing to set. Pass any of: name, color, arm, monitoring, fold, collapsed, "
                                               "input, input_channel, output, output_channel, show_chains")
    # Validate everything before changing anything.
    if name is not None and not str(name).strip():
        raise CommandError("invalid_argument", "name must not be empty")
    if color is not None:
        check_color(color)
    if arm is not None:
        arm = check_bool(arm, "arm")
        if not _safe(lambda: owner.can_be_armed, False):
            raise CommandError("unsupported", "Track '{0}' ({1}) cannot be armed".format(owner.name, kind))
    if monitoring is not None:
        monitoring = values.MONITORING.parse(monitoring)
        if kind not in ("midi", "audio"):
            raise CommandError("unsupported", "Track '{0}' ({1}) has no monitoring".format(owner.name, kind))
    if fold is not None:
        fold = check_bool(fold, "fold")
        if not _safe(lambda: owner.is_foldable, False):
            raise CommandError("unsupported", "Track '{0}' is not a group track, so it cannot fold".format(owner.name))
    if collapsed is not None:
        collapsed = check_bool(collapsed, "collapsed")
    if show_chains is not None:
        show_chains = check_bool(show_chains, "show_chains")
        if not _safe(lambda: owner.can_show_chains, False):
            raise CommandError("unsupported", "Track '{0}' has no Instrument Rack that can show chains".format(owner.name))
    if (input is not None or input_channel is not None) and not _has_input_routing(kind):
        raise CommandError("unsupported", "Track '{0}' ({1}) has no input routing".format(owner.name, kind))
    if input is not None:
        resolve_routing_type(song, owner, "input", input)
    if output is not None:
        resolve_routing_type(song, owner, "output", output)
    # Apply.
    _set_name(song, owner, name)
    if color is not None:
        values.apply_color(owner, color)
    if arm is not None:
        owner.arm = arm
    if monitoring is not None:
        owner.current_monitoring_state = monitoring
    if fold is not None:
        owner.fold_state = 1 if fold else 0
    if collapsed is not None:
        owner.view.is_collapsed = collapsed
    if show_chains is not None:
        owner.is_showing_chains = show_chains
    if input is not None or input_channel is not None:
        _apply_routing(song, owner, "input", input, input_channel)
    if output is not None or output_channel is not None:
        _apply_routing(song, owner, "output", output, output_channel)
    return _track_brief(song, owner)


def _delete(song, track):
    position = refs.index_of(song.tracks, track)
    if position is not None:
        song.delete_track(position)
        return
    position = refs.index_of(song.return_tracks, track)
    if position is not None:
        song.delete_return_track(position)
        return
    raise CommandError("invalid_argument", "The master track cannot be deleted")


@command("delete_track")
def delete_track(ctx, track):
    """Delete a regular or return track (the master cannot be deleted)."""
    song = ctx.song
    owner = refs.track(song, track)
    label = _label(song, owner)
    if label["kind"] == "master":
        raise CommandError("invalid_argument", "The master track cannot be deleted")
    before = len(song.tracks) + len(song.return_tracks)
    try:
        _delete(song, owner)
    except CommandError:
        raise
    except Exception as error:
        raise CommandError("live_error", "Live refused to delete track '{0}': {1}".format(label["name"], error))
    out = {"deleted": label, "tracks_removed": before - len(song.tracks) - len(song.return_tracks)}
    if label["kind"] == "return":
        out["note"] = "Every track's send to this return was removed; later returns moved up a letter."
    return out


@command("duplicate_track")
def duplicate_track(ctx, track, name=None):
    """Duplicate a regular track (with its devices and clips) right after it; optionally rename the copy."""
    song = ctx.song
    owner = refs.track(song, track)
    label = _label(song, owner)
    if label["kind"] in ("return", "master"):
        raise CommandError("unsupported", "Live can only duplicate regular tracks, not {0} tracks".format(label["kind"]))
    if name is not None and not str(name).strip():
        raise CommandError("invalid_argument", "name must not be empty")
    _require_unique_name(song, name)
    before = list(song.tracks)
    song.duplicate_track(refs.index_of(before, owner))
    created = [item for item in song.tracks if refs.index_of(before, item) is None]
    if not created:
        raise CommandError("live_error", "Live did not create a copy of track '{0}'".format(label["name"]))
    copy = created[0]
    _set_name(song, copy, name)
    out = {"source": _label(song, owner), "track": refs.track_ref(song, copy), "name": copy.name, "kind": _kind(song, copy)}
    if len(created) > 1:
        out["tracks_created"] = len(created)
    return out


@command("get_routing_options", readonly=True)
def get_routing_options(ctx, track):
    """Current input/output routing of a track plus the available types and channels."""
    song = ctx.song
    return routing_options(song, refs.track(song, track))


# ---------------------------------------------------------------------------
# Commands: buses
# ---------------------------------------------------------------------------


def _bus_source(song, ref, bus_name):
    source = refs.track(song, ref)
    kind = _kind(song, source)
    if kind == "master":
        raise CommandError("invalid_argument", "The master track cannot feed a bus")
    if not _safe(lambda: source.has_audio_output, False):
        raise CommandError("invalid_argument", "Track '{0}' has no audio output (a MIDI track needs an instrument first), "
                                               "so it cannot feed bus '{1}'".format(source.name, bus_name))
    return source


def _stable_ref(song, track):
    """A reference that survives other tracks being added: the name when unique, else the index."""
    key = _key(track.name)
    if sum(1 for item in list(song.tracks) + list(song.return_tracks) if _key(item.name) == key) == 1:
        return track.name
    return refs.track_ref(song, track)


@command("create_bus")
def create_bus(ctx, name, sources, color=None):
    """First step of create_bus: validate the sources and create the bus (audio track, monitoring In).

    The MCP tool routes the sources on a later call (tracks_route_to_bus), because a new track is only
    offered as a routing target from the next main-thread tick.
    """
    song = ctx.song
    if not isinstance(name, str) or not name.strip():
        raise CommandError("invalid_argument", "A bus needs a name")
    if any(_key(item.name) == _key(name) for item in list(song.tracks) + list(song.return_tracks)):
        raise CommandError("invalid_argument", "A track named {0!r} already exists; routing targets are chosen by name, "
                                               "so pick a unique bus name".format(name))
    if not isinstance(sources, (list, tuple)) or not sources:
        raise CommandError("invalid_argument", "sources must be a non-empty list of tracks")
    if color is not None:
        check_color(color)
    resolved = []
    for ref in sources:
        source = _bus_source(song, ref, name)
        if refs.index_of(resolved, source) is not None:
            raise CommandError("invalid_argument", "Track '{0}' is listed twice in sources".format(source.name))
        resolved.append(source)
    bus = song.create_audio_track(-1)
    bus.name = name
    if color is not None:
        values.apply_color(bus, color)
    bus.current_monitoring_state = values.MONITORING.parse("in")
    return {"bus": _track_brief(song, bus), "sources": [dict(_label(song, item), ref=_stable_ref(song, item)) for item in resolved]}


@command("tracks_route_to_bus")
def tracks_route_to_bus(ctx, bus, sources):
    """Second step of create_bus: route every source's output into the bus (one undo step)."""
    song = ctx.song
    target = refs.track(song, bus)
    if _kind(song, target) != "audio":
        raise CommandError("invalid_argument", "Bus '{0}' must be an audio track".format(target.name))
    if not isinstance(sources, (list, tuple)) or not sources:
        raise CommandError("invalid_argument", "sources must be a non-empty list of tracks")
    plan = []
    for ref in sources:
        source = _bus_source(song, ref, target.name)
        if refs.same(source, target):
            raise CommandError("invalid_argument", "Bus '{0}' cannot feed itself".format(target.name))
        items = _routing_items(source, "available_output_routing_types")
        if not _ready(items):
            raise _not_ready(source, "output")
        match = [item for item in items if refs.same(_safe(lambda: item.attached_object), target)]
        if not match:
            match = [item for item in items if _key(_routing_name(item) or "") == _key(target.name)][:1]
        if not match:
            raise CommandError(
                "busy",
                "Track '{0}' does not offer '{1}' as an output yet (not ready yet; Live adds new tracks to routing lists "
                "on the next tick). Outputs: {2}".format(source.name, target.name, ", ".join(_routing_name(item) or "" for item in items)),
                hint="not ready yet",
            )
        plan.append((source, match[0]))
    no_input = [item for item in _routing_items(target, "available_input_routing_types") if _routing_name(item) == "No Input"]
    for source, routing_type in plan:
        source.output_routing_type = routing_type
    if no_input:
        # Routed tracks still reach the bus; this keeps monitoring "In" from passing the audio interface input.
        target.input_routing_type = no_input[0]
    return {"bus": _track_brief(song, target),
            "sources": [dict(_label(song, source), output=_routing_state(song, source)["output"]) for source, _ in plan]}


# ---------------------------------------------------------------------------
# Commands: mixer and meters
# ---------------------------------------------------------------------------


@command("get_mixer", readonly=True)
def get_mixer(ctx, tracks=None):
    """Mixer state of every regular, return and master track (or only the given tracks)."""
    song = ctx.song
    return {"tracks": [mixer_state(song, item) for item in _selected_tracks(song, tracks)]}


_MIXER_PARAMS = ("volume_db", "volume", "pan", "sends", "mute", "solo", "active", "crossfade", "pan_mode",
                 "left_pan", "right_pan", "crossfader", "cue_volume_db")


def _set_db(param, db):
    if db == "-inf":
        param.value = param.min
    else:
        values.set_display_number(param, db)


@command("set_mixer")
def set_mixer(ctx, track, volume_db=None, volume=None, pan=None, sends=None, mute=None, solo=None, active=None,
              crossfade=None, pan_mode=None, left_pan=None, right_pan=None, crossfader=None, cue_volume_db=None):
    """Set a track's volume (dB or raw), pan, sends (dB by return), switches, crossfade and pan mode."""
    song = ctx.song
    owner = refs.track(song, track)
    kind = _kind(song, owner)
    mixer = owner.mixer_device
    given = dict((key, value) for key, value in zip(_MIXER_PARAMS, (
        volume_db, volume, pan, sends, mute, solo, active, crossfade, pan_mode, left_pan, right_pan, crossfader,
        cue_volume_db)) if value is not None)
    if not given:
        raise CommandError("invalid_argument", "Nothing to set. Pass any of: " + ", ".join(_MIXER_PARAMS))
    if volume_db is not None and volume is not None:
        raise CommandError("invalid_argument", "Pass volume_db or volume (raw 0..1), not both")
    # Validate everything before changing anything.
    actions = []  # (function, arguments), applied only once everything validated
    if volume_db is not None:
        actions.append((_set_db, (mixer.volume, check_db(volume_db, "volume_db", VOLUME_MAX_DB))))
    if volume is not None:
        if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not 0.0 <= float(volume) <= 1.0:
            raise CommandError("invalid_argument", "volume (raw) must be 0..1 (0.85 = 0 dB), got {0!r}".format(volume))
        actions.append((setattr, (mixer.volume, "value", float(volume))))
    if pan is not None:
        actions.append((setattr, (mixer.panning, "value", values.parse_pan(pan))))
    if sends is not None:
        if kind == "master":
            raise CommandError("unsupported", "The master track has no sends")
        if not isinstance(sends, dict) or not sends:
            raise CommandError("invalid_argument", "sends must be an object like {\"A\": -12, \"B\": \"-inf\"}")
        send_params = list(mixer.sends)
        for ref, amount in sends.items():
            position = refs.send_index(song, ref)
            if position >= len(send_params):
                raise CommandError("not_found", "Track '{0}' has no send {1}".format(owner.name, ref))
            if not send_is_active(send_params[position]):
                raise CommandError("unsupported", "Send {0} of '{1}' is inactive: Live turns return-to-return sends off "
                                                  "until they are enabled in Live".format(refs.return_letter(position), owner.name))
            actions.append((_set_db, (send_params[position], check_db(amount, "send {0}".format(ref), SEND_MAX_DB))))
    for switch in ("mute", "solo"):
        if given.get(switch) is not None:
            if kind == "master":
                raise CommandError("unsupported", "The master track has no {0}".format(switch))
            actions.append((setattr, (owner, switch, check_bool(given[switch], switch))))
    if active is not None:
        actions.append((setattr, (mixer.track_activator, "value", 1.0 if check_bool(active, "active") else 0.0)))
    if crossfade is not None:
        if kind == "master":
            raise CommandError("unsupported", "The master track has no crossfade assignment; use crossfader")
        actions.append((setattr, (mixer, "crossfade_assign", values.CROSSFADE_ASSIGN.parse(crossfade))))
    if pan_mode is not None:
        actions.append((setattr, (mixer, "panning_mode", values.PANNING_MODE.parse(pan_mode))))
    for side, attribute in (("left_pan", "left_split_stereo"), ("right_pan", "right_split_stereo")):
        if given.get(side) is not None:
            actions.append((setattr, (getattr(mixer, attribute), "value", values.parse_pan(given[side]))))
    if crossfader is not None or cue_volume_db is not None:
        if kind != "master":
            raise CommandError("invalid_argument", "crossfader and cue_volume_db exist only on the master track")
        if crossfader is not None:
            actions.append((setattr, (mixer.crossfader, "value", _parse_crossfader(crossfader))))
        if cue_volume_db is not None:
            actions.append((_set_db, (mixer.cue_volume, check_db(cue_volume_db, "cue_volume_db", VOLUME_MAX_DB))))
    for function, arguments in actions:
        function(*arguments)
    return mixer_state(song, owner)


def _parse_crossfader(value):
    """-1 (full A) .. 1 (full B), or a display string such as '50A', '0', '25B'."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip().upper()
        match = re.match(r"^(\d+(?:\.\d+)?)\s*([AB])$", text)
        if text in ("0", "C", "CENTER", "CENTRE"):
            number = 0.0
        elif match:
            number = float(match.group(1)) / 50.0 * (-1 if match.group(2) == "A" else 1)
        else:
            raise CommandError("invalid_argument", "crossfader must be -1..1 or a string like '50A', '0', '25B', got {0!r}".format(value))
    else:
        raise CommandError("invalid_argument", "crossfader must be -1..1, got {0!r}".format(value))
    if not -1.0 <= number <= 1.0:
        raise CommandError("invalid_argument", "crossfader must be within -1..1 (50A..50B), got {0!r}".format(value))
    return number


@command("get_meters", readonly=True)
def get_meters(ctx, tracks=None):
    """Momentary output (and audio input) peak levels of tracks, returns and master, in dBFS."""
    song = ctx.song
    out = {"playing": bool(song.is_playing), "tracks": [meters_state(song, item) for item in _selected_tracks(song, tracks)]}
    if not out["playing"]:
        out["note"] = "Transport is stopped; meters only move while clips or inputs produce sound."
    return out
