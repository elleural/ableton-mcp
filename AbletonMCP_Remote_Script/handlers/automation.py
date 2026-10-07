"""WS-F: clip automation envelopes (docs/PRD.md section 7.6). Owned by workstream F.

Live's API (docs/spikes.md, "Automation", verified on 12.4.6):
- Session clips: Clip.automation_envelope(param) returns the envelope (None if missing) and
  create_automation_envelope(param) creates one.
- Arrangement clips: automation_envelope always returns None and create_automation_envelope raises, but
  the envelopes a clip already has (carried in from a Session clip by duplicate_clip_to_arrangement) are
  listed in Clip.automation_envelopes, and those Envelope objects can be read and edited.
- Envelope.create_event(EnvelopeEvent(time, value)) writes raw parameter values. Two events at the same
  time make a vertical jump (value_at_time at that instant returns the first). delete_events_in_range
  includes both ends. events_in_range values use an internal scale for some parameters (volume), so
  values are always read with value_at_time.
- clear_envelope / clear_all_envelopes work on Session and arrangement clips.
- Envelopes are in clip time and loop with the clip loop.
Times are clip time in beats (0 = the clip's 1.1.1), or "bar.beat.sixteenth" strings.
"""
import math

from .. import refs, values
from ..core import command
from ..errors import CommandError

SHAPES = ("ramp", "sine", "triangle", "square", "saw", "steps")
UNITS = ("display", "raw")
SINE_POINTS_PER_CYCLE = 16
MAX_EVENTS = 1024
MAX_SAMPLES = 128
MAX_EVENTS_OUT = 64
EPSILON = 1e-9

ARRANGEMENT_HINT = (
    "Live's API edits an arrangement clip's envelope only when the clip already has one. Write the envelope "
    "on the Session clip (slot) instead, then place it with arrange_from_scenes or duplicate_clip: clip "
    "envelopes travel into the arrangement, and the copy's envelope can then be edited here."
)


# ---------------------------------------------------------------------------
# Shapes (pure; values stay in the caller's units)
# ---------------------------------------------------------------------------


def _shape_error(message):
    return CommandError("invalid_argument", "shape: " + message)


def shape_events(kind, start, end, low=None, high=None, period=None, steps=None, resolution=SINE_POINTS_PER_CYCLE):
    """Breakpoints (time, value) for an automation shape over [start, end], in time order.

    A cycle lasts `period` beats (default: the whole range) and starts at `low` (from):
    - ramp: low at start to high at end (period ignored);
    - sine / triangle: reach high half way through each cycle and return to low;
    - square: low for the first half of each cycle, high for the second;
    - saw: rise from low to high over each cycle, then drop back;
    - steps: hold each value of `steps` for period / len(steps), cycling.
    Jumps are two breakpoints at the same time (old value first).
    """
    if kind not in SHAPES:
        raise _shape_error("type must be one of {0}, got {1!r}".format(", ".join(SHAPES), kind))
    if end - start <= EPSILON:
        raise _shape_error("the range is empty: end ({0:g}) must be after start ({1:g})".format(end, start))
    if kind == "steps":
        if not isinstance(steps, (list, tuple)) or not steps:
            raise _shape_error("type 'steps' needs a non-empty 'steps' list of values")
    elif low is None or high is None:
        raise _shape_error("type '{0}' needs 'from' and 'to' values".format(kind))
    if kind == "ramp":
        return [(start, low), (end, high)]
    cycle = (end - start) if period is None else float(period)
    if cycle <= EPSILON:
        raise _shape_error("period must be positive")
    if kind == "sine":
        def sine(time):
            return low + (high - low) * (1.0 - math.cos(2.0 * math.pi * (time - start) / cycle)) / 2.0
        out = [(time, sine(time)) for time in _grid(start, end, cycle / float(resolution))] + [(end, sine(end))]
    elif kind == "triangle":
        out = _triangle(start, end, cycle, low, high)
    elif kind == "saw":
        out = _saw(start, end, cycle, low, high)
    elif kind == "square":
        out = _steps(start, end, cycle / 2.0, [low, high])
    else:
        out = _steps(start, end, cycle / float(len(steps)), list(steps))
    if len(out) > MAX_EVENTS:
        raise _shape_error("{0} breakpoints exceed the limit of {1}; use a longer period or a shorter range".format(len(out), MAX_EVENTS))
    return out


def _grid(start, end, step):
    """start, start + step, ... strictly before end (computed by index, so no drift)."""
    if (end - start) / step > MAX_EVENTS:
        raise _shape_error("more than {0} breakpoints; use a longer period or a shorter range".format(MAX_EVENTS))
    times, index = [], 0
    while True:
        time = start + index * step
        if time >= end - EPSILON:
            return times
        times.append(time)
        index += 1


def _triangle(start, end, cycle, low, high):
    phase = ((end - start) / cycle) % 1.0
    if abs(phase - 1.0) < EPSILON:
        phase = 0.0
    last = low + (high - low) * (2.0 * phase if phase <= 0.5 else 2.0 - 2.0 * phase)
    out = [(time, low if index % 2 == 0 else high) for index, time in enumerate(_grid(start, end, cycle / 2.0))]
    return out + [(end, last)]


def _segments(start, end, length):
    """(begin, stop) pairs tiling [start, end] on a grid of `length`; the last one may be shorter."""
    begins = _grid(start, end, length)
    return list(zip(begins, begins[1:] + [end]))


def _saw(start, end, cycle, low, high):
    out = []
    for begin, stop in _segments(start, end, cycle):
        out.append((begin, low))
        out.append((stop, low + (high - low) * min(1.0, (stop - begin) / cycle)))
    return out


def _steps(start, end, length, levels):
    out = []
    for index, (begin, stop) in enumerate(_segments(start, end, length)):
        level = levels[index % len(levels)]
        if out and out[-1] == (begin, level):
            out.pop()  # the same level continues: no joint needed
        else:
            out.append((begin, level))
        out.append((stop, level))
    return out


# ---------------------------------------------------------------------------
# Values: display units -> raw
# ---------------------------------------------------------------------------


def is_pan(parameter):
    """True for pan-like parameters (displayed as '50L' .. 'C' .. '50R')."""
    try:
        return (str(parameter.str_for_value(parameter.min)).strip().upper().endswith("L")
                and str(parameter.str_for_value(parameter.max)).strip().upper().endswith("R"))
    except Exception:
        return False


def _number(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CommandError("invalid_argument", "{0} must be a number, got {1!r}".format(what, value))
    return float(value)


def raw_value(parameter, value, units, cache=None):
    """Raw value of `parameter` for a point value given in `units`; the parameter itself is not changed.

    display: dB, Hz, ms, % ... as numbers or strings ("-6 dB", "2.5 kHz"); pan as -1..1 or "25L";
    quantized parameters by item name ("Off") or raw number. raw: Live's internal value (min..max).
    """
    key = (units, value)
    if cache is not None and isinstance(value, (int, float, str)) and key in cache:
        return cache[key]
    low, high = float(parameter.min), float(parameter.max)
    if units == "raw":
        raw = _number(value, "Raw value for '{0}'".format(parameter.name))
        if not low - 1e-9 <= raw <= high + 1e-9:
            raise CommandError("invalid_argument", "Raw value {0:g} is outside the range of '{1}' ({2:g}..{3:g})".format(raw, parameter.name, low, high))
    elif parameter.is_quantized:
        raw = _quantized(parameter, value)
    elif is_pan(parameter):
        raw = low + (values.parse_pan(value) + 1.0) / 2.0 * (high - low)
    else:
        raw = _display_to_raw(parameter, value)
    if cache is not None and isinstance(value, (int, float, str)):
        cache[key] = raw
    return raw


def _quantized(parameter, value):
    items = [str(item) for item in parameter.value_items]
    if isinstance(value, str):
        for position, item in enumerate(items):
            if item.lower() == value.strip().lower():
                return float(parameter.min) + position
        raise CommandError("invalid_argument", "'{0}' is not a value of '{1}'. Options: {2}".format(value, parameter.name, ", ".join(items)))
    raw = _number(value, "Value for '{0}'".format(parameter.name))
    if not parameter.min <= raw <= parameter.max:
        raise CommandError("invalid_argument", "{0:g} is outside '{1}' ({2:g}..{3:g}: {4})".format(raw, parameter.name, parameter.min, parameter.max, ", ".join(items)))
    return raw


def _display_to_raw(parameter, value):
    if isinstance(value, str):
        target = values.parse_display_number(value)
        if target is None:
            raise CommandError("invalid_argument", "Cannot read a number from {0!r} for '{1}'".format(value, parameter.name))
    else:
        target = _number(value, "Value for '{0}'".format(parameter.name))
    shown_low = values.display_number(parameter, parameter.min)
    shown_high = values.display_number(parameter, parameter.max)
    if shown_low is None or shown_high is None:
        raise CommandError("unsupported", "'{0}' has no numeric display value; pass units='raw'".format(parameter.name),
                           hint="Raw range: {0:g}..{1:g}".format(parameter.min, parameter.max))
    bottom, top = min(shown_low, shown_high), max(shown_low, shown_high)
    tolerance = 0.005 * (top - bottom) if math.isfinite(top - bottom) else 1e-6
    if target < bottom - tolerance or target > top + tolerance:
        raise CommandError("invalid_argument", "{0!r} is outside the range of '{1}' ({2} .. {3})".format(
            value, parameter.name, parameter.str_for_value(parameter.min), parameter.str_for_value(parameter.max)))
    return values.value_for_display_number(parameter, target)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_envelope(clip, parameter):
    """The clip's envelope for `parameter`, or None. Covers arrangement clips through automation_envelopes."""
    envelope = clip.automation_envelope(parameter)
    if envelope is not None:
        return envelope
    try:
        for candidate in clip.automation_envelopes:
            if refs.same(candidate.parameter, parameter):
                return candidate
    except Exception:
        pass
    return None


def parameter_label(song, owner, parameter):
    """{"parameter": "volume" | "pan" | "send:A" | name, "device": name path} for a track's parameter."""
    mixer = owner.mixer_device
    if refs.same(parameter, mixer.volume):
        return {"parameter": "volume"}
    if refs.same(parameter, mixer.panning):
        return {"parameter": "pan"}
    for position, send in enumerate(mixer.sends):
        if refs.same(send, parameter):
            return {"parameter": "send:" + refs.return_letter(position)}
    parent = parameter.canonical_parent
    if parent is not None and hasattr(parent, "class_name"):
        try:
            return {"parameter": parameter.name, "device": refs.device_path(parent)["name_path"]}
        except Exception:
            return {"parameter": parameter.name, "device": parent.name}
    return {"parameter": parameter.name}


def _clip_out(song, clip):
    out = refs.clip_ref(song, clip)
    out["name"] = clip.name
    return out


def _default_range(clip):
    if clip.looping:
        return float(clip.loop_start), float(clip.loop_end)
    return float(clip.start_marker), float(clip.end_marker)


def _automated(song, owner, clip):
    out = []
    try:
        envelopes = list(clip.automation_envelopes)
    except Exception:
        return out
    for envelope in envelopes:
        try:
            out.append(parameter_label(song, owner, envelope.parameter))
        except Exception:
            continue
    return out


def _display(parameter, raw):
    try:
        return str(parameter.str_for_value(raw))
    except Exception:
        return None


def _samples(envelope, parameter, start, end, count):
    count = max(0, min(int(count), MAX_SAMPLES))
    if count == 0:
        return []
    times = [start] if count == 1 or end <= start else [start + index * (end - start) / float(count - 1) for index in range(count)]
    out = []
    for time in times:
        raw = envelope.value_at_time(time)
        out.append({"time": round(time, 6), "value": round(float(raw), 6), "display": _display(parameter, raw)})
    return out


def _parameter_out(song, owner, parameter):
    out = parameter_label(song, owner, parameter)
    out["name"] = parameter.name
    out["range"] = [_display(parameter, parameter.min), _display(parameter, parameter.max)]
    return out


def _parse_points(song, points):
    if not isinstance(points, (list, tuple)) or not points:
        raise CommandError("invalid_argument", "points must be a non-empty list of {time, value} objects")
    if len(points) > MAX_EVENTS:
        raise CommandError("invalid_argument", "{0} points exceed the limit of {1}".format(len(points), MAX_EVENTS))
    parsed = []
    for position, point in enumerate(points):
        if not isinstance(point, dict) or "time" not in point or "value" not in point:
            raise CommandError("invalid_argument", "points[{0}] must be an object with 'time' and 'value', got {1!r}".format(position, point))
        parsed.append((values.parse_time(song, point["time"], "points[{0}].time".format(position)), point["value"]))
    parsed.sort(key=lambda item: item[0])  # stable: points sharing a time keep their order (a jump)
    return parsed


def _level(parameter, value, units, what):
    """A level that shapes do arithmetic on, as a number in `units` ('-6 dB' -> -6, pan '25L' -> -0.5)."""
    if value is None:
        return None
    if units == "raw" or not isinstance(value, str):
        return _number(value, what)
    if parameter.is_quantized:
        raise _shape_error("'{0}' is quantized: use type 'steps' or 'square' with item names, or numbers".format(parameter.name))
    if is_pan(parameter):
        return values.parse_pan(value)
    number = values.parse_display_number(value)
    if number is None:
        raise _shape_error("cannot read a number from {0} {1!r}".format(what, value))
    return number


def _shape_points(song, parameter, shape, start, end, units):
    if not isinstance(shape, dict):
        raise _shape_error("must be an object like {type: 'sine', from: -12, to: 0, period: '1 bar'}")
    known = {"type", "from", "to", "period", "steps"}
    unknown = sorted(set(shape) - known)
    if unknown:
        raise _shape_error("unknown keys {0}; use {1}".format(unknown, ", ".join(sorted(known))))
    kind = shape.get("type")
    low, high = shape.get("from"), shape.get("to")
    if kind in ("ramp", "sine", "triangle", "saw"):
        low, high = _level(parameter, low, units, "from"), _level(parameter, high, units, "to")
    period = shape.get("period")
    if period is not None:
        period = values.parse_length(song, period, "shape.period")
    return shape_events(kind, start, end, low=low, high=high, period=period, steps=shape.get("steps"))


def _resolve(song, track, slot, arrangement_clip, device, parameter):
    owner = refs.track(song, track)
    clip = refs.clip(song, track, slot=slot, arrangement_clip=arrangement_clip)
    target = None if parameter is None else refs.resolve_parameter(song, track, device, parameter)
    return owner, clip, target


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@command("write_automation", timeout=20.0)
def write_automation(ctx, track, parameter, slot=None, arrangement_clip=None, device=None, points=None, shape=None,
                     start=None, end=None, clear_range=True, units="display", samples=8):
    """Write a clip envelope for a mixer or device parameter from breakpoints or a shape."""
    import Live
    song = ctx.song
    if units not in UNITS:
        raise CommandError("invalid_argument", "units must be 'display' or 'raw', got {0!r}".format(units))
    if (points is None) == (shape is None):
        raise CommandError("invalid_argument", "Pass exactly one of points ([{time, value}, ...]) or shape ({type, from, to, period})")
    owner, clip, target = _resolve(song, track, slot, arrangement_clip, device, parameter)
    if not target.is_enabled:
        raise CommandError("unsupported", "Parameter '{0}' is disabled (macro-mapped or controlled by Max), so it cannot be automated".format(target.name))
    envelope = find_envelope(clip, target)
    if envelope is None and clip.is_arrangement_clip:
        raise CommandError("unsupported", "Arrangement clip has no envelope for '{0}', and Live's API cannot create one on arrangement clips".format(target.name), hint=ARRANGEMENT_HINT)
    range_start = None if start is None else values.parse_time(song, start, "start")
    range_end = None if end is None else values.parse_time(song, end, "end")
    if points is not None:
        breakpoints = _parse_points(song, points)
        range_start = breakpoints[0][0] if range_start is None else range_start
        range_end = breakpoints[-1][0] if range_end is None else range_end
    else:
        default_start, default_end = _default_range(clip)
        range_start = default_start if range_start is None else range_start
        range_end = default_end if range_end is None else range_end
        breakpoints = _shape_points(song, target, shape, range_start, range_end, units)
    if range_end < range_start:
        raise CommandError("invalid_argument", "end ({0:g}) is before start ({1:g})".format(range_end, range_start))
    cache = {}
    raw_points = [(time, raw_value(target, value, units, cache)) for time, value in breakpoints]
    created = envelope is None
    if created:
        try:
            envelope = clip.create_automation_envelope(target)
        except Exception as error:
            raise CommandError("live_error", "Live could not create an envelope for '{0}': {1}".format(target.name, error))
    elif clear_range:
        envelope.delete_events_in_range(range_start, range_end)
    for time, raw in raw_points:
        envelope.create_event(Live.Envelope.EnvelopeEvent(time, raw))
    return {
        "track": refs.track_label(song, owner),
        "clip": _clip_out(song, clip),
        "parameter": _parameter_out(song, owner, target),
        "created_envelope": created,
        "range": {"start": values.time_out(song, range_start), "end": values.time_out(song, range_end)},
        "points_written": len(raw_points),
        "samples": _samples(envelope, target, range_start, range_end, samples),
    }


@command("get_automation", readonly=True)
def get_automation(ctx, track, parameter=None, slot=None, arrangement_clip=None, device=None, samples=16):
    """Automated parameters of a clip; with a parameter, its breakpoints and sampled values."""
    song = ctx.song
    owner, clip, target = _resolve(song, track, slot, arrangement_clip, device, parameter)
    out = {
        "track": refs.track_label(song, owner),
        "clip": _clip_out(song, clip),
        "has_envelopes": bool(clip.has_envelopes),
        "automated": _automated(song, owner, clip),
    }
    if target is None:
        return out
    out["parameter"] = _parameter_out(song, owner, target)
    envelope = find_envelope(clip, target)
    if envelope is None:
        out["envelope"] = None
        return out
    start, end = _default_range(clip)
    events = list(envelope.events_in_range(min(start, 0.0) - 1e6, max(end, 0.0) + 1e6))
    shown = []
    for event in events[:MAX_EVENTS_OUT]:
        raw = envelope.value_at_time(event.time)
        shown.append({"time": round(float(event.time), 6), "value": round(float(raw), 6), "display": _display(target, raw)})
    out["envelope"] = {
        "event_count": len(events),
        "events": shown,
        "range": {"start": values.time_out(song, start), "end": values.time_out(song, end)},
        "samples": _samples(envelope, target, start, end, samples),
    }
    if len(events) > MAX_EVENTS_OUT:
        out["envelope"]["events_truncated"] = len(events) - MAX_EVENTS_OUT
    return out


@command("clear_automation")
def clear_automation(ctx, track, parameter=None, slot=None, arrangement_clip=None, device=None):
    """Clear one parameter's envelope, or every envelope, of a Session or arrangement clip."""
    song = ctx.song
    owner, clip, target = _resolve(song, track, slot, arrangement_clip, device, parameter)
    if target is None:
        cleared = "all"
        clip.clear_all_envelopes()
    else:
        cleared = parameter_label(song, owner, target)
        if find_envelope(clip, target) is None:
            cleared["note"] = "no envelope to clear"
        clip.clear_envelope(target)
    return {
        "track": refs.track_label(song, owner),
        "clip": _clip_out(song, clip),
        "cleared": cleared,
        "has_envelopes": bool(clip.has_envelopes),
        "automated": _automated(song, owner, clip),
    }
