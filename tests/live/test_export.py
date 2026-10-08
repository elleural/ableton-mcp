"""WS-E live tests: real-time bounce, analysis and release against the running Live (audible, about 20 s).

Scratch material sits far out in the arrangement (bar 201) so nothing else plays: an audio track with
a generated clip of tone bursts at known times, and a MIDI track with Operator and an (empty) clip that
starts armed, so the bounce must disarm it and re-arm it, and must not record over its clip.
"""
import os
import time
import wave

import numpy as np
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server.audio.ffmpeg import available, decode, probe
from MCP_Server.connection import AbletonError
from MCP_Server.tools import export

pytestmark = pytest.mark.skipif(not available(), reason="ffmpeg/ffprobe not installed")

FAR = 800.0  # beats: bar 201 in 4/4; moved past the set's own arrangement when that is longer (material["far"])
RATE = 44100
BURSTS = (0.5, 1.0, 1.5)  # seconds after the clip start
TRANSPORT = ["loop", "metronome", "record_mode", "arrangement_overdub", "punch_in", "punch_out", "session_automation_record",
             "current_song_time", "start_time", "is_playing"]


def write_bursts(path):
    """1 kHz bursts (60 ms) at BURSTS, then a 220 Hz tone from 2.0 to 3.0 s; 4 s, 16-bit stereo."""
    t = np.arange(4 * RATE) / float(RATE)
    signal = np.zeros_like(t)
    for onset in BURSTS:
        span = (t >= onset) & (t < onset + 0.06)
        signal[span] = 0.5 * np.sin(2 * np.pi * 1000 * (t[span] - onset))
    span = (t >= 2.0) & (t < 3.0)
    signal[span] = 0.3 * np.sin(2 * np.pi * 220 * (t[span] - 2.0))
    pcm = (np.stack([signal, signal], axis=1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(pcm.tobytes())
    return str(path)


def track_path(live, name):
    names = live.send_command("lom_get", {"path": "live_set", "properties": ["tracks"]})["values"]["tracks"]["items"]
    return "live_set tracks {0}".format(names.index(name))


def get(live, path, *properties):
    values = live.send_command("lom_get", {"path": path, "properties": list(properties)})["values"]
    return dict((key, value.get("value", value)) for key, value in values.items())


def snapshot(live):
    """Transport fields plus every track's (name, arm), in order, read in one main-thread batch."""
    state = get(live, "live_set", *(TRANSPORT + ["back_to_arranger"]))
    count = live.send_command("lom_get", {"path": "live_set", "properties": ["tracks"]})["values"]["tracks"]["count"]
    reads = [{"type": "lom_get", "params": {"path": "live_set tracks {0}".format(index), "properties": ["name", "arm"]}} for index in range(count)]
    results = live.send_command("batch", {"commands": reads})["results"]
    state["arms"] = [(item["result"]["values"]["name"]["value"], item["result"]["values"]["arm"]["value"]) for item in results]
    state["selected"] = live.send_command("lom_get", {"path": "live_set view", "properties": ["selected_track"]})["values"]["selected_track"]
    return state


def assert_same_state(before, after):
    for key in TRANSPORT:
        if isinstance(before[key], float):
            assert after[key] == pytest.approx(before[key], abs=1e-3), key
        else:
            assert after[key] == before[key], key
    assert after["back_to_arranger"] is False  # a bounce returns to the arrangement; Live cannot re-light the button
    assert after["arms"] == before["arms"] and after["selected"] == before["selected"]
    assert not [name for name, _ in after["arms"] if name.startswith("[bounce]")]


def onset(path, threshold=0.01):
    samples = decode(path)[0]
    hits = np.flatnonzero(np.abs(samples).max(axis=1) > threshold)
    return int(hits[0]) if hits.size else None


def wait_for(phases, timeout=30.0):
    """Long-poll for terminal phases; short-poll for running ones (the long poll only ends when a bounce does)."""
    deadline = time.time() + timeout
    terminal = all(phase not in export.RUNNING for phase in phases)
    while True:
        status = export.get_bounce_status(wait=min(5.0, max(0.1, deadline - time.time())) if terminal else 0)
        if status["phase"] in phases or time.time() > deadline:
            return status
        if not terminal:
            time.sleep(0.1)


def far_from_material(live):
    """Bar 201, or 16 bars past the open set's last arrangement event, so the set's own clips stay silent."""
    last = live.send_command("lom_get", {"path": "live_set", "properties": ["last_event_time"]})["values"]["last_event_time"]["value"]
    return max(FAR, float(int(last // 4) * 4 + 64))


@pytest.fixture
def material(live, scratch, song_state, tmp_path):
    far = far_from_material(live)
    tone = scratch.track("Tone", kind="audio")
    clip = live.send_command("lom_call", {"path": track_path(live, tone), "method": "create_audio_clip",
                                          "args": [write_bursts(tmp_path / "bursts.wav"), far]})["result"]["path"]
    live.send_command("lom_set", {"path": clip, "property": "warping", "value": False})
    synth = scratch.track("Synth", kind="midi")
    live.send_command("lom_call", {"path": track_path(live, synth), "method": "insert_device", "args": ["Operator"]})
    live.send_command("lom_call", {"path": track_path(live, synth), "method": "create_midi_clip", "args": [far, 8.0]})
    live.send_command("lom_set", {"path": track_path(live, synth), "property": "arm", "value": True})
    empty = scratch.track("No instrument", kind="midi")
    yield {"tone": tone, "synth": synth, "empty": empty, "out": tmp_path / "out", "far": far}
    try:  # never leave a bounce running or its tracks behind, even when a test fails
        export.cancel_bounce()
    except ToolError:
        pass


def test_bounce_master_and_stems_end_to_end(live, material):
    tempo = get(live, "live_set", "tempo")["tempo"]
    before = snapshot(live)
    started = time.time()
    job = export.bounce(start=material["far"], end=material["far"] + 8, tail=0, stems=[material["tone"], material["synth"]], name="export test",
                        output_dir=str(material["out"]))
    assert job["phase"] == "route" and job["stems"] == [material["tone"], material["synth"]]
    assert job["range"]["start"] == {"beats": material["far"], "bar": "{0}.1.1".format(int(material["far"] // 4) + 1)} and job["duration_seconds"] == pytest.approx(8 * 60.0 / tempo)
    done = wait_for(("done", "failed", "cancelled"))
    elapsed = time.time() - started
    assert done["phase"] == "done", done
    after = snapshot(live)
    assert_same_state(before, after)
    synth_clips = get(live, track_path(live, material["synth"]), "arrangement_clips")["arrangement_clips"]
    assert synth_clips["count"] == 1  # the armed MIDI track was disarmed: nothing recorded over its clip

    files = dict((item["stem"], item) for item in done["files"])
    assert set(files) == {"Master", material["tone"], material["synth"]}
    expected = 8 * 60.0 / tempo
    for item in files.values():
        assert os.path.isfile(item["path"]) and os.path.dirname(item["path"]) == str(material["out"])
        assert abs(probe(item["path"])["duration"] - expected) < 0.05
    assert not files["Master"]["silent"] and not files[material["tone"]]["silent"]
    assert files[material["synth"]]["silent"]  # Operator without notes
    master_onset, stem_onset = onset(files["Master"]["path"]), onset(files[material["tone"]]["path"])
    assert abs(master_onset - stem_onset) <= 1  # stem and master line up
    assert abs(master_onset - BURSTS[0] * RATE) <= 0.005 * RATE  # and sit where the arrangement put them
    assert os.path.isfile(done["manifest"])
    print("\nbounce: {0:.1f} s wall for {1:.1f} s audio; first onset at sample {2} (expected {3}); master-stem offset {4} samples".format(
        elapsed, expected, master_onset, int(BURSTS[0] * RATE), master_onset - stem_onset))

    analysis = export.analyze_audio(files["Master"]["path"], sections=[{"name": "bursts", "start": 0, "end": 2}, {"name": "tone", "start": 2}])
    assert analysis["duration_seconds"] == pytest.approx(expected, abs=0.01) and analysis["loudness"]["integrated_lufs"] < -10
    assert analysis["sections"][1]["sample_peak_dbfs"] == pytest.approx(20 * np.log10(0.3), abs=0.5)
    by_locators = export.analyze_audio(files["Master"]["path"], sections="locators")
    assert "sections" not in by_locators or by_locators["sections"]

    released = export.create_release(files["Master"]["path"], "Export Test", "AbletonMCP", year=2026, formats=["wav24", "wav16", "mp3"],
                                     output_dir=str(material["out"] / "release"), stems="auto")
    assert released["live"]["from"] == "bounce" and released["live"]["tempo"] == pytest.approx(tempo)
    assert released["stems"] == 2
    for item in released["files"]:
        assert os.path.isfile(item["path"]) and abs(item["duration_seconds"] - expected) < 0.05
        assert item["integrated_lufs"] == pytest.approx(-14.0, abs=1.0) and item["true_peak_dbtp"] <= -1.0


def test_cancel_interrupt_and_errors(live, material):
    before = snapshot(live)
    with pytest.raises(ToolError, match="must be after"):
        export.bounce(start=material["far"] + 8, end=material["far"])
    with pytest.raises(ToolError, match="no audio output"):
        export.bounce(start=material["far"], end=material["far"] + 4, stems=[material["empty"]])
    with pytest.raises(AbletonError):
        live.send_command("bounce_cleanup", {"job_id": "bounce-0"})
    info = live.send_command("bounce_song_info")
    assert info["tempo"] > 0 and "locators" in info and info["default_end"]["beats"] >= info["last_event"]["beats"]

    export.bounce(start=material["far"], end=material["far"] + 16, tail=0, name="cancelled", output_dir=str(material["out"]))
    with pytest.raises(ToolError, match="still"):
        export.bounce(start=material["far"], end=material["far"] + 4)
    assert wait_for(("recording",), timeout=10)["phase"] == "recording"
    cancelled = export.cancel_bounce()
    assert cancelled["phase"] == "cancelled" and cancelled["removed_tracks"]
    assert_same_state(before, snapshot(live))

    export.bounce(start=material["far"], end=material["far"] + 16, tail=0, stems=[material["tone"]], name="interrupted", output_dir=str(material["out"]))
    assert wait_for(("recording",), timeout=10)["phase"] == "recording"
    live.send_command("lom_call", {"path": "live_set", "method": "stop_playing", "args": []})  # someone presses Stop
    failed = wait_for(("failed", "done", "cancelled"), timeout=10)
    assert failed["phase"] == "failed" and "interrupted" in failed["error"]
    assert_same_state(before, snapshot(live))
    assert not os.path.exists(material["out"] / "interrupted - Master.wav")
