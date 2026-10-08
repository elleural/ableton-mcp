"""Clips and notes (docs/PRD.md section 7.5): create, inspect, edit, transform, pattern and launch clips.

Every clip tool addresses a clip by `track` plus exactly one of `slot` (Session scene index) or
`arrangement_clip` (index in the track's arrangement clips, ordered by start time).
"""
import time

from mcp.server.mcpserver.exceptions import ToolError

from .. import theory
from ..app import call, tool
from .references import loopback_busy

CONVERSION_WAIT = 30.0  # seconds clip_action waits for Live's audio-to-MIDI conversion


@tool(destructive=True)
def create_clip(track: int | str, slot: int | None = None, at: float | str | None = None, length: float | str | None = None,
                name: str | None = None, color: int | str | None = None, file_path: str | None = None,
                notes: list[dict] | None = None, pattern: dict[str, str] | None = None) -> dict:
    """Create a clip: MIDI in an empty Session `slot` (0-based scene index) or on the arrangement `at` a time; audio
    from `file_path` on audio tracks. Optionally fill it in the same call: notes (as write_notes) and/or pattern (drum
    steps, as write_drum_pattern).

    length: MIDI only, beats or "N bars" (default 4 beats; a bare number is beats). at: beats, "bar.beat.sixteenth"
    ("9.1.1") or a locator name. MIDI ranges that overlap arrangement clips are refused (audio reports what it trimmed).
    color: index 0..69 or "#RRGGBB". Returns the new clip (as get_clip).
    Example: create_clip("Drums", slot=0, length="1 bar", pattern={"kick": "x---x---x---x---"}).
    """
    created = call("create_clip", track=track, slot=slot, at=at, length=length, name=name, color=color, file_path=file_path)
    if notes is None and pattern is None:
        return created
    where = {"slot": slot} if slot is not None else {"arrangement_clip": created.get("arrangement_clip")}
    if notes is not None:
        written = write_notes(track=track, notes=notes, mode="add", **where)
        created["notes_written"] = written.get("count", written.get("added", len(notes)))
    if pattern is not None:
        drums = write_drum_pattern(track=track, pattern=pattern, **where)
        created["pattern"] = dict((key, drums[key]) for key in ("drums", "notes_written", "warnings") if key in drums)
    created["undo_steps"] = 1 + (notes is not None) + (pattern is not None)
    return created


@tool(read_only=True)
def get_clip(track: int | str, slot: int | None = None, arrangement_clip: int | None = None, notes: bool = False,
             limit: int = 200) -> dict:
    """Every property of one clip: name, colour, length (beats and bars), loop and markers, signature, launch mode and
    quantization, legato, mute, velocity amount, groove, grid, playing state and automated parameters.

    Audio clips add gain_db, pitch, warping, warp mode, file and warp markers. Arrangement clips give start and end in
    beats and bars. notes=True adds up to `limit` notes (or use get_notes with filters).
    """
    return call("get_clip", track=track, slot=slot, arrangement_clip=arrangement_clip, notes=notes, limit=limit)


@tool(idempotent=True)
def set_clip(track: int | str, slot: int | None = None, arrangement_clip: int | None = None, name: str | None = None,
             color: int | str | None = None, looping: bool | None = None, loop_start: float | str | None = None,
             loop_end: float | str | None = None, start_marker: float | str | None = None, end_marker: float | str | None = None,
             signature: str | None = None, launch_mode: str | None = None, launch_quantization: str | None = None,
             legato: bool | None = None, muted: bool | None = None, velocity_amount: float | None = None,
             groove: int | str | None = None, grid: str | None = None, grid_triplet: bool | None = None,
             gain_db: float | str | None = None, pitch_coarse: int | None = None, pitch_fine: float | None = None,
             warping: bool | None = None, warp_mode: str | None = None, ram_mode: bool | None = None) -> dict:
    """Set clip properties; only the ones you pass change. Returns the clip as get_clip.

    Times are clip beats or "bar.beat.sixteenth" (1.1.1 = clip start; seconds for unwarped audio). signature "3/4".
    launch_mode: trigger, gate, toggle, repeat. launch_quantization: global, none, "1 bar", "1/4", ... grid: "1/16", ...
    groove: groove pool name or index. Audio only: gain_db (-inf..+24), pitch_coarse (-48..48 semitones),
    pitch_fine (-50..49 cents), warping, warp_mode (beats, tones, texture, repitch, complex, complex_pro), ram_mode.
    Example: set_clip(track="Keys", slot=0, loop_end="3.1.1", launch_quantization="1 bar").
    """
    return call("set_clip", track=track, slot=slot, arrangement_clip=arrangement_clip, name=name, color=color, looping=looping,
                loop_start=loop_start, loop_end=loop_end, start_marker=start_marker, end_marker=end_marker, signature=signature,
                launch_mode=launch_mode, launch_quantization=launch_quantization, legato=legato, muted=muted,
                velocity_amount=velocity_amount, groove=groove, grid=grid, grid_triplet=grid_triplet, gain_db=gain_db,
                pitch_coarse=pitch_coarse, pitch_fine=pitch_fine, warping=warping, warp_mode=warp_mode, ram_mode=ram_mode)


@tool(destructive=True)
def delete_clip(track: int | str, slot: int | None = None, arrangement_clip: int | None = None) -> dict:
    """Delete a Session or arrangement clip. Destructive: confirm with the user before deleting their own material."""
    return call("delete_clip", track=track, slot=slot, arrangement_clip=arrangement_clip)


@tool(destructive=True)
def duplicate_clip(track: int | str, slot: int | None = None, arrangement_clip: int | None = None, to_track: int | str | None = None,
                   to_slot: int | None = None, to_time: float | str | None = None, move: bool = False) -> dict:
    """Copy (or move=True) a clip: Session -> Session slot, Session -> arrangement, or arrangement -> arrangement.

    to_slot: empty Session slot (default: next empty slot below, same track). to_time: arrangement time in beats or
    "bar.beat.sixteenth" (arrangement sources default to right after themselves). to_track defaults to the same track.
    Clip envelopes travel with the copy. Occupied slots and overlapping arrangement ranges are refused.
    Example: duplicate_clip(track="Drums", slot=0, to_time="9.1.1").
    """
    return call("duplicate_clip", track=track, slot=slot, arrangement_clip=arrangement_clip, to_track=to_track, to_slot=to_slot,
                to_time=to_time, move=move)


@tool()
def fire_clip(track: int | str, slot: int) -> dict:
    """Launch the clip in a Session slot (starts at the next launch-quantization boundary; Live starts the transport).

    Check the result with get_clip (state) or get_meters; stop with stop_clip or transport.
    """
    busy = loopback_busy()
    if busy:
        raise ToolError(busy)
    return call("fire_clip", track=track, slot=slot)


@tool()
def stop_clip(track: int | str, quantized: bool = True) -> dict:
    """Stop the playing or triggered Session clips on a track (quantized=False stops immediately)."""
    return call("stop_clip", track=track, quantized=quantized)


@tool(read_only=True)
def get_notes(track: int | str, slot: int | None = None, arrangement_clip: int | None = None,
              pitches: int | str | list[int | str] | None = None, pitch_min: int | str | None = None,
              pitch_max: int | str | None = None, start: float | str | None = None, end: float | str | None = None,
              note_ids: list[int] | None = None, limit: int = 200) -> dict:
    """Notes of a MIDI clip with note_id, pitch, name (C3 = 60), start, duration, velocity, probability,
    velocity_deviation, release_velocity and mute, sorted by time.

    Optional filters (combined): pitches (list), pitch_min/pitch_max (numbers or names), start/end (notes starting in
    [start, end), clip beats or "bar.beat.sixteenth"), note_ids. Use the ids with edit_notes, delete_notes or
    transform_notes. Example: get_notes(track="Bass", slot=0, start="2.1.1", end="3.1.1").
    """
    return call("get_notes", track=track, slot=slot, arrangement_clip=arrangement_clip, note_ids=note_ids, pitches=pitches,
                pitch_min=pitch_min, pitch_max=pitch_max, start=start, end=end, limit=limit)


@tool(destructive=True)
def write_notes(track: int | str, notes: list[dict], slot: int | None = None, arrangement_clip: int | None = None,
                mode: str = "add", start: float | str | None = None, end: float | str | None = None) -> dict:
    """Write MIDI notes into a clip. mode: "add", "replace" (clears the clip first) or "replace_range" (clears notes
    starting in [start, end); defaults to the span of the new notes).

    Each note: pitch (60 or "C3"), start (clip beats or "1.3.1"; 1.1.1 = clip start), duration (beats, "1/8", "1/16T"),
    optional velocity=100, probability=1, velocity_deviation=0, release_velocity=64, mute=false. Chords:
    "pitches": [...] or "chord": "Am7" (+ octave, inversion, voicing). music_theory progression "notes" fit as-is.
    Example: [{"pitch": "C3", "start": 0, "duration": 1}, {"chord": "F", "start": 4, "duration": 4}].
    """
    try:
        notes = theory.expand_note_chords(notes)
    except theory.TheoryError as error:
        raise ToolError(str(error))
    return call("write_notes", track=track, notes=notes, slot=slot, arrangement_clip=arrangement_clip, mode=mode, start=start, end=end)


@tool(idempotent=True)
def edit_notes(track: int | str, edits: list[dict], slot: int | None = None, arrangement_clip: int | None = None) -> dict:
    """Change existing notes by note_id (from get_notes), keeping their ids.

    Each edit: {"note_id": 12, ...} plus any of pitch, start, duration, velocity, probability, velocity_deviation,
    release_velocity, mute. Example: edit_notes(track="Keys", slot=0, edits=[{"note_id": 12, "velocity": 90, "pitch": "E3"}]).
    For relative changes on many notes use transform_notes.
    """
    return call("edit_notes", track=track, edits=edits, slot=slot, arrangement_clip=arrangement_clip)


@tool(destructive=True)
def delete_notes(track: int | str, slot: int | None = None, arrangement_clip: int | None = None, note_ids: list[int] | None = None,
                 pitches: int | str | list[int | str] | None = None, pitch_min: int | str | None = None,
                 pitch_max: int | str | None = None, start: float | str | None = None, end: float | str | None = None,
                 all: bool = False) -> dict:
    """Delete notes from a MIDI clip by note_ids, pitches, pitch_min/pitch_max and/or a start/end time range
    (notes starting in [start, end)), or every note with all=True. Filters combine; at least one is required.
    """
    return call("delete_notes", track=track, slot=slot, arrangement_clip=arrangement_clip, note_ids=note_ids, pitches=pitches,
                pitch_min=pitch_min, pitch_max=pitch_max, start=start, end=end, all=all)


@tool()
def transform_notes(track: int | str, operation: str, slot: int | None = None, arrangement_clip: int | None = None,
                    note_ids: list[int] | None = None, pitches: int | str | list[int | str] | None = None,
                    pitch_min: int | str | None = None, pitch_max: int | str | None = None, start: float | str | None = None,
                    end: float | str | None = None, semitones: int | None = None, steps: int | None = None,
                    grid: str | None = None, amount: float | None = None, swing: float | None = None,
                    timing: float | str | None = None, velocity: float | None = None, seed: int | None = None,
                    factor: float | None = None, offset: float | None = None, value: float | None = None,
                    random: float | None = None) -> dict:
    """Transform notes in place (ids kept). Filters as in get_notes select the notes (default: all).

    operation and its options:
    transpose: semitones, or steps (scale degrees in the song's key and scale).
    quantize: grid ("1/16", "1/8T"), amount 0..1 (default 1), swing 0..1 (delays every second grid line).
    humanize: timing (+/- beats, or "10ms"), velocity (+/- spread), seed.
    velocity: factor (multiply), offset (add), value (set), random (+/- spread), seed.
    legato; reverse (within start/end or the loop); stretch: factor (around start or loop start); shift: offset (beats).
    """
    return call("transform_notes", track=track, operation=operation, slot=slot, arrangement_clip=arrangement_clip,
                note_ids=note_ids, pitches=pitches, pitch_min=pitch_min, pitch_max=pitch_max, start=start, end=end,
                semitones=semitones, steps=steps, grid=grid, amount=amount, swing=swing, timing=timing, velocity=velocity,
                seed=seed, factor=factor, offset=offset, value=value, random=random)


@tool(destructive=True)
def write_drum_pattern(track: int | str, pattern: dict[str, str], slot: int | None = None, arrangement_clip: int | None = None,
                       steps_per_beat: int = 4, velocities: dict[str, int] | None = None, swing: float = 0.0,
                       mode: str = "replace") -> dict:
    """Write drums from step strings, repeated across the clip's loop: {"Kick": "x---x---x---x---", "Snare": "----x-------x---"}.

    Steps: "x" hit, "X" accent, "o" ghost, "-" or "." rest (spaces and "|" ignored); steps_per_beat=4 means 16ths.
    Drum names match the track's Drum Rack pads (case-insensitive, "kick" finds "Kick 808"), else General MIDI
    (kick 36, snare 38, clap 39, closed hat 42, open hat 46, crash 49, ride 51, toms); notes like "C1" or 36 work too.
    velocities: {"x": 100, "X": 127, "o": 60}. swing 0..1 delays every second step. mode: "replace" (those drums' notes) or "add".
    """
    try:
        lanes = theory.drum_lanes(pattern, steps_per_beat=steps_per_beat, velocities=velocities, swing=swing)
    except theory.TheoryError as error:
        raise ToolError(str(error))
    return call("write_drum_pattern", track=track, lanes=lanes, slot=slot, arrangement_clip=arrangement_clip, mode=mode)


@tool(destructive=True)
def clip_action(track: int | str, action: str, slot: int | None = None, arrangement_clip: int | None = None,
                args: dict | None = None) -> dict:
    """Run a clip function. Actions and args:
    crop (keeps the loop, or the marker range); duplicate_loop (doubles the loop and its content);
    duplicate_region {start, length, destination, pitch?, transpose?} (MIDI);
    quantize {grid "1/16", amount 0..1, pitch?} (MIDI notes, or audio warp markers; uses the song's swing);
    add_warp_marker {beat_time, sample_time? seconds}, move_warp_marker {beat_time, distance}, remove_warp_marker {beat_time};
    audio_to_midi {type: melody|harmony|drums, name?}, drum_rack_from_audio {name?}, simpler_track_from_audio {name?}
    (these create a new track and return it).
    """
    result = call("clip_action", track=track, action=action, slot=slot, arrangement_clip=arrangement_clip, args=args, timeout=70)
    if not (isinstance(result, dict) and result.get("pending")):
        return result
    deadline = time.time() + CONVERSION_WAIT
    while time.time() < deadline:
        time.sleep(0.25)
        status = call("clips_conversion_status", job=result["job"])
        if status.get("done"):
            result.pop("pending", None)
            result.pop("job", None)
            result.update(status)
            result.pop("done", None)
            return result
    result["hint"] = "Live is still converting; the new MIDI track appears after the source track (see get_song_overview)"
    return result
