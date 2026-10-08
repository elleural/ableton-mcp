"""Spec files: the musical requirements every check reads (PRD section 4, "musical requirements are data").

A spec names the key, the progressions, the stems with their loop lengths and variations, the layer
tiers, the sets (tempos, which progression each variation plays, how stems map to Live tracks and
scenes) and the targets and tolerances. When the brief changes, the spec changes and the code does not.

Vocabulary:
  stem       a layer of the brief ("bass"), with a loop length in bars
  part       one stem in one variation, named like the shipped file ("bassA"; "kick" when shared)
  set        a music set ("neon"): its tempos, its variation -> progression map, its track layout
  band       a tempo band of a set ("MID", 130-150 BPM) and the Live scene that holds its clips
"""
import json
import os
from collections import OrderedDict
from pathlib import Path

BUNDLED_DIR = Path(__file__).resolve().parent / "specs"
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MODES = {
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "major": (0, 2, 4, 5, 7, 9, 11),
}

# Tolerances the PRD marks with a dagger; a spec may override any of them under "tolerances".
DEFAULT_TOLERANCES = {
    "lufs_i_lu": 0.5,
    "tempo_consistency_lu": 1.0,
    "mono_sub_db": 1.0,
    "sum_null_db": 40.0,
    "bar_alignment_ms": 5.0,
    "duration_ms": 1.0,
    "seam_fold_db": 30.0,
    "seam_click_db": 6.0,
    "start_ms": 5.0,
    "lead_rest_points": 10,
    "grid_ms": 10.0,
    "chord_tone_beats": [1, 3],
    "clash_sixteenths": 1,
    "compare_noise_db": 0.5,
    "phone_highpass_hz": 200,
}


class SpecError(ValueError):
    """The spec file is missing, malformed, or does not define what a check needs."""


def pitch_class(name):
    """0..11 for a note name such as "A", "C#", "Bb" or "G♯"."""
    text = str(name).strip().replace("♯", "#").replace("♭", "b")
    if not text or text[0].upper() not in _PITCH_CLASS:
        raise SpecError("Not a note name: {0!r}".format(name))
    value = _PITCH_CLASS[text[0].upper()]
    for accidental in text[1:]:
        if accidental == "#":
            value += 1
        elif accidental == "b":
            value -= 1
        else:
            raise SpecError("Not a note name: {0!r}".format(name))
    return value % 12


def parse_key(text):
    """("A", 9, "minor") from "A minor", "Am" or "A natural minor"."""
    words = str(text).replace("natural", " ").split()
    if not words:
        raise SpecError("Empty key")
    tonic = words[0]
    mode = " ".join(words[1:]).strip().lower() or "major"
    if tonic.endswith("m") and len(tonic) > 1 and mode == "major" and len(words) == 1:
        tonic, mode = tonic[:-1], "minor"
    if mode in ("min", "aeolian"):
        mode = "minor"
    if mode in ("maj", "ionian"):
        mode = "major"
    if mode not in MODES:
        raise SpecError("Unsupported mode {0!r} in key {1!r}; use major or minor".format(mode, text))
    return tonic, pitch_class(tonic), mode


class Part(object):
    """One stem in one variation: the unit that is a track in Live and a file in the game."""

    __slots__ = ("id", "stem", "variation", "bars", "pitched", "role", "track", "clip_name", "progressions",
                 "rest_share", "set")

    def __init__(self, **fields):
        for name in self.__slots__:
            setattr(self, name, fields.get(name))

    def to_dict(self):
        return dict((name, getattr(self, name)) for name in self.__slots__)

    def __repr__(self):
        return "Part({0}, track={1!r})".format(self.id, self.track)


class Spec(object):
    """A loaded spec file with helpers for the checks."""

    def __init__(self, data, path=None):
        if not isinstance(data, dict):
            raise SpecError("A spec must be a JSON object, got {0}".format(type(data).__name__))
        self.data = data
        self.path = str(path) if path else None
        self.name = data.get("name") or (Path(path).stem.split(".")[0] if path else "spec")
        try:
            self.key_name, self.tonic, self.mode = parse_key(data["key"])
        except KeyError:
            raise SpecError("The spec has no key")
        self.scale = frozenset((self.tonic + step) % 12 for step in MODES[self.mode])
        meter = str(data.get("meter", "4/4"))
        try:
            numerator, denominator = (int(part) for part in meter.split("/"))
        except ValueError:
            raise SpecError("meter must look like '4/4', got {0!r}".format(meter))
        self.meter = meter
        self.beats_per_bar = numerator * 4.0 / denominator   # Live beats are quarter notes
        self.grid = int(data.get("grid", 16))
        self.a4_hz = float(data.get("a4_hz", 440.0))
        self.progressions = OrderedDict((key, list(value)) for key, value in (data.get("progressions") or {}).items())
        self.stems = OrderedDict(data.get("stems") or {})
        if not self.stems:
            raise SpecError("The spec defines no stems")
        self.tiers = OrderedDict(data.get("tiers") or {})
        self.sets = OrderedDict(data.get("sets") or {})
        if not self.sets:
            raise SpecError("The spec defines no sets")
        self.targets = dict(data.get("targets") or {})
        self.tolerances = dict(DEFAULT_TOLERANCES, **(data.get("tolerances") or {}))
        self.analyser = dict(data.get("analyser") or {})
        self.style = dict(data.get("style") or {})
        self.levels = dict(data.get("levels") or {})
        for stem, entry in self.stems.items():
            if not isinstance(entry, dict):
                raise SpecError("Stem {0!r} must be an object".format(stem))
            try:
                bars = int(entry.get("bars"))
            except (TypeError, ValueError):
                raise SpecError("Stem {0!r} needs bars (its loop length), got {1!r}".format(stem, entry.get("bars")))
            if bars <= 0:
                raise SpecError("Stem {0!r} bars must be positive".format(stem))
        for tier, stems in self.tiers.items():
            for stem in stems:
                if stem not in self.stems:
                    raise SpecError("Tier {0} names unknown stem {1!r}".format(tier, stem))
        for name, entry in self.sets.items():
            for variation, progression in (entry.get("variations") or {}).items():
                if progression not in self.progressions:
                    raise SpecError("Set {0!r} variation {1} plays unknown progression {2!r}".format(name, variation, progression))

    # -- general ------------------------------------------------------------------------------

    def tolerance(self, key, default=None):
        return self.tolerances.get(key, default)

    def target(self, key, default=None):
        return self.targets.get(key, default)

    def bar_seconds(self, bpm):
        return self.beats_per_bar * 60.0 / float(bpm)

    def tail_seconds(self):
        return float(self.targets.get("tail_ms", 50.0)) / 1000.0

    def to_dict(self):
        return self.data

    # -- sets, bands, parts -----------------------------------------------------------------------

    def set_names(self):
        return list(self.sets)

    def set_spec(self, name):
        if name is None:
            return self.set_spec(self.default_set())
        key = str(name).strip().lower()
        for candidate in self.sets:
            if candidate.lower() == key:
                return self.sets[candidate]
        raise SpecError("Spec {0!r} has no set {1!r}; sets: {2}".format(self.name, name, ", ".join(self.sets)))

    def set_name(self, name):
        """The canonical spelling of a set name (default: the first set)."""
        if name is None:
            return self.default_set()
        key = str(name).strip().lower()
        for candidate in self.sets:
            if candidate.lower() == key:
                return candidate
        raise SpecError("Spec {0!r} has no set {1!r}; sets: {2}".format(self.name, name, ", ".join(self.sets)))

    def default_set(self):
        return next(iter(self.sets))

    def tempos(self, set_name):
        return [float(tempo) for tempo in self.set_spec(set_name).get("tempos") or []]

    def middle_tempo(self, set_name):
        tempos = sorted(self.tempos(set_name))
        if not tempos:
            raise SpecError("Set {0!r} lists no tempos".format(set_name))
        return tempos[len(tempos) // 2]

    def variations(self, set_name):
        """Variation letters the set plays, in order ("A", "B")."""
        return list((self.set_spec(set_name).get("variations") or {}).keys())

    def progression(self, set_name, variation):
        """Chord names, one per bar, of the progression a variation plays in a set."""
        mapping = self.set_spec(set_name).get("variations") or {}
        if variation not in mapping:
            raise SpecError("Set {0!r} has no variation {1!r}; variations: {2}".format(set_name, variation, ", ".join(mapping) or "(none)"))
        return list(self.progressions[mapping[variation]])

    def progression_id(self, set_name, variation):
        return (self.set_spec(set_name).get("variations") or {})[variation]

    def bands(self, set_name):
        return list(self.set_spec(set_name).get("bands") or [])

    def band(self, set_name, tempo=None, name=None):
        """The band dict for a tempo (BPM) or a band name; None when the set defines no bands."""
        bands = self.bands(set_name)
        if not bands:
            return None
        if name is not None:
            for band in bands:
                if band["name"].lower() == str(name).lower():
                    return band
            raise SpecError("Set {0!r} has no band {1!r}; bands: {2}".format(set_name, name, ", ".join(b["name"] for b in bands)))
        tempo = float(tempo)
        for band in bands:
            low, high = band["tempos"]
            if float(low) - 1e-6 <= tempo <= float(high) + 1e-6:
                return band
        raise SpecError("{0:g} BPM is in no band of set {1!r}: {2}".format(
            tempo, set_name, ", ".join("{0} {1}-{2}".format(b["name"], *b["tempos"]) for b in bands)))

    def scenes_for(self, set_name, band=None):
        """Scene names to look for a part's clip in, most specific first (the band's, then the default)."""
        entry = self.set_spec(set_name)
        scenes = []
        if band and band.get("scene"):
            scenes.append(band["scene"])
        if entry.get("default_scene") and entry["default_scene"] not in scenes:
            scenes.append(entry["default_scene"])
        return scenes

    def layout(self, set_name):
        """"track" when each variation has its own track ("{stem}{variation}"), else "clip" (clips named A, B)."""
        return "track" if "{variation}" in self.track_pattern(set_name) else "clip"

    def track_pattern(self, set_name):
        return str(self.set_spec(set_name).get("tracks") or "{stem}")

    def track_name(self, set_name, stem, variation=None):
        pattern = self.track_pattern(set_name)
        return pattern.format(stem=stem, variation=variation or "") if "{variation}" in pattern else pattern.format(stem=stem)

    def parts(self, set_name=None, variations=None):
        """Every part of a set, in stem order; `variations` limits the varied stems ("A", ["A", "B"])."""
        set_name = self.set_name(set_name)
        set_variations = self.variations(set_name)
        if isinstance(variations, str):
            variations = [variations]
        wanted = list(variations) if variations else set_variations
        unknown = [v for v in wanted if v not in set_variations]
        if unknown:
            raise SpecError("Set {0!r} has no variation {1}; variations: {2}".format(set_name, ", ".join(unknown), ", ".join(set_variations)))
        layout = self.layout(set_name)
        all_progressions = []
        for variation in set_variations:
            progression = self.progression_id(set_name, variation)
            if progression not in all_progressions:
                all_progressions.append(progression)
        parts = []
        for stem, entry in self.stems.items():
            stem_variations = [v for v in entry.get("variations") or [] if v in set_variations]
            common = dict(stem=stem, bars=int(entry["bars"]), pitched=bool(entry.get("pitched", True)),
                          role=entry.get("role", stem), rest_share=entry.get("rest_share"), set=set_name)
            if stem_variations:
                for variation in stem_variations:
                    if variation not in wanted:
                        continue
                    parts.append(Part(
                        id=stem + variation, variation=variation, track=self.track_name(set_name, stem, variation),
                        clip_name=variation if layout == "clip" else None,
                        progressions=[self.progression_id(set_name, variation)], **common))
            else:
                parts.append(Part(id=stem, variation=None, track=self.track_name(set_name, stem, None), clip_name=None,
                                  progressions=list(all_progressions), **common))
        return parts

    def part(self, set_name, part_id):
        for part in self.parts(set_name):
            if part.id == part_id:
                return part
        raise SpecError("Set {0!r} has no part {1!r}; parts: {2}".format(set_name, part_id, ", ".join(p.id for p in self.parts(set_name))))

    def fills(self, set_name):
        return dict(self.set_spec(set_name).get("fills") or {})

    def longest_bars(self, parts):
        return max(int(part.bars) for part in parts) if parts else 0

    # -- tiers --------------------------------------------------------------------------------

    def tier_stems(self):
        """OrderedDict tier -> stems the tier contains, cumulatively (T3 = T1 + T2 + T3 stems)."""
        out, running = OrderedDict(), []
        for tier, stems in self.tiers.items():
            running = running + [stem for stem in stems if stem not in running]
            out[tier] = list(running)
        return out

    def tier_parts(self, set_name, variation):
        """OrderedDict tier -> part ids for one variation, cumulatively."""
        parts = self.parts(set_name, variations=[variation])
        by_stem = dict((part.stem, part.id) for part in parts)
        return OrderedDict((tier, [by_stem[stem] for stem in stems if stem in by_stem])
                           for tier, stems in self.tier_stems().items())


def bundled():
    """Names of the specs shipped with ears ("nova")."""
    return sorted(path.name.split(".")[0] for path in BUNDLED_DIR.glob("*.spec.json"))


def resolve_path(ref=None, home=None):
    """The spec file a reference points to: a path, a bundled name, $EARS_SPEC or <home>/spec.json."""
    candidates = []
    if ref:
        text = str(ref)
        if os.sep in text or text.endswith(".json") or text.startswith("~"):
            candidates.append(Path(text).expanduser())
        else:
            candidates.append(BUNDLED_DIR / "{0}.spec.json".format(text))
    else:
        if os.environ.get("EARS_SPEC"):
            return resolve_path(os.environ["EARS_SPEC"], home)
        if home:
            candidates.append(Path(home) / "spec.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    hint = "Pass spec= a path or one of the bundled specs: {0}".format(", ".join(bundled()) or "(none)")
    if ref:
        raise SpecError("No spec file {0!r}. {1}".format(ref, hint))
    raise SpecError("No spec given, EARS_SPEC is unset and {0} does not exist. {1}".format(
        Path(home) / "spec.json" if home else "<ears home>/spec.json", hint))


def load(ref=None, home=None):
    """Load a spec by path, bundled name ("nova"), $EARS_SPEC, or <home>/spec.json."""
    if isinstance(ref, Spec):
        return ref
    if isinstance(ref, dict):
        return Spec(ref)
    path = resolve_path(ref, home)
    try:
        data = json.loads(path.read_text())
    except ValueError as error:
        raise SpecError("Spec {0} is not valid JSON: {1}".format(path, error))
    return Spec(data, path)
