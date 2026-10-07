"""WS-C: clips, notes, drum patterns and clip actions (docs/PRD.md section 7.5). Owned by workstream C.

A clip is addressed by `track` plus exactly one of `slot` (Session scene index) or `arrangement_clip`
(index into the track's arrangement clips sorted by start time, see refs.arrangement_clips).

Times inside a clip are clip beats in the clip's own meter: "1.1.1" is clip beat 0 (Live's 1.1.1),
whatever the start marker. Unwarped audio clips measure loop and marker positions in seconds.

The note helpers below (normalisation, filters, transforms, gain mapping, drum resolution) work on
plain dicts and numbers so they are unit-tested offline (tests/unit/test_clips_*.py).
"""
import bisect
import math
import os
import random as _random
import re
import time

from .. import refs, values
from ..core import command
from ..errors import CommandError, not_found

DEFAULT_NOTE_LIMIT = 200
MAX_NOTE_LIMIT = 10000
MAX_ARRANGEMENT_TIME = 1576800.0  # Track.create_midi_clip accepts [0, 1576800] beats
EPS = 1e-6
NOTE_DEFAULTS = {"velocity": 100.0, "probability": 1.0, "velocity_deviation": 0.0, "release_velocity": 64.0, "mute": False}
_NOTE_KEYS = ("pitch", "pitches", "start", "duration", "velocity", "probability", "velocity_deviation", "release_velocity", "mute")
_EDIT_KEYS = ("note_id", "pitch", "start", "duration", "velocity", "probability", "velocity_deviation", "release_velocity", "mute")


# ---------------------------------------------------------------------------
# Small validators
# ---------------------------------------------------------------------------


def _number(value, name, low=None, high=None, integer=False):
    """A finite number (numeric strings accepted) within [low, high]."""
    if isinstance(value, bool):
        raise CommandError("invalid_argument", "{0} must be a number, not a boolean".format(name))
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            raise CommandError("invalid_argument", "{0} must be a number, got {1!r}".format(name, value))
    if not isinstance(value, (int, float)) or math.isnan(value) or math.isinf(value):
        raise CommandError("invalid_argument", "{0} must be a finite number, got {1!r}".format(name, value))
    if integer:
        if float(value) != int(value):
            raise CommandError("invalid_argument", "{0} must be a whole number, got {1!r}".format(name, value))
        value = int(value)
    if (low is not None and value < low) or (high is not None and value > high):
        raise CommandError("invalid_argument", "{0} must be within {1:g}..{2:g}, got {3!r}".format(
            name, low if low is not None else float("-inf"), high if high is not None else float("inf"), value))
    return value


def _flag(value, name):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ("true", "false", "on", "off", "1", "0", "yes", "no"):
        return value.strip().lower() in ("true", "on", "1", "yes")
    raise CommandError("invalid_argument", "{0} must be true or false, got {1!r}".format(name, value))


def _choice(value, options, name):
    text = str(value).strip().lower()
    if text not in options:
        raise CommandError("invalid_argument", "{0} must be one of: {1} (got {2!r})".format(name, ", ".join(options), value))
    return text


def _as_list(value):
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _r(value):
    """Compact JSON number: rounded to 6 decimals, integral values as ints."""
    value = round(float(value), 6)
    return int(value) if value.is_integer() else value


# ---------------------------------------------------------------------------
# Musical units inside a clip
# ---------------------------------------------------------------------------

_NOTE_VALUE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*([tT.]?)\s*$")


def note_value_beats(text):
    """Beats of a note value: '1/16' -> 0.25, '1/8T' -> 1/3, '1/4.' -> 1.5; None if text is not one."""
    match = _NOTE_VALUE.match(text) if isinstance(text, str) else None
    if not match:
        return None
    numerator, denominator, modifier = int(match.group(1)), int(match.group(2)), match.group(3)
    if numerator <= 0 or denominator <= 0:
        return None
    beats = 4.0 * numerator / denominator
    if modifier in ("t", "T"):
        beats *= 2.0 / 3.0
    elif modifier == ".":
        beats *= 1.5
    return beats


def parse_length(meter, value, name="length"):
    """Beats for a length: a number, 'N bars' / 'N beats' (in `meter`), or a note value ('1/8', '1/16T', '1/4.')."""
    beats = note_value_beats(value)
    if beats is not None:
        return beats
    return values.parse_length(meter, value, name)


def parse_grid(meter, value, name="grid"):
    """Quantize grid in beats: '1/16', '1/8T', '1/4.', '1 bar', or a number of beats."""
    if value is None:
        raise CommandError("invalid_argument", "{0} is required, e.g. '1/16', '1/8T' or '1 bar'".format(name))
    grid = parse_length(meter, value, name)
    if grid <= 0:
        raise CommandError("invalid_argument", "{0} must be positive".format(name))
    return grid


def parse_clip_time(meter, value, name):
    """Clip beats for a number or a 'bar.beat.sixteenth' string in the clip's meter (1.1.1 = 0)."""
    return values.parse_time(meter, value, name)


def parse_timing(value, tempo, name="timing"):
    """Beats for a timing amount: a number of beats, or milliseconds as '10ms' (at `tempo` BPM)."""
    if isinstance(value, str):
        match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*ms\s*$", value, re.IGNORECASE)
        if match:
            return float(match.group(1)) / 1000.0 * tempo / 60.0
        match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:beats?)?\s*$", value, re.IGNORECASE)
        if match:
            return float(match.group(1))
        raise CommandError("invalid_argument", "{0} must be beats (0.05) or milliseconds ('10ms'), got {1!r}".format(name, value))
    return _number(value, name, 0)


# ---------------------------------------------------------------------------
# Clips: resolution and description
# ---------------------------------------------------------------------------


def owner_track(clip):
    """The Track that holds a clip (Session or arrangement)."""
    if clip.is_arrangement_clip:
        node = clip.canonical_parent
        while node is not None and not hasattr(node, "clip_slots"):
            node = node.canonical_parent
        return node
    return clip.canonical_parent.canonical_parent


def _clip(song, track, slot, arrangement_clip):
    return refs.clip(song, track, slot, arrangement_clip)


def _midi_clip(song, track, slot, arrangement_clip, what):
    clip = _clip(song, track, slot, arrangement_clip)
    if not clip.is_midi_clip:
        raise CommandError("unsupported", "Clip '{0}' is an audio clip; {1} needs a MIDI clip".format(clip.name, what))
    return clip


def _require_audio(clip, what):
    if not clip.is_audio_clip:
        raise CommandError("unsupported", "{0} applies to audio clips; '{1}' is a MIDI clip".format(what, clip.name))


def _require_clip_track(song, owner):
    kind = refs.track_kind(song, owner)
    if kind in ("return", "master"):
        raise CommandError("unsupported", "'{0}' is a {1} track; clips live on MIDI and audio tracks".format(owner.name, kind))
    if kind == "group":
        raise CommandError("unsupported", "'{0}' is a group track; it holds no clips of its own".format(owner.name))
    return kind


def clip_label(song, clip):
    """{'track', 'track_name', 'slot' | 'arrangement_clip', 'name'} for outputs."""
    out = refs.clip_ref(song, clip)
    out["track_name"] = owner_track(clip).name
    out["name"] = clip.name
    return out


def _unwarped(clip):
    return bool(clip.is_audio_clip and not clip.warping)


def play_region(clip):
    """(start, end) clip time that plays: the loop when looping, otherwise the markers."""
    if clip.looping:
        return float(clip.loop_start), float(clip.loop_end)
    return float(clip.start_marker), float(clip.end_marker)


def _gain_db_out(clip):
    shown = values.parse_display_number(clip.gain_display_string)
    if shown is None:
        return None
    return "-inf" if math.isinf(shown) else shown


def _envelopes(clip):
    out = []
    try:
        envelopes = list(clip.automation_envelopes)
    except Exception:
        return out
    for envelope in envelopes:
        parameter = envelope.parameter
        if parameter is None:
            continue
        holder = parameter.canonical_parent
        device = "Mixer" if type(holder).__name__ == "MixerDevice" else getattr(holder, "name", None)
        out.append({"parameter": parameter.name, "device": device})
    return out


def _warp_markers(clip, limit=64):
    markers = [{"beat": _r(marker.beat_time), "seconds": _r(marker.sample_time)} for marker in clip.warp_markers]
    return markers[:limit], len(markers)


def _state(clip):
    if clip.is_recording:
        return "recording"
    if clip.is_playing:
        return "playing"
    if clip.is_triggered:
        return "triggered"
    return "stopped"


def clip_info(song, clip, notes=False, limit=DEFAULT_NOTE_LIMIT):
    """Everything about a clip, compactly (get_clip and the result of every clip mutation)."""
    out = clip_label(song, clip)
    audio = bool(clip.is_audio_clip)
    unwarped = _unwarped(clip)
    out["kind"] = "audio" if audio else "midi"
    out.update(values.color_out(clip))
    out["time_unit"] = "seconds" if unwarped else "beats"
    if unwarped:
        out["length"] = _r(clip.end_marker - clip.start_marker)  # Clip.length is meaningless for unwarped audio
    else:
        out["length"] = _r(clip.length)
        out["bars"] = _r(clip.length / values.bar_length(clip))
    out["looping"] = bool(clip.looping)
    if clip.looping:
        out["loop"] = {"start": _r(clip.loop_start), "end": _r(clip.loop_end)}
    out["markers"] = {"start": _r(clip.start_marker), "end": _r(clip.end_marker)}
    out["signature"] = "{0}/{1}".format(clip.signature_numerator, clip.signature_denominator)
    if clip.is_arrangement_clip:
        out["start"] = values.time_out(song, clip.start_time)
        out["end"] = values.time_out(song, clip.end_time)
    else:
        out["launch_mode"] = values.LAUNCH_MODE.name(clip.launch_mode)
        out["launch_quantization"] = values.CLIP_LAUNCH_QUANTIZATION.name(clip.launch_quantization)
        out["legato"] = bool(clip.legato)
        out["state"] = _state(clip)
        if clip.is_playing:
            out["playing_position"] = _r(clip.playing_position)
    out["muted"] = bool(clip.muted)
    out["velocity_amount"] = _r(clip.velocity_amount)
    try:
        out["groove"] = clip.groove.name if clip.has_groove and clip.groove is not None else None
    except Exception:
        out["groove"] = None
    try:
        view = clip.view
        out["grid"] = {"quantization": values.GRID_QUANTIZATION.name(view.grid_quantization), "triplet": bool(view.grid_is_triplet)}
    except Exception:
        pass
    out["envelopes"] = _envelopes(clip)
    out["has_envelopes"] = bool(clip.has_envelopes)
    if audio:
        markers, marker_count = _warp_markers(clip)
        audio_out = {
            "file_path": clip.file_path,
            "gain_db": _gain_db_out(clip),
            "gain": _r(clip.gain),
            "pitch_coarse": int(clip.pitch_coarse),
            "pitch_fine": _r(clip.pitch_fine),
            "warping": bool(clip.warping),
            "warp_mode": values.WARP_MODE.name(clip.warp_mode),
            "warp_modes": [values.WARP_MODE.name(mode) for mode in clip.available_warp_modes],
            "ram_mode": bool(clip.ram_mode),
            "sample_rate": _r(clip.sample_rate),
            "sample_length": int(clip.sample_length),
        }
        if clip.sample_rate:
            audio_out["file_seconds"] = _r(clip.sample_length / float(clip.sample_rate))
        audio_out["warp_markers"] = markers
        if marker_count > len(markers):
            audio_out["warp_marker_count"] = marker_count
        out["audio"] = audio_out
    else:
        all_notes = read_notes(clip)
        out["note_count"] = len(all_notes)
        if notes:
            shown = all_notes[:limit]
            out["notes"] = [note_out(note) for note in shown]
            if len(all_notes) > len(shown):
                out["notes_truncated"] = True
    return out


# ---------------------------------------------------------------------------
# Notes as plain dicts
# ---------------------------------------------------------------------------


def note_dict(note):
    """A Live MidiNote as a dict with clip-time fields."""
    return {
        "note_id": int(note.note_id),
        "pitch": int(note.pitch),
        "start": float(note.start_time),
        "duration": float(note.duration),
        "velocity": float(note.velocity),
        "probability": float(note.probability),
        "velocity_deviation": float(note.velocity_deviation),
        "release_velocity": float(note.release_velocity),
        "mute": bool(note.mute),
    }


def note_out(note):
    """JSON for a note dict: ids, pitch with its name, timing and every MIDI note property."""
    return {
        "note_id": note["note_id"],
        "pitch": note["pitch"],
        "name": values.pitch_name(note["pitch"]),
        "start": _r(note["start"]),
        "duration": _r(note["duration"]),
        "velocity": _r(note["velocity"]),
        "probability": _r(note["probability"]),
        "velocity_deviation": _r(note["velocity_deviation"]),
        "release_velocity": _r(note["release_velocity"]),
        "mute": bool(note["mute"]),
    }


def sort_notes(notes):
    return sorted(notes, key=lambda note: (note["start"], note["pitch"]))


def read_notes(clip):
    """Every note of a MIDI clip (regardless of markers), sorted by start then pitch."""
    return sort_notes(note_dict(note) for note in clip.get_all_notes_extended())


def _value(raw, key, default):
    value = raw.get(key)
    return default if value is None else value


def _pitch_of(raw, where):
    """Pitch from a note dict's 'pitch', falling back to 'name' (get_notes output uses both)."""
    if raw.get("pitch") is not None:
        return values.parse_pitch(raw["pitch"], where + ".pitch")
    return values.parse_pitch(raw["name"], where + ".name")


def _note_fields(meter, raw, where, partial=False):
    """Validated note fields from a dict. partial=True (edits) returns only the fields present."""
    out = {}
    if not partial or raw.get("start") is not None:
        if raw.get("start") is None:
            raise CommandError("invalid_argument", "{0} needs start (clip beats, or 'bar.beat.sixteenth' where 1.1.1 is the clip start)".format(where))
        out["start"] = parse_clip_time(meter, raw["start"], where + ".start")
        if out["start"] < 0:
            raise CommandError("invalid_argument", "{0}.start must not be before the clip start (beat 0)".format(where))
    if not partial or raw.get("duration") is not None:
        if raw.get("duration") is None:
            raise CommandError("invalid_argument", "{0} needs duration (beats, '1/8', '1/16T' or 'N bars')".format(where))
        out["duration"] = parse_length(meter, raw["duration"], where + ".duration")
    checks = (
        ("velocity", 1, 127), ("probability", 0, 1), ("velocity_deviation", -127, 127), ("release_velocity", 0, 127),
    )
    for key, low, high in checks:
        if raw.get(key) is not None:
            out[key] = float(_number(raw[key], where + "." + key, low, high))
        elif not partial:
            out[key] = NOTE_DEFAULTS[key]
    if raw.get("mute") is not None:
        out["mute"] = _flag(raw["mute"], where + ".mute")
    elif not partial:
        out["mute"] = False
    return out


def normalize_notes(meter, notes):
    """Validate write_notes input into note dicts, one per pitch ("pitches" writes a chord).

    Accepts get_notes output as input too: note_id is ignored and name is a fallback for pitch.
    Raises CommandError before anything is written.
    """
    if not isinstance(notes, (list, tuple)) or not notes:
        raise CommandError("invalid_argument", "notes must be a non-empty list of {pitch, start, duration, ...} objects")
    out = []
    for index, raw in enumerate(notes):
        where = "notes[{0}]".format(index)
        if not isinstance(raw, dict):
            raise CommandError("invalid_argument", "{0} must be an object like {{\"pitch\": \"C3\", \"start\": 0, \"duration\": 1}}, got {1!r}".format(where, raw))
        unknown = sorted(set(raw) - set(_NOTE_KEYS) - {"note_id", "name"})
        if unknown:
            raise CommandError("invalid_argument", "{0} has unknown keys {1}; accepted: {2}".format(where, ", ".join(unknown), ", ".join(_NOTE_KEYS)))
        single = raw.get("pitch") is not None or raw.get("name") is not None
        chord = raw.get("pitches") is not None
        if single == chord:
            raise CommandError("invalid_argument", "{0} needs pitch (one note) or pitches (a chord), not both".format(where))
        if chord:
            if not isinstance(raw["pitches"], (list, tuple)) or not raw["pitches"]:
                raise CommandError("invalid_argument", "{0}.pitches must be a non-empty list of pitches".format(where))
            pitches = [values.parse_pitch(item, where + ".pitches") for item in raw["pitches"]]
        else:
            pitches = [_pitch_of(raw, where)]
        fields = _note_fields(meter, raw, where)
        for pitch in pitches:
            note = dict(fields)
            note["pitch"] = pitch
            out.append(note)
    return out


class NoteFilter(object):
    """Selects notes by id, pitch set, pitch range and start-time range (all optional, combined with AND).

    Time range: notes whose start lies in [start, end), in clip beats or 'bar.beat.sixteenth'.
    """

    def __init__(self, meter, note_ids=None, pitches=None, pitch_min=None, pitch_max=None, start=None, end=None):
        self.ids = None
        if note_ids is not None:
            self.ids = [_number(item, "note_ids", 0, integer=True) for item in _as_list(note_ids)]
        self.pitches = None if pitches is None else set(values.parse_pitch(item, "pitches") for item in _as_list(pitches))
        self.low = None if pitch_min is None else values.parse_pitch(pitch_min, "pitch_min")
        self.high = None if pitch_max is None else values.parse_pitch(pitch_max, "pitch_max")
        self.start = None if start is None else parse_clip_time(meter, start, "start")
        self.end = None if end is None else parse_clip_time(meter, end, "end")
        if self.low is not None and self.high is not None and self.low > self.high:
            raise CommandError("invalid_argument", "pitch_min ({0}) is above pitch_max ({1})".format(pitch_min, pitch_max))
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise CommandError("invalid_argument", "start ({0}) must be before end ({1})".format(start, end))
        self._id_set = None if self.ids is None else set(self.ids)

    @property
    def empty(self):
        return all(item is None for item in (self.ids, self.pitches, self.low, self.high, self.start, self.end))

    def __call__(self, note):
        if self._id_set is not None and note["note_id"] not in self._id_set:
            return False
        if self.pitches is not None and note["pitch"] not in self.pitches:
            return False
        if self.low is not None and note["pitch"] < self.low:
            return False
        if self.high is not None and note["pitch"] > self.high:
            return False
        if self.start is not None and note["start"] < self.start - EPS:
            return False
        if self.end is not None and note["start"] >= self.end - EPS:
            return False
        return True

    def missing_ids(self, notes):
        if self.ids is None:
            return []
        present = set(note["note_id"] for note in notes)
        return [item for item in self.ids if item not in present]


def _missing_ids_error(missing, clip):
    shown = ", ".join(str(item) for item in missing[:20])
    return CommandError("not_found", "Note ids not in clip '{0}': {1}. Read current ids with get_notes".format(clip.name, shown))


# ---------------------------------------------------------------------------
# Note transforms (pure: lists of note dicts in, new note dicts out)
# ---------------------------------------------------------------------------


def clamp_velocity(value):
    return float(min(127, max(1, int(round(value)))))


def scale_step(pitch, steps, root, intervals):
    """Move a pitch by `steps` degrees of a scale (root pitch class, semitone intervals).

    A note outside the scale keeps its chromatic offset from the scale tone below it.
    """
    scale = sorted(set(int(item) % 12 for item in intervals) | {0})
    size = len(scale)
    octave, pc = divmod(pitch - root, 12)
    index = max(position for position, interval in enumerate(scale) if interval <= pc)
    offset = pc - scale[index]
    new_octave, new_index = divmod(octave * size + index + steps, size)
    return root + new_octave * 12 + scale[new_index] + offset


def transpose_notes(notes, semitones=None, steps=None, root=0, intervals=None):
    if (semitones is None) == (steps is None):
        raise CommandError("invalid_argument", "transpose needs semitones (chromatic) or steps (scale degrees in the song's key), not both")
    out = []
    for note in notes:
        if semitones is not None:
            pitch = note["pitch"] + int(semitones)
        else:
            pitch = scale_step(note["pitch"], int(steps), root, intervals)
        if not 0 <= pitch <= 127:
            raise CommandError("invalid_argument", "Transposing {0} lands on MIDI {1}, outside 0..127; filter the notes or transpose less".format(
                values.pitch_name(note["pitch"]), pitch))
        out.append(dict(note, pitch=pitch))
    return out


def quantize_notes(notes, grid, amount=1.0, swing=0.0, origin=0.0):
    """Pull note starts toward the grid by `amount` (0..1); swing (0..1) delays every second grid line by up to half a step."""
    out = []
    for note in notes:
        index = int(math.floor((note["start"] - origin) / grid + 0.5))
        target = origin + index * grid + (swing * grid / 2.0 if index % 2 == 1 else 0.0)
        out.append(dict(note, start=max(0.0, note["start"] + (target - note["start"]) * amount)))
    return out


def humanize_notes(notes, timing=0.0, velocity=0.0, seed=None):
    """Random start offsets within +/-timing beats and velocity offsets within +/-velocity (uniform)."""
    rng = _random.Random(seed)
    out = []
    for note in notes:
        start = note["start"] + (rng.uniform(-timing, timing) if timing else 0.0)
        level = note["velocity"] + (rng.uniform(-velocity, velocity) if velocity else 0.0)
        out.append(dict(note, start=max(0.0, start), velocity=clamp_velocity(level) if velocity else note["velocity"]))
    return out


def velocity_notes(notes, factor=None, offset=None, value=None, spread=None, seed=None):
    """velocity * factor + offset, or `value`; then a random +/-spread; clamped to 1..127."""
    if value is not None and (factor is not None or offset is not None):
        raise CommandError("invalid_argument", "value sets every velocity; do not combine it with factor or offset")
    if all(item is None for item in (factor, offset, value, spread)):
        raise CommandError("invalid_argument", "velocity needs factor, offset, value and/or random")
    rng = _random.Random(seed)
    out = []
    for note in notes:
        level = float(value) if value is not None else note["velocity"] * (1.0 if factor is None else factor) + (offset or 0.0)
        if spread:
            level += rng.uniform(-spread, spread)
        out.append(dict(note, velocity=clamp_velocity(level)))
    return out


def legato_notes(notes):
    """Extend each note to the next later start among the notes (chords move together); the last notes keep their length."""
    starts = sorted(set(note["start"] for note in notes))
    out = []
    for note in notes:
        position = bisect.bisect_right(starts, note["start"] + EPS)
        if position < len(starts):
            out.append(dict(note, duration=starts[position] - note["start"]))
        else:
            out.append(dict(note))
    return out


def reverse_notes(notes, region_start, region_end):
    """Mirror notes within [region_start, region_end): a note ending at the region end moves to the region start."""
    out = []
    for note in notes:
        start = region_start + region_end - (note["start"] + note["duration"])
        out.append(dict(note, start=max(region_start, start)))
    return out


def stretch_notes(notes, factor, anchor=0.0):
    """Scale note starts (around `anchor`) and durations by `factor`."""
    return [dict(note, start=max(0.0, anchor + (note["start"] - anchor) * factor), duration=note["duration"] * factor) for note in notes]


def shift_notes(notes, offset):
    out = [dict(note, start=note["start"] + offset) for note in notes]
    if out and min(note["start"] for note in out) < -EPS:
        raise CommandError("invalid_argument", "offset {0:g} would move notes before the clip start (earliest note at {1:g})".format(
            offset, min(note["start"] for note in notes)))
    return [dict(note, start=max(0.0, note["start"])) for note in out]


# ---------------------------------------------------------------------------
# Clip gain (dB <-> Live's raw 0..1 value), measured on Live 12.4.6
# ---------------------------------------------------------------------------

GAIN_UNITY = 0.4   # raw gain shown as 0.00 dB
GAIN_MAX_DB = 24.0  # raw gain 1.0
GAIN_QUADRATIC_FLOOR = 0.03  # below this raw value the curve steepens towards -inf


def gain_to_db(gain):
    """dB for a raw clip gain (None below the modelled range, -inf at 0).

    Live 12.4.6: dB = 40 (g - 0.4) for g >= 0.4 (up to +24 dB at 1.0) and dB = 42 x - 200 x^2 with
    x = g - 0.4 for 0.03 <= g < 0.4 (about -42.9 dB at 0.03). Lower values approach -inf.
    """
    if gain <= 0:
        return float("-inf")
    x = gain - GAIN_UNITY
    if x >= 0:
        return 40.0 * x
    if gain >= GAIN_QUADRATIC_FLOOR:
        return 42.0 * x - 200.0 * x * x
    return None


def db_to_gain(db):
    """Raw clip gain for a dB value within the modelled range (about -42.9..+24 dB); None below it."""
    if db >= 0:
        return min(1.0, GAIN_UNITY + db / 40.0)
    x = (42.0 - math.sqrt(1764.0 - 800.0 * db)) / 400.0
    gain = GAIN_UNITY + x
    return gain if gain >= GAIN_QUADRATIC_FLOOR - 1e-9 else None


def set_gain_db(clip, db):
    """Set an audio clip's gain in dB ('-inf' allowed, maximum +24 dB)."""
    if db is None or (isinstance(db, str) and db.strip().lower() in ("-inf", "-infinity", "off")):
        clip.gain = 0.0
        return
    db = _number(db, "gain_db", None, GAIN_MAX_DB)
    gain = db_to_gain(db)
    if gain is None:
        # Below about -43 dB the curve is not modelled: bisect on Live's own display instead.
        low, high = 0.0, GAIN_QUADRATIC_FLOOR
        for _ in range(32):
            middle = (low + high) / 2.0
            clip.gain = middle
            shown = values.parse_display_number(clip.gain_display_string)
            if shown is None or shown < db:
                low = middle
            else:
                high = middle
        gain = high  # the lowest gain Live displays at (or above) the target
    clip.gain = gain


# ---------------------------------------------------------------------------
# Drum pads
# ---------------------------------------------------------------------------


def find_drum_rack(container, depth=0):
    """The first Drum Rack in a device chain, looking inside rack chains (up to three levels)."""
    for device in container.devices:
        if getattr(device, "can_have_drum_pads", False):
            return device
        if depth < 3 and getattr(device, "can_have_chains", False):
            for chain in device.chains:
                found = find_drum_rack(chain, depth + 1)
                if found is not None:
                    return found
    return None


def drum_chains(rack):
    """[(chain name, in_note)] of a Drum Rack's chains that respond to one note."""
    out = []
    if rack is None:
        return out
    for chain in rack.chains:
        note = getattr(chain, "in_note", -1)
        if note is not None and 0 <= note <= 127:
            out.append((chain.name, int(note)))
    return out


def _drum_key(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def resolve_drum(name, gm, chains):
    """(pitch, source) for a drum lane: a MIDI number or note name, a Drum Rack chain name (exact, then
    unique substring; a General MIDI match breaks ties), or the General MIDI drum note `gm`."""
    text = str(name).strip()
    if re.match(r"^-?\d+$", text) or values._NOTE.match(text):
        return values.parse_pitch(text, "drum"), "note"
    key = _drum_key(text)
    exact = [(chain_name, note) for chain_name, note in chains if _drum_key(chain_name) == key]
    partial = exact or [(chain_name, note) for chain_name, note in chains if key and key in _drum_key(chain_name)]
    notes = sorted(set(note for _, note in partial))
    if len(notes) == 1:
        return notes[0], "pad '{0}'".format(partial[0][0])
    if len(notes) > 1:
        if gm in notes:
            return gm, "pad '{0}'".format([chain_name for chain_name, note in partial if note == gm][0])
        options = ", ".join("{0} ({1})".format(chain_name, values.pitch_name(note)) for chain_name, note in partial)
        raise CommandError("invalid_argument", "Drum {0!r} matches several pads: {1}. Use a fuller pad name or a note".format(text, options))
    if gm is not None:
        return int(gm), "gm"
    pads = ", ".join("{0} ({1})".format(chain_name, values.pitch_name(note)) for chain_name, note in chains) or "(no Drum Rack pads)"
    raise CommandError("not_found", "Drum {0!r} is not a pad, a note or a General MIDI drum. Pads: {1}. GM names: kick, snare, "
                                    "clap, rim, closed hat, open hat, pedal hat, low/mid/high tom, crash, ride, tambourine, "
                                    "cowbell, shaker; or pass a note such as 'C1' or 36".format(text, pads))


def _validate_lanes(lanes):
    if not isinstance(lanes, (list, tuple)) or not lanes:
        raise CommandError("invalid_argument", "lanes must be a non-empty list (the write_drum_pattern tool builds it from a step pattern)")
    out = []
    for index, lane in enumerate(lanes):
        where = "lanes[{0}]".format(index)
        if not isinstance(lane, dict) or lane.get("drum") is None or lane.get("cycle") is None or not isinstance(lane.get("hits"), (list, tuple)):
            raise CommandError("invalid_argument", "{0} must have drum, cycle and hits".format(where))
        cycle = _number(lane["cycle"], where + ".cycle", EPS)
        gm = lane.get("gm")
        if gm is not None:
            gm = _number(gm, where + ".gm", 0, 127, integer=True)
        hits = []
        for hit in lane["hits"]:
            if not isinstance(hit, (list, tuple)) or len(hit) != 3:
                raise CommandError("invalid_argument", "{0}.hits items must be [start, duration, velocity]".format(where))
            start = _number(hit[0], where + ".start", 0)
            if start >= cycle - EPS:
                raise CommandError("invalid_argument", "{0} hit at {1} is outside its {2}-beat cycle".format(where, start, cycle))
            hits.append((start, _number(hit[1], where + ".duration", EPS), float(_number(hit[2], where + ".velocity", 1, 127))))
        out.append({"drum": str(lane["drum"]), "gm": gm, "cycle": cycle, "hits": hits, "steps": lane.get("steps")})
    return out


def tile_hits(hits, cycle, region_start, region_end):
    """(start, duration, velocity) for a lane's hits repeated every `cycle` beats across the region."""
    out = []
    repeats = int(math.ceil((region_end - region_start) / cycle - EPS))
    for repeat in range(max(repeats, 0)):
        offset = region_start + repeat * cycle
        for start, duration, velocity in hits:
            if offset + start < region_end - EPS:
                out.append((offset + start, duration, velocity))
    return out


# ---------------------------------------------------------------------------
# Writing notes into Live
# ---------------------------------------------------------------------------


def _spec(note):
    import Live
    return Live.Clip.MidiNoteSpecification(
        pitch=int(note["pitch"]), start_time=float(note["start"]), duration=float(note["duration"]),
        velocity=float(note.get("velocity", NOTE_DEFAULTS["velocity"])), mute=bool(note.get("mute", False)),
        probability=float(note.get("probability", NOTE_DEFAULTS["probability"])),
        velocity_deviation=float(note.get("velocity_deviation", NOTE_DEFAULTS["velocity_deviation"])),
        release_velocity=float(note.get("release_velocity", NOTE_DEFAULTS["release_velocity"])),
    )


def _add_notes(clip, notes):
    if not notes:
        return []
    return [int(item) for item in clip.add_new_notes(tuple(_spec(note) for note in notes))]


def _remove_ids(clip, ids):
    ids = list(ids)
    if ids:
        clip.remove_notes_by_id(ids)
    return len(ids)


def _apply_modifications(clip, updated):
    """Write changed note dicts back by id through apply_note_modifications (ids and extra data survive)."""
    by_id = dict((note["note_id"], note) for note in updated)
    if not by_id:
        return 0
    vector = clip.get_notes_by_id(list(by_id))
    for live_note in vector:
        note = by_id[int(live_note.note_id)]
        live_note.pitch = int(note["pitch"])
        live_note.start_time = float(note["start"])
        live_note.duration = float(note["duration"])
        live_note.velocity = float(note["velocity"])
        live_note.probability = float(note["probability"])
        live_note.velocity_deviation = float(note["velocity_deviation"])
        live_note.release_velocity = float(note["release_velocity"])
        live_note.mute = bool(note["mute"])
    clip.apply_note_modifications(vector)
    return len(by_id)


def region_warnings(clip, notes):
    """Warnings for notes that start outside the part of the clip that plays."""
    region_start, region_end = play_region(clip)
    late = [note for note in notes if note["start"] >= region_end - EPS]
    early = [note for note in notes if note["start"] < region_start - EPS]
    warnings = []
    if late:
        warnings.append("{0} note(s) start at or after the clip end (beat {1:g}) and will not play; extend the clip with "
                        "set_clip(loop_end=...) or end_marker".format(len(late), region_end))
    if early:
        warnings.append("{0} note(s) start before the clip's {1} (beat {2:g}) and will not play".format(
            len(early), "loop start" if clip.looping else "start marker", region_start))
    return warnings


def _notes_result(notes, limit=100):
    shown = sort_notes(notes)[:limit]
    return [note_out(note) for note in shown]


# ---------------------------------------------------------------------------
# Commands: clips
# ---------------------------------------------------------------------------


def _check_color(color):
    if color is None:
        return
    if isinstance(color, int) and not isinstance(color, bool) and 0 <= color <= 69:
        return
    if isinstance(color, str) and re.match(r"^#?[0-9a-fA-F]{6}$", color.strip()):
        return
    raise CommandError("invalid_argument", "color must be a Live colour index 0..69 or '#RRGGBB', got {0!r}".format(color))


def _arrangement_extents(owner):
    return dict((getattr(item, "_live_ptr", id(item)), (item.name, float(item.start_time), float(item.end_time)))
                for item in owner.arrangement_clips)


def check_free(song, owner, start, end, ignore=None):
    """Refuse an arrangement range that overlaps another clip (Live would trim or replace it)."""
    for index, other in enumerate(refs.arrangement_clips(owner)):
        if ignore is not None and refs.same(other, ignore):
            continue
        if other.start_time < end - EPS and other.end_time > start + EPS:
            raise CommandError(
                "invalid_argument",
                "{0}..{1} overlaps arrangement clip {2} '{3}' ({4}..{5}) on '{6}'; Live would overwrite it. Delete it first "
                "(delete_clip) or choose a free time".format(
                    values.format_time(song, start), values.format_time(song, end), index, other.name,
                    values.format_time(song, other.start_time), values.format_time(song, other.end_time), owner.name),
            )


def _collateral(owner, before, created):
    """Warnings about arrangement clips that a new clip trimmed or replaced."""
    after = _arrangement_extents(owner)
    created_ptr = getattr(created, "_live_ptr", id(created))
    warnings = []
    for pointer, (name, start, end) in before.items():
        if pointer == created_ptr:
            continue
        now = after.get(pointer)
        if now is None:
            warnings.append("Replaced arrangement clip '{0}' ({1:g}..{2:g})".format(name, start, end))
        elif abs(now[1] - start) > EPS or abs(now[2] - end) > EPS:
            warnings.append("Trimmed arrangement clip '{0}' from {1:g}..{2:g} to {3:g}..{4:g}".format(name, start, end, now[1], now[2]))
    return warnings


@command("create_clip")
def create_clip(ctx, track, slot=None, at=None, length=None, name=None, color=None, file_path=None):
    """MIDI clip in a Session slot (ClipSlot.create_clip) or at an arrangement time (Track.create_midi_clip);
    audio clip from file_path (ClipSlot.create_audio_clip / Track.create_audio_clip)."""
    song = ctx.song
    owner = refs.track(song, track)
    _require_clip_track(song, owner)
    if (slot is None) == (at is None):
        raise CommandError("invalid_argument", "Pass slot (Session scene index) or at (arrangement time), not both")
    _check_color(color)
    midi = bool(owner.has_midi_input)
    path = None
    if file_path is not None:
        if midi:
            raise CommandError("unsupported", "'{0}' is a MIDI track; audio clips from file_path need an audio track".format(owner.name))
        path = os.path.abspath(os.path.expanduser(str(file_path)))
        if not os.path.isfile(path):
            raise CommandError("not_found", "Audio file not found: {0}".format(path))
        if length is not None:
            raise CommandError("invalid_argument", "length applies to MIDI clips; an audio clip takes its file's length "
                                                   "(change it afterwards with set_clip loop_end / end_marker)")
    elif not midi:
        raise CommandError("invalid_argument", "'{0}' is an audio track: pass file_path (an audio file) to create an audio clip".format(owner.name))
    beats = parse_length(song, 4.0 if length is None else length, "length") if midi else None
    warnings = []
    if slot is not None:
        holder = refs.clip_slot(song, track, slot)
        if holder.has_clip:
            raise CommandError("invalid_argument", "Slot {0} of '{1}' already holds clip '{2}'; delete_clip it first or pick an empty slot".format(
                slot, owner.name, holder.clip.name))
        clip = holder.create_clip(beats) if midi else holder.create_audio_clip(path)
    else:
        start = values.parse_time(song, at, "at")
        if not 0 <= start <= MAX_ARRANGEMENT_TIME:
            raise CommandError("invalid_argument", "at must be within 0..{0:g} beats, got {1!r}".format(MAX_ARRANGEMENT_TIME, at))
        if midi:
            check_free(song, owner, start, start + beats)
            clip = owner.create_midi_clip(start, beats)
        else:
            before = _arrangement_extents(owner)
            clip = owner.create_audio_clip(path, start)
            warnings = _collateral(owner, before, clip)
    if name is not None:
        clip.name = str(name)
    if color is not None:
        values.apply_color(clip, color)
    out = clip_info(song, clip)
    if warnings:
        out["warnings"] = warnings
    return out


@command("get_clip", readonly=True)
def get_clip(ctx, track, slot=None, arrangement_clip=None, notes=False, limit=DEFAULT_NOTE_LIMIT):
    """Every property of a clip; notes=True adds up to `limit` notes."""
    song = ctx.song
    clip = _clip(song, track, slot, arrangement_clip)
    return clip_info(song, clip, notes=_flag(notes, "notes"), limit=_number(limit, "limit", 0, MAX_NOTE_LIMIT, integer=True))


def _parse_signature(signature):
    if isinstance(signature, (list, tuple)) and len(signature) == 2:
        numerator, denominator = signature
    elif isinstance(signature, str) and re.match(r"^\s*\d+\s*/\s*\d+\s*$", signature):
        numerator, denominator = [int(part) for part in signature.split("/")]
    else:
        raise CommandError("invalid_argument", "signature must look like '3/4' or '7/8', got {0!r}".format(signature))
    numerator = _number(numerator, "signature numerator", 1, 99, integer=True)
    denominator = _number(denominator, "signature denominator", 1, 16, integer=True)
    if denominator not in (1, 2, 4, 8, 16):
        raise CommandError("invalid_argument", "signature denominator must be 1, 2, 4, 8 or 16, got {0}".format(denominator))
    return numerator, denominator


def _region_time(clip, value, name):
    if _unwarped(clip):
        return float(_number(value, name + " (seconds, unwarped audio)"))
    return parse_clip_time(clip, value, name)


def _set_pair(clip, first_attr, second_attr, first, second):
    """Set a (start, end) pair in an order Live accepts (it refuses start >= end at every step)."""
    current_first, current_second = float(getattr(clip, first_attr)), float(getattr(clip, second_attr))
    new_first = current_first if first is None else first
    new_second = current_second if second is None else second
    if new_first >= new_second - EPS:
        raise CommandError("invalid_argument", "{0} ({1:g}) must be before {2} ({3:g})".format(first_attr, new_first, second_attr, new_second))
    if new_first >= current_second:
        setattr(clip, second_attr, new_second)
        setattr(clip, first_attr, new_first)
    else:
        setattr(clip, first_attr, new_first)
        setattr(clip, second_attr, new_second)


def apply_region(clip, looping=None, loop_start=None, loop_end=None, start_marker=None, end_marker=None):
    """Set loop brace and markers. Live only applies them reliably while looping is on (docs/spikes.md),
    so looping is switched on for the edit and then set to the requested (or previous) state."""
    target = bool(clip.looping) if looping is None else looping
    touches = any(item is not None for item in (loop_start, loop_end, start_marker, end_marker))
    if touches:
        was_looping = bool(clip.looping)
        if not was_looping and not _unwarped(clip):
            clip.looping = True
        try:
            if loop_start is not None or loop_end is not None:
                _set_pair(clip, "loop_start", "loop_end", loop_start, loop_end)
            if start_marker is not None or end_marker is not None:
                _set_pair(clip, "start_marker", "end_marker", start_marker, end_marker)
        except Exception:
            if bool(clip.looping) != was_looping:
                clip.looping = was_looping
            raise
    if bool(clip.looping) != target:
        clip.looping = target


@command("set_clip")
def set_clip(ctx, track, slot=None, arrangement_clip=None, name=None, color=None, looping=None, loop_start=None, loop_end=None,
             start_marker=None, end_marker=None, signature=None, launch_mode=None, launch_quantization=None, legato=None,
             muted=None, velocity_amount=None, groove=None, grid=None, grid_triplet=None, gain_db=None, pitch_coarse=None,
             pitch_fine=None, warping=None, warp_mode=None, ram_mode=None):
    """Set any writable clip property; everything is validated before anything changes."""
    song = ctx.song
    clip = _clip(song, track, slot, arrangement_clip)
    audio = bool(clip.is_audio_clip)
    given = dict((key, value) for key, value in (("gain_db", gain_db), ("pitch_coarse", pitch_coarse), ("pitch_fine", pitch_fine),
                                                 ("warping", warping), ("warp_mode", warp_mode), ("ram_mode", ram_mode)) if value is not None)
    if given and not audio:
        raise CommandError("unsupported", "{0} apply to audio clips; '{1}' is a MIDI clip".format(", ".join(sorted(given)), clip.name))
    _check_color(color)
    parsed = {}
    if signature is not None:
        parsed["signature"] = _parse_signature(signature)
    if looping is not None:
        parsed["looping"] = _flag(looping, "looping")
    if launch_mode is not None:
        parsed["launch_mode"] = values.LAUNCH_MODE.parse(launch_mode)
    if launch_quantization is not None:
        parsed["launch_quantization"] = values.CLIP_LAUNCH_QUANTIZATION.parse(launch_quantization)
    for key, value in (("legato", legato), ("muted", muted), ("grid_triplet", grid_triplet), ("ram_mode", ram_mode), ("warping", warping)):
        if value is not None:
            parsed[key] = _flag(value, key)
    if velocity_amount is not None:
        parsed["velocity_amount"] = float(_number(velocity_amount, "velocity_amount", 0, 1))
    if grid is not None:
        parsed["grid"] = values.GRID_QUANTIZATION.parse(grid)
    if groove is not None:
        if isinstance(groove, str) and groove.strip().lower() in ("none", "off", ""):
            raise CommandError("unsupported", "Live's API cannot remove a clip's groove; assign another groove, or set its amounts with set_groove")
        parsed["groove"] = refs.groove(song, groove)
    if pitch_coarse is not None:
        parsed["pitch_coarse"] = _number(pitch_coarse, "pitch_coarse", -48, 48, integer=True)
    if pitch_fine is not None:
        parsed["pitch_fine"] = float(_number(pitch_fine, "pitch_fine", -50, 49))
    if warp_mode is not None:
        mode = values.WARP_MODE.parse(warp_mode)
        available = list(clip.available_warp_modes)
        if mode not in available:
            raise CommandError("invalid_argument", "Warp mode {0!r} is not available for '{1}'. Available: {2}".format(
                warp_mode, clip.name, ", ".join(str(values.WARP_MODE.name(item)) for item in available)))
        parsed["warp_mode"] = mode
    region = dict((key, value) for key, value in (("loop_start", loop_start), ("loop_end", loop_end),
                                                  ("start_marker", start_marker), ("end_marker", end_marker)) if value is not None)
    if region and "warping" in parsed and parsed["warping"] != bool(clip.warping):
        raise CommandError("invalid_argument", "Change warping in its own set_clip call first: it switches loop and marker units "
                                               "between beats and seconds, and Live applies it later")
    if gain_db is not None and not (isinstance(gain_db, str) and gain_db.strip().lower() in ("-inf", "-infinity", "off")):
        _number(gain_db, "gain_db", None, GAIN_MAX_DB)
    # Apply: name and meter first (bar notation of times depends on the clip's meter).
    if name is not None:
        clip.name = str(name)
    if color is not None:
        values.apply_color(clip, color)
    if "signature" in parsed:
        clip.signature_denominator = parsed["signature"][1]
        clip.signature_numerator = parsed["signature"][0]
    if "warping" in parsed:
        clip.warping = parsed["warping"]
    times = dict((key, _region_time(clip, value, key)) for key, value in region.items())
    apply_region(clip, parsed.get("looping"), times.get("loop_start"), times.get("loop_end"), times.get("start_marker"), times.get("end_marker"))
    for key in ("launch_mode", "launch_quantization", "legato", "muted", "velocity_amount", "groove", "pitch_coarse", "pitch_fine",
                "warp_mode", "ram_mode"):
        if key in parsed:
            setattr(clip, key, parsed[key])
    if "grid" in parsed:
        clip.view.grid_quantization = parsed["grid"]
    if "grid_triplet" in parsed:
        clip.view.grid_is_triplet = parsed["grid_triplet"]
    if gain_db is not None:
        set_gain_db(clip, gain_db)
    return clip_info(song, clip)


@command("delete_clip")
def delete_clip(ctx, track, slot=None, arrangement_clip=None):
    """Delete a Session or arrangement clip."""
    song = ctx.song
    clip = _clip(song, track, slot, arrangement_clip)
    label = clip_label(song, clip)
    label["kind"] = "midi" if clip.is_midi_clip else "audio"
    if clip.is_arrangement_clip:
        owner_track(clip).delete_clip(clip)
    else:
        clip.canonical_parent.delete_clip()
    return {"deleted": label}


def _arrangement_length(clip):
    """Beats a clip covers when copied into the arrangement (Session clips: loop or marker span)."""
    if clip.is_arrangement_clip:
        return float(clip.end_time - clip.start_time)
    if _unwarped(clip):
        return None
    start, end = play_region(clip)
    return float(end - start)


def _next_free_slot(owner, after):
    slots = list(owner.clip_slots)
    for position in range(after + 1, len(slots)):
        if not slots[position].has_clip:
            return position
    return None


@command("duplicate_clip")
def duplicate_clip(ctx, track, slot=None, arrangement_clip=None, to_track=None, to_slot=None, to_time=None, move=False):
    """Session -> Session (ClipSlot.duplicate_clip_to), Session or arrangement -> arrangement
    (Track.duplicate_clip_to_arrangement); move deletes the source afterwards."""
    song = ctx.song
    source = _clip(song, track, slot, arrangement_clip)
    source_owner = owner_track(source)
    target = refs.track(song, to_track) if to_track is not None else source_owner
    _require_clip_track(song, target)
    move = _flag(move, "move")
    if to_slot is not None and to_time is not None:
        raise CommandError("invalid_argument", "Pass to_slot (Session) or to_time (arrangement), not both")
    if bool(source.is_midi_clip) != bool(target.has_midi_input):
        raise CommandError("invalid_argument", "Cannot copy {0} clip '{1}' to {2} track '{3}'".format(
            "a MIDI" if source.is_midi_clip else "an audio", source.name, "a MIDI" if target.has_midi_input else "an audio", target.name))
    source_label = clip_label(song, source)
    if source.is_arrangement_clip and to_slot is not None:
        raise CommandError("unsupported", "Live cannot copy an arrangement clip into a Session slot; copy it within the arrangement (to_time)")
    if to_time is not None or source.is_arrangement_clip:
        start = values.parse_time(song, to_time, "to_time") if to_time is not None else float(source.end_time)
        if not 0 <= start <= MAX_ARRANGEMENT_TIME:
            raise CommandError("invalid_argument", "to_time must be within 0..{0:g} beats".format(MAX_ARRANGEMENT_TIME))
        length = _arrangement_length(source)
        if length is not None:
            check_free(song, target, start, start + length, ignore=source if move else None)
        copy = target.duplicate_clip_to_arrangement(source, start)
        if move:
            _delete_source(source)
    else:
        source_slot_index = source_label["slot"]
        if to_slot is None:
            if to_track is not None and not refs.same(target, source_owner):
                raise CommandError("invalid_argument", "Pass to_slot to copy into another track's Session slots")
            free = _next_free_slot(source_owner, source_slot_index)
            if free is None:
                raise CommandError("not_found", "No empty slot below slot {0} on '{1}'; pass to_slot or create a scene first".format(
                    source_slot_index, source_owner.name))
            holder = list(source_owner.clip_slots)[free]
        else:
            holder = refs.clip_slot(song, refs.track_ref(song, target), to_slot)
        if holder.has_clip:
            raise CommandError("invalid_argument", "Slot {0} of '{1}' already holds '{2}'; delete_clip it first or choose an empty slot".format(
                refs.index_of(target.clip_slots, holder), target.name, holder.clip.name))
        source.canonical_parent.duplicate_clip_to(holder)
        copy = holder.clip
        if move:
            source.canonical_parent.delete_clip()
    return {"source": source_label, "moved": move, "clip": clip_info(song, copy)}


def _delete_source(source):
    """Delete a moved clip, unless Live already replaced it with the copy (when the ranges overlap)."""
    if source.is_arrangement_clip:
        holder = owner_track(source)
        if refs.index_of(holder.arrangement_clips, source) is not None:
            holder.delete_clip(source)
    else:
        source.canonical_parent.delete_clip()


@command("fire_clip", undo=False)
def fire_clip(ctx, track, slot):
    """Launch a Session clip (subject to launch quantization; Live starts the transport if needed)."""
    song = ctx.song
    holder = refs.clip_slot(song, track, slot)
    if not holder.has_clip:
        raise CommandError("not_found", "Slot {0} of '{1}' is empty; firing it would stop the track or start recording".format(
            slot, refs.track(song, track).name))
    holder.fire()
    return {"fired": clip_label(song, holder.clip),
            "launch_quantization": values.SONG_QUANTIZATION.name(song.clip_trigger_quantization),
            "hint": "The clip starts at the next launch-quantization boundary; get_clip shows its state"}


@command("stop_clip", undo=False)
def stop_clip(ctx, track, quantized=True):
    """Stop the clips playing or triggered on a track (Track.stop_all_clips)."""
    song = ctx.song
    owner = refs.track(song, track)
    kind = refs.track_kind(song, owner)
    if kind in ("return", "master"):
        raise CommandError("unsupported", "'{0}' is a {1} track and plays no clips; stop all clips with transport".format(owner.name, kind))
    owner.stop_all_clips(_flag(quantized, "quantized"))
    return {"stopped": refs.track_label(song, owner), "quantized": _flag(quantized, "quantized")}


# ---------------------------------------------------------------------------
# Commands: notes
# ---------------------------------------------------------------------------


@command("get_notes", readonly=True)
def get_notes(ctx, track, slot=None, arrangement_clip=None, note_ids=None, pitches=None, pitch_min=None, pitch_max=None,
              start=None, end=None, limit=DEFAULT_NOTE_LIMIT):
    """Notes of a MIDI clip, filtered, sorted by start then pitch, at most `limit`."""
    song = ctx.song
    clip = _midi_clip(song, track, slot, arrangement_clip, "get_notes")
    selector = NoteFilter(clip, note_ids, pitches, pitch_min, pitch_max, start, end)
    limit = _number(limit, "limit", 0, MAX_NOTE_LIMIT, integer=True)
    notes = read_notes(clip)
    matching = [note for note in notes if selector(note)]
    out = {"clip": clip_label(song, clip), "count": len(matching), "notes": [note_out(note) for note in matching[:limit]]}
    if len(matching) > limit:
        out["truncated"] = True
        out["hint"] = "Narrow with start/end or pitch filters, or raise limit"
    missing = selector.missing_ids(notes)
    if missing:
        out["missing_ids"] = missing[:50]
    return out


@command("write_notes")
def write_notes(ctx, track, notes, slot=None, arrangement_clip=None, mode="add", start=None, end=None):
    """Add notes, replace all notes, or replace the notes starting in [start, end)."""
    song = ctx.song
    clip = _midi_clip(song, track, slot, arrangement_clip, "write_notes")
    mode = _choice(mode, ("add", "replace", "replace_range"), "mode")
    new = normalize_notes(clip, notes)
    if mode != "replace_range" and (start is not None or end is not None):
        raise CommandError("invalid_argument", "start/end apply to mode='replace_range'")
    removed = 0
    replaced = None
    existing = list(clip.get_all_notes_extended())
    if mode == "replace":
        removed = _remove_ids(clip, [note.note_id for note in existing])
    elif mode == "replace_range":
        low = parse_clip_time(clip, start, "start") if start is not None else min(note["start"] for note in new)
        high = parse_clip_time(clip, end, "end") if end is not None else max(note["start"] + note["duration"] for note in new)
        if high <= low + EPS:
            raise CommandError("invalid_argument", "replace_range needs start before end (got {0:g}..{1:g})".format(low, high))
        removed = _remove_ids(clip, [note.note_id for note in existing if low - EPS <= note.start_time < high - EPS])
        replaced = {"start": _r(low), "end": _r(high)}
    ids = _add_notes(clip, new)
    count = len(clip.get_all_notes_extended())
    out = {"clip": clip_label(song, clip), "mode": mode, "added": len(ids), "removed": removed, "note_ids": ids[:500],
           "note_count": count}
    if replaced:
        out["range"] = replaced
    warnings = region_warnings(clip, new)
    lost = len(existing) - removed + len(ids) - count
    if lost > 0:
        warnings.append("{0} note(s) were replaced: Live keeps one note per pitch and start time".format(lost))
    if warnings:
        out["warnings"] = warnings
    return out


@command("edit_notes")
def edit_notes(ctx, track, edits, slot=None, arrangement_clip=None):
    """Change notes by id (pitch, start, duration, velocity, probability, ...), keeping their ids."""
    song = ctx.song
    clip = _midi_clip(song, track, slot, arrangement_clip, "edit_notes")
    if not isinstance(edits, (list, tuple)) or not edits:
        raise CommandError("invalid_argument", "edits must be a non-empty list of {note_id, ...changes} objects")
    changes = {}
    for index, raw in enumerate(edits):
        where = "edits[{0}]".format(index)
        if not isinstance(raw, dict) or raw.get("note_id") is None:
            raise CommandError("invalid_argument", "{0} must be an object with note_id and the fields to change".format(where))
        unknown = sorted(set(raw) - set(_EDIT_KEYS) - {"name"})
        if unknown:
            raise CommandError("invalid_argument", "{0} has unknown keys {1}; accepted: {2}".format(where, ", ".join(unknown), ", ".join(_EDIT_KEYS)))
        note_id = _number(raw["note_id"], where + ".note_id", 0, integer=True)
        if note_id in changes:
            raise CommandError("invalid_argument", "note_id {0} appears twice in edits".format(note_id))
        fields = _note_fields(clip, raw, where, partial=True)
        if raw.get("pitch") is not None or raw.get("name") is not None:
            fields["pitch"] = _pitch_of(raw, where)
        changes[note_id] = fields
    notes = dict((note["note_id"], note) for note in read_notes(clip))
    missing = [note_id for note_id in changes if note_id not in notes]
    if missing:
        raise _missing_ids_error(missing, clip)
    updated = [dict(notes[note_id], **fields) for note_id, fields in changes.items()]
    _apply_modifications(clip, updated)
    after = [note for note in read_notes(clip) if note["note_id"] in changes]
    return {"clip": clip_label(song, clip), "edited": len(updated), "notes": _notes_result(after)}


@command("delete_notes")
def delete_notes(ctx, track, slot=None, arrangement_clip=None, note_ids=None, pitches=None, pitch_min=None, pitch_max=None,
                 start=None, end=None, all=False):
    """Delete notes by id, pitch and/or time range, or every note with all=True."""
    song = ctx.song
    clip = _midi_clip(song, track, slot, arrangement_clip, "delete_notes")
    everything = _flag(all, "all")
    selector = NoteFilter(clip, note_ids, pitches, pitch_min, pitch_max, start, end)
    if everything and not selector.empty:
        raise CommandError("invalid_argument", "all=True deletes every note; drop the filters, or drop all to delete only matching notes")
    if not everything and selector.empty:
        raise CommandError("invalid_argument", "Say which notes to delete: note_ids, pitches, pitch_min/pitch_max, start/end, or all=True")
    notes = read_notes(clip)
    missing = selector.missing_ids(notes)
    if missing:
        raise _missing_ids_error(missing, clip)
    doomed = [note["note_id"] for note in notes if everything or selector(note)]
    deleted = _remove_ids(clip, doomed)
    return {"clip": clip_label(song, clip), "deleted": deleted, "remaining": len(notes) - deleted}


_TRANSFORMS = {
    "transpose": ("semitones", "steps"),
    "quantize": ("grid", "amount", "swing"),
    "humanize": ("timing", "velocity", "seed"),
    "velocity": ("factor", "offset", "value", "random", "seed"),
    "legato": (),
    "reverse": (),
    "stretch": ("factor",),
    "shift": ("offset",),
}


@command("transform_notes")
def transform_notes(ctx, track, operation, slot=None, arrangement_clip=None, note_ids=None, pitches=None, pitch_min=None,
                    pitch_max=None, start=None, end=None, semitones=None, steps=None, grid=None, amount=None, swing=None,
                    timing=None, velocity=None, seed=None, factor=None, offset=None, value=None, random=None):
    """Transform the selected notes in place, keeping note ids (apply_note_modifications)."""
    song = ctx.song
    clip = _midi_clip(song, track, slot, arrangement_clip, "transform_notes")
    op = _choice(operation, tuple(_TRANSFORMS), "operation")
    given = dict((key, item) for key, item in (
        ("semitones", semitones), ("steps", steps), ("grid", grid), ("amount", amount), ("swing", swing), ("timing", timing),
        ("velocity", velocity), ("seed", seed), ("factor", factor), ("offset", offset), ("value", value), ("random", random),
    ) if item is not None)
    stray = sorted(set(given) - set(_TRANSFORMS[op]))
    if stray:
        accepted = ", ".join(_TRANSFORMS[op]) or "no options (only the note filters)"
        raise CommandError("invalid_argument", "{0} do(es) not apply to {1}; it takes: {2}".format(", ".join(stray), op, accepted))
    selector = NoteFilter(clip, note_ids, pitches, pitch_min, pitch_max, start, end)
    notes = read_notes(clip)
    missing = selector.missing_ids(notes)
    if missing:
        raise _missing_ids_error(missing, clip)
    selected = [note for note in notes if selector(note)]
    extra = {}
    if seed is not None:
        seed = _number(seed, "seed", integer=True)
    elif op in ("humanize", "velocity") and (op == "humanize" or random is not None):
        seed = _random.randint(0, 2 ** 31 - 1)
    if op == "transpose":
        if semitones is not None:
            new = transpose_notes(selected, semitones=_number(semitones, "semitones", -127, 127, integer=True))
        elif steps is not None:
            intervals = list(song.scale_intervals)
            if not intervals:
                raise CommandError("unsupported", "The song has no scale set; transpose by semitones or set the song's key and scale")
            new = transpose_notes(selected, steps=_number(steps, "steps", -64, 64, integer=True), root=int(song.root_note), intervals=intervals)
            extra["scale"] = {"root": values.NOTE_NAMES[int(song.root_note) % 12], "name": song.scale_name}
        else:
            raise CommandError("invalid_argument", "transpose needs semitones or steps")
    elif op == "quantize":
        grid_beats = parse_grid(clip, grid if grid is not None else "1/16")
        new = quantize_notes(selected, grid_beats, float(_number(1.0 if amount is None else amount, "amount", 0, 1)),
                             float(_number(0.0 if swing is None else swing, "swing", 0, 1)))
        extra["grid_beats"] = _r(grid_beats)
    elif op == "humanize":
        if timing is None and velocity is None:
            raise CommandError("invalid_argument", "humanize needs timing (beats or '10ms') and/or velocity (+/- spread)")
        timing_beats = parse_timing(timing, song.tempo) if timing is not None else 0.0
        new = humanize_notes(selected, timing_beats, float(_number(velocity or 0, "velocity", 0, 127)), seed)
        extra["timing_beats"] = _r(timing_beats)
    elif op == "velocity":
        new = velocity_notes(
            selected,
            factor=None if factor is None else float(_number(factor, "factor", 0, 16)),
            offset=None if offset is None else float(_number(offset, "offset", -127, 127)),
            value=None if value is None else float(_number(value, "value", 1, 127)),
            spread=None if random is None else float(_number(random, "random", 0, 127)),
            seed=seed,
        )
    elif op == "legato":
        new = legato_notes(selected)
    elif op == "reverse":
        region_start, region_end = play_region(clip)
        if selector.start is not None or selector.end is not None:
            region_start = selector.start if selector.start is not None else region_start
            region_end = selector.end if selector.end is not None else region_end
        new = reverse_notes(selected, region_start, region_end)
        extra["region"] = {"start": _r(region_start), "end": _r(region_end)}
    elif op == "stretch":
        if factor is None:
            raise CommandError("invalid_argument", "stretch needs factor (2 = twice as long, 0.5 = half)")
        anchor = selector.start if selector.start is not None else play_region(clip)[0]
        new = stretch_notes(selected, float(_number(factor, "factor", 0.01, 64)), anchor)
        extra["anchor"] = _r(anchor)
    else:
        if offset is None:
            raise CommandError("invalid_argument", "shift needs offset (beats, negative moves earlier)")
        new = shift_notes(selected, float(_number(offset, "offset", -MAX_ARRANGEMENT_TIME, MAX_ARRANGEMENT_TIME)))
    changed = [after for before, after in zip(selected, new) if after != before]
    _apply_modifications(clip, changed)
    changed_ids = set(note["note_id"] for note in changed)
    after_notes = read_notes(clip)
    out = {"clip": clip_label(song, clip), "operation": op, "selected": len(selected), "changed": len(changed),
           "note_count": len(after_notes), "notes": _notes_result([note for note in after_notes if note["note_id"] in changed_ids])}
    if seed is not None and op in ("humanize", "velocity"):
        out["seed"] = seed
    out.update(extra)
    if not selected:
        out["hint"] = "No notes matched the filters"
    warnings = region_warnings(clip, [note for note in after_notes if note["note_id"] in changed_ids])
    if len(after_notes) < len(notes):
        warnings.append("{0} note(s) merged with notes of the same pitch and start".format(len(notes) - len(after_notes)))
    if warnings:
        out["warnings"] = warnings
    return out


@command("write_drum_pattern")
def write_drum_pattern(ctx, track, lanes, slot=None, arrangement_clip=None, mode="replace"):
    """Write drum lanes (parsed step patterns from the MCP server) across the clip's playing region.

    Lane drums resolve through the track's Drum Rack chain names, then the General MIDI note `gm`.
    mode='replace' first removes existing notes on the lanes' pitches; mode='add' keeps them.
    """
    song = ctx.song
    clip = _midi_clip(song, track, slot, arrangement_clip, "write_drum_pattern")
    mode = _choice(mode, ("replace", "add"), "mode")
    parsed = _validate_lanes(lanes)
    rack = find_drum_rack(owner_track(clip))
    chains = drum_chains(rack)
    chain_notes = set(note for _, note in chains)
    region_start, region_end = play_region(clip)
    warnings, report, notes, pitches = [], [], [], set()
    for lane in parsed:
        pitch, source = resolve_drum(lane["drum"], lane["gm"], chains)
        pitches.add(pitch)
        if source == "gm":
            if rack is not None and pitch not in chain_notes:
                warnings.append("'{0}' has no matching pad in '{1}'; used General MIDI {2} ({3}), which has no pad".format(
                    lane["drum"], rack.name, values.pitch_name(pitch), pitch))
        if lane["cycle"] > region_end - region_start + EPS:
            warnings.append("The '{0}' pattern is {1:g} beats but the clip plays {2:g}; extend the clip (set_clip loop_end) to hear all of it".format(
                lane["drum"], lane["cycle"], region_end - region_start))
        hits = tile_hits(lane["hits"], lane["cycle"], region_start, region_end)
        for start, duration, level in hits:
            notes.append({"pitch": pitch, "start": start, "duration": duration, "velocity": level})
        report.append({"drum": lane["drum"], "pitch": pitch, "note": values.pitch_name(pitch), "source": source, "hits": len(hits)})
    removed = 0
    if mode == "replace":
        removed = _remove_ids(clip, [note.note_id for note in clip.get_all_notes_extended() if note.pitch in pitches])
    ids = _add_notes(clip, notes)
    out = {"clip": clip_label(song, clip), "mode": mode, "region": {"start": _r(region_start), "end": _r(region_end)},
           "lanes": report, "added": len(ids), "removed": removed}
    if rack is None:
        warnings.append("No Drum Rack on '{0}'; lanes use General MIDI drum notes".format(owner_track(clip).name))
    if warnings:
        out["warnings"] = warnings
    return out


# ---------------------------------------------------------------------------
# Commands: clip actions and conversions
# ---------------------------------------------------------------------------

_CLIP_ACTIONS = ("crop", "duplicate_loop", "duplicate_region", "quantize", "add_warp_marker", "move_warp_marker",
                 "remove_warp_marker", "audio_to_midi", "drum_rack_from_audio", "simpler_track_from_audio")
_AUDIO_TO_MIDI = {"melody": "melody_to_midi", "harmony": "harmony_to_midi", "drums": "drums_to_midi"}
_ACTION_ARGS = {
    "crop": (), "duplicate_loop": (), "duplicate_region": ("start", "length", "destination", "pitch", "transpose"),
    "quantize": ("grid", "amount", "pitch"), "add_warp_marker": ("beat_time", "sample_time"),
    "move_warp_marker": ("beat_time", "distance"), "remove_warp_marker": ("beat_time",),
    "audio_to_midi": ("type", "name"), "drum_rack_from_audio": ("name",), "simpler_track_from_audio": ("name",),
}


def _pointer(obj):
    return getattr(obj, "_live_ptr", None) or id(obj)


def _rename_new_tracks(song, tracks, name):
    for position, item in enumerate(tracks):
        item.name = name if position == 0 else "{0} {1}".format(name, position + 1)
    return [refs.track_label(song, item) for item in tracks]


def _require_arg(args, key, action, example):
    if args.get(key) is None:
        raise CommandError("invalid_argument", "{0} needs args.{1}, e.g. {2}".format(action, key, example))
    return args[key]


@command("clip_action", timeout=60.0)
def clip_action(ctx, track, action, slot=None, arrangement_clip=None, args=None):
    """Clip functions: crop, duplicate_loop, duplicate_region, quantize, warp markers and Live.Conversions."""
    import Live
    song = ctx.song
    clip = _clip(song, track, slot, arrangement_clip)
    act = _choice(action, _CLIP_ACTIONS, "action")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise CommandError("invalid_argument", "args must be an object, e.g. {\"grid\": \"1/16\"}")
    stray = sorted(set(args) - set(_ACTION_ARGS[act]))
    if stray:
        raise CommandError("invalid_argument", "{0} takes args: {1} (got {2})".format(act, ", ".join(_ACTION_ARGS[act]) or "none", ", ".join(stray)))
    out = {"action": act}
    if act == "crop":
        if clip.looping and not _unwarped(clip) and clip.start_marker < clip.loop_start - EPS:
            clip.start_marker = clip.loop_start  # Live keeps a pre-roll before the loop unless the start marker is on it
        clip.crop()
    elif act == "duplicate_loop":
        clip.duplicate_loop()
    elif act == "duplicate_region":
        if not clip.is_midi_clip:
            raise CommandError("unsupported", "duplicate_region works on MIDI clips")
        region_start = parse_clip_time(clip, _require_arg(args, "start", act, "{start: 0, length: 4, destination: 4}"), "start")
        region_length = parse_length(clip, _require_arg(args, "length", act, "{start: 0, length: 4, destination: 4}"), "length")
        destination = parse_clip_time(clip, _require_arg(args, "destination", act, "{start: 0, length: 4, destination: 4}"), "destination")
        pitch = -1 if args.get("pitch") is None else values.parse_pitch(args["pitch"], "pitch")
        transpose = _number(args.get("transpose", 0), "transpose", -127, 127, integer=True)
        clip.duplicate_region(region_start, region_length, destination, pitch, transpose)
    elif act == "quantize":
        grid = values.QUANTIZE_GRID.parse(args.get("grid", "1/16"))
        amount = float(_number(args.get("amount", 1.0), "amount", 0, 1))
        if args.get("pitch") is not None:
            if not clip.is_midi_clip:
                raise CommandError("unsupported", "quantize with pitch works on MIDI clips")
            clip.quantize_pitch(values.parse_pitch(args["pitch"], "pitch"), grid, amount)
        else:
            clip.quantize(grid, amount)
        out["note"] = "Live quantizes to the grid using the song's swing amount; audio clips align warp markers"
    elif act in ("add_warp_marker", "move_warp_marker", "remove_warp_marker"):
        _require_audio(clip, act)
        if not clip.warping:
            raise CommandError("unsupported", "Warp markers need a warped clip; set_clip(warping=true) first")
        beat = float(_number(_require_arg(args, "beat_time", act, "{beat_time: 2.0}"), "beat_time"))
        if act == "add_warp_marker":
            if args.get("sample_time") is not None:
                seconds = float(_number(args["sample_time"], "sample_time (seconds)", 0))
            else:
                seconds = clip.beat_to_sample_time(beat) / float(clip.sample_rate)
            clip.add_warp_marker(Live.Clip.WarpMarker(sample_time=seconds, beat_time=beat))
        elif act == "move_warp_marker":
            clip.move_warp_marker(beat, float(_number(_require_arg(args, "distance", act, "{beat_time: 2.0, distance: 0.5}"), "distance")))
        else:
            clip.remove_warp_marker(beat)
    elif act == "audio_to_midi":
        _require_audio(clip, act)
        kind = _choice(args.get("type", "melody"), tuple(_AUDIO_TO_MIDI), "type")
        if not Live.Conversions.is_convertible_to_midi(song, clip):
            raise CommandError("unsupported", "Live cannot convert '{0}' to MIDI".format(clip.name))
        before = [_pointer(item) for item in song.tracks]
        Live.Conversions.audio_to_midi_clip(song, clip, getattr(Live.Conversions.AudioToMidiType, _AUDIO_TO_MIDI[kind]))
        # Live adds the new MIDI track on a later tick: clips_conversion_status reports it.
        jobs = ctx.state.setdefault("clips_conversions", {})
        job = int(ctx.state.get("clips_next_job", 1))
        ctx.state["clips_next_job"] = job + 1
        jobs[job] = {"before": before, "name": args.get("name"), "started": time.time()}
        out.update({"pending": True, "job": job, "type": kind})
        out["clip"] = clip_label(song, clip)
        return out
    else:
        _require_audio(clip, act)
        before = set(_pointer(item) for item in song.tracks)
        if act == "drum_rack_from_audio":
            Live.Conversions.create_drum_rack_from_audio_clip(song, clip)
        else:
            Live.Conversions.create_midi_track_with_simpler(song, clip)
        new_tracks = [item for item in song.tracks if _pointer(item) not in before]
        if args.get("name") is not None:
            out["new_tracks"] = _rename_new_tracks(song, new_tracks, str(args["name"]))
        else:
            out["new_tracks"] = [refs.track_label(song, item) for item in new_tracks]
        out["clip"] = clip_label(song, clip)
        return out
    out["clip"] = clip_info(song, clip)
    return out


@command("clips_conversion_status", undo=False)
def clips_conversion_status(ctx, job):
    """Poll an audio_to_midi conversion started by clip_action: done with the new track, or still pending."""
    song = ctx.song
    jobs = ctx.state.setdefault("clips_conversions", {})
    key = _number(job, "job", 0, integer=True)
    entry = jobs.get(key)
    if entry is None:
        raise not_found("Conversion job", job, sorted(jobs))
    before = set(entry["before"])
    new_tracks = [item for item in song.tracks if _pointer(item) not in before]
    elapsed = time.time() - entry["started"]
    if new_tracks:
        jobs.pop(key, None)
        if entry.get("name") is not None:
            labels = _rename_new_tracks(song, new_tracks, str(entry["name"]))
        else:
            labels = [refs.track_label(song, item) for item in new_tracks]
        return {"done": True, "new_tracks": labels, "seconds": round(elapsed, 2)}
    if elapsed > 120:
        jobs.pop(key, None)
        return {"done": True, "new_tracks": [], "error": "Live created no MIDI track within 120 s (nothing detected in the audio?)"}
    return {"done": False, "seconds": round(elapsed, 2)}
