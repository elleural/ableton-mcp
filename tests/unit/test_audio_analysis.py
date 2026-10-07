"""WS-E: audio analysis on synthetic signals with known levels (needs ffmpeg; offline)."""
import math

import numpy as np
import pytest

from MCP_Server.audio import analysis, images
from MCP_Server.audio.ffmpeg import AudioError, available, run

pytestmark = pytest.mark.skipif(not available(), reason="ffmpeg/ffprobe not installed")
RATE = 48000


def write_wav(path, samples, rate=RATE, codec="pcm_f32le"):
    """Write float samples shaped (frames, channels) to a WAV through ffmpeg."""
    samples = np.asarray(samples, dtype="<f4")
    if samples.ndim == 1:
        samples = samples[:, None]
    run("ffmpeg", ["-v", "error", "-y", "-f", "f32le", "-ar", str(rate), "-ac", str(samples.shape[1]), "-i", "-", "-c:a", codec, str(path)],
        input_bytes=np.ascontiguousarray(samples).tobytes())
    return str(path)


def sine(frequency, seconds, dbfs, rate=RATE):
    t = np.arange(int(seconds * rate)) / float(rate)
    return (10 ** (dbfs / 20.0)) * np.sin(2 * np.pi * frequency * t)


def stereo(signal):
    return np.stack([signal, signal], axis=1)


def test_known_level_sine_measures_as_expected(tmp_path):
    # A stereo 997 Hz sine peaking at -20 dBFS reads -20 LUFS (BS.1770 calibration) and -23.01 dBFS RMS.
    path = write_wav(tmp_path / "sine.wav", stereo(sine(997, 6, -20.0)))
    result = analysis.analyze(path)
    assert result["loudness"]["integrated_lufs"] == pytest.approx(-20.0, abs=0.2)
    assert result["loudness"]["true_peak_dbtp"] == pytest.approx(-20.0, abs=0.2)
    assert result["loudness"]["loudness_range_lu"] == pytest.approx(0.0, abs=0.5)
    assert result["levels"]["sample_peak_dbfs"] == pytest.approx(-20.0, abs=0.05)
    assert result["levels"]["rms_dbfs"] == pytest.approx(-23.01, abs=0.05)
    assert result["levels"]["crest_factor_db"] == pytest.approx(3.01, abs=0.05)
    assert result["levels"]["clipped_samples"] == 0 and result["levels"]["dc_offset"] < 1e-4
    assert result["stereo"] == {"channels": 2, "correlation": 1.0, "width": 0.0}
    assert result["spectrum"]["low_mid"]["percent"] > 99
    assert result["duration_seconds"] == pytest.approx(6.0) and result["format"]["sample_rate"] == RATE
    assert result["notes"] == [] and result["dropouts"] == []


def test_mono_counts_as_dual_mono(tmp_path):
    path = write_wav(tmp_path / "mono.wav", sine(997, 5, -18.0))
    result = analysis.analyze(path)
    assert result["loudness"]["integrated_lufs"] == pytest.approx(-18.0, abs=0.2)
    assert result["stereo"]["channels"] == 1 and result["stereo"]["correlation"] is None


def test_gated_loudness_from_momentary_blocks_matches_ffmpeg(tmp_path):
    signal = np.concatenate([sine(997, 4, -30.0), sine(997, 4, -20.0), sine(997, 4, -12.0), np.zeros(RATE * 2)])
    path = write_wav(tmp_path / "steps.wav", stereo(signal))
    measured = analysis.measure_loudness(path)
    assert analysis.gated_loudness(measured["M"]) == pytest.approx(measured["integrated"], abs=0.15)
    assert analysis.gated_loudness([-80.0, -90.0]) == float("-inf")
    assert analysis.gated_loudness([-20.0, -20.0, -40.0]) == pytest.approx(-20.0)  # -40 is below the relative gate


def test_sections_and_loudness_curve(tmp_path):
    signal = np.concatenate([sine(997, 6, -30.0), sine(997, 6, -12.0)])
    path = write_wav(tmp_path / "two.wav", stereo(signal))
    result = analysis.analyze(path, [{"name": "Verse", "start": 0}, {"name": "Drop", "start": 6.0, "end": 12.0}])
    verse, drop = result["sections"]
    assert (verse["name"], verse["end"]) == ("Verse", 6.0)  # end filled from the next start
    assert verse["integrated_lufs"] == pytest.approx(-30.0, abs=0.5) and drop["integrated_lufs"] == pytest.approx(-12.0, abs=0.5)
    assert drop["sample_peak_dbfs"] == pytest.approx(-12.0, abs=0.05) and drop["short_term_max_lufs"] == pytest.approx(-12.0, abs=0.5)
    curve = result["loudness_curve"]
    assert curve["interval_seconds"] == 1.0 and len(curve["short_term_lufs"]) == 12
    assert curve["short_term_lufs"][0] == pytest.approx(-30.0, abs=0.5) and curve["short_term_lufs"][-1] == pytest.approx(-12.0, abs=0.5)
    with pytest.raises(AudioError):
        analysis.normalize_sections([{"name": "late", "start": 50}], 12.0)
    with pytest.raises(AudioError):
        analysis.normalize_sections([{"name": "no start"}], 12.0)
    with pytest.raises(AudioError):
        analysis.normalize_sections("intro", 12.0)


def test_spectral_bands_place_tones(tmp_path):
    expected = {40: "sub", 120: "low", 1000: "low_mid", 4000: "high_mid", 10000: "high"}
    for frequency, band in expected.items():
        samples = stereo(sine(frequency, 2, -12.0))
        result = analysis.spectral_balance(samples.astype("<f4"), RATE)
        assert result[band]["percent"] > 95, (frequency, result)
        assert sum(item["percent"] for item in result.values()) == pytest.approx(100.0, abs=0.5)


def test_stereo_image_correlation_and_width():
    rng = np.random.default_rng(1)
    left = rng.standard_normal(RATE).astype("<f4") * 0.1
    right = rng.standard_normal(RATE).astype("<f4") * 0.1
    inverted = analysis.stereo_image(np.stack([left, -left], axis=1))
    assert inverted["correlation"] == pytest.approx(-1.0) and inverted["width"] is None  # no mid at all
    unrelated = analysis.stereo_image(np.stack([left, right], axis=1))
    assert abs(unrelated["correlation"]) < 0.05 and unrelated["width"] == pytest.approx(1.0, abs=0.05)
    narrow = analysis.stereo_image(np.stack([left, 0.9 * left + 0.1 * right], axis=1))
    assert narrow["correlation"] > 0.9 and narrow["width"] < 0.2


def test_levels_report_dc_clipping_and_overs(tmp_path):
    hot = np.clip(sine(200, 2, 3.0), -1.0, 1.0) + 0.0
    result = analysis.levels(stereo(hot).astype("<f4"))
    assert result["clipped_samples"] > 1000 and result["sample_peak_dbfs"] == pytest.approx(0.0, abs=0.01)
    offset = analysis.levels(stereo(sine(200, 2, -20.0) + 0.01).astype("<f4"))
    assert offset["dc_offset"] == pytest.approx(0.01, abs=1e-4)
    over = analysis.levels(stereo(sine(200, 1, 2.0)).astype("<f4"))  # float data above full scale
    assert over["samples_over_full_scale"] > 0
    path = write_wav(tmp_path / "hot.wav", stereo(hot))
    notes = " ".join(analysis.analyze(path)["notes"])
    assert "True peak" in notes and "clipping" in notes


def test_dropouts_find_short_digital_silences():
    rng = np.random.default_rng(2)
    noise = (rng.standard_normal(RATE * 2) * 0.1).astype("<f4")
    assert analysis.dropouts(stereo(noise), RATE) == []
    gap = noise.copy()
    gap[RATE:RATE + RATE // 50] = 0.0  # 20 ms
    assert analysis.dropouts(stereo(gap), RATE) == [1.0]
    long_pause = noise.copy()
    long_pause[RATE // 2:RATE] = 0.0  # 500 ms of silence is music, not a dropout
    assert analysis.dropouts(stereo(long_pause), RATE) == []


def test_silent_file_is_flagged(tmp_path):
    path = write_wav(tmp_path / "silence.wav", np.zeros((RATE * 2, 2)))
    result = analysis.analyze(path)
    assert result["notes"] == ["The file is silent."] and result["loudness"]["integrated_lufs"] is None


def test_parse_ebur128_summary():
    text = ("[Parsed_ebur128_0 @ 0x1] t: 0.1  TARGET:-23 LUFS    M:-120.7 S:-120.7     I: -70.0 LUFS       LRA:   0.0 LU\n"
            "[Parsed_ebur128_0 @ 0x1] t: 0.4  TARGET:-23 LUFS    M: -14.2 S: -15.0     I: -14.2 LUFS\n"
            "  Summary:\n\n  Integrated loudness:\n    I:         -14.1 LUFS\n    Threshold: -24.1 LUFS\n\n"
            "  Loudness range:\n    LRA:         5.3 LU\n\n  True peak:\n    Peak:       -0.9 dBFS\n")
    parsed = analysis.parse_ebur128(text)
    assert (parsed["integrated"], parsed["range"], parsed["true_peak"]) == (-14.1, 5.3, -0.9)
    assert list(parsed["t"]) == [0.1, 0.4] and list(parsed["M"]) == [-120.7, -14.2] and list(parsed["S"]) == [-120.7, -15.0]
    with pytest.raises(AudioError):
        analysis.parse_ebur128("no summary here")


def test_images_are_png(tmp_path):
    path = write_wav(tmp_path / "img.wav", stereo(sine(440, 2, -12.0)))
    for picture in (images.spectrogram_png(path), images.waveform_png(path, width=600, height=200)):
        assert picture.startswith(images.PNG_SIGNATURE) and len(picture) > 500


def test_missing_and_unreadable_files_raise_clear_errors(tmp_path):
    with pytest.raises(AudioError, match="not found"):
        analysis.analyze(str(tmp_path / "nope.wav"))
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"not audio at all")
    with pytest.raises(AudioError, match="ffprobe failed|no audio"):
        analysis.analyze(str(junk))


def test_db_and_rounding_helpers():
    assert analysis.db(1.0) == 0.0 and analysis.db(0.0) == float("-inf")
    assert analysis.rounded(float("-inf")) is None and analysis.rounded(-3.14159, 1) == -3.1
    assert math.isnan(analysis._float("nan")) and analysis._float("-inf") == float("-inf")
