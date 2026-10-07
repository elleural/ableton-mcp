"""Unit tests for MCP_Server/theory.py: notes, scales, chords, progressions and the music_theory tool."""
import pytest

from MCP_Server import theory
from MCP_Server.theory import TheoryError


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text, pitch", [
    ("C3", 60), ("C-2", 0), ("G8", 127), ("A3", 69), ("F#2", 54), ("Gb2", 54), ("Bb3", 70), ("bb3", 70), ("B#3", 72),
    ("Cb4", 71), ("E#3", 65), ("C##3", 62), ("Dbb3", 60), ("C♯3", 61), ("D♭3", 61), (64, 64), (64.0, 64), ("72", 72),
])
def test_parse_pitch(text, pitch):
    assert theory.parse_pitch(text) == pitch


@pytest.mark.parametrize("bad", ["H3", "C", "C9", "C-3", 128, -1, True, None, "x", 60.5, "Cbbb3"])
def test_parse_pitch_rejects(bad):
    with pytest.raises(TheoryError):
        theory.parse_pitch(bad)


def test_parse_pitch_error_mentions_octave_for_pitch_class():
    with pytest.raises(TheoryError, match="needs an octave"):
        theory.parse_pitch("F#")


@pytest.mark.parametrize("pitch, sharp, flat", [(60, "C3", "C3"), (61, "C#3", "Db3"), (0, "C-2", "C-2"), (127, "G8", "G8"), (70, "A#3", "Bb3")])
def test_pitch_name(pitch, sharp, flat):
    assert theory.pitch_name(pitch) == sharp
    assert theory.pitch_name(pitch, flats=True) == flat


def test_names_round_trip_every_pitch():
    for pitch in range(128):
        assert theory.parse_pitch(theory.pitch_name(pitch)) == pitch
        assert theory.parse_pitch(theory.pitch_name(pitch, flats=True)) == pitch


@pytest.mark.parametrize("pitch, letter, name", [(70, "B", "Bb3"), (70, "A", "A#3"), (71, "C", "Cb4"), (72, "B", "B#3"), (60, "D", "Dbb3")])
def test_spell_pitch(pitch, letter, name):
    assert theory.spell_pitch(pitch, letter) == name
    assert theory.parse_pitch(name) == pitch


def test_frequency_uses_live_naming():
    assert theory.frequency(69) == pytest.approx(440.0)  # A3 in Live's naming
    assert theory.frequency(60) == pytest.approx(261.626, abs=1e-3)


def test_describe_note_keeps_input_spelling():
    out = theory.describe_note("Bb2")
    assert out["pitch"] == 58 and out["name"] == "Bb2" and out["sharp_name"] == "A#2" and out["flat_name"] == "Bb2"
    assert out["octave"] == 2 and out["pitch_class"] == 10
    pitch_class = theory.describe_note("F#")
    assert pitch_class == {"input": "F#", "pitch_class": 6, "name": "F#", "sharp_name": "F#", "flat_name": "Gb"}


# ---------------------------------------------------------------------------
# Scales
# ---------------------------------------------------------------------------


def test_live_scales_are_complete_and_rooted():
    assert len(theory.LIVE_SCALES) == 35
    for name, intervals in theory.ALL_SCALES:
        assert intervals[0] == 0 and list(intervals) == sorted(set(intervals)) and max(intervals) < 12, name


@pytest.mark.parametrize("name, canonical", [
    ("major", "Major"), ("Ionian", "Major"), ("aeolian", "Minor"), ("natural minor", "Minor"), ("dorian", "Dorian"),
    ("harmonic minor", "Harmonic Minor"), ("Melodic-Minor", "Melodic Minor"), ("pentatonic", "Major Pentatonic"),
    ("minor pentatonic", "Minor Pentatonic"), ("blues", "Minor Blues"), ("whole tone", "Whole Tone"),
    ("half-whole dim.", "Half-whole Dim."), ("halfwhole", "Half-whole Dim."), ("diminished", "Whole-half Dim."),
    ("altered", "Super Locrian"), ("Dorian #4", "Dorian #4"), ("8-tone spanish", "8-Tone Spanish"), ("chromatic", "Chromatic"),
    ("major blues", "Major Blues"), ("lydian dominant", "Lydian Dominant"), ("in-sen", "In-Sen"), ("messiaen 3", "Messiaen 3"),
])
def test_find_scale_names_and_aliases(name, canonical):
    assert theory.find_scale(name).name == canonical


def test_find_scale_custom_and_unknown():
    assert theory.find_scale([2, 4, 7]).intervals == (0, 2, 4, 7)
    with pytest.raises(TheoryError, match="Unknown scale"):
        theory.find_scale("bebop wonder")


@pytest.mark.parametrize("key, scale, notes", [
    ("C", "major", ["C", "D", "E", "F", "G", "A", "B"]),
    ("A minor", None, ["A", "B", "C", "D", "E", "F", "G"]),
    ("F", "major", ["F", "G", "A", "Bb", "C", "D", "E"]),
    ("Eb", "major", ["Eb", "F", "G", "Ab", "Bb", "C", "D"]),
    ("F#", "major", ["F#", "G#", "A#", "B", "C#", "D#", "E#"]),
    ("Gb", "major", ["Gb", "Ab", "Bb", "Cb", "Db", "Eb", "F"]),
    ("D", "dorian", ["D", "E", "F", "G", "A", "B", "C"]),
    ("E", "phrygian", ["E", "F", "G", "A", "B", "C", "D"]),
    ("A", "harmonic minor", ["A", "B", "C", "D", "E", "F", "G#"]),
    ("C", "minor pentatonic", ["C", "Eb", "F", "G", "Bb"]),
    ("E", "minor pentatonic", ["E", "G", "A", "B", "D"]),
    ("F#m", None, ["F#", "G#", "A", "B", "C#", "D", "E"]),
    ("Bbm", None, ["Bb", "C", "Db", "Eb", "F", "Gb", "Ab"]),
])
def test_scale_spelling(key, scale, notes):
    assert theory.scale_info(key, scale)["notes"] == notes


@pytest.mark.parametrize("pc, scale, root", [(10, "major", "Bb"), (1, "major", "Db"), (6, "major", "F#"), (8, "minor", "G#"), (3, "minor", "Eb"), (3, "major", "Eb")])
def test_numeric_roots_choose_the_simpler_key_signature(pc, scale, root):
    assert theory.scale_info(pc, scale)["root"] == root


def test_scale_pitches_span_octaves_with_top_root():
    out = theory.scale_info("C", "major", octave=3, octaves=2)
    assert out["pitches"][:8] == [60, 62, 64, 65, 67, 69, 71, 72]
    assert len(out["pitches"]) == 15 and out["pitches"][-1] == 84
    assert out["names"][0] == "C3" and out["names"][-1] == "C5"
    assert out["live_scale"] == "Major" and out["key"] == "C major"


def test_scale_names_use_key_spelling():
    out = theory.scale_info("Eb", "minor", octave=2)
    assert out["names"] == ["Eb2", "F2", "Gb2", "Ab2", "Bb2", "Cb3", "Db3", "Eb3"]
    assert [theory.parse_pitch(name) for name in out["names"]] == out["pitches"]


def test_scale_rejects_out_of_range_octaves():
    with pytest.raises(TheoryError):
        theory.scale_info("C", "major", octave=8, octaves=2)
    with pytest.raises(TheoryError):
        theory.scale_info("C", "major", octaves=0)


def test_parse_key_forms():
    assert theory.parse_key("Am").scale == "Minor"
    assert theory.parse_key("A minor").scale == "Minor"
    assert theory.parse_key("A min").scale == "Minor"
    assert theory.parse_key("F# dorian").scale == "Dorian" and theory.parse_key("F# dorian").pc == 6
    assert theory.parse_key("C", "minor").scale == "Minor"
    assert theory.parse_key("Bb").pc == 10 and theory.parse_key("Bb").scale == "Major"
    with pytest.raises(TheoryError):
        theory.parse_key("H")
    with pytest.raises(TheoryError):
        theory.parse_key(None)


# ---------------------------------------------------------------------------
# Chords
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol, pitches", [
    ("C", [60, 64, 67]), ("Cm", [60, 63, 67]), ("Cmin", [60, 63, 67]), ("C-", [60, 63, 67]), ("Cdim", [60, 63, 66]),
    ("C°", [60, 63, 66]), ("Caug", [60, 64, 68]), ("C+", [60, 64, 68]), ("Csus2", [60, 62, 67]), ("Csus4", [60, 65, 67]),
    ("Csus", [60, 65, 67]), ("C5", [60, 67]), ("C6", [60, 64, 67, 69]), ("Cm6", [60, 63, 67, 69]), ("C6/9", [60, 64, 67, 69, 74]),
    ("C7", [60, 64, 67, 70]), ("Cmaj7", [60, 64, 67, 71]), ("CM7", [60, 64, 67, 71]), ("CΔ", [60, 64, 67, 71]),
    ("CΔ7", [60, 64, 67, 71]), ("Cm7", [60, 63, 67, 70]), ("C-7", [60, 63, 67, 70]), ("CmMaj7", [60, 63, 67, 71]),
    ("Cm(maj7)", [60, 63, 67, 71]), ("Cdim7", [60, 63, 66, 69]), ("C°7", [60, 63, 66, 69]), ("Cm7b5", [60, 63, 66, 70]),
    ("Cø", [60, 63, 66, 70]), ("Cø7", [60, 63, 66, 70]), ("Caug7", [60, 64, 68, 70]), ("C+7", [60, 64, 68, 70]),
    ("C7#5", [60, 64, 68, 70]), ("C7b5", [60, 64, 66, 70]), ("C7sus4", [60, 65, 67, 70]), ("C9", [60, 64, 67, 70, 74]),
    ("Cmaj9", [60, 64, 67, 71, 74]), ("Cm9", [60, 63, 67, 70, 74]), ("C11", [60, 64, 67, 70, 74, 77]),
    ("Cm11", [60, 63, 67, 70, 74, 77]), ("C13", [60, 64, 67, 70, 74, 81]), ("Cmaj13", [60, 64, 67, 71, 74, 81]),
    ("C7b9", [60, 64, 67, 70, 73]), ("C7#9", [60, 64, 67, 70, 75]), ("Cmaj7#11", [60, 64, 67, 71, 78]),
    ("C13b9", [60, 64, 67, 70, 73, 81]), ("C7(b9,#11)", [60, 64, 67, 70, 73, 78]), ("Cadd9", [60, 64, 67, 74]),
    ("Cmadd9", [60, 63, 67, 74]), ("Cadd2", [60, 62, 64, 67]), ("Cadd11", [60, 64, 67, 77]), ("C7no3", [60, 67, 70]),
    ("C9sus4", [60, 65, 67, 70, 74]), ("Cmaj", [60, 64, 67]), ("Cmajor7", [60, 64, 67, 71]), ("C7-9", [60, 64, 67, 70, 73]),
])
def test_chord_qualities(symbol, pitches):
    assert theory.chord_lookup(symbol)["pitches"] == pitches


@pytest.mark.parametrize("symbol, notes", [
    ("Am7", ["A", "C", "E", "G"]), ("F#m7b5", ["F#", "A", "C", "E"]), ("Ebmaj7", ["Eb", "G", "Bb", "D"]),
    ("Bbm", ["Bb", "Db", "F"]), ("Cdim7", ["C", "Eb", "Gb", "Bbb"]), ("Caug", ["C", "E", "G#"]), ("Db7", ["Db", "F", "Ab", "Cb"]),
    ("G7b9", ["G", "B", "D", "F", "Ab"]), ("E7#9", ["E", "G#", "B", "D", "F##"]),
])
def test_chord_spelling(symbol, notes):
    assert theory.chord_lookup(symbol)["notes"] == notes


def test_chord_output_fields():
    out = theory.chord_lookup("Am7", octave=2)
    assert out["symbol"] == "Am7" and out["root"] == "A" and out["quality"] == "m7"
    assert out["tones"] == ["1", "b3", "5", "b7"]
    assert out["pitches"] == [57, 60, 64, 67] and out["names"] == ["A2", "C3", "E3", "G3"]
    assert theory.chord_lookup("C")["quality"] == "maj"


def test_inversions():
    assert theory.chord_lookup("C", inversion=1)["pitches"] == [64, 67, 72]
    assert theory.chord_lookup("C", inversion=2)["pitches"] == [67, 72, 76]
    assert theory.chord_lookup("Cmaj7", inversion=3)["pitches"] == [71, 72, 76, 79]
    with pytest.raises(TheoryError, match="inversion"):
        theory.chord_lookup("C", inversion=3)


@pytest.mark.parametrize("voicing, pitches", [
    ("close", [60, 64, 67, 71]), ("drop2", [55, 60, 64, 71]), ("drop3", [52, 60, 67, 71]), ("open", [60, 67, 76, 83]),
    ("spread", [48, 64, 67, 71]),
])
def test_voicings(voicing, pitches):
    assert theory.chord_lookup("Cmaj7", voicing=voicing)["pitches"] == pitches


def test_unknown_voicing():
    with pytest.raises(TheoryError, match="voicing"):
        theory.chord_lookup("C", voicing="cluster")


def test_slash_chords():
    assert theory.chord_lookup("C/E")["pitches"] == [64, 67, 72]
    assert theory.chord_lookup("C/G")["pitches"] == [67, 72, 76]
    assert theory.chord_lookup("Am7/G")["pitches"] == [67, 69, 72, 76]
    assert theory.chord_lookup("C/D")["pitches"] == [50, 60, 64, 67]
    assert theory.chord_lookup("C/Bb")["names"][0] == "Bb2"
    out = theory.chord_lookup("F/A")
    assert out["bass"] == "A" and out["symbol"] == "F/A" and out["pitches"][0] % 12 == 9


@pytest.mark.parametrize("bad", ["", "H7", "Cxyz", "C7#", 5, None])
def test_bad_chords(bad):
    with pytest.raises(TheoryError):
        theory.chord_lookup(bad)


def test_chord_out_of_range():
    with pytest.raises(TheoryError):
        theory.chord_lookup("C13", octave=8)


def test_parse_chord_symbol_round_trip():
    for symbol in ("C", "Dm7", "G7sus4", "Ebmaj9", "F#m7b5", "Bb13", "Abaug", "C#dim7", "E7b9#11"):
        chord = theory.parse_chord(symbol)
        assert theory.parse_chord(theory.chord_symbol(chord)).tones == chord.tones


# ---------------------------------------------------------------------------
# Progressions
# ---------------------------------------------------------------------------


def _symbols(result):
    return [chord["symbol"] for chord in result["chords"]]


def test_pop_progression_in_c():
    out = theory.progression_info("C", "I-V-vi-IV")
    assert _symbols(out) == ["C", "G", "Am", "F"]
    assert out["notes"][0] == {"pitches": [60, 64, 67], "start": 0.0, "duration": 4.0}
    assert [note["start"] for note in out["notes"]] == [0.0, 4.0, 8.0, 12.0]
    assert out["length"] == 16.0 and out["key"] == "C major"


def test_minor_key_degrees_and_flat_numerals():
    assert _symbols(theory.progression_info("A minor", "i iv v VI III VII")) == ["Am", "Dm", "Em", "F", "C", "G"]
    assert _symbols(theory.progression_info("A minor", "i-bVI-bIII-bVII")) == ["Am", "F", "C", "G"]
    assert _symbols(theory.progression_info("A minor", "i iv V7 i")) == ["Am", "Dm", "E7", "Am"]


def test_sevenths_and_qualities():
    out = theory.progression_info("C", ["ii7", "V7", "Imaj7", "vi7", "iii7", "viiø7", "vii°7", "IV6", "Vsus4", "ii9"])
    assert _symbols(out) == ["Dm7", "G7", "Cmaj7", "Am7", "Em7", "Bm7b5", "Bdim7", "F6", "Gsus4", "Dm9"]


def test_borrowed_and_secondary_chords():
    out = theory.progression_info("C", "bVII bIII bVI iv V7/V V/vi vii°7/V #ivø7")
    assert _symbols(out) == ["Bb", "Eb", "Ab", "Fm", "D7", "E", "F#dim7", "F#m7b5"]


def test_progression_spelling_in_flat_keys():
    out = theory.progression_info("Eb", "I IV V7 vi")
    assert _symbols(out) == ["Eb", "Ab", "Bb7", "Cm"]
    assert out["chords"][2]["notes"] == ["Bb", "D", "F", "Ab"]


def test_chord_symbols_in_progressions_and_separators():
    assert _symbols(theory.progression_info("C", "Am | F | C | G")) == ["Am", "F", "C", "G"]
    assert _symbols(theory.progression_info("C", "Dm7, G7, Cmaj7")) == ["Dm7", "G7", "Cmaj7"]
    assert _symbols(theory.progression_info("C", "ii7 -> V7 -> I")) == ["Dm7", "G7", "C"]


def test_beats_per_chord_scalar_and_list():
    out = theory.progression_info("C", "I V", beats_per_chord=2)
    assert [(note["start"], note["duration"]) for note in out["notes"]] == [(0.0, 2.0), (2.0, 2.0)]
    out = theory.progression_info("C", "I V vi", beats_per_chord=[4, 2, 2])
    assert [note["start"] for note in out["notes"]] == [0.0, 4.0, 6.0] and out["length"] == 8.0
    with pytest.raises(TheoryError):
        theory.progression_info("C", "I V", beats_per_chord=[4])
    with pytest.raises(TheoryError):
        theory.progression_info("C", "I V", beats_per_chord=0)


def test_voice_leading_moves_less_than_root_position():
    plain = theory.progression_info("C", "I vi IV V")
    led = theory.progression_info("C", "I vi IV V", voice_leading=True)

    def movement(result):
        chords = [chord["pitches"] for chord in result["chords"]]
        return sum(theory._movement(first, second) for first, second in zip(chords, chords[1:]))

    assert movement(led) < movement(plain)
    assert led["chords"][0]["pitches"] == [60, 64, 67]
    assert [sorted(set(pitch % 12 for pitch in chord["pitches"])) for chord in led["chords"]] == \
        [sorted(set(pitch % 12 for pitch in chord["pitches"])) for chord in plain["chords"]]
    for chord in led["chords"]:
        assert [theory.parse_pitch(name) for name in chord["names"]] == chord["pitches"]


def test_progression_errors():
    with pytest.raises(TheoryError, match="7-note scale"):
        theory.progression_info("C", "I IV", scale="major pentatonic")
    with pytest.raises(TheoryError):
        theory.progression_info("C", "I Q")
    with pytest.raises(TheoryError):
        theory.progression_info("C", "")


def test_numeral_chord_needs_key():
    assert theory.chord_lookup("V7", key="C")["symbol"] == "G7"
    with pytest.raises(TheoryError, match="needs a key"):
        theory.chord_lookup("V7")


# ---------------------------------------------------------------------------
# Chord shorthand for write_notes and the dispatcher
# ---------------------------------------------------------------------------


def test_expand_note_chords():
    notes = [{"chord": "Am7", "start": 0, "duration": 4, "octave": 2, "velocity": 90},
             {"pitch": "C3", "start": 4, "duration": 1},
             {"chord": "C/E", "start": 4, "duration": 2, "voicing": "close"},
             {"chord": "V7", "key": "C", "start": 6, "duration": 2}]
    out = theory.expand_note_chords(notes)
    assert out[0] == {"start": 0, "duration": 4, "velocity": 90, "pitches": [57, 60, 64, 67]}
    assert out[1] == notes[1]
    assert out[2]["pitches"] == [64, 67, 72] and "chord" not in out[2]
    assert out[3]["pitches"] == [67, 71, 74, 77]
    with pytest.raises(TheoryError, match="notes\\[0\\]"):
        theory.expand_note_chords([{"chord": "C", "pitch": 60, "start": 0, "duration": 1}])
    with pytest.raises(TheoryError, match="notes\\[0\\]"):
        theory.expand_note_chords([{"chord": "Hm", "start": 0, "duration": 1}])
    assert theory.expand_note_chords("not a list") == "not a list"


def test_music_theory_dispatcher():
    assert theory.music_theory("scale", key="D", scale="dorian")["notes"][0] == "D"
    assert theory.music_theory("chord", chord="G7")["pitches"] == [67, 71, 74, 77]
    assert theory.music_theory("chord", chord="ii7", key="F")["symbol"] == "Gm7"
    assert theory.music_theory("progression", key="G", progression=["I", "IV"])["notes"][1]["pitches"] == [60, 64, 67]
    assert theory.music_theory("notes", notes=["C3", 61])["notes"][1]["name"] == "C#3"
    assert theory.music_theory("note", notes="A3")["notes"][0]["frequency"] == 440.0
    listing = theory.music_theory("list")
    assert "Major" in listing["scales"] and "m7b5" in listing["chord_qualities"] and "drop2" in listing["voicings"]
    with pytest.raises(TheoryError, match="operation"):
        theory.music_theory("compose")
    with pytest.raises(TheoryError, match="needs key"):
        theory.music_theory("scale")
    with pytest.raises(TheoryError, match="needs chord"):
        theory.music_theory("chord")
    with pytest.raises(TheoryError, match="progression needs"):
        theory.music_theory("progression", key="C")


def test_music_theory_tool_raises_tool_errors():
    from mcp.server.mcpserver.exceptions import ToolError

    from MCP_Server.tools.theory import music_theory

    assert music_theory("chord", chord="Cmaj7")["pitches"] == [60, 64, 67, 71]
    with pytest.raises(ToolError):
        music_theory("chord", chord="Hmaj7")
