"""Musical units and JSON conversion shared by every command handler.

Conventions (see docs/PRD.md section 8):
- Time is beats (quarter notes) or a "bar.beat.sixteenth" string, 1-based, in the song's meter.
- Pitch is a MIDI number or a note name in Live's convention, where C3 is 60.
- Volume and sends are dB; pan is -1..1.
- Enums use Live's display names, e.g. "1/16", "1 bar", "complex_pro".
"""
import math
import re

from .errors import CommandError

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

SIXTEENTH = 0.25
_BAR_TIME = re.compile(r"^\s*(\d+)(?:\.(\d+))?(?:\.(\d+(?:\.\d+)?))?\s*$")
_LENGTH = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(bars?|beats?)\s*$", re.IGNORECASE)


def beat_length(song):
    """Length in quarter-note beats of one beat of the song's meter (0.5 in 6/8)."""
    return 4.0 / song.signature_denominator


def bar_length(song):
    """Length in quarter-note beats of one bar of the song's meter."""
    return song.signature_numerator * beat_length(song)


def parse_time(song, value, name="time"):
    """Return beats for a number of beats or a 'bar.beat.sixteenth' string.

    Numbers (and digit-only strings) are beats. A locator name ("Chorus") is that locator's time.
    A string containing a dot is always bar notation,
    1-based: '17.1.1' is the start of bar 17, '3.3' is bar 3 beat 3. Beats per bar and sixteenths per
    beat are range-checked against the song's meter, so '2.5' in 4/4 is an error rather than a guess.
    """
    if isinstance(value, bool):
        raise CommandError("invalid_argument", "{0} must be beats or 'bar.beat.sixteenth', not a boolean".format(name))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if re.match(r"^-?\d+$", text):
            return float(text)
        match = _BAR_TIME.match(text)
        if match and "." in text:
            bar = int(match.group(1))
            beat = int(match.group(2) or 1)
            sixteenth = float(match.group(3) or 1)
            beats_per_bar = song.signature_numerator
            sixteenths_per_beat = beat_length(song) / SIXTEENTH
            if bar < 1 or not 1 <= beat <= beats_per_bar or not 1 <= sixteenth < sixteenths_per_beat + 1:
                raise CommandError(
                    "invalid_argument",
                    "{0} '{1}' is not a valid 'bar.beat.sixteenth' in {2}/{3}: bars start at 1, beats run 1..{4}, "
                    "sixteenths 1..{5:g}. Pass beats as a number instead.".format(
                        name, value, song.signature_numerator, song.signature_denominator, beats_per_bar, sixteenths_per_beat),
                )
            return (bar - 1) * bar_length(song) + (beat - 1) * beat_length(song) + (sixteenth - 1) * SIXTEENTH
        located = _locator_time(song, text)
        if located is not None:
            return located
    raise CommandError(
        "invalid_argument",
        "{0} must be beats, a 'bar.beat.sixteenth' string such as '17.1.1', or a locator name, got {1!r}".format(name, value),
    )


def _locator_time(song, name):
    """Time in beats of the locator (cue point) named `name`, case-insensitively, or None."""
    key = name.strip().lower()
    if not key:
        return None
    try:
        cues = list(song.cue_points)
    except Exception:
        return None
    matches = [float(cue.time) for cue in cues if str(cue.name).strip().lower() == key]
    if len(matches) > 1:
        raise CommandError("invalid_argument", "{0} locators are named {1!r}; rename one or pass the time".format(len(matches), name))
    return matches[0] if matches else None


def parse_length(song, value, name="length"):
    """Return beats for a number of beats or a string such as '8 bars' or '6 beats'."""
    if isinstance(value, bool):
        raise CommandError("invalid_argument", "{0} must be beats or 'N bars', not a boolean".format(name))
    if isinstance(value, (int, float)):
        length = float(value)
    elif isinstance(value, str):
        match = _LENGTH.match(value)
        if match:
            amount = float(match.group(1))
            length = amount * (bar_length(song) if match.group(2).lower().startswith("bar") else 1.0)
        else:
            try:
                length = float(value)
            except ValueError:
                raise CommandError("invalid_argument", "{0} must be beats or a string like '8 bars', got {1!r}".format(name, value))
    else:
        raise CommandError("invalid_argument", "{0} must be beats or a string like '8 bars', got {1!r}".format(name, value))
    if length <= 0:
        raise CommandError("invalid_argument", "{0} must be positive, got {1!r}".format(name, value))
    return length


def format_time(song, beats):
    """Format beats as a 1-based 'bar.beat.sixteenth' string in the song's meter."""
    beats = float(beats)
    bar_len = bar_length(song)
    beat_len = beat_length(song)
    bar = int(math.floor(beats / bar_len + 1e-9))
    remainder = beats - bar * bar_len
    beat = int(math.floor(remainder / beat_len + 1e-9))
    remainder -= beat * beat_len
    sixteenth = remainder / SIXTEENTH
    whole = int(round(sixteenth))
    if abs(sixteenth - whole) < 1e-6:
        return "{0}.{1}.{2}".format(bar + 1, beat + 1, whole + 1)
    return "{0}.{1}.{2:.3g}".format(bar + 1, beat + 1, sixteenth + 1)


def time_out(song, beats):
    """Time as both beats and bar notation, for outputs."""
    return {"beats": round(float(beats), 6), "bar": format_time(song, beats)}


# ---------------------------------------------------------------------------
# Pitch
# ---------------------------------------------------------------------------

_NOTE = re.compile(r"^\s*([A-Ga-g])([#b]{0,2})(-?\d+)\s*$")
_SEMITONES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def parse_pitch(value, name="pitch"):
    """Return a MIDI number for a number or a note name (Live convention: C3 = 60)."""
    if isinstance(value, bool):
        raise CommandError("invalid_argument", "{0} must be a MIDI number or note name, not a boolean".format(name))
    if isinstance(value, (int, float)) and float(value).is_integer():
        pitch = int(value)
    elif isinstance(value, str):
        text = value.strip()
        if re.match(r"^-?\d+$", text):
            pitch = int(text)
        else:
            match = _NOTE.match(text)
            if not match:
                raise CommandError("invalid_argument", "{0} {1!r} is not a MIDI number or note name like 'C3' or 'F#2'".format(name, value))
            letter, accidentals, octave = match.groups()
            pitch = (int(octave) + 2) * 12 + _SEMITONES[letter.lower()]
            pitch += accidentals.count("#") - accidentals.count("b")
    else:
        raise CommandError("invalid_argument", "{0} must be a MIDI number or note name, got {1!r}".format(name, value))
    if not 0 <= pitch <= 127:
        raise CommandError("invalid_argument", "{0} {1!r} is outside the MIDI range 0..127 (C-2..G8)".format(name, value))
    return pitch


def pitch_name(pitch, flats=False):
    """Note name for a MIDI number in Live's convention (60 -> 'C3')."""
    names = _FLAT_NAMES if flats else _SHARP_NAMES
    return "{0}{1}".format(names[int(pitch) % 12], int(pitch) // 12 - 2)


NOTE_NAMES = _SHARP_NAMES


def parse_root_note(value):
    """Return a pitch class 0..11 for a number or a note name without octave ('C', 'F#', 'Bb')."""
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 11:
        return value
    if isinstance(value, str):
        match = re.match(r"^\s*([A-Ga-g])([#b]?)\s*$", value)
        if match:
            letter, accidental = match.groups()
            return (_SEMITONES[letter.lower()] + (1 if accidental == "#" else -1 if accidental == "b" else 0)) % 12
    raise CommandError("invalid_argument", "key must be a note name like 'C', 'F#' or 'Bb' (or 0..11), got {0!r}".format(value))


# ---------------------------------------------------------------------------
# Parameter display units (dB, Hz, %, ...)
# ---------------------------------------------------------------------------

_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def parse_display_number(text):
    """Number from a parameter display string, in DeviceParameter.display_value's canonical units.

    display_value counts frequencies in Hz and times in ms (docs/spikes.md), so '1.20 kHz' -> 1200,
    '2.50 s' -> 2500, '35 ms' -> 35, '-6.0 dB' -> -6.0, '-inf dB' -> -inf, '25L' -> -25, 'C' -> 0.
    Returns None when the string carries no number.
    """
    if text is None:
        return None
    text = str(text).strip()
    lowered = text.lower()
    if "-inf" in lowered:
        return float("-inf")
    if lowered in ("c", "center", "centre"):
        return 0.0
    match = _NUMBER.search(text)
    if not match:
        return None
    number = float(match.group(0))
    suffix = text[match.end():].strip().lower()
    unit = re.match(r"[a-z%]*", suffix).group(0)
    if unit == "khz":
        number *= 1000.0
    elif unit in ("s", "sec", "secs", "second", "seconds"):
        number *= 1000.0
    elif unit == "l":
        number = -abs(number)
    return number


def display_number(parameter, value=None):
    """Numeric display value of a parameter (current value unless ``value`` is given)."""
    if value is None:
        try:
            return float(parameter.display_value)
        except Exception:
            value = parameter.value
    return parse_display_number(parameter.str_for_value(value))


def set_display_number(parameter, target):
    """Set a continuous parameter in display units ('-6' dB, '800' Hz, '-25' pan).

    Live 12.4 accepts display units through DeviceParameter.display_value (see docs/spikes.md);
    the bisection over str_for_value is the fallback for parameters that reject it.
    """
    target = float(target)
    try:
        parameter.display_value = target
        shown = parse_display_number(parameter.str_for_value(parameter.value))
        if shown is not None and (shown == target or abs(shown - target) <= max(abs(target) * 0.02, 0.011)):
            return
    except Exception:
        pass
    # display_value rejected the write or landed elsewhere (unit mismatch): search the display string.
    parameter.value = value_for_display_number(parameter, target)


def value_for_display_number(parameter, target, iterations=48):
    """Raw value whose display number equals ``target``, by bisection.

    Live's display mappings (dB faders, Hz frequencies, ...) are monotonic in the raw value, so a
    bisection over [min, max] converges for any continuous parameter with a numeric display.
    """
    low, high = float(parameter.min), float(parameter.max)
    low_display = display_number(parameter, low)
    high_display = display_number(parameter, high)
    if low_display is None or high_display is None:
        raise CommandError("unsupported", "Parameter '{0}' has no numeric display value".format(parameter.name))
    increasing = high_display >= low_display
    if target <= min(low_display, high_display):
        return low if increasing else high
    if target >= max(low_display, high_display):
        return high if increasing else low
    for _ in range(iterations):
        middle = (low + high) / 2.0
        shown = display_number(parameter, middle)
        if shown is None:
            break
        if (shown < target) == increasing:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def parameter_out(parameter, index=None, detail=False):
    """JSON description of a DeviceParameter."""
    out = {"name": parameter.name, "value": round(float(parameter.value), 6), "display": parameter.str_for_value(parameter.value)}
    if index is not None:
        out = dict({"index": index}, **out)
    out["min"] = parameter.min
    out["max"] = parameter.max
    if parameter.is_quantized:
        out["items"] = list(parameter.value_items)
    if detail:
        out["is_quantized"] = bool(parameter.is_quantized)
        out["is_enabled"] = bool(parameter.is_enabled)
        if parameter.original_name != parameter.name:
            out["original_name"] = parameter.original_name
        try:
            out["default_value"] = parameter.default_value
        except Exception:
            pass
        out["automation_state"] = ["none", "playing", "overridden"][int(parameter.automation_state)]
    if not parameter.is_enabled:
        out["is_enabled"] = False
    return out


def set_parameter(parameter, value):
    """Set a parameter from a raw number, a display string ('-6 dB', '800 Hz') or a quantized item name.

    Returns the parameter's new JSON description. Numbers are raw values clamped to the parameter
    range; strings are matched against quantized items first, then parsed as display values.
    """
    if not parameter.is_enabled:
        raise CommandError("unsupported", "Parameter '{0}' is disabled (macro-mapped or controlled by Max)".format(parameter.name))
    if isinstance(value, bool):
        raw = parameter.max if value else parameter.min
    elif isinstance(value, (int, float)):
        raw = float(value)
        if not parameter.min - 1e-9 <= raw <= parameter.max + 1e-9:
            raise CommandError(
                "invalid_argument",
                "{0!r} is outside the raw range {1:g}..{2:g} of '{3}' (now {4}). Numbers are raw values; for display "
                "units pass a string such as '30 %', '800 Hz' or '-6 dB'.".format(value, parameter.min, parameter.max, parameter.name, parameter.str_for_value(parameter.value)),
            )
    elif isinstance(value, str):
        raw = None
        if parameter.is_quantized:
            items = [str(item) for item in parameter.value_items]
            for position, item in enumerate(items):
                if item.lower() == value.strip().lower():
                    raw = parameter.min + position
                    break
            if raw is None:
                raise CommandError("invalid_argument", "'{0}' is not a value of '{1}'. Options: {2}".format(value, parameter.name, ", ".join(items)))
        else:
            target = parse_display_number(value)
            if target is None:
                raise CommandError("invalid_argument", "Cannot read a number from {0!r} for parameter '{1}'".format(value, parameter.name))
            set_display_number(parameter, target)
            return parameter_out(parameter)
    else:
        raise CommandError("invalid_argument", "Value for '{0}' must be a number or string, got {1!r}".format(parameter.name, value))
    parameter.value = raw
    return parameter_out(parameter)


def volume_db(parameter):
    """Current dB of a volume or send parameter; -inf at the minimum (display_value floors at -70)."""
    if parameter.value <= parameter.min:
        return float("-inf")
    return display_number(parameter)


def set_volume_db(parameter, db):
    """Set a volume or send parameter in dB ('-inf' or None for silence)."""
    if db is None or (isinstance(db, str) and db.strip().lower() in ("-inf", "-infinity", "off")):
        parameter.value = parameter.min
        return
    try:
        target = float(db)
    except (TypeError, ValueError):
        raise CommandError("invalid_argument", "Volume must be a number of dB or '-inf', got {0!r}".format(db))
    set_display_number(parameter, target)


def parse_pan(value):
    """Return -1..1 for a number or a display string ('25L', 'C', '50R')."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        pan = float(value)
    elif isinstance(value, str):
        text = value.strip().upper()
        if text in ("C", "CENTER", "CENTRE", "0"):
            return 0.0
        match = re.match(r"^(\d+(?:\.\d+)?)\s*([LR])$", text)
        if not match:
            raise CommandError("invalid_argument", "pan must be -1..1 or a string like '25L', 'C', '50R', got {0!r}".format(value))
        pan = float(match.group(1)) / 50.0 * (-1 if match.group(2) == "L" else 1)
    else:
        raise CommandError("invalid_argument", "pan must be -1..1 or a string like '25L', got {0!r}".format(value))
    if not -1.0 <= pan <= 1.0:
        raise CommandError("invalid_argument", "pan must be within -1..1 (50L..50R), got {0!r}".format(value))
    return pan


# ---------------------------------------------------------------------------
# Enums: Live's integer enums <-> display names
# ---------------------------------------------------------------------------


class Enum(object):
    """Bidirectional mapping between display names and Live's integer enum values."""

    def __init__(self, label, names_to_values, aliases=None):
        self.label = label
        self._to_value = dict((name.lower(), value) for name, value in names_to_values.items())
        self._to_name = dict((value, name) for name, value in names_to_values.items())
        for alias, value in (aliases or {}).items():
            self._to_value[alias.lower()] = value
        self.names = list(names_to_values)

    def parse(self, value):
        if isinstance(value, int) and not isinstance(value, bool) and value in self._to_name:
            return value
        if isinstance(value, str) and value.strip().lower() in self._to_value:
            return self._to_value[value.strip().lower()]
        raise CommandError("invalid_argument", "{0} must be one of: {1} (got {2!r})".format(self.label, ", ".join(self.names), value))

    def name(self, value):
        return self._to_name.get(int(value), int(value))


# Session clip launch quantization (Song.clip_trigger_quantization, Live.Song.Quantization).
SONG_QUANTIZATION = Enum("quantization", {
    "none": 0, "8 bars": 1, "4 bars": 2, "2 bars": 3, "1 bar": 4, "1/2": 5, "1/2T": 6, "1/4": 7,
    "1/4T": 8, "1/8": 9, "1/8T": 10, "1/16": 11, "1/16T": 12, "1/32": 13,
}, aliases={"bar": 4, "1/1": 4, "off": 0})

# Per-clip launch quantization (Clip.launch_quantization, Live.Clip.ClipLaunchQuantization).
CLIP_LAUNCH_QUANTIZATION = Enum("launch_quantization", {
    "global": 0, "none": 1, "8 bars": 2, "4 bars": 3, "2 bars": 4, "1 bar": 5, "1/2": 6, "1/2T": 7,
    "1/4": 8, "1/4T": 9, "1/8": 10, "1/8T": 11, "1/16": 12, "1/16T": 13, "1/32": 14,
}, aliases={"bar": 5, "1/1": 5, "off": 1})

# MIDI recording quantization (Song.midi_recording_quantization, Live.Song.RecordingQuantization).
RECORD_QUANTIZATION = Enum("record_quantization", {
    "none": 0, "1/4": 1, "1/8": 2, "1/8T": 3, "1/8+1/8T": 4, "1/16": 5, "1/16T": 6, "1/16+1/16T": 7, "1/32": 8,
}, aliases={"off": 0})

# Note quantization grids for Clip.quantize (Live.Song.RecordingQuantization values).
QUANTIZE_GRID = RECORD_QUANTIZATION

# Clip view grid (Clip.View.grid_quantization, Live.Clip.GridQuantization).
GRID_QUANTIZATION = Enum("grid", {
    "none": 0, "8 bars": 1, "4 bars": 2, "2 bars": 3, "1 bar": 4, "1/2": 5, "1/4": 6, "1/8": 7, "1/16": 8, "1/32": 9,
})

LAUNCH_MODE = Enum("launch_mode", {"trigger": 0, "gate": 1, "toggle": 2, "repeat": 3})

WARP_MODE = Enum("warp_mode", {
    "beats": 0, "tones": 1, "texture": 2, "repitch": 3, "complex": 4, "rex": 5, "complex_pro": 6,
}, aliases={"complex pro": 6, "pro": 6})

MONITORING = Enum("monitoring", {"in": 0, "auto": 1, "off": 2})

CROSSFADE_ASSIGN = Enum("crossfade", {"A": 0, "none": 1, "B": 2})

PANNING_MODE = Enum("pan_mode", {"stereo": 0, "split": 1}, aliases={"stereo_split": 1})

DEVICE_TYPE = Enum("device_type", {"undefined": 0, "instrument": 1, "audio_effect": 2, "midi_effect": 4})

GROOVE_BASE = Enum("groove_base", {"1/4": 0, "1/8": 1, "1/8T": 2, "1/16": 3, "1/16T": 4, "1/32": 5})


# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------


def color_out(obj):
    """Colour of a Live object as index plus hex (tracks, clips, scenes, chains)."""
    out = {}
    try:
        index = obj.color_index
        out["color_index"] = None if index is None or index < 0 else int(index)
    except Exception:
        pass
    try:
        out["color"] = "#{0:06X}".format(int(obj.color) & 0xFFFFFF)
    except Exception:
        pass
    return out


def apply_color(obj, value):
    """Set a colour from a Live colour index (0..69) or a '#RRGGBB' hex string."""
    if isinstance(value, int) and not isinstance(value, bool):
        obj.color_index = value
    elif isinstance(value, str) and re.match(r"^#?[0-9a-fA-F]{6}$", value.strip()):
        obj.color = int(value.strip().lstrip("#"), 16)
    else:
        raise CommandError("invalid_argument", "color must be a Live colour index (0..69) or '#RRGGBB', got {0!r}".format(value))


# ---------------------------------------------------------------------------
# JSON conversion
# ---------------------------------------------------------------------------


def jsonable(value, depth=0):
    """Convert Live values (vectors, enums, BeatTime, objects) into JSON-safe data."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return str(value)
        return value
    if depth > 3:
        return repr(value)
    type_name = type(value).__name__
    if type_name in ("BeatTime", "SmptTime"):
        fields = ("bars", "beats", "sub_division", "ticks") if type_name == "BeatTime" else ("hours", "minutes", "seconds", "frames")
        return dict((field, getattr(value, field)) for field in fields)
    if isinstance(value, dict):
        return dict((str(key), jsonable(item, depth + 1)) for key, item in value.items())
    if hasattr(value, "__len__") and hasattr(value, "__getitem__") and not hasattr(value, "canonical_parent"):
        try:
            return [jsonable(item, depth + 1) for item in list(value)]
        except TypeError:
            pass
    # Live objects (Track, Device, RoutingType, ...): Boost.Python reports bare module names such as
    # "Track", so identify them by a name rather than by module.
    label = {"type": type_name}
    for attribute in ("display_name", "name"):
        try:
            label[attribute] = str(getattr(value, attribute))
            break
        except Exception:
            pass
    if len(label) == 1:
        label["repr"] = repr(value)[:120]
    return label
