"""Live tests for WS-F clip automation: write_automation, get_automation and clear_automation.

Scratch tracks and scenes only. Values are written in display units (dB, Hz, pan) and read back with
value_at_time, also in display units. Arrangement placements start at beat 1200, away from anything else.
"""
import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from AbletonMCP_Remote_Script.values import parse_display_number
from MCP_Server.connection import AbletonError
from MCP_Server.tools.arrangement import arrange_from_scenes
from MCP_Server.tools.automation import clear_automation, get_automation, write_automation
from tests.live.conftest import scene_names, track_names

BASE = 1200.0


def tpath(live, name):
    return "live_set tracks {0}".format(track_names(live).index(name))


def scene_index(live, name):
    return scene_names(live).index(name)


def under(live, track, rest, command, **params):
    """Send a LOM command for a path under the named track. Other builders add and remove tracks and
    scenes meanwhile, so the path is resolved just before sending and again if it went stale."""
    for attempt in range(3):
        suffix = rest(live) if callable(rest) else rest
        path = " ".join(part for part in (tpath(live, track), suffix) if part)
        try:
            return live.send_command(command, dict(params, path=path))
        except AbletonError as error:
            if attempt == 2 or "out of range" not in str(error):
                raise


def session_clip(live, track, scene, length=4.0):
    under(live, track, lambda live: "clip_slots {0}".format(scene_index(live, scene)), "lom_call", method="create_clip", args=[float(length)])
    return scene_index(live, scene)


def number(display):
    return parse_display_number(display)


def sample_at(result, at):
    samples = (result.get("envelope") or result)["samples"]
    for sample in samples:
        if abs(sample["time"] - at) < 1e-6:
            return sample
    raise AssertionError("no sample at {0}: {1}".format(at, samples))


@pytest.fixture
def clip(live, scratch):
    """(track name, slot) of a 1-bar MIDI clip on a scratch track."""
    track = scratch.track("auto")
    scene = scratch.scene("s")
    return track, session_clip(live, track, scene, 4.0)


def test_points_in_db_round_trip_without_moving_the_fader(live, clip):
    track, slot = clip
    def fader():
        return under(live, track, "mixer_device volume", "lom_get", properties=["value"])["values"]["value"]["value"]
    before = fader()
    result = write_automation(track, "volume", slot=slot, points=[{"time": 0, "value": -12}, {"time": "1.3.1", "value": "0 dB"}])
    assert result["created_envelope"] is True and result["points_written"] == 2
    assert result["parameter"]["parameter"] == "volume" and result["parameter"]["range"][1] == "6.0 dB"
    assert result["range"]["start"]["beats"] == 0.0 and result["range"]["end"] == {"beats": 2.0, "bar": "1.3.1"}
    assert number(result["samples"][0]["display"]) == pytest.approx(-12, abs=0.01)
    assert number(result["samples"][-1]["display"]) == pytest.approx(0, abs=0.01)
    assert fader() == before  # display conversion never touches the parameter

    read = get_automation(track, slot=slot, parameter="volume", samples=5)
    assert read["has_envelopes"] and read["automated"] == [{"parameter": "volume"}]
    envelope = read["envelope"]
    assert envelope["event_count"] == 2 and [event["time"] for event in envelope["events"]] == [0.0, 2.0]
    assert number(envelope["events"][0]["display"]) == pytest.approx(-12, abs=0.01)
    assert [sample["time"] for sample in envelope["samples"]] == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert number(sample_at(read, 1.0)["display"]) == pytest.approx(-6, abs=0.1)  # half way along the ramp
    assert number(sample_at(read, 3.0)["display"]) == pytest.approx(0, abs=0.01)   # holds after the last point


def test_shapes_on_device_and_mixer_parameters(live, scratch):
    track = scratch.track("shapes")
    scene = scratch.scene("s")
    slot = session_clip(live, track, scene, 4.0)
    under(live, track, "", "lom_call", method="insert_device", args=["Auto Filter"])

    sine = write_automation(track, "Frequency", slot=slot, device="Auto Filter",
                            shape={"type": "sine", "from": 200, "to": "2 kHz", "period": "1 bar"})
    assert sine["parameter"] == {"parameter": "Frequency", "device": "Auto Filter", "name": "Frequency", "range": sine["parameter"]["range"]}
    assert sine["points_written"] == 17 and sine["range"]["end"]["beats"] == 4.0
    read = get_automation(track, slot=slot, parameter="Frequency", device="Auto Filter", samples=5)
    hertz = [number(sample["display"]) for sample in read["envelope"]["samples"]]
    assert hertz == [pytest.approx(expected, rel=0.02) for expected in (200, 1100, 2000, 1100, 200)]

    write_automation(track, "pan", slot=slot, shape={"type": "square", "from": -1, "to": "50R", "period": 2})
    pan = get_automation(track, slot=slot, parameter="pan", samples=9)["envelope"]["samples"]
    assert [sample["display"] for sample in pan if sample["time"] % 1 == 0.5] == ["50L", "50R", "50L", "50R"]

    write_automation(track, "send:A", slot=slot, shape={"type": "steps", "steps": ["-inf", -12, -6, 0], "period": "1 bar"})
    send = get_automation(track, slot=slot, parameter="send:A", samples=9)["envelope"]["samples"]
    assert [number(sample["display"]) for sample in send if sample["time"] % 1 == 0.5] == [float("-inf"), pytest.approx(-12, abs=0.05), pytest.approx(-6, abs=0.05), pytest.approx(0, abs=0.05)]

    write_automation(track, "volume", slot=slot, shape={"type": "saw", "from": -24, "to": 0, "period": 2})
    saw = get_automation(track, slot=slot, parameter="volume", samples=9)
    assert number(sample_at(saw, 0.0)["display"]) == pytest.approx(-24, abs=0.01)
    assert number(sample_at(saw, 1.5)["display"]) > -8      # rising towards 0 dB
    assert number(sample_at(saw, 2.5)["display"]) < -15     # dropped back to -24 at beat 2 and rising again

    write_automation(track, "Filter Type", slot=slot, device="Auto Filter", shape={"type": "steps", "steps": ["Low-pass", "High-pass"]})
    filter_type = get_automation(track, slot=slot, parameter="Filter Type", device="Auto Filter", samples=5)["envelope"]["samples"]
    assert [sample["value"] for sample in filter_type][1:4:2] == [0.0, 1.0]  # beat 1: Low-pass, beat 3: High-pass

    write_automation(track, "Resonance", slot=slot, device=0, units="raw", shape={"type": "triangle", "from": 0.0, "to": 1.0, "period": 4})
    resonance = get_automation(track, slot=slot, parameter="Resonance", device=0, samples=5)["envelope"]["samples"]
    assert [sample["value"] for sample in resonance] == [pytest.approx(v, abs=1e-4) for v in (0.0, 0.5, 1.0, 0.5, 0.0)]

    automated = get_automation(track, slot=slot)["automated"]
    assert {"parameter": "volume"} in automated and {"parameter": "send:A"} in automated
    assert {"parameter": "Frequency", "device": "Auto Filter"} in automated and len(automated) == 6


def test_clear_range_replaces_only_the_range(live, clip):
    track, slot = clip
    write_automation(track, "volume", slot=slot, points=[{"time": t, "value": -3 * t} for t in range(5)])
    write_automation(track, "volume", slot=slot, points=[{"time": 1, "value": -30}, {"time": 3, "value": -30}])
    events = get_automation(track, slot=slot, parameter="volume")["envelope"]["events"]
    assert [event["time"] for event in events] == [0.0, 1.0, 3.0, 4.0]  # 1..3 replaced, ends included
    write_automation(track, "volume", slot=slot, points=[{"time": 2, "value": -6}], clear_range=False)
    events = get_automation(track, slot=slot, parameter="volume")["envelope"]["events"]
    assert [event["time"] for event in events] == [0.0, 1.0, 2.0, 3.0, 4.0]
    jump = write_automation(track, "volume", slot=slot, points=[{"time": 2, "value": -40}, {"time": 2, "value": 0}], start=2, end=2)
    assert jump["points_written"] == 2
    read = get_automation(track, slot=slot, parameter="volume", samples=0)
    assert [event["time"] for event in read["envelope"]["events"]].count(2.0) == 2


def test_arrangement_copies_carry_editable_envelopes(live, scratch, song_state):
    track = scratch.track("arr")
    scene = scratch.scene("s")
    slot = session_clip(live, track, scene, 4.0)
    write_automation(track, "volume", slot=slot, shape={"type": "ramp", "from": -24, "to": 0})
    source_before = sample_at(get_automation(track, slot=slot, parameter="volume", samples=5), 1.0)["display"]
    arrange_from_scenes([{"scene": scene, "bars": 2}], start=BASE, tracks=[track], locators=False)
    copied = get_automation(track, arrangement_clip=0, parameter="volume", samples=5)
    assert sample_at(copied, 1.0)["display"] == source_before

    edited = write_automation(track, "volume", arrangement_clip=0, points=[{"time": 1, "value": -6}], clear_range=False)
    assert edited["created_envelope"] is False and edited["clip"]["arrangement_clip"] == 0
    arrangement = get_automation(track, arrangement_clip=0, parameter="volume", samples=5)
    session = get_automation(track, slot=slot, parameter="volume", samples=5)
    assert number(sample_at(arrangement, 1.0)["display"]) == pytest.approx(-6, abs=0.05)
    assert sample_at(session, 1.0)["display"] == source_before  # the Session source is untouched

    with pytest.raises(ToolError) as error:
        write_automation(track, "pan", arrangement_clip=0, points=[{"time": 0, "value": 0}])
    assert "cannot create one on arrangement clips" in str(error.value) and "Session clip" in str(error.value)

    cleared = clear_automation(track, arrangement_clip=0)
    assert cleared["cleared"] == "all" and cleared["has_envelopes"] is False and cleared["automated"] == []
    assert get_automation(track, slot=slot)["has_envelopes"] is True


def test_clear_automation_one_then_all(live, clip):
    track, slot = clip
    write_automation(track, "volume", slot=slot, points=[{"time": 0, "value": -6}])
    write_automation(track, "pan", slot=slot, points=[{"time": 0, "value": 0.5}])
    one = clear_automation(track, slot=slot, parameter="pan")
    assert one["cleared"] == {"parameter": "pan"} and one["automated"] == [{"parameter": "volume"}]
    assert get_automation(track, slot=slot, parameter="pan")["envelope"] is None
    again = clear_automation(track, slot=slot, parameter="pan")
    assert again["cleared"]["note"] == "no envelope to clear"
    every = clear_automation(track, slot=slot)
    assert every["cleared"] == "all" and every["has_envelopes"] is False


WRITE_ERRORS = [
    ({"parameter": "volume"}, "exactly one of points"),
    ({"parameter": "volume", "points": [{"time": 0, "value": 0}], "shape": {"type": "ramp", "from": 0, "to": 1}}, "exactly one of points"),
    ({"parameter": "volume", "points": [{"time": 0, "value": 0}], "units": "db"}, "units must be"),
    ({"parameter": "volume", "points": [{"time": 0, "value": 20}]}, "outside the range"),
    ({"parameter": "volume", "points": [{"time": 0}]}, "'time' and 'value'"),
    ({"parameter": "volume", "shape": {"type": "wobble", "from": 0, "to": 1}}, "type must be one of"),
    ({"parameter": "volume", "shape": {"type": "sine", "from": 0, "to": 1, "speed": 2}}, "unknown keys"),
    ({"parameter": "cutoff", "points": [{"time": 0, "value": 0}]}, "not found"),
    ({"parameter": "volume", "points": [{"time": 0, "value": 0.5}], "units": "raw", "start": 2, "end": 1}, "before start"),
]


def test_write_automation_errors_change_nothing(live, clip):
    track, slot = clip
    for kwargs, message in WRITE_ERRORS:
        with pytest.raises(ToolError) as error:
            write_automation(track, slot=slot, **kwargs)
        assert message in str(error.value), (kwargs, str(error.value))
    assert get_automation(track, slot=slot)["has_envelopes"] is False  # nothing was written


def test_empty_slot_and_missing_clip_ref(live, scratch):
    track = scratch.track("empty")
    scene = scratch.scene("s")
    with pytest.raises(ToolError) as error:
        get_automation(track, slot=scene_index(live, scene))
    assert "is empty" in str(error.value)
    with pytest.raises(ToolError) as error:
        clear_automation(track)
    assert "exactly one of slot" in str(error.value)
