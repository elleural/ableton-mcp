"""Music theory (docs/PRD.md section 7.10): scales, chords, progressions and note names, computed locally."""
from mcp.server.mcpserver.exceptions import ToolError

from .. import theory
from ..app import tool


@tool(read_only=True)
def music_theory(operation: str, key: str | int | None = None, scale: str | None = None, chord: str | None = None,
                 progression: str | list[str] | None = None, notes: list[int | str] | None = None, octave: int = 3,
                 octaves: int = 1, inversion: int = 0, voicing: str = "close", beats_per_chord: float | list[float] = 4.0,
                 voice_leading: bool = False) -> dict:
    """Music theory without touching Live (C3 = 60). operation:
    scale: key ("A", "F# dorian") + scale (any Live scale name, "minor", "blues"...) -> notes, pitches from `octave`.
    chord: chord symbol ("Am7", "F#m7b5", "C7sus4", "Cadd9", "C/E"), or a numeral ("V7") with key; inversion, voicing
    (close, open, drop2, drop3, spread), octave -> pitches.
    progression: key ("C", "A minor") + numerals ("ii7-V7-Imaj7", "i-bVI-bIII-bVII", "V7/V") or chord symbols;
    beats_per_chord, voice_leading -> chords plus "notes" ready for write_notes.
    notes: note names or numbers -> MIDI number, names, frequency. list: available scales, chords, voicings.
    """
    try:
        return theory.music_theory(operation, key=key, scale=scale, chord=chord, progression=progression, notes=notes,
                                   octave=octave, octaves=octaves, inversion=inversion, voicing=voicing,
                                   beats_per_chord=beats_per_chord, voice_leading=voice_leading)
    except theory.TheoryError as error:
        raise ToolError(str(error))
