"""WS-E: release pipeline on synthetic signals: normalisation, every format, tags, artwork, dither, manifest."""
import json
import os

import numpy as np
import pytest

from MCP_Server.audio import release
from MCP_Server.audio.analysis import measure_loudness
from MCP_Server.audio.ffmpeg import AudioError, available, decode, probe, run

pytestmark = pytest.mark.skipif(not available(), reason="ffmpeg/ffprobe not installed")
RATE = 44100


def write_wav(path, samples, rate=RATE, codec="pcm_s24le"):
    samples = np.asarray(samples, dtype="<f4")
    if samples.ndim == 1:
        samples = np.stack([samples, samples], axis=1)
    run("ffmpeg", ["-v", "error", "-y", "-f", "f32le", "-ar", str(rate), "-ac", str(samples.shape[1]), "-i", "-", "-c:a", codec, str(path)],
        input_bytes=np.ascontiguousarray(samples).tobytes())
    return str(path)


def quiet_tone(seconds=6.0, dbfs=-30.0):
    t = np.arange(int(seconds * RATE)) / float(RATE)
    return 10 ** (dbfs / 20.0) * (0.6 * np.sin(2 * np.pi * 220 * t) + 0.4 * np.sin(2 * np.pi * 997 * t))


def drum_loop(seconds=8.0, peak=0.89):
    """Peaky material (kick-like bursts over a quiet bed): reaching -14 LUFS needs limiting."""
    n = int(seconds * RATE)
    rng = np.random.default_rng(7)
    out = 0.02 * rng.standard_normal(n)
    for start in range(0, n, RATE // 2):
        m = np.arange(n - start)
        out[start:] += np.exp(-m / (0.06 * RATE)) * np.sin(2 * np.pi * 70 * m / RATE)
    left = out + 0.01 * rng.standard_normal(n)
    pair = np.stack([left, out], axis=1)
    return pair * (peak / np.abs(pair).max())


@pytest.fixture
def artwork(tmp_path):
    path = tmp_path / "art.png"
    run("ffmpeg", ["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=300x300:rate=1", "-frames:v", "1", str(path)])
    return str(path)


def test_linear_normalisation_hits_target(tmp_path):
    source = write_wav(tmp_path / "quiet.wav", quiet_tone())
    info = probe(source)
    measured = measure_loudness(source, info)
    premaster, after, report = release.normalize(info, measured, -14.0, -1.0, str(tmp_path))
    assert report["method"] == "linear" and report["gain_db"] == pytest.approx(-14.0 - measured["integrated"], abs=0.01)
    assert after["integrated"] == pytest.approx(-14.0, abs=0.5)
    assert measure_loudness(premaster)["integrated"] == pytest.approx(-14.0, abs=0.2)
    assert probe(premaster)["codec"] == "pcm_f32le" and probe(premaster)["frames"] == info["frames"]


def test_limited_normalisation_hits_target_under_the_ceiling(tmp_path):
    source = write_wav(tmp_path / "drums.wav", drum_loop())
    info = probe(source)
    measured = measure_loudness(source, info)
    assert measured["true_peak"] + (-14.0 - measured["integrated"]) > -1.0  # linear gain would overshoot the ceiling
    premaster, after, report = release.normalize(info, measured, -14.0, -1.0, str(tmp_path))
    assert report["method"] == "limited" and report["passes"] <= release.MAX_PASSES
    assert after["integrated"] == pytest.approx(-14.0, abs=0.5)
    assert after["true_peak"] <= -1.0
    assert probe(premaster)["frames"] == info["frames"]  # the limiter's lookahead is compensated


def test_every_format_encodes_with_tags_artwork_and_checksums(tmp_path, artwork):
    source = write_wav(tmp_path / "song.wav", drum_loop(6.0, peak=0.5))
    result = release.create_release(source, "Night Drive", "The Agents", album="Synthetic", year=2026, genre="Electronic",
                                    track_number=3, artwork=artwork, output_dir=str(tmp_path / "out"), live_info={"tempo": 124.0})
    assert [item["format"] for item in result["files"]] == ["wav24", "wav16", "flac", "mp3", "aac"]
    names = sorted(os.listdir(result["folder"]))
    assert names == sorted(["The Agents - Night Drive (24-bit).wav", "The Agents - Night Drive (16-bit).wav", "The Agents - Night Drive.flac",
                            "The Agents - Night Drive.mp3", "The Agents - Night Drive.m4a", "cover.png", "release.json"])
    expected_codecs = {"wav24": ("pcm_s24le", 24), "wav16": ("pcm_s16le", 16), "flac": ("flac", 24), "mp3": ("mp3", None), "aac": ("aac", None)}
    for item, path in zip(result["files"], result["file_paths"]):
        info = probe(path)  # read the tags back from the file itself
        assert info["tags"]["title"] == "Night Drive" and info["tags"]["artist"] == "The Agents", item["format"]
        assert info["tags"]["album"] == "Synthetic" and info["tags"]["genre"] == "Electronic"
        assert info["tags"]["date"].startswith("2026") and info["tags"]["track"].split("/")[0] == "3"
        assert info["artwork"] == (item["format"] in release.ARTWORK_FORMATS)
        assert (info["codec"], item["bit_depth"]) == expected_codecs[item["format"]]
        assert abs(info["duration"] - 6.0) < 0.05
        assert item["integrated_lufs"] == pytest.approx(-14.0, abs=1.0) and item["true_peak_dbtp"] <= -1.0
        assert item["sha256"] == release.sha256(path)
    mp3 = next(item for item in result["files"] if item["format"] == "mp3")
    assert 300 <= mp3["bitrate_kbps"] <= 330
    manifest = json.load(open(result["manifest"]))
    assert manifest["live"] == {"tempo": 124.0} and manifest["mastering"]["target_lufs"] == -14.0
    assert manifest["artwork"]["file"] == "cover.png" and manifest["artwork"]["width"] == 300
    assert manifest["source"]["sha256"] == release.sha256(source) and manifest["duration_seconds"] == pytest.approx(6.0, abs=0.01)
    assert all("path" not in item for item in manifest["files"])  # the manifest is relocatable
    assert any("WAV" in warning for warning in result["warnings"])


def test_sixteen_bit_output_is_dithered(tmp_path):
    t = np.arange(RATE * 2) / float(RATE)
    whisper = 10 ** (-110 / 20.0) * np.sin(2 * np.pi * 1000 * t)  # below one 16-bit step
    premaster = write_wav(tmp_path / "whisper.wav", whisper, codec="pcm_f32le")
    plain = tmp_path / "plain.wav"
    run("ffmpeg", ["-v", "error", "-y", "-i", premaster, "-c:a", "pcm_s16le", str(plain)])
    dithered = release.encode(premaster, "wav16", str(tmp_path / "dithered.wav"), {"title": "x"})
    assert not np.any(decode(str(plain))[0])  # truncation alone gives digital silence
    noise = decode(dithered)[0]
    # TPDF: about a quarter of the samples non-zero at +-1 LSB (ffmpeg 6), half at +-2 LSB (ffmpeg 8)
    assert np.count_nonzero(noise) > noise.size * 0.15 and np.abs(noise).max() <= 2.5 / 32768


def test_artwork_in_other_image_formats_is_converted(tmp_path):
    bmp = tmp_path / "art.bmp"
    run("ffmpeg", ["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=1", "-frames:v", "1", str(bmp)])
    source = write_wav(tmp_path / "s.wav", quiet_tone(3.0))
    result = release.create_release(source, "T", "A", artwork=str(bmp), formats=["flac"], output_dir=str(tmp_path / "out"))
    assert result["artwork"]["file"] == "cover.png" and probe(result["file_paths"][0])["artwork"]


def test_stems_are_copied_with_checksums(tmp_path):
    folder = tmp_path / "bounce"
    folder.mkdir()
    master = write_wav(folder / "Demo - Master.wav", quiet_tone(3.0))
    write_wav(folder / "Demo - Bass.wav", quiet_tone(3.0, -36.0))
    (folder / "bounce.json").write_text(json.dumps({"files": [{"path": "Demo - Master.wav", "role": "master"},
                                                              {"path": "Demo - Bass.wav", "role": "stem", "stem": "Bass"}]}))
    result = release.create_release(master, "Demo", "Me", formats=["wav24"], output_dir=str(tmp_path / "rel"), stems="auto")
    assert [item["file"] for item in result["stems"]] == [os.path.join("Stems", "Me - Demo - Bass.wav")]
    copied = os.path.join(result["folder"], result["stems"][0]["file"])
    assert release.sha256(copied) == release.sha256(str(folder / "Demo - Bass.wav")) == result["stems"][0]["sha256"]
    with pytest.raises(AudioError, match="bounce.json"):
        release.resolve_stems("auto", write_wav(tmp_path / "loose.wav", quiet_tone(1.0)))
    with pytest.raises(AudioError, match="not found"):
        release.resolve_stems([str(tmp_path / "missing.wav")], master)


def test_parse_formats():
    assert release.parse_formats(None) == list(release.DEFAULT_FORMATS)
    assert release.parse_formats(["WAV", "m4a", "mp3", "mp3", "wav-16"]) == ["wav24", "aac", "mp3", "wav16"]
    assert release.parse_formats("flac") == ["flac"]
    for bad in (["ogg"], []):
        with pytest.raises(AudioError):
            release.parse_formats(bad)


def test_bad_requests_fail_clearly(tmp_path):
    source = write_wav(tmp_path / "s.wav", quiet_tone(2.0))
    silent = write_wav(tmp_path / "silent.wav", np.zeros(RATE * 2))
    with pytest.raises(AudioError, match="title and artist"):
        release.create_release(source, "", "A")
    with pytest.raises(AudioError, match="target_lufs"):
        release.create_release(source, "T", "A", target_lufs=0)
    with pytest.raises(AudioError, match="true_peak"):
        release.create_release(source, "T", "A", true_peak=1.0)
    with pytest.raises(AudioError, match="silent"):
        release.create_release(silent, "T", "A", output_dir=str(tmp_path / "x"))
    with pytest.raises(AudioError, match="not found"):
        release.create_release(str(tmp_path / "nope.wav"), "T", "A")
    with pytest.raises(AudioError, match="Artwork"):
        release.create_release(source, "T", "A", artwork=str(tmp_path / "nope.png"), output_dir=str(tmp_path / "y"))


def test_loud_masters_keep_lossy_files_under_the_ceiling_at_the_same_loudness(tmp_path):
    rng = np.random.default_rng(5)
    loud = drum_loop(8.0) + 0.05 * rng.standard_normal((8 * RATE, 2))  # transients plus hiss: lossy codecs overshoot
    source = write_wav(tmp_path / "loud.wav", loud / np.abs(loud).max() * 0.89)
    result = release.create_release(source, "Loud", "A", target_lufs=-8.0, formats=["wav24", "mp3", "aac"], output_dir=str(tmp_path / "out"))
    for item in result["files"]:
        assert item["true_peak_dbtp"] <= -1.05, item  # printed to 0.1 dB, so -1.1 or lower
        assert item["integrated_lufs"] == pytest.approx(-8.0, abs=0.6), item
    assert result["mastering"]["method"] == "limited"


def test_lossy_overshoot_triggers_a_harder_limited_premaster(tmp_path, monkeypatch):
    source = write_wav(tmp_path / "s.wav", drum_loop(4.0))
    real_describe, real_normalize, seen, injected = release.describe_file, release.normalize, [], []

    def describe(path, fmt):
        record = real_describe(path, fmt)
        if fmt == "mp3" and not injected:
            injected.append(True)
            record["true_peak_dbtp"] = -0.4  # pretend the encoder overshot by 0.6 dB
        return record

    def normalize(source_info, measured, target, ceiling, workdir, name="premaster.wav"):
        seen.append((ceiling, name))
        return real_normalize(source_info, measured, target, ceiling, workdir, name)

    monkeypatch.setattr(release, "describe_file", describe)
    monkeypatch.setattr(release, "normalize", normalize)
    result = release.create_release(source, "T", "A", formats=["wav24", "mp3"], output_dir=str(tmp_path / "out"))
    assert seen[0] == (-1.0, "premaster.wav")
    assert seen[1][1] == "premaster-lossy.wav" and seen[1][0] == pytest.approx(-1.0 - (0.65 + 0.2))
    mp3 = result["files"][1]
    assert mp3["limited_for_encoding"] and mp3["true_peak_dbtp"] <= -1.05 and "limited_for_encoding" not in result["files"][0]
    assert result["mastering"]["lossy_true_peak_ceiling_dbtp"] == pytest.approx(-1.85, abs=0.01)
