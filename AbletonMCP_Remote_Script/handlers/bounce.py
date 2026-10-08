"""WS-E: the real-time bounce (render) engine (docs/PRD.md sections 7.9 and 9). Owned by workstream E.

Live has no render API, so a bounce records the arrangement in real time by resampling. A ticker
drives a state machine whose job lives in ctx.state["bounce"] as plain data (it survives
reload_remote_script):

  bounce_start  validate the range, snapshot transport and arm state, create "[bounce] Master" and
                one "[bounce] <stem>" audio track per stem
  route         on a later tick (routing lists are empty in the tick a track is created): Master
                input "Resampling", stems the source track's "Post Mixer"; monitoring Off
  arm           disarm every other track (armed MIDI tracks record over their clips), arm the bounce
                tracks, stop Session clips, back to the arrangement, loop, metronome, punch and
                automation arm off, playhead to start
  go / starting record_mode on and start_playing, then wait until Live is really recording
  recording     progress from current_song_time until end + tail + a margin; an external stop, a
                playhead jump or a deleted or disarmed bounce track fails the job
  finalizing    collect the recorded clips: file path, and the sample offset of `start` (the file
                has a pre-roll, so song time `start` sits at the clip's start_marker)
  verifying     restore the snapshot, read it back on a later tick, re-apply what did not stick
  recorded      the MCP server copies and trims the files, then calls bounce_cleanup

Failures and bounce_cancel stop the transport at once and go through "aborting", which restores the
snapshot and deletes the bounce tracks on a later tick.
"""
import math
import re
import time
import traceback

from .. import journal, refs, values
from ..core import command, ticker
from ..errors import CommandError

LABEL = "bounce"   # journal name of this engine

PREFIX = "[bounce] "
MASTER_STEM = "Master"
STEM_CHANNEL = "Post Mixer"
RESAMPLING_CATEGORY = 2   # Live.Track.RoutingTypeCategory.resampling
MONITORING_OFF = 2        # Live.Track.Track.monitoring_states.OFF

STOP_MARGIN_SECONDS = 0.5  # keep recording past end + tail so the file always covers it
SETTLE_SECONDS = 1.0       # quiet time before recording when the transport was playing
MAX_SECONDS = 30 * 60.0
# Timeouts are generous: a busy Live ticks slowly, and once took over 5 s to fill new routing lists.
ROUTE_TIMEOUT = 15.0
ROUTE_MIN_ATTEMPTS = 10
START_TIMEOUT = 10.0
FINALIZE_DELAY = 0.3
FINALIZE_TIMEOUT = 15.0
VERIFY_ATTEMPTS = 3

ACTIVE = ("route", "arm", "go", "starting", "recording", "finalizing", "verifying", "aborting")
TERMINAL = ("recorded", "done", "failed", "cancelled")

# Song state restored after a bounce, in the order it is written back. back_to_arranger is
# snapshotted but not restored: the API can only switch it off (return to the arrangement), which a
# bounce must do, and Live cannot re-light it.
RESTORE_FIELDS = (
    "loop", "metronome", "punch_in", "punch_out", "arrangement_overdub", "session_automation_record",
    "record_mode", "start_time", "current_song_time",
)
SNAPSHOT_FIELDS = RESTORE_FIELDS + ("back_to_arranger", "overdub", "session_record", "is_playing")
COUNT_IN_BARS = {0: 0, 1: 1, 2: 2, 3: 4}

_SECONDS = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds)\s*$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Pure helpers (unit tested offline)
# ---------------------------------------------------------------------------


def round_up_to_bar(beats, bar_length):
    """The first bar line at or after ``beats``."""
    if beats <= 0:
        return 0.0
    return math.ceil(beats / bar_length - 1e-9) * bar_length


def parse_tail(song, value):
    """Tail length in beats: a number of beats, '1 bar', '4 beats', or seconds such as '2 s'."""
    if value is None or isinstance(value, bool):
        if isinstance(value, bool):
            raise CommandError("invalid_argument", "tail must be beats, 'N bars' or seconds like '2 s', not a boolean")
        return 0.0
    if isinstance(value, (int, float)):
        if value < 0:
            raise CommandError("invalid_argument", "tail cannot be negative, got {0!r}".format(value))
        return float(value)
    if isinstance(value, str):
        match = _SECONDS.match(value)
        if match:
            return float(match.group(1)) * float(song.tempo) / 60.0
        if re.match(r"^\s*0+(\.0*)?\s*(bars?|beats?|s)?\s*$", value):
            return 0.0
    try:
        return values.parse_length(song, value, "tail")
    except CommandError as error:
        raise CommandError("invalid_argument", error.message + " Seconds also work: '2 s'.")


def unique_labels(names, reserved=(MASTER_STEM,)):
    """Distinct stem labels for track names ('Synth', 'Synth (2)'); reserved labels are avoided."""
    taken = set(label.lower() for label in reserved)
    labels = []
    for name in names:
        base = str(name).strip() or "Track"
        label, counter = base, 2
        while label.lower() in taken:
            label = "{0} ({1})".format(base, counter)
            counter += 1
        taken.add(label.lower())
        labels.append(label)
    return labels


def sample_at(clip, song_beat, tempo):
    """Sample position in a recorded clip's file of song time ``song_beat``.

    The file starts with a pre-roll: the clip's start_marker is where its start_time is. Warped clips
    map clip beats to samples through their warp markers (exact even with tempo changes); unwarped
    clips count their markers in seconds.
    """
    relative = float(song_beat) - float(clip.start_time)
    if clip.warping:
        return float(clip.beat_to_sample_time(float(clip.start_marker) + relative))
    return (float(clip.start_marker) + relative * 60.0 / float(tempo)) * float(clip.sample_rate)


def mismatched(expected, actual):
    if isinstance(expected, bool) or isinstance(actual, bool):
        return bool(expected) != bool(actual)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) > 1e-3
    return expected != actual


# ---------------------------------------------------------------------------
# Live helpers
# ---------------------------------------------------------------------------


def _now():
    return time.time()


def _song_identity(song):
    pointer = getattr(song, "_live_ptr", None)
    return int(pointer) if isinstance(pointer, int) else None


def _bounce_tracks(song):
    return [(index, track) for index, track in enumerate(song.tracks) if str(track.name).startswith(PREFIX)]


def _track_named(song, name):
    matches = [track for track in song.tracks if track.name == name]
    if len(matches) > 1:
        raise CommandError("live_error", "Several tracks are named {0!r}; the bounce cannot tell them apart".format(name))
    return matches[0] if matches else None


def _require_track(song, name):
    track = _track_named(song, name)
    if track is None:
        raise CommandError("not_found", "Bounce track {0!r} was deleted during the bounce".format(name))
    return track


def _source_track(song, source):
    """The stem's source track, by its stored ref when the name still matches, else by unique name."""
    try:
        track = refs.track(song, source["ref"])
        if track.name == source["name"]:
            return track
    except CommandError:
        pass
    candidates = [track for track in list(song.tracks) + list(song.return_tracks) if track.name == source["name"]]
    if len(candidates) == 1:
        return candidates[0]
    raise CommandError("not_found", "Stem source track {0!r} was deleted or renamed during the bounce".format(source["name"]))


def _locators(song):
    return [dict({"name": cue.name}, **values.time_out(song, cue.time)) for cue in refs.locators(song)]


def _song_info(song):
    try:
        key = values.NOTE_NAMES[int(song.root_note) % 12]
    except Exception:
        key = None
    return {
        "tempo": round(float(song.tempo), 4),
        "time_signature": "{0}/{1}".format(song.signature_numerator, song.signature_denominator),
        "key": key,
        "scale": getattr(song, "scale_name", None),
        "set_name": getattr(song, "name", "") or None,
        "set_path": getattr(song, "file_path", "") or None,
        "locators": _locators(song),
    }


def _parse_position(song, value, name):
    """Beats, 'bar.beat.sixteenth', or a locator name."""
    try:
        return values.parse_time(song, value, name)
    except CommandError as error:
        if isinstance(value, str):
            try:
                return float(refs.locator(song, value).time)
            except CommandError:
                pass
        names = ", ".join(cue.name for cue in refs.locators(song)) or "(none)"
        raise CommandError("invalid_argument", "{0} Locator names also work: {1}".format(error.message, names))


def _resolve_stems(song, stems, include_returns):
    """[(track, kind)] stem sources plus [(name, reason)] skipped tracks."""
    chosen, skipped = [], []

    def add(track):
        if refs.index_of([item for item, _ in chosen], track) is None:
            chosen.append((track, refs.track_kind(song, track)))

    if isinstance(stems, str) and stems.strip().lower() == "all":
        for track in song.tracks:
            if str(track.name).startswith(PREFIX):
                continue
            if not track.has_audio_output:
                skipped.append({"name": track.name, "reason": "no audio output (MIDI track without an instrument)"})
            elif track.mute:
                skipped.append({"name": track.name, "reason": "muted"})
            else:
                add(track)
    elif stems is not None:
        for ref in stems if isinstance(stems, (list, tuple)) else [stems]:
            track = refs.track(song, ref)
            if refs.same(track, song.master_track):
                raise CommandError("invalid_argument", "The master is always bounced; list only tracks and returns in stems")
            if str(track.name).startswith(PREFIX):
                raise CommandError("invalid_argument", "{0!r} is a bounce track, not a stem source".format(track.name))
            if not track.has_audio_output:
                raise CommandError(
                    "invalid_argument",
                    "Track {0!r} has no audio output (a MIDI track without an instrument), so it cannot be a stem".format(track.name),
                    hint="Add an instrument first, or leave it out of stems.",
                )
            add(track)
    if include_returns:
        for track in song.return_tracks:
            add(track)
    return chosen, skipped


def _snapshot(song):
    snapshot = {"song": {}, "arms": [], "selected_track": None}
    for field in SNAPSHOT_FIELDS:
        try:
            value = getattr(song, field)
            snapshot["song"][field] = value if isinstance(value, bool) else float(value) if isinstance(value, float) else value
        except Exception:
            pass
    for index, track in enumerate(song.tracks):
        if track.can_be_armed:
            snapshot["arms"].append({"index": index, "name": track.name, "arm": bool(track.arm)})
    try:
        selected = song.view.selected_track
        snapshot["selected_track"] = {"ref": refs.track_ref(song, selected), "name": selected.name}
    except Exception:
        pass
    return snapshot


def _snapshot_track(song, entry):
    tracks = list(song.tracks)
    if entry["index"] < len(tracks) and tracks[entry["index"]].name == entry["name"]:
        return tracks[entry["index"]]
    matches = [track for track in tracks if track.name == entry["name"]]
    return matches[0] if len(matches) == 1 else None


def _restore(song, job, only=None):
    """Write the snapshot back (song fields, then arm states). Returns fields that raised."""
    snapshot = job["_internal"]["snapshot"]
    failures = []
    for field in RESTORE_FIELDS:
        if field not in snapshot["song"] or (only is not None and field not in only):
            continue
        try:
            setattr(song, field, snapshot["song"][field])
        except Exception as error:
            failures.append("{0} ({1})".format(field, error))
    for entry in snapshot["arms"]:
        if only is not None and "arm:" + entry["name"] not in only:
            continue
        track = _snapshot_track(song, entry)
        if track is None:
            continue
        try:
            if bool(track.arm) != entry["arm"]:
                track.arm = entry["arm"]
        except Exception as error:
            failures.append("arm of {0!r} ({1})".format(entry["name"], error))
    return failures


def _restore_mismatches(song, job):
    snapshot = job["_internal"]["snapshot"]
    out = []
    for field in RESTORE_FIELDS:
        if field in snapshot["song"]:
            try:
                if mismatched(snapshot["song"][field], getattr(song, field)):
                    out.append(field)
            except Exception:
                out.append(field)
    for entry in snapshot["arms"]:
        track = _snapshot_track(song, entry)
        if track is not None and bool(track.arm) != entry["arm"]:
            out.append("arm:" + entry["name"])
    return out


def _restore_selection(song, job):
    selected = job["_internal"]["snapshot"].get("selected_track")
    if not selected:
        return
    try:
        track = refs.track(song, selected["ref"])
        if track.name != selected["name"]:
            track = refs.track(song, selected["name"])
        song.view.selected_track = track
    except Exception:
        pass


def _delete_tracks(song, names):
    removed = []
    for index in reversed(range(len(song.tracks))):
        name = song.tracks[index].name
        if name in names:
            song.delete_track(index)
            removed.append(name)
    return removed


class _UndoStep(object):
    def __init__(self, song):
        self.song = song

    def __enter__(self):
        self.song.begin_undo_step()

    def __exit__(self, *exc):
        self.song.end_undo_step()
        return False


# ---------------------------------------------------------------------------
# Job bookkeeping
# ---------------------------------------------------------------------------


def _job(ctx):
    return ctx.state.get("bounce")


def _set_phase(job, phase):
    journal.event("phase", "{0} {1}: {2} -> {3}".format(LABEL, job.get("id"), job.get("phase"), phase))
    job["phase"] = phase
    job["_internal"]["phase_since"] = _now()
    job["_internal"]["ticks"] = 0


def _elapsed(job):
    return _now() - job["_internal"]["phase_since"]


def _seconds(job, beats):
    return float(beats) * 60.0 / job["tempo"]


def _eta(job):
    phase = job["phase"]
    if phase in ("route", "arm", "go", "starting"):
        return round(job["duration_seconds"] + STOP_MARGIN_SECONDS + 1.5, 1)
    if phase == "recording":
        return round(max(0.0, _seconds(job, job["range"]["record_until_beats"] - job.get("position", 0.0))) + 1.0, 1)
    if phase in ("finalizing", "verifying", "aborting"):
        return 0.5
    return 0.0


def _view(job):
    """The job as the MCP server sees it (internal bookkeeping omitted)."""
    out = dict((key, value) for key, value in job.items() if not key.startswith("_"))
    out["eta_seconds"] = _eta(job)
    return out


def _fail(ctx, job, message, cancelled=False):
    """Stop recording now; the "aborting" phase restores state and removes the tracks on a later tick."""
    if job.get("phase") in TERMINAL:
        return
    job.setdefault("warnings", [])
    if cancelled:
        job["cancelled"] = True
    else:
        job["error"] = message
    ctx.log("bounce {0}: {1}".format(job["id"], message))
    try:
        song = ctx.song
        if job["_internal"].get("transport_changed"):
            if song.is_playing:
                song.stop_playing()
            song.record_mode = False
    except Exception:
        ctx.log("bounce abort could not stop the transport:\n" + traceback.format_exc())
    _set_phase(job, "aborting")


def _abort_finish(ctx, song, job):
    """Restore what the bounce changed and delete its tracks; ends in "failed" or "cancelled"."""
    internal = job["_internal"]
    problems = []
    try:
        with _UndoStep(song):
            if internal.get("transport_changed"):
                if song.is_playing:
                    song.stop_playing()
                song.record_mode = False
                problems += _restore(song, job)
            removed = _delete_tracks(song, set(entry["name"] for entry in job["tracks"]))
            _restore_selection(song, job)
        job["removed_tracks"] = removed
    except Exception as error:
        problems.append(str(error))
        ctx.log("bounce abort cleanup error:\n" + traceback.format_exc())
    if problems:
        job["warnings"].append("Cleanup problems: " + "; ".join(problems))
    job["phase"] = "cancelled" if job.get("cancelled") else "failed"
    job["finished_at"] = _now()
    journal.event("phase", "{0} {1}: {2}".format(LABEL, job.get("id"), job["phase"]))


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def _phase_route(ctx, song, job):
    internal = job["_internal"]
    if internal["ticks"] < 2:
        return  # never in the tick the tracks were created: their routing lists are still empty
    pending = []
    internal["route_attempts"] = internal.get("route_attempts", 0) + 1
    for entry in job["tracks"]:
        track = _require_track(song, entry["name"])
        offered = list(track.available_input_routing_types)
        types = [item for item in offered if str(item.display_name)]
        if not types:
            pending.append("{0} (offered: {1})".format(entry["name"], len(offered)))
            continue
        if entry["role"] == "master":
            target = [item for item in types if _category(item) == RESAMPLING_CATEGORY or item.display_name == "Resampling"]
            if not target:
                raise CommandError("unsupported", "Live offers no 'Resampling' input. Inputs: " + ", ".join(item.display_name for item in types))
        else:
            source = _source_track(song, entry["source"])
            target = [item for item in types if _attached(item, source)]
            if not target:
                pending.append("{0} (no input from {1!r}; offered: {2})".format(
                    entry["name"], entry["source"]["name"], ", ".join(item.display_name for item in types)))
                continue
        track.input_routing_type = target[0]
        if entry["role"] == "stem":
            channels = list(track.available_input_routing_channels)
            channel = [item for item in channels if item.display_name == STEM_CHANNEL]
            if not channel:
                if _elapsed(job) < ROUTE_TIMEOUT:
                    pending.append(entry["name"])
                    continue
                raise CommandError(
                    "unsupported",
                    "Track {0!r} offers no '{1}' channel. Channels: {2}".format(
                        entry["source"]["name"], STEM_CHANNEL, ", ".join(item.display_name for item in channels) or "(none)"),
                )
            track.input_routing_channel = channel[0]
        track.current_monitoring_state = MONITORING_OFF
    if pending:
        if _elapsed(job) > ROUTE_TIMEOUT and internal["route_attempts"] >= ROUTE_MIN_ATTEMPTS:
            raise CommandError("timeout", "Live did not offer the inputs after {0} attempts: {1}".format(
                internal["route_attempts"], "; ".join(pending)))
        return
    _set_phase(job, "arm")


def _category(routing_type):
    try:
        return int(routing_type.category)
    except Exception:
        return None


def _attached(routing_type, track):
    try:
        return refs.same(routing_type.attached_object, track)
    except Exception:
        return False


def _verify_routing(song, job):
    for entry in job["tracks"]:
        track = _require_track(song, entry["name"])
        current = track.input_routing_type
        if entry["role"] == "master":
            ok = _category(current) == RESAMPLING_CATEGORY or current.display_name == "Resampling"
        else:
            ok = _attached(current, _source_track(song, entry["source"])) and track.input_routing_channel.display_name == STEM_CHANNEL
        if not ok:
            raise CommandError("live_error", "The input of {0!r} did not stay on its source (now {1!r})".format(entry["name"], current.display_name))
        if int(track.current_monitoring_state) != MONITORING_OFF:
            raise CommandError("live_error", "Monitoring of {0!r} is not Off".format(entry["name"]))


def _phase_arm(ctx, song, job):
    internal = job["_internal"]
    if internal["ticks"] < 1:
        return
    settle_until = internal.get("settle_until") or 0
    if _now() < settle_until:
        return
    _verify_routing(song, job)
    bounce_names = set(entry["name"] for entry in job["tracks"])
    internal["transport_changed"] = True
    with _UndoStep(song):
        for track in song.tracks:
            if track.can_be_armed:
                wanted = track.name in bounce_names
                if bool(track.arm) != wanted:
                    track.arm = wanted
                # Push and auto-arm surfaces arm the selected track implicitly; that records too.
                if not wanted and getattr(track, "implicit_arm", False):
                    track.implicit_arm = False
        # Keep the selection on a bounce track so auto-arm cannot implicitly arm a user track.
        try:
            song.view.selected_track = _require_track(song, job["tracks"][0]["name"])
        except Exception:
            pass
        song.stop_all_clips(False)
        song.back_to_arranger = False
        song.loop = False
        song.metronome = False
        song.punch_in = False
        song.punch_out = False
        song.session_automation_record = False
        start = job["range"]["start"]["beats"]
        song.current_song_time = start
        song.start_time = start
    _set_phase(job, "go")


def _phase_go(ctx, song, job):
    internal = job["_internal"]
    if internal["ticks"] < 1:
        return
    bounce_names = set(entry["name"] for entry in job["tracks"])
    for track in song.tracks:
        if track.can_be_armed and bool(track.arm) != (track.name in bounce_names):
            if internal["ticks"] > 20:
                raise CommandError("live_error", "Could not {0}arm track {1!r}".format("" if track.name in bounce_names else "dis", track.name))
            track.arm = track.name in bounce_names
            return
    start = job["range"]["start"]["beats"]
    if abs(float(song.current_song_time) - start) > 1e-3:
        if internal["ticks"] > 20:
            raise CommandError("live_error", "Could not move the playhead to the bounce start")
        song.current_song_time = start
        return
    song.record_mode = True
    song.start_playing()
    _set_phase(job, "starting")


def _phase_starting(ctx, song, job):
    count_in_seconds = _seconds(job, COUNT_IN_BARS.get(job.get("count_in", 0), 0) * job["bar_beats"])
    if song.is_counting_in:
        return
    if song.is_playing and song.record_mode:
        job["_internal"]["last_position"] = float(song.current_song_time)
        job["_internal"]["last_time"] = _now()
        job["recording_started_at"] = _now()
        _set_phase(job, "recording")
        return
    if _elapsed(job) > START_TIMEOUT + count_in_seconds:
        raise CommandError("live_error", "Live did not start recording (playing={0}, record_mode={1})".format(bool(song.is_playing), bool(song.record_mode)))


def _phase_recording(ctx, song, job):
    internal = job["_internal"]
    position = float(song.current_song_time)
    now = _now()
    start = job["range"]["start"]["beats"]
    stop = job["range"]["stop_beats"]
    until = job["range"]["record_until_beats"]
    job["position"] = round(position, 4)
    job["progress"] = round(min(1.0, max(0.0, (position - start) / (until - start))), 3)
    complete = position >= stop - 1e-6
    if not song.is_playing:
        if complete:
            song.record_mode = False
            _set_phase(job, "finalizing")
            return
        raise CommandError("live_error", "Playback stopped at {0} before the bounce end {1}; the bounce was interrupted".format(
            values.format_time(song, position), values.format_time(song, stop)))
    if not song.record_mode and not complete:
        raise CommandError("live_error", "Recording was switched off at {0}; the bounce was interrupted".format(values.format_time(song, position)))
    last = internal.get("last_position", position)
    allowed = (now - internal.get("last_time", now)) * float(song.tempo) / 60.0 * 2.0 + 1.0
    if position < last - 0.05 or position - last > allowed:
        raise CommandError("live_error", "The playhead jumped from {0} to {1}; the bounce was interrupted".format(
            values.format_time(song, last), values.format_time(song, position)))
    internal["last_position"], internal["last_time"] = position, now
    bounce_names = set(entry["name"] for entry in job["tracks"])
    for entry in job["tracks"]:
        if not _require_track(song, entry["name"]).arm:
            raise CommandError("live_error", "Bounce track {0!r} was disarmed during the bounce".format(entry["name"]))
    for track in song.tracks:
        if track.name in bounce_names or not track.can_be_armed:
            continue
        if track.arm or getattr(track, "implicit_arm", False):
            # Fail fast: an armed user track is recording over its own arrangement clips.
            raise CommandError("live_error", "Track {0!r} was armed during the bounce, so the bounce stopped before it could record "
                               "over its clips; its arrangement may hold a short take (undo reverts it)".format(track.name))
    if abs(float(song.tempo) - job["tempo"]) > 1e-3 and not internal.get("tempo_warned"):
        internal["tempo_warned"] = True
        job["warnings"].append("The tempo changed during the bounce (tempo automation?); offsets come from the recorded clips' warp markers")
    if position >= until:
        song.stop_playing()
        song.record_mode = False
        job["recorded_until"] = round(position, 4)
        _set_phase(job, "finalizing")


def _collect(song, job):
    """File, sample offset of `start` and sample length for every bounce track; None while not ready."""
    start = job["range"]["start"]["beats"]
    stop = job["range"]["stop_beats"]
    files = []
    for entry in job["tracks"]:
        track = _require_track(song, entry["name"])
        clips = sorted([clip for clip in track.arrangement_clips if clip.is_audio_clip], key=lambda clip: clip.start_time)
        if not clips:
            return None
        covering = [clip for clip in clips if clip.start_time <= start + 1e-6 and clip.end_time >= stop - 1e-6]
        clip = covering[0] if covering else clips[0]
        path = clip.file_path
        if not path:
            return None
        offset = sample_at(clip, start, job["tempo"])
        end = sample_at(clip, stop, job["tempo"])
        record = {
            "stem": entry["stem"], "role": entry["role"], "track": entry["name"], "file_path": path,
            "sample_rate": float(clip.sample_rate), "sample_length": int(clip.sample_length),
            "offset_samples": round(offset, 3), "length_samples": round(end - offset, 3),
            "duration_seconds": round((end - offset) / float(clip.sample_rate), 6),
            "recorded_seconds": round(int(clip.sample_length) / float(clip.sample_rate), 6),
            "clip": {"start": round(float(clip.start_time), 6), "end": round(float(clip.end_time), 6),
                     "start_marker": round(float(clip.start_marker), 6), "warping": bool(clip.warping)},
        }
        if entry.get("source"):
            record["source"] = entry["source"]["name"]
        if len(clips) > 1:
            record["clips_recorded"] = len(clips)
        if not covering:
            job["warnings"].append("The recording of {0!r} does not cover the whole range (clip {1:g}..{2:g})".format(
                entry["name"], clip.start_time, clip.end_time))
        if end > int(clip.sample_length) + 1:
            job["warnings"].append("{0!r} is {1:.0f} samples short of the bounce end".format(entry["name"], end - int(clip.sample_length)))
        files.append(record)
    return files


def _phase_finalizing(ctx, song, job):
    if _elapsed(job) < FINALIZE_DELAY:
        return
    if song.is_playing:
        song.stop_playing()
        return
    files = _collect(song, job)
    if files is None:
        if _elapsed(job) > FINALIZE_TIMEOUT:
            raise CommandError("live_error", "Live did not create the recorded clips within {0:.0f}s".format(FINALIZE_TIMEOUT))
        return
    job["files"] = files
    with _UndoStep(song):
        for entry in job["tracks"]:
            track = _track_named(song, entry["name"])
            if track is not None and track.arm:
                track.arm = False
        failures = _restore(song, job)
    if failures:
        job["warnings"].append("Could not restore: " + "; ".join(failures))
    job["_internal"]["verify_attempts"] = 0
    _set_phase(job, "verifying")


def _phase_verifying(ctx, song, job):
    internal = job["_internal"]
    if internal["ticks"] < 2:
        return  # song properties read back in the tick they were written still show the old value
    mismatches = _restore_mismatches(song, job)
    if mismatches and internal["verify_attempts"] < VERIFY_ATTEMPTS:
        internal["verify_attempts"] += 1
        with _UndoStep(song):
            _restore(song, job, only=set(mismatches))
        internal["ticks"] = 0
        return
    if mismatches:
        job["warnings"].append("Could not restore: " + ", ".join(mismatches))
    job["restored"] = not mismatches
    job["phase"] = "recorded"
    job["finished_at"] = _now()
    journal.event("phase", "{0} {1}: recorded".format(LABEL, job.get("id")))


def _phase_aborting(ctx, song, job):
    if job["_internal"]["ticks"] < 2:
        return  # let Live finish the recording before its tracks are deleted
    _abort_finish(ctx, song, job)


PHASES = {
    "route": _phase_route,
    "arm": _phase_arm,
    "go": _phase_go,
    "starting": _phase_starting,
    "recording": _phase_recording,
    "finalizing": _phase_finalizing,
    "verifying": _phase_verifying,
    "aborting": _phase_aborting,
}


@ticker
def bounce_tick(ctx):
    job = _job(ctx)
    if not job or job.get("phase") not in ACTIVE:
        return
    job["_internal"]["ticks"] += 1
    try:
        song = ctx.song
        identity = job["_internal"].get("song_identity")
        if identity is not None and _song_identity(song) not in (None, identity):
            job["error"] = "The Live Set changed during the bounce; nothing was restored"
            job["phase"] = "failed"
            job["finished_at"] = _now()
            return
        PHASES[job["phase"]](ctx, song, job)
    except CommandError as error:
        if job["phase"] == "aborting":
            job["phase"] = "failed"
            job.setdefault("error", error.message)
        else:
            _fail(ctx, job, error.message)
    except Exception as error:
        ctx.log("bounce engine error:\n" + traceback.format_exc())
        if job["phase"] == "aborting":
            job["phase"] = "failed"
            job.setdefault("error", str(error))
        else:
            _fail(ctx, job, "Bounce engine error: {0}".format(error))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _warnings(ctx, song, chosen, count_in):
    warnings = []
    if song.back_to_arranger:
        warnings.append("Back to Arrangement is lit (Session clips override the arrangement); the bounce returns every "
                        "track to the arrangement, and Live's API cannot re-light the button afterwards")
    if count_in:
        warnings.append("Count-in is {0} bar(s) (read-only in the API); recording starts after it".format(COUNT_IN_BARS.get(count_in, count_in)))
    soloed = [track.name for track in list(song.tracks) + list(song.return_tracks) if track.solo]
    if soloed:
        warnings.append("Soloed tracks ({0}): the master contains only them, and stems of other tracks are silent".format(", ".join(soloed)))
    muted = [track.name for track, _ in chosen if getattr(track, "mute", False)]
    if muted:
        warnings.append("Muted stems are silent: " + ", ".join(muted))
    try:
        if song.re_enable_automation_enabled:
            warnings.append("Some automated parameters are overridden, so their automation will not play; "
                            "lom_call('live_set', 're_enable_automation') first to render it")
    except Exception:
        pass
    try:
        load = float(ctx.app.average_process_usage)
        if load > 75.0:
            warnings.append("Live's CPU load is {0:.0f}%; a real-time bounce may drop out".format(load))
    except Exception:
        pass
    return warnings


@command("bounce_start", timeout=30.0)
def bounce_start(ctx, start=0, end=None, tail=0, stems=None, include_returns=False, name=None, output_dir=None):
    """Start a real-time bounce of the arrangement from start to end (+ tail): the master plus optional stems.

    start / end: beats, 'bar.beat.sixteenth' or a locator name; end defaults to the last event
    rounded up to a bar. tail: beats, '1 bar' or seconds ('2 s'). stems: None, 'all' (tracks with
    audio output that are not muted) or a list of track refs; include_returns adds every return.
    output_dir is stored with the job for the MCP server. Poll bounce_status.
    """
    song = ctx.song
    job = _job(ctx)
    if job and job.get("phase") in ACTIVE + ("recorded",):
        raise CommandError("busy", "Bounce {0} is still {1}".format(job["id"], job["phase"]),
                           hint="Poll get_bounce_status until it finishes, or call cancel_bounce.")
    capture = ctx.state.get("capture")
    if capture and capture.get("phase") not in (None, "idle", "done", "failed", "cancelled"):
        raise CommandError("busy", "A capture is {0}; Live can record one thing at a time".format(capture.get("phase")),
                           hint="Wait for it with capture(wait=...), or capture(cancel=True).")
    stale = [track.name for _, track in _bounce_tracks(song)]
    if stale:
        raise CommandError("busy", "Leftover bounce tracks exist: " + ", ".join(stale),
                           hint="Call cancel_bounce to remove them, then bounce again.")
    if song.record_mode or song.session_record:
        raise CommandError("busy", "Live is recording (Arrangement or Session Record is on)", hint="Turn recording off first.")
    start_beats = _parse_position(song, start, "start")
    if start_beats < 0:
        raise CommandError("invalid_argument", "start cannot be negative")
    bar = values.bar_length(song)
    if end is None:
        end_beats = round_up_to_bar(float(song.last_event_time), bar)
        if end_beats <= start_beats:
            raise CommandError("invalid_argument", "The arrangement has nothing after {0}; pass end explicitly".format(values.format_time(song, start_beats)))
    else:
        end_beats = _parse_position(song, end, "end")
    if end_beats <= start_beats:
        raise CommandError("invalid_argument", "end ({0}) must be after start ({1})".format(values.format_time(song, end_beats), values.format_time(song, start_beats)))
    tail_beats = parse_tail(song, tail)
    tempo = float(song.tempo)
    stop_beats = end_beats + tail_beats
    duration = (stop_beats - start_beats) * 60.0 / tempo
    if duration > MAX_SECONDS:
        raise CommandError("invalid_argument", "The bounce would last {0:.0f} min; the limit is {1:.0f} min".format(duration / 60, MAX_SECONDS / 60),
                           hint="Pass a shorter range with start and end.")
    chosen, skipped = _resolve_stems(song, stems, include_returns)
    labels = unique_labels([track.name for track, _ in chosen])
    count_in = int(getattr(song, "count_in_duration", 0) or 0)
    warnings = _warnings(ctx, song, chosen, count_in)
    snapshot = _snapshot(song)
    was_playing = bool(song.is_playing)
    if was_playing:
        song.stop_playing()
        warnings.append("The transport was playing; it was stopped for the bounce")

    entries = [{"name": PREFIX + MASTER_STEM, "role": "master", "stem": MASTER_STEM}]
    for (track, kind), label in zip(chosen, labels):
        entries.append({"name": PREFIX + label, "role": "stem", "stem": label,
                        "source": {"ref": refs.track_ref(song, track), "name": track.name, "kind": kind}})
    created = []
    try:
        for entry in entries:
            track = song.create_audio_track(-1)
            track.name = entry["name"]
            created.append(entry["name"])
    except Exception as error:
        _delete_tracks(song, set(created))
        raise CommandError("unsupported", "Could not create the bounce tracks: {0}".format(error),
                           hint="Live editions limit the number of tracks; bounce fewer stems.")

    job_id = "bounce-{0}".format(int(_now() * 1000))
    job = {
        "id": job_id,
        "phase": "route",
        "name": (name or "").strip() or getattr(song, "name", "") or "Bounce",
        "output_dir": output_dir,
        "range": {
            "start": values.time_out(song, start_beats),
            "end": values.time_out(song, end_beats),
            "tail_beats": round(tail_beats, 6),
            "stop_beats": round(stop_beats, 6),
            "record_until_beats": round(stop_beats + STOP_MARGIN_SECONDS * tempo / 60.0, 6),
        },
        "tempo": tempo,
        "bar_beats": bar,
        "duration_seconds": round(duration, 6),
        "stems": [entry["stem"] for entry in entries[1:]],
        "tracks": entries,
        "skipped": skipped,
        "warnings": warnings,
        "count_in": count_in,
        "song": _song_info(song),
        "progress": 0.0,
        "created_at": _now(),
        "_internal": {
            "snapshot": snapshot,
            "song_identity": _song_identity(song),
            "settle_until": _now() + SETTLE_SECONDS if was_playing else 0,
            "transport_changed": False,
            "phase_since": _now(),
            "ticks": 0,
        },
    }
    ctx.state["bounce"] = job
    return _view(job)


@command("bounce_status", readonly=True)
def bounce_status(ctx):
    """The current or last bounce job: phase, progress, ETA, warnings, and the recorded files when done."""
    job = _job(ctx)
    if not job:
        return {"phase": "idle"}
    return _view(job)


@command("bounce_cancel")
def bounce_cancel(ctx):
    """Cancel the running bounce: stop recording, restore the transport and remove the bounce tracks.

    With no running bounce, removes leftover "[bounce] ..." tracks.
    """
    song = ctx.song
    job = _job(ctx)
    if job and job.get("phase") in ACTIVE:
        if job["phase"] != "aborting":
            _fail(ctx, job, "cancelled", cancelled=True)
        return _view(job)
    if job and job.get("phase") == "recorded":
        job["removed_tracks"] = _delete_tracks(song, set(entry["name"] for entry in job["tracks"]))
        _restore_selection(song, job)
        job["cancelled"] = True
        job["phase"] = "cancelled"
        job["finished_at"] = _now()
        return _view(job)
    removed = _delete_tracks(song, set(track.name for _, track in _bounce_tracks(song)))
    return {"phase": job["phase"] if job else "idle", "removed_tracks": removed}


@command("bounce_cleanup")
def bounce_cleanup(ctx, job_id, outputs=None):
    """Remove a finished bounce's tracks after its files were copied; outputs is stored with the job."""
    song = ctx.song
    job = _job(ctx)
    if not job or job.get("id") != job_id:
        raise CommandError("not_found", "No bounce job {0!r} (current: {1})".format(job_id, job["id"] if job else "none"))
    if job["phase"] in ACTIVE:
        raise CommandError("busy", "Bounce {0} is still {1}".format(job_id, job["phase"]), hint="Use cancel_bounce to stop it.")
    job["removed_tracks"] = _delete_tracks(song, set(entry["name"] for entry in job["tracks"]))
    _restore_selection(song, job)
    if job["phase"] == "recorded":
        job["phase"] = "done"
    if outputs is not None:
        job["outputs"] = outputs
    return _view(job)


@command("bounce_song_info", readonly=True)
def bounce_song_info(ctx):
    """Tempo, meter, key, scale, set name and locators, plus the default bounce end (last event, rounded up to a bar)."""
    song = ctx.song
    info = _song_info(song)
    info["last_event"] = values.time_out(song, float(song.last_event_time))
    info["default_end"] = values.time_out(song, round_up_to_bar(float(song.last_event_time), values.bar_length(song)))
    info["count_in"] = int(getattr(song, "count_in_duration", 0) or 0)
    return info
