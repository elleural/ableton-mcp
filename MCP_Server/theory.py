"""Pure-Python music theory for AbletonMCP: note names, scales, chords, progressions and drum steps.

Nothing here talks to Live. Pitches follow Live's convention: MIDI numbers where C3 = 60 (C-2 = 0,
G8 = 127) and A3 = 440 Hz. Outputs are plain JSON data shaped to feed write_notes directly: chords
give "pitches", and progressions give a "notes" list of {"pitches", "start", "duration"}.

Sections:
- notes: parse and name pitches, spell them for a key
- scales: every scale Live 12.4 offers (same names and intervals) plus common aliases
- chords: chord symbols ("Am7", "F#m7b5", "Cmaj9#11", "G7sus4", "C/E"), inversions and voicings
- progressions: Roman numerals in a key ("ii7-V7-Imaj7", "i-bVI-bIII-bVII", "V7/V")
- drums: step patterns ("x---x---") parsed into timed hits, and the General MIDI drum map
"""
import re
from collections import namedtuple


class TheoryError(ValueError):
    """Input the caller can fix; the message says what is accepted."""


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

LETTERS = "CDEFGAB"
NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
_ACCIDENTALS = {"#": 1, "♯": 1, "b": -1, "♭": -1}
_NOTE = re.compile("^\\s*([A-Ga-g])([#b♯♭]{0,2})\\s*(-?\\d+)?\\s*$")
_INTEGER = re.compile(r"^\s*-?\d+\s*$")

Note = namedtuple("Note", "letter alter octave")


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def parse_note(value, what="note"):
    """Note(letter, alter, octave or None) for a note name such as 'C', 'F#2', 'Bb' or 'Eb-1'."""
    if not isinstance(value, str):
        raise TheoryError("{0} must be a note name like 'C3', 'F#2' or 'Bb', got {1!r}".format(what, value))
    match = _NOTE.match(value)
    if not match:
        raise TheoryError("{0} {1!r} is not a note name like 'C3', 'F#2' or 'Bb' (C3 = 60)".format(what, value))
    letter, accidentals, octave = match.groups()
    alter = sum(_ACCIDENTALS[char] for char in accidentals)
    return Note(letter.upper(), alter, None if octave is None else int(octave))


def note_pc(note):
    """Pitch class 0..11 of a Note."""
    return (NATURAL[note.letter] + note.alter) % 12


def _check_range(pitch, value, what):
    if not 0 <= pitch <= 127:
        raise TheoryError("{0} {1!r} is outside the MIDI range 0..127 (C-2..G8)".format(what, value))
    return pitch


def parse_pitch(value, what="pitch"):
    """MIDI number for a number or a note name with octave, in Live's convention (C3 = 60)."""
    if isinstance(value, bool):
        raise TheoryError("{0} must be a MIDI number or note name, not a boolean".format(what))
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if _is_int(value):
        return _check_range(value, value, what)
    if isinstance(value, str) and _INTEGER.match(value):
        return _check_range(int(value), value, what)
    note = parse_note(value, what)
    if note.octave is None:
        raise TheoryError("{0} {1!r} needs an octave, e.g. '{1}3' (C3 = 60)".format(what, value.strip()))
    return _check_range((note.octave + 2) * 12 + NATURAL[note.letter] + note.alter, value, what)


def parse_pitch_class(value, what="key"):
    """Pitch class 0..11 for 0..11 or a note name ('C', 'F#', 'Bb'; an octave is ignored)."""
    if _is_int(value):
        if 0 <= value <= 11:
            return value
        raise TheoryError("{0} as a number must be a pitch class 0..11 (0 = C), got {1}".format(what, value))
    return note_pc(parse_note(value, what))


def pitch_name(pitch, flats=False):
    """Name of a MIDI pitch in Live's convention (60 -> 'C3', 61 -> 'C#3' or 'Db3')."""
    names = FLAT_NAMES if flats else SHARP_NAMES
    return "{0}{1}".format(names[pitch % 12], pitch // 12 - 2)


def _alter_text(alter):
    return "#" * alter if alter > 0 else "b" * -alter


def _alter_for(letter, pc):
    """Accidental (-6..5, normally -2..2) that turns a letter into a pitch class."""
    return ((pc - NATURAL[letter] + 6) % 12) - 6


def spell(letter, alter):
    return letter + _alter_text(alter)


def spell_pitch(pitch, letter):
    """Name of a MIDI pitch spelled with a given letter: spell_pitch(70, 'B') -> 'Bb3', (70, 'A') -> 'A#3'."""
    alter = _alter_for(letter, pitch % 12)
    octave = (pitch - alter - NATURAL[letter]) // 12 - 2
    return "{0}{1}".format(spell(letter, alter), octave)


def frequency(pitch):
    """Equal-tempered frequency in Hz (A3 = MIDI 69 = 440 Hz in Live's naming)."""
    return 440.0 * 2.0 ** ((pitch - 69) / 12.0)


def describe_note(value, flats=False):
    """Everything about one note: MIDI number, names, pitch class, octave and frequency."""
    if isinstance(value, str) and not _INTEGER.match(value):
        note = parse_note(value, "note")
        if note.octave is None:
            pc = note_pc(note)
            return {"input": value, "pitch_class": pc, "name": spell(note.letter, note.alter),
                    "sharp_name": SHARP_NAMES[pc], "flat_name": FLAT_NAMES[pc]}
    pitch = parse_pitch(value, "note")
    name = pitch_name(pitch, flats)
    if isinstance(value, str) and not _INTEGER.match(value):
        note = parse_note(value, "note")
        name = "{0}{1}".format(spell(note.letter, note.alter), note.octave)
    return {
        "input": value,
        "pitch": pitch,
        "name": name,
        "sharp_name": pitch_name(pitch),
        "flat_name": pitch_name(pitch, True),
        "pitch_class": pitch % 12,
        "octave": pitch // 12 - 2,
        "frequency": round(frequency(pitch), 3),
    }


# ---------------------------------------------------------------------------
# Scales
# ---------------------------------------------------------------------------

# Song.get_all_scales_ordered() in Live 12.4.6: Live's own names and intervals, in Live's order.
LIVE_SCALES = (
    ("Major", (0, 2, 4, 5, 7, 9, 11)),
    ("Minor", (0, 2, 3, 5, 7, 8, 10)),
    ("Dorian", (0, 2, 3, 5, 7, 9, 10)),
    ("Mixolydian", (0, 2, 4, 5, 7, 9, 10)),
    ("Lydian", (0, 2, 4, 6, 7, 9, 11)),
    ("Phrygian", (0, 1, 3, 5, 7, 8, 10)),
    ("Locrian", (0, 1, 3, 5, 6, 8, 10)),
    ("Whole Tone", (0, 2, 4, 6, 8, 10)),
    ("Half-whole Dim.", (0, 1, 3, 4, 6, 7, 9, 10)),
    ("Whole-half Dim.", (0, 2, 3, 5, 6, 8, 9, 11)),
    ("Minor Blues", (0, 3, 5, 6, 7, 10)),
    ("Minor Pentatonic", (0, 3, 5, 7, 10)),
    ("Major Pentatonic", (0, 2, 4, 7, 9)),
    ("Harmonic Minor", (0, 2, 3, 5, 7, 8, 11)),
    ("Harmonic Major", (0, 2, 4, 5, 7, 8, 11)),
    ("Dorian #4", (0, 2, 3, 6, 7, 9, 10)),
    ("Phrygian Dominant", (0, 1, 4, 5, 7, 8, 10)),
    ("Melodic Minor", (0, 2, 3, 5, 7, 9, 11)),
    ("Lydian Augmented", (0, 2, 4, 6, 8, 9, 11)),
    ("Lydian Dominant", (0, 2, 4, 6, 7, 9, 10)),
    ("Super Locrian", (0, 1, 3, 4, 6, 8, 10)),
    ("8-Tone Spanish", (0, 1, 3, 4, 5, 6, 8, 10)),
    ("Bhairav", (0, 1, 4, 5, 7, 8, 11)),
    ("Hungarian Minor", (0, 2, 3, 6, 7, 8, 11)),
    ("Hirajoshi", (0, 2, 3, 7, 8)),
    ("In-Sen", (0, 1, 5, 7, 10)),
    ("Iwato", (0, 1, 5, 6, 10)),
    ("Kumoi", (0, 2, 3, 7, 9)),
    ("Pelog Selisir", (0, 1, 3, 7, 8)),
    ("Pelog Tembung", (0, 1, 5, 7, 8)),
    ("Messiaen 3", (0, 2, 3, 4, 6, 7, 8, 10, 11)),
    ("Messiaen 4", (0, 1, 2, 5, 6, 7, 8, 11)),
    ("Messiaen 5", (0, 1, 5, 6, 7, 11)),
    ("Messiaen 6", (0, 2, 4, 5, 6, 8, 10, 11)),
    ("Messiaen 7", (0, 1, 2, 3, 5, 6, 7, 8, 9, 11)),
)
EXTRA_SCALES = (
    ("Major Blues", (0, 2, 3, 4, 7, 9)),
    ("Chromatic", tuple(range(12))),
)
ALL_SCALES = LIVE_SCALES + EXTRA_SCALES
LIVE_SCALE_NAMES = tuple(name for name, _ in LIVE_SCALES)

_SCALE_ALIASES = {
    "ionian": "Major", "maj": "Major", "aeolian": "Minor", "naturalminor": "Minor", "min": "Minor", "m": "Minor",
    "pentatonic": "Major Pentatonic", "pentatonicmajor": "Major Pentatonic", "pentatonicminor": "Minor Pentatonic",
    "blues": "Minor Blues", "bluesminor": "Minor Blues", "bluesmajor": "Major Blues",
    "jazzminor": "Melodic Minor", "melodicminorascending": "Melodic Minor",
    "diminished": "Whole-half Dim.", "wholehalf": "Whole-half Dim.", "wholehalfdiminished": "Whole-half Dim.",
    "octatonic": "Whole-half Dim.", "halfwhole": "Half-whole Dim.", "halfwholediminished": "Half-whole Dim.",
    "dominantdiminished": "Half-whole Dim.", "altered": "Super Locrian", "alteredscale": "Super Locrian",
    "acoustic": "Lydian Dominant", "overtone": "Lydian Dominant", "lydianb7": "Lydian Dominant",
    "freygish": "Phrygian Dominant", "spanishphrygian": "Phrygian Dominant", "doubleharmonic": "Bhairav",
    "doubleharmonicmajor": "Bhairav", "byzantine": "Bhairav", "gypsyminor": "Hungarian Minor",
    "ukrainiandorian": "Dorian #4", "romanian": "Dorian #4", "romanianminor": "Dorian #4",
    "wholetonescale": "Whole Tone", "spanish8tone": "8-Tone Spanish", "spanish": "8-Tone Spanish",
}

Scale = namedtuple("Scale", "name intervals")
MAJOR = (0, 2, 4, 5, 7, 9, 11)
NATURAL_MINOR = (0, 2, 3, 5, 7, 8, 10)


def _scale_key(name):
    return re.sub(r"[^a-z0-9#]", "", str(name).lower())


_SCALE_LOOKUP = dict((_scale_key(name), Scale(name, intervals)) for name, intervals in ALL_SCALES)


def find_scale(name):
    """Scale(name, intervals) for a scale name (Live's names, case-insensitive, or a common alias)
    or a custom list of semitone intervals from the root."""
    if name is None:
        return Scale("Major", MAJOR)
    if isinstance(name, (list, tuple)):
        try:
            intervals = sorted(set(int(item) % 12 for item in name) | {0})
        except (TypeError, ValueError):
            raise TheoryError("A custom scale must be a list of semitone intervals, e.g. [0, 2, 3, 5, 7, 8, 10]")
        return Scale("Custom", tuple(intervals))
    key = _scale_key(name)
    if key in _SCALE_LOOKUP:
        return _SCALE_LOOKUP[key]
    if key in _SCALE_ALIASES:
        return _SCALE_LOOKUP[_scale_key(_SCALE_ALIASES[key])]
    if key.endswith("scale") and key[:-5] in _SCALE_LOOKUP:
        return _SCALE_LOOKUP[key[:-5]]
    raise TheoryError("Unknown scale {0!r}. Scales: {1}; aliases such as ionian, aeolian, blues, pentatonic, altered".format(
        name, ", ".join(name for name, _ in ALL_SCALES)))


Key = namedtuple("Key", "pc letter alter scale intervals")

_KEY = re.compile("^\\s*([A-Ga-g][#b♯♭]{0,2})\\s*(.*?)\\s*$")
# Tie-break for roots spelled as often with sharps as with flats: Db, Eb, Ab, Bb and F#.
_TIE_FLAT = {1: True, 3: True, 6: False, 8: True, 10: True}


def _spell_heptatonic(letter, alter, intervals):
    """(letter, alter) for each degree of a 7-note scale, one letter per degree."""
    root_pc = (NATURAL[letter] + alter) % 12
    start = LETTERS.index(letter)
    out = []
    for position, interval in enumerate(intervals):
        degree_letter = LETTERS[(start + position) % 7]
        out.append((degree_letter, _alter_for(degree_letter, (root_pc + interval) % 12)))
    return out


def _accidental_count(letter, alter, intervals):
    return sum(abs(item_alter) for _, item_alter in _spell_heptatonic(letter, alter, intervals))


def _proxy_heptatonic(intervals):
    """A 7-note scale that stands in for key-signature decisions about any scale."""
    if len(intervals) == 7:
        return tuple(intervals)
    return NATURAL_MINOR if 3 in intervals and 4 not in intervals else MAJOR


def _root_spelling(pc, intervals):
    """(letter, alter) for a numeric root: the spelling with the simpler key signature."""
    if SHARP_NAMES[pc] == FLAT_NAMES[pc]:
        return SHARP_NAMES[pc], 0
    proxy = _proxy_heptatonic(intervals)
    sharp = (SHARP_NAMES[pc][0], 1)
    flat = (FLAT_NAMES[pc][0], -1)
    sharp_count = _accidental_count(sharp[0], sharp[1], proxy)
    flat_count = _accidental_count(flat[0], flat[1], proxy)
    if sharp_count == flat_count:
        return flat if _TIE_FLAT.get(pc, False) else sharp
    return sharp if sharp_count < flat_count else flat


def _prefers_flats(letter, alter, intervals):
    if alter:
        return alter < 0
    alters = [item_alter for _, item_alter in _spell_heptatonic(letter, alter, _proxy_heptatonic(intervals))]
    return any(item < 0 for item in alters) and not any(item > 0 for item in alters)


def parse_key(key, scale=None):
    """Key(pc, letter, alter, scale, intervals) for 'C', 'A minor', 'Am', 'F# dorian', 'Bb' or 0..11.

    `scale` overrides a scale named in `key`; the default scale is Major.
    """
    if key is None:
        raise TheoryError("A key is required, e.g. 'C', 'A minor' or 'F# dorian'")
    named_scale = None
    if _is_int(key):
        pc = parse_pitch_class(key)
        letter = alter = None
    elif isinstance(key, str):
        match = _KEY.match(key)
        if not match:
            raise TheoryError("key {0!r} must start with a note name, e.g. 'C', 'A minor', 'Bbm' or 'F# dorian'".format(key))
        root, rest = match.groups()
        note = parse_note(root, "key")
        pc, letter, alter = note_pc(note), note.letter, note.alter
        rest = rest.strip()
        if rest in ("m", "min", "-"):
            named_scale = "Minor"
        elif rest:
            named_scale = rest
    else:
        raise TheoryError("key must be a note name such as 'C' or 'A minor', or a pitch class 0..11, got {0!r}".format(key))
    found = find_scale(scale if scale is not None else named_scale)
    if letter is None:
        letter, alter = _root_spelling(pc, found.intervals)
    return Key(pc, letter, alter, found.name, found.intervals)


def key_name(key):
    return "{0} {1}".format(spell(key.letter, key.alter), key.scale.lower() if key.scale in ("Major", "Minor") else key.scale)


def _scale_spelling(key):
    """(letter, alter) per scale degree of a key."""
    if len(key.intervals) == 7:
        return _spell_heptatonic(key.letter, key.alter, key.intervals)
    flats = _prefers_flats(key.letter, key.alter, key.intervals)
    out = [(key.letter, key.alter)]
    for interval in key.intervals[1:]:
        name = (FLAT_NAMES if flats else SHARP_NAMES)[(key.pc + interval) % 12]
        out.append((name[0], _alter_for(name[0], (key.pc + interval) % 12)))
    return out


def scale_info(key, scale=None, octave=3, octaves=1):
    """Notes of a scale: pitch classes spelled for the key, plus MIDI pitches from the root in `octave`."""
    parsed = parse_key(key, scale)
    octave = _int_arg(octave, "octave", -2, 8)
    octaves = _int_arg(octaves, "octaves", 1, 8)
    spelling = _scale_spelling(parsed)
    root_pitch = (octave + 2) * 12 + parsed.pc
    voiced = [(root_pitch + 12 * count + interval, spelling[position][0])
              for count in range(octaves) for position, interval in enumerate(parsed.intervals)]
    voiced.append((root_pitch + 12 * octaves, parsed.letter))
    if not all(0 <= pitch <= 127 for pitch, _ in voiced):
        raise TheoryError("Octave {0} with {1} octave(s) leaves the MIDI range 0..127; use another octave".format(octave, octaves))
    pitches = [pitch for pitch, _ in voiced]
    names = [spell_pitch(pitch, letter) for pitch, letter in voiced]
    return {
        "key": key_name(parsed),
        "root": spell(parsed.letter, parsed.alter),
        "scale": parsed.scale,
        "live_scale": parsed.scale if parsed.scale in LIVE_SCALE_NAMES else None,
        "intervals": list(parsed.intervals),
        "notes": [spell(letter, alter) for letter, alter in spelling],
        "pitches": pitches,
        "names": names,
    }


def _int_arg(value, what, low, high):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not _is_int(value) or not low <= value <= high:
        raise TheoryError("{0} must be an integer {1}..{2}, got {3!r}".format(what, low, high, value))
    return value


# ---------------------------------------------------------------------------
# Chords
# ---------------------------------------------------------------------------

_DEGREE_SEMITONES = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11, 9: 14, 11: 17, 13: 21}
_TONE = re.compile(r"^(bb|b|##|#)?(\d+)$")
_TONE_ALTER = {None: 0, "b": -1, "bb": -2, "#": 1, "##": 2}


def _tones(formula):
    """[(degree, semitones)] for a degree formula such as '1 b3 5 b7'."""
    out = []
    for token in formula.split():
        accidental, degree = _TONE.match(token).groups()
        out.append((int(degree), _DEGREE_SEMITONES[int(degree)] + _TONE_ALTER[accidental]))
    return out


# Base chord qualities, matched as the longest prefix of the quality text (case-sensitive: M vs m).
_BASES = dict((suffix, _tones(formula)) for suffix, formula in (
    ("", "1 3 5"), ("maj", "1 3 5"), ("m", "1 b3 5"), ("dim", "1 b3 b5"), ("aug", "1 3 #5"), ("5", "1 5"),
    ("6", "1 3 5 6"), ("m6", "1 b3 5 6"), ("69", "1 3 5 6 9"), ("m69", "1 b3 5 6 9"),
    ("7", "1 3 5 b7"), ("maj7", "1 3 5 7"), ("m7", "1 b3 5 b7"), ("mmaj7", "1 b3 5 7"),
    ("dim7", "1 b3 b5 bb7"), ("m7b5", "1 b3 b5 b7"), ("aug7", "1 3 #5 b7"), ("augmaj7", "1 3 #5 7"),
    ("9", "1 3 5 b7 9"), ("maj9", "1 3 5 7 9"), ("m9", "1 b3 5 b7 9"), ("mmaj9", "1 b3 5 7 9"),
    ("11", "1 3 5 b7 9 11"), ("maj11", "1 3 5 7 9 11"), ("m11", "1 b3 5 b7 9 11"),
    ("13", "1 3 5 b7 9 13"), ("maj13", "1 3 5 7 9 13"), ("m13", "1 b3 5 b7 9 13"),
))
_BASE_ORDER = sorted(_BASES, key=len, reverse=True)

# Modifiers after the base: (text, operation, degree, semitones).
_MODIFIERS = (
    ("add13", "add", 13, 21), ("add11", "add", 11, 17), ("add9", "add", 9, 14), ("add6", "add", 6, 9),
    ("add4", "add", 4, 5), ("add2", "add", 2, 2), ("sus2", "sus", 2, 2), ("sus4", "sus", 4, 5), ("sus", "sus", 4, 5),
    ("omit3", "omit", 3, None), ("omit5", "omit", 5, None), ("no3", "omit", 3, None), ("no5", "omit", 5, None),
    ("maj7", "add", 7, 11), ("b13", "add", 13, 20), ("#11", "add", 11, 18), ("b9", "add", 9, 13), ("#9", "add", 9, 15),
    ("-13", "add", 13, 20), ("+11", "add", 11, 18), ("-9", "add", 9, 13), ("+9", "add", 9, 15),
    ("b5", "alter", 5, 6), ("#5", "alter", 5, 8), ("-5", "alter", 5, 6), ("+5", "alter", 5, 8),
    ("13", "add", 13, 21), ("11", "add", 11, 17), ("9", "add", 9, 14), ("7", "add", 7, 10), ("6", "add", 6, 9),
)

_QUALITY_SYNONYMS = (
    ("ø7", "m7b5"), ("ø", "m7b5"), ("°", "dim"), ("♯", "#"), ("♭", "b"),
    ("major", "maj"), ("Major", "maj"), ("MAJ", "maj"), ("Maj", "maj"), ("minor", "m"), ("min", "m"),
    ("halfdim", "m7b5"), ("half-dim", "m7b5"), ("dom", ""), ("6/9", "69"),
)

VOICINGS = ("close", "open", "drop2", "drop3", "spread")

Chord = namedtuple("Chord", "pc letter alter quality tones bass")  # bass: (pc, letter, alter) or None


def _normalize_quality(text):
    """Canonical quality text: 'M7' / 'Δ7' -> 'maj7', 'Δ' -> 'maj7', '-7' -> 'm7', 'ø' -> 'm7b5', '+' -> 'aug'."""
    quality = re.sub(r"[\s(),]", "", text)
    quality = re.sub("Δ(?=\\d)", "maj", quality).replace("Δ", "maj7")
    for old, new in _QUALITY_SYNONYMS:
        quality = quality.replace(old, new)
    if quality.startswith("mM"):
        quality = "mmaj" + quality[2:]
    elif quality.startswith("M"):
        quality = "maj" + quality[1:]
    elif quality.startswith("-"):
        quality = "m" + quality[1:]
    elif quality.startswith("+"):
        quality = "aug" + quality[1:]
    elif quality.startswith("o") and not quality.startswith("omit"):
        quality = "dim" + quality[1:]
    return quality


def _apply_modifier(tones, operation, degree, semitones):
    tones = list(tones)
    if operation == "omit":
        return [tone for tone in tones if tone[0] != degree]
    if operation == "sus":
        return [tone for tone in tones if tone[0] != 3] + [(degree, semitones)]
    if operation == "alter":
        return [tone for tone in tones if tone[0] != degree] + [(degree, semitones)]
    natural = _DEGREE_SEMITONES[degree] if degree in _DEGREE_SEMITONES else None
    if degree == 7:
        tones = [tone for tone in tones if tone[0] != 7]
    elif semitones != natural:
        tones = [tone for tone in tones if not (tone[0] == degree and tone[1] == natural)]
    if (degree, semitones) not in tones:
        tones.append((degree, semitones))
    return tones


def _parse_quality(quality, symbol):
    base = next(suffix for suffix in _BASE_ORDER if quality.startswith(suffix))
    tones = list(_BASES[base])
    rest = quality[len(base):]
    while rest:
        for text, operation, degree, semitones in _MODIFIERS:
            if rest.startswith(text):
                tones = _apply_modifier(tones, operation, degree, semitones)
                rest = rest[len(text):]
                break
        else:
            raise TheoryError("Cannot read chord {0!r} (stuck at {1!r}). Use symbols like C, Cm, C7, Cmaj7, Cm7, Cdim7, "
                              "Cm7b5, Caug, Csus4, C7sus4, Cadd9, C6, C69, C9, Cm9, C11, C13, C7b9, C7#9, Cmaj7#11 "
                              "or slash chords like C/E".format(symbol, rest))
    return sorted(set(tones), key=lambda tone: (tone[1], tone[0]))


_CHORD = re.compile("^\\s*([A-Ga-g][#b♯♭]{0,2})(.*?)(?:/([A-Ga-g][#b♯♭]{0,2}))?\\s*$")


def parse_chord(symbol):
    """Chord for a chord symbol: root, quality and optional slash bass ('Am7', 'F#m7b5', 'C/E')."""
    if not isinstance(symbol, str) or not symbol.strip():
        raise TheoryError("chord must be a chord symbol such as 'Am7', 'Cmaj7' or 'G7sus4', got {0!r}".format(symbol))
    match = _CHORD.match(symbol)
    if not match:
        raise TheoryError("Cannot read chord {0!r}; it must start with a root note such as C, F# or Bb".format(symbol))
    root_text, quality_text, bass_text = match.groups()
    # "Bb" is the root B-flat, but in "Bbm" the "b" belongs to the root, too: the regex prefers that.
    root = parse_note(root_text, "chord root")
    tones = _parse_quality(_normalize_quality(quality_text), symbol)
    bass = None
    if bass_text:
        bass_note = parse_note(bass_text, "bass note")
        bass = (note_pc(bass_note), bass_note.letter, bass_note.alter)
    return Chord(note_pc(root), root.letter, root.alter, _normalize_quality(quality_text), tones, bass)


def _tone_label(degree, semitones):
    alter = semitones - _DEGREE_SEMITONES[degree]
    return _alter_text(alter) + str(degree)


def _tone_letter(chord, degree):
    return LETTERS[(LETTERS.index(chord.letter) + degree - 1) % 7]


def _close_position(chord, octave):
    root = (octave + 2) * 12 + chord.pc
    return [(root + semitones, _tone_letter(chord, degree)) for degree, semitones in chord.tones]


def _apply_voicing(pitches, voicing):
    pitches = sorted(pitches)
    count = len(pitches)
    if voicing == "close":
        return pitches
    if voicing == "drop2" and count >= 3:
        pitches[-2] -= 12
    elif voicing == "drop3" and count >= 4:
        pitches[-3] -= 12
    elif voicing == "open":
        for position in range(1, count, 2):
            pitches[position] += 12
    elif voicing == "spread":
        pitches[0] -= 12
    elif voicing not in VOICINGS:
        raise TheoryError("voicing must be one of: {0}, got {1!r}".format(", ".join(VOICINGS), voicing))
    return sorted(pitches)


def _invert(voiced, inversion):
    """Raise the lowest note an octave, `inversion` times. voiced: [(pitch, letter)]."""
    voiced = sorted(voiced)
    for _ in range(inversion):
        lowest = voiced.pop(0)
        voiced.append((lowest[0] + 12, lowest[1]))
        voiced.sort()
    return voiced


def voice_chord(chord, octave=3, inversion=0, voicing="close"):
    """[(pitch, letter)] of a chord: close position from the root in `octave`, inverted, then voiced.

    A slash bass that is a chord tone selects the matching inversion (C/E = first inversion); any other
    bass note is added below the chord.
    """
    voicing = str(voicing or "close").strip().lower()
    if voicing not in VOICINGS:
        raise TheoryError("voicing must be one of: {0}, got {1!r}".format(", ".join(VOICINGS), voicing))
    voiced = _close_position(chord, octave)
    count = len(voiced)
    if not 0 <= inversion < count:
        raise TheoryError("inversion must be 0..{0} for a {1}-note chord, got {2}".format(count - 1, count, inversion))
    extra_bass = None
    if chord.bass is not None:
        if chord.bass[0] in [pitch % 12 for pitch, _ in voiced]:
            if inversion == 0:
                inversion = _inversion_for(voiced, chord.bass[0])
        else:
            extra_bass = chord.bass
    root_pitch = voiced[0][0]
    voiced = _invert(voiced, inversion)
    if chord.bass is not None and extra_bass is None and voiced[0][0] - root_pitch > 7:
        # Keep a slash chord's bass within a fifth above the root's register (Am7/G -> G3 A3 C4 E4).
        voiced = [(pitch - 12, letter) for pitch, letter in voiced]
    letters = dict((pitch % 12, letter) for pitch, letter in voiced)
    pitches = _apply_voicing([pitch for pitch, _ in voiced], voicing)
    result = [(pitch, letters[pitch % 12]) for pitch in pitches]
    if extra_bass is not None:
        lowest = result[0][0]
        bass_pitch = lowest - ((lowest - extra_bass[0]) % 12 or 12)
        result.insert(0, (bass_pitch, extra_bass[1]))
    for pitch, _ in result:
        if not 0 <= pitch <= 127:
            raise TheoryError("Octave {0} puts this chord outside the MIDI range 0..127; use a lower or higher octave".format(octave))
    return result


def _inversion_for(voiced, bass_pc):
    ordered = sorted(voiced)
    for position, (pitch, _) in enumerate(ordered):
        if pitch % 12 == bass_pc:
            return position
    return 0


def chord_symbol(chord):
    text = spell(chord.letter, chord.alter) + chord.quality
    if chord.bass is not None:
        text += "/" + spell(chord.bass[1], chord.bass[2])
    return text


def chord_info(chord, octave=3, inversion=0, voicing="close", numeral=None):
    """JSON for a Chord: symbol, tones, spelled notes, MIDI pitches and names."""
    octave = _int_arg(octave, "octave", -2, 8)
    inversion = _int_arg(inversion, "inversion", 0, 12)
    voiced = voice_chord(chord, octave, inversion, voicing)
    out = {}
    if numeral is not None:
        out["numeral"] = numeral
    out.update({
        "symbol": chord_symbol(chord),
        "root": spell(chord.letter, chord.alter),
        "quality": chord.quality or "maj",
        "tones": [_tone_label(degree, semitones) for degree, semitones in chord.tones],
        "notes": [spell(_tone_letter(chord, degree), _alter_for(_tone_letter(chord, degree), (chord.pc + semitones) % 12))
                  for degree, semitones in chord.tones],
        "pitches": [pitch for pitch, _ in voiced],
        "names": [spell_pitch(pitch, letter) for pitch, letter in voiced],
    })
    if chord.bass is not None:
        out["bass"] = spell(chord.bass[1], chord.bass[2])
    return out


# ---------------------------------------------------------------------------
# Roman-numeral progressions
# ---------------------------------------------------------------------------

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}
_NUMERAL = re.compile("^(?P<accidental>[b#♭♯]?)(?P<roman>VII|VI|IV|V|III|II|I|vii|vi|iv|v|iii|ii|i)(?P<rest>.*)$")
_SEPARATORS = re.compile(r"[\s,|\-–—>]+")


def is_numeral(text):
    return bool(_NUMERAL.match(text.strip())) if isinstance(text, str) else False


def _numeral_quality(roman, rest):
    rest = rest.strip()
    for old, new in (("ø7", "m7b5"), ("ø", "m7b5"), ("°7", "dim7"), ("°", "dim"), ("o7", "dim7")):
        if rest.startswith(old):
            rest = new + rest[len(old):]
            break
    else:
        if rest.startswith("o") and not rest.startswith("omit"):
            rest = "dim" + rest[1:]
        elif rest.startswith("+"):
            rest = "aug" + rest[1:]
    if rest.startswith(("dim", "aug", "m7b5")):
        return rest
    if roman.isupper():
        return rest
    if rest.startswith("m") and not rest.startswith("maj"):
        return rest
    return "m" + rest


def parse_numeral(numeral, key):
    """Chord for a Roman numeral in a key: 'ii7', 'V7', 'bVII', 'viiø7', 'V7/V' (secondary)."""
    text = numeral.strip()
    if "/" in text:
        head, target = text.rsplit("/", 1)
        if is_numeral(target):
            target_chord = parse_numeral(target, key)
            local = Key(target_chord.pc, target_chord.letter, target_chord.alter, "Major", MAJOR)
            return parse_numeral(head, local)
    match = _NUMERAL.match(text)
    if not match:
        raise TheoryError("Cannot read numeral {0!r}; use I..VII (major) or i..vii (minor) with optional b/# and a "
                          "suffix, e.g. ii7, V7, Imaj7, vii°, bVII, V7/V".format(numeral))
    roman = match.group("roman")
    if not (roman.isupper() or roman.islower()):
        raise TheoryError("Numeral {0!r} mixes upper and lower case".format(numeral))
    degree = _ROMAN[roman.upper()]
    accidental = _ACCIDENTALS.get(match.group("accidental"), 0) if match.group("accidental") else None
    if accidental is None:
        if len(key.intervals) != 7:
            raise TheoryError("Roman numerals need a 7-note scale; {0} has {1} notes".format(key.scale, len(key.intervals)))
        semitones = key.intervals[degree - 1]
    else:
        semitones = MAJOR[degree - 1] + accidental  # accidentals are relative to the major scale: bVII, bIII, #iv
    quality = _numeral_quality(roman, match.group("rest"))
    if accidental is None and degree == 7 and key.intervals[6] == 10 and _normalize_quality(quality).startswith(("dim", "m7b5")):
        semitones = 11  # vii°, vii°7, viiø7 in minor: the leading tone of harmonic minor (A minor -> G# dim)
    pc = (key.pc + semitones) % 12
    letter = LETTERS[(LETTERS.index(key.letter) + degree - 1) % 7]
    tones = _parse_quality(_normalize_quality(quality), numeral)
    return Chord(pc, letter, _alter_for(letter, pc), _normalize_quality(quality), tones, None)


def split_progression(progression):
    if isinstance(progression, (list, tuple)):
        items = [str(item).strip() for item in progression]
    elif isinstance(progression, str):
        items = [item for item in _SEPARATORS.split(progression.strip()) if item]
    else:
        raise TheoryError("progression must be a list like ['I', 'V', 'vi', 'IV'] or a string like 'I-V-vi-IV'")
    items = [item for item in items if item]
    if not items:
        raise TheoryError("progression is empty; give numerals like 'I-V-vi-IV' or chords like 'Am F C G'")
    return items


def _movement(previous, candidate):
    return (sum(min(abs(pitch - other) for other in previous) for pitch in candidate)
            + sum(min(abs(pitch - other) for other in candidate) for pitch in previous))


def _led_voicing(chord, previous, center, octave, voicing):
    """The inversion and octave of a chord that moves least from the previous chord, near `center`."""
    best = None
    # A slash chord keeps the inversion its bass asks for; other chords try every inversion.
    inversions = [0] if chord.bass is not None else range(len(chord.tones))
    for shift in (-1, 0, 1):
        for inversion in inversions:
            try:
                voiced = voice_chord(chord, octave + shift, inversion, voicing)
            except TheoryError:
                continue
            pitches = [pitch for pitch, _ in voiced]
            mean = sum(pitches) / float(len(pitches))
            if abs(mean - center) > 7.5:
                continue
            score = (_movement(previous, pitches), abs(mean - center))
            if best is None or score < best[0]:
                best = (score, voiced)
    return best[1] if best else voice_chord(chord, octave, 0, voicing)


def progression_info(key, progression, scale=None, octave=3, beats_per_chord=4.0, voicing="close", voice_leading=False):
    """Chords for a progression of Roman numerals or chord symbols, with a write_notes-ready `notes` list."""
    parsed_key = parse_key(key, scale)
    items = split_progression(progression)
    octave = _int_arg(octave, "octave", -2, 8)
    durations = beats_per_chord if isinstance(beats_per_chord, (list, tuple)) else [beats_per_chord] * len(items)
    if len(durations) != len(items):
        raise TheoryError("beats_per_chord has {0} values for {1} chords".format(len(durations), len(items)))
    for value in durations:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise TheoryError("beats_per_chord must be positive beats, got {0!r}".format(value))
    chords, notes, time, previous, center = [], [], 0.0, None, None
    for item, duration in zip(items, durations):
        if is_numeral(item):
            chord, numeral = parse_numeral(item, parsed_key), item
        else:
            chord, numeral = parse_chord(item), None
        if voice_leading and previous is not None:
            voiced = _led_voicing(chord, previous, center, octave, voicing)
            info = chord_info(chord, octave, 0, voicing, numeral)
            info["pitches"] = [pitch for pitch, _ in voiced]
            info["names"] = [spell_pitch(pitch, letter) for pitch, letter in voiced]
        else:
            info = chord_info(chord, octave, 0, voicing, numeral)
        if center is None:
            center = sum(info["pitches"]) / float(len(info["pitches"]))
        previous = info["pitches"]
        info["start"] = round(time, 6)
        info["duration"] = float(duration)
        chords.append(info)
        notes.append({"pitches": list(info["pitches"]), "start": round(time, 6), "duration": float(duration)})
        time += float(duration)
    return {"key": key_name(parsed_key), "scale": parsed_key.scale, "chords": chords, "notes": notes, "length": round(time, 6)}


def chord_lookup(symbol, key=None, scale=None, octave=3, inversion=0, voicing="close"):
    """chord_info for a chord symbol, or for a Roman numeral when `key` is given."""
    if isinstance(symbol, str) and is_numeral(symbol):
        if key is None:
            raise TheoryError("Roman numeral {0!r} needs a key, e.g. key='C' or key='A minor'".format(symbol))
        return chord_info(parse_numeral(symbol, parse_key(key, scale)), octave, inversion, voicing, symbol.strip())
    return chord_info(parse_chord(symbol), octave, inversion, voicing)


# ---------------------------------------------------------------------------
# Chord shorthand for write_notes
# ---------------------------------------------------------------------------

_CHORD_NOTE_KEYS = ("chord", "octave", "inversion", "voicing", "key")


def expand_note_chords(notes):
    """Replace {"chord": "Am7", "octave": 3, "inversion": 0, "voicing": "close"} in note dicts with "pitches"."""
    if not isinstance(notes, list):
        return notes
    out = []
    for index, note in enumerate(notes):
        if not isinstance(note, dict) or note.get("chord") is None:
            out.append(note)
            continue
        if note.get("pitch") is not None or note.get("pitches") is not None:
            raise TheoryError("notes[{0}] has chord and pitch/pitches; give one of them".format(index))
        try:
            info = chord_lookup(note["chord"], note.get("key"), None, note.get("octave", 3), note.get("inversion", 0),
                                note.get("voicing", "close"))
        except TheoryError as error:
            raise TheoryError("notes[{0}]: {1}".format(index, error))
        expanded = dict((name, value) for name, value in note.items() if name not in _CHORD_NOTE_KEYS)
        expanded["pitches"] = info["pitches"]
        out.append(expanded)
    return out


# ---------------------------------------------------------------------------
# Drums: General MIDI map and step patterns
# ---------------------------------------------------------------------------

GM_DRUMS = {
    35: ("acoustic bass drum", "bass drum 2", "kick 2"),
    36: ("kick", "bass drum", "bass drum 1", "bd", "kick drum"),
    37: ("side stick", "rim", "rimshot", "rim shot", "stick", "rs"),
    38: ("snare", "acoustic snare", "sd", "snare drum"),
    39: ("clap", "hand clap", "handclap", "cp"),
    40: ("electric snare", "snare 2"),
    41: ("low floor tom", "floor tom"),
    42: ("closed hat", "closed hihat", "closed hi hat", "hat", "hihat", "hi hat", "hh", "ch", "chh"),
    43: ("high floor tom",),
    44: ("pedal hat", "pedal hihat", "pedal hi hat", "ph"),
    45: ("low tom", "tom", "lt"),
    46: ("open hat", "open hihat", "open hi hat", "oh", "ohh"),
    47: ("low mid tom", "mid tom", "mt"),
    48: ("hi mid tom", "high mid tom"),
    49: ("crash", "crash cymbal", "crash 1", "cr"),
    50: ("high tom", "hi tom", "ht"),
    51: ("ride", "ride cymbal", "ride 1", "rd"),
    52: ("china", "chinese cymbal"),
    53: ("ride bell", "bell"),
    54: ("tambourine", "tamb"),
    55: ("splash", "splash cymbal"),
    56: ("cowbell",),
    57: ("crash 2", "crash cymbal 2"),
    58: ("vibraslap",),
    59: ("ride 2", "ride cymbal 2"),
    60: ("hi bongo", "high bongo", "bongo"),
    61: ("low bongo",),
    62: ("mute hi conga", "mute conga"),
    63: ("open hi conga", "conga", "high conga"),
    64: ("low conga",),
    65: ("high timbale", "timbale"),
    66: ("low timbale",),
    67: ("high agogo", "agogo"),
    68: ("low agogo",),
    69: ("cabasa",),
    70: ("maracas", "shaker"),
    71: ("short whistle",),
    72: ("long whistle", "whistle"),
    73: ("short guiro",),
    74: ("long guiro", "guiro"),
    75: ("claves", "clave"),
    76: ("hi wood block", "high wood block", "wood block", "woodblock"),
    77: ("low wood block",),
    78: ("mute cuica", "cuica"),
    79: ("open cuica",),
    80: ("mute triangle",),
    81: ("open triangle", "triangle"),
}


def _drum_key(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


_GM_LOOKUP = dict((_drum_key(alias), pitch) for pitch, aliases in GM_DRUMS.items() for alias in aliases)


def gm_drum(name):
    """General MIDI drum note for a drum name ('kick' -> 36, 'closed hat' -> 42), or None."""
    key = _drum_key(name)
    if key in _GM_LOOKUP:
        return _GM_LOOKUP[key]
    if key.endswith("s") and key[:-1] in _GM_LOOKUP:
        return _GM_LOOKUP[key[:-1]]
    return None


DEFAULT_VELOCITIES = {"x": 100, "X": 127, "o": 60}
_VELOCITY_KEYS = {"x": "x", "X": "X", "o": "o", "normal": "x", "hit": "x", "accent": "X", "ghost": "o"}
_STEP_RESTS = "-._"
_STEP_IGNORED = " |\t\n"


def drum_lanes(pattern, steps_per_beat=4, velocities=None, swing=0.0):
    """Parse step strings per drum into timed hits for one cycle of each lane.

    pattern: {"Kick": "x---x---x---x---", ...}; "x" hit, "X" accent, "o" ghost, "-" "." or "_" rest;
    spaces and "|" are ignored. Each lane repeats on its own cycle (len(steps) / steps_per_beat beats).
    swing (0..1) delays every second step by swing x half a step (MPC-style 50 + 25 x swing percent:
    0.16 = 54 %, 0.32 = 58 %, 0.67 = triplet shuffle 66.7 %, 1 = 75 %).
    Returns [{"drum", "gm", "steps", "cycle", "hits": [[start, duration, velocity], ...]}].
    """
    if not isinstance(pattern, dict) or not pattern:
        raise TheoryError('pattern must map drum names to step strings, e.g. {"Kick": "x---x---x---x---", "Snare": "----x-------x---"}')
    steps_per_beat = _int_arg(steps_per_beat, "steps_per_beat", 1, 64)
    if isinstance(swing, bool) or not isinstance(swing, (int, float)) or not 0.0 <= swing <= 1.0:
        raise TheoryError("swing must be 0..1 (0 straight, 0.67 triplet shuffle, 1 = half a step), got {0!r}".format(swing))
    levels = dict(DEFAULT_VELOCITIES)
    for name, value in (velocities or {}).items():
        target = _VELOCITY_KEYS.get(name) or _VELOCITY_KEYS.get(str(name).lower())
        if target is None:
            raise TheoryError("velocities keys are x (or normal), X (or accent) and o (or ghost), got {0!r}".format(name))
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 1 <= value <= 127:
            raise TheoryError("velocity for {0!r} must be 1..127, got {1!r}".format(name, value))
        levels[target] = value
    step = 1.0 / steps_per_beat
    delay = swing * step / 2.0
    duration = step - delay
    lanes = []
    for drum, steps in pattern.items():
        label = str(drum).strip()
        if not label:
            raise TheoryError("Drum names in pattern must not be empty")
        if not isinstance(steps, str):
            raise TheoryError("Steps for {0!r} must be a string such as 'x---x---', got {1!r}".format(label, steps))
        cells = [char for char in steps if char not in _STEP_IGNORED]
        if not cells:
            raise TheoryError("Steps for {0!r} are empty".format(label))
        hits = []
        for position, char in enumerate(cells):
            if char in _STEP_RESTS:
                continue
            if char not in levels:
                raise TheoryError("Steps for {0!r} contain {1!r} at step {2}; use x (hit), X (accent), o (ghost), "
                                  "- or . (rest); spaces and | are ignored".format(label, char, position + 1))
            start = position * step + (delay if position % 2 == 1 else 0.0)
            hits.append([round(start, 6), round(duration, 6), levels[char]])
        lanes.append({"drum": label, "gm": gm_drum(label), "steps": len(cells), "cycle": round(len(cells) * step, 6), "hits": hits})
    return lanes


# ---------------------------------------------------------------------------
# music_theory tool dispatcher
# ---------------------------------------------------------------------------

OPERATIONS = ("scale", "chord", "progression", "notes", "list")


def music_theory(operation, key=None, scale=None, chord=None, progression=None, notes=None, octave=3, octaves=1,
                 inversion=0, voicing="close", beats_per_chord=4.0, voice_leading=False):
    """Run one music_theory operation (see the tool docstring); raises TheoryError on bad input."""
    op = str(operation or "").strip().lower()
    if op in ("note", "convert", "names"):
        op = "notes"
    if op in ("scales", "chords", "help"):
        op = "list"
    if op == "scale":
        if key is None:
            raise TheoryError("scale needs key, e.g. key='A', scale='minor' (or key='A minor')")
        return scale_info(key, scale, octave, octaves)
    if op == "chord":
        if chord is None:
            raise TheoryError("chord needs chord, e.g. chord='Am7' (or a numeral like 'V7' with key='C')")
        return chord_lookup(chord, key, scale, octave, inversion, voicing)
    if op == "progression":
        if progression is None or key is None:
            raise TheoryError("progression needs key and progression, e.g. key='C', progression='I-V-vi-IV'")
        return progression_info(key, progression, scale, octave, beats_per_chord, voicing, voice_leading)
    if op == "notes":
        if notes is None:
            raise TheoryError("notes needs notes, e.g. notes=['C3', 64, 'Bb2']")
        values = notes if isinstance(notes, (list, tuple)) else [notes]
        return {"notes": [describe_note(value) for value in values]}
    if op == "list":
        return {
            "operations": list(OPERATIONS),
            "scales": [name for name, _ in ALL_SCALES],
            "live_scales": list(LIVE_SCALE_NAMES),
            "chord_qualities": sorted((suffix or "(major)") for suffix in _BASES),
            "chord_modifiers": [text for text, _, _, _ in _MODIFIERS],
            "voicings": list(VOICINGS),
        }
    raise TheoryError("operation must be one of: {0}, got {1!r}".format(", ".join(OPERATIONS), operation))
