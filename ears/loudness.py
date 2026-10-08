"""Loudness per ITU-R BS.1770-4 and EBU R128 / Tech 3341-3342, in numpy and scipy.

It works on in-memory signals (tier sums are never written to disk) at any sample rate:

- K-weighting: the two BS.1770 biquads (high shelf, then the RLB high-pass), designed for the
  file's own rate from the analogue prototypes, as libebur128 does.
- Integrated loudness: 400 ms blocks every 100 ms, absolute gate -70 LUFS, relative gate -10 LU.
- Loudness range (Tech 3342): 3 s short-term values every 100 ms, gates -70 LUFS and -20 LU,
  95th minus 10th percentile.
- True peak: 4x oversampling (polyphase FIR) below 96 kHz, 2x below 192 kHz.

Mono signals are measured as dual mono (the same signal on both speakers), which is how the game
plays a mono stem and what ffmpeg's ebur128 `dualmono` option does. Results agree with ffmpeg's
ebur128 filter to within 0.1 LU (tests/ears/test_loudness.py).
"""
import math

import numpy as np
from scipy import signal as sps

ABSOLUTE_GATE = -70.0
RELATIVE_GATE = 10.0
LRA_RELATIVE_GATE = 20.0
BLOCK = 0.4
STEP = 0.1
SHORT_TERM = 3.0
SILENCE = -200.0   # what "no measurable loudness" reports, so results stay JSON-safe


def k_weighting(rate):
    """((b, a) shelf, (b, a) high-pass) biquad coefficients of the BS.1770 K-filter at `rate` Hz."""
    rate = float(rate)
    f0, gain, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / rate)
    vh = 10.0 ** (gain / 20.0)
    vb = vh ** 0.4996667741545416
    a0 = 1.0 + k / q + k * k
    shelf_b = np.array([(vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0])
    shelf_a = np.array([1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0])
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / rate)
    a0 = 1.0 + k / q + k * k
    high_b = np.array([1.0, -2.0, 1.0])
    high_a = np.array([1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0])
    return (shelf_b, shelf_a), (high_b, high_a)


def _stereo(samples):
    # One NaN or infinity (a damaged float file) would otherwise poison every sum: treat it as silence.
    samples = np.nan_to_num(np.asarray(samples, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    if samples.ndim == 1:
        samples = samples[:, None]
    if samples.shape[1] == 1:
        return np.repeat(samples, 2, axis=1)   # dual mono
    return samples[:, :2]


def k_filter(samples, rate):
    """K-weighted copy of (frames, channels) samples."""
    (b1, a1), (b2, a2) = k_weighting(rate)
    return sps.lfilter(b2, a2, sps.lfilter(b1, a1, samples, axis=0), axis=0)


def _window_energies(weighted, rate, length, step):
    """Mean square per window (summed over channels, weights 1.0 for L and R), windows every `step` s."""
    frames = weighted.shape[0]
    size = int(round(length * rate))
    hop = int(round(step * rate))
    if frames < size or size <= 0:
        return np.zeros(0)
    power = np.sum(weighted * weighted, axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(power)])
    starts = np.arange(0, frames - size + 1, hop)
    return (cumulative[starts + size] - cumulative[starts]) / float(size)


def _lufs(energy):
    return -0.691 + 10.0 * math.log10(energy) if energy > 0 else SILENCE


def _gated_mean(energies, relative):
    """Mean energy after the absolute gate and a relative gate `relative` LU below the absolute-gated mean."""
    if not energies.size:
        return 0.0
    loudness = -0.691 + 10.0 * np.log10(np.maximum(energies, 1e-30))
    kept = energies[loudness > ABSOLUTE_GATE]
    if not kept.size:
        return 0.0
    threshold = _lufs(float(np.mean(kept))) - relative
    loudness = -0.691 + 10.0 * np.log10(np.maximum(kept, 1e-30))
    kept = kept[loudness > threshold]
    return float(np.mean(kept)) if kept.size else 0.0


def integrated(samples, rate, weighted=None):
    """Integrated loudness in LUFS (SILENCE when everything is gated out)."""
    weighted = k_filter(_stereo(samples), rate) if weighted is None else weighted
    return _lufs(_gated_mean(_window_energies(weighted, rate, BLOCK, STEP), RELATIVE_GATE))


def short_term(samples, rate, step=STEP, weighted=None):
    """Short-term loudness (3 s windows) every `step` s, in LUFS."""
    weighted = k_filter(_stereo(samples), rate) if weighted is None else weighted
    energies = _window_energies(weighted, rate, SHORT_TERM, step)
    return np.array([_lufs(value) for value in energies])


def momentary(samples, rate, step=STEP, weighted=None):
    weighted = k_filter(_stereo(samples), rate) if weighted is None else weighted
    energies = _window_energies(weighted, rate, BLOCK, step)
    return np.array([_lufs(value) for value in energies])


def loudness_range(samples, rate, weighted=None):
    """EBU Tech 3342 loudness range in LU (0 for signals shorter than 3 s or fully gated)."""
    weighted = k_filter(_stereo(samples), rate) if weighted is None else weighted
    energies = _window_energies(weighted, rate, SHORT_TERM, STEP)
    if not energies.size:
        return 0.0
    loudness = -0.691 + 10.0 * np.log10(np.maximum(energies, 1e-30))
    loudness = loudness[loudness > ABSOLUTE_GATE]
    if not loudness.size:
        return 0.0
    threshold = _lufs(float(np.mean(10.0 ** ((loudness + 0.691) / 10.0)))) - LRA_RELATIVE_GATE
    loudness = loudness[loudness > threshold]
    if loudness.size < 2:
        return 0.0
    low, high = np.percentile(loudness, [10.0, 95.0])
    return float(high - low)


def true_peak(samples, rate):
    """True peak in dBTP: the highest absolute value after oversampling (BS.1770-4 Annex 2)."""
    samples = np.nan_to_num(np.asarray(samples, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    if samples.ndim == 1:
        samples = samples[:, None]
    if not samples.size:
        return SILENCE
    factor = 4 if rate < 96000 else 2 if rate < 192000 else 1
    if factor == 1:
        value = float(np.max(np.abs(samples)))
    else:
        value = 0.0
        for channel in range(samples.shape[1]):
            up = sps.resample_poly(samples[:, channel], factor, 1)
            value = max(value, float(np.max(np.abs(up))), float(np.max(np.abs(samples[:, channel]))))
    return 20.0 * math.log10(value) if value > 0 else SILENCE


def sample_peak(samples):
    samples = np.nan_to_num(np.asarray(samples, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    value = float(np.max(np.abs(samples))) if samples.size else 0.0
    return 20.0 * math.log10(value) if value > 0 else SILENCE


def measure(audio, peaks=True, series=False):
    """Everything loudness about an Audio object, rounded for reports.

    Returns integrated (LUFS), range (LU), short_term_max and momentary_max (LUFS), true_peak (dBTP)
    and sample_peak (dBFS); series=True adds the short-term curve at 1 value per second.
    """
    stereo = _stereo(audio.samples)
    weighted = k_filter(stereo, audio.rate)
    st = short_term(stereo, audio.rate, weighted=weighted)
    mo = momentary(stereo, audio.rate, weighted=weighted)
    out = {
        "integrated": round(integrated(stereo, audio.rate, weighted=weighted), 2),
        "range": round(loudness_range(stereo, audio.rate, weighted=weighted), 2),
        "short_term_max": round(float(np.max(st)), 2) if st.size else SILENCE,
        "momentary_max": round(float(np.max(mo)), 2) if mo.size else SILENCE,
    }
    if peaks:
        out["true_peak"] = round(true_peak(audio.samples, audio.rate), 2)
        out["sample_peak"] = round(sample_peak(audio.samples), 2)
    if series:
        out["short_term"] = [round(float(value), 1) for value in short_term(stereo, audio.rate, step=1.0, weighted=weighted)]
    return out


def gain_to(current_lufs, target_lufs):
    """dB of gain that moves a measured loudness to a target (0 for silence)."""
    if current_lufs <= SILENCE + 1:
        return 0.0
    return float(target_lufs) - float(current_lufs)
