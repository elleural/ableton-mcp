"""WS-E: the export MCP tools against a scripted fake Remote Script (offline; ffmpeg for the audio parts)."""
import asyncio
import json

import numpy as np
import pytest
from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server import server
from MCP_Server.audio import AudioError, available
from MCP_Server.audio.ffmpeg import run
from MCP_Server.tools import export

RATE = 44100


class FakeRemote(object):
    """Answers call(command, **params) from a script of bounce_status replies."""

    def __init__(self, statuses=(), song=None):
        self.statuses = list(statuses)
        self.calls = []
        self.song = song or {"tempo": 120.0, "time_signature": "4/4", "key": "A", "scale": "Minor", "set_name": "Demo", "locators": []}

    def __call__(self, command, timeout=None, **params):
        self.calls.append((command, dict((key, value) for key, value in params.items() if value is not None)))
        if command == "bounce_status":
            return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        if command == "bounce_start":
            return dict(job("route"), output_dir=params.get("output_dir"))
        if command == "bounce_cleanup":
            return dict(job("done"), outputs=params["outputs"])
        if command == "bounce_cancel":
            return self.statuses.pop(0)
        if command == "bounce_song_info":
            return self.song
        raise AssertionError(command)

    def commands(self):
        return [name for name, _ in self.calls]


def job(phase, **extra):
    out = {"id": "bounce-7", "phase": phase, "name": "Demo", "duration_seconds": 4.0, "stems": ["Bass"],
           "range": {"start": {"beats": 0.0, "bar": "1.1.1"}, "end": {"beats": 8.0, "bar": "3.1.1"}, "tail_beats": 0.0},
           "warnings": [], "progress": 0.5, "eta_seconds": 2.0, "files": [{"stem": "Master"}]}
    out.update(extra)
    return out


@pytest.fixture
def remote(monkeypatch):
    fake = FakeRemote([job("recording")])
    monkeypatch.setattr(export, "call", fake)
    monkeypatch.setattr(export, "POLL_SECONDS", 0.01)
    return fake


def test_bounce_starts_a_job_and_points_at_the_output(remote, tmp_path):
    out = export.bounce(stems=["Bass"], name="Demo", output_dir=str(tmp_path / "x" / ".." / "y"))
    assert remote.calls[0] == ("bounce_start", {"start": 0, "tail": "2 s", "stems": ["Bass"], "include_returns": False,
                                                "name": "Demo", "output_dir": str(tmp_path / "y")})
    assert out["job"] == "bounce-7" and out["phase"] == "route" and out["output_dir"] == str(tmp_path / "y")
    assert "get_bounce_status" in out["hint"]


def test_status_without_wait_returns_progress(remote):
    out = export.get_bounce_status()
    assert out["phase"] == "recording" and out["progress"] == 0.5 and out["eta_seconds"] == 2.0
    assert remote.commands() == ["bounce_status"]


def test_long_poll_delivers_then_cleans_up(remote, monkeypatch):
    remote.statuses = [job("recording"), job("recording"), job("recorded")]
    delivered = []

    def deliver(found):
        delivered.append(found["id"])
        files = [{"stem": "Master", "path": "/b/Demo - Master.wav", "duration_seconds": 4.0, "peak_dbfs": -3.0, "silent": False, "recording": "/r"}]
        return files, {"folder": "/b", "manifest": "/b/bounce.json", "new_warnings": ["late"]}

    monkeypatch.setattr(export.render, "deliver", deliver)
    out = export.get_bounce_status(wait=5)
    assert delivered == ["bounce-7"] and out["phase"] == "done"
    assert out["folder"] == "/b" and out["files"][0]["path"] == "/b/Demo - Master.wav" and "recording" not in out["files"][0]
    assert out["delivery_warnings"] == ["late"]
    cleanup = [params for name, params in remote.calls if name == "bounce_cleanup"][0]
    assert cleanup["job_id"] == "bounce-7" and cleanup["outputs"]["manifest"] == "/b/bounce.json"


def test_delivery_failure_keeps_the_recordings(remote, monkeypatch):
    remote.statuses = [job("recorded")]

    def broken(found):
        raise AudioError("disk full")

    monkeypatch.setattr(export.render, "deliver", broken)
    with pytest.raises(ToolError, match="disk full.*kept"):
        export.get_bounce_status(wait=1)
    assert "bounce_cleanup" not in remote.commands()


def test_long_poll_gives_up_at_the_deadline(remote):
    started = __import__("time").time()
    out = export.get_bounce_status(wait=0.2)
    assert out["phase"] == "recording" and __import__("time").time() - started < 2


def test_failed_and_idle_summaries(remote):
    remote.statuses = [job("failed", error="Playback stopped")]
    assert export.get_bounce_status(wait=10)["error"] == "Playback stopped"
    remote.statuses = [{"phase": "idle"}]
    assert export.get_bounce_status()["phase"] == "idle"


def test_cancel_waits_for_the_abort_to_finish(remote):
    remote.statuses = [job("aborting"), job("aborting"), job("cancelled", removed_tracks=["[bounce] Master"])]
    out = export.cancel_bounce()
    assert out["phase"] == "cancelled" and out["removed_tracks"] == ["[bounce] Master"]


def write_wav(path, seconds=3.0):
    t = np.arange(int(seconds * RATE)) / float(RATE)
    tone = (0.25 * np.sin(2 * np.pi * 440 * t)).astype("<f4")
    run("ffmpeg", ["-v", "error", "-y", "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", "-", "-ac", "2", "-c:a", "pcm_s24le", str(path)],
        input_bytes=tone.tobytes())
    return str(path)


@pytest.mark.skipif(not available(), reason="ffmpeg/ffprobe not installed")
def test_analyze_audio_sections_from_live_locators_and_images(remote, tmp_path):
    path = write_wav(tmp_path / "mix.wav", 4.0)
    remote.song = dict(remote.song, locators=[{"name": "Drop", "beats": 4.0, "bar": "2.1.1"}, {"name": "Far", "beats": 400.0, "bar": "101.1.1"}])
    result = export.analyze_audio(path, sections="locators")
    assert [item["name"] for item in result["sections"]] == ["(start)", "Drop"] and result["sections"][1]["start"] == 2.0
    with pytest.raises(ToolError, match="locators"):
        export.analyze_audio(path, sections="chorus")
    with pytest.raises(ToolError, match="not found"):
        export.analyze_audio(str(tmp_path / "nope.wav"))
    content = export.analyze_audio(path, images=True)
    assert isinstance(content[0], str) and json.loads(content[0])["images"] and all(isinstance(item, Image) for item in content[1:])


@pytest.mark.skipif(not available(), reason="ffmpeg/ffprobe not installed")
def test_analyze_audio_through_the_server_returns_image_content(remote, tmp_path):
    path = write_wav(tmp_path / "mix.wav", 2.0)
    result = asyncio.run(server.mcp.call_tool("analyze_audio", {"path": path, "images": True}))
    kinds = [block.type for block in result.content]
    assert kinds == ["text", "image", "image"] and not result.is_error
    assert json.loads(result.content[0].text)["loudness"]["integrated_lufs"] is not None
    assert result.content[1].mime_type == "image/png"


@pytest.mark.skipif(not available(), reason="ffmpeg/ffprobe not installed")
def test_create_release_tool_reports_files_and_live_info(remote, tmp_path):
    path = write_wav(tmp_path / "master.wav")
    out = export.create_release(path, "Song", "Artist", formats=["wav24", "mp3"], output_dir=str(tmp_path / "rel"))
    assert [item["format"] for item in out["files"]] == ["wav24", "mp3"] and out["mastering"]["method"] == "linear"
    assert out["live"] == {"tempo": 120.0, "time_signature": "4/4", "key": "A", "scale": "Minor", "set_name": "Demo", "from": "live"}
    assert all(item["integrated_lufs"] == pytest.approx(-14.0, abs=0.5) for item in out["files"])
    with pytest.raises(ToolError, match="Unknown format"):
        export.create_release(path, "Song", "Artist", formats=["ogg"], output_dir=str(tmp_path / "rel2"))


def test_bounce_without_ffmpeg_fails_before_rendering(remote, monkeypatch):
    def missing(name):
        raise AudioError("ffmpeg was not found. Install FFmpeg")

    monkeypatch.setattr(export, "find_tool", missing)
    with pytest.raises(ToolError, match="Install FFmpeg"):
        export.bounce()
    assert remote.calls == []
