"""Audio files in and out: a WAV reader and writer in numpy, ffmpeg for everything else.

Samples are float64 arrays shaped (frames, channels), full scale = 1.0. The WAV reader handles PCM
16/24/32-bit and IEEE float 32/64, including WAVE_FORMAT_EXTENSIBLE headers (Live writes these).
Other formats (FLAC, AIFF, MP3) are decoded by ffmpeg when it is installed.
"""
import os
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np

FFMPEG_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin", "/usr/bin")
_PCM, _FLOAT, _EXTENSIBLE = 1, 3, 0xFFFE


class AudioFileError(Exception):
    """A file could not be read or written."""


class Audio(object):
    """Decoded audio: samples (frames, channels) float64, sample rate, and file facts."""

    __slots__ = ("samples", "rate", "path", "bit_depth", "format")

    def __init__(self, samples, rate, path=None, bit_depth=None, format=None):
        samples = np.asarray(samples, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples[:, None]
        self.samples = samples
        self.rate = int(rate)
        self.path = str(path) if path else None
        self.bit_depth = bit_depth
        self.format = format

    @property
    def frames(self):
        return int(self.samples.shape[0])

    @property
    def channels(self):
        return int(self.samples.shape[1])

    @property
    def duration(self):
        return self.frames / float(self.rate) if self.rate else 0.0

    def mono(self):
        return self.samples.mean(axis=1)

    def stereo(self):
        """(frames, 2): mono files are duplicated to both channels."""
        if self.channels == 2:
            return self.samples
        if self.channels == 1:
            return np.repeat(self.samples, 2, axis=1)
        return self.samples[:, :2]

    def slice(self, start_s=0.0, end_s=None):
        start = int(round(start_s * self.rate))
        end = self.frames if end_s is None else int(round(end_s * self.rate))
        return Audio(self.samples[max(0, start):max(0, end)], self.rate, self.path, self.bit_depth, self.format)

    def info(self):
        return {"path": self.path, "rate": self.rate, "channels": self.channels, "frames": self.frames,
                "duration": round(self.duration, 6), "bit_depth": self.bit_depth, "format": self.format}

    def __repr__(self):
        return "Audio({0} frames, {1} ch, {2} Hz{3})".format(self.frames, self.channels, self.rate,
                                                             ", " + os.path.basename(self.path) if self.path else "")


def _chunks(data):
    position = 12
    while position + 8 <= len(data):
        tag, size = struct.unpack("<4sI", data[position:position + 8])
        body = position + 8
        yield tag, body, size
        position = body + size + (size & 1)


def read_wav(path):
    """Decode a WAV file without ffmpeg (AudioFileError for anything malformed)."""
    try:
        return _read_wav(path)
    except AudioFileError:
        raise
    except (struct.error, ValueError, ZeroDivisionError, IndexError) as error:
        raise AudioFileError("{0} is not a readable WAV file: {1}".format(path, error))


def _read_wav(path):
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise AudioFileError("Cannot read {0}: {1}".format(path, error))
    if len(data) < 12 or data[:4] not in (b"RIFF", b"RF64") or data[8:12] != b"WAVE":
        raise AudioFileError("{0} is not a WAV file".format(path))
    fmt = None
    frames = None
    for tag, body, size in _chunks(data):
        if tag == b"fmt ":
            code, channels, rate, _, block, bits = struct.unpack("<HHIIHH", data[body:body + 16])
            if channels <= 0 or block <= 0 or rate <= 0:
                raise AudioFileError("{0} has an invalid fmt chunk ({1} channels, block {2}, {3} Hz)".format(path, channels, block, rate))
            if code == _EXTENSIBLE and size >= 40:
                code = struct.unpack("<H", data[body + 24:body + 26])[0]
            fmt = (code, channels, rate, block, bits)
        elif tag == b"data" and fmt is not None:
            code, channels, rate, block, bits = fmt
            size = min(size, len(data) - body)
            raw = data[body:body + size - size % block]
            frames = _decode(raw, code, channels, bits)
            break
    if fmt is None or frames is None:
        raise AudioFileError("{0} has no fmt or data chunk".format(path))
    code, channels, rate, block, bits = fmt
    return Audio(frames, rate, path, bit_depth=bits, format="float" if code == _FLOAT else "pcm")


def _decode(raw, code, channels, bits):
    if code == _FLOAT and bits in (32, 64):
        values = np.frombuffer(raw, dtype="<f4" if bits == 32 else "<f8").astype(np.float64)
    elif code == _PCM and bits == 16:
        values = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif code == _PCM and bits == 24:
        triples = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        ints = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
        ints = np.where(ints >= 1 << 23, ints - (1 << 24), ints)
        values = ints.astype(np.float64) / float(1 << 23)
    elif code == _PCM and bits == 32:
        values = np.frombuffer(raw, dtype="<i4").astype(np.float64) / float(1 << 31)
    elif code == _PCM and bits == 8:
        values = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    else:
        raise AudioFileError("Unsupported WAV encoding (format {0}, {1} bits)".format(code, bits))
    return values.reshape(-1, channels)


def find_ffmpeg(name="ffmpeg"):
    override = os.environ.get("EARS_" + name.upper()) or os.environ.get("ABLETON_MCP_" + name.upper())
    if override and os.path.isfile(override):
        return override
    found = shutil.which(name)
    if found:
        return found
    for folder in FFMPEG_DIRS:
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _probe(path):
    ffprobe = find_ffmpeg("ffprobe")
    if not ffprobe:
        raise AudioFileError("Reading {0} needs ffprobe (brew install ffmpeg)".format(path))
    completed = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries",
                                "stream=sample_rate,channels,bits_per_raw_sample,bits_per_sample", "-of", "default=nw=1",
                                str(path)], capture_output=True, timeout=60)
    facts = {}
    for line in completed.stdout.decode("utf-8", "replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            facts[key.strip()] = value.strip()
    if "sample_rate" not in facts:
        raise AudioFileError("ffprobe found no audio stream in {0}".format(path))
    bits = None
    for key in ("bits_per_raw_sample", "bits_per_sample"):
        try:
            bits = int(facts.get(key)) or bits
        except (TypeError, ValueError):
            pass
    return int(facts["sample_rate"]), int(facts.get("channels") or 2), bits


def read_ffmpeg(path):
    ffmpeg = find_ffmpeg("ffmpeg")
    if not ffmpeg:
        raise AudioFileError("Reading {0} needs ffmpeg (brew install ffmpeg)".format(path))
    rate, channels, bits = _probe(path)
    completed = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "f64le", "-acodec", "pcm_f64le", "-"],
                               capture_output=True, timeout=600)
    if completed.returncode != 0:
        raise AudioFileError("ffmpeg could not decode {0}: {1}".format(path, completed.stderr.decode("utf-8", "replace")[-300:]))
    values = np.frombuffer(completed.stdout, dtype="<f8")
    return Audio(values[: len(values) - len(values) % channels].reshape(-1, channels), rate, path, bits, "decoded")


def read(path):
    """Decode any audio file: WAV natively, anything else through ffmpeg."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise AudioFileError("No such audio file: {0}".format(path))
    if path.suffix.lower() in (".wav", ".wave"):
        try:
            return read_wav(path)
        except AudioFileError:
            if find_ffmpeg():
                return read_ffmpeg(path)
            raise
    return read_ffmpeg(path)


def write_wav(path, samples, rate, bit_depth=32):
    """Write a WAV file: bit_depth 32 = IEEE float (lossless for analysis), 24 or 16 = PCM (clipped)."""
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim == 1:
        samples = samples[:, None]
    frames, channels = samples.shape
    if bit_depth == 32:
        code, payload = _FLOAT, samples.astype("<f4").tobytes()
    elif bit_depth == 24:
        ints = np.clip(np.round(samples * (1 << 23)), -(1 << 23), (1 << 23) - 1).astype("<i4").reshape(-1)
        payload = np.stack([(ints & 0xFF), (ints >> 8) & 0xFF, (ints >> 16) & 0xFF], axis=1).astype(np.uint8).tobytes()
        code = _PCM
    elif bit_depth == 16:
        code, payload = _PCM, np.clip(np.round(samples * 32768.0), -32768, 32767).astype("<i2").tobytes()
    else:
        raise AudioFileError("bit_depth must be 16, 24 or 32 (float)")
    block = channels * bit_depth // 8
    header = struct.pack("<4sI4s", b"RIFF", 36 + len(payload) + (len(payload) & 1), b"WAVE")
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, code, channels, int(rate), int(rate) * block, block, bit_depth)
    data = struct.pack("<4sI", b"data", len(payload)) + payload + (b"\0" if len(payload) & 1 else b"")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(header + fmt + data)
    os.replace(tmp, path)
    return path


def write(path, audio, bit_depth=32):
    return write_wav(path, audio.samples, audio.rate, bit_depth)


def db(value, floor=-200.0):
    """20*log10 of an amplitude, floored (never -inf, so results stay JSON-safe)."""
    value = float(value)
    return 20.0 * np.log10(value) if value > 10 ** (floor / 20.0) else floor


def power_db(value, floor=-200.0):
    value = float(value)
    return 10.0 * np.log10(value) if value > 10 ** (floor / 10.0) else floor


def rms(samples):
    samples = np.asarray(samples, dtype=np.float64)
    return float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0


def peak(samples):
    samples = np.asarray(samples, dtype=np.float64)
    return float(np.max(np.abs(samples))) if samples.size else 0.0


def match_length(signals):
    """Zero-pad (frames, ch) arrays to the longest one."""
    longest = max(signal.shape[0] for signal in signals)
    out = []
    for signal in signals:
        if signal.shape[0] < longest:
            signal = np.vstack([signal, np.zeros((longest - signal.shape[0], signal.shape[1]))])
        out.append(signal)
    return out


def mix(audios):
    """Sum several Audio objects (same rate), padding to the longest, as stereo."""
    if not audios:
        raise AudioFileError("Nothing to mix")
    rates = set(audio.rate for audio in audios)
    if len(rates) > 1:
        raise AudioFileError("Cannot mix different sample rates: {0}".format(sorted(rates)))
    total = np.sum(match_length([audio.stereo() for audio in audios]), axis=0)
    return Audio(total, audios[0].rate)
