"""WS-E: bounce (real-time render), audio analysis and release packaging (docs/PRD.md section 7.9)."""
import json
import os
import threading
import time

from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError

from ..app import call, tool
from .references import loopback_busy
from ..audio import analysis, release, render
from ..audio.ffmpeg import AudioError, check_file, find_tool, probe
from ..audio.images import spectrogram_png, waveform_png

MAX_WAIT = 50.0
POLL_SECONDS = 0.5
RUNNING = ("route", "arm", "go", "starting", "recording", "finalizing", "verifying", "aborting")
_DELIVERY = threading.Lock()


def _audio_errors(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except AudioError as error:
        raise ToolError(str(error))


def _summary(job):
    """Compact view of a Remote Script bounce job for the agent."""
    phase = job.get("phase")
    if phase == "idle":
        out = {"phase": "idle", "hint": "No bounce yet: call bounce."}
        if job.get("removed_tracks"):
            out["removed_tracks"] = job["removed_tracks"]
        return out
    out = {"job": job.get("id"), "phase": phase, "name": job.get("name")}
    span = job.get("range") or {}
    if span:
        out["range"] = {"start": span.get("start"), "end": span.get("end"), "tail_beats": span.get("tail_beats")}
    out["duration_seconds"] = job.get("duration_seconds")
    if phase in RUNNING:
        out["progress"] = job.get("progress", 0.0)
        out["eta_seconds"] = job.get("eta_seconds")
        if job.get("position") is not None:
            out["position_beats"] = job["position"]
    out["stems"] = job.get("stems") or []
    for key in ("skipped", "warnings", "error", "removed_tracks"):
        if job.get(key):
            out[key] = job[key]
    outputs = job.get("outputs")
    if outputs:
        out.update(outputs)
    elif phase == "recorded":
        out["hint"] = "Recorded; call get_bounce_status to copy the files."
    elif phase in RUNNING:
        out["hint"] = "Poll get_bounce_status(wait=50) until phase is done."
    return out


def _deliver(job_id):
    """Copy and trim the recordings of a finished job, then remove its temporary tracks."""
    with _DELIVERY:
        job = call("bounce_status")
        if job.get("id") != job_id or job.get("phase") != "recorded":
            return _summary(job)
        try:
            files, manifest = render.deliver(job)
        except AudioError as error:
            raise ToolError("The bounce recorded, but copying its files failed: {0}. Live's recordings are kept; "
                            "fix this and call get_bounce_status again, or cancel_bounce.".format(error))
        keep = ("stem", "path", "duration_seconds", "sample_rate", "bit_depth", "peak_dbfs", "silent", "dropouts", "clipped_samples")
        outputs = {"folder": manifest["folder"], "manifest": manifest["manifest"],
                   "files": [dict((key, item[key]) for key in keep if key in item) for item in files]}
        if manifest["new_warnings"]:
            outputs["delivery_warnings"] = manifest["new_warnings"]
        return _summary(call("bounce_cleanup", job_id=job_id, outputs=outputs))


@tool(destructive=True)
def bounce(start: float | str = 0, end: float | str | None = None, tail: float | str = "2 s",
           stems: list[int | str] | str | None = None, include_returns: bool = False,
           name: str | None = None, output_dir: str | None = None) -> dict:
    """Render the arrangement to WAV in real time (resampling inside Live): the master plus optional stems.

    start/end: beats, "bar.beat.sixteenth" or a locator name; end defaults to the last arrangement event
    rounded up to a bar. tail: time after end for reverb and delay tails: beats, "1 bar", or seconds ("2 s").
    stems: "all" (unmuted tracks with audio), or track names or indices ("return:A" works); include_returns
    adds every return. Files go to output_dir (default ~/Music/AbletonMCP/Bounces/<name>/) as
    "<name> - Master.wav" and "<name> - <stem>.wav", replacing same-named files. The song plays audibly;
    transport, loop, metronome and arm states are restored. Returns a job: poll get_bounce_status(wait=50)
    until phase is "done" (polling is required: it delivers the files and removes the temporary tracks).
    Example: bounce(stems=["Drums", "Bass"], name="Demo").
    """
    try:
        find_tool("ffmpeg")
        find_tool("ffprobe")
    except AudioError as error:
        raise ToolError("{0} Bounces need it to deliver their files.".format(error))
    if output_dir:
        output_dir = os.path.abspath(os.path.expanduser(output_dir))
    busy = loopback_busy()
    if busy:
        raise ToolError(busy)
    job = call("bounce_start", start=start, end=end, tail=tail, stems=stems, include_returns=include_returns,
               name=name, output_dir=output_dir, timeout=40)
    out = _summary(job)
    out["output_dir"] = output_dir or render.default_dir("Bounces", job.get("name") or "Bounce")
    return out


@tool(idempotent=True)
def get_bounce_status(wait: float = 0) -> dict:
    """Progress of the current bounce; when recording ends, deliver the files and return their paths.

    wait: seconds (0-50) to long-poll until the bounce finishes. While running: phase, progress (0-1) and
    eta_seconds. When done: folder, manifest (bounce.json) and files [{stem, path, duration_seconds,
    peak_dbfs, silent}]; delivery trims each take sample-exactly to the range and removes the temporary
    "[bounce]" tracks. failed carries error; cancelled after cancel_bounce. Next: analyze_audio(path).
    """
    deadline = time.time() + max(0.0, min(MAX_WAIT, float(wait or 0)))
    while True:
        job = call("bounce_status")
        phase = job.get("phase")
        if phase == "recorded":
            return _deliver(job["id"])
        if phase not in RUNNING or time.time() >= deadline:
            return _summary(job)
        time.sleep(min(POLL_SECONDS, max(0.05, deadline - time.time())))


@tool(idempotent=True)
def cancel_bounce() -> dict:
    """Cancel a running bounce: recording stops, transport and arm states are restored, and the temporary
    "[bounce]" tracks are removed. With no bounce running, removes leftover "[bounce]" tracks."""
    job = call("bounce_cancel")
    deadline = time.time() + 5.0
    while job.get("phase") == "aborting" and time.time() < deadline:
        time.sleep(0.2)
        job = call("bounce_status")
    return _summary(job)


def _live_locator_sections(duration):
    """Sections from Live's locators, assuming the file starts at the beginning of the arrangement."""
    try:
        info = call("bounce_song_info")
    except ToolError as error:
        raise ToolError("sections='locators' needs a bounced file (bounce.json beside it) or a running Live: {0}".format(error))
    tempo = float(info["tempo"])
    sections = [{"name": item["name"], "start": float(item["beats"]) * 60.0 / tempo, "start_bar": item.get("bar")}
                for item in info.get("locators") or [] if float(item["beats"]) * 60.0 / tempo < duration]
    if sections and sections[0]["start"] > 0.05:
        sections.insert(0, {"name": "(start)", "start": 0.0})
    return sections


@tool(read_only=True)
def analyze_audio(path: str | None = None, sections: list[dict] | str | None = None, images: bool = False,
                  take: str | None = None, strict: bool = False, spec: str | None = None) -> list | dict:
    """Measure audio so you can judge a mix without hearing it: a file (path) or a listening-loop take.

    path: loudness (LUFS, LU, dBTP), levels, stereo, spectrum (% per band), a loudness curve, dropouts and notes;
    sections: "locators" or [{name, start, end}] in seconds. take (id or "latest", from capture): the spec's
    checks on tier sums T1..T5 (game-style looping): loudness -14 LUFS / -1 dBTP, key, mono sub, stems+returns
    cancel the mix, tempo consistency; reports tier ladder, masking, analyser bands, phone survival.
    strict adds delivery-file checks (duration, seam, start, 48 kHz/24-bit). images=True adds two PNGs.
    """
    if take is not None:
        from .listening import take_report
        return take_report(take, strict=strict, images=images, spec=spec)
    if not path:
        raise ToolError("Give path (an audio file) or take (a listening-loop take id)")
    full = _audio_errors(check_file, path)
    chosen, by_locators = None, isinstance(sections, str)
    if by_locators:
        if sections.strip().lower() != "locators":
            raise ToolError("sections must be 'locators' or a list of {name, start, end} in seconds")
        duration = _audio_errors(probe, full)["duration"]
        manifest, _ = render.manifest_for(full)
        chosen = render.locator_sections(manifest, duration) if manifest else _live_locator_sections(duration)
    elif sections:
        chosen = sections
    result = _audio_errors(analysis.analyze, full, chosen)
    if by_locators and not chosen:
        result["notes"].append("No locators fall inside this file, so there are no sections.")
    if not images:
        return result
    pictures = [Image(data=_audio_errors(spectrogram_png, full), format="png"),
                Image(data=_audio_errors(waveform_png, full), format="png")]
    result["images"] = ["spectrogram (log frequency, dBFS)", "waveform (peak, one lane per channel)"]
    return [json.dumps(result, separators=(",", ":")), *pictures]


def _bounce_live_info(source):
    manifest, _ = render.manifest_for(source)
    song = (manifest or {}).get("song")
    if song:
        info = dict((key, song.get(key)) for key in ("tempo", "time_signature", "key", "scale", "set_name"))
        info["from"] = "bounce"
        return info
    try:
        song = call("bounce_song_info")
    except ToolError:
        return None
    info = dict((key, song.get(key)) for key in ("tempo", "time_signature", "key", "scale", "set_name"))
    info["from"] = "live"
    return info


@tool(destructive=True)
def create_release(source: str, title: str, artist: str, album: str | None = None, year: int | str | None = None,
                   genre: str | None = None, track_number: int | None = None, artwork: str | None = None,
                   target_lufs: float = -14.0, true_peak: float = -1.0, formats: list[str] | None = None,
                   output_dir: str | None = None, stems: list[str] | str | None = None) -> dict:
    """Master and package a finished song: normalise a bounced master, encode, tag, embed artwork, write release.json.

    Loudness goes to target_lufs (-14 for streaming) with true peak at most true_peak dBTP: linear gain when
    peaks allow, else a 4x-oversampled true-peak limiter. formats (default all): wav24, wav16 (triangular
    dither), flac (24-bit), mp3 (320 kbps CBR), aac (256 kbps .m4a). artwork: JPEG or PNG, embedded in
    FLAC/MP3/M4A. stems: "auto" (the bounce's other files) or paths, copied unprocessed to Stems/. Output:
    ~/Music/AbletonMCP/Releases/<artist> - <title>/, replacing same-named files. release.json holds tempo,
    key, loudness per file and sha256 checksums.
    """
    live_info = _bounce_live_info(os.path.abspath(os.path.expanduser(source))) if source else None
    result = _audio_errors(release.create_release, source, title, artist, album=album, year=year, genre=genre,
                           track_number=track_number, artwork=artwork, target_lufs=target_lufs, true_peak=true_peak,
                           formats=formats, output_dir=output_dir, stems=stems, live_info=live_info)
    files = [{"format": item["format"], "path": os.path.join(result["folder"], item["file"]), "duration_seconds": item["duration_seconds"],
              "integrated_lufs": item["integrated_lufs"], "true_peak_dbtp": item["true_peak_dbtp"]} for item in result["files"]]
    out = {"folder": result["folder"], "manifest": result["manifest"], "mastering": result["mastering"], "files": files,
           "artwork": bool(result["artwork"]), "stems": len(result["stems"]), "live": live_info}
    if result["warnings"]:
        out["warnings"] = result["warnings"]
    return out
