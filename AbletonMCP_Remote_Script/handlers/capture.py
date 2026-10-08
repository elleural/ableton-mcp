"""Listening loop: the Session capture engine (docs/listening-loop-plan.md, PRD section 6).

A capture records Session clips in real time: temporary audio tracks named "cap:<key>" take their
input from a source track's Post Mixer tap, a return track, or Resampling (the main mix), and record
into an empty Session slot that is fired in the same main-thread tick as the source clips. Verified on
Live 12.4.6 (docs/spikes.md): recording starts on the same sample as the source clips, the recorded
clip is warped with clip beat 0 at its start marker, and gain is unity for every route.

The MCP server plans the job (which clips to fire, which taps to record, how many beats) from the
spec; this module only drives Live. A job is a list of passes; a ticker runs each pass:

  route       on a later tick (routing lists are empty in the tick a track is created): inputs,
              output "Sends Only", sends at minimum, monitoring Off
  prepare     stop clips and transport, tempo, quantization 1 bar, loop/metronome/record off, mutes
              or solos for the pass, arm only this pass's capture tracks (disarm everything else)
  fire        once the settings read back: fire the source slots and the capture slots in one tick
  starting    wait until every capture slot records
  recording   until the planned beats plus a margin; a stop, a tempo change, a disarmed capture
              track or an armed user track fails the job (C7: the tempo is read at start and end)
  collect     stop the transport, read each recorded clip (file, sample rate, offset of beat 0),
              delete the clip so the slot is free for the next pass
  restore     after the last pass: song settings, mutes, solos, arms, selection
  verifying   read the restored state back on a later tick and re-apply what did not stick
  recorded    the MCP server copies and cuts the files, then calls capture_cleanup (tracks deleted)

Failures and capture_cancel stop the transport and go through "aborting", which restores the
snapshot and deletes the capture tracks on a later tick. The job lives in ctx.state["capture"] as
plain data, so it survives reload_remote_script.
"""
import time
import traceback

from .. import refs
from ..core import command, ticker
from ..errors import CommandError

PREFIX = "cap:"
MONITORING_OFF = 2          # Live.Track.Track.monitoring_states.OFF
RESAMPLING_CATEGORY = 2     # Live.Track.RoutingTypeCategory.resampling
ONE_BAR = 4                 # Song.clip_trigger_quantization: 1 bar
CAPTURE_SLOT = 0            # capture tracks record into their first slot, freed after every pass
STOP_MARGIN_SECONDS = 0.5   # keep recording past the planned beats so every cut has its tail
ROUTE_TIMEOUT = 15.0
PREPARE_TIMEOUT = 5.0
START_TIMEOUT = 10.0
COLLECT_DELAY = 0.3
COLLECT_TIMEOUT = 15.0
VERIFY_ATTEMPTS = 3
MAX_SECONDS = 60 * 60.0
TAPS = ("Pre FX", "Post FX", "Post Mixer")

ACTIVE = ("route", "prepare", "fire", "starting", "recording", "collect", "restore", "verifying", "aborting")
TERMINAL = ("recorded", "done", "failed", "cancelled")
BOUNCE_IDLE = (None, "idle", "done", "failed", "cancelled")

# Song settings a capture changes, in the order they are written back. back_to_arranger is
# snapshotted and switched off again when it was off (firing Session clips lights it).
SONG_FIELDS = (
    "tempo", "clip_trigger_quantization", "loop", "metronome", "punch_in", "punch_out", "arrangement_overdub",
    "session_automation_record", "record_mode", "session_record", "start_time", "current_song_time",
)
SNAPSHOT_ONLY = ("back_to_arranger", "is_playing")


# ---------------------------------------------------------------------------
# Pure helpers (unit tested offline)
# ---------------------------------------------------------------------------


def capture_track_name(key):
    return PREFIX + str(key)


def _number(value, what):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise CommandError("invalid_argument", "{0} must be a number, got {1!r}".format(what, value))
    if number != number or number in (float("inf"), float("-inf")):
        raise CommandError("invalid_argument", "{0} must be finite, got {1!r}".format(what, value))
    return number


def validate_passes(passes):
    """Normalise the planned passes; raises CommandError naming the first problem."""
    if not isinstance(passes, (list, tuple)) or not passes:
        raise CommandError("invalid_argument", "passes must be a non-empty list")
    out = []
    for number, item in enumerate(passes):
        where = "pass {0}".format(number)
        if not isinstance(item, dict):
            raise CommandError("invalid_argument", where + " must be an object")
        fire = item.get("fire") or []
        record = item.get("record") or []
        if not isinstance(fire, (list, tuple)) or not fire:
            raise CommandError("invalid_argument", where + " fires no clips")
        if not isinstance(record, (list, tuple)) or not record:
            raise CommandError("invalid_argument", where + " records nothing")
        if item.get("beats") is None:
            raise CommandError("invalid_argument", where + " needs beats (how long to record)")
        beats = _number(item.get("beats"), where + " beats")
        if beats <= 0:
            raise CommandError("invalid_argument", where + " beats must be positive")
        tempo = item.get("tempo")
        if tempo is not None:
            tempo = _number(tempo, where + " tempo")
            if not 20.0 <= tempo <= 999.0:
                raise CommandError("invalid_argument", where + " tempo must be 20..999 BPM")
        fires = []
        for entry in fire:
            if not isinstance(entry, dict) or "track" not in entry or "slot" not in entry:
                raise CommandError("invalid_argument", where + " fire entries need track and slot")
            slot = _number(entry["slot"], where + " slot")
            if slot != int(slot) or slot < 0:
                raise CommandError("invalid_argument", where + " slot must be a scene index (0 or more)")
            fires.append({"track": str(entry["track"]), "slot": int(slot)})
        keys = []
        records = []
        for entry in record:
            if not isinstance(entry, dict):
                raise CommandError("invalid_argument", where + " record entries must be objects")
            key = str(entry.get("key") or "").strip()
            source = str(entry.get("source") or "").strip()
            tap = entry.get("tap") or "Post Mixer"
            if not key or not source:
                raise CommandError("invalid_argument", where + " record entries need key and source")
            if tap not in TAPS:
                raise CommandError("invalid_argument", "{0}: tap must be one of {1}".format(where, ", ".join(TAPS)))
            if key in keys:
                raise CommandError("invalid_argument", "{0} records key {1!r} twice".format(where, key))
            keys.append(key)
            records.append({"key": key, "source": source, "tap": tap})
        solo = item.get("solo")
        if solo is not None and not isinstance(solo, (list, tuple)):
            raise CommandError("invalid_argument", where + " solo must be a list of track names")
        out.append({
            "label": str(item.get("label") or "pass {0}".format(number + 1)),
            "tempo": tempo,
            "fire": fires,
            "record": records,
            "solo": [str(name) for name in solo] if solo else None,
            "mute_others": bool(item.get("mute_others", not solo)),
            "beats": beats,
        })
    return out


def pass_seconds(item, default_tempo):
    tempo = item["tempo"] or default_tempo
    return item["beats"] * 60.0 / float(tempo) + STOP_MARGIN_SECONDS


def mismatched(expected, actual):
    if isinstance(expected, bool) or isinstance(actual, bool):
        return bool(expected) != bool(actual)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) > 1e-3
    return expected != actual


def wanted_states(tracks, item):
    """{name: (mute, solo, arm)} a pass wants for every regular track.

    tracks: [(name, user mute, is_capture, is_group)], where the mute is the user's own (from the
    snapshot taken before the capture), so a track one pass muted is unmuted again when a later pass
    fires it. Capture tracks of this pass are armed and everything else disarmed. Tap passes
    (mute_others) mute every track that is not fired, so their arrangement clips cannot play into the
    mix; solo passes solo exactly the listed tracks.
    """
    fired = set(entry["track"] for entry in item["fire"])
    recording = set(capture_track_name(entry["key"]) for entry in item["record"])
    solo = set(item["solo"] or [])
    out = {}
    for name, mute, is_capture, is_group in tracks:
        if is_capture:
            out[name] = (False, False, name in recording)
            continue
        if item["mute_others"] and name not in fired and not is_group:
            mute = True
        out[name] = (bool(mute), name in solo, False)
    return out


# ---------------------------------------------------------------------------
# Live helpers
# ---------------------------------------------------------------------------


def _now():
    return time.time()


def _song_identity(song):
    pointer = getattr(song, "_live_ptr", None)
    return int(pointer) if isinstance(pointer, int) else None


def _exact_track(song, name, include_returns=False):
    """The one track named exactly `name` (regular tracks; returns by full or bare name if asked)."""
    matches = [track for track in song.tracks if track.name == name]
    if include_returns and not matches:
        for index, track in enumerate(song.return_tracks):
            if name in (track.name, refs.return_bare_name(track.name), "return:" + refs.return_letter(index)):
                matches.append(track)
    if not matches:
        return None
    if len(matches) > 1:
        raise CommandError("invalid_argument", "Several tracks are named {0!r}; capture needs unique names".format(name))
    return matches[0]


def _require(song, name, what="Track", include_returns=False):
    track = _exact_track(song, name, include_returns)
    if track is None:
        raise CommandError("not_found", "{0} {1!r} does not exist (deleted or renamed?)".format(what, name))
    return track


def _capture_tracks(song):
    """Leftover capture tracks: named "cap:..." and routed to Sends Only, as the engine leaves them."""
    out = []
    for index, track in enumerate(song.tracks):
        if not str(track.name).startswith(PREFIX):
            continue
        try:
            ours = track.output_routing_type.display_name == "Sends Only"
        except Exception:
            ours = False
        if ours:
            out.append((index, track))
    return out


def _delete_tracks(song, names):
    removed = []
    for index in reversed(range(len(song.tracks))):
        name = song.tracks[index].name   # read before deleting: a deleted track raises on any read
        if name in names:
            song.delete_track(index)
            removed.append(name)
    return removed


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


class _UndoStep(object):
    def __init__(self, song):
        self.song = song

    def __enter__(self):
        self.song.begin_undo_step()

    def __exit__(self, *exc):
        self.song.end_undo_step()
        return False


def _plain(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return float(value)
    if isinstance(value, int):
        return int(value)
    return value


def _snapshot(song):
    snapshot = {"song": {}, "tracks": [], "returns": [], "selected_track": None}
    for field in SONG_FIELDS + SNAPSHOT_ONLY:
        try:
            snapshot["song"][field] = _plain(getattr(song, field))
        except Exception:
            pass
    for index, track in enumerate(song.tracks):
        entry = {"index": index, "name": track.name, "mute": bool(track.mute), "solo": bool(track.solo)}
        if track.can_be_armed:
            entry["arm"] = bool(track.arm)
        try:
            entry["back_to_arranger"] = bool(track.back_to_arranger)
        except Exception:
            pass
        snapshot["tracks"].append(entry)
    for index, track in enumerate(song.return_tracks):
        snapshot["returns"].append({"index": index, "name": track.name, "mute": bool(track.mute), "solo": bool(track.solo)})
    try:
        selected = song.view.selected_track
        snapshot["selected_track"] = {"ref": refs.track_ref(song, selected), "name": selected.name}
    except Exception:
        pass
    return snapshot


def _snapshot_track(song, entry, returns=False):
    tracks = list(song.return_tracks if returns else song.tracks)
    if entry["index"] < len(tracks) and tracks[entry["index"]].name == entry["name"]:
        return tracks[entry["index"]]
    matches = [track for track in tracks if track.name == entry["name"]]
    return matches[0] if len(matches) == 1 else None


def _restore(song, snapshot, only=None):
    """Write the snapshot back; returns the fields that raised."""
    failures = []
    for field in SONG_FIELDS:
        if field not in snapshot["song"] or (only is not None and field not in only):
            continue
        try:
            setattr(song, field, snapshot["song"][field])
        except Exception as error:
            failures.append("{0} ({1})".format(field, error))
    for returns, entries in ((False, snapshot["tracks"]), (True, snapshot["returns"])):
        for entry in entries:
            track = _snapshot_track(song, entry, returns)
            if track is None:
                continue
            for field in ("mute", "solo", "arm"):
                if field not in entry or (only is not None and "{0}:{1}".format(field, entry["name"]) not in only):
                    continue
                try:
                    if bool(getattr(track, field)) != entry[field]:
                        setattr(track, field, entry[field])
                except Exception as error:
                    failures.append("{0} of {1!r} ({2})".format(field, entry["name"], error))
    # Firing Session clips takes tracks off the arrangement. The API can only send a track back
    # (False), so every track that followed the arrangement before the capture is sent back.
    for entry in snapshot["tracks"]:
        if entry.get("back_to_arranger") is not False:
            continue
        if only is not None and "back_to_arranger:" + entry["name"] not in only:
            continue
        track = _snapshot_track(song, entry)
        try:
            if track is not None and track.back_to_arranger:
                track.back_to_arranger = False
        except Exception as error:
            failures.append("back_to_arranger of {0!r} ({1})".format(entry["name"], error))
    return failures


def _mismatches(song, snapshot):
    out = []
    for field in SONG_FIELDS:
        if field in snapshot["song"]:
            try:
                if mismatched(snapshot["song"][field], getattr(song, field)):
                    out.append(field)
            except Exception:
                out.append(field)
    for returns, entries in ((False, snapshot["tracks"]), (True, snapshot["returns"])):
        for entry in entries:
            track = _snapshot_track(song, entry, returns)
            if track is None:
                continue
            for field in ("mute", "solo", "arm"):
                if field in entry and bool(getattr(track, field)) != entry[field]:
                    out.append("{0}:{1}".format(field, entry["name"]))
            if not returns and entry.get("back_to_arranger") is False:
                try:
                    if track.back_to_arranger:
                        out.append("back_to_arranger:" + entry["name"])
                except Exception:
                    pass
    return out


def _restore_selection(song, snapshot):
    selected = snapshot.get("selected_track")
    if not selected:
        return
    try:
        track = refs.track(song, selected["ref"])
        if track.name != selected["name"]:
            track = refs.track(song, selected["name"])
        song.view.selected_track = track
    except Exception:
        pass


def _slot(track, index):
    slots = list(track.clip_slots)
    if not 0 <= index < len(slots):
        raise CommandError("not_found", "Track {0!r} has no slot {1} (slots 0..{2})".format(track.name, index, len(slots) - 1))
    return slots[index]


def _source_track(song, source):
    if source.lower() == "resampling":
        return None
    return _require(song, source, "Capture source", include_returns=True)


def _track_rows(song, snapshot):
    """Rows for wanted_states: each track's mute as the user left it before the capture."""
    user = dict((entry["name"], entry["mute"]) for entry in snapshot["tracks"])
    return [(track.name, user.get(track.name, bool(track.mute)), track.name.startswith(PREFIX),
             bool(getattr(track, "is_foldable", False))) for track in song.tracks]


# ---------------------------------------------------------------------------
# Job bookkeeping
# ---------------------------------------------------------------------------


def _job(ctx):
    return ctx.state.get("capture")


def _set_phase(job, phase):
    job["phase"] = phase
    job["_internal"]["phase_since"] = _now()
    job["_internal"]["ticks"] = 0


def _elapsed(job):
    return _now() - job["_internal"]["phase_since"]


def _current(job):
    return job["passes"][job["pass_index"]]


def _eta(job):
    if job["phase"] in TERMINAL:
        return 0.0
    if job["phase"] in ("restore", "verifying", "aborting"):
        return 1.0
    remaining = 0.0
    for index, item in enumerate(job["passes"]):
        if index < job["pass_index"]:
            continue
        seconds = pass_seconds(item, job["tempo"]) + 1.0
        if index == job["pass_index"] and job["phase"] == "recording":
            seconds = max(0.0, seconds * (1.0 - job.get("pass_progress", 0.0)))
        elif index == job["pass_index"] and job["phase"] == "collect":
            seconds = 1.0
        remaining += seconds
    return round(remaining + 1.0, 1)


def _view(job):
    out = dict((key, value) for key, value in job.items() if not key.startswith("_"))
    out["eta_seconds"] = _eta(job)
    return out


def _fail(ctx, job, message, cancelled=False):
    if job.get("phase") in TERMINAL:
        return
    job.setdefault("warnings", [])
    if cancelled:
        job["cancelled"] = True
    else:
        job["error"] = message
    ctx.log("capture {0}: {1}".format(job["id"], message))
    try:
        song = ctx.song
        if song.is_playing:
            song.stop_playing()
        song.stop_all_clips(False)
        song.record_mode = False   # it was off at the start; a capture never records the arrangement
    except Exception:
        ctx.log("capture abort could not stop the transport:\n" + traceback.format_exc())
    _set_phase(job, "aborting")


def _abort_finish(ctx, song, job):
    problems = []
    try:
        with _UndoStep(song):
            if song.is_playing:
                song.stop_playing()
            if job["_internal"].get("touched"):
                problems += _restore(song, job["_internal"]["snapshot"])
            job["removed_tracks"] = _delete_tracks(song, set(job["tracks"]))
            _restore_selection(song, job["_internal"]["snapshot"])
    except Exception as error:
        problems.append(str(error))
        ctx.log("capture abort cleanup error:\n" + traceback.format_exc())
    if problems:
        job["warnings"].append("Cleanup problems: " + "; ".join(problems))
    job["phase"] = "cancelled" if job.get("cancelled") else "failed"
    job["finished_at"] = _now()


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def _phase_route(ctx, song, job):
    if job["_internal"]["ticks"] < 2:
        return  # never in the tick the tracks were created: their routing lists are still empty
    pending = []
    for key, entry in job["routes"].items():
        track = _require(song, capture_track_name(key), "Capture track")
        types = [item for item in track.available_input_routing_types if str(item.display_name)]
        if not types:
            pending.append(key)
            continue
        source = _source_track(song, entry["source"])
        if source is None:
            target = [item for item in types if _category(item) == RESAMPLING_CATEGORY or item.display_name == "Resampling"]
        else:
            target = [item for item in types if _attached(item, source)]
        if not target:
            if _elapsed(job) < ROUTE_TIMEOUT:
                pending.append(key)
                continue
            raise CommandError("unsupported", "Live offers no input from {0!r} to {1!r}. Inputs: {2}".format(
                entry["source"], track.name, ", ".join(item.display_name for item in types)))
        track.input_routing_type = target[0]
        if source is not None:
            channels = [item for item in track.available_input_routing_channels if item.display_name == entry["tap"]]
            if not channels:
                if _elapsed(job) < ROUTE_TIMEOUT:
                    pending.append(key)
                    continue
                raise CommandError("unsupported", "{0!r} offers no {1!r} tap".format(entry["source"], entry["tap"]))
            track.input_routing_channel = channels[0]
        outputs = [item for item in track.available_output_routing_types if item.display_name == "Sends Only"]
        if outputs:
            track.output_routing_type = outputs[0]
        try:
            for send in track.mixer_device.sends:
                send.value = send.min
        except Exception:
            pass
        track.current_monitoring_state = MONITORING_OFF
    if pending:
        if _elapsed(job) > ROUTE_TIMEOUT:
            raise CommandError("timeout", "Live did not offer the capture inputs in time: " + ", ".join(pending))
        return
    _set_phase(job, "prepare")


def _phase_prepare(ctx, song, job):
    internal = job["_internal"]
    item = _current(job)
    if internal["ticks"] == 1:
        internal["touched"] = True
        with _UndoStep(song):
            if song.is_playing:
                song.stop_playing()
            song.stop_all_clips(False)
            song.record_mode = False
            song.session_record = False
            song.session_automation_record = False
            song.loop = False
            song.metronome = False
            song.punch_in = False
            song.punch_out = False
            song.clip_trigger_quantization = ONE_BAR
            song.start_time = 0.0
            if item["tempo"] is not None:
                song.tempo = item["tempo"]
            wanted = wanted_states(_track_rows(song, job["_internal"]["snapshot"]), item)
            for track in song.tracks:
                mute, solo, arm = wanted[track.name]
                if bool(track.mute) != mute:
                    track.mute = mute
                if bool(track.solo) != solo:
                    track.solo = solo
                if track.can_be_armed and bool(track.arm) != arm:
                    track.arm = arm
                if not arm and getattr(track, "implicit_arm", False):
                    track.implicit_arm = False   # auto-arm surfaces arm the selected track implicitly
            for track in song.return_tracks:
                if track.solo:
                    track.solo = False
            recording = [name for name, (_, _, arm) in wanted.items() if arm]
            try:
                song.view.selected_track = _require(song, recording[0])
            except Exception:
                pass
        return
    if internal["ticks"] < 3:
        return  # song properties read back in the tick they were written still show the old value
    problems = []
    if song.is_playing:
        problems.append("the transport is still playing")
    if item["tempo"] is not None and abs(float(song.tempo) - item["tempo"]) > 1e-6:
        problems.append("tempo is {0:g}, not {1:g}".format(song.tempo, item["tempo"]))
    wanted = wanted_states(_track_rows(song, job["_internal"]["snapshot"]), item)
    for track in song.tracks:
        mute, solo, arm = wanted[track.name]
        if bool(track.mute) != mute or bool(track.solo) != solo or (track.can_be_armed and bool(track.arm) != arm):
            problems.append("{0!r} is not in its pass state".format(track.name))
            if internal["ticks"] % 3 == 0:
                track.mute, track.solo = mute, solo
                if track.can_be_armed:
                    track.arm = arm
    for entry in item["fire"]:
        slot = _slot(_require(song, entry["track"]), entry["slot"])
        if not slot.has_clip:
            raise CommandError("not_found", "Track {0!r} has no clip in slot {1}".format(entry["track"], entry["slot"]))
    if problems:
        if _elapsed(job) > PREPARE_TIMEOUT:
            raise CommandError("live_error", "Live did not take the capture settings: " + "; ".join(problems[:4]))
        return
    _set_phase(job, "fire")


def _phase_fire(ctx, song, job):
    item = _current(job)
    sources = [_slot(_require(song, entry["track"]), entry["slot"]) for entry in item["fire"]]
    captures = [_require(song, capture_track_name(entry["key"]), "Capture track") for entry in item["record"]]
    for track in captures:
        if track.clip_slots[CAPTURE_SLOT].has_clip:
            track.clip_slots[CAPTURE_SLOT].delete_clip()
    # One tick: the source clips and the record slots start on the same launch quantum (spike-verified).
    for slot in sources:
        slot.fire()
    for track in captures:
        track.clip_slots[CAPTURE_SLOT].fire()
    job["_internal"]["fired_at"] = _now()
    _set_phase(job, "starting")


def _phase_starting(ctx, song, job):
    item = _current(job)
    captures = [_require(song, capture_track_name(entry["key"]), "Capture track") for entry in item["record"]]
    recording = all(track.clip_slots[CAPTURE_SLOT].is_recording for track in captures)
    if song.is_playing and recording:
        internal = job["_internal"]
        internal["start_position"] = float(song.start_time)
        internal["last_position"] = float(song.current_song_time)
        internal["last_time"] = _now()
        internal["start_tempo"] = float(song.tempo)
        _set_phase(job, "recording")
        return
    if _elapsed(job) > START_TIMEOUT:
        idle = [track.name for track in captures if not track.clip_slots[CAPTURE_SLOT].is_recording]
        raise CommandError("live_error", "Live did not start recording (playing={0}; not recording: {1})".format(
            bool(song.is_playing), ", ".join(idle) or "none"))


def _phase_recording(ctx, song, job):
    internal = job["_internal"]
    item = _current(job)
    position = float(song.current_song_time)
    now = _now()
    tempo = float(song.tempo)
    target = item["beats"] + STOP_MARGIN_SECONDS * tempo / 60.0
    done = position - internal["start_position"]
    job["pass_progress"] = round(min(1.0, max(0.0, done / target)), 3)
    job["progress"] = round((job["pass_index"] + job["pass_progress"]) / len(job["passes"]), 3)
    if not song.is_playing:
        raise CommandError("live_error", "Playback stopped at beat {0:.2f} of {1:g}; the capture was interrupted".format(done, item["beats"]))
    if abs(tempo - internal["start_tempo"]) > 1e-6:
        raise CommandError("live_error", "The tempo moved from {0:g} to {1:g} during the pass (C7: tempo automation is not allowed)".format(
            internal["start_tempo"], tempo))
    if song.record_mode:
        # (Session Record lights by itself while the capture slots record; only Arrangement Record is a risk.)
        raise CommandError("live_error", "Arrangement Record was switched on during the capture; stopped so Live does not write "
                           "the Session clips into the arrangement (undo reverts anything it wrote)")
    for entry in item["record"]:
        track = _require(song, capture_track_name(entry["key"]), "Capture track")
        if not track.clip_slots[CAPTURE_SLOT].is_recording:
            raise CommandError("live_error", "{0!r} stopped recording during the pass".format(track.name))
    for entry in item["fire"]:
        track = _require(song, entry["track"], "Source track")
        playing = int(track.playing_slot_index)
        if playing == entry["slot"]:
            continue
        slot = _slot(track, entry["slot"])
        looping = bool(slot.has_clip and slot.clip.looping)
        if playing >= 0 or looping:   # another clip launched, or a looping clip stopped (a one-shot may end)
            raise CommandError("live_error", "The clip of {0!r} stopped or another clip was launched on it during the pass".format(entry["track"]))
    allowed = (now - internal["last_time"]) * tempo / 60.0 * 2.0 + 1.0
    if position < internal["last_position"] - 0.05 or position - internal["last_position"] > allowed:
        raise CommandError("live_error", "The playhead jumped; the capture was interrupted")
    internal["last_position"], internal["last_time"] = position, now
    recording = set(capture_track_name(entry["key"]) for entry in item["record"])
    for track in song.tracks:
        if not track.can_be_armed:
            continue
        if track.name in recording:
            if not track.arm:
                raise CommandError("live_error", "Capture track {0!r} was disarmed during the pass".format(track.name))
        elif track.arm or getattr(track, "implicit_arm", False):
            raise CommandError("live_error", "Track {0!r} was armed during the capture; stopped before it could record over its "
                               "clips (undo reverts any take)".format(track.name))
    if done >= target:
        internal["end_tempo"] = tempo
        song.stop_playing()
        _set_phase(job, "collect")


def _collect(song, job):
    """Recorded file, rate, length and the sample of clip beat 0 per capture track; None while not ready."""
    item = _current(job)
    files = []
    for entry in item["record"]:
        track = _require(song, capture_track_name(entry["key"]), "Capture track")
        slot = track.clip_slots[CAPTURE_SLOT]
        if not slot.has_clip or slot.is_recording:
            return None
        clip = slot.clip
        path = clip.file_path
        if not path:
            return None
        start_marker = float(clip.start_marker)
        if clip.warping:
            offset = float(clip.beat_to_sample_time(start_marker))
        else:
            offset = start_marker * float(clip.sample_rate)
        files.append({
            "key": entry["key"], "source": entry["source"], "tap": None if entry["source"].lower() == "resampling" else entry["tap"],
            "file_path": path, "sample_rate": float(clip.sample_rate), "sample_length": int(clip.sample_length),
            "offset_samples": round(offset, 3), "warping": bool(clip.warping), "start_marker": start_marker,
        })
    return files


def _phase_collect(ctx, song, job):
    if _elapsed(job) < COLLECT_DELAY:
        return
    if song.is_playing:
        song.stop_playing()
        return
    files = _collect(song, job)
    if files is None:
        if _elapsed(job) > COLLECT_TIMEOUT:
            raise CommandError("live_error", "Live did not finish the recorded clips within {0:.0f}s".format(COLLECT_TIMEOUT))
        return
    item = _current(job)
    internal = job["_internal"]
    end_tempo = internal.get("end_tempo", internal["start_tempo"])
    job["results"].append({"label": item["label"], "tempo": internal["start_tempo"], "beats": item["beats"], "files": files,
                           "tempo_start": internal["start_tempo"], "tempo_end": end_tempo,
                           "tempo_steady": abs(end_tempo - internal["start_tempo"]) <= 1e-6})
    with _UndoStep(song):
        song.stop_all_clips(False)
        for entry in item["record"]:
            track = _exact_track(song, capture_track_name(entry["key"]))
            if track is not None and track.clip_slots[CAPTURE_SLOT].has_clip:
                track.clip_slots[CAPTURE_SLOT].delete_clip()
    job["pass_progress"] = 0.0
    if job["pass_index"] + 1 < len(job["passes"]):
        job["pass_index"] += 1
        _set_phase(job, "prepare")
        return
    job["progress"] = 1.0
    _set_phase(job, "restore")


def _phase_restore(ctx, song, job):
    if job["_internal"]["ticks"] < 2:
        return
    snapshot = job["_internal"]["snapshot"]
    with _UndoStep(song):
        song.stop_all_clips(False)
        for track in song.tracks:
            if track.name.startswith(PREFIX) and track.arm:
                track.arm = False
        failures = _restore(song, snapshot)
        _restore_selection(song, snapshot)
    if failures:
        job["warnings"].append("Could not restore: " + "; ".join(failures))
    job["_internal"]["verify_attempts"] = 0
    _set_phase(job, "verifying")


def _phase_verifying(ctx, song, job):
    internal = job["_internal"]
    if internal["ticks"] < 2:
        return
    snapshot = internal["snapshot"]
    mismatches = _mismatches(song, snapshot)
    if mismatches and internal["verify_attempts"] < VERIFY_ATTEMPTS:
        internal["verify_attempts"] += 1
        with _UndoStep(song):
            _restore(song, snapshot, only=set(mismatches))
        internal["ticks"] = 0
        return
    if mismatches:
        job["warnings"].append("Could not restore: " + ", ".join(mismatches))
    job["restored"] = not mismatches
    job["phase"] = "recorded"
    job["finished_at"] = _now()


def _phase_aborting(ctx, song, job):
    if job["_internal"]["ticks"] < 2:
        return  # let Live finish the recording before its tracks are deleted
    _abort_finish(ctx, song, job)


PHASES = {
    "route": _phase_route,
    "prepare": _phase_prepare,
    "fire": _phase_fire,
    "starting": _phase_starting,
    "recording": _phase_recording,
    "collect": _phase_collect,
    "restore": _phase_restore,
    "verifying": _phase_verifying,
    "aborting": _phase_aborting,
}


@ticker
def capture_tick(ctx):
    job = _job(ctx)
    if not job or job.get("phase") not in ACTIVE:
        return
    job["_internal"]["ticks"] += 1
    try:
        song = ctx.song
        identity = job["_internal"].get("song_identity")
        if identity is not None and _song_identity(song) not in (None, identity):
            job["error"] = "The Live Set changed during the capture; nothing was restored"
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
        ctx.log("capture engine error:\n" + traceback.format_exc())
        if job["phase"] == "aborting":
            job["phase"] = "failed"
            job.setdefault("error", str(error))
        else:
            _fail(ctx, job, "Capture engine error: {0}".format(error))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _live_version(app):
    try:
        return "{0}.{1}.{2}".format(app.get_major_version(), app.get_minor_version(), app.get_bugfix_version())
    except Exception:
        return None


def _warnings(ctx, song, passes):
    warnings = []
    if song.back_to_arranger:
        warnings.append("Back to Arrangement was lit before the capture: tracks already playing Session clips stay "
                        "off the arrangement; the others are sent back to it afterwards")
    fired = sorted(set(entry["track"] for item in passes for entry in item["fire"]))
    muted = [name for name in fired if _exact_track(song, name) is not None and _exact_track(song, name).mute]
    if muted:
        warnings.append("Muted source tracks record silence: " + ", ".join(muted))
    try:
        if song.re_enable_automation_enabled:
            warnings.append("Some automated parameters are overridden, so their automation will not play")
    except Exception:
        pass
    try:
        load = float(ctx.app.average_process_usage)
        if load > 75.0:
            warnings.append("Live's CPU load is {0:.0f}%; a real-time capture may drop out".format(load))
    except Exception:
        pass
    return warnings


@command("capture_start", timeout=30.0)
def capture_start(ctx, passes, name=None):
    """Start a Session capture: record the planned passes in real time. Poll capture_status.

    passes: [{label, tempo, fire: [{track, slot}], record: [{key, source, tap}], solo, mute_others, beats}]
    where source is a track name, a return ("return:A" or its name) or "resampling", and tap is
    "Post Mixer" (default), "Post FX" or "Pre FX". Each record key gets an audio track "cap:<key>".
    """
    song = ctx.song
    job = _job(ctx)
    if job and job.get("phase") in ACTIVE + ("recorded",):
        raise CommandError("busy", "Capture {0} is still {1}".format(job["id"], job["phase"]),
                           hint="Wait for it with capture(wait=...), or cancel it with capture(cancel=True).")
    bounce = ctx.state.get("bounce")
    if bounce and bounce.get("phase") not in BOUNCE_IDLE:
        raise CommandError("busy", "A bounce is {0}; Live can record one thing at a time".format(bounce.get("phase")),
                           hint="Wait with get_bounce_status, or cancel_bounce.")
    stale = [track.name for _, track in _capture_tracks(song)]
    if stale:
        raise CommandError("busy", "Leftover capture tracks exist: " + ", ".join(stale), hint="capture(cancel=True) removes them.")
    if song.record_mode or song.session_record:
        raise CommandError("busy", "Live is recording (Arrangement or Session Record is on)", hint="Turn recording off first.")
    passes = validate_passes(passes)
    tempo = float(song.tempo)
    total = sum(pass_seconds(item, tempo) for item in passes)
    if total > MAX_SECONDS:
        raise CommandError("invalid_argument", "The capture would record {0:.0f} min; the limit is {1:.0f} min".format(total / 60, MAX_SECONDS / 60))
    routes = {}
    for item in passes:
        for entry in item["fire"]:
            track = _require(song, entry["track"], "Source track")
            if not _slot(track, entry["slot"]).has_clip:
                raise CommandError("not_found", "Track {0!r} has no clip in slot {1}".format(entry["track"], entry["slot"]))
        for track_name in item["solo"] or []:
            _require(song, track_name, "Solo track")
        for entry in item["record"]:
            if entry["source"].lower() != "resampling":
                source = _source_track(song, entry["source"])
                if refs.same(source, song.master_track):
                    raise CommandError("invalid_argument", "Record the main mix with source 'resampling'")
            previous = routes.get(entry["key"])
            if previous and (previous["source"], previous["tap"]) != (entry["source"], entry["tap"]):
                raise CommandError("invalid_argument", "Key {0!r} is recorded from two different sources".format(entry["key"]))
            routes[entry["key"]] = {"source": entry["source"], "tap": entry["tap"]}
    warnings = _warnings(ctx, song, passes)
    snapshot = _snapshot(song)
    names = [capture_track_name(key) for key in routes]
    created = []
    try:
        for track_name in names:
            track = song.create_audio_track(-1)
            track.name = track_name
            created.append(track_name)
    except Exception as error:
        _delete_tracks(song, set(created))
        raise CommandError("unsupported", "Could not create the capture tracks: {0}".format(error),
                           hint="Live editions limit the number of tracks; capture fewer stems per pass.")
    job = {
        "id": "capture-{0}".format(int(_now() * 1000)),
        "name": name,
        "phase": "route",
        "passes": passes,
        "pass_index": 0,
        "pass_progress": 0.0,
        "progress": 0.0,
        "tempo": tempo,
        "duration_seconds": round(total, 3),
        "tracks": names,
        "routes": routes,
        "results": [],
        "warnings": warnings,
        "live_version": _live_version(ctx.app),
        "set": {"name": getattr(song, "name", "") or None, "path": getattr(song, "file_path", "") or None},
        "created_at": _now(),
        "_internal": {"snapshot": snapshot, "song_identity": _song_identity(song), "phase_since": _now(), "ticks": 0, "touched": False},
    }
    ctx.state["capture"] = job
    return _view(job)


@command("capture_status", readonly=True)
def capture_status(ctx):
    """The current or last capture job: phase, pass, progress, ETA, warnings and the recorded files."""
    job = _job(ctx)
    if not job:
        return {"phase": "idle"}
    return _view(job)


@command("capture_cancel")
def capture_cancel(ctx):
    """Cancel the running capture (restores the set and removes the capture tracks); with none running,
    remove leftover "cap:" tracks."""
    song = ctx.song
    job = _job(ctx)
    if job and job.get("phase") in ACTIVE:
        if job["phase"] != "aborting":
            _fail(ctx, job, "cancelled", cancelled=True)
        return _view(job)
    if job and job.get("phase") == "recorded":
        job["removed_tracks"] = _delete_tracks(song, set(job["tracks"]))
        job["cancelled"] = True
        job["phase"] = "cancelled"
        job["finished_at"] = _now()
        return _view(job)
    removed = _delete_tracks(song, set(track.name for _, track in _capture_tracks(song)))
    return {"phase": job["phase"] if job else "idle", "removed_tracks": removed}


@command("capture_cleanup")
def capture_cleanup(ctx, job_id, outputs=None):
    """Remove a finished capture's tracks after the MCP server copied its files; outputs is kept with the job."""
    song = ctx.song
    job = _job(ctx)
    if not job or job.get("id") != job_id:
        raise CommandError("not_found", "No capture job {0!r} (current: {1})".format(job_id, job["id"] if job else "none"))
    if job["phase"] in ACTIVE:
        raise CommandError("busy", "Capture {0} is still {1}".format(job_id, job["phase"]))
    job["removed_tracks"] = _delete_tracks(song, set(job["tracks"]))
    _restore_selection(song, job["_internal"]["snapshot"])
    if job["phase"] == "recorded":
        job["phase"] = "done"
    if outputs is not None:
        job["outputs"] = outputs
    return _view(job)
