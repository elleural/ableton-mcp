"""Live checks for the review fixes (M4): sidechain, one-call clips, locator times, naming and error safety."""
import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server.app import LiveToolError
from MCP_Server.tools.arrangement import clear_arrangement, get_arrangement
from MCP_Server.tools.clips import create_clip, get_notes
from MCP_Server.tools.devices import get_device, set_device_parameters, set_sidechain
from MCP_Server.tools.export import bounce, cancel_bounce, get_bounce_status
from MCP_Server.tools.song import create_locator, delete_locator
from MCP_Server.tools.status import get_status
from MCP_Server.tools.tracks import create_track


def _parameter(device, name):
    return next(item for item in device["parameters"] if item["name"] == name)


def test_set_sidechain_routes_and_enables(scratch):
    kick = create_track("midi", scratch.name("Kick"), device="Operator")["name"]
    bass = create_track("midi", scratch.name("Bass"), device="Operator")["name"]
    result = set_sidechain(bass, kick, threshold_db=-30, ratio=6, attack_ms=2, release_ms=150)
    assert result["added_compressor"] is True and result["source"] == kick
    compressor = get_device(bass, result["device"])
    assert compressor["properties"]["input_routing_type"]["value"] == kick
    assert _parameter(compressor, "S/C On")["display"].lower() == "on"
    assert _parameter(compressor, "Threshold")["display"].startswith("-30")
    # A Compressor it adds gets the kick-ducking defaults: Peak and a 120 Hz low-pass trigger.
    shown = [_parameter(compressor, name)["display"] for name in ("Model", "S/C EQ On", "S/C EQ Type")]
    assert shown == ["Peak", "On", "Low pass"]
    assert _parameter(compressor, "S/C EQ Freq")["display"].startswith("120")
    changed = set_sidechain(bass, kick, model="RMS", sidechain_eq={"type": "Bell", "freq": 60, "gain": 6})
    assert "errors" not in changed and "as_found" not in changed
    compressor = get_device(bass, result["device"])
    assert [_parameter(compressor, name)["display"] for name in ("Model", "S/C EQ Type")] == ["RMS", "Bell"]
    assert _parameter(compressor, "S/C EQ Freq")["display"].startswith("60")
    assert _parameter(compressor, "S/C EQ Gain")["display"].startswith("6")
    kept = set_sidechain(bass, kick, sidechain_eq="off")  # an existing Compressor keeps what the call leaves out
    assert kept["as_found"] == {"Model": "RMS"}
    assert _parameter(get_device(bass, result["device"]), "S/C EQ On")["display"] == "Off"
    off = set_sidechain(bass, enabled=False)
    assert off["enabled"] is False and off["device"] == result["device"]  # reuses the same Compressor


def test_create_clip_fills_pattern_and_notes(scratch):
    drums = create_track("midi", scratch.name("Drums"), device="Drum Rack")["name"]
    clip = create_clip(drums, slot=0, length="1 bar", pattern={"kick": "x---x---x---x---"})
    assert clip["undo_steps"] == 2
    assert len(get_notes(drums, slot=0)["notes"]) == 4
    keys = create_track("midi", scratch.name("Keys"), device="Operator")["name"]
    create_clip(keys, slot=0, length=4, notes=[{"chord": "Am", "start": 0, "duration": 4}])
    assert len(get_notes(keys, slot=0)["notes"]) == 3


def test_locator_names_work_as_times(scratch, song_state):
    track = create_track("midi", scratch.name("Loc"), device="Operator")["name"]
    create_clip(track, at=0, length="8 bars")
    name = scratch.name("Section")
    create_locator("5.1.1", name)
    try:
        window = get_arrangement(start=name, tracks=[track])
        assert window["tracks"][0]["clips"], window
        with pytest.raises(ToolError):
            clear_arrangement()  # no tracks and no all_tracks: refused, nothing deleted
        assert get_arrangement(tracks=[track])["tracks"][0]["clips"]
    finally:
        delete_locator(name)


def test_duplicate_track_names_are_refused(scratch):
    name = scratch.name("Unique")
    create_track("midi", name)
    with pytest.raises(LiveToolError) as error:
        create_track("audio", name)
    assert error.value.code == "invalid_argument"
    assert str(error.value).startswith("[invalid_argument]")


def test_raw_values_out_of_range_are_errors(scratch):
    track = create_track("audio", scratch.name("Fx"), device="Reverb")["name"]
    with pytest.raises(LiveToolError) as error:  # a raw 30 on a 0..1 parameter must not be clamped silently
        set_device_parameters(track, "Reverb", {"Dry/Wet": 30})
    assert "raw range" in str(error.value) and "30 %" in str(error.value)
    applied = set_device_parameters(track, "Reverb", {"Dry/Wet": "30 %"})
    reverb = get_device(track, "Reverb")
    assert _parameter(reverb, "Dry/Wet")["display"].startswith("30"), applied


def test_status_reports_a_running_bounce(scratch, tmp_path):
    track = create_track("midi", scratch.name("Tone"), device="Operator")["name"]
    create_clip(track, at=0, length="1 bar", notes=[{"pitch": "C3", "start": 0, "duration": 1}])
    job = bounce(start=0, end="2.1.1", tail="0.5 s", name="status-check", output_dir=str(tmp_path))
    try:
        time.sleep(0.5)
        jobs = get_status()["jobs"]
        assert any(entry.get("kind") == "bounce" for entry in jobs), jobs
        status = job
        for _ in range(6):
            status = get_bounce_status(wait=20)
            if status.get("phase") in ("done", "failed", "cancelled"):
                break
        assert status.get("phase") == "done", status
    finally:
        if get_bounce_status().get("phase") not in ("done", "failed", "cancelled", "idle"):
            cancel_bounce()
