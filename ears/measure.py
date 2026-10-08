"""Spectral and perceptual measurements for the measurement ear (PRD section 8).

Every function takes an `ears.audio.Audio` (samples float64 shaped (frames, channels), full scale = 1.0),
or for `masking` a dict of them, and returns plain Python values that serialise to JSON as they are:
floats, ints, strings, lists and dicts. Never numpy scalars or arrays, never inf or nan. The orchestration
that turns these numbers into pass/fail checks lives elsewhere; nothing here knows about specs or takes.

Conventions
  level   dB relative to full scale of the mean square: 10*log10(mean(x**2)). A full-scale sine reads
          -3.01 dB and a sine of amplitude 0.5 reads -9.03 dB (the convention of MCP_Server/audio/analysis.py).
          Anything quieter than -200 dB reads -200.0, so silence never produces -inf.
  share   percent, 0..100: band_levels "share", masking "overlap_share", phone "survival_share". The one exception is
          grid_stats "on_grid_share", a fraction 0..1 (ears/analyze.py prints it with {:.0%}).
  time    seconds. Frequencies are Hz.
  stereo  measurements that need one channel use the mono mix 0.5*(L+R) (`Audio.mono`); DC is excluded
          from every spectral measurement.

Speed: a 30 s stereo stem takes about 0.4 s for all functions together (FFT based; the few filters in mono_sub,
phone and the onset refinement run once over the signal), so a take of about ten stems takes a few seconds.
"""
import math

import numpy as np
from scipy import fft as sp_fft
from scipy import ndimage
from scipy import signal as sp_signal

from .audio import Audio

FLOOR_DB = -200.0
_TINY_POWER = 10.0 ** (FLOOR_DB / 10.0)

# (name, low Hz, high Hz); high None runs to Nyquist. Same bands as MCP_Server/audio/analysis.py.
DEFAULT_BANDS = (("sub", 0.0, 60.0), ("low", 60.0, 250.0), ("low_mid", 250.0, 2000.0),
                 ("high_mid", 2000.0, 6000.0), ("high", 6000.0, None))

# IEC 61260 nominal one-third-octave centres; the exact centres are 1000 * 10**(n/10) Hz.
THIRD_OCTAVE_CENTERS = (25.0, 31.5, 40.0, 50.0, 63.0, 80.0, 100.0, 125.0, 160.0, 200.0, 250.0, 315.0, 400.0, 500.0,
                        630.0, 800.0, 1000.0, 1250.0, 1600.0, 2000.0, 2500.0, 3150.0, 4000.0, 5000.0, 6300.0,
                        8000.0, 10000.0, 12500.0, 16000.0, 20000.0)

# The game's Web Audio AnalyserNode as the soundtrack requirements define it (specs/nova.spec.json "analyser").
DEFAULT_ANALYSER = {
    "fft_size": 2048,
    "smoothing": 0.5,
    "min_db": -90.0,
    "max_db": -20.0,
    "bands": {"sub": (20.0, 80.0), "low_mid": (80.0, 500.0), "high_mid": (500.0, 4000.0), "treble": (4000.0, 10000.0)},
    "attack_ms": 20.0,
    "release_ms": 200.0,
    "frame_rate": 60.0,
}

MASKING_LOW_HZ = 25.0
MASKING_HIGH_HZ = 16000.0

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
# Krumhansl-Kessler (1982) probe-tone profiles, tonic first.
KEY_PROFILES = {
    "major": (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88),
    "minor": (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db(power):
    """10*log10 of a power (mean square), floored at -200 dB, as a Python float."""
    power = float(power)
    return 10.0 * math.log10(power) if power > _TINY_POWER else FLOOR_DB


def _samples(audio):
    """(frames, channels) float64 without nan or inf (a corrupt decode must not poison every number)."""
    samples = np.asarray(audio.samples, dtype=np.float64)
    if samples.ndim == 1:
        samples = samples[:, None]
    if samples.size and not np.isfinite(samples.sum()):
        samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
    return samples


def _mono(audio):
    samples = _samples(audio)
    return samples.mean(axis=1) if samples.shape[1] > 1 else samples[:, 0].copy()


def _stereo(audio):
    """(frames, 2): mono is duplicated, extra channels beyond the first two are ignored."""
    samples = _samples(audio)
    if samples.shape[1] == 1:
        return np.repeat(samples, 2, axis=1)
    return samples[:, :2]


def _pow2_floor(n):
    return 1 << max(0, int(n).bit_length() - 1)


def _pow2_ceil(n):
    return 1 << max(0, int(n - 1).bit_length())


def _welch_power(x, rate, nperseg=32768):
    """Welch average of the one-sided power spectrum of `x`.

    Returns (freqs, p): p[k] is the mean-square power that falls in bin k, so p.sum() is the signal's mean
    square without DC (a Hann window, 50% overlap, per-segment mean removed). A silent or tiny signal gives
    zeros.
    """
    n = len(x)
    if n < 64 or not np.any(x):
        return np.fft.rfftfreq(256, 1.0 / rate), np.zeros(129)
    size = max(64, min(int(nperseg), _pow2_floor(n)))
    freqs, density = sp_signal.welch(x, fs=rate, window="hann", nperseg=size, noverlap=size // 2,
                                     detrend="constant", scaling="density")
    power = density * (freqs[1] - freqs[0])
    power[0] = 0.0
    return freqs, power


def _band_weights(freqs, lows, highs):
    """(bins, bands) matrix: the fraction of each FFT bin's span [f - df/2, f + df/2] inside each band.

    Fractional weights keep a band's level smooth when its edge falls between bins (the low third-octave
    bands are only a few bins wide).
    """
    spacing = float(freqs[1] - freqs[0])
    lows = np.asarray(lows, dtype=np.float64)
    highs = np.asarray(highs, dtype=np.float64)
    overlap = np.minimum((freqs + spacing / 2.0)[:, None], highs[None, :]) - np.maximum((freqs - spacing / 2.0)[:, None], lows[None, :])
    return np.clip(overlap, 0.0, spacing) / spacing


def _bands_argument(bands):
    """[(name, low, high)] from None, a {name: (low, high)} dict or an iterable of (name, low, high); high None = no limit."""
    if bands is None:
        bands = DEFAULT_BANDS
    if isinstance(bands, dict):
        items = [(name, edges[0], edges[1]) for name, edges in bands.items()]
    else:
        items = [tuple(item) for item in bands]
    out = []
    for name, low, high in items:
        low = 0.0 if low is None else float(low)
        high = math.inf if high is None else float(high)
        if high <= low:
            raise ValueError("Band {0!r} needs high > low (got {1}..{2})".format(name, low, high))
        out.append((str(name), low, high))
    return out


def _third_octave_bands(low, high, rate):
    """(nominal centres, exact lower edges, exact upper edges) of the IEC third-octave bands whose centre is in [low, high]."""
    nyquist = rate / 2.0
    centers, lows, highs = [], [], []
    for nominal in THIRD_OCTAVE_CENTERS:
        if nominal < low - 1e-9 or nominal > high + 1e-9:
            continue
        exact = 1000.0 * 10.0 ** (round(10.0 * math.log10(nominal / 1000.0)) / 10.0)
        lower, upper = exact * 10.0 ** -0.05, exact * 10.0 ** 0.05
        if lower >= nyquist:
            continue
        centers.append(nominal)
        lows.append(lower)
        highs.append(min(upper, nyquist))
    return centers, lows, highs


# ---------------------------------------------------------------------------
# Levels and bands
# ---------------------------------------------------------------------------


def levels(audio):
    """Peak, RMS, crest factor and DC of a file.

    {"peak_dbfs": sample peak over all channels, "rms_dbfs": RMS over all samples and channels,
     "crest_db": peak - RMS, "dc_offset": the channel mean with the largest magnitude (signed),
     "silent": True when the peak is below -80 dBFS}. Silence reads -200 dB with a crest of 0.
    """
    samples = _samples(audio)
    if not samples.size:
        return {"peak_dbfs": FLOOR_DB, "rms_dbfs": FLOOR_DB, "crest_db": 0.0, "dc_offset": 0.0, "silent": True}
    peak = float(np.max(np.abs(samples)))
    mean_square = float(np.mean(samples * samples))
    peak_db = _db(peak * peak)
    rms_db = _db(mean_square)
    means = samples.mean(axis=0)
    dc = float(means[int(np.argmax(np.abs(means)))])
    return {"peak_dbfs": peak_db, "rms_dbfs": rms_db, "crest_db": peak_db - rms_db if peak_db > FLOOR_DB else 0.0,
            "dc_offset": dc, "silent": bool(peak_db < -80.0)}


def band_levels(audio, bands=None):
    """Energy per frequency band of the mono mix (Welch average spectrum).

    bands: None for sub <60 Hz, low 60-250, low_mid 250-2000, high_mid 2000-6000, high >6000, or a dict
    {name: (low, high)} / a list of (name, low, high); high None means Nyquist.
    Returns {"bands": {name: {"db": level of the band (dB re full scale of the mean square),
                              "share": percent of the signal's energy}}, "total_db": level of the whole signal}.
    DC is excluded. Shares are relative to the whole spectrum, so custom bands that do not cover it sum to
    less than 100.
    """
    spec = _bands_argument(bands)
    freqs, power = _welch_power(_mono(audio), audio.rate)
    weights = _band_weights(freqs, [b[1] for b in spec], [b[2] for b in spec])
    per_band = power @ weights
    total = float(power.sum())
    out = {}
    for (name, _, _), value in zip(spec, per_band):
        out[name] = {"db": _db(value), "share": 100.0 * float(value) / total if total > 0.0 else 0.0}
    return {"bands": out, "total_db": _db(total)}


def third_octave_levels(audio, low=25.0, high=16000.0):
    """Level of each IEC one-third-octave band of the mono mix.

    Returns {"centers": nominal centre frequencies (25, 31.5, 40, ... Hz) from `low` to `high`,
             "db": level of each band (dB re full scale of the mean square),
             "relative_db": db minus the level of the whole signal, for loudness-matched comparisons,
             "total_db": the level of the whole signal}.
    Bands above Nyquist are dropped and the top band is cut at Nyquist. Silence gives -200 for every band.
    """
    centers, lows, highs = _third_octave_bands(float(low), float(high), audio.rate)
    freqs, power = _welch_power(_mono(audio), audio.rate)
    per_band = power @ _band_weights(freqs, lows, highs) if centers else np.zeros(0)
    total = float(power.sum())
    total_db = _db(total)
    db = [_db(value) for value in per_band]
    relative = [value - total_db for value in db] if total_db > FLOOR_DB else [FLOOR_DB] * len(db)
    return {"centers": [float(c) for c in centers], "db": db, "relative_db": relative, "total_db": total_db}


# ---------------------------------------------------------------------------
# Stereo image
# ---------------------------------------------------------------------------


def _correlation(left, right):
    """Pearson correlation of two channels; 1.0 when both are silent, 0.0 when only one is."""
    left = left - left.mean()
    right = right - right.mean()
    ll, rr = float(np.dot(left, left)), float(np.dot(right, right))
    if ll <= 0.0 and rr <= 0.0:
        return 1.0
    if ll <= 0.0 or rr <= 0.0:
        return 0.0
    return max(-1.0, min(1.0, float(np.dot(left, right)) / math.sqrt(ll * rr)))


def mono_sub(audio, cutoff=120.0):
    """What the mono sum loses below `cutoff` Hz (the bass crossover of the brief).

    Both channels are low-passed with a 4th-order zero-phase Butterworth filter; then
    loss_db = 10*log10(E_stereo / E_mono) with E_stereo = mean((L^2 + R^2) / 2) and E_mono = mean(((L + R) / 2)^2).
    Identical channels and mono files lose 0 dB, decorrelated channels of equal level 3 dB, a polarity-inverted
    sub is capped at 60 dB. Below -100 dBFS there is no sub to lose and the loss reads 0.
    Returns {"loss_db", "correlation": of the low-passed channels (-1..1; 1.0 for mono or no sub),
             "level_db": level of the low-passed stereo signal, so a caller can tell a missing sub from a good one}.
    """
    rate = audio.rate
    stereo = _stereo(audio)
    cutoff = min(float(cutoff), 0.45 * rate)
    if stereo.shape[0] < 64 or not np.any(stereo):
        return {"loss_db": 0.0, "correlation": 1.0, "level_db": FLOOR_DB}
    sos = sp_signal.butter(4, cutoff, btype="low", fs=rate, output="sos")
    low = sp_signal.sosfiltfilt(sos, stereo, axis=0)
    left, right = low[:, 0], low[:, 1]
    e_stereo = 0.5 * (float(np.dot(left, left)) + float(np.dot(right, right))) / len(left)
    mid = 0.5 * (left + right)
    e_mono = float(np.dot(mid, mid)) / len(left)
    level = _db(e_stereo)
    if e_stereo < 1e-10 or audio.channels == 1:
        return {"loss_db": 0.0, "correlation": 1.0, "level_db": level}
    loss = 60.0 if e_mono <= e_stereo * 1e-6 else min(60.0, max(0.0, 10.0 * math.log10(e_stereo / e_mono)))
    return {"loss_db": float(loss), "correlation": _correlation(left, right), "level_db": level}


def stereo(audio):
    """Stereo image: {"correlation": Pearson correlation of L and R (-1..1), "width": side RMS / mid RMS}.

    mid = (L + R) / 2 and side = (L - R) / 2. Mono files and silence give correlation 1.0 and width 0.0; a
    polarity-inverted pair has no mid, and its width is capped at 1000.
    """
    pair = _stereo(audio)
    left, right = pair[:, 0], pair[:, 1]
    if not left.size:
        return {"correlation": 1.0, "width": 0.0}
    mid = 0.5 * (left + right)
    side = 0.5 * (left - right)
    mid_ms, side_ms = float(np.dot(mid, mid)), float(np.dot(side, side))
    if side_ms <= 0.0:
        width = 0.0
    elif mid_ms <= side_ms * 1e-12:
        width = 1000.0
    else:
        width = min(1000.0, math.sqrt(side_ms / mid_ms))
    return {"correlation": _correlation(left, right), "width": float(width)}


# ---------------------------------------------------------------------------
# Phone speaker
# ---------------------------------------------------------------------------


def phone(audio, highpass_hz=200.0):
    """Phone-speaker simulation: mono sum and a 4th-order Butterworth high-pass.

    Returns (Audio, {"survival_db": level after minus level before,
                     "survival_share": percent of the energy that survives}). The Audio is mono at the same
    rate. A signal that is silent to begin with reports 0 dB and 100 percent (nothing was lost).
    """
    rate = audio.rate
    mono = _mono(audio)
    cutoff = float(highpass_hz)
    if not 0.0 < cutoff < 0.45 * rate:
        raise ValueError("highpass_hz must be between 0 and 0.45 * the sample rate")
    sos = sp_signal.butter(4, cutoff, btype="high", fs=rate, output="sos")
    filtered = sp_signal.sosfilt(sos, mono) if mono.size else mono
    before = float(np.dot(mono, mono))
    after = float(np.dot(filtered, filtered))
    if before <= 0.0:
        stats = {"survival_db": 0.0, "survival_share": 100.0}
    else:
        stats = {"survival_db": max(FLOOR_DB, 10.0 * math.log10(after / before)) if after > 0.0 else FLOOR_DB,
                 "survival_share": min(100.0, 100.0 * after / before)}
    return Audio(filtered, rate), stats


# ---------------------------------------------------------------------------
# The game's analyser
# ---------------------------------------------------------------------------


def _analyser_config(analyser):
    config = dict(DEFAULT_ANALYSER)
    for key, value in (analyser or {}).items():
        if value is not None:
            config[key] = value
    return config


def reactivity(audio, analyser=None):
    """Simulate the game's Web Audio AnalyserNode over a file and report how much each band moves.

    analyser: the spec's "analyser" block (fft_size, smoothing, min_db, max_db, bands {name: [low, high]},
    attack_ms, release_ms, frame_rate); missing keys fall back to the nova defaults (2048, 0.5, -90, -20,
    sub 20-80, low_mid 80-500, high_mid 500-4000, treble 4000-10000, 20 ms, 200 ms, 60 Hz).

    Per frame (frame_rate per second, the first frame is the first full window): mono mix 0.5*(L+R), the last
    fft_size samples, a Blackman window, magnitude normalised by fft_size, smoothed over frames as
    X = tau*X_prev + (1 - tau)*|X| (X_prev starts at 0), dB = 20*log10(X), byte = floor(255*(dB - min_db) /
    (max_db - min_db)) clipped to 0..255. A band's value is the mean byte over its bins round(f*fft_size/rate)
    (low inclusive, high exclusive) divided by 255, followed by a one-pole envelope with attack_ms when
    rising and release_ms when falling.

    Returns {band: {"mean", "std", "p5", "p95", "movement"}} of that 0..1 series, movement = p95 - p5. A band
    with no energy (bytes all 0) has movement 0.0.
    """
    config = _analyser_config(analyser)
    size = int(config["fft_size"])
    tau = float(config["smoothing"])
    min_db, max_db = float(config["min_db"]), float(config["max_db"])
    frame_rate = float(config["frame_rate"])
    rate = audio.rate
    band_items = [(str(name), float(edges[0]), float(edges[1])) for name, edges in config["bands"].items()]
    nbins = size // 2 + 1
    ranges = []
    for _, low, high in band_items:
        first = int(math.floor(low * size / rate + 0.5))
        last = int(math.floor(high * size / rate + 0.5))
        ranges.append((min(first, nbins), min(max(last, first + 1), nbins)))
    top = max([last for _, last in ranges] + [1])

    x = _mono(audio)
    if len(x) < size:
        x = np.concatenate([np.zeros(size - len(x)), x])
    step = rate / frame_rate
    count = int((len(x) - size) // step) + 1
    starts = np.floor(np.arange(count) * step).astype(np.int64)
    window = sp_signal.windows.blackman(size, sym=False)
    view = np.lib.stride_tricks.sliding_window_view(x, size)
    magnitude = np.empty((count, top))
    for first in range(0, count, 512):
        block = view[starts[first:first + 512]] * window
        magnitude[first:first + len(block)] = np.abs(sp_fft.rfft(block, axis=1)[:, :top]) / size
    if tau > 0.0:
        magnitude = sp_signal.lfilter([1.0 - tau], [1.0, -tau], magnitude, axis=0)
    decibels = 20.0 * np.log10(np.maximum(magnitude, 1e-300))
    byte = np.clip(np.floor(255.0 * (decibels - min_db) / (max_db - min_db)), 0.0, 255.0)

    dt = 1.0 / frame_rate
    attack = math.exp(-dt / (float(config["attack_ms"]) / 1000.0)) if float(config["attack_ms"]) > 0 else 0.0
    release = math.exp(-dt / (float(config["release_ms"]) / 1000.0)) if float(config["release_ms"]) > 0 else 0.0
    out = {}
    for (name, _, _), (first, last) in zip(band_items, ranges):
        values = byte[:, first:last].mean(axis=1) / 255.0 if last > first else np.zeros(count)
        smoothed = np.empty(count)
        state = 0.0
        for index, value in enumerate(values.tolist()):
            coefficient = attack if value > state else release
            state = coefficient * state + (1.0 - coefficient) * value
            smoothed[index] = state
        p5, p95 = (float(v) for v in np.percentile(smoothed, [5.0, 95.0]))
        out[name] = {"mean": float(smoothed.mean()), "std": float(smoothed.std()), "p5": p5, "p95": p95,
                     "movement": p95 - p5}
    return out


# ---------------------------------------------------------------------------
# Masking
# ---------------------------------------------------------------------------


def masking(parts, frame_s=0.1, top=8):
    """Where pairs of stems sit in the same third-octave band at the same time.

    parts: {name: Audio} at one sample rate. Each stem's mono mix is cut into frames of `frame_s` seconds
    (Hann windows of twice that length, 50% overlap) and the energy of every third-octave band is taken
    per frame. In a band a frame "counts" for a stem when the stem is within 12 dB of its own maximum
    in that band and above -60 dB. overlap_share is the percent of frames (of the longest stem) in which both
    stems of a pair count.

    Returns up to `top` entries {"a", "b", "band_hz": centre of the band, "overlap_share": percent,
    "level_db": the lower of the two stems' loudest frame in that band}, largest overlap first (ties: the
    louder pair first). Pairs and bands with no overlap are left out.
    """
    names = list(parts)
    if len(names) < 2:
        return []
    rates = set(parts[name].rate for name in names)
    if len(rates) > 1:
        raise ValueError("masking needs one sample rate, got {0}".format(sorted(rates)))
    rate = rates.pop()
    levels_db = [_frame_band_levels(_mono(parts[name]), rate, frame_s) for name in names]
    centers = levels_db[0][1]
    frames = max(item[0].shape[0] for item in levels_db)
    nbands = len(centers)
    stack = np.full((len(names), frames, nbands), FLOOR_DB)
    for index, (matrix, _) in enumerate(levels_db):
        stack[index, :matrix.shape[0]] = matrix
    peak = stack.max(axis=1)
    active = ((stack >= peak[:, None, :] - 12.0) & (stack > -60.0)).astype(np.float32)
    overlap = np.einsum("itb,jtb->ijb", active, active)
    found = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            for band in np.flatnonzero(overlap[i, j] > 0):
                found.append((100.0 * float(overlap[i, j, band]) / frames, float(min(peak[i, band], peak[j, band])),
                              names[i], names[j], float(centers[band])))
    found.sort(key=lambda item: (-item[0], -item[1]))
    return [{"a": a, "b": b, "band_hz": hz, "overlap_share": share, "level_db": level}
            for share, level, a, b, hz in found[:max(0, int(top))]]


def _frame_band_levels(x, rate, frame_s):
    """(frames x bands) third-octave levels in dB and the nominal band centres, for 25 Hz to 16 kHz."""
    hop = max(16, int(round(frame_s * rate)))
    size = 2 * hop
    nfft = _pow2_ceil(size)
    centers, lows, highs = _third_octave_bands(MASKING_LOW_HZ, MASKING_HIGH_HZ, rate)
    if len(x) < size:
        x = np.concatenate([x, np.zeros(size - len(x))])
    count = (len(x) - size) // hop + 1
    window = sp_signal.windows.hann(size, sym=False)
    freqs = np.fft.rfftfreq(nfft, 1.0 / rate)
    weights = _band_weights(freqs, lows, highs)
    scale = np.full(len(freqs), 2.0)
    scale[0] = 1.0
    if nfft % 2 == 0:
        scale[-1] = 1.0
    scale = scale / (nfft * float(np.sum(window * window)))
    view = np.lib.stride_tricks.sliding_window_view(x, size)
    out = np.empty((count, len(centers)))
    for first in range(0, count, 128):
        block = view[first * hop:count * hop:hop][:128] * window
        power = np.abs(sp_fft.rfft(block, n=nfft, axis=1)) ** 2 * scale
        out[first:first + len(block)] = 10.0 * np.log10(np.maximum(power @ weights, _TINY_POWER))
    return out, centers


# ---------------------------------------------------------------------------
# Rhythm
# ---------------------------------------------------------------------------


# Onset detection ------------------------------------------------------------------------------------------

_ONSET_WINDOW_S = 0.0232     # analysis window: 1024 samples at 44.1 and 48 kHz
_ONSET_BAND_EDGES = (30.0, 80.0, 160.0, 320.0, 640.0, 1280.0, 2560.0, 5120.0, 10240.0)
_ONSET_DELTA = 0.10        # a peak must beat the local mean flux by this fraction of the 98th percentile flux ...
_ONSET_SPREADS = 4.0       # ... or by this many robust standard deviations of the flux (noise has no onsets) ...
_ONSET_FLOOR = 0.03        # ... or by this much (log-magnitude units), whichever is largest
_ONSET_REFINE_MIN_RATIO = 3.0


def _onset_flux(x, rate, size, hop):
    """Spectral flux of the log-compressed, band-averaged magnitude spectrogram.

    Frames of ~23 ms every ~6 ms, Hann windowed; magnitudes are scaled so a full-scale sine is 1 and compressed
    as log(1 + 1000 m). The flux of a frame is the mean over octave bands of the band-averaged positive
    change since the previous frame (SuperFlux), so a kick (a few bins) counts as much as a hi-hat (hundreds).
    Returns the flux per frame; frame i is centred on sample i * hop.
    """
    count = max(1, (len(x) - size // 2) // hop + 1)               # no frame reaches past the end: a cut is not an onset
    padded = np.concatenate([np.zeros(size // 2), x, np.zeros(size)])    # silence before the start
    view = np.lib.stride_tricks.sliding_window_view(padded, size)
    window = sp_signal.windows.hann(size, sym=False)
    freqs = np.fft.rfftfreq(size, 1.0 / rate)
    edges = np.asarray(_ONSET_BAND_EDGES)
    band = np.searchsorted(edges, freqs, side="right") - 1
    nbands = len(edges) - 1
    average = np.zeros((len(freqs), nbands))
    for index in range(nbands):
        members = np.flatnonzero(band == index)
        if not members.size:                      # a band narrower than a bin: borrow the nearest bin
            members = np.array([int(np.argmin(np.abs(freqs - math.sqrt(edges[index] * edges[index + 1]))))])
        average[members, index] = 1.0 / members.size
    flux = np.empty(count)
    previous = np.zeros(len(freqs))
    scale = 4.0 / size
    for first in range(0, count, 2048):
        rows = np.arange(first, min(count, first + 2048))
        block = view[rows * hop] * window
        compressed = np.log1p(1000.0 * scale * np.abs(sp_fft.rfft(block, axis=1)))
        # SuperFlux: a frame is compared with the neighbourhood maximum of the one before, so partials that beat
        # against each other or drift between adjacent bins do not count as new energy.
        reference = ndimage.maximum_filter1d(np.vstack([previous, compressed[:-1]]), size=3, axis=1, mode="nearest")
        flux[rows] = (np.maximum(compressed - reference, 0.0) @ average).mean(axis=1)
        previous = compressed[-1]
    # An onset keeps the new energy for several frames; a bin recovering from an interference null does not.
    first_frame = flux[0]                                       # a sound that starts with the file has no past to persist from
    flux = np.minimum(flux, np.append(flux[1:], flux[-1]))
    flux[0] = first_frame
    return flux


def _onset_bands(x, rate):
    """The signal split into low (<250 Hz), mid (250-2500 Hz) and high (>2500 Hz) parts for onset refinement.

    A sustained pad or bass hides the rise of a hi-hat in full-band energy; in its own band the rise is sharp.
    """
    nyquist = rate / 2.0
    top = min(2500.0, 0.9 * nyquist)
    filters = (sp_signal.butter(2, 250.0, btype="low", fs=rate, output="sos"),
               sp_signal.butter(2, [250.0, top], btype="band", fs=rate, output="sos"),
               sp_signal.butter(2, top, btype="high", fs=rate, output="sos"))
    return [sp_signal.sosfilt(sos, x) for sos in filters]


def _refine_onset(bands, centre, size, hop, rate):
    """Sample index of the sharpest energy rise near a spectral-flux peak, or None if there is no sharp rise.

    The flux peaks when an onset first enters the analysis window, up to half a window early. In each band the
    onset is placed where the energy of the next 1.5 ms most exceeds that of the previous 1.5 ms (a ratio, so a
    quiet note after a loud tail still counts); the band with the sharpest rise decides, and on a plateau the
    last sample wins, which is the onset of a click.
    """
    width = max(8, int(round(0.0015 * rate)))
    length = len(bands[0])
    first = max(0, centre - size // 2 - hop)
    last = min(length - 1, centre + size // 2)
    if last <= first:
        return None
    best_ratio, best_sample = 0.0, None
    for x in bands:
        lo = max(0, first - width)
        segment = np.concatenate([np.zeros(width), x[lo:last + width + 1], np.zeros(width)])
        offset = first - lo + width                                  # index of `first` in `segment`
        cumulative = np.concatenate([[0.0], np.cumsum(segment * segment)])
        positions = np.arange(offset, offset + (last - first) + 1)
        positions = positions[(positions >= width) & (positions + width < len(segment))]
        if not positions.size:
            continue
        before = (cumulative[positions] - cumulative[positions - width]) / width
        after = (cumulative[positions + width] - cumulative[positions]) / width
        floor = 1e-3 * float(after.max()) + 1e-30
        ratio = (after + floor) / (before + floor)
        top = float(ratio.max())
        if top > best_ratio * (1.0 + 1e-9):
            plateau = np.flatnonzero(ratio >= top * (1.0 - 1e-9))
            best_ratio, best_sample = top, first + int(positions[plateau[-1]]) - offset
    if best_ratio < _ONSET_REFINE_MIN_RATIO:
        return None
    return best_sample


def onsets(audio, min_gap=0.03):
    """Onset times in seconds of the mono mix (spectral flux, adaptive threshold, peak picking).

    The detection function is the spectral flux of band-averaged, log-compressed spectra; a frame is an onset
    when it is the largest within 30 ms, exceeds the mean flux of the surrounding 200 ms by 10% of the 98th
    percentile flux, by four robust standard deviations of the flux and by an absolute floor (so silence, steady
    tones and noise give nothing), and is at least
    `min_gap` seconds from a stronger onset. Each onset is then refined to the sample where the energy rises
    sharpest, so clicks and plucked or struck notes are found within about 2 ms. Where the energy does not
    rise (a legato note change) the time falls back to the flux peak plus 0.3 of a window, where legato pitch
    changes were measured to sit (median 7.3 ms after the peak frame at 1024 samples, spread +-3 ms).
    """
    x = _mono(audio)
    rate = audio.rate
    if len(x) < 512 or not np.any(x):
        return []
    size = max(256, 1 << int(round(math.log2(_ONSET_WINDOW_S * rate))))
    hop = size // 4
    flux = _onset_flux(x, rate, size, hop)
    frame_rate = rate / float(hop)
    reach = max(1, int(round(0.03 * frame_rate)))
    span = max(2, int(round(0.10 * frame_rate)))
    local_max = ndimage.maximum_filter1d(flux, size=2 * reach + 1, mode="nearest")
    local_mean = ndimage.uniform_filter1d(flux, size=2 * span + 1, mode="nearest")
    body = flux[3:] if len(flux) > 8 else flux           # the first frames can hold the start of a sustained sound
    typical = float(np.percentile(body, 98.0))
    spread = 1.4826 * float(np.median(np.abs(body - np.median(body))))
    delta = max(_ONSET_DELTA * typical, _ONSET_SPREADS * spread, _ONSET_FLOOR)
    candidates = np.flatnonzero((flux >= local_max) & (flux > local_mean + delta))
    chosen = []
    for frame in candidates[np.argsort(-flux[candidates], kind="stable")]:
        if all(abs(int(frame) - other) * hop >= min_gap * rate for other in chosen):
            chosen.append(int(frame))
    times = []
    bands = _onset_bands(x, rate) if chosen else []
    for frame in sorted(chosen):
        centre = frame * hop
        sample = _refine_onset(bands, centre, size, hop, rate)
        times.append((sample if sample is not None else centre + int(0.3 * size)) / float(rate))
    times.sort()
    deduped = []
    for value in times:
        if not deduped or value - deduped[-1] >= min_gap:
            deduped.append(float(value))
    return deduped


def grid_stats(onset_times, bpm, grid=16, offset=0.0, beats_per_bar=4.0, tolerance_ms=10.0):
    """How far onsets sit from the rhythmic grid.

    grid is the note value of the grid lines (16 = sixteenth notes: 1/4 beat; 12 = eighth triplets), counted
    from `offset` seconds, the time of the first grid line (bar 1 beat 1). beats_per_bar is accepted for the
    spec's meter and does not change the spacing, since a grid is a note value.
    Each onset is compared with its nearest line; positive deviations are late.

    Returns {"count", "mean_abs_ms", "max_ms": largest |deviation|, "on_grid_share": the FRACTION (0..1, not
    percent) of onsets within tolerance_ms, "late_ms_median": median signed deviation, "worst": up to three
    {"time", "deviation_ms"} with the largest |deviation|}. No onsets gives a count of 0 and zeros.
    """
    if not bpm or float(bpm) <= 0.0:
        raise ValueError("bpm must be positive")
    if not grid or float(grid) <= 0.0:
        raise ValueError("grid must be positive")
    times = np.asarray(list(onset_times), dtype=np.float64).reshape(-1)
    times = times[np.isfinite(times)]
    if not times.size:
        return {"count": 0, "mean_abs_ms": 0.0, "max_ms": 0.0, "on_grid_share": 0.0, "late_ms_median": 0.0, "worst": []}
    step = 60.0 / float(bpm) * 4.0 / float(grid)
    relative = times - float(offset)
    deviation = (relative - np.round(relative / step) * step) * 1000.0
    magnitude = np.abs(deviation)
    order = np.argsort(-magnitude, kind="stable")[:3]
    return {"count": int(times.size), "mean_abs_ms": float(magnitude.mean()), "max_ms": float(magnitude.max()),
            "on_grid_share": float(np.mean(magnitude <= float(tolerance_ms))),
            "late_ms_median": float(np.median(deviation)),
            "worst": [{"time": float(times[i]), "deviation_ms": float(deviation[i])} for i in order]}


# ---------------------------------------------------------------------------
# Key
# ---------------------------------------------------------------------------

_KEY_FRAME_S = 0.74          # analysis window: 32768 samples at 44.1 and 48 kHz (1.4 Hz bins, resolves bass notes)
_KEY_MAX_FRAMES = 480        # a long file is sampled sparsely rather than analysed in full
_KEY_REL_DB = 50.0           # spectral peaks weaker than this under the frame's strongest are ignored
_KEY_GATE_DB = 45.0          # frames quieter than this under the loudest are ignored
_KEY_SMEAR = {7: 0.4, 4: 0.15}        # templates of the full-range view also credit each profile note's 3rd and 5th partial
_KEY_FUNDAMENTAL_FROM = 150.0         # the salience view takes evidence from here up ...
_KEY_MIDRANGE_FROM = 400.0            # ... and the mid-range view votes with fundamentals and partials from here up
_KEY_HARMONICS = 8
_KEY_DECAY = 0.8                      # weight of harmonic h of a pitch: 0.8 ** (h - 1)
_KEY_TOLERANCE_CENTS = 35.0


def _key_peaks(x, rate):
    """Spectral peaks of long Hann frames: {"frame", "freq", "amp"} arrays, per-frame RMS and the frame hop in seconds.

    Local maxima of the magnitude spectrum between 40 Hz and 6 kHz, within 70 dB of the frame's strongest, with their
    frequency and amplitude interpolated parabolically on the log magnitude (sub-bin accuracy, which keeps a bass
    note from smearing across neighbouring semitones).
    """
    size = 1 << int(round(math.log2(_KEY_FRAME_S * rate)))
    if len(x) < size:
        x = np.concatenate([x, np.zeros(size - len(x))])
    hop = size // 2
    count = (len(x) - size) // hop + 1
    if count > _KEY_MAX_FRAMES:
        hop = (len(x) - size) // (_KEY_MAX_FRAMES - 1)
        count = (len(x) - size) // hop + 1
    window = sp_signal.windows.hann(size, sym=False)
    low = max(1, int(40.0 * size / rate) - 1)
    high = min(size // 2 - 2, int(math.ceil(6000.0 * size / rate)) + 1)
    view = np.lib.stride_tricks.sliding_window_view(x, size)
    frames, freqs, amps = [], [], []
    rms = np.zeros(count)
    for first in range(0, count, 32):
        rows = np.arange(first, min(count, first + 32))
        block = view[rows * hop]
        rms[rows] = np.sqrt(np.mean(block * block, axis=1))
        magnitude = np.abs(sp_fft.rfft(block * window, axis=1))[:, low - 1:high + 2]
        centre = magnitude[:, 1:-1]
        peaks = (centre > magnitude[:, :-2]) & (centre >= magnitude[:, 2:])
        peaks &= centre > centre.max(axis=1, keepdims=True) * 10.0 ** (-70.0 / 20.0)
        row, column = np.nonzero(peaks)
        left = np.log(magnitude[row, column] + 1e-30)
        middle = np.log(magnitude[row, column + 1] + 1e-30)
        right = np.log(magnitude[row, column + 2] + 1e-30)
        curvature = left - 2.0 * middle + right
        shift = np.where(curvature < 0.0, 0.5 * (left - right) / np.where(curvature < 0.0, curvature, -1.0), 0.0)
        shift = np.clip(shift, -0.5, 0.5)
        frames.append(row + first)
        freqs.append((low + column + shift) * rate / size)
        amps.append(np.exp(middle - 0.25 * (left - right) * shift))
    return {"frame": np.concatenate(frames).astype(np.int64), "freq": np.concatenate(freqs), "amp": np.concatenate(amps),
            "rms": rms, "count": count, "hop_s": hop / float(rate)}


def _key_fold(votes, rms, weights):
    """Per-frame votes (frames x 12) -> chroma (12, sum 1): quiet frames dropped, each frame counted equally, then weighted."""
    sums = votes.sum(axis=1)
    use = (rms > 0.0) & (rms >= rms.max() * 10.0 ** (-_KEY_GATE_DB / 20.0)) & (sums > 0.0)
    if not np.any(use):
        return np.zeros(12)
    folded = (votes[use] / sums[use][:, None]) * weights[use][:, None]
    total = folded.sum(axis=0)
    return total / total.sum()


def _key_own_chroma(peaks, a4_hz, low, weights, high=5000.0):
    """Every spectral peak between `low` and `high` Hz votes for its own pitch class with its amplitude."""
    count, frame, freq, amp = peaks["count"], peaks["frame"], peaks["freq"], peaks["amp"]
    strongest = np.zeros(count)
    np.maximum.at(strongest, frame, amp)
    keep = (freq >= low) & (freq <= high) & (amp >= strongest[frame] * 10.0 ** (-_KEY_REL_DB / 20.0))
    pitch_class = np.rint(69.0 + 12.0 * np.log2(freq[keep] / a4_hz)).astype(np.int64) % 12
    votes = np.bincount(frame[keep] * 12 + pitch_class, weights=amp[keep], minlength=count * 12).reshape(count, 12)
    return _key_fold(votes, peaks["rms"], weights)


def _key_fundamental_chroma(peaks, a4_hz, weights, low=_KEY_FUNDAMENTAL_FROM, high=5000.0):
    """Fundamental-weighted pitch salience: each peak is credited to the pitch that best explains it.

    For a peak at f the candidate fundamentals are f/1 ... f/8 (down to 55 Hz). The salience of a candidate is
    the sum over its harmonics h = 1..8 of 0.8**(h-1) times the amplitude of the nearest peak within 35 cents of
    h * candidate. The peak votes, once and with its own amplitude, for the pitch class of its most salient
    candidate. So an overtone (the C# fifth-and-a-third partial of an A) feeds the A that carries it, and a
    strong fundamental cannot feed the sub-harmonic ghosts (D, F) that a plain harmonic sum would credit.
    """
    count, frame, freq, amp = peaks["count"], peaks["frame"], peaks["freq"], peaks["amp"]
    starts = np.searchsorted(frame, np.arange(count))
    ends = np.searchsorted(frame, np.arange(count), side="right")
    harmonics = np.arange(1, _KEY_HARMONICS + 1)
    divisors = np.arange(1, _KEY_HARMONICS + 1)
    weight = _KEY_DECAY ** (harmonics - 1)
    votes = np.zeros((count, 12))
    for index in range(count):
        first, last = starts[index], ends[index]
        f, a = freq[first:last], amp[first:last]
        evidence = (f >= low) & (f <= high)
        if not evidence.any():
            continue
        f, a = f[evidence], a[evidence]
        keep = a >= a.max() * 10.0 ** (-_KEY_REL_DB / 20.0)
        f, a = f[keep], a[keep]
        candidates = f[:, None] / divisors[None, :]                           # (peaks, divisors)
        targets = candidates[:, :, None] * harmonics[None, None, :]           # (peaks, divisors, harmonics)
        position = np.searchsorted(f, targets)
        below = np.clip(position - 1, 0, len(f) - 1)
        above = np.clip(position, 0, len(f) - 1)
        miss_below = np.abs(np.log2(f[below] / targets))
        miss_above = np.abs(np.log2(f[above] / targets))
        nearest = np.where(miss_below <= miss_above, below, above)
        cents = 1200.0 * np.minimum(miss_below, miss_above)
        found = np.where(cents <= _KEY_TOLERANCE_CENTS, a[nearest], 0.0)
        salience = np.where(candidates >= 55.0, (found * weight).sum(axis=2), -1.0)
        chosen = np.argmax(salience, axis=1)
        rows = np.arange(len(f))
        pitch_class = np.rint(69.0 + 12.0 * np.log2(candidates[rows, chosen] / a4_hz)).astype(np.int64) % 12
        np.add.at(votes[index], pitch_class, a)
    return _key_fold(votes, peaks["rms"], weights)


def _key_templates(smear):
    """(24, 12) unit-length centred key templates, majors C..B then minors C..B, from the Krumhansl-Kessler profiles.

    smear: {semitones above: fraction}; each profile weight is also credited to the pitch classes of its 3rd and
    5th partial (a fifth and a major third above), as a harmonic-rich instrument does.
    """
    rows = []
    for mode in ("major", "minor"):
        profile = np.asarray(KEY_PROFILES[mode], dtype=np.float64)
        for tonic in range(12):
            base = np.roll(profile, tonic)
            template = base.copy()
            for offset, fraction in (smear or {}).items():
                template = template + fraction * np.roll(base, offset)
            template = template - template.mean()
            rows.append(template / np.linalg.norm(template))
    return np.asarray(rows)


_KEY_TEMPLATES = {"plain": _key_templates(None), "smeared": _key_templates(_KEY_SMEAR)}


def _key_scores(chroma, kind):
    """Pearson correlation of a chroma with the 24 key templates (majors then minors), or None for a flat chroma."""
    centred = chroma - chroma.mean()
    norm = float(np.linalg.norm(centred))
    if norm < 1e-12:
        return None
    return _KEY_TEMPLATES[kind] @ centred / norm


def _key_label(index):
    """"A minor" for index 21: majors C..B are 0..11, minors C..B are 12..23."""
    return "{0} {1}".format(NOTE_NAMES[index % 12], "major" if index < 12 else "minor")


def key_estimate(audio, a4_hz=440.0, start_weight=4.0, start_seconds=3.0):
    """Musical key of a file: pitch-class profiles matched to the Krumhansl-Kessler key profiles.

    Three views of the file are matched against the 24 keys and the best fit of each key counts; on the real NOVA
    masters no single view was enough (the first reads bass distortion as the major third, the others lose
    the harmony when a sine-like pad lives below 400 Hz):
      full         every spectral peak from 55 Hz to 5 kHz votes for its pitch class; the templates also credit
                   each profile note's 3rd and 5th partial, as a harmonic-rich instrument does
      fundamental  fundamental-weighted pitch salience from 150 Hz up: each peak is credited to the pitch that
                   explains it as a harmonic (0.8**(h-1) weights, h = 1..8; see `_key_fundamental_chroma`)
      midrange     peaks from 400 Hz up only: bass notes that glide, distort or approach chromatically cannot
                   push the profile toward the wrong mode there
    Frames are long (0.74 s) so a bass note is resolved, quiet frames are ignored, each frame counts equally, and
    the opening counts more: a frame at the start of the file weighs 1 + start_weight, falling with a time
    constant of start_seconds, because a loop or piece opens on its tonic chord (pass start_weight=0 for an
    excerpt cut from the middle of music).

    Returns {"key": "A minor", "tonic": "A", "mode": "minor" or "major", "confidence": Pearson r of the best key
             (-1..1), "second": {"key", "confidence"} the best other key (often the relative major or minor, so
             confidence minus second is the margin), "chroma": 12 floats, C first, sum 1, the winning view's
             profile (start weighting included), "view": "full", "fundamental" or "midrange"}.
    Pitch classes are counted relative to a4_hz. A file with no tonal content gives key, tonic and mode None,
    confidence 0.0, a chroma of zeros and view None. Two chords a fourth apart (an i-iv vamp) are genuinely
    ambiguous in pitch-class statistics: look at the margin.
    """
    a4_hz = float(a4_hz)
    peaks = _key_peaks(_mono(audio), audio.rate)
    times = np.arange(peaks["count"]) * peaks["hop_s"]
    weights = 1.0 + float(start_weight) * np.exp(-times / max(1e-3, float(start_seconds)))
    views = (("full", _key_own_chroma(peaks, a4_hz, 55.0, weights), "smeared"),
             ("fundamental", _key_fundamental_chroma(peaks, a4_hz, weights), "plain"),
             ("midrange", _key_own_chroma(peaks, a4_hz, _KEY_MIDRANGE_FROM, weights), "plain"))
    fitted = []                                                 # (scores of the 24 keys, chroma, view name)
    for name, chroma, kind in views:
        scores = _key_scores(chroma, kind)
        if scores is not None:
            fitted.append((scores, chroma, name))
    if not fitted:
        return {"key": None, "tonic": None, "mode": None, "confidence": 0.0, "second": {"key": None, "confidence": 0.0},
                "chroma": [0.0] * 12, "view": None}
    fit = np.max([scores for scores, _, _ in fitted], axis=0)   # the best correlation each key gets in any view
    holder = max(fitted, key=lambda view: float(view[0].max()))  # the view that holds the best key
    winner, runner = (int(index) for index in np.argsort(-fit)[:2])
    return {"key": _key_label(winner), "tonic": NOTE_NAMES[winner % 12], "mode": "major" if winner < 12 else "minor",
            "confidence": float(fit[winner]), "second": {"key": _key_label(runner), "confidence": float(fit[runner])},
            "chroma": [float(v) for v in holder[1]], "view": holder[2]}
