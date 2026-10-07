"""WS-E: delivering a recorded bounce: sample-exact trims, naming, alignment and bounce.json (offline)."""
import json
import os

import numpy as np
import pytest

from MCP_Server.audio import render
from MCP_Server.audio.ffmpeg import AudioError, available, decode, probe, run

pytestmark = pytest.mark.skipif(not available(), reason="ffmpeg/ffprobe not installed")
RATE = 44100


def write_wav(path, samples, codec="pcm_s24le"):
    samples = np.asarray(samples, dtype="<f4")
    if samples.ndim == 1:
        samples = np.stack([samples, samples], axis=1)
    run("ffmpeg", ["-v", "error", "-y", "-f", "f32le", "-ar", str(RATE), "-ac", "2", "-i", "-", "-c:a", codec, str(path)],
        input_bytes=np.ascontiguousarray(samples).tobytes())
    return str(path)


def clicks(total, positions, value=0.5):
    out = np.zeros(total)
    out[list(positions)] = value
    return out


def first_click(path):
    samples = decode(path)[0]
    return int(np.flatnonzero(np.abs(samples[:, 0]) > 0.1)[0])


def test_trim_is_sample_exact(tmp_path):
    source = write_wav(tmp_path / "take.wav", clicks(RATE * 3, [8704 + 22050]))  # pre-roll 8704, click 0.5 s later
    out = render.trim(source, str(tmp_path / "out" / "cut.wav"), 8703.997, 2 * RATE)
    info = probe(out)
    assert info["frames"] == 2 * RATE and info["codec"] == "pcm_s24le"
    assert first_click(out) == 22050
    assert not [name for name in os.listdir(tmp_path / "out") if name.startswith(".")]  # no partial file left


def test_trim_pads_short_and_late_recordings(tmp_path):
    source = write_wav(tmp_path / "short.wav", clicks(RATE, [100]))
    padded = render.trim(source, str(tmp_path / "padded.wav"), 0, 2 * RATE)
    assert probe(padded)["frames"] == 2 * RATE and first_click(padded) == 100
    late = render.trim(source, str(tmp_path / "late.wav"), -50, RATE)  # the take started 50 samples late
    assert probe(late)["frames"] == RATE and first_click(late) == 150
    with pytest.raises(AudioError):
        render.trim(source, str(tmp_path / "none.wav"), 0, 0)


def test_float_and_big_endian_sources_keep_their_sample_format():
    assert render.pcm_codec("pcm_f32le") == "pcm_f32le"
    assert render.pcm_codec("pcm_s24be") == "pcm_s24le"
    assert render.pcm_codec("pcm_s16le") == "pcm_s16le"
    assert render.pcm_codec("mp3") == "pcm_f32le"


def test_names_are_safe_and_unique():
    assert render.safe_filename('A/B: "C"?') == "A-B- -C-"
    assert render.safe_filename("  ..  ") == "Untitled"
    files = [{"stem": "Master"}, {"stem": "Bass/Sub"}, {"stem": "bass-sub"}, {"stem": "Keys"}]
    assert render.output_names("My Song", files) == [
        "My Song - Master.wav", "My Song - Bass-Sub.wav", "My Song - bass-sub (2).wav", "My Song - Keys.wav"]
    assert render.default_dir("Bounces", "x/y").endswith(os.path.join("AbletonMCP", "Bounces", "x-y"))


def recorded_job(tmp_path, preroll=8704, seconds=2.0):
    """A finished Remote Script job whose takes carry a pre-roll, like Live's recordings."""
    total = preroll + int(seconds * RATE) + 9000
    (tmp_path / "rec").mkdir(exist_ok=True)
    master = write_wav(tmp_path / "rec" / "[bounce] Master 0001.wav", clicks(total, [preroll + 1000, preroll + 30000]))
    stem = write_wav(tmp_path / "rec" / "[bounce] Bass 0001.wav", clicks(total, [preroll + 30000], 0.3), codec="pcm_f32le")
    length = seconds * RATE
    return {
        "id": "bounce-1", "name": "Demo", "phase": "recorded", "duration_seconds": seconds, "tempo": 120.0,
        "range": {"start": {"beats": 8.0, "bar": "3.1.1"}, "end": {"beats": 12.0, "bar": "4.1.1"}, "tail_beats": 0.0, "stop_beats": 12.0},
        "song": {"tempo": 120.0, "locators": [{"name": "Intro", "beats": 4.0, "bar": "2.1.1"}, {"name": "Hook", "beats": 10.0, "bar": "3.3.1"}]},
        "warnings": ["from live"],
        "files": [
            {"stem": "Master", "role": "master", "track": "[bounce] Master", "file_path": master, "sample_rate": 44100.0,
             "offset_samples": preroll - 0.002, "length_samples": length + 0.001},
            {"stem": "Bass", "role": "stem", "track": "[bounce] Bass", "source": "Bass", "file_path": stem, "sample_rate": 44100.0,
             "offset_samples": preroll, "length_samples": length},
        ],
    }


def test_deliver_trims_aligns_and_writes_the_manifest(tmp_path):
    job = recorded_job(tmp_path)
    folder = tmp_path / "Bounces" / "Demo"
    outputs, manifest = render.deliver(job, str(folder))
    master, bass = outputs
    assert master["path"] == str(folder / "Demo - Master.wav") and bass["path"] == str(folder / "Demo - Bass.wav")
    for item in outputs:
        info = probe(item["path"])
        assert info["frames"] == 2 * RATE and item["duration_seconds"] == 2.0 and not item["silent"]
    assert first_click(master["path"]) == 1000 and first_click(bass["path"]) == 30000
    assert probe(bass["path"])["codec"] == "pcm_f32le" and bass["track"] == "Bass" and bass["peak_dbfs"] == pytest.approx(-10.46, abs=0.05)
    saved = json.load(open(folder / "bounce.json"))
    assert saved["files"][0]["path"] == "Demo - Master.wav" and saved["warnings"] == ["from live"] and saved["tempo"] == 120.0
    assert manifest["manifest"] == str(folder / "bounce.json") and manifest["new_warnings"] == []
    found, entry = render.manifest_for(master["path"])
    assert found["name"] == "Demo" and entry["stem"] == "Master"
    assert render.manifest_for(str(tmp_path / "elsewhere.wav")) == (None, None)
    sections = render.locator_sections(found, 2.0)
    assert sections == [{"name": "(start)", "start": 0.0}, {"name": "Hook", "start": 1.0, "start_bar": "3.3.1"}]


def test_deliver_reports_short_takes_and_missing_files(tmp_path):
    job = recorded_job(tmp_path)
    job["files"][1]["length_samples"] = 9 * RATE
    job["files"][0]["length_samples"] = 9 * RATE  # longer than the takes: padded, with a warning
    job["duration_seconds"] = 9.0
    outputs, manifest = render.deliver(job, str(tmp_path / "out"))
    assert probe(outputs[0]["path"])["frames"] == 9 * RATE
    assert any("early" in warning for warning in manifest["new_warnings"])
    job["files"][0]["file_path"] = str(tmp_path / "gone.wav")
    with pytest.raises(AudioError, match="missing"):
        render.deliver(job, str(tmp_path / "out2"))
    with pytest.raises(AudioError, match="no recorded master"):
        render.deliver({"files": []})
