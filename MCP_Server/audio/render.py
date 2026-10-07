"""Deliver a recorded bounce: copy each take, trimmed sample-exactly, into the output folder.

The Remote Script reports, per bounce track, the recorded file, the sample offset of the bounce
start (recordings carry a pre-roll) and the sample length of start..end+tail. Every output gets the
master's length, so stems and master line up sample for sample.
"""
import json
import os
import re
import time

from . import analysis
from .ffmpeg import AudioError, decode, probe, run, timeout_for

DEFAULT_ROOT = os.path.join("~", "Music", "AbletonMCP")
MANIFEST = "bounce.json"
_UNSAFE = re.compile(r'[\x00-\x1f/\\:*?"<>|]+')


def safe_filename(text, fallback="Untitled"):
    """A file-name-safe version of text (no path separators or reserved characters)."""
    cleaned = _UNSAFE.sub("-", str(text or "")).strip().strip(".").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] or fallback


def default_dir(kind, name):
    """~/Music/AbletonMCP/<kind>/<name>/ (kind: Bounces or Releases)."""
    return os.path.join(os.path.expanduser(DEFAULT_ROOT), kind, safe_filename(name))


def output_names(name, files):
    """'<name> - Master.wav' and '<name> - <stem>.wav', unique within the job."""
    base, used, names = safe_filename(name, "Bounce"), set(), []
    for entry in files:
        label = safe_filename(entry.get("stem") or entry.get("track"), "Stem")
        candidate, counter = "{0} - {1}.wav".format(base, label), 2
        while candidate.lower() in used:
            candidate = "{0} - {1} ({2}).wav".format(base, label, counter)
            counter += 1
        used.add(candidate.lower())
        names.append(candidate)
    return names


def pcm_codec(codec):
    """A little-endian WAV PCM codec with the source's sample format (lossless re-wrap)."""
    if codec and codec.startswith("pcm_"):
        return codec[:-2] + "le" if codec.endswith("be") else codec
    return "pcm_f32le"


def trim(source, destination, start_sample, count, info=None):
    """Write exactly ``count`` samples of source starting at ``start_sample`` (silence pads both ends)."""
    info = info or probe(source)
    start, count = int(round(start_sample)), int(round(count))
    if count <= 0:
        raise AudioError("Nothing to copy: {0} samples requested".format(count))
    filters = ["atrim=start_sample={0}".format(start) if start >= 0 else "adelay=delays={0}S:all=1".format(-start),
               "asetpts=N/SR/TB", "apad=whole_len={0}".format(count), "atrim=end_sample={0}".format(count)]
    folder = os.path.dirname(destination)
    os.makedirs(folder, exist_ok=True)
    partial = os.path.join(folder, ".{0}.part.wav".format(os.path.basename(destination)))
    try:
        run("ffmpeg", ["-v", "error", "-y", "-i", info["path"], "-map", "0:a:0", "-map_metadata", "-1", "-af", ",".join(filters),
                       "-c:a", pcm_codec(info["codec"]), partial], timeout=timeout_for(info["duration"], 0.5))
        os.replace(partial, destination)
    finally:
        if os.path.exists(partial):
            os.remove(partial)
    return destination


def wait_for_file(path, frames_needed, timeout=5.0, settle=0.6):
    """Probe a recording until it holds ``frames_needed`` frames or stops growing (Live may still be closing it)."""
    deadline = time.time() + timeout
    last, stable_since = None, time.time()
    while True:
        try:
            info = probe(path)
            frames = info["frames"]
            if frames is None or frames >= frames_needed or time.time() > deadline:
                return info
            if frames != last:
                last, stable_since = frames, time.time()
            elif time.time() - stable_since >= settle:
                return info
        except AudioError:
            if time.time() > deadline:
                raise
        time.sleep(0.2)


def quick_check(path):
    """Peak level, silence and dropouts of a delivered file."""
    samples, info = decode(path)
    level = analysis.levels(samples)
    peak = level["sample_peak_dbfs"]
    out = {"peak_dbfs": peak, "silent": peak is None or peak < -90.0}
    found = analysis.dropouts(samples, info["sample_rate"])
    if found:
        out["dropouts"] = found[:10]
    if level["clipped_samples"]:
        out["clipped_samples"] = level["clipped_samples"]
    return out


def deliver(job, output_dir=None):
    """Copy and trim every recorded file of a finished job; write bounce.json. Returns (outputs, manifest)."""
    files = job.get("files") or []
    master = next((entry for entry in files if entry.get("role") == "master"), None)
    if master is None:
        raise AudioError("The bounce job has no recorded master file")
    rate = float(master["sample_rate"])
    count = int(round(master["length_samples"]))
    expected = int(round(job["duration_seconds"] * rate))
    warnings = []
    if abs(count - expected) > rate * 0.005:
        warnings.append("Recorded length {0:.3f} s differs from the tempo-based {1:.3f} s (tempo change?)".format(count / rate, expected / rate))
    folder = os.path.abspath(os.path.expanduser(output_dir or job.get("output_dir") or default_dir("Bounces", job.get("name") or "Bounce")))
    outputs = []
    for entry, filename in zip(files, output_names(job.get("name") or "Bounce", files)):
        source = entry["file_path"]
        if not os.path.isfile(source):
            raise AudioError("Live's recording is missing: {0}".format(source))
        info = wait_for_file(source, int(round(entry["offset_samples"])) + count)
        if info["frames"] is not None and info["frames"] < int(round(entry["offset_samples"])) + count:
            short = int(round(entry["offset_samples"])) + count - info["frames"]
            warnings.append("{0}: recording ended {1:.1f} ms early; padded with silence".format(entry["stem"], 1000.0 * short / rate))
        destination = trim(source, os.path.join(folder, filename), entry["offset_samples"], count, info)
        record = {"stem": entry["stem"], "role": entry["role"], "path": destination, "duration_seconds": round(count / rate, 6),
                  "sample_rate": int(rate), "bit_depth": info["bit_depth"], "codec": pcm_codec(info["codec"]), "recording": source}
        if entry.get("source"):
            record["track"] = entry["source"]
        record.update(quick_check(destination))
        outputs.append(record)
    manifest = {
        "name": job.get("name"),
        "job": job.get("id"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "range": job.get("range"),
        "tempo": job.get("tempo"),
        "duration_seconds": round(count / rate, 6),
        "sample_rate": int(rate),
        "song": job.get("song"),
        "files": [dict(record, path=os.path.basename(record["path"])) for record in outputs],
        "warnings": list(job.get("warnings") or []) + warnings,
    }
    with open(os.path.join(folder, MANIFEST), "w") as handle:
        json.dump(manifest, handle, indent=2)
    return outputs, dict(manifest, folder=folder, manifest=os.path.join(folder, MANIFEST), new_warnings=warnings)


def manifest_for(path):
    """(manifest, file entry) when path is a delivered bounce file (bounce.json beside it), else (None, None)."""
    folder = os.path.dirname(os.path.abspath(os.path.expanduser(path)))
    candidate = os.path.join(folder, MANIFEST)
    if not os.path.isfile(candidate):
        return None, None
    try:
        with open(candidate) as handle:
            manifest = json.load(handle)
    except (OSError, ValueError):
        return None, None
    name = os.path.basename(path)
    entry = next((item for item in manifest.get("files") or [] if item.get("path") == name), None)
    return (manifest, entry) if entry else (None, None)


def locator_sections(manifest, duration):
    """Sections between the locators captured with a bounce, in seconds within the file."""
    start = float(manifest["range"]["start"]["beats"])
    tempo = float(manifest["tempo"])
    sections = []
    for locator in (manifest.get("song") or {}).get("locators") or []:
        seconds = (float(locator["beats"]) - start) * 60.0 / tempo
        if 0.0 <= seconds < duration:
            sections.append({"name": locator["name"], "start": round(seconds, 6), "start_bar": locator.get("bar")})
    if sections and sections[0]["start"] > 0.05:
        sections.insert(0, {"name": "(start)", "start": 0.0})
    return sections
