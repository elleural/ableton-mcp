"""WS-A: song settings, transport, scenes, locators, grooves and selection (docs/PRD.md 7.2, 7.7, 7.8).

Owned by workstream A.

Live applies a playhead move (Song.current_song_time) on its next tick, and set_or_delete_cue works at
the playhead. Locator edits are therefore two-phase: the first call moves the playhead and answers
{"pending": "playhead", "restore": <old position>}; the caller repeats the call with `restore`, and the
second call toggles the cue and puts the playhead back. transport("play", position) while stopped works
the same way through the start marker ({"pending": "start_marker"}). MCP_Server/tools/song.py runs
those loops (docs/spikes.md).
"""
import re

from .. import refs, values
from ..core import command
from ..errors import CommandError, not_found
from .status import locator_out, number, safe, scene_out, song_settings

DENOMINATORS = (1, 2, 4, 8, 16)
TEMPO_RANGE = (20.0, 999.0)
GROOVE_AMOUNT_MAX = 1.3125  # Live clamps the global groove amount at 131.25 %
PLAYHEAD_TOLERANCE = 1e-3

_SIGNATURE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
_OFF = ("off", "none", "disable", "disabled", "false")


# ---------------------------------------------------------------------------
# Argument parsing (pure; unit-tested offline)
# ---------------------------------------------------------------------------


def parse_signature(value, name="time_signature"):
    """(numerator, denominator) from '3/4' or [3, 4], validated against Live's limits."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        numerator, denominator = value
    elif isinstance(value, str) and _SIGNATURE.match(value):
        numerator, denominator = _SIGNATURE.match(value).groups()
    else:
        raise CommandError("invalid_argument", "{0} must look like '3/4' or '7/8', got {1!r}".format(name, value))
    try:
        numerator, denominator = int(numerator), int(denominator)
    except (TypeError, ValueError):
        raise CommandError("invalid_argument", "{0} must look like '3/4' or '7/8', got {1!r}".format(name, value))
    if not 1 <= numerator <= 99 or denominator not in DENOMINATORS:
        raise CommandError("invalid_argument", "{0} {1!r} is not supported: numerator 1..99, denominator one of 1, 2, 4, 8, 16".format(name, value))
    return numerator, denominator


def parse_tempo(value, name="tempo"):
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            pass
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CommandError("invalid_argument", "{0} must be a number of BPM, got {1!r}".format(name, value))
    if not TEMPO_RANGE[0] <= float(value) <= TEMPO_RANGE[1]:
        raise CommandError("invalid_argument", "{0} {1!r} is outside Live's range 20..999 BPM".format(name, value))
    return float(value)


def parse_flag(value, name):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ("true", "on", "yes", "false", "off", "no"):
        return value.strip().lower() in ("true", "on", "yes")
    raise CommandError("invalid_argument", "{0} must be true or false, got {1!r}".format(name, value))


def parse_amount(value, name, low=0.0, high=1.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= float(value) <= high:
        raise CommandError("invalid_argument", "{0} must be a number from {1:g} to {2:g}, got {3!r}".format(name, low, high, value))
    return float(value)


def split_key(value):
    """'A minor' -> ('A', 'minor'); 'F#' -> ('F#', None); 9 -> (9, None)."""
    if isinstance(value, str) and len(value.strip().split(None, 1)) == 2:
        root, scale = value.strip().split(None, 1)
        return root, scale
    return value, None


def is_off(value):
    return value is False or (isinstance(value, str) and value.strip().lower() in _OFF)


def scale_names():
    """Scale names Live offers, in Live's order (Live.Song.get_all_scales_ordered); None if unavailable."""
    try:
        import Live
        scales = Live.Song.get_all_scales_ordered()
    except Exception:
        return None
    if not isinstance(scales, (tuple, list)):
        return None
    names = []
    for entry in scales:
        names.append(str(entry[0]) if isinstance(entry, (tuple, list)) and entry else str(entry))
    return names


def resolve_scale(name, available):
    """Live's exact spelling of a scale name (case-insensitive); not_found lists every scale."""
    if not isinstance(name, str) or not name.strip():
        raise CommandError("invalid_argument", "scale must be a scale name such as 'Minor' or 'Dorian', got {0!r}".format(name))
    if available is None:
        return name.strip()
    key = name.strip().lower()
    for candidate in available:
        if candidate.lower() == key:
            return candidate
    raise not_found("Scale", name, available)


class _Meter(object):
    """The meter that bar-notation arguments refer to (the new one when set_song changes it)."""

    def __init__(self, numerator, denominator):
        self.signature_numerator = numerator
        self.signature_denominator = denominator


def loop_region(meter, current_start, current_length, loop_start=None, loop_length=None, loop_end=None):
    """(start, length) in beats for the loop arguments; None when none was given."""
    if loop_start is None and loop_length is None and loop_end is None:
        return None
    if loop_length is not None and loop_end is not None:
        raise CommandError("invalid_argument", "Pass loop_length or loop_end, not both")
    start = values.parse_time(meter, loop_start, "loop_start") if loop_start is not None else float(current_start)
    if start < 0:
        raise CommandError("invalid_argument", "loop_start must not be negative")
    if loop_end is not None:
        end = values.parse_time(meter, loop_end, "loop_end")
        if end <= start:
            raise CommandError("invalid_argument", "loop_end ({0:g} beats) must be after loop_start ({1:g} beats)".format(end, start))
        length = end - start
    elif loop_length is not None:
        length = values.parse_length(meter, loop_length, "loop_length")
    else:
        length = float(current_length)
    return start, length


# ---------------------------------------------------------------------------
# set_song
# ---------------------------------------------------------------------------

# set_song flag -> Song attribute
FLAGS = (
    ("scale_mode", "scale_mode"),
    ("metronome", "metronome"),
    ("loop", "loop"),
    ("punch_in", "punch_in"),
    ("punch_out", "punch_out"),
    ("record_mode", "record_mode"),
    ("session_record", "session_record"),
    ("arrangement_overdub", "arrangement_overdub"),
    ("session_automation_record", "session_automation_record"),
    ("link", "is_ableton_link_enabled"),
    ("tempo_follower", "tempo_follower_enabled"),
)


def plan_song_changes(song, scales, tempo=None, time_signature=None, key=None, scale=None, swing=None, groove_amount=None,
                      loop_start=None, loop_length=None, loop_end=None, launch_quantization=None, record_quantization=None,
                      follow=None, **flags):
    """Validate every argument and return [(attribute path, value)] to apply, in order.

    Validation happens before anything changes, so a bad argument leaves the song untouched.
    """
    changes = []
    numerator, denominator = song.signature_numerator, song.signature_denominator
    if time_signature is not None:
        numerator, denominator = parse_signature(time_signature)
        changes += [("signature_numerator", numerator), ("signature_denominator", denominator)]
    if tempo is not None:
        changes.append(("tempo", parse_tempo(tempo)))
    if key is not None:
        root, key_scale = split_key(key)
        changes.append(("root_note", values.parse_root_note(root)))
        if key_scale is not None:
            if scale is not None:
                raise CommandError("invalid_argument", "key {0!r} already names a scale; drop scale or pass key as a root note only".format(key))
            scale = key_scale
    if scale is not None:
        changes.append(("scale_name", resolve_scale(scale, scales)))
    if swing is not None:
        changes.append(("swing_amount", parse_amount(swing, "swing")))
    if groove_amount is not None:
        changes.append(("groove_amount", parse_amount(groove_amount, "groove_amount", 0.0, GROOVE_AMOUNT_MAX)))
    region = loop_region(_Meter(numerator, denominator), song.loop_start, song.loop_length, loop_start, loop_length, loop_end)
    if region is not None:
        changes += [("loop_start", region[0]), ("loop_length", region[1])]
    if launch_quantization is not None:
        changes.append(("clip_trigger_quantization", values.SONG_QUANTIZATION.parse(launch_quantization)))
    if record_quantization is not None:
        changes.append(("midi_recording_quantization", values.RECORD_QUANTIZATION.parse(record_quantization)))
    if follow is not None:
        changes.append(("view.follow_song", parse_flag(follow, "follow")))
    unknown = sorted(set(flags) - set(name for name, _ in FLAGS))
    if unknown:
        raise CommandError("invalid_argument", "Unknown set_song settings: {0}".format(", ".join(unknown)))
    for name, attribute in FLAGS:
        if flags.get(name) is not None:
            changes.append((attribute, parse_flag(flags[name], name)))
    return changes


def apply_change(song, attribute, value):
    owner = song
    parts = attribute.split(".")
    for part in parts[:-1]:
        owner = getattr(owner, part)
    setattr(owner, parts[-1], value)


@command("set_song")
def set_song(ctx, tempo=None, time_signature=None, key=None, scale=None, scale_mode=None, swing=None, groove_amount=None,
             metronome=None, loop=None, loop_start=None, loop_length=None, loop_end=None, punch_in=None, punch_out=None,
             launch_quantization=None, record_quantization=None, follow=None, record_mode=None, session_record=None,
             arrangement_overdub=None, session_automation_record=None, link=None, tempo_follower=None):
    """Change song settings in one undo step; with no arguments, read them.

    Returns every setting. Some (punch_in, punch_out, ...) only read back on Live's next tick, so the
    MCP tool calls again without arguments to verify.
    """
    song = ctx.song
    flags = dict(scale_mode=scale_mode, metronome=metronome, loop=loop, punch_in=punch_in, punch_out=punch_out,
                 record_mode=record_mode, session_record=session_record, arrangement_overdub=arrangement_overdub,
                 session_automation_record=session_automation_record, link=link, tempo_follower=tempo_follower)
    scales = scale_names() if (scale is not None or (key is not None and split_key(key)[1] is not None)) else None
    changes = plan_song_changes(
        song, scales, tempo=tempo, time_signature=time_signature, key=key, scale=scale, swing=swing, groove_amount=groove_amount,
        loop_start=loop_start, loop_length=loop_length, loop_end=loop_end, launch_quantization=launch_quantization,
        record_quantization=record_quantization, follow=follow, **flags)
    for attribute, value in changes:
        try:
            apply_change(song, attribute, value)
        except Exception as error:
            raise CommandError("live_error", "Live rejected {0} = {1!r}: {2}".format(attribute, value, error))
    return song_settings(song)


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

TRANSPORT_ACTIONS = (
    "play", "continue", "stop", "jump", "jump_to_next_locator", "jump_to_prev_locator", "play_selection",
    "stop_all_clips", "back_to_arrangement", "tap_tempo", "capture_midi", "capture_scene",
)
_ACTION_ALIASES = {
    "start": "play", "pause": "stop", "resume": "continue", "next_locator": "jump_to_next_locator",
    "prev_locator": "jump_to_prev_locator", "previous_locator": "jump_to_prev_locator",
    "jump_to_previous_locator": "jump_to_prev_locator", "back_to_arranger": "back_to_arrangement",
    "capture": "capture_midi", "tap": "tap_tempo",
}


def transport_action(action):
    name = str(action or "").strip().lower().replace(" ", "_").replace("-", "_")
    name = _ACTION_ALIASES.get(name, name)
    if name not in TRANSPORT_ACTIONS:
        raise CommandError("invalid_argument", "Unknown transport action {0!r}. Actions: {1}".format(action, ", ".join(TRANSPORT_ACTIONS)))
    return name


def _position(song, position):
    """(beats, cue) for a position: beats, 'bar.beat.sixteenth', or a locator name."""
    if isinstance(position, str):
        key = position.strip().lower()
        for cue in refs.locators(song):
            if str(cue.name).strip().lower() == key:
                return float(cue.time), cue
    try:
        return values.parse_time(song, position, "position"), None
    except CommandError:
        if not isinstance(position, str):
            raise
    cue = refs.locator(song, position)
    return float(cue.time), cue


def _set_playhead(song, beats):
    try:
        song.current_song_time = beats
    except Exception as error:
        raise CommandError("invalid_argument", "Cannot move the playhead to {0:g} beats: {1} (song length {2:g} beats)".format(beats, error, song.song_length))


def _set_start_marker(song, beats):
    """Move the start marker and the shown playhead (what clicking the timeline does while stopped)."""
    try:
        song.start_time = beats
    except Exception as error:
        raise CommandError("invalid_argument", "Cannot move the start marker to {0:g} beats: {1}".format(beats, error))
    _set_playhead(song, beats)


@command("transport")
def transport(ctx, action, position=None):
    """Play, stop, jump and the other transport functions. Live applies them on its next tick.

    play with a position while stopped is two-phase: the first call moves the start marker and answers
    {"pending": "start_marker"}; repeating the call starts playback there. While stopped, jump moves the
    start marker too, because Live's continue_playing ignores a playhead moved while stopped.
    """
    song = ctx.song
    name = transport_action(action)
    out = {"action": name}
    beats = cue = None
    if name in ("play", "jump") and position is not None:
        beats, cue = _position(song, position)
        out["position"] = values.time_out(song, beats)
        if cue is not None:
            out["locator"] = cue.name
    if name == "play":
        if beats is None:
            song.start_playing()
        elif song.is_playing:
            _set_playhead(song, beats)
        elif abs(float(song.start_time) - beats) > PLAYHEAD_TOLERANCE:
            # While stopped, Live starts from the start marker (a current_song_time write is ignored by
            # continue_playing), and applies a marker move on its next tick: the caller repeats the call.
            _set_start_marker(song, beats)
            out["pending"] = "start_marker"
        else:
            song.start_playing()
    elif name == "continue":
        song.continue_playing()
    elif name == "stop":
        song.stop_playing()
    elif name == "jump":
        if beats is None:
            raise CommandError("invalid_argument", "jump needs a position (beats, 'bar.beat.sixteenth' or a locator name)")
        if song.is_playing:
            if cue is not None:
                cue.jump()
            else:
                _set_playhead(song, beats)
        else:
            _set_start_marker(song, beats)
    elif name in ("jump_to_next_locator", "jump_to_prev_locator"):
        forward = name == "jump_to_next_locator"
        if not (song.can_jump_to_next_cue if forward else song.can_jump_to_prev_cue):
            names = ["{0} ({1})".format(cue.name, values.format_time(song, cue.time)) for cue in refs.locators(song)]
            raise CommandError("not_found", "No locator {0} the playhead at {1}. Locators: {2}".format(
                "after" if forward else "before", values.format_time(song, song.current_song_time), ", ".join(names) or "(none)"))
        (song.jump_to_next_cue if forward else song.jump_to_prev_cue)()
    elif name == "play_selection":
        song.play_selection()
    elif name == "stop_all_clips":
        song.stop_all_clips()
    elif name == "back_to_arrangement":
        song.back_to_arranger = False
    elif name == "tap_tempo":
        song.tap_tempo()
    elif name == "capture_midi":
        if not song.can_capture_midi:
            raise CommandError("unsupported", "There is no recently played MIDI to capture", hint="Play some MIDI into an armed or monitored MIDI track first")
        song.capture_midi()
    elif name == "capture_scene":
        before = list(song.scenes)
        song.capture_and_insert_scene()
        created = [scene for scene in song.scenes if refs.index_of(before, scene) is None]
        if created:
            out["scene"] = scene_out(song, created[0])
    return out


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------


def plan_scene_changes(name=None, color=None, tempo=None, time_signature=None):
    """Validate scene arguments; returns [(attribute, value)] where tempo/signature switch themselves on."""
    changes = []
    if name is not None:
        changes.append(("name", str(name)))
    if color is not None:
        changes.append(("color", color))
    if tempo is not None:
        if is_off(tempo):
            changes.append(("tempo_enabled", False))
        else:
            changes += [("tempo_enabled", True), ("tempo", parse_tempo(tempo, "scene tempo"))]
    if time_signature is not None:
        if is_off(time_signature):
            changes.append(("time_signature_enabled", False))
        else:
            numerator, denominator = parse_signature(time_signature)
            changes += [("time_signature_enabled", True), ("time_signature_numerator", numerator), ("time_signature_denominator", denominator)]
    return changes


def apply_scene_changes(scene, changes):
    for attribute, value in changes:
        if attribute == "color":
            values.apply_color(scene, value)
        else:
            setattr(scene, attribute, value)


@command("create_scene")
def create_scene(ctx, index=-1, name=None, color=None, tempo=None, time_signature=None):
    """Insert a scene (at the end by default) with an optional name, colour, tempo and signature."""
    song = ctx.song
    count = len(song.scenes)
    if isinstance(index, bool) or not isinstance(index, int) or not (index == -1 or 0 <= index <= count):
        raise CommandError("invalid_argument", "index must be -1 (end) or 0..{0}, got {1!r}".format(count, index))
    changes = plan_scene_changes(name, color, tempo, time_signature)
    scene = song.create_scene(index)
    apply_scene_changes(scene, changes)
    return scene_out(song, scene, detail=True)


@command("set_scene")
def set_scene(ctx, scene, name=None, color=None, tempo=None, time_signature=None):
    """Rename or recolour a scene, or set or clear ("off") its tempo and time signature."""
    song = ctx.song
    target = refs.scene(song, scene)
    changes = plan_scene_changes(name, color, tempo, time_signature)
    if not changes:
        raise CommandError("invalid_argument", "Nothing to change: pass name, color, tempo or time_signature")
    apply_scene_changes(target, changes)
    return scene_out(song, target, detail=True)


@command("fire_scene")
def fire_scene(ctx, scene, force_legato=False):
    """Launch every clip slot of a scene (and its tempo/signature, if set)."""
    song = ctx.song
    target = refs.scene(song, scene)
    target.fire(bool(force_legato))
    out = scene_out(song, target)
    out["fired"] = True
    return out


@command("delete_scene")
def delete_scene(ctx, scene):
    """Delete a scene and the clips in its slots."""
    song = ctx.song
    target = refs.scene(song, scene)
    scenes = list(song.scenes)
    if len(scenes) <= 1:
        raise CommandError("unsupported", "A Live Set needs at least one scene, so the last scene cannot be deleted")
    position = refs.index_of(scenes, target)
    info = {"scene": position, "name": target.name}
    song.delete_scene(position)
    return {"deleted": info, "scenes": len(song.scenes)}


@command("duplicate_scene")
def duplicate_scene(ctx, scene):
    """Duplicate a scene (with its clips) into a new scene right below it."""
    song = ctx.song
    target = refs.scene(song, scene)
    position = refs.index_of(song.scenes, target)
    song.duplicate_scene(position)
    out = scene_out(song, list(song.scenes)[position + 1], position + 1, detail=True)
    out["source"] = position
    return out


# ---------------------------------------------------------------------------
# Locators (two-phase: see the module docstring)
# ---------------------------------------------------------------------------


def _require_stopped(song, what):
    if song.is_playing:
        raise CommandError("busy", "Stop the transport before {0}: Live edits locators at the moving playhead".format(what), hint="transport('stop') first")


def _playhead_pending(song, beats, restore):
    """Phase 1: move the playhead; Live applies it on the next tick."""
    original = float(song.current_song_time) if restore is None else float(restore)
    _set_playhead(song, beats)
    return {"pending": "playhead", "restore": original}


def _restore_playhead(song, restore):
    if restore is not None:
        try:
            song.current_song_time = float(restore)
        except Exception:
            pass


def _at_playhead(song, beats):
    return abs(float(song.current_song_time) - float(beats)) <= PLAYHEAD_TOLERANCE


@command("create_locator")
def create_locator(ctx, time, name=None, restore=None):
    """Create a locator (cue point) at a time. Two-phase; see the module docstring."""
    song = ctx.song
    beats = values.parse_time(song, time)
    if beats < 0:
        raise CommandError("invalid_argument", "time must not be negative")
    _require_stopped(song, "creating a locator")
    for cue in refs.locators(song):
        if abs(cue.time - beats) <= PLAYHEAD_TOLERANCE:
            _restore_playhead(song, restore)
            raise CommandError("invalid_argument", "Locator {0!r} already exists at {1}".format(cue.name, values.format_time(song, cue.time)), hint="Use set_locator to rename it")
    if not _at_playhead(song, beats):
        return _playhead_pending(song, beats, restore)
    if song.is_cue_point_selected():
        _restore_playhead(song, restore)
        raise CommandError("invalid_argument", "A locator already sits at {0} (Live snaps locators to the grid)".format(values.format_time(song, beats)), hint="Use set_locator to rename it, or pick another time")
    before = list(song.cue_points)
    song.set_or_delete_cue()
    created = [cue for cue in song.cue_points if refs.index_of(before, cue) is None]
    _restore_playhead(song, restore)
    if len(created) != 1:
        raise CommandError("live_error", "Live did not create exactly one locator ({0} new)".format(len(created)))
    cue = created[0]
    if name is not None:
        cue.name = str(name)
    out = locator_out(song, cue)
    if abs(cue.time - beats) > PLAYHEAD_TOLERANCE:
        out["requested"] = values.time_out(song, beats)
    return out


@command("set_locator")
def set_locator(ctx, locator, name):
    """Rename a locator (addressed by index in time order, or by name)."""
    song = ctx.song
    cue = refs.locator(song, locator)
    cue.name = str(name)
    return locator_out(song, cue)


@command("delete_locator")
def delete_locator(ctx, locator, restore=None):
    """Delete a locator. Two-phase; see the module docstring."""
    song = ctx.song
    cue = refs.locator(song, locator)
    _require_stopped(song, "deleting a locator")
    if not _at_playhead(song, cue.time):
        return _playhead_pending(song, cue.time, restore)
    if not song.is_cue_point_selected():
        _restore_playhead(song, restore)
        raise CommandError("live_error", "Live does not see locator {0!r} at the playhead; try again".format(cue.name))
    info = locator_out(song, cue)
    before = refs.locators(song)
    song.set_or_delete_cue()
    remaining = refs.locators(song)
    _restore_playhead(song, restore)
    gone = [item for item in before if refs.index_of(remaining, item) is None]
    if len(gone) != 1 or not refs.same(gone[0], cue):
        raise CommandError("live_error", "Deleting locator {0!r} removed {1} locator(s)".format(info["name"], len(gone)))
    return {"deleted": info, "locators": len(remaining)}


# ---------------------------------------------------------------------------
# Grooves
# ---------------------------------------------------------------------------


def groove_out(groove, position):
    return {
        "groove": position,
        "name": groove.name,
        "base": values.GROOVE_BASE.name(groove.base),
        "quantize": number(groove.quantization_amount, 3),
        "timing": number(groove.timing_amount, 3),
        "random": number(groove.random_amount, 3),
        "velocity": number(groove.velocity_amount, 3),
    }


@command("get_grooves", readonly=True)
def get_grooves(ctx):
    """The groove pool with each groove's settings, plus the global groove amount."""
    song = ctx.song
    grooves = list(song.groove_pool.grooves)
    return {"groove_amount": number(song.groove_amount, 3), "grooves": [groove_out(groove, position) for position, groove in enumerate(grooves)]}


# set_groove argument -> (Groove attribute, low, high); Live stores groove amounts in percent.
GROOVE_AMOUNTS = (
    ("quantize", "quantization_amount", 0.0, 100.0),
    ("timing", "timing_amount", 0.0, 100.0),
    ("random", "random_amount", 0.0, 100.0),
    ("velocity", "velocity_amount", -100.0, 100.0),
)


@command("set_groove")
def set_groove(ctx, groove, name=None, base=None, quantize=None, random=None, timing=None, velocity=None):
    """Change a groove's name, base grid and amounts (percent: quantize/timing/random 0..100, velocity -100..100)."""
    song = ctx.song
    target = refs.groove(song, groove)
    given = {"quantize": quantize, "random": random, "timing": timing, "velocity": velocity}
    changes = []
    if name is not None:
        changes.append(("name", str(name)))
    if base is not None:
        changes.append(("base", values.GROOVE_BASE.parse(base)))
    for argument, attribute, low, high in GROOVE_AMOUNTS:
        if given[argument] is not None:
            changes.append((attribute, parse_amount(given[argument], argument, low, high)))
    if not changes:
        raise CommandError("invalid_argument", "Nothing to change: pass name, base, quantize, random, timing or velocity")
    for attribute, value in changes:
        setattr(target, attribute, value)
    return groove_out(target, refs.index_of(song.groove_pool.grooves, target))


# ---------------------------------------------------------------------------
# Selection and feedback
# ---------------------------------------------------------------------------

VIEW_ALIASES = {
    "session": "Session", "arranger": "Arranger", "arrangement": "Arranger", "detail": "Detail",
    "clip": "Detail/Clip", "detail/clip": "Detail/Clip", "device": "Detail/DeviceChain",
    "devices": "Detail/DeviceChain", "device_chain": "Detail/DeviceChain", "devicechain": "Detail/DeviceChain",
    "detail/devicechain": "Detail/DeviceChain", "browser": "Browser",
}


def view_name(view, available=None):
    """Live's view identifier for a view name or alias ('arrangement' -> 'Arranger')."""
    key = str(view or "").strip().lower().replace(" ", "_")
    resolved = VIEW_ALIASES.get(key)
    if resolved is None and available:
        for candidate in available:
            if candidate.lower() == key:
                resolved = candidate
    if resolved is None or (available and resolved not in available):
        options = list(available) if available else sorted(set(VIEW_ALIASES.values()))
        raise CommandError("invalid_argument", "Unknown view {0!r}. Views: {1}".format(view, ", ".join(options)))
    return resolved


def selection_state(song, app):
    view = song.view
    out = {}
    track = safe(lambda: view.selected_track)
    if track is not None:
        out["track"] = refs.track_label(song, track)
        device = safe(lambda: track.view.selected_device)
        if device is not None:
            path = safe(lambda: refs.device_path(device), {})
            out["device"] = dict({"name": device.name}, **path)
    scene = safe(lambda: view.selected_scene)
    if scene is not None:
        out["scene"] = {"scene": refs.index_of(song.scenes, scene), "name": scene.name}
    slot = safe(lambda: view.highlighted_clip_slot)
    if slot is not None:
        owner = safe(lambda: slot.canonical_parent)
        if owner is not None:
            out["slot"] = {"track": refs.track_ref(song, owner), "slot": refs.index_of(owner.clip_slots, slot)}
    clip = safe(lambda: view.detail_clip)
    if clip is not None:
        out["detail_clip"] = dict({"name": clip.name}, **safe(lambda: refs.clip_ref(song, clip), {}))
    app_view = app.view
    out["view"] = safe(lambda: str(app_view.focused_document_view))
    available = safe(lambda: list(app_view.available_main_views()), [])
    out["visible_views"] = [name for name in available if safe(lambda name=name: app_view.is_view_visible(name), False)]
    return out


def _refuse_during_bounce(ctx):
    """Selecting or loading during a real-time bounce can arm a user track, which would record over it."""
    job = ctx.state.get("bounce")
    if isinstance(job, dict) and job.get("phase") in ("route", "arm", "go", "starting", "recording", "finalizing", "verifying", "aborting"):
        raise CommandError("busy", "A bounce is recording; selection and browser loads wait until get_bounce_status reports it done")


@command("select", undo=False)
def select(ctx, track=None, scene=None, device=None, slot=None, view=None):
    """Select a track, scene, clip slot or device and show/focus a view; no arguments reads the selection."""
    if any(value is not None for value in (track, scene, device, slot, view)):
        _refuse_during_bounce(ctx)
    song, app = ctx.song, ctx.app
    if (device is not None or slot is not None) and track is None:
        raise CommandError("invalid_argument", "device and slot need a track")
    if slot is not None and scene is not None:
        raise CommandError("invalid_argument", "Pass slot or scene, not both: a slot is the track's cell in that scene, so selecting it selects its scene")
    focus = None
    if view is not None:
        focus = view_name(view, safe(lambda: list(app.view.available_main_views())))
    owner = refs.track(song, track) if track is not None else None
    scene_obj = refs.scene(song, scene) if scene is not None else None
    slot_obj = refs.clip_slot(song, track, slot) if slot is not None else None
    device_obj = refs.device(song, track, device)[0] if device is not None else None
    if owner is not None:
        song.view.selected_track = owner
    if scene_obj is not None:
        song.view.selected_scene = scene_obj
    if slot_obj is not None:
        song.view.highlighted_clip_slot = slot_obj
        if slot_obj.has_clip:
            song.view.detail_clip = slot_obj.clip
    if device_obj is not None:
        song.view.select_device(device_obj)
    if focus is not None:
        app.view.focus_view(focus)
    return selection_state(song, app)


@command("show_message", readonly=True)
def show_message(ctx, text):
    """Show text in Live's status bar."""
    text = str(text)
    ctx.show_message(text)
    return {"shown": text}
