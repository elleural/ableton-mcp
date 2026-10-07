"""WS-A: status, overview, undo/redo and dialogs (docs/PRD.md section 7.1). Owned by workstream A."""
import math
import sys

from .. import core, refs, values
from ..core import command
from ..errors import CommandError

# Job states that mean "finished" for get_status's active-jobs report.
_FINISHED = ("done", "complete", "completed", "finished", "error", "failed", "cancelled", "canceled", "idle")


# ---------------------------------------------------------------------------
# Small shared formatting helpers (also used by handlers/song.py)
# ---------------------------------------------------------------------------


def signature_text(numerator, denominator):
    return "{0}/{1}".format(int(numerator), int(denominator))


def number(value, digits=4):
    """Round a float for output; infinities become strings so the JSON stays valid."""
    value = float(value)
    if math.isinf(value) or math.isnan(value):
        return str(value)
    return round(value, digits)


def db(parameter):
    """A volume or send parameter in dB, rounded, '-inf' for silence."""
    level = values.volume_db(parameter)
    if level is None:
        return None
    return number(level, 2)


def color(obj):
    """'#RRGGBB' of a track, clip or scene (None when it has no colour)."""
    return values.color_out(obj).get("color")


def safe(getter, default=None):
    """Read a Live property that some objects lack (mute on master, arm on returns, ...)."""
    try:
        return getter()
    except Exception:
        return default


def document_id(song):
    """An identifier of the open Live Set that changes when a new set is created or opened."""
    pointer = getattr(song, "_live_ptr", None)
    return "{0:x}".format(pointer) if isinstance(pointer, int) else "{0:x}".format(id(song))


def active_jobs(state):
    """Unfinished background jobs in the script's reload-safe state.

    Convention for job owners (e.g. the bounce engine): keep jobs in state["jobs"] as
    {job_id: {"kind": ..., "status": ...}}, or keep one dict with a "status" key at the top level
    of the state. Any status not in _FINISHED counts as active.
    """
    found = []
    if not isinstance(state, dict):
        return found
    jobs = state.get("jobs")
    if isinstance(jobs, dict):
        for job_id, job in jobs.items():
            if isinstance(job, dict) and str(job.get("status", "")).lower() not in _FINISHED:
                found.append(dict({"id": str(job_id)}, **_job_summary(job)))
    for key, job in state.items():
        # Job owners report either "status" or, like the bounce engine, "phase".
        if key == "jobs" or not isinstance(job, dict) or not ("status" in job or "phase" in job):
            continue
        status = job.get("status", job.get("phase"))
        if str(status).lower() not in _FINISHED:
            summary = _job_summary(job)
            summary.setdefault("kind", key)
            summary["status"] = status
            found.append(dict({"id": str(job.get("id", key))}, **summary))
    return found


def _job_summary(job):
    summary = {}
    for key in ("kind", "status", "phase", "progress", "message"):
        if key in job and isinstance(job[key], (str, int, float, bool)):
            summary[key] = job[key]
    return summary


def dialog_out(app):
    """The open Live dialog (message and button count), or None."""
    count = safe(lambda: int(app.open_dialog_count), 0)
    if not count:
        return None
    return {
        "open": count,
        "message": safe(lambda: str(app.current_dialog_message), ""),
        "buttons": safe(lambda: int(app.current_dialog_button_count), 0),
    }


def transport_out(song):
    loop_start = float(song.loop_start)
    loop_length = float(song.loop_length)
    return {
        "playing": bool(song.is_playing),
        "position": values.time_out(song, song.current_song_time),
        "start_marker": values.time_out(song, song.start_time),
        "tempo": number(song.tempo, 3),
        "time_signature": signature_text(song.signature_numerator, song.signature_denominator),
        "loop": {
            "on": bool(song.loop),
            "start": values.time_out(song, loop_start),
            "end": values.time_out(song, loop_start + loop_length),
            "length": number(loop_length),
        },
        "record": bool(song.record_mode),
        "session_record": bool(song.session_record),
        "metronome": bool(song.metronome),
        "back_to_arranger": bool(song.back_to_arranger),
        "count_in": safe(lambda: int(song.count_in_duration), 0),
    }


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


@command("get_status", readonly=True)
def get_status(ctx):
    """Versions, open set, transport, open dialog and active jobs."""
    song, app = ctx.song, ctx.app
    report = getattr(ctx.cs, "core_report", None) or {}
    path = str(song.file_path or "")
    return {
        "live": {
            "version": app.get_version_string(),
            "python": sys.version.split()[0],
            "cpu": number(safe(lambda: app.average_process_usage, 0.0), 3),
        },
        "script": {
            "version": core.SCRIPT_VERSION,
            "protocol": core.PROTOCOL_VERSION,
            "commands": len(core.COMMANDS),
            "handlers_failed": sorted(report.get("failed", {})),
        },
        "set": {
            "name": str(song.name or "") or None,
            "path": path or None,
            "saved": bool(path),
            "document": document_id(song),
        },
        "transport": transport_out(song),
        "dialog": dialog_out(app),
        "jobs": active_jobs(ctx.state),
    }


# ---------------------------------------------------------------------------
# get_song_overview
# ---------------------------------------------------------------------------

_MAX_DETAIL_ARRANGEMENT_CLIPS = 64


def song_summary(song, detail=False):
    summary = {
        "tempo": number(song.tempo, 3),
        "time_signature": signature_text(song.signature_numerator, song.signature_denominator),
        "key": values.NOTE_NAMES[int(song.root_note) % 12],
        "scale": str(song.scale_name),
        "swing": number(song.swing_amount, 3),
        "groove_amount": number(song.groove_amount, 3),
        "loop": {
            "on": bool(song.loop),
            "start": values.time_out(song, song.loop_start),
            "end": values.time_out(song, float(song.loop_start) + float(song.loop_length)),
        },
        "length": values.time_out(song, song.last_event_time),
    }
    if detail:
        summary["state"] = song_settings(song)
        summary["position"] = values.time_out(song, song.current_song_time)
        summary["playing"] = bool(song.is_playing)
    return summary


def song_settings(song):
    """Every setting set_song can change, as set_song names them."""
    quantization = int(song.clip_trigger_quantization)
    record_quantization = int(song.midi_recording_quantization)
    loop_start = float(song.loop_start)
    loop_length = float(song.loop_length)
    return {
        "tempo": number(song.tempo, 3),
        "time_signature": signature_text(song.signature_numerator, song.signature_denominator),
        "key": values.NOTE_NAMES[int(song.root_note) % 12],
        "scale": str(song.scale_name),
        "scale_mode": bool(song.scale_mode),
        "swing": number(song.swing_amount, 3),
        "groove_amount": number(song.groove_amount, 3),
        "metronome": bool(song.metronome),
        "loop": bool(song.loop),
        "loop_start": values.time_out(song, loop_start),
        "loop_end": values.time_out(song, loop_start + loop_length),
        "loop_length": number(loop_length),
        "punch_in": bool(song.punch_in),
        "punch_out": bool(song.punch_out),
        "launch_quantization": values.SONG_QUANTIZATION.name(quantization),
        "record_quantization": values.RECORD_QUANTIZATION.name(record_quantization),
        "follow": bool(song.view.follow_song),
        "record_mode": bool(song.record_mode),
        "session_record": bool(song.session_record),
        "arrangement_overdub": bool(song.arrangement_overdub),
        "session_automation_record": bool(song.session_automation_record),
        "link": bool(song.is_ableton_link_enabled),
        "tempo_follower": bool(song.tempo_follower_enabled),
    }


def _clip_length(clip):
    """Clip length for outputs: beats, or seconds for unwarped audio (whose length is in seconds)."""
    if clip.is_audio_clip and not safe(lambda: clip.warping, True):
        return {"length_seconds": number(clip.length, 3)}
    return {"length": number(clip.length)}


def _slot_clips(track, detail):
    clips = []
    for position, slot in enumerate(safe(lambda: list(track.clip_slots), [])):
        if not slot.has_clip:
            continue
        clip = slot.clip
        entry = {"slot": position, "name": clip.name}
        entry.update(_clip_length(clip))
        if clip.is_playing:
            entry["playing"] = True
        elif clip.is_triggered:
            entry["triggered"] = True
        if detail:
            entry["color"] = color(clip)
            entry["looping"] = bool(clip.looping)
            if clip.muted:
                entry["muted"] = True
            entry["type"] = "audio" if clip.is_audio_clip else "midi"
        clips.append(entry)
    return clips


def _arrangement(song, track, detail):
    clips = safe(lambda: refs.arrangement_clips(track), [])
    if not clips:
        return None
    out = {
        "clips": len(clips),
        "start": values.time_out(song, min(clip.start_time for clip in clips)),
        "end": values.time_out(song, max(clip.end_time for clip in clips)),
    }
    if detail:
        out["items"] = [
            {"arrangement_clip": position, "name": clip.name, "start": values.time_out(song, clip.start_time), "end": values.time_out(song, clip.end_time)}
            for position, clip in enumerate(clips[:_MAX_DETAIL_ARRANGEMENT_CLIPS])
        ]
        if len(clips) > _MAX_DETAIL_ARRANGEMENT_CLIPS:
            out["truncated"] = True
    return out


def track_overview(song, track, detail=False):
    """Compact summary of one track for get_song_overview."""
    out = refs.track_label(song, track)
    out["color"] = color(track)
    kind = out["kind"]
    if kind != "master":
        out["mute"] = bool(safe(lambda: track.mute, False))
        out["solo"] = bool(safe(lambda: track.solo, False))
    if safe(lambda: track.can_be_armed, False):
        out["arm"] = bool(track.arm)
    if safe(lambda: track.is_grouped, False):
        out["group"] = refs.track_ref(song, track.group_track)
    if detail:
        out["devices"] = [
            {"name": device.name, "class": device.class_display_name, "on": bool(safe(lambda device=device: device.is_active, True))}
            for device in track.devices
        ]
        mixer = track.mixer_device
        out["volume_db"] = db(mixer.volume)
        out["pan"] = number(mixer.panning.value, 3)
        sends = list(safe(lambda: mixer.sends, []))
        if sends:
            out["sends_db"] = dict((refs.return_letter(position), db(send)) for position, send in enumerate(sends))
        if safe(lambda: track.is_frozen, False):
            out["frozen"] = True
        if kind == "group":
            out["folded"] = bool(safe(lambda: track.fold_state, False))
    else:
        out["devices"] = [device.name for device in track.devices]
    if kind not in ("master", "return"):
        clips = _slot_clips(track, detail)
        if clips:
            out["clips"] = clips
        arrangement = _arrangement(song, track, detail)
        if arrangement:
            out["arrangement"] = arrangement
    return out


def scene_out(song, scene, position=None, detail=False):
    """Scene summary: index, name, emptiness, and tempo / signature when the scene sets them."""
    if position is None:
        position = refs.index_of(song.scenes, scene)
    out = {"scene": position, "name": scene.name, "empty": bool(scene.is_empty)}
    if scene.tempo_enabled:
        out["tempo"] = number(scene.tempo, 3)
    if scene.time_signature_enabled:
        out["time_signature"] = signature_text(scene.time_signature_numerator, scene.time_signature_denominator)
    if detail:
        out["color"] = color(scene)
        if scene.is_triggered:
            out["triggered"] = True
    return out


def locator_out(song, cue, position=None):
    if position is None:
        position = refs.index_of(refs.locators(song), cue)
    return {"locator": position, "name": cue.name, "time": values.time_out(song, cue.time)}


def selection_out(song):
    view = song.view
    out = {}
    selected = safe(lambda: view.selected_track)
    if selected is not None:
        out["track"] = refs.track_ref(song, selected)
    scene = safe(lambda: view.selected_scene)
    if scene is not None:
        out["scene"] = refs.index_of(song.scenes, scene)
    return out


@command("get_song_overview", readonly=True)
def get_song_overview(ctx, detail=False):
    """One-call project map: song settings, every track, returns, master, scenes and locators."""
    song = ctx.song
    detail = bool(detail)
    return {
        "song": song_summary(song, detail),
        "tracks": [track_overview(song, track, detail) for track in song.tracks],
        "returns": [track_overview(song, track, detail) for track in song.return_tracks],
        "master": track_overview(song, song.master_track, detail),
        "scenes": [scene_out(song, scene, position, detail) for position, scene in enumerate(song.scenes)],
        "locators": [locator_out(song, cue, position) for position, cue in enumerate(refs.locators(song))],
        "selection": selection_out(song),
    }


# ---------------------------------------------------------------------------
# undo / redo
# ---------------------------------------------------------------------------


def _steps(steps):
    if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 100:
        raise CommandError("invalid_argument", "steps must be an integer from 1 to 100, got {0!r}".format(steps))
    return steps


def _history(song, method, available, steps):
    """Undo or redo up to `steps` times; returns how many steps were taken.

    (Live's undo()/redo() return only "Undo Custom Action"-style labels, so they are not reported.)
    """
    done = 0
    for _ in range(_steps(steps)):
        if not getattr(song, available):
            break
        getattr(song, method)()
        done += 1
    return done


@command("undo", undo=False)
def undo(ctx, steps=1):
    """Step back through Live's undo history (each AbletonMCP call is one step)."""
    song = ctx.song
    if not song.can_undo:
        raise CommandError("unsupported", "Nothing to undo", hint="Live's undo history is empty")
    done = _history(song, "undo", "can_undo", steps)
    return {"undone": done, "can_undo": bool(song.can_undo), "can_redo": bool(song.can_redo)}


@command("redo", undo=False)
def redo(ctx, steps=1):
    """Step forward again through actions undone with undo."""
    song = ctx.song
    if not song.can_redo:
        raise CommandError("unsupported", "Nothing to redo", hint="Only actions undone since the last change can be redone")
    done = _history(song, "redo", "can_redo", steps)
    return {"redone": done, "can_undo": bool(song.can_undo), "can_redo": bool(song.can_redo)}


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

# Live does not expose button labels. Names are resolved only where the layout is known; the
# save prompt's order (Save / Don't Save / Cancel, left to right) is unverified on 12.4.6
# (docs/spikes.md), so callers that care should prefer indices.
# Verified on Live 12.4.6 (macOS) by pressing each index on a real "Save changes ... before closing?"
# prompt: 0 = Don't Save, 1 = Cancel, 2 = Save (docs/spikes.md). Other platforms are unverified, so
# there only indices are accepted.
SAVE_PROMPT_BUTTONS = {"dont_save": 0, "don't save": 0, "dont save": 0, "no": 0, "discard": 0, "cancel": 1, "save": 2, "yes": 2}
SAVE_PROMPT_ORDER_VERIFIED = sys.platform == "darwin"


def is_save_prompt(message):
    text = str(message or "").lower()
    return "save" in text and ("change" in text or "before" in text)


def dialog_button_index(button, message, count):
    """Index of the button to press on the open dialog, from an index or a known name."""
    if isinstance(button, bool):
        raise CommandError("invalid_argument", "button must be an index or a name, not a boolean")
    if isinstance(button, float) and button.is_integer():
        button = int(button)
    if isinstance(button, int):
        if not 0 <= button < count:
            raise CommandError("invalid_argument", "button {0} is out of range: this dialog has {1} button(s) (0..{2})".format(button, count, count - 1))
        return button
    name = str(button).strip().lower().replace("_", " ").replace("’", "'")
    if name.isdigit():
        return dialog_button_index(int(name), message, count)
    if count == 1 and name in ("ok", "okay", "close", "continue"):
        return 0
    if count == 3 and is_save_prompt(message) and SAVE_PROMPT_ORDER_VERIFIED:
        for key, index in SAVE_PROMPT_BUTTONS.items():
            if name == key.replace("_", " "):
                return index
    raise CommandError(
        "invalid_argument",
        "Cannot resolve button {0!r} for this dialog ({1} button(s)); Live does not expose button labels, so pass an index 0..{2}".format(button, count, count - 1),
        hint="Named buttons work for single-button dialogs ('ok') and Live's save prompt ('save', 'dont_save', 'cancel')",
    )


@command("respond_to_dialog", undo=False)
def respond_to_dialog(ctx, button):
    """Press a button, by index or known name, on the dialog Live is showing."""
    app = ctx.app
    dialog = dialog_out(app)
    if dialog is None:
        raise CommandError("not_found", "No dialog is open in Live", hint="get_status reports Live's open dialog and its message")
    index = dialog_button_index(button, dialog["message"], dialog["buttons"])
    app.press_current_dialog_button(index)
    return {"pressed": index, "message": dialog["message"], "buttons": dialog["buttons"]}
