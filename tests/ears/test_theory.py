"""Unit tests for ears/theory.py: note names in Live's convention, intervals, scale membership and chords."""
import pytest

from ears import theory
from ears.spec import load


# ---------------------------------------------------------------------------
# Note names (C3 = 60)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pitch, name", [
    (60, "C3"), (45, "A1"), (43, "G1"), (0, "C-2"), (127, "G8"), (69, "A3"), (61, "C#3"), (59, "B2"), (36, "C1"), (81, "A4"),
])
def test_note_name_uses_lives_convention(pitch, name):
    assert theory.note_name(pitch) == name


def test_note_name_flats():
    assert theory.note_name(70, flats=True) == "Bb3"
    assert theory.note_name(70) == "A#3"
    assert theory.pc_name(8) == "G#" and theory.pc_name(8, flats=True) == "Ab"


@pytest.mark.parametrize("name, pitch", [
    ("C3", 60), ("A1", 45), ("G1", 43), ("C-2", 0), ("G8", 127), ("F#2", 54), ("Gb2", 54), ("Bb3", 70), ("bb3", 70),
    ("b3", 71), ("Cb3", 59), ("B#2", 60), ("C♯3", 61), ("D♭3", 61),
])
def test_parse_note(name, pitch):
    assert theory.parse_note(name) == pitch


@pytest.mark.parametrize("bad", ["H3", "C", "C9", "C-3", "", "Am", "F#", "3C", None])
def test_parse_note_rejects(bad):
    with pytest.raises(ValueError):
        theory.parse_note(bad)


def test_names_round_trip_every_pitch():
    for pitch in range(128):
        assert theory.parse_note(theory.note_name(pitch)) == pitch
        assert theory.parse_note(theory.note_name(pitch, flats=True)) == pitch


@pytest.mark.parametrize("name, pc", [("A", 9), ("G#", 8), ("Ab", 8), ("Bb", 10), ("C", 0), ("B", 11), ("F♯", 6), ("E♭", 3)])
def test_parse_pitch_class(name, pc):
    assert theory.parse_pitch_class(name) == pc


@pytest.mark.parametrize("bad", ["Am", "H", "", "A3"])
def test_parse_pitch_class_rejects(bad):
    with pytest.raises(ValueError):
        theory.parse_pitch_class(bad)


def test_pitch_class_of_pitch():
    assert theory.pitch_class(45) == 9 and theory.pitch_class(60) == 0 and theory.pitch_class(127) == 7


# ---------------------------------------------------------------------------
# Intervals and scales
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("a, b, expected", [
    (60, 60, 0), (60, 61, 1), (61, 60, 1), (60, 62, 2), (60, 67, 5), (60, 66, 6), (60, 72, 0), (60, 71, 1), (60, 49, 1),
    (45, 56, 1), (57, 56, 1), (0, 127, 5),
])
def test_interval_class(a, b, expected):
    assert theory.interval_class(a, b) == expected


def test_is_semitone_apart_in_any_octave():
    assert theory.is_semitone_apart(60, 61)       # a minor second
    assert theory.is_semitone_apart(60, 71)       # a major seventh
    assert theory.is_semitone_apart(45, 80)       # three octaves and a major seventh
    assert theory.is_semitone_apart(57, 68)       # A and G#
    assert not theory.is_semitone_apart(60, 62)
    assert not theory.is_semitone_apart(60, 60)
    assert not theory.is_semitone_apart(60, 72)


def test_in_scale_uses_the_specs_scale():
    scale = load("nova").scale   # A natural minor
    assert sorted(scale) == [0, 2, 4, 5, 7, 9, 11]
    for pitch in (57, 59, 60, 62, 64, 65, 67, 45, 43):
        assert theory.in_scale(pitch, scale), pitch
    for pitch in (56, 58, 61, 63, 66, 68, 42, 44):   # G#, Bb, C#, D#, F#
        assert not theory.in_scale(pitch, scale), pitch


def test_semitone_neighbours():
    assert theory.semitone_neighbours([9]) == frozenset([8, 10])
    assert theory.semitone_neighbours([0]) == frozenset([11, 1])         # wraps around the octave
    assert theory.semitone_neighbours([4, 5]) == frozenset([3, 4, 5, 6])  # E and F are each other's neighbours
    assert theory.semitone_neighbours([]) == frozenset()


def test_the_pad_rule_example_from_the_prd():
    """Over Dm (A) and E (B) in the fourth bar only D and B are safe for a shared pad."""
    tones = theory.chord_tones("Dm") | theory.chord_tones("E")
    forbidden = theory.semitone_neighbours(tones)
    safe = [theory.pc_name(pc) for pc in range(12) if pc not in forbidden and pc in load("nova").scale | tones]
    assert sorted(safe) == ["B", "D"]


# ---------------------------------------------------------------------------
# Chords
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol, root, tones", [
    ("Am", 9, (9, 0, 4)),
    ("F", 5, (5, 9, 0)),
    ("E", 4, (4, 8, 11)),
    ("G", 7, (7, 11, 2)),
    ("C", 0, (0, 4, 7)),
    ("Dm", 2, (2, 5, 9)),
    ("E7", 4, (4, 8, 11, 2)),
    ("Bdim", 11, (11, 2, 5)),
    ("Asus4", 9, (9, 2, 4)),
    ("Asus2", 9, (9, 11, 4)),
    ("Bb", 10, (10, 2, 5)),
    ("F#m", 6, (6, 9, 1)),
    ("Cmaj7", 0, (0, 4, 7, 11)),
    ("Am7", 9, (9, 0, 4, 7)),
    ("Em7b5", 4, (4, 7, 10, 2)),
    ("Caug", 0, (0, 4, 8)),
    ("C5", 0, (0, 7)),
])
def test_parse_chord(symbol, root, tones):
    chord = theory.parse_chord(symbol)
    assert chord.root == root
    assert chord.tones == tones
    assert theory.chord_root(symbol) == root
    assert theory.chord_tones(symbol) == frozenset(tones)


def test_chord_tones_are_a_frozenset_of_pitch_classes():
    assert theory.chord_tones("Am") == frozenset([9, 0, 4])
    assert isinstance(theory.chord_tones("Am"), frozenset)


def test_every_chord_of_the_nova_progressions_parses_and_has_no_semitone_inside():
    spec = load("nova")
    for name, chords in spec.progressions.items():
        for symbol in chords:
            tones = sorted(theory.chord_tones(symbol))
            for a in tones:
                for b in tones:
                    assert theory.interval_class(a, b) != 1, (name, symbol)


def test_slash_chord_keeps_its_bass_as_a_tone():
    chord = theory.parse_chord("Am/G")
    assert chord.root == 9 and chord.bass == 7
    assert 7 in chord.tones and chord.tones[:3] == (9, 0, 4)
    assert theory.parse_chord("Am/E").tones == (9, 0, 4)   # the bass is already a tone


@pytest.mark.parametrize("bad", ["", "H", "Amaj13", "Xm", "N.C.", "A/H", "A!", None, ["Am"], {"chord": "Am"}, 5])
def test_parse_chord_rejects(bad):
    with pytest.raises(ValueError):
        theory.parse_chord(bad)


def test_describe_chord_spells_the_tones():
    assert theory.describe_chord("Dm") == "Dm (D F A)"
    assert theory.describe_chord("E") == "E (E G# B)"
    assert theory.describe_chord("Am") == "Am (A C E)"
    assert theory.describe_chord("Bb") == "Bb (Bb D F)"
    assert theory.describe_chord("Gm") == "Gm (G Bb D)"
    assert theory.describe_chord("F#m") == "F#m (F# A C#)"
