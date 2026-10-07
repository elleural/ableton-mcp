"""WS-F: arrangement timeline, arrange_from_scenes and clear_arrangement (docs/PRD.md section 7.7).
Owned by workstream F.

Live's API (verified on 12.4.6, see docs/spikes.md):
- An arrangement clip's extent (end_time) is read-only, and end_marker never changes it. It can be
  resized by unlooping the clip, setting loop_end (the end of an unlooped clip, in beats, or seconds for
  unwarped audio), and looping it again: Live restores the loop region and keeps the new extent.
  This shrinks and extends MIDI and warped audio clips (looping past the sample end) in one call.
  Extending stops at the next clip on the track; it never overwrites.
- duplicate_clip_to_arrangement and create_midi_clip overwrite the range they land on: clips there are
  trimmed or split at the new clip's edges, keeping their content offset (like a paste in Live).
  Arrangement-to-arrangement copies keep the source's extent and envelopes.
- duplicate_clip_to_arrangement and create_midi_clip move the playhead (current_song_time) to where the
  clip lands, immediately; commands that paste put it back afterwards.
- Unwarped audio: loop_end is in seconds (beats = seconds * tempo / 60), and a new extent only applies on
  the next tick, so a copy sized in one call is pasted in the next (state kept in ctx.state).
- Costs on the main thread: duplicate_clip_to_arrangement about 23 ms, delete_clip about 12 ms, property
  writes under 1 ms. Long jobs are therefore split into calls of about WORK_BUDGET seconds that the MCP
  tool resumes (`resume` = index of the next work unit).
- Song.set_or_delete_cue toggles a locator at the *committed* playhead. A write to current_song_time
  is committed on the next main-thread tick (the getter still returns the old value until then), so a
  locator at a given time takes two calls: move the playhead, then toggle. Writing the committed value
  again is ignored, and the playhead cannot be moved past song_length.
"""
import math
import time as _time

from .. import refs, values
from ..core import command
from ..errors import CommandError

EPSILON = 1e-6
MAX_TIME = 1576800.0          # Live's arrangement limit for clip positions
FAR_MARGIN = 16.0             # Beats between the last event and the scratch area used for temporary copies
DEFAULT_LIMIT = 200
MAX_SECTIONS = 256
CLEAR_MODES = ("trim", "overlapping", "inside")
WORK_BUDGET = 0.75            # Seconds of main-thread work per call before handing back a resume point


# ---------------------------------------------------------------------------
# Pure planning helpers
# ---------------------------------------------------------------------------


def section_bounds(origin, lengths):
    """[(start, end)] for consecutive sections of `lengths` beats starting at `origin`."""
    bounds, cursor = [], float(origin)
    for length in lengths:
        bounds.append((cursor, cursor + float(length)))
        cursor += float(length)
    return bounds


def section_length(song, section, position):
    """Beats of one section spec: {"bars": n} or {"length": beats | "8 bars"}."""
    if not isinstance(section, dict):
        raise CommandError("invalid_argument", "sections[{0}] must be an object like {{scene, bars}}, got {1!r}".format(position, section))
    has_bars, has_length = section.get("bars") is not None, section.get("length") is not None
    if has_bars == has_length:
        raise CommandError("invalid_argument", "sections[{0}] needs exactly one of 'bars' (number of bars) or 'length' (beats or '8 bars')".format(position))
    if has_length:
        return values.parse_length(song, section["length"], "sections[{0}].length".format(position))
    bars = section["bars"]
    if isinstance(bars, bool) or not isinstance(bars, (int, float)) or bars <= 0:
        raise CommandError("invalid_argument", "sections[{0}].bars must be a positive number, got {1!r}".format(position, bars))
    return float(bars) * values.bar_length(song)


def overlaps(clip_start, clip_end, start, end):
    return clip_end > start + EPSILON and clip_start < end - EPSILON


def inside(clip_start, clip_end, start, end):
    return clip_start >= start - EPSILON and clip_end <= end + EPSILON


def resume_index(resume, total):
    if isinstance(resume, bool) or not isinstance(resume, int) or not 0 <= resume <= total:
        raise CommandError("invalid_argument", "resume must be a work-unit index 0..{0}, got {1!r}".format(total, resume))
    return resume


# ---------------------------------------------------------------------------
# Clip extent primitives
# ---------------------------------------------------------------------------


def extent(clip):
    return float(clip.end_time) - float(clip.start_time)


def set_extent(clip, length):
    """Resize an arrangement clip to `length` beats on the timeline; returns the extent reached.

    Unloop, set loop_end (clip units: beats, or seconds for unwarped audio), loop again. Live restores
    the loop region itself; the markers are put back explicitly in case it does not.
    """
    if abs(extent(clip) - length) < EPSILON:
        return extent(clip)
    looping = bool(clip.looping)
    saved = (clip.loop_start, clip.loop_end, clip.start_marker, clip.end_marker)
    for _ in range(3):
        if clip.looping:
            clip.looping = False
        current = extent(clip)
        span = float(clip.loop_end) - float(clip.loop_start)
        units_per_beat = span / current if current > EPSILON and span > EPSILON else 1.0
        clip.loop_end = float(clip.loop_start) + length * units_per_beat
        if abs(extent(clip) - length) < EPSILON:
            break
    if looping:
        clip.looping = True
        _restore_loop(clip, saved)
    return extent(clip)


def _restore_loop(clip, saved):
    loop_start, loop_end, start_marker, end_marker = saved
    try:
        if abs(clip.loop_end - loop_end) > EPSILON or abs(clip.loop_start - loop_start) > EPSILON:
            if loop_start >= clip.loop_end:
                clip.loop_end = loop_end
                clip.loop_start = loop_start
            else:
                clip.loop_start = loop_start
                clip.loop_end = loop_end
        if abs(clip.start_marker - start_marker) > EPSILON:
            clip.start_marker = start_marker
        if abs(clip.end_marker - end_marker) > EPSILON and end_marker > clip.start_marker:
            clip.end_marker = end_marker
    except Exception:
        pass  # Markers are cosmetic for a looping clip; the extent is what matters.


def natural_bound(clip):
    """Upper bound in beats of the extent an arrangement copy of `clip` gets (None for unwarped audio,
    whose markers are in seconds). A copy spans at most the clip's markers and loop together."""
    if clip.is_audio_clip and not clip.warping:
        return None
    return max(float(clip.loop_end), float(clip.end_marker)) - min(float(clip.loop_start), float(clip.start_marker))


def far_point(song, extra=0.0):
    """A time beyond every event in the set, where temporary copies cannot overwrite anything."""
    far = max(float(song.last_event_time), float(extra)) + FAR_MARGIN
    return math.ceil(far)


def _check_room(far, length):
    if far + length > MAX_TIME:
        raise CommandError("invalid_argument", "The arrangement is too long to place temporary copies (limit {0:g} beats)".format(MAX_TIME))


SETTLING = "ws_f_settling"  # ctx.state key: an unwarped audio copy waiting one tick for its new length


class Settling(Exception):
    """An unwarped audio copy needs a tick to take its new length: end this call and resume the same unit."""


def unwarped(clip):
    return bool(clip.is_audio_clip) and not clip.warping


def _sized(clip, source, length):
    """Size a fresh copy of `source`: looping sources fill `length`, one-shots keep theirs up to `length`."""
    want = float(length) if source.looping else min(extent(clip), float(length))
    reached = set_extent(clip, want)
    if abs(reached - want) > 1e-4:
        raise CommandError("live_error", "Could not size the copy of '{0}' to {1:g} beats (reached {2:g})".format(source.name, want, reached))
    return want


def _clip_at(track, time):
    for clip in track.arrangement_clips:
        if abs(float(clip.start_time) - time) < EPSILON:
            return clip
    return None


def _settled_copy(ctx, track, source, far, length, key):
    """A copy of unwarped audio `source` at `far`, at most `length` beats long, whose length has settled.

    Live applies an unwarped clip's new loop_end (seconds) on the next tick, and a paste in the same tick
    would copy the old length. The first call makes and sizes the copy, then raises Settling; the call
    after returns it. Returns (copy, beats).
    """
    song = track.canonical_parent
    pending = ctx.state.get(SETTLING)
    temp = _clip_at(track, pending["far"]) if pending and pending.get("key") == key else None
    if temp is not None:
        if abs(extent(temp) - pending["want"]) < 1e-3:
            ctx.state.pop(SETTLING, None)
            return temp, pending["want"]
        if pending["tries"] < 3:
            ratio = (float(temp.loop_end) - float(temp.loop_start)) / extent(temp) if extent(temp) > EPSILON else 60.0 / float(song.tempo)
            temp.loop_end = float(temp.loop_start) + pending["want"] * ratio
            pending["tries"] += 1
            raise Settling()
        ctx.state.pop(SETTLING, None)
        track.delete_clip(temp)
        raise CommandError("live_error", "Could not size a copy of unwarped clip '{0}'".format(source.name))
    _drop_stale_copy(ctx, song)  # an abandoned step, or this one's copy vanished: start over
    temp = track.duplicate_clip_to_arrangement(source, far)
    want = min(extent(temp), float(length))
    _check_room(far, extent(temp))
    if abs(extent(temp) - want) < EPSILON:
        return temp, want
    temp.loop_end = float(temp.loop_start) + want * 60.0 / float(song.tempo)
    ctx.state[SETTLING] = {"key": key, "far": float(far), "want": want, "tries": 0, "track": track.name}
    raise Settling()


def _drop_stale_copy(ctx, song):
    """Delete the copy of an abandoned two-call step, if one is still waiting."""
    pending = ctx.state.pop(SETTLING, None)
    if not pending:
        return
    for track in song.tracks:
        if track.name == pending.get("track"):
            temp = _clip_at(track, pending["far"])
            if temp is not None:
                track.delete_clip(temp)


def place(ctx, track, source, start, length, far, occupied):
    """Copy `source` onto `track` covering exactly [start, start + length) and return the new clip.

    `occupied` lists (start, end) spans that may hold clips on this track (never missing one); the
    new clip's span is added. When nothing occupies the landing zone the copy is pasted in place and
    resized there; otherwise it is built at `far` (beyond all material) and then pasted, so nothing
    outside the range is touched. Whatever was inside the range is overwritten. Unwarped audio is
    always built at `far` and takes two calls (Settling).
    """
    bound = natural_bound(source)
    if unwarped(source):
        temp, want = _settled_copy(ctx, track, source, far, length, ("place", track.name, float(start), float(length)))
        try:
            clip = track.duplicate_clip_to_arrangement(temp, start)
        finally:
            track.delete_clip(temp)
    elif not any(overlaps(a, b, start, start + max(float(length), bound)) for a, b in occupied):
        clip = track.duplicate_clip_to_arrangement(source, start)
        want = _sized(clip, source, length)
    else:
        temp = track.duplicate_clip_to_arrangement(source, far)
        try:
            _check_room(far, extent(temp) + float(length))
            want = _sized(temp, source, length)
            clip = track.duplicate_clip_to_arrangement(temp, start)
        finally:
            track.delete_clip(temp)
    occupied.append((float(start), float(start) + want))
    return clip


def _cut(ctx, track, clip, start, end, far):
    """Remove [start, end) from a clip that crosses it, by pasting a temporary clip there and deleting it."""
    if track.has_midi_input:
        temp = track.create_midi_clip(start, end - start)
        track.delete_clip(temp)
        return
    if unwarped(clip):
        temp, _ = _settled_copy(ctx, track, clip, far, end - start, ("cut", track.name, float(start), float(end)))
    else:
        temp = track.duplicate_clip_to_arrangement(clip, far)
        try:
            _check_room(far, extent(temp))
            reached = set_extent(temp, end - start)
            if abs(reached - (end - start)) > 1e-4:
                raise CommandError("live_error", "Could not cut clip '{0}' at {1:g}..{2:g}".format(clip.name, start, end))
        except Exception:
            track.delete_clip(temp)
            raise
    try:
        pasted = track.duplicate_clip_to_arrangement(temp, start)
        track.delete_clip(pasted)
    finally:
        track.delete_clip(temp)


def clear_range(ctx, track, start, end, mode, far):
    """Delete arrangement clips of `track` in [start, end). Returns (deleted, trimmed, settling).

    trim: clips inside are deleted and clips crossing an edge are cut at it (nothing outside the range
    changes); overlapping: every clip touching the range is deleted whole; inside: only clips entirely
    within the range are deleted. settling is True when a cut of unwarped audio needs another call:
    call again for the same track (work already done is not repeated).
    """
    deleted = trimmed = 0
    for clip in list(track.arrangement_clips):
        clip_start, clip_end = float(clip.start_time), float(clip.end_time)
        if not overlaps(clip_start, clip_end, start, end):
            continue
        if inside(clip_start, clip_end, start, end) or mode == "overlapping":
            track.delete_clip(clip)
            deleted += 1
    if mode != "trim":
        return deleted, trimmed, False
    for _ in range(4):  # at most one clip per edge, or one clip spanning both
        crossing = [clip for clip in track.arrangement_clips if overlaps(float(clip.start_time), float(clip.end_time), start, end)]
        if not crossing:
            break
        clip = crossing[0]
        try:
            _cut(ctx, track, clip, max(start, float(clip.start_time)), min(end, float(clip.end_time)), far)
        except Settling:
            return deleted, trimmed, True
        trimmed += 1
    return deleted, trimmed, False


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def clip_out(song, clip, index):
    out = {
        "index": index,
        "name": clip.name,
        "start": values.time_out(song, clip.start_time),
        "end": values.time_out(song, clip.end_time),
        "length": round(extent(clip), 6),
        "looping": bool(clip.looping),
        "type": "audio" if clip.is_audio_clip else "midi",
    }
    out.update(values.color_out(clip))
    if clip.muted:
        out["muted"] = True
    if clip.has_envelopes:
        out["envelopes"] = True
    return out


def locator_out(song, cue, index=None):
    out = {"name": cue.name, "time": values.time_out(song, cue.time)}
    if index is not None:
        out = dict({"index": index}, **out)
    return out


def cue_at(song, time):
    for cue in song.cue_points:
        if abs(float(cue.time) - time) < EPSILON:
            return cue
    return None


def _arrangement_tracks(song, track_refs):
    """Regular tracks that hold arrangement clips: all of them by default, else the named ones."""
    if track_refs is None:
        return [item for item in song.tracks if not item.is_foldable]
    chosen = refs.tracks(song, track_refs)
    for item in chosen:
        if refs.index_of(song.tracks, item) is None or item.is_foldable:
            raise CommandError("invalid_argument", "Track '{0}' has no arrangement clips: only regular MIDI and audio tracks do (not return, master or group tracks)".format(item.name))
    return chosen


def restore_playhead(song, position):
    """Put the playhead back after pastes moved it (applied on the next tick). Skipped while playing."""
    if song.is_playing:
        return
    try:
        if abs(float(song.current_song_time) - position) > EPSILON:
            song.current_song_time = position
    except Exception:
        pass


def _time_or(song, value, default, name):
    return default if value is None else values.parse_time(song, value, name)


def _over_budget(started, position, first):
    return position > first and _time.time() - started > WORK_BUDGET


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@command("get_arrangement", readonly=True)
def get_arrangement(ctx, start=None, end=None, tracks=None, limit=DEFAULT_LIMIT):
    """Arrangement timeline: clips per track, locators, loop and song length."""
    song = ctx.song
    range_start = _time_or(song, start, None, "start")
    range_end = _time_or(song, end, None, "end")
    if range_start is not None and range_end is not None and range_end <= range_start:
        raise CommandError("invalid_argument", "end must be after start")
    low = -MAX_TIME if range_start is None else range_start
    high = MAX_TIME * 2 if range_end is None else range_end
    budget = max(0, int(limit))
    omitted = 0
    track_list = []
    for owner in _arrangement_tracks(song, tracks):
        clips = refs.arrangement_clips(owner)
        entry = refs.track_label(song, owner)
        shown = []
        for index, clip in enumerate(clips):
            if not overlaps(float(clip.start_time), float(clip.end_time), low, high):
                continue
            if budget > 0:
                shown.append(clip_out(song, clip, index))
                budget -= 1
            else:
                omitted += 1
        entry["clips"] = shown
        if len(shown) != len(clips):
            entry["clip_count"] = len(clips)
        track_list.append(entry)
    out = {
        "song": {
            "length": values.time_out(song, song.last_event_time),
            "tempo": round(float(song.tempo), 3),
            "time_signature": "{0}/{1}".format(song.signature_numerator, song.signature_denominator),
        },
        "loop": {
            "on": bool(song.loop),
            "start": values.time_out(song, song.loop_start),
            "end": values.time_out(song, song.loop_start + song.loop_length),
        },
        "locators": [locator_out(song, cue, index) for index, cue in enumerate(refs.locators(song))],
        "tracks": track_list,
    }
    if range_start is not None or range_end is not None:
        out["range"] = {
            "start": None if range_start is None else values.time_out(song, range_start),
            "end": None if range_end is None else values.time_out(song, range_end),
        }
    if omitted:
        out["truncated"] = {"clips_omitted": omitted, "hint": "Narrow the range with start/end, pass tracks, or raise limit"}
    return out


@command("clear_arrangement", timeout=30.0)
def clear_arrangement(ctx, tracks=None, start=None, end=None, mode="trim", resume=0):
    """Delete arrangement clips by track and time range (work beyond WORK_BUDGET returns `resume`)."""
    started = _time.time()
    song = ctx.song
    if mode not in CLEAR_MODES:
        raise CommandError("invalid_argument", "mode must be one of {0}, got {1!r}".format(", ".join(CLEAR_MODES), mode))
    range_start = _time_or(song, start, 0.0, "start")
    range_end = _time_or(song, end, MAX_TIME, "end")
    if range_end <= range_start:
        raise CommandError("invalid_argument", "end must be after start")
    targets = _arrangement_tracks(song, tracks)
    first = position = resume_index(resume, len(targets))
    far = far_point(song)
    playhead = float(song.current_song_time)
    report, total_deleted, total_trimmed = [], 0, 0
    try:
        while position < len(targets) and not _over_budget(started, position, first):
            owner = targets[position]
            deleted, trimmed, settling = clear_range(ctx, owner, range_start, range_end, mode, far)
            if deleted or trimmed:
                entry = refs.track_label(song, owner)
                entry.update({"deleted": deleted, "trimmed": trimmed, "remaining": len(owner.arrangement_clips)})
                report.append(entry)
            total_deleted += deleted
            total_trimmed += trimmed
            if settling:
                break  # an unwarped audio cut finishes on the next call
            position += 1
    finally:
        restore_playhead(song, playhead)
    out = {
        "mode": mode,
        "range": {"start": values.time_out(song, range_start), "end": None if end is None else values.time_out(song, range_end)},
        "deleted": total_deleted,
        "trimmed": total_trimmed,
        "tracks": report,
    }
    if position < len(targets):
        out["resume"] = position
    return out


def _plan_sections(song, sections):
    if not isinstance(sections, (list, tuple)) or not sections:
        raise CommandError("invalid_argument", "sections must be a non-empty list like [{scene: 'Verse', bars: 8}, ...]")
    if len(sections) > MAX_SECTIONS:
        raise CommandError("invalid_argument", "At most {0} sections per call".format(MAX_SECTIONS))
    scenes = list(song.scenes)
    plan = []
    for position, section in enumerate(sections):
        length = section_length(song, section, position)
        if "scene" not in section:
            raise CommandError("invalid_argument", "sections[{0}] needs a 'scene' (index or name)".format(position))
        unknown = sorted(set(section) - {"scene", "bars", "length", "name"})
        if unknown:
            raise CommandError("invalid_argument", "sections[{0}]: unknown keys {1}; use scene, bars or length, name".format(position, unknown))
        scene = refs.scene(song, section["scene"])
        name = section.get("name") or scene.name or "Section {0}".format(position + 1)
        plan.append((scene, refs.index_of(scenes, scene), str(name), length))
    return plan


@command("arrange_from_scenes", timeout=60.0)
def arrange_from_scenes(ctx, sections, start=None, clear=False, tracks=None, locators=True, resume=0):
    """Lay out scenes as consecutive arrangement sections.

    Work is split into units (clear one track, place one track's clip for one section). A call stops
    after about WORK_BUDGET seconds and returns `resume`; call again with the same arguments and that
    `resume` until it is absent. The final call queues the locators for arrangement_locator.
    """
    started = _time.time()
    song = ctx.song
    if locators and song.is_playing:
        raise CommandError("busy", "Live is playing, and locators are created at the playhead", hint="Stop playback first, or pass locators=False")
    origin = _time_or(song, start, 0.0, "start")
    if origin < 0:
        raise CommandError("invalid_argument", "start must not be negative")
    plan = _plan_sections(song, sections)
    bounds = section_bounds(origin, [item[3] for item in plan])
    range_end = bounds[-1][1]
    if range_end > MAX_TIME:
        raise CommandError("invalid_argument", "The arrangement would end past Live's limit of {0:g} beats".format(MAX_TIME))
    targets = _arrangement_tracks(song, tracks)
    units = []
    if clear:
        # Without an explicit track list, clear only the tracks taking part (a clip in at least one
        # listed scene), so unrelated material such as recorded audio is left alone.
        units = [("clear", index) for index, owner in enumerate(targets)
                 if tracks is not None or any(owner.clip_slots[item[1]].has_clip for item in plan)]
    for section_index, (_, scene_index, _, _) in enumerate(plan):
        for index, owner in enumerate(targets):
            if owner.clip_slots[scene_index].has_clip:
                if owner.is_frozen:
                    raise CommandError("unsupported", "Track '{0}' is frozen; unfreeze it before arranging".format(owner.name))
                units.append(("place", section_index, index))
    first = position = resume_index(resume, len(units))
    far = far_point(song, range_end)
    _check_room(far, 0.0)
    playhead = float(song.current_song_time)  # pastes move the playhead; it is put back below
    occupied = {}
    placed, warnings = [], []
    cleared = {"deleted": 0, "trimmed": 0}
    try:
        while position < len(units) and not _over_budget(started, position, first):
            unit = units[position]
            if unit[0] == "clear":
                deleted, trimmed, settling = clear_range(ctx, targets[unit[1]], origin, range_end, "trim", far)
                cleared["deleted"] += deleted
                cleared["trimmed"] += trimmed
                if settling:
                    break  # an unwarped audio cut finishes on the next call
            else:
                section_index, index = unit[1], unit[2]
                owner, (_, scene_index, name, length) = targets[index], plan[section_index]
                source = owner.clip_slots[scene_index].clip
                if index not in occupied:
                    occupied[index] = [(float(clip.start_time), float(clip.end_time)) for clip in owner.arrangement_clips]
                try:
                    clip = place(ctx, owner, source, bounds[section_index][0], length, far, occupied[index])
                except Settling:
                    break  # an unwarped audio copy is pasted on the next call
                if not source.looping and extent(clip) < length - EPSILON:
                    warnings.append("'{0}' in '{1}' does not loop, so it plays once ({2:g} of {3:g} beats)".format(owner.name, name, extent(clip), length))
                placed.append({"section": section_index, "track": owner.name, "automated": bool(clip.has_envelopes)})
            position += 1
    finally:
        done = position >= len(units)
        if not (done and locators and not song.is_playing):
            restore_playhead(song, playhead)  # otherwise arrangement_locator restores it after the last locator

    bar = values.bar_length(song)
    out = {
        "range": {"start": values.time_out(song, origin), "end": values.time_out(song, range_end), "bars": round((range_end - origin) / bar, 6)},
        "sections": [
            {"index": index, "name": name, "scene": {"index": scene_index, "name": scene.name},
             "start": values.time_out(song, section_start), "end": values.time_out(song, section_end), "bars": round(length / bar, 6)}
            for index, ((scene, scene_index, name, length), (section_start, section_end)) in enumerate(zip(plan, bounds))
        ],
        "placed": placed,
    }
    if clear:
        out["cleared"] = cleared
    if warnings:
        out["warnings"] = warnings
    if not done:
        out["resume"] = position
        return out
    if locators:
        out["locators_pending"] = [{"time": section_start, "name": item[2]} for item, (section_start, _) in zip(plan, bounds)]
        out["playhead_restore"] = playhead
        try:
            song.current_song_time = bounds[0][0]  # committed on the next tick, ready for arrangement_locator
        except Exception as error:
            out.setdefault("warnings", []).append("Could not move the playhead to the first locator: {0}".format(error))
        stale = [locator_out(song, cue) for cue in refs.locators(song)
                 if origin - EPSILON <= cue.time < range_end - EPSILON and all(abs(cue.time - s) > EPSILON for s, _ in bounds)]
        if stale:
            out["other_locators_in_range"] = stale
    return out


@command("arrangement_locator")
def arrangement_locator(ctx, time, name=None, then=None, remove=False):
    """Internal step of arrange_from_scenes (and test cleanup): ensure a named locator at `time`, or remove it.

    Live toggles locators at the committed playhead, which moves one tick after it is written. When the
    playhead is elsewhere this moves it and returns status "pending": call again on a later tick. An
    existing locator at `time` is renamed rather than toggled away. `then` moves the playhead once the
    step is done or fails (the next locator, or the position to restore).
    """
    song = ctx.song
    target = float(time)
    if song.is_playing:
        raise CommandError("busy", "Live is playing; locators are created at the playhead", hint="Stop playback first")
    cue = cue_at(song, target)
    if remove and cue is None:
        _move(song, then)
        return {"status": "done", "removed": False}
    if not remove and cue is not None:
        previous = cue.name
        try:
            if name is not None:
                cue.name = name
        finally:
            _move(song, then)
        out = {"status": "done", "created": False, "locator": locator_out(song, cue)}
        if name is not None and previous != name:
            out["renamed_from"] = previous
        return out
    if abs(float(song.current_song_time) - target) > EPSILON:
        try:
            song.current_song_time = target
        except Exception as error:
            _move(song, then)
            raise CommandError("invalid_argument", "Cannot move the playhead to beat {0:g}: {1}".format(target, error),
                               hint="Locators can only be placed within the song length")
        return {"status": "pending", "time": target}
    try:
        if not remove and song.is_cue_point_selected():
            raise CommandError("live_error", "Live reports a locator at the playhead ({0:g}) that is not exactly there; not toggling".format(target))
        song.set_or_delete_cue()
        cue = cue_at(song, target)
        if remove:
            return {"status": "done", "removed": cue is None}
        if cue is None:
            raise CommandError("live_error", "Live did not create a locator at beat {0:g}".format(target))
        if name is not None:
            cue.name = name
        return {"status": "done", "created": True, "locator": locator_out(song, cue)}
    finally:
        _move(song, then)


def _move(song, then):
    if then is None:
        return
    try:
        song.current_song_time = float(then)
    except Exception:
        pass
