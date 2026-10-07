"""Locate and run ffmpeg / ffprobe with timeouts and readable errors; probe and decode audio files."""
import json
import os
import shutil
import subprocess

import numpy as np

# MCP clients often start servers with a minimal PATH, so look where package managers install too.
SEARCH_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin", "/usr/bin")
INSTALL_HINT = "Install FFmpeg (macOS: `brew install ffmpeg`) or set {0} to the binary's path."

_FOUND = {}
_ENCODERS = {}


class AudioError(Exception):
    """A problem the caller can fix: ffmpeg missing, a file unreadable, an option invalid."""


def find_tool(name):
    """Absolute path of ffmpeg or ffprobe (env ABLETON_MCP_FFMPEG / ABLETON_MCP_FFPROBE overrides)."""
    env = "ABLETON_MCP_" + name.upper()
    override = os.environ.get(env)
    if override:
        if os.path.isfile(override) and os.access(override, os.X_OK):
            return override
        raise AudioError("{0}={1!r} is not an executable file. ".format(env, override) + INSTALL_HINT.format(env))
    if name not in _FOUND:
        path = shutil.which(name)
        if not path:
            for folder in SEARCH_DIRS:
                candidate = os.path.join(folder, name)
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    path = candidate
                    break
        if not path:
            raise AudioError("{0} was not found. ".format(name) + INSTALL_HINT.format(env))
        _FOUND[name] = path
    return _FOUND[name]


def available():
    """True when both ffmpeg and ffprobe can be found."""
    try:
        find_tool("ffmpeg")
        find_tool("ffprobe")
        return True
    except AudioError:
        return False


def timeout_for(duration, per_second=1.0, base=60.0):
    """A generous subprocess timeout for processing ``duration`` seconds of audio."""
    return base + max(0.0, float(duration or 0.0)) * per_second


def _stderr_tail(stderr, lines=4):
    text = stderr.decode("utf-8", "replace") if isinstance(stderr, bytes) else (stderr or "")
    useful = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(useful[-lines:])


def run(tool, args, timeout=120.0, input_bytes=None):
    """Run ffmpeg or ffprobe; returns the CompletedProcess (stdout/stderr as bytes)."""
    command = [find_tool(tool), "-hide_banner"] + (["-nostdin"] if tool == "ffmpeg" and input_bytes is None else []) + [str(item) for item in args]
    try:
        completed = subprocess.run(command, capture_output=True, timeout=timeout, input=input_bytes)
    except subprocess.TimeoutExpired:
        raise AudioError("{0} timed out after {1:.0f}s".format(tool, timeout))
    except OSError as error:
        raise AudioError("Could not run {0}: {1}".format(tool, error))
    if completed.returncode != 0:
        raise AudioError("{0} failed: {1}".format(tool, _stderr_tail(completed.stderr) or "exit code {0}".format(completed.returncode)))
    return completed


def has_encoder(name):
    """True when this ffmpeg build has the named encoder (e.g. 'aac_at', 'libmp3lame')."""
    if name not in _ENCODERS:
        listing = run("ffmpeg", ["-encoders"], timeout=30).stdout.decode("utf-8", "replace")
        _ENCODERS[name] = any(len(line.split()) > 1 and line.split()[1] == name for line in listing.splitlines())
    return _ENCODERS[name]


def check_file(path, what="Audio file"):
    """Absolute path of an existing file (``~`` expanded), or AudioError."""
    if not path or not isinstance(path, str):
        raise AudioError("{0} path is required".format(what))
    full = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(full):
        raise AudioError("{0} not found: {1}".format(what, full))
    return full


def probe(path):
    """Format, codec, sample rate, channels, duration, frame count, bit depth, tags and artwork of a file."""
    full = check_file(path)
    raw = run("ffprobe", ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", full], timeout=30).stdout
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        raise AudioError("ffprobe returned unreadable output for {0}".format(full))
    streams = data.get("streams") or []
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not audio:
        raise AudioError("{0} has no audio stream".format(full))
    stream, container = audio[0], data.get("format") or {}
    sample_rate = int(stream.get("sample_rate") or 0)
    duration = float(stream.get("duration") or container.get("duration") or 0.0)
    frames = None
    if stream.get("duration_ts") is not None and stream.get("time_base") == "1/{0}".format(sample_rate):
        frames = int(stream["duration_ts"])
    bits = stream.get("bits_per_raw_sample") or stream.get("bits_per_sample") or None
    tags = {}
    for source in (container.get("tags") or {}, stream.get("tags") or {}):
        for key, value in source.items():
            tags.setdefault(key.lower(), value)
    return {
        "path": full,
        "container": container.get("format_name"),
        "codec": stream.get("codec_name"),
        "sample_format": stream.get("sample_fmt"),
        "sample_rate": sample_rate,
        "channels": int(stream.get("channels") or 0),
        "duration": duration,
        "frames": frames,
        "bit_depth": int(bits) if bits and str(bits).isdigit() and int(bits) > 0 else None,
        "bit_rate": int(container["bit_rate"]) if str(container.get("bit_rate", "")).isdigit() else None,
        "tags": tags,
        "artwork": any(item.get("codec_type") == "video" and (item.get("disposition") or {}).get("attached_pic") for item in streams),
    }


def decode(path, info=None):
    """Decode the first audio stream to float32 samples shaped (frames, channels), plus the probe info."""
    info = info or probe(path)
    raw = run("ffmpeg", ["-v", "error", "-i", info["path"], "-map", "0:a:0", "-f", "f32le", "-acodec", "pcm_f32le", "-"],
              timeout=timeout_for(info["duration"], 0.5)).stdout
    channels = max(1, info["channels"])
    samples = np.frombuffer(raw, dtype="<f4")
    frames = len(samples) // channels
    return samples[: frames * channels].reshape(frames, channels), info
