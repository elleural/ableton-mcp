"""Notes ear (PRD section 7): exact checks on the MIDI notes of the stem clips in a Live snapshot.

It needs no audio and runs in well under a second, so it is the first check after any note edit. Input is a
listening snapshot (docs/listening-loop-plan.md section 5) and a spec; output is a report made by
`ears.report.make`, with one check result per stem and clip (rules), per tempo band (reports) or per
variation (clashes).

Vocabulary, as in spec.py: a *part* is one stem in one variation ("bassA"); a *band* is a tempo band of the
set ("MID") whose Live scene holds its clips. A part is resolved to a snapshot *track* by exact name and to a
*clip* by scene (layout "track", one track per variation, the real set) or by clip name (layout "clip"). Parts
that sit in the same clip for several bands (only kick and perc have per-band clips in the real set) are
analysed once and labelled with the band that owns the clip's scene: "bassA@MID".

Checks and their levels (the PRD table; a violation of a "report" level check is only information):

    set.names          fail    tracks and variation clips are named as the spec says
    set.unwarped       fail    stem clips are MIDI, or audio with warping off
    notes.in_key       fail    every pitch is in the key or a tone of the bar's chord (G# over E)
    notes.chord_tones  fail for bass, warn elsewhere   notes on beats 1 and 3 are tones of the bar's chord
    notes.clash        fail    no two stems of a variation a semitone apart for a sixteenth or longer
    notes.shared_stem  fail    a shared stem avoids a semitone from any chord tone any progression plays
    notes.loop_length  fail    the clip loops over the stem's bar count
    notes.grid         warn    onsets sit on the sixteenth grid
    notes.lead_rests   warn    the lead rests for the spec's share of sixteenth steps
    notes.kick_pattern report  the kick's 16-step bars and what they are
    notes.density      report  onsets per bar per stem
    notes.motif        report  how alike a stem's clips are in different bands
    notes.probability  info    notes with probability below 1 (takes differ)
    notes.midi_effects info    MIDI effects change what sounds; results are "before MIDI effects"

Times are beats from the start of the clip's loop; "where" is clip time "bar.beat.sixteenth" (1-based).
Pitches are named in Live's convention (C3 = 60). Muted notes and unpitched parts are left out of pitch
checks. Nothing here raises for a problem in the snapshot (missing track, no clip, audio instead of MIDI):
that is a failed set.names and skipped dependent checks. Only a wrong argument (unknown set or band, a bad
chord in the spec) raises, as SpecError.

The report (`ears.report.make("notes", "live set", checks, ...)`) carries, beside the checks:

    set, band, tempo   what was asked for
    values             what the compact report keeps: the tempo each band was judged at, and per stem the
                       share of sounding time on chord tones and the share of rests
    stems              full report only: the track, scene and clip each analysed stem was read from, its
                       length in bars, notes and onsets per bar
    roll               full report only: [{part, band, pitch, name, start, duration, status}] for the pitched
                       stems, status "chord" (a tone of the bar's chord), "scale" (in key, not in the chord)
                       or "out" (neither): the data of the piano-roll image
    warnings           things that are not checks (an unknown part asked for, notes skipped as malformed)
"""
import math
import re
from collections import OrderedDict
from itertools import combinations

from . import theory
from .report import beats_to_where, check, make, violation
from .spec import SpecError, load as load_spec

# The level of each check (PRD section 7). chord_tones is warn, but fail for the bass.
CHECK_LEVELS = OrderedDict([
    ("set.names", "fail"),
    ("set.unwarped", "fail"),
    ("notes.in_key", "fail"),
    ("notes.chord_tones", "warn"),
    ("notes.clash", "fail"),
    ("notes.shared_stem", "fail"),
    ("notes.loop_length", "fail"),
    ("notes.grid", "warn"),
    ("notes.lead_rests", "warn"),
    ("notes.kick_pattern", "report"),
    ("notes.density", "report"),
    ("notes.motif", "report"),
    ("notes.probability", "report"),
    ("notes.midi_effects", "report"),
])
ROLE_LEVELS = {"notes.chord_tones": {"bass": "fail"}}
CHECKS = tuple(CHECK_LEVELS)

EPS = 1e-6
DOWNBEAT_WINDOW = 0.0625   # beats: a start this close to a beat counts as on it (27 ms at 140 BPM)
LOOP_TOLERANCE = 1e-4      # beats: a loop length this close to the spec's counts as equal
MAX_ITEMS = 40             # items kept per check in the full report; the compact report trims further
MAX_LOOP_BEATS = 4096.0    # a loop longer than this (1,024 bars) is read only up to here
MAX_TILES = 1024           # copies of a short loop laid end to end when stems of different lengths are compared
MOTIF_ONSETS = 512         # onsets per clip compared by notes.motif
KICK_FLOOR = "four-on-the-floor"
KICK_HALF = "half-time"


class _Unit(object):
    """One part resolved to one clip of the snapshot, with the notes the checks read."""

    def __init__(self, part, key):
        self.part = part
        self.key = key
        self.selected = True
        self.track = None
        self.track_position = None
        self.clip = None
        self.scene = None          # the spec's scene name the clip was found in
        self.problem = None        # why there is no clip to analyse (a failed set.names)
        self.problem_item = None
        self.bands = []            # requested band names that resolve to this unit
        self.band = None           # the band that owns the clip's scene (else the first requested one)
        self.label = part.id       # "bassA@MID"
        self.tempo = None
        self.is_midi = None
        self.notes = None          # note dicts within the loop, or None when the snapshot has none to read
        self.notes_problem = None
        self.skipped_notes = 0
        self.loop_beats = None     # the clip's loop length, None when the snapshot does not give it
        self.window_start = 0.0
        self.window_length = 0.0
        self.midi_effects = []


class _Run(object):
    """State shared by the checks of one analyze_notes call."""

    def __init__(self, spec, set_name):
        self.spec = spec
        self.set_name = set_name
        self.beats_per_bar = spec.beats_per_bar
        self.step = 4.0 / spec.grid if spec.grid else 0.25   # beats per grid step (a sixteenth)
        self.buckets = OrderedDict((name, []) for name in CHECK_LEVELS)
        self.warnings = []
        self._tones = {}
        self._chords = {}
        self.effects_reported = set()

    # -- harmony: the chords a part's progressions play, bar by bar ----------------------------------

    def chords(self, part, bar):
        """[(progression id, chord symbol)] the part's progressions play in `bar` (0-based, wrapping)."""
        key = (part.id, bar)
        if key not in self._chords:
            found = []
            for progression in part.progressions or []:
                chords = self.spec.progressions.get(progression) or []
                if chords:
                    found.append((progression, chords[bar % len(chords)]))
            self._chords[key] = found
        return self._chords[key]

    def tones(self, part, bar):
        """Pitch classes of every chord the part's progressions play in `bar`."""
        key = (part.id, bar)
        if key not in self._tones:
            tones = set()
            for _, chord in self.chords(part, bar):
                tones.update(theory.chord_tones(chord))
            self._tones[key] = frozenset(tones)
        return self._tones[key]

    def describe(self, part, bar):
        """"Dm (D F A)", or "Dm (D F A) / E (E G# B)" when progressions disagree."""
        seen = []
        for _, chord in self.chords(part, bar):
            text = theory.describe_chord(chord)
            if text not in seen:
                seen.append(text)
        return " / ".join(seen)

    def where(self, beats):
        return beats_to_where(beats, self.beats_per_bar, self.spec.grid)

    def level(self, name, part=None):
        level = CHECK_LEVELS[name]
        if part is not None:
            level = ROLE_LEVELS.get(name, {}).get(part.role, level)
        return level


# -- small helpers ----------------------------------------------------------------------------------


def _number(value):
    """A finite float, or None for anything else (booleans included)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _norm(text):
    return "" if text is None else str(text).strip().lower()


def _list(value):
    """The value when it is a list, else an empty one: nothing in a snapshot is trusted to have the right type."""
    return list(value) if isinstance(value, (list, tuple)) else []


def _dicts(value):
    """(position, item) for the dict items of a list-like value."""
    return [(position, item) for position, item in enumerate(_list(value)) if isinstance(item, dict)]


def _fmt(value, digits=2):
    return "{0:g}".format(round(float(value), digits))


def _count(number, word):
    return "{0} {1}{2}".format(number, word, "" if str(number) == "1" else "s")


def _bars(beats, beats_per_bar):
    """"8 bars" for a length in beats."""
    return _count(_fmt(beats / beats_per_bar), "bar")


def _join(words):
    """"A", "A and B" or "A, B and C"."""
    words = [str(word) for word in words]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _beats_text(beats):
    """"beat 1" or "beats 1 and 3"."""
    ordered = sorted(beats)
    return ("beat " if len(ordered) == 1 else "beats ") + _join(ordered)


def _progressions_text(names):
    """"progression A" or "progressions A and B"."""
    return ("progression " if len(names) == 1 else "progressions ") + _join(names)


def _percent(share):
    return "n/a" if share is None else "{0:g}%".format(round(share * 100.0, 1))


def _snap(start):
    """A start within DOWNBEAT_WINDOW of a beat, moved onto it (a hair early or late is on the beat)."""
    nearest = round(start)
    return float(nearest) if abs(start - nearest) <= DOWNBEAT_WINDOW else start


def _bar_of(start, beats_per_bar):
    """0-based bar a note belongs to; a start just before a bar line belongs to the next bar."""
    return int(math.floor(_snap(start) / beats_per_bar + EPS))


def _downbeat(start, beats_per_bar):
    """(bar, beat) with a 0-based bar and 1-based beat when the note starts on a beat, else None."""
    nearest = round(start)
    if abs(start - nearest) > DOWNBEAT_WINDOW:
        return None
    bar = int(math.floor(nearest / beats_per_bar + EPS))
    return bar, int(round(nearest - bar * beats_per_bar)) + 1


def _is_midi_effect(device):
    kind = str(device.get("type", "")).strip().lower().replace(" ", "_").replace("-", "_")
    return kind in ("midi_effect", "midieffect", "4")   # Live's device type 4 is a MIDI effect


def _cap(items):
    return items[:MAX_ITEMS]


def _fields(unit):
    """Fields every check of a unit carries beside the result itself."""
    return {
        "band": unit.band,
        "scene": unit.scene,
        "bands": list(unit.bands) if len(unit.bands) > 1 else None,
        "before_midi_effects": True if unit.midi_effects else None,
    }


def _emit(run, name, status, owner, summary, **fields):
    """Add a result for the clip `owner` (a _Unit) to the report. `fields` are extra keys of the result
    (items, value, target, tolerance, unit, ...)."""
    extra = _fields(owner)
    extra.update(fields)
    items = extra.pop("items", None)
    if items and len(items) > MAX_ITEMS:
        extra["count"] = len(items)
    run.buckets[name].append(check(name, status, subject=owner.label, summary=summary,
                                   items=_cap(items) if items else None, **extra))


# -- arguments --------------------------------------------------------------------------------------


def _requested_bands(run, band):
    """The band dicts to analyse: the named band, every band of the set, or [None] when it defines none."""
    spec, set_name = run.spec, run.set_name
    bands = spec.bands(set_name)
    if not bands:
        if band is not None:
            run.warnings.append("Set {0!r} defines no tempo bands; band {1!r} ignored.".format(set_name, band))
        return [None]
    if band is None:
        return list(bands)
    if isinstance(band, dict):
        return [band]
    tempo = _number(band)
    if tempo is not None:
        return [spec.band(set_name, tempo=tempo)]
    return [spec.band(set_name, name=str(band))]


def _band_tempo(band):
    low, high = band["tempos"]
    return (float(low) + float(high)) / 2.0


def _select_parts(run, parts, wanted):
    """Ids of the parts to report on: all, or those matching the given ids, stems or track names."""
    ids = [part.id for part in parts]
    if not wanted:
        return set(ids)
    if isinstance(wanted, str):
        wanted = [word for word in re.split("[,\\s]+", wanted) if word]
    elif not isinstance(wanted, (list, tuple, set)):
        wanted = [wanted]
    chosen = set()
    for word in wanted:
        key = _norm(word)
        matches = [part.id for part in parts if key in (_norm(part.id), _norm(part.stem), _norm(part.track))]
        if matches:
            chosen.update(matches)
        else:
            run.warnings.append("No part {0!r} in set {1!r}; parts: {2}.".format(word, run.set_name, ", ".join(ids)))
    return chosen


def _validate_chords(spec, parts):
    """A chord the spec names that theory cannot read is a spec error, not a finding about the music."""
    used = []
    for part in parts:
        for progression in part.progressions or []:
            if progression not in used:
                used.append(progression)
    for progression in used:
        for chord in spec.progressions.get(progression) or []:
            try:
                theory.parse_chord(chord)
            except ValueError as error:
                raise SpecError("Progression {0}: {1}".format(progression, error)) from None


# -- resolving parts to clips ----------------------------------------------------------------------


def _scene_index(snapshot):
    """normalised scene name -> set of scene indices, from snapshot["scenes"]."""
    out = {}
    for position, scene in _dicts(snapshot.get("scenes")):
        index = scene.get("index", position)
        out.setdefault(_norm(scene.get("name")), set()).add(index if isinstance(index, int) else position)
    return out


def _in_scene(clip, scene, scene_index):
    """Whether a clip sits in the named scene: by the clip's scene name, else by its slot number."""
    name = clip.get("scene")
    if name not in (None, ""):
        return _norm(name) == _norm(scene)
    return isinstance(clip.get("slot"), int) and clip["slot"] in scene_index.get(_norm(scene), set())


def _clip_in_scene(track, scene, scene_index):
    """(position, clip) of the track's clip in the named scene, or None."""
    for position, clip in _dicts(track.get("clips")):
        if _in_scene(clip, scene, scene_index):
            return position, clip
    return None


def _choose_clip(track, part, scenes, layout, scene_index):
    """(position, clip, scene, None) for the part's clip, or (None, None, None, why not)."""
    clips = _dicts(track.get("clips"))
    if not clips:
        return None, None, None, "track {0!r} has no clips".format(track.get("name"))
    if layout == "clip" and part.clip_name:
        named = [(position, clip) for position, clip in clips if clip.get("name") == part.clip_name]
        if not named:
            names = ", ".join(repr(clip.get("name")) for _, clip in clips[:6])
            return None, None, None, "track {0!r} has no clip named {1!r} (clips: {2})".format(
                track.get("name"), part.clip_name, names)
        for scene in scenes:
            for position, clip in named:
                if _in_scene(clip, scene, scene_index):
                    return position, clip, scene, None
        position, clip = named[0]
        return position, clip, clip.get("scene") or None, None
    for scene in scenes:
        found = _clip_in_scene(track, scene, scene_index)
        if found:
            return found[0], found[1], scene, None
    if not scenes:
        position, clip = clips[0]
        return position, clip, clip.get("scene") or None, None
    return None, None, None, "track {0!r} has no clip in {1}".format(
        track.get("name"), " or ".join(repr(scene) for scene in scenes))


def _window(clip):
    """(start, length) in beats of the part of the clip that loops, or plays once when it does not loop."""
    start, end = _number(clip.get("loop_start")), _number(clip.get("loop_end"))
    if clip.get("looping") is False:
        marker_start, marker_end = _number(clip.get("start_marker")), _number(clip.get("end_marker"))
        if marker_start is not None and marker_end is not None:
            start, end = marker_start, marker_end
    if start is not None and end is not None and end > start:
        return start, end - start
    length = _number(clip.get("length"))
    if length is not None and length > 0:
        return (start or 0.0), length
    return (start or 0.0), None


def _load_clip(unit, run):
    """Fill the unit's loop window and notes from its clip (notes stay None when there is nothing to read)."""
    clip = unit.clip
    unit.is_midi = clip.get("is_midi") if clip.get("is_midi") is not None else ("notes" in clip)
    unit.window_start, unit.loop_beats = _window(clip)
    raw_notes = clip.get("notes")
    if not unit.is_midi:
        unit.notes_problem = "audio clip: the notes ear reads MIDI clips"
    elif not isinstance(raw_notes, (list, tuple)):
        unit.notes_problem = "the snapshot has no notes for this clip"
    if unit.notes_problem:
        unit.window_length = _bounded(run, unit, unit.loop_beats or 0.0)
        return
    parsed = []
    for raw in raw_notes:
        if not isinstance(raw, dict):
            unit.skipped_notes += 1
            continue
        if raw.get("mute"):
            continue   # muted notes do not sound
        pitch, start, duration = _number(raw.get("pitch")), _number(raw.get("start")), _number(raw.get("duration"))
        if pitch is None or start is None or duration is None or not 0 <= pitch <= 127:
            unit.skipped_notes += 1
            continue
        if duration <= EPS:
            continue
        probability = _number(raw.get("probability"))
        parsed.append((int(round(pitch)), start - unit.window_start, duration, 1.0 if probability is None else probability))
    length = unit.loop_beats
    if length is None:   # no loop length in the snapshot: take the notes' extent rounded up to whole bars
        extent = max([start + duration for _, start, duration, _ in parsed] or [0.0])
        length = max(math.ceil(extent / run.beats_per_bar - EPS), 1) * run.beats_per_bar
    length = _bounded(run, unit, length)
    unit.window_length = length
    notes = []
    for pitch, start, duration, probability in parsed:
        if start < -EPS or start >= length - EPS:
            continue   # outside the loop: it does not sound
        start = max(start, 0.0)
        end = min(start + duration, length)
        notes.append({"pitch": pitch, "start": start, "end": end, "probability": probability,
                      "name": theory.note_name(pitch)})
    notes.sort(key=lambda note: (note["start"], note["pitch"]))
    unit.notes = notes
    if unit.skipped_notes:
        run.warnings.append("{0}: {1} skipped (missing or out-of-range pitch, start or duration).".format(
            unit.label, _count(unit.skipped_notes, "malformed note")))


def _bounded(run, unit, length):
    """A loop length the checks can afford: longer than MAX_LOOP_BEATS is read only up to that, with a warning."""
    if length > MAX_LOOP_BEATS:
        run.warnings.append("{0}: the loop is {1:g} beats long; only the first {2:g} are read.".format(
            unit.label, length, MAX_LOOP_BEATS))
        return MAX_LOOP_BEATS
    return length


def _resolve_units(run, snapshot, parts, bands, selected, tempo_arg):
    """Resolve every part for every requested band. Returns (units, by_band) where
    by_band[(band name, part id)] is the unit that part uses in that band."""
    spec, set_name = run.spec, run.set_name
    tracks = _dicts(snapshot.get("tracks"))
    by_name = {}
    for position, track in tracks:
        if isinstance(track.get("name"), str):
            by_name.setdefault(track["name"], []).append((position, track))
    scene_index = _scene_index(snapshot)
    layout = spec.layout(set_name)
    band_names = [band["name"] if band else None for band in bands]
    units, by_band = OrderedDict(), {}
    for part in parts:
        found = by_name.get(part.track) or []
        if len(found) != 1:
            unit = units.setdefault(("!track", part.id), _Unit(part, ("!track", part.id)))
            unit.bands = list(band_names)
            if not found:
                near = [track.get("name") for _, track in tracks
                        if track.get("name") != part.track and _norm(track.get("name")).replace(" ", "") == _norm(part.track)]
                hint = " (found {0!r}: names must match exactly)".format(near[0]) if near else ""
                unit.problem = "no track named {0!r}{1}".format(part.track, hint)
                unit.problem_item = {"where": "set", "found": near[0] if near else None,
                                     "expected": "a track named {0!r}".format(part.track)}
            else:
                unit.problem = "{0} tracks are named {1!r}; names must be unique".format(len(found), part.track)
                unit.problem_item = {"where": "set", "found": "{0} tracks".format(len(found)),
                                     "expected": "one track named {0!r}".format(part.track)}
            for name in band_names:
                by_band[(name, part.id)] = unit
            continue
        track_position, track = found[0]
        for band in bands:
            name = band["name"] if band else None
            scenes = spec.scenes_for(set_name, band)
            position, clip, scene, why = _choose_clip(track, part, scenes, layout, scene_index)
            if clip is None:
                key = ("!clip", part.id, name)
                unit = units.setdefault(key, _Unit(part, key))
                unit.track, unit.track_position = track, track_position
                unit.problem = why
                unit.problem_item = {"where": "set", "found": None, "expected": "a clip for {0}".format(part.id)}
            else:
                key = (part.id, track_position, position)
                unit = units.get(key)
                if unit is None:
                    unit = units[key] = _Unit(part, key)
                    unit.track, unit.track_position, unit.clip, unit.scene = track, track_position, clip, scene
            unit.bands.append(name)
            by_band[(name, part.id)] = unit
    owner = {}
    band_by_name = {}
    for band in spec.bands(set_name):
        band_by_name[band["name"]] = band
        if band.get("scene"):
            owner.setdefault(_norm(band["scene"]), band["name"])
    for unit in units.values():
        unit.selected = unit.part.id in selected
        names = [name for name in unit.bands if name is not None]
        if unit.key[0] == "!track":
            unit.band = None
        else:
            unit.band = owner.get(_norm(unit.scene)) if unit.scene else None
            unit.band = unit.band or (names[0] if names else None)
        unit.label = unit.part.id + ("@" + unit.band if unit.band else "")
        tempos = [_band_tempo(band_by_name[name]) for name in names if name in band_by_name]
        if tempo_arg:
            unit.tempo = tempo_arg
        elif tempos:
            unit.tempo = min(tempos)   # a clip shared by several bands is judged at the strictest grid
        else:
            unit.tempo = _default_tempo(spec, set_name, snapshot)
        if not unit.tempo or unit.tempo <= 0:
            unit.tempo = 120.0   # a band that lists no usable tempo must not divide by zero
        if unit.clip is not None:
            _load_clip(unit, run)
            unit.midi_effects = [device.get("name") or device.get("class_name") or "MIDI effect"
                                 for device in _devices(unit.track) if _is_midi_effect(device) and device.get("active") is not False]
    return units, by_band


def _devices(track):
    return [device for _, device in _dicts(track.get("devices"))]


def _default_tempo(spec, set_name, snapshot):
    """Tempo for the grid check when neither the caller nor a band gives one."""
    try:
        return spec.middle_tempo(set_name)
    except SpecError:
        pass
    song = snapshot.get("song") if isinstance(snapshot.get("song"), dict) else {}
    return _number(song.get("tempo")) or 120.0


# -- checks on one clip ------------------------------------------------------------------------------


def _skip(run, name, unit, why):
    _emit(run, name, "skip", unit, why)


def _applicable(run, unit):
    """Names of the per-clip checks that read the notes and apply to this part."""
    part = unit.part
    names = []
    if part.pitched:
        names.append("notes.in_key")
        if len(part.progressions or []) == 1:
            names.append("notes.chord_tones")
    names.append("notes.grid")
    if part.rest_share is not None:
        names.append("notes.lead_rests")
    return names


def _unit_checks(run, unit):
    _check_names(run, unit)
    if unit.clip is None:
        for name in ["set.unwarped", "notes.loop_length"] + _applicable(run, unit):
            _skip(run, name, unit, unit.problem)
        return
    _check_unwarped(run, unit)
    _check_loop_length(run, unit)
    if unit.notes is None:
        for name in _applicable(run, unit):
            _skip(run, name, unit, unit.notes_problem)
    else:
        part = unit.part
        if part.pitched:
            _check_in_key(run, unit)
            if len(part.progressions or []) == 1:
                _check_chord_tones(run, unit)
        _check_grid(run, unit)
        if part.rest_share is not None:
            _check_lead_rests(run, unit)
        _check_probability(run, unit)
    _check_midi_effects(run, unit)


def _check_names(run, unit):
    part = unit.part
    if unit.problem:
        _emit(run, "set.names", "fail", unit, unit.problem, items=[unit.problem_item])
        return
    name = unit.clip.get("name")
    if part.variation and name != part.variation:
        _emit(run, "set.names", "fail", unit,
              "the clip on {0!r} is named {1!r}; variation clips are named {2!r}".format(part.track, name, part.variation),
              items=[{"where": "track {0!r}".format(part.track), "found": name,
                      "expected": "a clip named {0!r}".format(part.variation)}])
        return
    _emit(run, "set.names", "pass", unit, "track {0!r}, clip {1!r}{2}".format(
        part.track, name, " in " + unit.scene if unit.scene else ""))


def _check_unwarped(run, unit):
    if unit.is_midi:
        _emit(run, "set.unwarped", "pass", unit, "MIDI clip")
    elif unit.clip.get("warping"):
        _emit(run, "set.unwarped", "fail", unit, "audio clip with warping on; stems must be unwarped",
              items=[{"where": "clip {0!r}".format(unit.clip.get("name")), "found": "warping on", "expected": "warping off"}])
    else:
        _emit(run, "set.unwarped", "pass", unit, "audio clip with warping off")


def _check_loop_length(run, unit):
    part = unit.part
    if unit.loop_beats is None:
        _skip(run, "notes.loop_length", unit, "the snapshot gives no loop length for the clip")
        return
    found = unit.loop_beats / run.beats_per_bar
    expected = float(part.bars)
    extra = "" if unit.clip.get("looping") is not False else " (the clip is not looping)"
    if abs(found - expected) * run.beats_per_bar <= LOOP_TOLERANCE:
        _emit(run, "notes.loop_length", "pass", unit,
              "loops over {0}{1}".format(_count(_fmt(found), "bar"), extra), value=found, target=expected)
        return
    _emit(run, "notes.loop_length", violation(run.level("notes.loop_length")), unit,
          "loops over {0}; the spec says {1}{2}".format(_count(_fmt(found), "bar"), _count(_fmt(expected), "bar"), extra),
          items=[{"where": "clip {0!r}".format(unit.clip.get("name")), "found": _count(_fmt(found), "bar"),
                  "expected": _count(_fmt(expected), "bar")}],
          value=found, target=expected)


def _key_text(spec):
    return "{0} {1}".format(spec.key_name, spec.mode)


def _check_in_key(run, unit):
    spec, part = run.spec, unit.part
    bad = []
    for note in unit.notes:
        bar = _bar_of(note["start"], run.beats_per_bar)
        pc = note["pitch"] % 12
        if pc in spec.scale or pc in run.tones(part, bar):
            continue
        chords = run.describe(part, bar)
        bad.append({"where": run.where(note["start"]), "found": note["name"],
                    "expected": "in {0}{1}".format(_key_text(spec), ", or a tone of " + chords if chords else "")})
    total = len(unit.notes)
    if not total:
        _skip(run, "notes.in_key", unit, "no notes in the clip")
        return
    share = (total - len(bad)) / float(total)
    if not bad:
        _emit(run, "notes.in_key", "pass", unit,
              "all {0} in {1} or a tone of the bar's chord".format(_count(total, "note"), _key_text(spec)),
              value=share, target=1.0)
        return
    _emit(run, "notes.in_key", violation(run.level("notes.in_key")), unit,
          "{0} of {1} out of key ({2}); first {3} at {4}".format(
              len(bad), _count(total, "note"), _key_text(spec), bad[0]["found"], bad[0]["where"]),
          items=bad, value=share, target=1.0)


def _chord_time_share(run, unit):
    """Share of the part's sounding time that is on tones of the bar's chord (None when nothing sounds)."""
    part, size = unit.part, run.beats_per_bar
    total = on_chord = 0.0
    for note in unit.notes:
        pc = note["pitch"] % 12
        first = int(math.floor(note["start"] / size + EPS))
        last = int(math.floor((note["end"] - EPS) / size))
        for bar in range(first, last + 1):
            length = min(note["end"], (bar + 1) * size) - max(note["start"], bar * size)
            if length <= EPS:
                continue
            total += length
            if pc in run.tones(part, bar):
                on_chord += length
    return on_chord / total if total else None


def _check_chord_tones(run, unit):
    spec, part = run.spec, unit.part
    if not unit.notes:
        _skip(run, "notes.chord_tones", unit, "no notes in the clip")
        return
    beats = set(int(beat) for beat in spec.tolerance("chord_tone_beats", [1, 3]))
    level = run.level("notes.chord_tones", part)
    checked, bad = 0, []
    for note in unit.notes:
        located = _downbeat(note["start"], run.beats_per_bar)
        if located is None or located[1] not in beats:
            continue
        bar, _ = located
        chords = run.chords(part, bar)
        if not chords:
            continue
        checked += 1
        if note["pitch"] % 12 not in run.tones(part, bar):
            bad.append({"where": run.where(note["start"]), "found": note["name"],
                        "expected": "a tone of {0}".format(run.describe(part, bar))})
    share = _chord_time_share(run, unit)
    beat_text = _beats_text(beats)
    time_text = "{0} of sounding time is on chord tones".format(_percent(share))
    extra = {"downbeat_notes": checked, "level": level}
    if not checked:
        _emit(run, "notes.chord_tones", "pass", unit, "no notes start on {0}; {1}".format(beat_text, time_text),
              value=share, **extra)
        return
    if not bad:
        _emit(run, "notes.chord_tones", "pass", unit,
              "all {0} starting on {1} are chord tones; {2}".format(_count(checked, "note"), beat_text, time_text),
              value=share, **extra)
        return
    _emit(run, "notes.chord_tones", violation(level), unit,
          "{0} of {1} starting on {2} are not chord tones; first {3} at {4}; {5}".format(
              len(bad), _count(checked, "note"), beat_text, bad[0]["found"], bad[0]["where"], time_text),
          items=bad, value=share, **extra)


def _check_grid(run, unit):
    spec = run.spec
    if unit.midi_effects:
        _skip(run, "notes.grid", unit, "rhythm comes from audio onsets: MIDI effects ({0}) change when notes sound".format(
            ", ".join(unit.midi_effects)))
        return
    if not unit.notes:
        _skip(run, "notes.grid", unit, "no notes in the clip")
        return
    tolerance_ms = float(spec.tolerance("grid_ms", 10.0))
    beat_ms = 60000.0 / unit.tempo
    tolerance_beats = tolerance_ms / beat_ms
    bad, worst = [], 0.0
    for note in unit.notes:
        nearest = round(note["start"] / run.step) * run.step
        deviation = note["start"] - nearest
        worst = max(worst, abs(deviation) * beat_ms)
        if abs(deviation) > tolerance_beats + EPS:
            bad.append({"where": run.where(note["start"]), "found": "{0} by {1:g} ms".format(
                            "late" if deviation > 0 else "early", round(abs(deviation) * beat_ms, 1)),
                        "expected": "on the 1/{0} grid (within {1:g} ms)".format(spec.grid, tolerance_ms),
                        "note": note["name"], "deviation_ms": round(deviation * beat_ms, 1)})
    common = {"value": worst, "target": tolerance_ms, "unit": "ms", "tempo": unit.tempo}
    if not bad:
        _emit(run, "notes.grid", "pass", unit,
              "all {0} on the 1/{1} grid (largest deviation {2:g} ms at {3:g} BPM)".format(
                  _count(len(unit.notes), "onset"), spec.grid, round(worst, 1), unit.tempo), **common)
        return
    _emit(run, "notes.grid", violation(run.level("notes.grid")), unit,
          "{0} of {1} off the 1/{2} grid by more than {3:g} ms at {4:g} BPM; first {5} at {6}".format(
              len(bad), _count(len(unit.notes), "onset"), spec.grid, tolerance_ms, unit.tempo, bad[0]["found"], bad[0]["where"]),
          items=bad, **common)


def _rest_share(run, unit):
    """Share of sixteenth steps of the loop in which no note sounds (None for a loop without steps)."""
    total = int(round(unit.window_length / run.step))
    if total <= 0:
        return None
    starts = [0] * (total + 1)   # +1 where a note begins sounding, -1 after it stops: a running sum counts the notes
    for note in unit.notes:
        first = max(int(math.floor(note["start"] / run.step + EPS)), 0)
        last = min(int(math.ceil(note["end"] / run.step - EPS)) - 1, total - 1)
        if last >= first:
            starts[first] += 1
            starts[last + 1] -= 1
    sounding = running = 0
    for step in range(total):
        running += starts[step]
        sounding += 1 if running > 0 else 0
    return 1.0 - sounding / float(total)


def _check_lead_rests(run, unit):
    spec, part = run.spec, unit.part
    share = _rest_share(run, unit)
    if share is None:
        _skip(run, "notes.lead_rests", unit, "the loop has no sixteenth steps")
        return
    target = float(part.rest_share)
    tolerance = float(spec.tolerance("lead_rest_points", 10)) / 100.0
    common = {"value": share, "target": target, "tolerance": tolerance}
    text = "{0} of sixteenth steps are rests; the spec says {1} +/- {2:g} points".format(
        _percent(share), _percent(target), round(tolerance * 100, 1))
    if abs(share - target) <= tolerance + 1e-9:
        _emit(run, "notes.lead_rests", "pass", unit, text, **common)
        return
    _emit(run, "notes.lead_rests", violation(run.level("notes.lead_rests")), unit, text,
          items=[{"where": "clip {0!r}".format(unit.clip.get("name")), "found": _percent(share),
                  "expected": "{0} +/- {1:g} points".format(_percent(target), round(tolerance * 100, 1))}], **common)


def _check_probability(run, unit):
    uncertain = [note for note in unit.notes if note["probability"] < 1.0 - EPS]
    if not uncertain:
        return
    items = [{"where": run.where(note["start"]), "found": "{0} at probability {1:g}".format(note["name"], round(note["probability"], 3)),
              "expected": "probability 1 (takes differ otherwise)"} for note in uncertain]
    _emit(run, "notes.probability", "info", unit,
          "{0} with probability below 1: takes of this clip will differ".format(_count(len(uncertain), "note")),
          items=items, value=len(uncertain))


def _check_midi_effects(run, unit):
    if not unit.midi_effects or unit.part.id in run.effects_reported:
        return
    run.effects_reported.add(unit.part.id)
    _emit(run, "notes.midi_effects", "info", unit,
          "{0} on the track: the notes in the clip are not what sounds, so results for {1} are before MIDI effects; "
          "take its rhythm from audio onsets".format(", ".join(unit.midi_effects), unit.part.id),
          items=[{"where": "track {0!r}".format(unit.part.track), "found": name, "expected": "no MIDI effect to check the notes as written"}
                 for name in unit.midi_effects])


# -- checks across parts ------------------------------------------------------------------------------


def _tile(notes, loop, horizon):
    """The notes repeated every `loop` beats up to `horizon`, each cut at the end of its loop."""
    copies = 1
    if loop > EPS and horizon > loop + EPS:
        copies = min(int(math.ceil(horizon / loop - 1e-9)), MAX_TILES)
    out = []
    for copy in range(copies):
        offset = copy * loop if copies > 1 else 0.0
        limit = min(offset + loop, horizon) if copies > 1 else horizon
        for note in notes:
            start = note["start"] + offset
            if start >= limit - EPS:
                continue
            end = min(note["end"] + offset, limit)
            if end - start > EPS:
                out.append({"pitch": note["pitch"], "start": start, "end": end, "name": note["name"]})
    return out


def _semitone_overlaps(notes_a, notes_b, minimum):
    """[(a, b, start, end)] for notes a semitone apart (interval class 1) sounding together for `minimum` beats."""
    events = [(note["start"], 0, index, note) for index, note in enumerate(notes_a)]
    events += [(note["start"], 1, index, note) for index, note in enumerate(notes_b)]
    events.sort(key=lambda event: event[:3])
    active = ([], [])
    out = []
    for start, side, _, note in events:
        for bucket in active:
            bucket[:] = [other for other in bucket if other["end"] > start + EPS]
        for other in active[1 - side]:
            if theory.interval_class(note["pitch"], other["pitch"]) != 1:
                continue
            low, high = max(start, other["start"]), min(note["end"], other["end"])
            if high - low >= minimum - EPS:
                pair = (note, other) if side == 0 else (other, note)
                out.append((pair[0], pair[1], low, high))
        active[side].append(note)
    return out


def _clash_groups(run, parts, by_band, band_names):
    """Groups of parts that sound together: a variation's pitched parts plus the shared ones, per band.

    Bands that resolve to the same clips share one group. Returns a list of dicts."""
    variations = run.spec.variations(run.set_name) or [None]
    groups = OrderedDict()
    for name in band_names:
        for variation in variations:
            members = []
            for part in parts:
                if not part.pitched or (variation is not None and part.variation not in (variation, None)):
                    continue
                members.append((part, by_band.get((name, part.id))))
            key = (variation, tuple(unit.key if unit else ("none", part.id) for part, unit in members))
            group = groups.get(key)
            if group is None:
                group = groups[key] = {"variation": variation, "members": members, "bands": []}
            group["bands"].append(name)
    return list(groups.values())


def _clash_checks(run, parts, by_band, band_names):
    spec = run.spec
    minimum = float(spec.tolerance("clash_sixteenths", 1)) * run.step
    for group in _clash_groups(run, parts, by_band, band_names):
        variation = group["variation"]
        usable = [(part, unit) for part, unit in group["members"]
                  if unit is not None and unit.clip is not None and unit.notes]
        absent = [part.id for part, unit in group["members"]
                  if unit is None or unit.clip is None or unit.notes is None]
        if not any(unit.selected for _, unit in usable):
            continue   # nothing the caller asked about sits in this group
        owner = next((unit.band for part, unit in group["members"] if unit is not None and part.variation is not None and unit.band),
                     next((unit.band for _, unit in group["members"] if unit is not None and unit.band), None))
        what = "variation {0}".format(variation) if variation is not None else "all stems"
        subject = what + ("@" + owner if owner else "")
        fields = {"band": owner, "bands": [name for name in group["bands"] if name] if len(group["bands"]) > 1 else None}
        effects = [part.id for part, unit in usable if unit.midi_effects]
        if effects:
            fields["before_midi_effects"] = True
        if len(usable) < 2:
            run.buckets["notes.clash"].append(check(
                "notes.clash", "skip", subject=subject,
                summary="fewer than two pitched stems to compare" + (" ({0} missing)".format(", ".join(absent)) if absent else ""),
                **fields))
            continue
        horizon = max(unit.window_length for _, unit in usable)
        tiled = dict((part.id, _tile(unit.notes, unit.window_length, horizon)) for part, unit in usable)
        selected = set(part.id for part, unit in usable if unit.selected)
        found = []
        for (part_a, unit_a), (part_b, unit_b) in combinations(usable, 2):
            if part_a.id not in selected and part_b.id not in selected:
                continue
            for note_a, note_b, low, high in _semitone_overlaps(tiled[part_a.id], tiled[part_b.id], minimum):
                found.append((low, part_a.id, part_b.id, note_a, note_b, high - low))
        found.sort(key=lambda entry: (entry[0], entry[1], entry[2]))
        compared = "{0} compared over {1}".format(
            ", ".join(part.id for part, _ in usable), _count(_fmt(horizon / run.beats_per_bar), "bar"))
        missing = " ({0} not compared: no clip to read)".format(", ".join(absent)) if absent else ""
        if not found:
            run.buckets["notes.clash"].append(check(
                "notes.clash", "pass", subject=subject, summary="no stems a semitone apart; " + compared + missing,
                value=0, target=0, **fields))
            continue
        pairs = OrderedDict()
        for _, a, b, _, _, _ in found:
            pairs[(a, b)] = pairs.get((a, b), 0) + 1
        items = [{"where": run.where(low), "parts": [a, b],
                  "found": "{0} ({1}) against {2} ({3})".format(note_a["name"], a, note_b["name"], b),
                  "expected": "no pitches a semitone apart for {0} or longer".format(_count(_fmt(minimum / run.step), "sixteenth")),
                  "overlap_beats": round(length, 3)}
                 for low, a, b, note_a, note_b, length in found]
        extra = dict(fields)
        if len(items) > MAX_ITEMS:
            extra["count"] = len(items)
        by_pair = ", ".join("{0} / {1} x{2}".format(a, b, n) for (a, b), n in list(pairs.items())[:4])
        first = found[0]
        run.buckets["notes.clash"].append(check(
            "notes.clash", violation(run.level("notes.clash")), subject=subject,
            summary="{0} where stems sit a semitone apart ({1}); first at {2}: {3} ({4}) against {5} ({6})".format(
                _count(len(found), "overlap"), by_pair, run.where(first[0]), first[3]["name"], first[1], first[4]["name"], first[2]),
            items=_cap(items), value=len(found), target=0, **extra))


def _semitone_conflicts(run, part, bar, pc):
    """Texts like "G# of E (progression B)": the chord tones, in every progression the part follows, that the
    pitch class sits a semitone from in `bar`. Progressions that play the same chord are named together."""
    found = OrderedDict()
    for progression, chord in run.chords(part, bar):
        parsed = theory.parse_chord(chord)
        for tone in parsed.tones:
            if theory.interval_class(pc, tone) == 1:
                found.setdefault((theory.pc_name(tone, parsed.flats), chord), []).append(progression)
    return ["{0} of {1} ({2})".format(tone, chord, _progressions_text(names)) for (tone, chord), names in found.items()]


def _check_shared_stem(run, unit):
    spec, part = run.spec, unit.part
    minimum = float(spec.tolerance("clash_sixteenths", 1)) * run.step
    size = run.beats_per_bar
    bad, held = [], 0
    for note in unit.notes:
        pc = note["pitch"] % 12
        first = _bar_of(note["start"], size)
        last = max(int(math.floor((note["end"] - EPS) / size)), first)
        for bar in range(first, last + 1):
            if bar > first and min(note["end"], (bar + 1) * size) - bar * size < minimum - EPS:
                continue   # an overhang shorter than a sixteenth is not held in that bar
            held += 1
            conflicts = _semitone_conflicts(run, part, bar, pc)
            if conflicts:
                bad.append({"where": run.where(note["start"] if bar == first else bar * size), "found": note["name"],
                            "expected": "not a semitone from a tone of {0}".format(run.describe(part, bar)),
                            "against": conflicts[0] if len(conflicts) == 1 else conflicts})
    if not held:
        _skip(run, "notes.shared_stem", unit, "no notes in the clip")
        return
    share = (held - len(bad)) / float(held)
    if not bad:
        _emit(run, "notes.shared_stem", "pass", unit,
              "no held pitch is a semitone from a chord tone of {0}".format(_progressions_text(list(part.progressions or []))),
              value=share, target=1.0)
        return
    first = bad[0]
    against = first["against"] if isinstance(first["against"], str) else first["against"][0]
    _emit(run, "notes.shared_stem", violation(run.level("notes.shared_stem")), unit,
          "{0} of {1} held pitches sit a semitone from a chord tone that a progression plays in that bar; "
          "first {2} at {3}, against {4}".format(len(bad), held, first["found"], first["where"], against),
          items=bad, value=share, target=1.0)


def _shared_stem_checks(run, units):
    for unit in units:
        part = unit.part
        if unit.selected and part.variation is None and part.pitched and unit.clip is not None and unit.notes is not None:
            _check_shared_stem(run, unit)


# -- reports per band and across bands ---------------------------------------------------------------


def _kick_bars(run, unit):
    """One 16-step string per bar ("x---x---x---x---"): x where a kick starts, nearest step, ties to the earlier."""
    size = run.beats_per_bar
    steps = int(round(size / run.step))
    bars = max(int(math.ceil(unit.window_length / size - EPS)), 1)
    grid = [["-"] * steps for _ in range(bars)]
    for note in unit.notes:
        index = int(math.floor(note["start"] / run.step + 0.5 - 1e-9))
        bar, step = divmod(index, steps)
        if 0 <= bar < bars:
            grid[bar][step] = "x"
    return ["".join(row) for row in grid]


def _classify_kick(run, bars):
    """"four-on-the-floor", "half-time", "other" or "none" for a list of bar strings."""
    per_beat = int(round(1.0 / run.step))
    beats = int(round(run.beats_per_bar))
    hits = [set(index for index, char in enumerate(bar) if char == "x") for bar in bars]
    if not any(hits):
        return "none"
    every_beat = set(beat * per_beat for beat in range(beats))
    half = set(beat * per_beat for beat in range(0, beats, 2))
    off_half = every_beat - half
    if all(every_beat <= bar for bar in hits):
        return KICK_FLOOR
    if all(half <= bar and not (off_half & bar) for bar in hits):
        return KICK_HALF
    return "other"


def _kick_pattern_checks(run, units_by_band, band_by_name):
    for name, units in units_by_band.items():
        for unit in units:
            if unit.part.role != "kick" or unit.notes is None:
                continue
            bars = _kick_bars(run, unit)
            found = _classify_kick(run, bars)
            band = band_by_name.get(name)
            expected = band.get("kick") if band else None
            per_beat = int(round(1.0 / run.step))
            extra_hits = sum(1 for bar in bars for index, char in enumerate(bar) if char == "x" and index % per_beat)
            if expected is None:
                verdict = "; the spec names no kick pattern for {0}".format(name or "this set")
            elif expected == found:
                verdict = ", as the spec says"
            else:
                verdict = ", but the spec says {0}".format(expected)
            label = unit.part.id + ("@" + name if name else "")
            run.buckets["notes.kick_pattern"].append(check(
                "notes.kick_pattern", violation("report"), subject=label,
                summary="{0} ({1}){2}".format(found, " | ".join(bars), verdict),
                items=[{"bar": index + 1, "pattern": bar} for index, bar in enumerate(bars)],
                value=found, target=expected, band=name, scene=unit.scene,
                off_beat_hits=extra_hits, matches=(expected == found) if expected else None,
                before_midi_effects=True if unit.midi_effects else None))


def _onsets_per_bar(run, unit):
    onsets = set(round(note["start"], 4) for note in unit.notes)
    bars = unit.window_length / run.beats_per_bar
    return (len(onsets) / bars if bars > 0 else 0.0), len(onsets), bars


def _density_checks(run, units_by_band):
    for name, units in units_by_band.items():
        usable = [unit for unit in units if unit.notes is not None]
        if not usable:
            continue
        items, parts = [], []
        for unit in usable:
            per_bar, onsets, bars = _onsets_per_bar(run, unit)
            items.append({"part": unit.part.id, "onsets_per_bar": round(per_bar, 2), "onsets": onsets, "bars": round(bars, 3)})
            parts.append("{0} {1:g}".format(unit.part.id, round(per_bar, 2)))
        run.buckets["notes.density"].append(check(
            "notes.density", violation("report"), subject=name or run.set_name,
            summary="onsets per bar: " + ", ".join(parts), items=items, band=name))


def _contour(run, unit):
    """(intervals, rhythm) of a clip: semitones between successive onsets (the lowest note of a chord) and the
    gaps between onsets in grid steps. Two clips with the same contour sound like the same figure."""
    lowest = {}
    for note in unit.notes:
        key = round(note["start"], 4)
        lowest[key] = min(lowest.get(key, 1000), note["pitch"])
    times = sorted(lowest)[:MOTIF_ONSETS]
    intervals = [lowest[times[index]] - lowest[times[index - 1]] for index in range(1, len(times))]
    rhythm = [round((times[index] - times[index - 1]) / run.step, 2) for index in range(1, len(times))]
    return intervals, rhythm


def _edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def _similarity(a, b):
    """1 for equal sequences, 0 for nothing in common (edit distance over the longer length); None for two empty ones."""
    longest = max(len(a), len(b))
    if not longest:
        return None
    return 1.0 - _edit_distance(a, b) / float(longest)


def _motif_check(run, units_by_band, band_names, band_asked):
    subject = run.set_name
    if len(run.spec.bands(run.set_name)) < 2:
        run.buckets["notes.motif"].append(check(
            "notes.motif", "skip", subject=subject, summary="the set has fewer than two tempo bands to compare"))
        return
    if band_asked:
        run.buckets["notes.motif"].append(check(
            "notes.motif", "skip", subject=subject,
            summary="compares a stem's clips across tempo bands; run without a band to see it"))
        return
    by_part = OrderedDict()
    for name in band_names:
        for unit in units_by_band.get(name, []):
            if unit.notes is None:
                continue
            distinct = by_part.setdefault(unit.part.id, OrderedDict())
            distinct.setdefault(unit.key, unit)
    items, same, differing = [], [], []
    for part_id, distinct in by_part.items():
        units = list(distinct.values())
        if len(units) == 1:
            same.append(part_id)
            items.append({"part": part_id, "same_clip": True, "scene": units[0].scene})
            continue
        similarities = []
        for unit_a, unit_b in combinations(units, 2):
            intervals_a, rhythm_a = _contour(run, unit_a)
            intervals_b, rhythm_b = _contour(run, unit_b)
            rhythm = _similarity(rhythm_a, rhythm_b)
            pitched = unit_a.part.pitched
            pitch = _similarity(intervals_a, intervals_b) if pitched else None
            parts = [value for value in (pitch, rhythm) if value is not None]
            overall = sum(parts) / len(parts) if parts else None
            similarities.append(overall)
            items.append({"part": part_id, "bands": "{0} vs {1}".format(unit_a.band or unit_a.bands[0], unit_b.band or unit_b.bands[0]),
                          "similarity": None if overall is None else round(overall, 3),
                          "intervals": None if pitch is None else round(pitch, 3),
                          "rhythm": None if rhythm is None else round(rhythm, 3)})
        known = [value for value in similarities if value is not None]
        differing.append((part_id, sum(known) / len(known) if known else None))
    if not by_part:
        run.buckets["notes.motif"].append(check("notes.motif", "skip", subject=subject, summary="no clips with notes to compare"))
        return
    if not differing:
        summary = "every band uses the same clip for every stem: nothing to compare"
        value = 1.0
    else:
        parts = ["{0} {1}".format(part_id, "n/a" if value is None else _fmt(value)) for part_id, value in differing]
        summary = "similarity between bands (1 = same figure): {0}".format(", ".join(parts))
        if same:
            summary += "; same clip in every band: {0}".format(", ".join(same))
        known = [value for _, value in differing if value is not None]
        value = sum(known) / len(known) if known else None
    run.buckets["notes.motif"].append(check(
        "notes.motif", violation("report"), subject=subject, summary=summary, items=items, value=value))


# -- the piano roll and the report ------------------------------------------------------------------


def _roll(run, units):
    """Notes of the pitched parts with how each sits against the key and the bar's chord: chord, scale or out."""
    spec, out = run.spec, []
    for unit in units:
        part = unit.part
        if not unit.selected or not part.pitched or unit.notes is None:
            continue
        for note in unit.notes:
            pc = note["pitch"] % 12
            if pc in run.tones(part, _bar_of(note["start"], run.beats_per_bar)):
                status = "chord"
            elif pc in spec.scale:
                status = "scale"
            else:
                status = "out"
            out.append({"part": part.id, "band": unit.band, "pitch": note["pitch"], "name": note["name"],
                        "start": round(note["start"], 4), "duration": round(note["end"] - note["start"], 4), "status": status})
    return out


def analyze_notes(snapshot, spec, set_name=None, band=None, parts=None, tempo=None):
    """The notes ear on a listening snapshot: a report made by `ears.report.make("notes", ...)`.

    snapshot  the dict of docs/listening-loop-plan.md section 5 (tracks with clips and notes, scenes)
    spec      a Spec, a spec dict, or a name or path `ears.spec.load` accepts
    set_name  the spec's set ("neon"); default: the spec's first set
    band      a band name ("MID"), a tempo in BPM, or None for every band of the set. With no band the
              per-band checks run for every band and the cross-band report (notes.motif) runs once
    parts     limit the report to these parts: ids ("bassA"), stems ("bass") or track names
    tempo     BPM for the grid check's millisecond tolerance; default: the band's middle tempo

    Raises SpecError for an unknown set, band or chord; a problem in the snapshot never raises, it is a failed
    set.names with the dependent checks skipped.
    """
    spec = load_spec(spec)
    set_name = spec.set_name(set_name)
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    tempo_arg = None
    if tempo is not None:
        tempo_arg = _number(tempo)
        if tempo_arg is None or tempo_arg <= 0:
            raise ValueError("tempo must be a positive number of BPM, got {0!r}".format(tempo))
    run = _Run(spec, set_name)
    bands = _requested_bands(run, band)
    band_names = [entry["name"] if entry else None for entry in bands]
    parts_all = spec.parts(set_name)
    _validate_chords(spec, parts_all)
    selected = _select_parts(run, parts_all, parts)
    units_map, by_band = _resolve_units(run, snapshot, parts_all, bands, selected, tempo_arg)
    units = list(units_map.values())
    for unit in units:
        if unit.selected:
            _unit_checks(run, unit)
    _shared_stem_checks(run, units)
    _clash_checks(run, parts_all, by_band, band_names)
    units_by_band = OrderedDict()
    for name in band_names:
        seen = []
        for part in parts_all:
            unit = by_band.get((name, part.id))
            if unit is not None and unit.selected and unit.clip is not None and unit not in seen:
                seen.append(unit)
        units_by_band[name] = seen
    band_by_name = dict((entry["name"], entry) for entry in spec.bands(set_name))
    _kick_pattern_checks(run, units_by_band, band_by_name)
    _density_checks(run, units_by_band)
    _motif_check(run, units_by_band, band_names, band is not None)

    checks = [result for name in CHECK_LEVELS for result in run.buckets[name]]
    values = _values(run, units, band_names, tempo_arg)
    asked = band_names[0] if band is not None and len(band_names) == 1 else None
    return make("notes", "live set", checks, set=set_name, band=asked, tempo=tempo_arg, values=values,
                stems=_stems(run, units), roll=_roll(run, units), warnings=run.warnings or None)


def _values(run, units, band_names, tempo_arg):
    """The numbers the compact report keeps: the tempo each band was judged at, and the share of sounding time
    on chord tones and the share of rests for the stems that have them."""
    values = OrderedDict()
    tempos = OrderedDict()
    for entry in run.spec.bands(run.set_name):
        if entry["name"] in band_names:
            tempos[entry["name"]] = tempo_arg or _band_tempo(entry)
    if tempos:
        values["tempos"] = tempos
    chord_share, rest_share = OrderedDict(), OrderedDict()
    for unit in units:
        if not unit.selected or unit.notes is None:
            continue
        part = unit.part
        if part.pitched and len(part.progressions or []) == 1 and unit.notes:
            share = _chord_time_share(run, unit)
            if share is not None:
                chord_share[unit.label] = round(share, 3)
        if part.rest_share is not None:
            share = _rest_share(run, unit)
            if share is not None:
                rest_share[unit.label] = round(share, 3)
    for key, table in (("chord_tone_share", chord_share), ("rest_share", rest_share)):
        if table:
            values[key] = table
    return dict(values)


def _stems(run, units):
    """Which clip each analysed stem was read from, with its size and onset rate (full report only)."""
    out = OrderedDict()
    for unit in units:
        if not unit.selected or unit.clip is None:
            continue
        entry = OrderedDict([("track", unit.part.track), ("scene", unit.scene), ("clip", unit.clip.get("name")),
                             ("bars", round(unit.window_length / run.beats_per_bar, 3))])
        if unit.notes is not None:
            entry["notes"] = len(unit.notes)
            entry["onsets_per_bar"] = round(_onsets_per_bar(run, unit)[0], 2)
        else:
            entry["audio"] = True
        if len(unit.bands) > 1:
            entry["bands"] = list(unit.bands)
        out[unit.label] = dict(entry)
    return dict(out)
