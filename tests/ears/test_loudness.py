"""Unit tests for ears/loudness.py: BS.1770-4 / EBU R128 integrated loudness, loudness range (Tech 3342), true peak,
dual mono, and a cross-check against ffmpeg's ebur128 filter (skipped when ffmpeg is not installed).

Signals follow the EBU Tech 3341 test set where it applies: a stereo 1 kHz sine at -23 dBFS peak per channel reads
-23.0 LUFS because the 0.691 offset of the loudness formula cancels the K-weighting gain at 1 kHz.
"""
import json
import shutil
import math
import subprocess

import numpy as np
import pytest
from scipy import signal as sps

from ears import audio, loudness
from ears.audio import Audio

RATE = 48000


@pytest.fixture(autouse=True)
def remove_temp_files(tmp_path):
    yield
    shutil.rmtree(tmp_path, ignore_errors=True)


def sine(dbfs, seconds, freq=1000.0, rate=RATE, channels=2, phase=0.0):
    t = np.arange(int(round(seconds * rate))) / float(rate)
    x = 10 ** (dbfs / 20.0) * np.sin(2 * np.pi * freq * t + phase)
    return np.repeat(x[:, None], channels, axis=1) if channels > 1 else x[:, None]


def pink(seconds, rate, seed, level_db):
    """Pink-ish noise (Paul Kellet's filter) at an RMS level in dBFS."""
    white = np.random.default_rng(seed).standard_normal(int(seconds * rate))
    x = sps.lfilter([0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400], white)
    return x / np.sqrt(np.mean(x ** 2)) * 10 ** (level_db / 20.0)


# ---------------------------------------------------------------------------
# K-weighting
# ---------------------------------------------------------------------------


def test_k_weighting_coefficients_match_the_bs1770_table_at_48k():
    (shelf_b, shelf_a), (high_b, high_a) = loudness.k_weighting(48000)
    assert shelf_b == pytest.approx([1.53512485958697, -2.69169618940638, 1.19839281085285], abs=1e-9)
    assert shelf_a == pytest.approx([1.0, -1.69065929318241, 0.73248077421585], abs=1e-9)
    assert high_b == pytest.approx([1.0, -2.0, 1.0], abs=1e-12)
    assert high_a == pytest.approx([1.0, -1.99004745483398, 0.99007225036621], abs=1e-9)


@pytest.mark.parametrize("rate", [44100, 48000, 96000])
def test_k_weighting_response_is_the_same_curve_at_every_sample_rate(rate):
    (b1, a1), (b2, a2) = loudness.k_weighting(rate)

    def gain_db(freq):
        _, h1 = sps.freqz(b1, a1, worN=[2 * math.pi * freq / rate])
        _, h2 = sps.freqz(b2, a2, worN=[2 * math.pi * freq / rate])
        return 20 * math.log10(abs(h1[0] * h2[0]))

    assert gain_db(1000) == pytest.approx(0.69, abs=0.03)       # why the loudness formula has -0.691
    assert gain_db(10000) == pytest.approx(4.0, abs=0.1)        # the head-related shelf
    assert gain_db(5000) == pytest.approx(4.0, abs=0.1)
    assert gain_db(100) == pytest.approx(-1.13, abs=0.05)       # the RLB high-pass
    assert gain_db(38.0) == pytest.approx(-6.0, abs=0.1)
    assert gain_db(20.0) < -12.5


@pytest.mark.parametrize("freq", [50.0, 100.0, 1000.0, 5000.0, 10000.0])
def test_integrated_tone_loudness_follows_the_k_curve(freq):
    (b1, a1), (b2, a2) = loudness.k_weighting(RATE)
    _, h1 = sps.freqz(b1, a1, worN=[2 * math.pi * freq / RATE])
    _, h2 = sps.freqz(b2, a2, worN=[2 * math.pi * freq / RATE])
    expected = -0.691 + (-23.0) + 20 * math.log10(abs(h1[0] * h2[0]))      # two channels of half-power each
    assert loudness.integrated(sine(-23.0, 6.0, freq=freq), RATE) == pytest.approx(expected, abs=0.02)


# ---------------------------------------------------------------------------
# Integrated loudness: EBU Tech 3341 style cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dbfs, expected", [(-23.0, -23.0), (-33.0, -33.0), (-3.0, -3.0), (-50.0, -50.0), (-60.0, -60.0)])
@pytest.mark.parametrize("rate", [44100, 48000, 96000])
def test_stereo_1khz_sine_reads_its_level_in_lufs(dbfs, expected, rate):
    assert loudness.integrated(sine(dbfs, 20.0, rate=rate), rate) == pytest.approx(expected, abs=0.1)


def test_level_follows_gain_one_for_one():
    base = loudness.integrated(sine(-30.0, 10.0), RATE)
    assert loudness.integrated(sine(-20.0, 10.0), RATE) - base == pytest.approx(10.0, abs=1e-6)
    assert loudness.integrated(sine(-36.0, 10.0), RATE) - base == pytest.approx(-6.0, abs=1e-6)


def test_relative_gate_ignores_the_quiet_half():
    """Tech 3341 case 3: 20 s at -36 LUFS then 20 s at -23 LUFS. The -36 blocks sit 10 LU under the ungated mean."""
    signal = np.vstack([sine(-36.0, 20.0), sine(-23.0, 20.0)])
    assert loudness.integrated(signal, RATE) == pytest.approx(-23.0, abs=0.1)


def test_blocks_inside_the_relative_gate_still_count():
    signal = np.vstack([sine(-30.0, 20.0), sine(-23.0, 20.0)])           # 7 LU apart: both halves pass the gate
    expected = 10 * math.log10(0.5 * (10 ** -3.0 + 10 ** -2.3))          # energy mean of -30 and -23
    assert loudness.integrated(signal, RATE) == pytest.approx(expected, abs=0.1)
    assert loudness.integrated(signal, RATE) > -23.5 - 2.0


def test_absolute_gate_ignores_blocks_below_minus_70_lufs():
    quiet_then_loud = np.vstack([sine(-75.0, 20.0), sine(-23.0, 20.0)])
    assert loudness.integrated(quiet_then_loud, RATE) == pytest.approx(-23.0, abs=0.1)
    assert loudness.integrated(sine(-75.0, 20.0), RATE) == loudness.SILENCE         # everything gated out
    assert loudness.integrated(sine(-69.0, 20.0), RATE) == pytest.approx(-69.0, abs=0.1)
    assert loudness.integrated(sine(-71.0, 20.0), RATE) == loudness.SILENCE


def test_integrated_with_a_precomputed_k_filter_gives_the_same_number():
    signal = sine(-23.0, 5.0)
    weighted = loudness.k_filter(signal, RATE)
    assert loudness.integrated(signal, RATE, weighted=weighted) == loudness.integrated(signal, RATE)


def test_silence_and_too_short_signals_report_the_silence_value_not_minus_infinity():
    assert loudness.integrated(np.zeros((RATE * 5, 2)), RATE) == loudness.SILENCE == -200.0
    assert loudness.integrated(sine(-23.0, 0.3), RATE) == loudness.SILENCE         # shorter than one 400 ms block
    assert loudness.integrated(sine(-23.0, 0.4), RATE) == pytest.approx(-23.0, abs=0.1)
    assert loudness.integrated(np.zeros((10, 2)), RATE) == loudness.SILENCE
    assert math.isfinite(loudness.integrated(np.zeros((0, 2)), RATE))


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


def test_mono_is_measured_as_dual_mono():
    mono = sine(-23.0, 10.0, channels=1)
    assert loudness.integrated(mono, RATE) == pytest.approx(-23.0, abs=0.1)
    assert loudness.integrated(mono[:, 0], RATE) == loudness.integrated(mono, RATE)       # a 1-D array too
    one_channel = np.hstack([mono, np.zeros_like(mono)])                                  # the same sine on L only
    assert loudness.integrated(one_channel, RATE) == pytest.approx(-26.0, abs=0.1)
    assert loudness.integrated(mono, RATE) - loudness.integrated(one_channel, RATE) == pytest.approx(3.01, abs=0.02)


def test_channels_add_in_power_and_only_the_first_two_count():
    both = sine(-23.0, 10.0)
    assert loudness.integrated(both, RATE) - loudness.integrated(both[:, :1] * np.array([[1.0, 0.0]]), RATE) == pytest.approx(3.01, abs=0.02)
    three = np.hstack([both, sine(-3.0, 10.0)[:, :1]])                                   # a loud third channel is ignored
    assert loudness.integrated(three, RATE) == loudness.integrated(both, RATE)


# ---------------------------------------------------------------------------
# Momentary and short-term
# ---------------------------------------------------------------------------


def test_momentary_and_short_term_of_a_constant_tone_equal_the_integrated_value():
    signal = sine(-23.0, 10.0)
    momentary = loudness.momentary(signal, RATE)
    short = loudness.short_term(signal, RATE)
    assert np.allclose(momentary, momentary[0], atol=0.01) and np.allclose(short, short[0], atol=0.01)   # the first block carries the filter's start-up
    assert momentary[0] == pytest.approx(-23.0, abs=0.1) and short[0] == pytest.approx(-23.0, abs=0.1)


def test_window_counts_follow_the_hop():
    assert len(loudness.momentary(sine(-23.0, 1.0), RATE)) == 7             # 400 ms windows every 100 ms in 1 s
    assert len(loudness.short_term(sine(-23.0, 5.0), RATE)) == 21           # 3 s windows every 100 ms in 5 s
    assert len(loudness.short_term(sine(-23.0, 2.0), RATE)) == 0
    assert len(loudness.short_term(sine(-23.0, 5.0), RATE, step=1.0)) == 3
    assert len(loudness.momentary(sine(-23.0, 0.2), RATE)) == 0


def test_momentary_follows_a_level_step():
    signal = np.vstack([sine(-40.0, 3.0), sine(-20.0, 3.0)])
    momentary = loudness.momentary(signal, RATE)
    assert momentary[0] == pytest.approx(-40.0, abs=0.1) and momentary[-1] == pytest.approx(-20.0, abs=0.1)
    assert np.all(np.diff(momentary) >= -1e-9)                               # rises monotonically through the step


# ---------------------------------------------------------------------------
# Loudness range (Tech 3342)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("levels, expected", [
    ((-30.0, -20.0), 10.0),
    ((-35.0, -15.0), 20.0),
    ((-40.0, -30.0, -20.0), 20.0),
    ((-50.0, -35.0, -20.0, -35.0, -50.0), 15.0),       # the -50 LUFS parts fall under the relative gate (-20 LU)
    ((-23.0,), 0.0),
])
def test_loudness_range_of_stepped_tones(levels, expected):
    signal = np.vstack([sine(level, 20.0) for level in levels])
    assert loudness.loudness_range(signal, RATE) == pytest.approx(expected, abs=0.2)     # Tech 3342 allows +-1 LU


def test_loudness_range_of_signals_that_are_too_short_is_zero():
    assert loudness.loudness_range(sine(-23.0, 2.9), RATE) == 0.0
    assert loudness.loudness_range(np.zeros((RATE * 10, 2)), RATE) == 0.0
    assert loudness.loudness_range(np.vstack([sine(-23.0, 1.0), sine(-13.0, 1.5)]), RATE) == 0.0


def test_loudness_range_ignores_a_tail_under_the_absolute_gate():
    with_tail = np.vstack([sine(-23.0, 30.0), sine(-90.0, 30.0)])
    assert loudness.loudness_range(with_tail, RATE) < 3.0                     # only the 3 s windows straddling the cut can widen it


# ---------------------------------------------------------------------------
# True peak
# ---------------------------------------------------------------------------


def inter_sample_peak_sine(frames=RATE * 2):
    """A sine at fs/4 shifted by 45 degrees: every sample is +-0.7071, but the waveform between them reaches 1.0."""
    n = np.arange(frames)
    return np.sin(np.pi * n / 2.0 + np.pi / 4.0)


def test_true_peak_finds_the_peak_between_samples():
    isp = inter_sample_peak_sine()
    assert loudness.sample_peak(isp) == pytest.approx(-3.01, abs=0.005)
    assert loudness.true_peak(isp, RATE) == pytest.approx(0.0, abs=0.3)      # full scale between the samples
    assert loudness.true_peak(isp, RATE) > loudness.sample_peak(isp) + 2.5


def test_true_peak_of_a_windowed_inter_sample_peak_sine_is_exact_to_a_few_hundredths():
    isp = inter_sample_peak_sine() * sps.windows.tukey(RATE * 2, 0.2)       # no edge transients
    assert loudness.true_peak(isp, RATE) == pytest.approx(0.0, abs=0.05)
    assert loudness.true_peak(isp * 0.5, RATE) == pytest.approx(-6.02, abs=0.05)
    assert loudness.true_peak(np.stack([isp * 0.25, isp], axis=1), RATE) == pytest.approx(0.0, abs=0.05)   # the loudest channel counts


def test_true_peak_is_never_below_the_sample_peak_and_follows_the_oversampling_rule():
    rng = np.random.default_rng(4)
    noise = rng.standard_normal((RATE, 2)) * 0.1
    for rate in (44100, 48000, 96000, 192000):
        assert loudness.true_peak(noise, rate) >= loudness.sample_peak(noise) - 1e-9
    isp = inter_sample_peak_sine()
    assert loudness.true_peak(isp, 96000) > -1.0              # 2x oversampling still sees it
    assert loudness.true_peak(isp, 192000) == pytest.approx(loudness.sample_peak(isp), abs=1e-6)   # no oversampling at 192 kHz and up


def test_true_peak_of_silence_and_nothing():
    assert loudness.true_peak(np.zeros((100, 2)), RATE) == loudness.SILENCE
    assert loudness.true_peak(np.zeros((0, 2)), RATE) == loudness.SILENCE
    assert loudness.sample_peak(np.zeros((0, 2))) == loudness.SILENCE and loudness.sample_peak(np.zeros(10)) == loudness.SILENCE
    assert loudness.true_peak(np.array([0.5, -0.5, 0.5, -0.5] * 100), RATE) > -6.0    # a 1-D array is one channel


def test_sample_peak_is_the_largest_absolute_value_over_all_channels():
    assert loudness.sample_peak(np.array([[0.1, -0.5], [0.25, 0.0]])) == pytest.approx(-6.0206, abs=1e-3)
    assert loudness.sample_peak(np.array([0.5, 1.0])) == 0.0


# ---------------------------------------------------------------------------
# measure() and gain_to()
# ---------------------------------------------------------------------------


def test_measure_returns_json_safe_rounded_numbers():
    result = loudness.measure(Audio(sine(-23.0, 10.0), RATE))
    assert set(result) == {"integrated", "range", "short_term_max", "momentary_max", "true_peak", "sample_peak"}
    assert result["integrated"] == pytest.approx(-23.0, abs=0.1) and result["range"] == 0.0
    assert result["sample_peak"] == -23.0 and result["true_peak"] >= result["sample_peak"]
    assert result["short_term_max"] == pytest.approx(-23.0, abs=0.1) and result["momentary_max"] == pytest.approx(-23.0, abs=0.1)
    assert all(round(value, 2) == value for value in result.values())
    json.dumps(result, allow_nan=False)


def test_measure_options():
    sig = Audio(sine(-23.0, 10.0), RATE)
    assert "true_peak" not in loudness.measure(sig, peaks=False) and "sample_peak" not in loudness.measure(sig, peaks=False)
    series = loudness.measure(sig, series=True)["short_term"]
    assert len(series) == 8 and all(value == pytest.approx(-23.0, abs=0.1) for value in series)     # one value per second
    assert json.dumps(loudness.measure(sig, series=True), allow_nan=False)


def test_measure_silence_and_short_audio_stay_finite():
    for frames in (RATE * 5, 1000, 0):
        result = loudness.measure(Audio(np.zeros((frames, 2)), RATE), series=True)
        assert result["integrated"] == -200.0 and result["short_term_max"] == -200.0 and result["momentary_max"] == -200.0
        assert result["true_peak"] == -200.0 and result["sample_peak"] == -200.0 and result["range"] == 0.0
        json.dumps(result, allow_nan=False)


def test_measure_mono_audio_as_dual_mono():
    assert loudness.measure(Audio(sine(-23.0, 5.0, channels=1), RATE))["integrated"] == pytest.approx(-23.0, abs=0.1)


def test_gain_to():
    assert loudness.gain_to(-20.0, -14.0) == 6.0 and loudness.gain_to(-9.0, -14.0) == -5.0
    assert loudness.gain_to(loudness.SILENCE, -14.0) == 0.0 and loudness.gain_to(-199.5, -14.0) == 0.0     # nothing to scale


# ---------------------------------------------------------------------------
# Cross-check against ffmpeg's ebur128 filter
# ---------------------------------------------------------------------------


def ffmpeg_ebur128(path, dualmono=False):
    """Final integrated loudness (LUFS), LRA (LU) and true peak (dBTP) as ffmpeg's ebur128 prints them in metadata."""
    ffmpeg = audio.find_ffmpeg()
    spec = "ebur128=metadata=1:peak=true" + (":dualmono=true" if dualmono else "") + ",ametadata=print:file=-"
    run = subprocess.run([ffmpeg, "-nostats", "-hide_banner", "-v", "error", "-i", str(path), "-af", spec, "-f", "null", "-"],
                         capture_output=True, text=True, timeout=120)
    values = {}
    for line in run.stdout.splitlines():
        if line.startswith("lavfi.r128."):
            key, _, text = line.partition("=")
            try:
                values[key[len("lavfi.r128."):]] = float(text)
            except ValueError:
                pass
    if "I" not in values or "true_peak" not in values:
        pytest.skip("this ffmpeg build prints no ebur128 metadata: " + run.stderr[-200:])
    return {"I": values["I"], "LRA": values.get("LRA", 0.0), "tp": 20 * math.log10(max(values["true_peak"], 1e-9))}


needs_ffmpeg = pytest.mark.skipif(audio.find_ffmpeg() is None, reason="ffmpeg is not installed")


@needs_ffmpeg
@pytest.mark.parametrize("rate", [48000, 44100])
def test_pink_noise_agrees_with_ffmpeg_ebur128(tmp_path, rate):
    """Integrated within 0.1 LU, true peak within 0.2 dB, on stereo noise with a 20 LU hole so the gates matter."""
    left, right = pink(30.0, rate, 1, -20.0), pink(30.0, rate, 2, -23.0)
    stereo = np.stack([left, right], axis=1)
    stereo[10 * rate:20 * rate] *= 0.1
    path = audio.write_wav(tmp_path / "pink.wav", stereo, rate, 32)
    theirs = ffmpeg_ebur128(path)
    ours = loudness.measure(audio.read_wav(path))
    assert abs(ours["integrated"] - theirs["I"]) <= 0.1
    assert abs(ours["true_peak"] - theirs["tp"]) <= 0.2
    assert abs(ours["range"] - theirs["LRA"]) <= 0.3


@needs_ffmpeg
def test_steady_pink_noise_and_a_loud_burst_agree_with_ffmpeg(tmp_path):
    steady = np.stack([pink(20.0, RATE, 3, -18.0), pink(20.0, RATE, 4, -18.0)], axis=1)
    steady[5 * RATE:5 * RATE + 4800] *= 4.0                                      # a transient: peaks well above the body
    path = audio.write_wav(tmp_path / "burst.wav", np.clip(steady, -1.0, 1.0), RATE, 32)
    theirs = ffmpeg_ebur128(path)
    ours = loudness.measure(audio.read_wav(path))
    assert abs(ours["integrated"] - theirs["I"]) <= 0.1 and abs(ours["true_peak"] - theirs["tp"]) <= 0.2


@needs_ffmpeg
@pytest.mark.parametrize("freq", [60.0, 440.0, 3000.0, 9000.0])
def test_tones_agree_with_ffmpeg(tmp_path, freq):
    path = audio.write_wav(tmp_path / "tone.wav", sine(-20.0, 10.0, freq=freq), RATE, 32)
    assert abs(loudness.integrated(audio.read_wav(path).samples, RATE) - ffmpeg_ebur128(path)["I"]) <= 0.1


@needs_ffmpeg
def test_mono_dual_mono_agrees_with_ffmpegs_dualmono_option(tmp_path):
    mono = pink(15.0, RATE, 9, -21.0)
    path = audio.write_wav(tmp_path / "mono.wav", mono, RATE, 32)
    assert abs(loudness.integrated(audio.read_wav(path).samples, RATE) - ffmpeg_ebur128(path, dualmono=True)["I"]) <= 0.1


@needs_ffmpeg
def test_inter_sample_peak_agrees_with_ffmpegs_true_peak(tmp_path):
    isp = inter_sample_peak_sine() * sps.windows.tukey(RATE * 2, 0.2)
    path = audio.write_wav(tmp_path / "isp.wav", np.stack([isp, isp], axis=1) * 0.89, RATE, 32)
    assert abs(loudness.true_peak(audio.read_wav(path).samples, RATE) - ffmpeg_ebur128(path)["tp"]) <= 0.2
