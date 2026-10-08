"""Tests for ears.measure: spectral and perceptual measurements on synthetic signals (offline, no Live).

Every signal is generated here with numpy. Tolerances are set from what the physics allows (for example a
sine of amplitude 0.5 reads -9.03 dB, and decorrelated channels lose 3.01 dB in a mono sum), not from what the
code happens to return.
"""
import json
import math
import time

import numpy as np
import pytest
from scipy import signal

from ears import measure
from ears.audio import Audio

RATE = 44100
NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------


def sine(freq, seconds, amp=0.5, rate=RATE, phase=0.0):
    t = np.arange(int(round(seconds * rate))) / rate
    return amp * np.sin(2.0 * np.pi * freq * t + phase)


def mono(x, rate=RATE):
    return Audio(np.asarray(x, dtype=np.float64)[:, None], rate)


def stereo(left, right=None, rate=RATE):
    right = left if right is None else right
    return Audio(np.stack([left, right], axis=1), rate)


def faded(x, ms=50.0, rate=RATE):
    """Hann fades at both ends, so the cut of a test tone adds no broadband click."""
    n = min(len(x) // 2, int(ms * rate / 1000.0))
    out = np.array(x, dtype=np.float64)
    ramp = 0.5 - 0.5 * np.cos(np.pi * np.arange(n) / n)
    out[:n] *= ramp
    out[len(out) - n:] *= ramp[::-1]
    return out


def peaking(x, freq, gain_db, q, rate=RATE):
    """RBJ peaking EQ."""
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * freq / rate
    alpha = np.sin(w0) / (2.0 * q)
    b = [1 + alpha * a, -2 * np.cos(w0), 1 - alpha * a]
    den = [1 + alpha / a, -2 * np.cos(w0), 1 - alpha / a]
    return signal.lfilter(b, den, x)


def lowpassed_noise(seed, seconds, cutoff, amp, rate=RATE):
    rng = np.random.default_rng(seed)
    sos = signal.butter(4, cutoff, btype="low", fs=rate, output="sos")
    return amp * signal.sosfilt(sos, rng.standard_normal(int(seconds * rate)))


def note(freq, rate=RATE, length=0.3, attack=0.003, decay=0.12, release=0.04, amp=0.5):
    """A plucked sine: short attack, exponential decay, smooth release (no click at the end)."""
    n = int(length * rate)
    t = np.arange(n) / rate
    envelope = np.minimum(1.0, t / attack) * np.exp(-t / decay) * np.clip((length - t) / release, 0.0, 1.0)
    return amp * np.sin(2.0 * np.pi * freq * t) * envelope


def place(sound, times, seconds, rate=RATE):
    out = np.zeros(int(seconds * rate))
    for when in times:
        start = int(round(when * rate))
        end = min(len(out), start + len(sound))
        if end > start:
            out[start:end] += sound[:end - start]
    return out


def assert_plain(value, path="result"):
    """JSON-safe: only dict/list/str/bool/int/float/None, floats finite, no numpy scalars or arrays."""
    if isinstance(value, dict):
        for key, item in value.items():
            assert isinstance(key, str), "{0}: non-string key {1!r}".format(path, key)
            assert_plain(item, "{0}.{1}".format(path, key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_plain(item, "{0}[{1}]".format(path, index))
    elif value is None or type(value) in (str, bool, int):
        return
    else:
        assert type(value) is float, "{0}: {1!r} is {2}, not a plain float".format(path, value, type(value).__name__)
        assert math.isfinite(value), "{0}: not finite".format(path)
    json.dumps(value, allow_nan=False)


# ---------------------------------------------------------------------------
# levels
# ---------------------------------------------------------------------------


def test_levels_of_a_sine():
    result = measure.levels(mono(sine(1000, 1.0, amp=0.5)))
    assert result["peak_dbfs"] == pytest.approx(-6.02, abs=0.02)
    assert result["rms_dbfs"] == pytest.approx(-9.03, abs=0.02)
    assert result["crest_db"] == pytest.approx(3.01, abs=0.03)
    assert abs(result["dc_offset"]) < 1e-6
    assert result["silent"] is False
    assert_plain(result)


def test_levels_dc_offset_and_peak_over_channels():
    left = sine(1000, 1.0, amp=0.1) + 0.2
    right = sine(1000, 1.0, amp=0.4)
    result = measure.levels(stereo(left, right))
    assert result["dc_offset"] == pytest.approx(0.2, abs=1e-6)
    assert result["peak_dbfs"] == pytest.approx(20 * math.log10(0.4), abs=0.01)           # the right channel's peak, not the left's 0.3


def test_levels_silence_and_very_quiet_files_are_silent():
    zeros = measure.levels(stereo(np.zeros(1000)))
    assert zeros["silent"] is True and zeros["peak_dbfs"] == -200.0 and zeros["rms_dbfs"] == -200.0 and zeros["crest_db"] == 0.0
    quiet = measure.levels(mono(sine(1000, 1.0, amp=10 ** (-90 / 20.0))))
    assert quiet["silent"] is True
    assert measure.levels(mono(sine(1000, 1.0, amp=10 ** (-70 / 20.0))))["silent"] is False
    assert measure.levels(mono(np.zeros(0)))["silent"] is True
    assert_plain(zeros)


# ---------------------------------------------------------------------------
# band_levels and third_octave_levels
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("freq,band", [(30, "sub"), (100, "low"), (1000, "low_mid"), (4000, "high_mid"), (10000, "high")])
def test_pure_tone_lands_in_its_band(freq, band):
    result = measure.band_levels(stereo(sine(freq, 3.0, amp=0.5)))
    assert_plain(result)
    assert list(result["bands"]) == ["sub", "low", "low_mid", "high_mid", "high"]
    assert result["bands"][band]["share"] > 99.9
    assert result["bands"][band]["db"] == pytest.approx(-9.03, abs=0.1)
    assert result["total_db"] == pytest.approx(-9.03, abs=0.1)
    for other, values in result["bands"].items():
        if other != band:
            assert values["db"] < -55.0


def test_band_shares_sum_to_100_and_follow_the_spectrum():
    # equal energy below and above 1 kHz: 500 Hz and 3 kHz sines of the same amplitude
    result = measure.band_levels(mono(sine(500, 3.0, amp=0.3) + sine(3000, 3.0, amp=0.3)))
    shares = dict((name, values["share"]) for name, values in result["bands"].items())
    assert sum(shares.values()) == pytest.approx(100.0, abs=0.01)
    assert shares["low_mid"] == pytest.approx(50.0, abs=1.0)
    assert shares["high_mid"] == pytest.approx(50.0, abs=1.0)


def test_band_levels_custom_bands_silence_and_dc():
    custom = measure.band_levels(mono(sine(1000, 2.0)), bands={"voice": (300, 3400), "rest": (3400, None)})
    assert list(custom["bands"]) == ["voice", "rest"]
    assert custom["bands"]["voice"]["share"] > 99.9
    triples = measure.band_levels(mono(sine(1000, 2.0)), bands=[("a", 0, 500), ("b", 500, 2000)])
    assert triples["bands"]["b"]["share"] > 99.9
    silent = measure.band_levels(mono(np.zeros(RATE)))
    assert all(v["db"] == -200.0 and v["share"] == 0.0 for v in silent["bands"].values()) and silent["total_db"] == -200.0
    # DC is not sub-bass
    offset = measure.band_levels(mono(sine(1000, 2.0) + 0.3))
    assert offset["bands"]["sub"]["db"] < -60.0
    with pytest.raises(ValueError):
        measure.band_levels(mono(sine(1000, 1.0)), bands={"bad": (500, 100)})


@pytest.mark.parametrize("freq,center", [(31.5, 31.5), (63, 63.0), (1000, 1000.0), (3150, 3150.0), (8000, 8000.0)])
def test_third_octave_pure_tone(freq, center):
    result = measure.third_octave_levels(stereo(sine(freq, 4.0, amp=0.5)))
    assert_plain(result)
    index = int(np.argmax(result["db"]))
    assert result["centers"][index] == center
    assert result["db"][index] == pytest.approx(-9.03, abs=0.1)
    assert result["relative_db"][index] == pytest.approx(0.0, abs=0.1)
    for j, level in enumerate(result["db"]):
        if abs(j - index) >= 2:                 # two bands away is more than a third of an octave from the tone
            assert level < result["db"][index] - 35.0


def test_third_octave_grid_and_relative_levels():
    result = measure.third_octave_levels(mono(lowpassed_noise(1, 3.0, 8000, 0.1)))
    assert len(result["centers"]) == len(result["db"]) == len(result["relative_db"]) == 29
    assert result["centers"][0] == 25.0 and result["centers"][-1] == 16000.0
    assert 1000.0 in result["centers"] and 31.5 in result["centers"] and 3150.0 in result["centers"]
    for level, relative in zip(result["db"], result["relative_db"]):
        assert relative == pytest.approx(level - result["total_db"], abs=1e-9)
    narrow = measure.third_octave_levels(mono(sine(1000, 1.0)), low=500.0, high=2000.0)
    assert narrow["centers"] == [500.0, 630.0, 800.0, 1000.0, 1250.0, 1600.0, 2000.0]
    silent = measure.third_octave_levels(mono(np.zeros(RATE)))
    assert set(silent["db"]) == {-200.0} and set(silent["relative_db"]) == {-200.0}
    assert measure.third_octave_levels(mono(sine(1000, 1.0)), low=30000.0, high=40000.0)["centers"] == []


def test_third_octave_resolves_a_6_db_boost_at_3_khz():
    """The 3150 Hz band rises by about 6 dB when a pad-like stem gets a +6 dB bell at 3 kHz; its neighbours rise much less."""
    pad = lowpassed_noise(2, 6.0, 4000, 0.1)
    boosted = peaking(pad, 3162.0, 6.0, q=2.0)
    before = measure.third_octave_levels(mono(pad))
    after = measure.third_octave_levels(mono(boosted))
    delta = dict(zip(before["centers"], np.array(after["db"]) - np.array(before["db"])))
    assert delta[3150.0] == pytest.approx(5.6, abs=1.0)
    assert 2500.0 in delta and 4000.0 in delta
    assert delta[2500.0] < delta[3150.0] - 1.5 and delta[4000.0] < delta[3150.0] - 1.5
    for center, change in delta.items():
        if center <= 1000.0 or center >= 8000.0:
            assert abs(change) < 1.0, (center, change)
    # loudness-matched comparison: relative levels show the same bump
    relative = dict(zip(before["centers"], np.array(after["relative_db"]) - np.array(before["relative_db"])))
    assert relative[3150.0] > 3.0 and relative[3150.0] > relative[1000.0] + 3.0


# ---------------------------------------------------------------------------
# mono_sub and stereo
# ---------------------------------------------------------------------------


def test_mono_sub_identical_channels_lose_nothing():
    result = measure.mono_sub(stereo(faded(sine(60, 3.0))))
    assert_plain(result)
    assert result["loss_db"] == pytest.approx(0.0, abs=0.01)
    assert result["correlation"] == pytest.approx(1.0, abs=1e-6)
    assert result["level_db"] == pytest.approx(-9.06, abs=0.4)


def test_mono_sub_decorrelated_sub_loses_3_db():
    left = lowpassed_noise(3, 4.0, 90, 0.4)
    right = lowpassed_noise(4, 4.0, 90, 0.4)
    result = measure.mono_sub(stereo(left, right))
    assert result["loss_db"] == pytest.approx(3.01, abs=0.4)
    assert abs(result["correlation"]) < 0.15
    # a 90 degree phase shift between two sines is decorrelated too
    quadrature = measure.mono_sub(stereo(faded(sine(60, 3.0)), faded(sine(60, 3.0, phase=np.pi / 2))))
    assert quadrature["loss_db"] == pytest.approx(3.01, abs=0.1)
    assert abs(quadrature["correlation"]) < 0.05


def test_mono_sub_polarity_inverted_sub_is_capped_at_60_db():
    tone = faded(sine(60, 3.0))
    result = measure.mono_sub(stereo(tone, -tone))
    assert result["loss_db"] == 60.0
    assert result["correlation"] < -0.999


def test_mono_sub_ignores_content_above_the_cutoff_and_handles_mono():
    highs = faded(sine(1000, 3.0))
    result = measure.mono_sub(stereo(highs, -highs))          # out of phase, but nothing below 120 Hz
    assert result["level_db"] < -60.0                         # a caller can see there is no sub to judge
    # a mono file loses nothing
    mono_result = measure.mono_sub(mono(faded(sine(60, 3.0))))
    assert mono_result["loss_db"] == 0.0 and mono_result["correlation"] == 1.0
    assert measure.mono_sub(stereo(np.zeros(RATE)))["loss_db"] == 0.0
    # the cutoff matters: a 200 Hz inverted tone is above 120 Hz but below 400
    tone = faded(sine(200, 3.0))
    assert measure.mono_sub(stereo(tone, -tone), cutoff=120.0)["level_db"] < -20.0
    assert measure.mono_sub(stereo(tone, -tone), cutoff=400.0)["loss_db"] == 60.0


def test_stereo_correlation_and_width():
    tone = sine(440, 2.0)
    identical = measure.stereo(stereo(tone))
    assert identical["correlation"] == pytest.approx(1.0, abs=1e-9) and identical["width"] == pytest.approx(0.0, abs=1e-9)
    inverted = measure.stereo(stereo(tone, -tone))
    assert inverted["correlation"] == pytest.approx(-1.0, abs=1e-9) and inverted["width"] >= 100.0
    rng = np.random.default_rng(5)
    wide = measure.stereo(stereo(0.2 * rng.standard_normal(RATE * 2), 0.2 * rng.standard_normal(RATE * 2)))
    assert abs(wide["correlation"]) < 0.02 and wide["width"] == pytest.approx(1.0, abs=0.03)
    hard_left = measure.stereo(stereo(tone, np.zeros_like(tone)))
    assert hard_left["correlation"] == 0.0 and hard_left["width"] == pytest.approx(1.0, abs=1e-9)
    assert measure.stereo(mono(tone)) == {"correlation": 1.0, "width": 0.0}
    assert measure.stereo(stereo(np.zeros(100))) == {"correlation": 1.0, "width": 0.0}
    for result in (identical, inverted, wide, hard_left):
        assert_plain(result)


# ---------------------------------------------------------------------------
# phone
# ---------------------------------------------------------------------------


def test_phone_removes_a_low_sweep_and_keeps_a_kilohertz_tone():
    t = np.arange(int(4.0 * RATE)) / RATE
    sweep = 0.5 * signal.chirp(t, 80.0, 4.0, 35.0, method="linear")
    out, stats = measure.phone(mono(sweep))
    assert_plain(stats)
    assert stats["survival_share"] < 1.0
    assert stats["survival_db"] < -20.0
    assert out.channels == 1 and out.rate == RATE and out.frames == len(sweep)
    tone = sine(1000, 2.0)
    kept, tone_stats = measure.phone(stereo(tone))
    assert tone_stats["survival_share"] > 99.9
    assert abs(tone_stats["survival_db"]) < 0.01
    assert kept.channels == 1


def test_phone_cutoff_input_untouched_and_edge_cases():
    original = stereo(sine(150, 1.0), sine(150, 1.0))
    before = original.samples.copy()
    _, stats = measure.phone(original, highpass_hz=200.0)
    assert np.array_equal(original.samples, before)
    assert stats["survival_share"] < 50.0                    # 150 Hz is below the 200 Hz corner
    _, higher = measure.phone(mono(sine(300, 1.0)), highpass_hz=500.0)
    assert higher["survival_share"] < 10.0
    _, at_corner = measure.phone(mono(sine(200, 1.0)))
    assert at_corner["survival_db"] == pytest.approx(-3.0, abs=0.2)         # Butterworth: -3 dB at the corner
    _, silent = measure.phone(mono(np.zeros(1000)))
    assert silent == {"survival_db": 0.0, "survival_share": 100.0}
    _, cancelled = measure.phone(stereo(sine(1000, 1.0), -sine(1000, 1.0)))   # mono sum is silent
    assert cancelled == {"survival_db": 0.0, "survival_share": 100.0}
    with pytest.raises(ValueError):
        measure.phone(mono(sine(1000, 1.0)), highpass_hz=0.0)


# ---------------------------------------------------------------------------
# reactivity
# ---------------------------------------------------------------------------


def _smooth_gate(seconds, rate_hz=0.5, rate=RATE):
    """Raised-cosine pulses (no clicks). The analyser's 200 ms release smooths anything faster than about 1 Hz."""
    t = np.arange(int(seconds * rate)) / rate
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * rate_hz * t)


def test_reactivity_a_pulsed_sub_moves_only_the_low_bands():
    pulsed = sine(50, 8.0, amp=0.5) * _smooth_gate(8.0)
    result = measure.reactivity(mono(pulsed))
    assert_plain(result)
    assert list(result) == ["sub", "low_mid", "high_mid", "treble"]
    assert set(result["sub"]) == {"mean", "std", "p5", "p95", "movement"}
    assert result["sub"]["movement"] > 0.3
    assert result["sub"]["movement"] == pytest.approx(result["sub"]["p95"] - result["sub"]["p5"], abs=1e-12)
    assert result["treble"]["movement"] == 0.0
    assert result["high_mid"]["movement"] < 0.02
    # window leakage (Blackman, 2048 points) lets a 50 Hz tone reach into the bins just above 80 Hz, but far less than the sub band
    assert result["low_mid"]["movement"] < 0.25 * result["sub"]["movement"]
    for values in result.values():
        assert 0.0 <= values["p5"] <= values["mean"] <= values["p95"] <= 1.0


def test_reactivity_silence_and_steady_tones_do_not_move():
    silent = measure.reactivity(mono(np.zeros(RATE * 3)))
    for values in silent.values():
        assert values == {"mean": 0.0, "std": 0.0, "p5": 0.0, "p95": 0.0, "movement": 0.0}
    steady = measure.reactivity(mono(sine(1000, 5.0, amp=0.2)))
    assert all(values["movement"] < 0.01 for values in steady.values())
    assert steady["high_mid"]["mean"] > 0.0


def test_reactivity_follows_the_analyser_settings():
    loud = measure.reactivity(mono(sine(1000, 3.0, amp=0.2)))["high_mid"]["mean"]
    quiet = measure.reactivity(mono(sine(1000, 3.0, amp=0.002)))["high_mid"]["mean"]
    assert loud > quiet > 0.0                                 # 40 dB quieter reads lower on the -90..-20 dB byte scale
    custom = {"fft_size": 4096, "bands": {"tone": [800, 1200]}, "min_db": -100, "max_db": -10}
    result = measure.reactivity(mono(sine(1000, 3.0, amp=0.2)), custom)
    assert list(result) == ["tone"] and result["tone"]["mean"] > 0.05          # a few of the band's 37 bins carry the tone
    assert measure.reactivity(mono(sine(3000, 3.0, amp=0.2)), custom)["tone"]["mean"] == 0.0
    # 0.5 * (L + R): an out-of-phase pair sums to silence
    cancelled = measure.reactivity(stereo(sine(1000, 2.0), -sine(1000, 2.0)))
    assert all(values["mean"] == 0.0 for values in cancelled.values())
    # the envelope: a 200 ms release keeps the band up after a note stops, a 5 ms release does not
    gate = np.concatenate([np.zeros(RATE), sine(1000, 1.0, amp=0.3), np.zeros(RATE)])
    slow = measure.reactivity(mono(gate))["high_mid"]
    fast = measure.reactivity(mono(gate), {"release_ms": 5.0})["high_mid"]
    assert slow["p95"] > 0.1 and slow["p5"] == 0.0 and slow["std"] > 0.02
    assert slow["mean"] > 1.05 * fast["mean"]


def test_reactivity_treble_band_sees_noise_bursts_in_it():
    rng = np.random.default_rng(6)
    sos = signal.butter(4, 6000, btype="high", fs=RATE, output="sos")
    noise = signal.sosfilt(sos, rng.standard_normal(RATE * 8)) * 0.2 * _smooth_gate(8.0)
    result = measure.reactivity(mono(noise))
    assert result["treble"]["movement"] > 0.15
    assert result["sub"]["movement"] < 0.05


# ---------------------------------------------------------------------------
# masking
# ---------------------------------------------------------------------------


def test_masking_finds_stems_that_share_a_band():
    a = mono(sine(1000, 6.0, amp=0.3))
    b = mono(sine(1000, 6.0, amp=0.1) + sine(250, 6.0, amp=0.1))
    found = measure.masking({"a": a, "b": b})
    assert_plain(found)
    assert found[0]["a"] == "a" and found[0]["b"] == "b" and found[0]["band_hz"] == 1000.0
    assert found[0]["overlap_share"] > 95.0
    assert set(found[0]) >= {"a", "b", "band_hz", "overlap_share"}
    assert all(item["band_hz"] != 250.0 for item in found)    # 'a' has nothing at 250 Hz


def test_masking_ignores_stems_in_different_bands_and_different_times():
    low = mono(sine(250, 6.0, amp=0.3))
    high = mono(sine(4000, 6.0, amp=0.3))
    assert measure.masking({"low": low, "high": high}) == []
    first_half = np.concatenate([sine(1000, 3.0, amp=0.3), np.zeros(3 * RATE)])
    second_half = np.concatenate([np.zeros(3 * RATE), sine(1000, 3.0, amp=0.3)])
    alternating = measure.masking({"x": mono(faded(first_half, 20)), "y": mono(faded(second_half, 20))})
    assert all(item["overlap_share"] < 10.0 for item in alternating)
    # partial overlap: the second stem only plays for the last third
    tail = np.concatenate([np.zeros(4 * RATE), sine(1000, 2.0, amp=0.3)])
    partial = measure.masking({"x": mono(sine(1000, 6.0, amp=0.3)), "y": mono(faded(tail, 20))})
    assert partial[0]["band_hz"] == 1000.0 and 25.0 < partial[0]["overlap_share"] < 40.0


def test_masking_sorts_limits_and_validates():
    rng = np.random.default_rng(7)
    parts = dict(("s{0}".format(i), mono(0.1 * rng.standard_normal(RATE * 3))) for i in range(4))
    found = measure.masking(parts, top=5)
    assert len(found) == 5
    shares = [item["overlap_share"] for item in found]
    assert shares == sorted(shares, reverse=True)
    assert measure.masking({"only": parts["s0"]}) == []
    with pytest.raises(ValueError):
        measure.masking({"a": mono(np.zeros(RATE)), "b": Audio(np.zeros((RATE, 1)), 48000)})
    # a quiet band never counts: -60 dB gate
    quiet = measure.masking({"a": mono(sine(1000, 3.0, amp=0.0001)), "b": mono(sine(1000, 3.0, amp=0.0001))})
    assert quiet == []


# ---------------------------------------------------------------------------
# key_estimate
# ---------------------------------------------------------------------------

KEY_RATE = 22050
PARTIALS = {
    "harmonic": [(1, 1.0), (2, 0.5), (3, 0.36), (4, 0.25), (5, 0.13), (6, 0.08)],
    "saw": [(h, 1.0 / h) for h in range(1, 13)],
    # strongly distorted / FM-like: the 3rd and 5th harmonic are only 4.4 and 6 dB under the fundamental
    "distorted": [(1, 1.0), (2, 0.5), (3, 0.6), (4, 0.3), (5, 0.5), (6, 0.2), (7, 0.3), (8, 0.15)],
}


def _tone(freq, seconds, partials, rate=KEY_RATE, clip=None):
    n = int(seconds * rate)
    t = np.arange(n) / rate
    if clip:
        x = np.tanh(clip * np.sin(2.0 * np.pi * freq * t))
    else:
        x = sum(a * np.sin(2.0 * np.pi * h * freq * t + 0.3 * h) for h, a in partials if h * freq < 0.45 * rate)
    envelope = np.ones(n)
    attack, release = int(0.01 * rate), int(0.05 * rate)
    envelope[:attack] = np.linspace(0.0, 1.0, attack)
    envelope[n - release:] *= np.linspace(1.0, 0.0, release)
    return x * envelope


def render_progression(chords, timbre="harmonic", clip=None, a4=440.0, transpose=0, cycles=2, bass_level=1.0, chord_seconds=2.0):
    """chords: [(root pitch class, is_minor)], each held for chord_seconds with a root-note bass and a triad on top.

    The bass plays the chord root on every beat at 120 BPM; the chord is voiced around A3..G#4. Returns mono samples.
    """
    partials = PARTIALS[timbre]
    total = chord_seconds * len(chords) * cycles
    out = np.zeros(int(total * KEY_RATE) + KEY_RATE)

    def put(sound, when):
        start = int(round(when * KEY_RATE))
        out[start:start + len(sound)] += sound[:max(0, len(out) - start)]

    def hz(midi):
        return a4 * 2.0 ** ((midi - 69) / 12.0)

    for cycle in range(cycles):
        for index, (root, minor) in enumerate(chords):
            start = (cycle * len(chords) + index) * chord_seconds
            root = (root + transpose) % 12
            base = 57 + ((root - 57) % 12)
            if base > 64:
                base -= 12
            for interval in (0, 3 if minor else 4, 7):
                put(0.4 * _tone(hz(base + interval), chord_seconds, partials, clip=clip), start)
            bass = 33 + ((root - 33) % 12)
            for beat in range(int(chord_seconds / 0.5)):
                put(bass_level * _tone(hz(bass), 0.45, partials, clip=clip), start + beat * 0.5)
    out = out[:int(total * KEY_RATE)]
    return out / np.max(np.abs(out)) * 0.5


A_MINOR = [(9, True), (2, True), (4, False), (9, True)]        # Am  Dm  E  Am
C_MAJOR = [(0, False), (5, False), (7, False), (0, False)]     # C  F  G  C


def _key(x, **kwargs):
    return measure.key_estimate(Audio(x[:, None], KEY_RATE), **kwargs)


def _assert_key_result(result, key, tonic, mode):
    assert_plain(result)
    assert result["key"] == key and result["tonic"] == tonic and result["mode"] == mode
    assert len(result["chroma"]) == 12 and sum(result["chroma"]) == pytest.approx(1.0, abs=1e-9)
    assert min(result["chroma"]) >= 0.0
    assert -1.0 <= result["confidence"] <= 1.0
    assert result["second"]["key"] != result["key"]
    assert result["second"]["confidence"] <= result["confidence"]


@pytest.mark.parametrize("timbre,clip", [("harmonic", None), ("saw", None), ("distorted", None), ("harmonic", 8.0)],
                         ids=["harmonic", "sawtooth", "distorted-5th-at-minus-6-dB", "tanh-clipped-sines"])
def test_key_a_minor_progression_with_an_a_centred_bass(timbre, clip):
    """Am Dm E Am over a root bass reads A minor, also with tones whose overtones (the C# of an A) are strong."""
    result = _key(render_progression(A_MINOR, timbre=timbre, clip=clip))
    _assert_key_result(result, "A minor", "A", "minor")
    assert result["confidence"] > 0.75
    assert result["confidence"] - result["second"]["confidence"] > 0.02
    chroma = result["chroma"]
    assert chroma[9] == max(chroma) or chroma[9] >= sorted(chroma)[-2]      # A is the strongest or second strongest class
    assert chroma[0] > chroma[1]                                            # C (minor third) over C# (the A's fifth-and-a-third partial)


def test_key_c_major_is_not_called_a_minor():
    result = _key(render_progression(C_MAJOR))
    _assert_key_result(result, "C major", "C", "major")
    assert result["confidence"] > 0.75
    distorted = _key(render_progression(C_MAJOR, timbre="distorted"))
    assert distorted["key"] == "C major"


def test_key_transposition_naming_and_tuning():
    f_sharp_minor = _key(render_progression(A_MINOR, transpose=-3))
    _assert_key_result(f_sharp_minor, "F# minor", "F#", "minor")
    d_major = _key(render_progression(C_MAJOR, transpose=2))
    assert d_major["key"] == "D major"
    # A4 = 432 Hz music read against a 432 Hz reference gives the same answer
    retuned = _key(render_progression(A_MINOR, a4=432.0), a4_hz=432.0)
    assert retuned["key"] == "A minor"
    # opening weight is a tie-breaker, not a requirement
    assert _key(render_progression(A_MINOR), start_weight=0.0)["key"] == "A minor"


def test_key_no_tonal_content():
    silent = measure.key_estimate(mono(np.zeros(RATE * 2)))
    assert silent["key"] is None and silent["tonic"] is None and silent["mode"] is None
    assert silent["confidence"] == 0.0 and silent["chroma"] == [0.0] * 12
    assert silent["second"] == {"key": None, "confidence": 0.0}
    assert_plain(silent)
    short = measure.key_estimate(mono(sine(440, 0.2)))        # shorter than one analysis frame
    assert short["tonic"] == "A"                              # a lone A is still an A of some key
    assert_plain(short)


# ---------------------------------------------------------------------------
# onsets and grid_stats
# ---------------------------------------------------------------------------

EIGHTHS = 0.5 + 0.25 * np.arange(16)         # 16 events at 120 BPM eighth notes, the first at 0.5 s


def _assert_onsets(found, truth, tolerance=0.005):
    assert isinstance(found, list) and all(type(value) is float for value in found)
    assert len(found) == len(truth), "found {0}".format(np.round(found, 4))
    assert np.max(np.abs(np.asarray(found) - np.asarray(truth))) <= tolerance


def test_onsets_sixteen_clicks():
    clicks = np.zeros(int(5.5 * RATE))
    clicks[np.round(EIGHTHS * RATE).astype(int)] = 0.9
    _assert_onsets(measure.onsets(mono(clicks)), EIGHTHS, 0.001)
    _assert_onsets(measure.onsets(stereo(clicks, 0.5 * clicks)), EIGHTHS, 0.001)


@pytest.mark.parametrize("freq", [55.0, 220.0, 1760.0])
def test_onsets_sixteen_notes(freq):
    notes = place(note(freq), EIGHTHS, 5.5)
    _assert_onsets(measure.onsets(mono(notes)), EIGHTHS)


def test_onsets_noise_bursts_and_other_sample_rates():
    rng = np.random.default_rng(8)
    burst = signal.sosfilt(signal.butter(4, 3000, btype="high", fs=RATE, output="sos"), rng.standard_normal(int(0.04 * RATE)))
    burst = 0.4 * burst * np.exp(-np.arange(len(burst)) / RATE / 0.01)
    _assert_onsets(measure.onsets(mono(place(burst, EIGHTHS, 5.5))), EIGHTHS)
    rate = 48000
    notes = place(note(330.0, rate=rate), EIGHTHS, 5.5, rate=rate)
    _assert_onsets(measure.onsets(Audio(notes[:, None], rate)), EIGHTHS)


def test_onsets_hats_over_a_sustained_pad():
    rng = np.random.default_rng(9)
    hat = signal.sosfilt(signal.butter(4, 7000, btype="high", fs=RATE, output="sos"), rng.standard_normal(int(0.04 * RATE)))
    hat = 0.3 * hat * np.exp(-np.arange(len(hat)) / RATE / 0.01)
    pad = 0.15 * (sine(220, 5.5, amp=1.0) + sine(330, 5.5, amp=1.0))
    found = measure.onsets(mono(place(hat, EIGHTHS, 5.5) + pad))
    found = [value for value in found if value > 0.05]            # the pad itself starts at t = 0
    _assert_onsets(found, EIGHTHS)


def test_onsets_silence_steady_tone_and_noise_floor():
    assert measure.onsets(mono(np.zeros(RATE * 2))) == []
    assert measure.onsets(mono(np.zeros(100))) == []
    steady = measure.onsets(mono(sine(440, 3.0)))
    assert all(value < 0.05 for value in steady)                  # only the start of the sound, if anything
    rng = np.random.default_rng(10)
    assert measure.onsets(mono(rng.standard_normal(RATE * 3) * 10 ** (-70 / 20.0))) == []
    pad = 0.15 * (sine(220, 5.0, amp=1.0) + sine(330, 5.0, amp=1.0))
    assert all(value < 0.05 for value in measure.onsets(mono(pad)))   # two partials beating inside a window are not onsets


def test_onset_of_a_legato_pitch_change():
    """No energy rise at a legato note change: the spectral flux alone places it, to within a few milliseconds."""
    t = np.arange(2 * RATE) / RATE
    legato = np.where(t < 1.0, 0.4 * np.sin(2 * np.pi * 330 * t), 0.4 * np.sin(2 * np.pi * 440 * t))
    legato = faded(legato * np.minimum(1.0, t / 0.01), 20.0)
    found = [value for value in measure.onsets(mono(legato)) if value > 0.1]
    _assert_onsets(found, [1.0], 0.005)


def test_onset_at_the_very_start_of_a_file():
    clicks = np.zeros(2 * RATE)
    clicks[0] = 0.9
    clicks[RATE // 2] = 0.9
    found = measure.onsets(mono(clicks))
    _assert_onsets(found, [0.0, 0.5], 0.002)


def test_grid_stats_for_a_click_one_54_ms_late():
    times = EIGHTHS.copy()
    times[5] += 0.054
    clicks = np.zeros(int(5.5 * RATE))
    clicks[np.round(times * RATE).astype(int)] = 0.9
    found = measure.onsets(mono(clicks))
    stats = measure.grid_stats(found, 120.0, grid=8, offset=0.5)
    assert_plain(stats)
    assert stats["count"] == 16
    assert stats["max_ms"] == pytest.approx(54.0, abs=1.0)
    assert stats["mean_abs_ms"] == pytest.approx(54.0 / 16.0, abs=0.3)
    assert stats["on_grid_share"] == pytest.approx(15.0 / 16.0, abs=1e-9)
    assert stats["late_ms_median"] == pytest.approx(0.0, abs=0.5)
    assert stats["worst"][0]["deviation_ms"] == pytest.approx(54.0, abs=1.0)
    assert stats["worst"][0]["time"] == pytest.approx(times[5], abs=0.002)


def test_grid_stats_arithmetic():
    # sixteenth grid at 120 BPM is 125 ms
    exact = measure.grid_stats([0.0, 0.125, 0.25, 0.5, 1.0], 120.0)
    assert exact["count"] == 5 and exact["max_ms"] == pytest.approx(0.0, abs=1e-9) and exact["on_grid_share"] == 1.0
    shifted = measure.grid_stats([0.007, 0.132, 0.257, 0.507], 120.0)          # all 7 ms late
    assert shifted["late_ms_median"] == pytest.approx(7.0, abs=1e-6) and shifted["mean_abs_ms"] == pytest.approx(7.0, abs=1e-6)
    assert shifted["on_grid_share"] == 1.0
    early = measure.grid_stats([-0.004 + 0.125, 0.25 - 0.004], 120.0)
    assert early["late_ms_median"] == pytest.approx(-4.0, abs=1e-6)
    assert measure.grid_stats([0.0, 0.015], 120.0, tolerance_ms=20.0)["on_grid_share"] == 1.0
    assert measure.grid_stats([0.0, 0.015], 120.0, tolerance_ms=10.0)["on_grid_share"] == 0.5
    offset = measure.grid_stats([1.0, 1.125, 1.25], 120.0, offset=1.0)
    assert offset["max_ms"] == pytest.approx(0.0, abs=1e-9)
    triplets = measure.grid_stats([0.0, 1.0 / 6.0, 1.0 / 3.0], 120.0, grid=12)        # eighth-note triplets: 1/6 s
    assert triplets["max_ms"] == pytest.approx(0.0, abs=1e-6)
    # nearest line, not the previous one: 100 ms after a line is 25 ms before the next
    assert measure.grid_stats([0.1], 120.0)["late_ms_median"] == pytest.approx(-25.0, abs=1e-6)
    empty = measure.grid_stats([], 120.0)
    assert empty["count"] == 0 and empty["on_grid_share"] == 0.0 and empty["worst"] == []
    assert measure.grid_stats(np.array([0.0, 0.125]), 120.0)["count"] == 2           # arrays are fine
    with pytest.raises(ValueError):
        measure.grid_stats([0.0], 0.0)
    with pytest.raises(ValueError):
        measure.grid_stats([0.0], 120.0, grid=0)


# ---------------------------------------------------------------------------
# Whole-stem smoke test
# ---------------------------------------------------------------------------


def test_every_function_returns_plain_json_and_a_whole_stem_is_measured_quickly():
    rate = 48000
    seconds = 30
    rng = np.random.default_rng(11)
    t = np.arange(seconds * rate) / rate
    left = 0.2 * np.sin(2 * np.pi * 110 * t) + 0.05 * rng.standard_normal(len(t))
    right = 0.2 * np.sin(2 * np.pi * 110 * t + 0.4) + 0.05 * rng.standard_normal(len(t))
    hits = place(note(800.0, rate=rate, length=0.2, attack=0.002, decay=0.05, amp=0.6), np.arange(0.0, seconds - 0.3, 0.25), seconds, rate=rate)
    stem = Audio(np.stack([left + hits, right + hits], axis=1), rate)
    other = Audio(np.stack([right, left], axis=1), rate)
    started = time.perf_counter()
    results = {
        "levels": measure.levels(stem),
        "band_levels": measure.band_levels(stem),
        "third_octave_levels": measure.third_octave_levels(stem),
        "mono_sub": measure.mono_sub(stem),
        "stereo": measure.stereo(stem),
        "key_estimate": measure.key_estimate(stem),
        "onsets": measure.onsets(stem),
        "grid_stats": measure.grid_stats(measure.onsets(stem), 240.0, 16),
        "reactivity": measure.reactivity(stem),
        "phone": measure.phone(stem)[1],
        "masking": measure.masking({"a": stem, "b": other}),
    }
    elapsed = time.perf_counter() - started
    for name, value in results.items():
        assert_plain(value, name)
    assert len(results["onsets"]) >= 100
    assert elapsed < 10.0, "measuring one 30 s stereo stem took {0:.1f} s".format(elapsed)
