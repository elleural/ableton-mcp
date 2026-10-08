"""The ref and meter tools (MCP_Server/tools/references.py) without Live, Spotify or an audio device."""
import time

import numpy as np
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from ears import meter as ears_meter
from ears import profile as profiles
from ears import refs as ears_refs
from MCP_Server.tools import references
from tests.ears.test_references import RATE, FakePlayer, groove

URI = "spotify:track:32ZmFcP0qeEIuXtO6TDZ1K"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("EARS_REFS", str(tmp_path / "refs"))
    monkeypatch.setattr(references, "_live_playing", lambda: False)
    monkeypatch.setattr(ears_refs, "alert_device", lambda: "MacBook Pro Speakers")
    references._JOB.clear()
    yield
    if references._JOB.get("state") == "measuring":
        references._JOB["stop"].set()
        time.sleep(0.5)
    references._JOB.clear()


def _fakes(monkeypatch, seconds=24.0):
    song = np.concatenate([np.zeros((int(0.6 * RATE), 2)), groove(124.0, seconds)])
    player = FakePlayer(duration=seconds + 0.6)
    monkeypatch.setattr(references, "Spotify", lambda **kwargs: player)
    monkeypatch.setattr(references.ears_meter, "LoopbackInput", lambda: ears_meter.ArrayInput(song, RATE))
    return player


def test_status_is_idle_and_cancel_needs_a_job():
    assert references.ref() == {"state": "idle", "references": 0}
    with pytest.raises(ToolError, match="No measurement"):
        references.ref(action="cancel")
    with pytest.raises(ToolError, match="action must be"):
        references.ref(action="dance")


def test_measure_refuses_bad_input_and_a_playing_live(monkeypatch):
    with pytest.raises(ToolError, match="needs uri"):
        references.ref(action="measure")
    with pytest.raises(ToolError, match="Not a Spotify track"):
        references.ref(action="measure", uri="spotify:album:7lcpCG4RBy3njzxHXlhOnp")
    for bad in ({"drop": [72]}, {"drop": [102, 72]}, {"drop": "1:12"}, []):
        with pytest.raises(ToolError, match="(?i)section"):
            references.ref(action="measure", uri=URI, sections=bad)
    monkeypatch.setattr(references, "_live_playing", lambda: True)
    with pytest.raises(ToolError, match="Live is playing"):
        references.ref(action="measure", uri=URI)


def test_measure_runs_as_a_job_and_lists_the_reference(monkeypatch):
    player = _fakes(monkeypatch)
    out = references.ref(action="measure", uri="https://open.spotify.com/track/32ZmFcP0qeEIuXtO6TDZ1K?si=x", wait=60)
    assert out["state"] == "finished" and len(out["done"]) == 1 and not out.get("error")
    done = out["done"][0]
    assert done["name"] == "closer" and not done["cached"] and set(done["sections"]) >= {"track", "full"}
    assert ("play", URI, None) in player.calls
    listed = references.ref(action="list")
    assert [item["name"] for item in listed["references"]] == ["closer"] and listed["envelope"]["references"] == ["closer"]
    again = references.ref(action="measure", uri=URI, wait=30)
    assert again["done"][0]["cached"]


def test_a_failed_measurement_reports_its_error(monkeypatch):
    _fakes(monkeypatch)
    monkeypatch.setattr(references.ears_meter, "LoopbackInput", lambda: ears_meter.ArrayInput(np.zeros((RATE * 30, 2)), RATE))
    out = references.ref(action="measure", uri=URI, wait=60)
    assert out["state"] == "failed" and "No signal" in out["error"]


def test_setup_reports_m6_and_only_frederic_confirms_it(monkeypatch):
    _fakes(monkeypatch)
    first = references.ref(action="setup")
    assert first["confirmed"] == {} and any("Ask Frederic" in item and "ears ref setup --confirm" in item for item in first["warnings"])
    with pytest.raises(TypeError):
        references.ref(action="setup", confirm=True)                     # the agent cannot confirm it for him
    ears_refs.confirm_setup()                                             # what `ears ref setup --confirm` does
    assert references.ref(action="setup")["warnings"] == []


def test_the_loopback_is_guarded_while_a_reference_plays(monkeypatch):
    from MCP_Server.tools import clips, song
    references._JOB.update(id="ref-1", state="measuring", stop=__import__("threading").Event(), done=[], started=time.time())
    for call in (lambda: references.ref(action="pause"), lambda: references.ref(action="play", uri=URI),
                 lambda: references.meter(seconds=5), lambda: song.fire_scene(0), lambda: song.transport("play"),
                 lambda: clips.fire_clip("kick", 0)):
        with pytest.raises(ToolError, match="measur"):
            call()
    assert references.loopback_busy().startswith("A reference is being measured")
    references._JOB["state"] = "finished"
    assert references.loopback_busy() is None


def test_meter_of_live_refuses_while_spotify_plays_and_drops_levels_when_unsure(monkeypatch):
    _fakes(monkeypatch)
    monkeypatch.setattr(references, "_live_playing", lambda: True)
    monkeypatch.setattr(references, "_spotify_playing", lambda: True)
    with pytest.raises(ToolError, match="Spotify is playing"):
        references.meter(seconds=5, source="live")
    monkeypatch.setattr(references, "_spotify_playing", lambda: None)
    unsure = references.meter(seconds=5, source="live")
    assert "lufs_i" not in unsure["profile"] and "Could not check whether Spotify" in unsure["warning"]


def test_a_cancelled_job_says_cancelled_and_a_finished_one_finished(monkeypatch):
    _fakes(monkeypatch, seconds=30.0)
    real_record = ears_meter.ArrayInput.record

    def slow(self, seconds, stop=None, progress=None, started=None):    # a real-time input: cancel lands mid-track
        if seconds > 5:
            for _ in range(100):
                if stop is not None and stop.is_set():
                    break
                time.sleep(0.05)
        return real_record(self, seconds, stop=stop, progress=progress, started=started)

    monkeypatch.setattr(ears_meter.ArrayInput, "record", slow)
    references.ref(action="measure", uri=URI, wait=0.3)
    out = references.ref(action="cancel")
    assert out["state"] == "cancelled" and "Cancelled" in out["error"] and out["done"] == []
    assert ears_refs.all_refs() == []


def test_meter_checks_its_arguments_and_live(monkeypatch):
    for kwargs in ({"source": "radio"}, {"seconds": 1.0}, {"seconds": 500}):
        with pytest.raises(ToolError):
            references.meter(**kwargs)
    with pytest.raises(ToolError, match="Live is not playing"):
        references.meter(source="live")
    monkeypatch.setattr(references, "_live_playing", lambda: True)
    with pytest.raises(ToolError, match="Live is playing"):
        references.meter(source="external")


def test_meter_of_an_external_source_has_no_absolute_level(monkeypatch):
    _fakes(monkeypatch)
    out = references.meter(seconds=10, source="external")
    assert out["source"] == "external" and not set(out["profile"]) & set(profiles.ABSOLUTE_KEYS)
    monkeypatch.setattr(references, "_live_playing", lambda: True)
    live = references.meter(seconds=10, source="live")
    assert "lufs_i" in live["profile"]


def test_delete_and_add(tmp_path):
    from ears.audio import write_wav
    path = tmp_path / "mine.wav"
    write_wav(path, groove(124.0, 12.0), RATE, bit_depth=24)
    added = references.ref(action="add", file=str(path), name="mine")
    assert added["added"]["name"] == "mine" and added["added"]["source"] == "file"
    assert references.ref(action="delete", name="mine") == {"deleted": "mine"}
    with pytest.raises(ToolError):
        references.ref(action="delete", name="mine")
    with pytest.raises(ToolError):
        references.ref(action="add", file=str(tmp_path / "missing.wav"))


def test_check_counts_leave_out_reference_dependent_and_skipped_checks(tmp_path):
    import json
    from types import SimpleNamespace
    from MCP_Server.tools import listening

    def take(name, checks):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "report.json").write_text(json.dumps({"checks": [{"check": c, "subject": s, "status": st} for c, s, st in checks]}))
        return SimpleNamespace(path=folder)

    best = take("best", [("audio.loudness", "T5@A", "pass"), ("audio.balance", "T5@A", "skip"), ("audio.key", "mix", "warn"),
                         ("audio.parts", "take", "skip")])
    latest = take("latest", [("audio.loudness", "T5@A", "pass"), ("audio.balance", "T5@A", "warn"), ("audio.key", "mix", "warn"),
                             ("audio.parts", "take", "fail")])
    assert listening.comparable_counts(latest, best) == {"a": {"fail": 0, "warn": 1}, "b": {"fail": 0, "warn": 1}}
    assert listening.comparable_counts(latest, take("empty", [])) == {"a": {"fail": 0, "warn": 0}, "b": {"fail": 0, "warn": 0}}
    assert listening.comparable_counts(latest, SimpleNamespace(path=tmp_path / "missing")) is None
