"""meter: measure what the Mac is playing, in memory, and keep only numbers (PRD section 11.2).

The audio comes from the audio interface's loopback inputs (what the Mac plays: Live, or the Spotify app)
through PortAudio into a numpy buffer, is measured, and is dropped. For an external source:

- M1. No audio reaches disk, a cache, a log or a result; only derived numbers do. This module has no file
  writer, logs nothing about the signal, and returns plain numbers.
- M2. The path computes measurements only; nothing here can send audio anywhere.
- M4. The absolute level is uncalibrated (the player's volume and normalisation decide it), so an external
  result carries no absolute loudness figure: only the level-independent profile (ears.profile).

On this Mac the loopback is the Scarlett Solo 4th Gen's inputs 3-4, read at the device's own sample rate
while Live keeps using the interface (verified 2026-10-08: a -30 dBFS tone read back at -30.000 dBFS peak).
EARS_METER_DEVICE (part of a device name) and EARS_METER_CHANNELS ("3,4") override the choice.
"""
import os
import sys
import threading
import time

import numpy as np

from . import loudness
from . import profile as profiles
from .audio import Audio

DEVICE_ENV = "EARS_METER_DEVICE"
CHANNELS_ENV = "EARS_METER_CHANNELS"
SILENCE_DBFS = -100.0          # the loopback carries exact digital zeros when nothing plays
SIGNAL_DBFS = -90.0            # where a track's audio is taken to start
WINDOW_SECONDS = 10.0
FULL_LU = 3.0                  # windows within this of the loudest are a track's full sections ...
SPARSE_LU = 12.0               # ... down to this, its sparse ones; quieter windows (intros, breaks) are neither
SOURCES = ("external", "live", "file")


class MeterError(Exception):
    """The meter cannot measure (no device, no signal, something else playing)."""


def _dbfs(samples):
    if not len(samples):
        return -240.0
    peak = float(np.max(np.abs(samples)))
    return 20.0 * np.log10(peak) if peak > 0.0 else -240.0


class Recording(object):
    """Samples read into memory: (frames, 2) float32, the rate, and how many blocks overflowed."""

    __slots__ = ("samples", "rate", "dropouts")

    def __init__(self, samples, rate, dropouts=0):
        self.samples = samples
        self.rate = int(rate)
        self.dropouts = int(dropouts)

    @property
    def seconds(self):
        return len(self.samples) / float(self.rate) if self.rate else 0.0


class LoopbackInput(object):
    """The interface's loopback inputs, read with PortAudio at the device's nominal rate.

    The stream never changes the device's sample rate or buffer size (Live keeps the device) and refuses
    to open if a rate conversion would be needed, so what is read is what the Mac played.
    """

    def __init__(self, device=None, channels=None):
        try:
            import sounddevice
        except (ImportError, OSError) as error:   # OSError: PortAudio itself is missing
            raise MeterError("PortAudio is not available ({0}); install the sounddevice package".format(error))
        self._sd = sounddevice
        self.index, self.info = self._find(device or os.environ.get(DEVICE_ENV))
        self.channels = self._channels(channels or os.environ.get(CHANNELS_ENV))
        if max(self.channels) > self.info["max_input_channels"]:
            raise MeterError("{0} has {1} inputs; channels {2} do not exist".format(
                self.info["name"], self.info["max_input_channels"], self.channels))
        self.rate = int(self.info["default_samplerate"])

    def _find(self, wanted):
        devices = list(self._sd.query_devices())
        inputs = [(index, item) for index, item in enumerate(devices) if item["max_input_channels"] > 0]
        if wanted:
            for index, item in inputs:
                if str(wanted).lower() in item["name"].lower():
                    return index, item
            raise MeterError("No input device matches {0!r}; inputs: {1}".format(wanted, ", ".join(item["name"] for _, item in inputs)))
        for index, item in inputs:   # a 4th Gen Scarlett: loopback on the inputs after the analogue ones
            if "scarlett" in item["name"].lower() and item["max_input_channels"] >= 4:
                return index, item
        for index, item in inputs:
            if any(word in item["name"].lower() for word in ("blackhole", "loopback", "soundflower")):
                return index, item
        raise MeterError("No loopback input found (a 4th Gen Scarlett or a virtual device such as BlackHole); "
                         "set {0} to the device name".format(DEVICE_ENV))

    def _channels(self, value):
        if value:
            items = value if isinstance(value, (list, tuple)) else str(value).replace(" ", "").split(",")
            channels = tuple(int(item) for item in items)
        elif "scarlett" in self.info["name"].lower() and self.info["max_input_channels"] >= 4:
            channels = (self.info["max_input_channels"] - 1, self.info["max_input_channels"])   # Solo and 2i2: 3-4
        else:
            channels = (1, 2)
        if len(channels) != 2 or min(channels) < 1:
            raise MeterError("channels must be two 1-based inputs, such as 3,4")
        return channels

    def describe(self):
        return {"device": self.info["name"], "channels": list(self.channels), "rate": self.rate}

    def record(self, seconds, stop=None, progress=None, started=None):
        """Read `seconds` into memory. stop: a threading.Event that ends early; progress(seconds_read) is called
        about every 0.2 s and ends early when it returns False; started() is called once the stream runs."""
        sd = self._sd
        frames = max(1, int(round(float(seconds) * self.rate)))
        buffer = np.zeros((frames, 2), dtype=np.float32)
        state = {"position": 0, "dropouts": 0}
        finished = threading.Event()
        first, second = self.channels[0] - 1, self.channels[1] - 1

        def callback(indata, count, info, status):
            if status.input_overflow:
                state["dropouts"] += 1
            position = state["position"]
            n = min(count, frames - position)
            if n > 0:
                block = indata[:n] if indata.shape[1] == 2 else indata[:n, [first, second]]
                buffer[position:position + n] = block
                state["position"] = position + n
            if state["position"] >= frames:
                raise sd.CallbackStop

        if sys.platform == "darwin":
            extra = sd.CoreAudioSettings(channel_map=[first, second], change_device_parameters=False,
                                         fail_if_conversion_required=True)
            width = 2
        else:
            extra, width = None, max(self.channels)
        try:
            stream = sd.InputStream(device=self.index, channels=width, samplerate=self.rate, dtype="float32",
                                    blocksize=1024, extra_settings=extra, callback=callback,
                                    finished_callback=finished.set)
        except Exception as error:   # PortAudioError and friends
            raise MeterError("Cannot open {0} at {1} Hz: {2}".format(self.info["name"], self.rate, error))
        with stream:
            if started:
                started()
            while not finished.wait(0.2):
                if stop is not None and stop.is_set():
                    break
                if progress is not None and progress(state["position"] / float(self.rate)) is False:
                    break
        return Recording(buffer[:state["position"]], self.rate, state["dropouts"])


class ArrayInput(object):
    """An input that plays back an array instead of a device (tests and synthetic calibration only)."""

    def __init__(self, samples, rate, name="array"):
        samples = np.asarray(samples, dtype=np.float32)
        self.samples = samples if samples.ndim == 2 else np.column_stack([samples, samples])
        self.rate = int(rate)
        self.position = 0
        self.name = name

    def describe(self):
        return {"device": self.name, "channels": [1, 2], "rate": self.rate}

    def record(self, seconds, stop=None, progress=None, started=None):
        if started:
            started()
        frames = int(round(float(seconds) * self.rate))
        end = min(len(self.samples), self.position + frames)
        step = max(1, int(0.2 * self.rate))
        position = self.position
        while position < end:
            if stop is not None and stop.is_set():
                break
            position = min(end, position + step)
            if progress is not None and progress((position - self.position) / float(self.rate)) is False:
                break
        chunk = self.samples[self.position:position].copy()
        self.position = position
        return Recording(chunk, self.rate)


def check_silent(source, seconds=0.5):
    """Raise MeterError unless the input carries digital silence (nothing else is playing into it)."""
    recording = source.record(seconds)
    level = _dbfs(recording.samples)
    del recording
    if level > SILENCE_DBFS:
        raise MeterError("Something is already playing into {0} ({1:.0f} dBFS): stop Live and other players "
                         "before measuring".format(source.describe()["device"], level))
    return level


def signal_start(samples, threshold_dbfs=SIGNAL_DBFS):
    """Index of the first frame above the threshold (the start of the audio after digital silence), or None."""
    hits = np.flatnonzero(np.max(np.abs(samples), axis=1) > 10.0 ** (threshold_dbfs / 20.0)) if len(samples) else []
    return int(hits[0]) if len(hits) else None


def windows(audio, window=WINDOW_SECONDS):
    """Loudness of consecutive windows relative to the loudest (LU; never absolute), labelled full, sparse or
    quiet. A last window shorter than half a window is merged into the one before."""
    rate = audio.rate
    size = int(round(window * rate))
    bounds = list(range(0, audio.frames, size))
    if len(bounds) > 1 and audio.frames - bounds[-1] < size // 2:
        bounds.pop()
    out = []
    for i, start in enumerate(bounds):
        end = bounds[i + 1] if i + 1 < len(bounds) else audio.frames
        value = loudness.integrated(audio.samples[start:end], rate)
        out.append({"start": round(start / float(rate), 2), "end": round(end / float(rate), 2), "_lufs": value})
    loudest = max((item["_lufs"] for item in out), default=loudness.SILENCE)
    for item in out:
        value = item.pop("_lufs")
        relative = value - loudest if value > loudness.SILENCE + 1 else None
        item["loudness_lu"] = round(relative, 1) if relative is not None else None
        if relative is None or relative < -SPARSE_LU:
            item["kind"] = "quiet"
        elif relative >= -FULL_LU:
            item["kind"] = "full"
        else:
            item["kind"] = "sparse"
    return out


def _spans(items, kind):
    spans = []
    for item in items:
        if item["kind"] != kind:
            continue
        if spans and abs(spans[-1][1] - item["start"]) < 1e-6:
            spans[-1][1] = item["end"]
        else:
            spans.append([item["start"], item["end"]])
    return spans


def _cut(audio, spans):
    parts = [audio.samples[int(round(a * audio.rate)):int(round(b * audio.rate))] for a, b in spans]
    return Audio(np.concatenate(parts) if parts else np.zeros((0, 2)), audio.rate)


def measure_sections(audio, source, sections=None, a4_hz=440.0, crossover_hz=120.0, window=WINDOW_SECONDS):
    """Profiles of a whole recording: "track", "full" and "sparse" (from the windows), plus named sections.

    sections: {name: [start_s, end_s]} measured as given (times from the start of the audio).
    An external source keeps no absolute figure (M4).
    """
    if source not in SOURCES:
        raise MeterError("source must be one of {0}".format(", ".join(SOURCES)))
    absolute = source != "external"
    items = windows(audio, window)
    out = {"windows": items, "sections": {}}
    out["sections"]["track"] = dict(profiles.profile(audio, a4_hz, crossover_hz, absolute), span=[[0.0, round(audio.duration, 2)]])
    for kind in ("full", "sparse"):
        spans = _spans(items, kind)
        if spans:
            part = _cut(audio, spans)
            if part.duration >= 4.0:
                out["sections"][kind] = dict(profiles.profile(part, a4_hz, crossover_hz, absolute), span=spans)
    for name, (start, end) in (sections or {}).items():
        part = _cut(audio, [[float(start), float(end)]])
        if part.duration > 0.5:
            out["sections"][str(name)] = dict(profiles.profile(part, a4_hz, crossover_hz, absolute), span=[[float(start), float(end)]])
    if not absolute:
        for name, values in out["sections"].items():
            out["sections"][name] = profiles.shape_only(values)
    return out


def meter(source, seconds, kind="external", a4_hz=440.0, crossover_hz=120.0, stop=None, progress=None, trim=True):
    """Record `seconds` from `source` into memory, measure, drop the samples, return numbers only.

    kind: "external" (a streaming service: no absolute figures) or "live" (Live's output through the same
    loopback, M3). trim drops leading digital silence (playback that starts a moment late).
    """
    if kind not in ("external", "live"):
        raise MeterError("kind must be external or live")
    started = time.time()
    recording = source.record(seconds, stop=stop, progress=progress)
    samples, rate, dropouts = recording.samples, recording.rate, recording.dropouts
    del recording
    start = signal_start(samples) if trim else 0
    if start is None:
        raise MeterError("No signal on {0}: nothing played during the measurement".format(source.describe()["device"]))
    audio = Audio(samples[start:], rate)
    del samples
    values = profiles.profile(audio, a4_hz, crossover_hz, absolute=kind != "external")
    result = {"source": kind, "chain": source.describe(), "seconds": round(audio.duration, 2),
              "lead_in_seconds": round(start / float(rate), 3), "dropouts": dropouts,
              "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "elapsed": round(time.time() - started, 1),
              "profile": profiles.shape_only(values) if kind == "external" else values}
    del audio
    return result
