"""Resolve the references tools pass (tracks, clips, devices, parameters, ...) to Live objects.

Addressing contract (docs/PRD.md section 8):
- track: int = regular track index; "master"; "return:<letter|index|name>"; or a case-insensitive
  exact name of a regular or return track.
- device: int index, name, or a path alternating device and chain segments, either as a list
  ([0, 1, 0]) or a string ("Drum Rack/Kick/Simpler"). Chain segments accept an index, a chain name,
  or a drum note ("C1", "note:36").
- parameter: int index or name; with no device, mixer names ("volume", "pan", "send:A", ...).
- scene / locator / groove: int index or name.
Every resolver raises CommandError with the valid options when a reference does not resolve.
"""
import re

from . import values
from .errors import CommandError, not_found

_INT = re.compile(r"^\s*-?\d+\s*$")


def _int_like(ref):
    if isinstance(ref, bool):
        return None
    if isinstance(ref, int):
        return ref
    if isinstance(ref, float) and ref.is_integer():
        return int(ref)
    if isinstance(ref, str) and _INT.match(ref):
        return int(ref)
    return None


def _key(text):
    return str(text).strip().lower()


def same(first, second):
    """True when two Live object wrappers refer to the same underlying object."""
    if first is None or second is None:
        return first is second
    pointer_a = getattr(first, "_live_ptr", None)
    pointer_b = getattr(second, "_live_ptr", None)
    if pointer_a is not None and pointer_b is not None:
        return pointer_a == pointer_b
    return first == second


def index_of(sequence, obj):
    for position, item in enumerate(sequence):
        if same(item, obj):
            return position
    return None


def _pick_index(items, index, what, context=""):
    count = len(items)
    if -count <= index < count:
        return items[index]
    span = "none exist" if count == 0 else "valid: 0..{0}".format(count - 1)
    raise CommandError("not_found", "{0} index {1} is out of range{2} ({3})".format(what, index, context, span))


def _pick_named(items, ref, what, label=lambda item: item.name, extra_keys=()):
    """Find exactly one item whose name matches ref (exact, then extra keys, then unique substring)."""
    key = _key(ref)
    exact = [item for item in items if _key(label(item)) == key]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise CommandError("invalid_argument", "{0} name {1!r} is ambiguous ({2} matches); use an index".format(what, ref, len(exact)))
    for extra in extra_keys:
        matches = []
        for item in items:
            try:
                if _key(extra(item)) == key:
                    matches.append(item)
            except Exception:
                pass
        if len(matches) == 1:
            return matches[0]
    partial = [item for item in items if key and key in _key(label(item))]
    if len(partial) == 1:
        return partial[0]
    raise not_found(what, ref, ["{0}: {1}".format(position, label(item)) for position, item in enumerate(items)])


# ---------------------------------------------------------------------------
# Tracks
# ---------------------------------------------------------------------------


def return_letter(index):
    return chr(ord("A") + index) if 0 <= index < 26 else str(index)


_RETURN_PREFIX = re.compile(r"^[A-Z]-")


def return_bare_name(name):
    """Live names return tracks with their letter prefix ("A-Reverb"); this strips it ("Reverb")."""
    return _RETURN_PREFIX.sub("", str(name))


def _return_index_from_letter(text):
    text = text.strip()
    if len(text) == 1 and text.isalpha():
        return ord(text.upper()) - ord("A")
    return None


def track_kind(song, track):
    if same(track, song.master_track):
        return "master"
    if index_of(song.return_tracks, track) is not None:
        return "return"
    if getattr(track, "is_foldable", False):
        return "group"
    return "midi" if track.has_midi_input else "audio"


def track_ref(song, track):
    """Canonical reference for a track: index, 'return:A' or 'master'."""
    position = index_of(song.tracks, track)
    if position is not None:
        return position
    position = index_of(song.return_tracks, track)
    if position is not None:
        return "return:" + return_letter(position)
    if same(track, song.master_track):
        return "master"
    return None


def track_label(song, track):
    """{'track': ref, 'name': ..., 'kind': ...} for outputs."""
    return {"track": track_ref(song, track), "name": track.name, "kind": track_kind(song, track)}


def _track_names(song):
    names = ["{0}: {1}".format(position, track.name) for position, track in enumerate(song.tracks)]
    names += ["return:{0}: {1}".format(return_letter(position), track.name) for position, track in enumerate(song.return_tracks)]
    return names + ["master"]


def _return_track(song, text, original):
    returns = list(song.return_tracks)
    position = _int_like(text)
    if position is None:
        position = _return_index_from_letter(text)
    if position is not None:
        return _pick_index(returns, position, "Return track")
    return _pick_named(returns, text, "Return track", extra_keys=(lambda item: return_bare_name(item.name),))


def track(song, ref):
    """Resolve a track reference to a Track."""
    if ref is None:
        raise CommandError("invalid_argument", "A track is required (index, name, 'return:A' or 'master')")
    position = _int_like(ref)
    if position is not None:
        tracks = list(song.tracks)
        if -len(tracks) <= position < len(tracks):
            return tracks[position]
        raise CommandError(
            "not_found",
            "Track index {0} is out of range: the set has {1} regular tracks (0..{2}). "
            "Use 'return:A' or 'master' for return and master tracks.".format(position, len(tracks), len(tracks) - 1),
        )
    if not isinstance(ref, str):
        raise CommandError("invalid_argument", "track must be an index or a name, got {0!r}".format(ref))
    key = _key(ref)
    if key in ("master", "main"):
        return song.master_track
    for prefix in ("return:", "return "):
        if key.startswith(prefix):
            return _return_track(song, ref.strip()[len(prefix):], ref)
    regular, returns = list(song.tracks), list(song.return_tracks)
    exact = [item for item in regular + returns if _key(item.name) == key]
    if not exact:
        exact = [item for item in returns if _key(return_bare_name(item.name)) == key]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise CommandError("invalid_argument", "Track name {0!r} is ambiguous ({1} tracks share it); use the track index".format(ref, len(exact)))
    raise not_found("Track", ref, _track_names(song))


def tracks(song, refs=None):
    """Resolve a list of track references; None means all regular tracks."""
    if refs is None:
        return list(song.tracks)
    if not isinstance(refs, (list, tuple)):
        refs = [refs]
    return [track(song, ref) for ref in refs]


# ---------------------------------------------------------------------------
# Scenes, locators, grooves
# ---------------------------------------------------------------------------


def scene(song, ref):
    scenes = list(song.scenes)
    position = _int_like(ref)
    if position is not None:
        return _pick_index(scenes, position, "Scene")
    return _pick_named(scenes, ref, "Scene")


def locators(song):
    """Cue points sorted by time (the order every tool uses for locator indices)."""
    return sorted(list(song.cue_points), key=lambda cue: cue.time)


def locator(song, ref):
    cues = locators(song)
    position = _int_like(ref)
    if position is not None:
        return _pick_index(cues, position, "Locator")
    return _pick_named(cues, ref, "Locator")


def groove(song, ref):
    grooves = list(song.groove_pool.grooves)
    position = _int_like(ref)
    if position is not None:
        return _pick_index(grooves, position, "Groove")
    return _pick_named(grooves, ref, "Groove")


# ---------------------------------------------------------------------------
# Clip slots and clips
# ---------------------------------------------------------------------------


def clip_slot(song, track_ref_value, slot):
    owner = track(song, track_ref_value)
    slots = list(owner.clip_slots)
    if not slots:
        raise CommandError("unsupported", "Track '{0}' has no clip slots (return and master tracks have none)".format(owner.name))
    position = _int_like(slot)
    if position is None:
        raise CommandError("invalid_argument", "slot must be a scene index, got {0!r}".format(slot))
    return _pick_index(slots, position, "Slot", " for track '{0}'".format(owner.name))


def arrangement_clips(owner):
    """A track's arrangement clips sorted by start time (the order arrangement_clip indexes)."""
    return sorted(list(owner.arrangement_clips), key=lambda clip_item: clip_item.start_time)


def clip(song, track_ref_value, slot=None, arrangement_clip=None):
    """Resolve a clip by Session slot or by arrangement clip index (exactly one)."""
    if (slot is None) == (arrangement_clip is None):
        raise CommandError("invalid_argument", "Pass exactly one of slot (Session scene index) or arrangement_clip (index in the track's arrangement clips)")
    if slot is not None:
        holder = clip_slot(song, track_ref_value, slot)
        if not holder.has_clip:
            raise CommandError("not_found", "Slot {0} of track '{1}' is empty".format(slot, track(song, track_ref_value).name))
        return holder.clip
    owner = track(song, track_ref_value)
    position = _int_like(arrangement_clip)
    if position is None:
        raise CommandError("invalid_argument", "arrangement_clip must be an index, got {0!r}".format(arrangement_clip))
    return _pick_index(arrangement_clips(owner), position, "Arrangement clip", " on track '{0}'".format(owner.name))


def clip_ref(song, clip_obj):
    """{'track': ref, 'slot': n} or {'track': ref, 'arrangement_clip': n} for a clip."""
    parent = clip_obj.canonical_parent
    if clip_obj.is_arrangement_clip:
        owner = parent
        while owner is not None and not hasattr(owner, "arrangement_clips"):
            owner = owner.canonical_parent
        return {"track": track_ref(song, owner), "arrangement_clip": index_of(arrangement_clips(owner), clip_obj)}
    owner = parent.canonical_parent
    return {"track": track_ref(song, owner), "slot": index_of(owner.clip_slots, parent)}


# ---------------------------------------------------------------------------
# Devices and chains
# ---------------------------------------------------------------------------


def _segments(ref):
    if isinstance(ref, (list, tuple)):
        return list(ref)
    if isinstance(ref, str) and "/" in ref:
        return [segment.strip() for segment in ref.split("/")]
    return [ref]


def _pick_device(devices, ref, where):
    position = _int_like(ref)
    if position is not None:
        return _pick_index(devices, position, "Device", " in '{0}'".format(where))
    return _pick_named(devices, ref, "Device", extra_keys=(lambda item: item.class_display_name, lambda item: item.class_name))


def chain(rack, ref):
    """Resolve a chain of a rack by index, name, or drum note ('C1', 'note:36')."""
    if not rack.can_have_chains:
        raise CommandError("invalid_argument", "Device '{0}' is not a rack, so it has no chains".format(rack.name))
    chains = list(rack.chains)
    if isinstance(ref, str) and rack.can_have_drum_pads:
        text = ref.strip()
        note_text = text[5:] if text.lower().startswith("note:") else text
        is_note = text.lower().startswith("note:") or bool(values._NOTE.match(text))
        if is_note:
            note = values.parse_pitch(note_text, "drum note")
            for item in chains:
                if getattr(item, "in_note", None) == note:
                    return item
            raise not_found("Drum chain for note", text, ["{0} ({1})".format(item.name, values.pitch_name(item.in_note)) for item in chains])
    position = _int_like(ref)
    if position is not None:
        return _pick_index(chains, position, "Chain", " in '{0}'".format(rack.name))
    return _pick_named(chains, ref, "Chain")


def device(song, track_ref_value, device_ref):
    """Resolve a device reference. Returns (device, container, index_in_container)."""
    if device_ref is None:
        raise CommandError("invalid_argument", "A device is required (index, name or rack path like 'Drum Rack/Kick/Simpler')")
    owner = track(song, track_ref_value)
    segments = _segments(device_ref)
    if len(segments) % 2 == 0:
        raise CommandError("invalid_argument", "Device path {0!r} must alternate device and chain segments and end with a device".format(device_ref))
    container = owner
    current = _pick_device(list(container.devices), segments[0], owner.name)
    for position in range(1, len(segments), 2):
        container = chain(current, segments[position])
        current = _pick_device(list(container.devices), segments[position + 1], container.name)
    return current, container, index_of(container.devices, current)


def device_path(device_obj):
    """Index path ('0/1/2') and name path ('Rack/Chain/Device') of a device within its track.

    Walks up the parents: a device lives in a Track (which has clip_slots) or in a rack Chain,
    whose rack (possibly behind a DrumPad) lives in turn in a Track or Chain.
    """
    indices, names = [], []
    node = device_obj
    while True:
        container = node.canonical_parent
        indices.insert(0, index_of(container.devices, node))
        names.insert(0, node.name)
        if hasattr(container, "clip_slots"):
            break
        rack = container.canonical_parent
        while rack is not None and not hasattr(rack, "chains"):
            rack = rack.canonical_parent
        if rack is None:
            break
        indices.insert(0, index_of(rack.chains, container))
        names.insert(0, container.name)
        node = rack
    return {"path": "/".join(str(item) for item in indices), "name_path": "/".join(names)}


_NATIVE_DEVICES = {}


def native_device_names(app):
    """{category: [names]} of native Live devices, as Track.insert_device spells them (cached)."""
    if not _NATIVE_DEVICES:
        # Packs add Max for Live devices to these categories (source = the pack's name, e.g.
        # "Creative Extensions"); insert_device rejects them, so keep only built-in devices.
        # Comparing against installed pack names stays correct if Live localises "Built-in".
        packs = set(item.name for item in app.browser.packs.children) - {"Core Library"}
        for category in ("instruments", "audio_effects", "midi_effects"):
            _NATIVE_DEVICES[category] = [
                item.name for item in getattr(app.browser, category).children
                if item.is_device and (item.source == "Built-in" or item.source not in packs)
            ]
    return _NATIVE_DEVICES


def native_device_name(app, name):
    """The exact insert_device name for a case-insensitive device name ("eq eight" -> "EQ Eight").

    Raises not_found listing close matches (or every native device) when the name is not native;
    pack and Max for Live devices must be loaded through the browser instead.
    """
    key = _key(name)
    everything = []
    for names in native_device_names(app).values():
        for candidate in names:
            if _key(candidate) == key:
                return candidate
            everything.append(candidate)
    close = [candidate for candidate in everything if key in _key(candidate) or _key(candidate) in key]
    error = not_found("Native device", name, close or everything)
    error.hint = "Pack and Max for Live devices are not native: load them with search_browser / load_from_browser."
    return _raise(error)


def _raise(error):
    raise error


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

_MIXER_NAMES = "volume, pan, send:A (letter, index or return name), activator, crossfader, cue_volume, tempo, left_pan, right_pan"


def send_index(song, ref):
    returns = list(song.return_tracks)
    position = _int_like(ref)
    if position is None and isinstance(ref, str):
        position = _return_index_from_letter(ref)
    if position is None:
        target = _pick_named(returns, ref, "Return track")
        position = index_of(returns, target)
    if not 0 <= position < len(returns):
        raise not_found("Send", ref, [return_letter(index) for index in range(len(returns))])
    return position


def mixer_parameter(song, owner, ref):
    """A mixer DeviceParameter of a track by name: volume, pan, send:A, activator, ..."""
    mixer = owner.mixer_device
    key = _key(ref)
    if key in ("volume", "vol", "gain"):
        return mixer.volume
    if key in ("pan", "panning"):
        return mixer.panning
    if key in ("activator", "track_activator", "on", "speaker"):
        return mixer.track_activator
    if key in ("left_pan", "left_split_stereo"):
        return mixer.left_split_stereo
    if key in ("right_pan", "right_split_stereo"):
        return mixer.right_split_stereo
    if key in ("crossfader", "cue_volume", "tempo", "song_tempo"):
        if not same(owner, song.master_track):
            raise CommandError("invalid_argument", "'{0}' exists only on the master track".format(ref))
        attribute = {"tempo": "song_tempo"}.get(key, key)
        return getattr(mixer, attribute)
    if key.startswith("send"):
        target = str(ref).strip()[4:].lstrip(":").strip()
        sends = list(mixer.sends)
        position = send_index(song, target)
        if position >= len(sends):
            raise CommandError("not_found", "Track '{0}' has no send {1}".format(owner.name, target))
        return sends[position]
    raise not_found("Mixer parameter", ref, _MIXER_NAMES.split(", "))


def parameter(device_obj, ref):
    """A device's DeviceParameter by index or name (exact, original name, unique substring)."""
    parameters = list(device_obj.parameters)
    position = _int_like(ref)
    if position is not None:
        return _pick_index(parameters, position, "Parameter", " of '{0}'".format(device_obj.name))
    return _pick_named(parameters, ref, "Parameter of '{0}'".format(device_obj.name), extra_keys=(lambda item: item.original_name,))


def resolve_parameter(song, track_ref_value, device_ref, parameter_ref):
    """Parameter on a device, or on the track mixer when device_ref is None."""
    owner = track(song, track_ref_value)
    if device_ref is None:
        return mixer_parameter(song, owner, parameter_ref)
    device_obj, _, _ = device(song, track_ref_value, device_ref)
    return parameter(device_obj, parameter_ref)
