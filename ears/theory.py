"""Small music-theory helpers for the notes ear: note names, intervals, scale membership and chords.

Standard library only, so `ears` runs without Live or the MCP server. Pitches are MIDI numbers in Live's
naming, where C3 = 60 (C-2 = 0, G8 = 127): MIDI 45 is A1 and 43 is G1. Pitch classes are 0..11 with C = 0.
Names use sharps by default (a G# over an E chord), flats on request.

Chords are parsed from the symbols a spec's progressions use ("Am", "F", "E7", "Bdim", "Asus4"). The table of
qualities is deliberately small; an unknown symbol raises ValueError so a typo in a spec is loud.
"""
import re
from collections import namedtuple
from functools import lru_cache

SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
_NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACCIDENTAL = {"#": 1, "♯": 1, "b": -1, "♭": -1}
_NOTE = re.compile("^\\s*([A-Ga-g])([#b♯♭]*)\\s*(-?\\d+)\\s*$")
_ROOT = re.compile("^\\s*([A-Ga-g])([#b♯♭]*)(.*)$")

# Chord qualities: (suffixes, quality name, semitones above the root). Suffixes are case-sensitive
# ("M7" is major, "m7" minor). The first entry of a row is the name `describe_chord` shows.
_QUALITIES = (
    (("", "maj", "M", "major"), "major", (0, 4, 7)),
    (("m", "min", "mi", "-", "minor"), "minor", (0, 3, 7)),
    (("dim", "o", "°"), "diminished", (0, 3, 6)),
    (("aug", "+"), "augmented", (0, 4, 8)),
    (("sus4", "sus"), "sus4", (0, 5, 7)),
    (("sus2",), "sus2", (0, 2, 7)),
    (("5",), "power", (0, 7)),
    (("6",), "major 6th", (0, 4, 7, 9)),
    (("m6", "min6"), "minor 6th", (0, 3, 7, 9)),
    (("7", "dom7"), "dominant 7th", (0, 4, 7, 10)),
    (("maj7", "Maj7", "M7", "Δ", "Δ7"), "major 7th", (0, 4, 7, 11)),
    (("m7", "min7", "mi7", "-7"), "minor 7th", (0, 3, 7, 10)),
    (("dim7", "o7", "°7"), "diminished 7th", (0, 3, 6, 9)),
    (("m7b5", "min7b5", "ø", "ø7"), "half-diminished 7th", (0, 3, 6, 10)),
    (("7sus4", "7sus"), "7sus4", (0, 5, 7, 10)),
    (("add9",), "add9", (0, 4, 7, 14)),
    (("9",), "dominant 9th", (0, 4, 7, 10, 14)),
    (("m9", "min9"), "minor 9th", (0, 3, 7, 10, 14)),
    (("maj9", "Maj9", "M9"), "major 9th", (0, 4, 7, 11, 14)),
)
_SUFFIX = dict((suffix, (name, intervals)) for suffixes, name, intervals in _QUALITIES for suffix in suffixes)

# symbol: the text as given; root: pitch class; quality: name from the table; tones: pitch classes, root first
# (a slash bass is appended when it is not already a tone); bass: pitch class of a slash bass or None;
# flats: whether tones are spelled with flats.
Chord = namedtuple("Chord", "symbol root quality tones bass flats")


# -- pitch classes and note names ------------------------------------------------------------------


def pitch_class(pitch):
    """0..11 for a MIDI pitch (or a pitch class)."""
    return int(pitch) % 12


def pc_name(pc, flats=False):
    """"G#" (or "Ab" with flats=True) for a pitch class."""
    return (FLAT_NAMES if flats else SHARP_NAMES)[int(pc) % 12]


def note_name(pitch, flats=False):
    """Live's name for a MIDI pitch: 60 -> "C3", 45 -> "A1", 43 -> "G1", 0 -> "C-2"."""
    pitch = int(pitch)
    return "{0}{1}".format(pc_name(pitch, flats), pitch // 12 - 2)


def parse_pitch_class(name):
    """Pitch class of a note name without octave: "A" -> 9, "G#" -> 8, "Bb" -> 10 (also with ♯ and ♭)."""
    match = _ROOT.match(str(name))
    if not match or match.group(3).strip():
        raise ValueError("Not a note name: {0!r}".format(name))
    return _spelled(match.group(1), match.group(2))


def parse_note(name):
    """MIDI pitch of a name with octave in Live's convention: "C3" -> 60, "A1" -> 45, "F#2" -> 54."""
    match = _NOTE.match(str(name))
    if not match:
        raise ValueError("Not a note name with octave (C3 = 60): {0!r}".format(name))
    letter, accidentals, octave = match.groups()
    pitch = (int(octave) + 2) * 12 + _spelled(letter, accidentals, wrap=False)
    if not 0 <= pitch <= 127:
        raise ValueError("{0!r} is outside the MIDI range C-2..G8".format(name))
    return pitch


def _spelled(letter, accidentals, wrap=True):
    value = _NATURAL[letter.upper()] + sum(_ACCIDENTAL[char] for char in accidentals)
    return value % 12 if wrap else value


# -- intervals and scales ----------------------------------------------------------------------------


def interval_class(a, b):
    """Distance between two pitches (or pitch classes) folded into 0..6 semitones, whatever the octaves."""
    distance = abs(int(a) - int(b)) % 12
    return min(distance, 12 - distance)


def is_semitone_apart(a, b):
    """True when two pitches are a semitone apart in any octave (a minor second, a major seventh, a minor ninth)."""
    return interval_class(a, b) == 1


def in_scale(pitch, scale):
    """Whether a pitch belongs to a scale given as pitch classes (`Spec.scale` is a frozenset of them)."""
    return pitch_class(pitch) in scale


def semitone_neighbours(pitch_classes):
    """The pitch classes a semitone above or below any of the given ones (they may include the given ones)."""
    out = set()
    for pc in pitch_classes:
        out.add((int(pc) + 1) % 12)
        out.add((int(pc) - 1) % 12)
    return frozenset(out)


# -- chords ---------------------------------------------------------------------------------------


def parse_chord(symbol):
    """Chord(symbol, root, quality, tones, bass, flats) for "Am", "F", "E7", "Bdim", "Asus4", "Am7/E".

    Raises ValueError for a symbol it does not know.
    """
    return _parse_chord(str(symbol).strip())


@lru_cache(maxsize=None)
def _parse_chord(text):
    body, slash, bass_text = text.partition("/")
    match = _ROOT.match(body)
    if not match:
        raise ValueError("Not a chord symbol: {0!r}".format(text))
    letter, accidentals, suffix = match.group(1), match.group(2), match.group(3).strip()
    if suffix not in _SUFFIX:
        raise ValueError("Unknown chord quality {0!r} in {1!r}; known: {2}".format(
            suffix, text, ", ".join(repr(s) for s in sorted(_SUFFIX, key=lambda s: (len(s), s)) if s)))
    root = _spelled(letter, accidentals)
    quality, intervals = _SUFFIX[suffix]
    tones = []
    for interval in intervals:
        pc = (root + interval) % 12
        if pc not in tones:
            tones.append(pc)
    bass = None
    if slash:
        bass = parse_pitch_class(bass_text)
        if bass not in tones:
            tones.append(bass)
    flat_root = any(_ACCIDENTAL[char] < 0 for char in accidentals)
    flats = flat_root or (letter.upper() in "FCGD" and 3 in intervals and not accidentals)
    return Chord(text, root, quality, tuple(tones), bass, flats)


def chord_root(symbol):
    """Pitch class of the chord's root."""
    return parse_chord(symbol).root


def chord_tones(symbol):
    """Pitch classes of the chord's tones, as a frozenset ("Dm" -> {2, 5, 9})."""
    return frozenset(parse_chord(symbol).tones)


def describe_chord(symbol):
    """"Dm (D F A)": the symbol with its tones spelled out, for messages."""
    chord = parse_chord(symbol)
    return "{0} ({1})".format(chord.symbol, " ".join(pc_name(pc, chord.flats) for pc in chord.tones))
