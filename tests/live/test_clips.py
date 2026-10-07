"""Live tests for clips, notes, drum patterns and clip actions (WS-C).

Run with: uv run pytest tests/live/test_clips.py -x   (needs Ableton Live with the AbletonMCP Remote Script)

Everything happens on "[test:clips] ..." scratch tracks addressed by name. The MCP tool functions are called
directly, so each test exercises the tool and its Remote Script command together.
"""
import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server.connection import AbletonError
from MCP_Server.tools import clips as C
from MCP_Server.tools.theory import music_theory
from tests.live.conftest import lom_value, track_names

PING = "/System/Library/Sounds/Ping.aiff"  # 1.5 s, stereo 48 kHz
POP = "/System/Library/Sounds/Pop.aiff"


def track_path(live, name):
    return "live_set tracks {0}".format(track_names(live).index(name))


def wait_for(read, accept, timeout=4.0):
    """Poll read() until accept(value) (Live applies launches and stops on a later tick)."""
    deadline = time.time() + timeout
    value = read()
    while not accept(value) and time.time() < deadline:
        time.sleep(0.1)
        value = read()
    return value


def starts(result):
    return [note["start"] for note in result["notes"]]


def pitches(result):
    return [note["pitch"] for note in result["notes"]]


# ---------------------------------------------------------------------------
# Session clips: create, read, set, delete
# ---------------------------------------------------------------------------


def test_session_clip_lifecycle(live, scratch):
    track = scratch.track("lifecycle")
    clip = C.create_clip(track=track, slot=0, length="2 bars", name="Verse", color=5)
    assert (clip["slot"], clip["track_name"], clip["name"], clip["kind"]) == (0, track, "Verse", "midi")
    assert (clip["length"], clip["bars"], clip["loop"], clip["color_index"]) == (8, 2, {"start": 0, "end": 8}, 5)
    assert clip["state"] == "stopped" and clip["note_count"] == 0 and clip["signature"] == "4/4"

    with pytest.raises(ToolError, match="already holds clip 'Verse'"):
        C.create_clip(track=track, slot=0)
    with pytest.raises(ToolError, match="not both"):
        C.create_clip(track=track, slot=1, at=0)
    with pytest.raises(ToolError, match="not both"):
        C.create_clip(track=track)
    with pytest.raises(ToolError, match="MIDI track"):
        C.create_clip(track=track, slot=1, file_path=PING)
    with pytest.raises(ToolError, match="out of range"):
        C.create_clip(track=track, slot=999)
    with pytest.raises(ToolError, match="no clip slots|clips live on"):
        C.create_clip(track="master", slot=0)

    info = C.set_clip(track=track, slot=0, signature="3/4", loop_start=2, loop_end="3.1.1", start_marker=1, end_marker=7,
                      launch_mode="gate", launch_quantization="1/4", legato=True, muted=True, velocity_amount=0.5,
                      grid="1/8", grid_triplet=True, color="#FF0000", name="Chorus")
    assert info["signature"] == "3/4" and info["loop"] == {"start": 2, "end": 6} and info["markers"] == {"start": 1, "end": 7}
    assert (info["launch_mode"], info["launch_quantization"], info["legato"], info["muted"]) == ("gate", "1/4", True, True)
    assert info["velocity_amount"] == 0.5 and info["grid"] == {"quantization": "1/8", "triplet": True} and info["name"] == "Chorus"

    # Loop and markers on an unlooped clip: the loop brace persists while looping stays off.
    info = C.set_clip(track=track, slot=0, looping=False)
    assert info["looping"] is False and "loop" not in info and info["markers"] == {"start": 1, "end": 7}
    info = C.set_clip(track=track, slot=0, loop_end=4, end_marker=5)
    assert info["looping"] is False and info["markers"] == {"start": 1, "end": 5}
    assert C.set_clip(track=track, slot=0, looping=True)["loop"] == {"start": 2, "end": 4}

    grooves = live.send_command("lom_get", {"path": "live_set groove_pool", "properties": ["grooves"]})["values"]["grooves"]
    if grooves.get("count"):
        assert C.set_clip(track=track, slot=0, groove=0)["groove"] is not None

    with pytest.raises(ToolError, match="must be before"):
        C.set_clip(track=track, slot=0, loop_start=9)
    with pytest.raises(ToolError, match="audio clips"):
        C.set_clip(track=track, slot=0, gain_db=-3)
    with pytest.raises(ToolError, match="launch_mode must be one of"):
        C.set_clip(track=track, slot=0, launch_mode="sometimes")
    with pytest.raises(ToolError, match="cannot remove"):
        C.set_clip(track=track, slot=0, groove="none")
    with pytest.raises(ToolError, match="colour"):
        C.set_clip(track=track, slot=0, color="red")

    assert C.get_clip(track=track, slot=0)["name"] == "Chorus"
    assert C.delete_clip(track=track, slot=0)["deleted"] == {"track": info["track"], "slot": 0, "track_name": track, "name": "Chorus", "kind": "midi"}
    with pytest.raises(ToolError, match="empty"):
        C.get_clip(track=track, slot=0)
    with pytest.raises(ToolError, match="exactly one"):
        C.get_clip(track=track, slot=0, arrangement_clip=0)
    with pytest.raises(ToolError, match="not found"):
        C.get_clip(track="[test:clips] no such track", slot=0)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


def test_write_read_edit_delete_notes(scratch):
    track = scratch.track("notes")
    C.create_clip(track=track, slot=0, length="2 bars")
    written = C.write_notes(track=track, slot=0, notes=[
        {"pitch": "C3", "start": 0, "duration": 1, "velocity": 90, "probability": 0.5, "velocity_deviation": -10, "release_velocity": 30},
        {"pitch": 64, "start": "1.2.1", "duration": "1/8"},
        {"pitches": ["C3", "E3", "G3"], "start": "2.1.1", "duration": 2},
        {"chord": "Am7", "octave": 2, "start": 6, "duration": 1, "mute": True},
    ])
    assert written["added"] == 9 and written["note_count"] == 9 and len(written["note_ids"]) == 9 and "warnings" not in written

    notes = C.get_notes(track=track, slot=0)
    assert notes["count"] == 9 and starts(notes) == [0, 1, 4, 4, 4, 6, 6, 6, 6]
    first = notes["notes"][0]
    assert first == {"note_id": first["note_id"], "pitch": 60, "name": "C3", "start": 0, "duration": 1, "velocity": 90,
                     "probability": 0.5, "velocity_deviation": -10, "release_velocity": 30, "mute": False}
    assert notes["notes"][1]["duration"] == 0.5 and notes["notes"][-1]["mute"] is True
    assert pitches(C.get_notes(track=track, slot=0, pitches=["C3"])) == [60, 60, 60]
    assert pitches(C.get_notes(track=track, slot=0, pitch_min="E3", pitch_max=67)) == [64, 64, 67, 64, 67]
    assert starts(C.get_notes(track=track, slot=0, start="2.1.1", end=6)) == [4, 4, 4]
    limited = C.get_notes(track=track, slot=0, limit=2)
    assert limited["count"] == 9 and len(limited["notes"]) == 2 and limited["truncated"] is True
    assert C.get_notes(track=track, slot=0, note_ids=[first["note_id"]])["count"] == 1

    edited = C.edit_notes(track=track, slot=0, edits=[{"note_id": first["note_id"], "pitch": "D3", "start": 0.5, "velocity": 70}])
    assert edited["notes"] == [dict(first, pitch=62, name="D3", start=0.5, velocity=70)]
    with pytest.raises(ToolError, match="not in clip"):
        C.edit_notes(track=track, slot=0, edits=[{"note_id": 999999, "velocity": 10}])
    with pytest.raises(ToolError, match="unknown keys"):
        C.edit_notes(track=track, slot=0, edits=[{"note_id": first["note_id"], "colour": 3}])

    # Notes copied from get_notes output can be written back as-is.
    copy = C.write_notes(track=track, slot=0, notes=C.get_notes(track=track, slot=0, pitches=[62])["notes"], mode="replace_range", start=0.5, end=1)
    assert copy["removed"] == 1 and copy["added"] == 1 and copy["range"] == {"start": 0.5, "end": 1}

    ranged = C.write_notes(track=track, slot=0, notes=[{"pitch": 72, "start": 4, "duration": 1}], mode="replace_range", start="2.1.1", end=6)
    assert ranged["removed"] == 3 and ranged["note_count"] == 7
    late = C.write_notes(track=track, slot=0, notes=[{"pitch": 72, "start": 9, "duration": 1}])
    assert "will not play" in late["warnings"][0]

    assert C.delete_notes(track=track, slot=0, note_ids=late["note_ids"])["deleted"] == 1
    assert C.delete_notes(track=track, slot=0, pitches=["A2"])["deleted"] == 1
    assert C.delete_notes(track=track, slot=0, start=6, end=7)["deleted"] == 3
    with pytest.raises(ToolError, match="Say which notes"):
        C.delete_notes(track=track, slot=0)
    with pytest.raises(ToolError, match="drop the filters"):
        C.delete_notes(track=track, slot=0, all=True, pitches=[60])
    with pytest.raises(ToolError, match="not in clip"):
        C.delete_notes(track=track, slot=0, note_ids=[999999])
    remaining = C.delete_notes(track=track, slot=0, all=True)
    assert remaining["remaining"] == 0 and remaining["deleted"] == 3

    replaced = C.write_notes(track=track, slot=0, notes=[{"pitch": 60, "start": 0, "duration": 1}, {"pitch": 60, "start": 1, "duration": 1}])
    assert C.write_notes(track=track, slot=0, notes=[{"pitch": 48, "start": 0, "duration": 4}], mode="replace")["removed"] == 2
    assert replaced["added"] == 2
    with pytest.raises(ToolError, match="note name"):
        C.write_notes(track=track, slot=0, notes=[{"pitch": "H3", "start": 0, "duration": 1}])
    with pytest.raises(ToolError, match="mode must be one of"):
        C.write_notes(track=track, slot=0, notes=[{"pitch": 60, "start": 0, "duration": 1}], mode="merge")
    with pytest.raises(ToolError, match="replace_range"):
        C.write_notes(track=track, slot=0, notes=[{"pitch": 60, "start": 0, "duration": 1}], start=0)
    assert C.get_notes(track=track, slot=0)["count"] == 1


def set_song(live, **settings):
    """Set song properties in one round trip (the song_state fixture restores them)."""
    commands = [{"type": "lom_set", "params": {"path": "live_set", "property": name, "value": value}} for name, value in settings.items()]
    results = live.send_command("batch", {"commands": commands})["results"]
    assert all(item["status"] == "success" for item in results), results


def test_transform_notes(live, scratch, song_state):
    set_song(live, root_note=0, scale_name="Major")
    tempo = lom_value(live, "live_set", "tempo")
    track = scratch.track("transform")
    C.create_clip(track=track, slot=0, length=4)
    ids = C.write_notes(track=track, slot=0, notes=[
        {"pitch": "C3", "start": 0, "duration": 0.5}, {"pitch": "E3", "start": 1.1, "duration": 0.5},
        {"pitch": "G3", "start": 2.2, "duration": 0.5}, {"pitch": "B3", "start": 2.9, "duration": 0.25},
    ])["note_ids"]

    out = C.transform_notes(track=track, slot=0, operation="transpose", semitones=2, pitches=["C3"])
    assert (out["selected"], out["changed"], out["notes"][0]["pitch"], out["notes"][0]["note_id"]) == (1, 1, 62, ids[0])
    out = C.transform_notes(track=track, slot=0, operation="transpose", steps=1, pitch_min="E3")
    assert [note["pitch"] for note in out["notes"]] == [65, 69, 72] and out["scale"] == {"root": "C", "name": "Major"}

    out = C.transform_notes(track=track, slot=0, operation="quantize", grid="1/4")
    assert starts(C.get_notes(track=track, slot=0)) == [0, 1, 2, 3] and out["grid_beats"] == 1
    C.edit_notes(track=track, slot=0, edits=[{"note_id": ids[1], "start": 1.3}])
    C.transform_notes(track=track, slot=0, operation="quantize", grid="1/8", amount=0.5, note_ids=[ids[1]])
    assert C.get_notes(track=track, slot=0, note_ids=[ids[1]])["notes"][0]["start"] == pytest.approx(1.4)
    C.transform_notes(track=track, slot=0, operation="quantize", grid="1/8", swing=0.5, note_ids=[ids[1]])
    assert C.get_notes(track=track, slot=0, note_ids=[ids[1]])["notes"][0]["start"] == pytest.approx(1.625)

    out = C.transform_notes(track=track, slot=0, operation="humanize", timing="10ms", velocity=5, seed=1)
    assert out["seed"] == 1 and out["timing_beats"] == pytest.approx(0.01 * tempo / 60.0, abs=1e-6) and out["changed"] == 4
    for note in C.get_notes(track=track, slot=0)["notes"]:
        assert 95 <= note["velocity"] <= 105

    assert {note["velocity"] for note in C.transform_notes(track=track, slot=0, operation="velocity", value=80)["notes"]} == {80}
    assert {note["velocity"] for note in C.transform_notes(track=track, slot=0, operation="velocity", factor=0.5, offset=10)["notes"]} == {50}
    out = C.transform_notes(track=track, slot=0, operation="velocity", random=5, seed=2)
    assert all(45 <= note["velocity"] <= 55 for note in out["notes"]) and out["seed"] == 2

    C.edit_notes(track=track, slot=0, edits=[{"note_id": note_id, "start": index} for index, note_id in enumerate(ids)])
    C.transform_notes(track=track, slot=0, operation="legato")
    assert [note["duration"] for note in C.get_notes(track=track, slot=0)["notes"]] == [1, 1, 1, 0.25]
    reversed_out = C.transform_notes(track=track, slot=0, operation="reverse", start=0, end=2)
    assert reversed_out["region"] == {"start": 0, "end": 2} and reversed_out["changed"] == 2
    assert sorted(starts(C.get_notes(track=track, slot=0, end=2))) == [0, 1]
    out = C.transform_notes(track=track, slot=0, operation="stretch", factor=2, end=2)
    assert out["anchor"] == 0 and sorted(note["duration"] for note in out["notes"]) == [2, 2]
    out = C.transform_notes(track=track, slot=0, operation="shift", offset=1, pitches=["B3", "C4"])
    assert out["changed"] >= 1
    assert C.transform_notes(track=track, slot=0, operation="legato", pitches=[0])["hint"] == "No notes matched the filters"

    with pytest.raises(ToolError, match="operation must be one of"):
        C.transform_notes(track=track, slot=0, operation="explode")
    with pytest.raises(ToolError, match="grid do\\(es\\) not apply to transpose"):
        C.transform_notes(track=track, slot=0, operation="transpose", semitones=1, grid="1/16")
    with pytest.raises(ToolError, match="outside 0..127"):
        C.transform_notes(track=track, slot=0, operation="transpose", semitones=100)
    with pytest.raises(ToolError, match="stretch needs factor"):
        C.transform_notes(track=track, slot=0, operation="stretch")


# ---------------------------------------------------------------------------
# Drum patterns
# ---------------------------------------------------------------------------


def _drum_rack(live, track, pads):
    path = track_path(live, track)
    live.send_command("lom_call", {"path": path, "method": "insert_device", "args": ["Drum Rack"]})
    for name, note in pads:
        chain = live.send_command("lom_call", {"path": path + " devices 0", "method": "insert_chain", "args": []})["result"]["path"]
        live.send_command("lom_set", {"path": chain, "property": "in_note", "value": note})
        live.send_command("lom_set", {"path": chain, "property": "name", "value": name})


def test_drum_pattern_resolves_pads_and_gm(live, scratch):
    track = scratch.track("drums")
    _drum_rack(live, track, [("Kick 808", 36), ("Snare Tight", 38), ("Closed Hat", 42), ("Open Hat", 46)])
    C.create_clip(track=track, slot=0, length="2 bars")
    out = C.write_drum_pattern(track=track, slot=0, pattern={
        "kick": "x---x---x---x---", "Hat": "x.x.x.x.x.x.x.X.", "Clap": "----x-------x---", "snare": "-o",
    })
    lanes = dict((lane["drum"], lane) for lane in out["lanes"])
    assert (lanes["kick"]["pitch"], lanes["kick"]["source"], lanes["kick"]["hits"]) == (36, "pad 'Kick 808'", 8)
    assert (lanes["Hat"]["pitch"], lanes["Hat"]["source"], lanes["Hat"]["hits"]) == (42, "pad 'Closed Hat'", 16)
    assert (lanes["Clap"]["pitch"], lanes["Clap"]["source"]) == (39, "gm")
    assert (lanes["snare"]["pitch"], lanes["snare"]["hits"]) == (38, 16)
    assert any("Clap" in warning for warning in out["warnings"]) and out["region"] == {"start": 0, "end": 8}
    kicks = C.get_notes(track=track, slot=0, pitches=[36])
    assert starts(kicks) == [0, 1, 2, 3, 4, 5, 6, 7] and {note["velocity"] for note in kicks["notes"]} == {100}
    hats = C.get_notes(track=track, slot=0, pitches=["F#1"])["notes"]
    assert [note["velocity"] for note in hats[:8]] == [100] * 7 + [127]
    assert {note["velocity"] for note in C.get_notes(track=track, slot=0, pitches=[38])["notes"]} == {60}

    added = C.write_drum_pattern(track=track, slot=0, pattern={"36": "--x-------------"}, mode="add")
    assert added["lanes"][0]["source"] == "note" and added["removed"] == 0
    assert C.get_notes(track=track, slot=0, pitches=[36])["count"] == 10
    replaced = C.write_drum_pattern(track=track, slot=0, pattern={"Kick 808": "x-------"}, swing=0.5)
    assert replaced["removed"] == 10 and C.get_notes(track=track, slot=0, pitches=[36])["count"] == 4
    assert C.get_notes(track=track, slot=0, pitches=[42])["count"] == 16
    swung = C.write_drum_pattern(track=track, slot=0, pattern={"Open Hat": "xx"}, swing=0.5)
    assert starts(C.get_notes(track=track, slot=0, pitches=[46], end=1)) == [0, 0.3125, 0.5, 0.8125] and swung["lanes"][0]["hits"] == 32

    with pytest.raises(ToolError, match="Kick 808 \\(C1\\)"):
        C.write_drum_pattern(track=track, slot=0, pattern={"Theremin": "x---"})
    with pytest.raises(ToolError, match="several pads"):
        C.write_drum_pattern(track=track, slot=0, pattern={"Ha": "x---"})
    with pytest.raises(ToolError, match="step 2"):
        C.write_drum_pattern(track=track, slot=0, pattern={"Kick": "x?"})

    plain = scratch.track("drums plain")
    C.create_clip(track=plain, slot=0, length=1)
    out = C.write_drum_pattern(track=plain, slot=0, pattern={"Kick": "x---x---"})
    assert out["lanes"][0]["source"] == "gm" and "No Drum Rack" in out["warnings"][-1] and any("is 2 beats" in item for item in out["warnings"])


# ---------------------------------------------------------------------------
# Arrangement clips and duplication
# ---------------------------------------------------------------------------


def test_arrangement_clips_and_duplicates(live, scratch):
    track = scratch.track("arrangement")
    other = scratch.track("arrangement 2")
    audio = scratch.track("arrangement audio", "audio")
    clip = C.create_clip(track=track, at="2.1.1", length="1 bar", name="A")
    assert clip["arrangement_clip"] == 0 and clip["start"] == {"beats": 4.0, "bar": "2.1.1"} and clip["end"]["beats"] == 8.0
    C.write_notes(track=track, arrangement_clip=0, notes=[{"pitch": "C3", "start": 0, "duration": 1}, {"pitch": "D3", "start": 2, "duration": 1}])
    assert C.get_clip(track=track, arrangement_clip=0, notes=True)["note_count"] == 2
    assert C.set_clip(track=track, arrangement_clip=0, name="A1", muted=True)["muted"] is True
    with pytest.raises(ToolError, match="overlaps arrangement clip 0 'A1'"):
        C.create_clip(track=track, at=6, length=4)
    with pytest.raises(ToolError, match="out of range"):
        C.get_clip(track=track, arrangement_clip=5)

    copy = C.duplicate_clip(track=track, arrangement_clip=0)
    assert copy["clip"]["start"]["beats"] == 8.0 and copy["clip"]["arrangement_clip"] == 1 and copy["clip"]["note_count"] == 2
    across = C.duplicate_clip(track=track, arrangement_clip=0, to_track=other, to_time="1.1.1")
    assert across["clip"]["track_name"] == other and across["clip"]["start"]["beats"] == 0.0
    with pytest.raises(ToolError, match="overlaps"):
        C.duplicate_clip(track=track, arrangement_clip=0, to_time=10)
    moved = C.duplicate_clip(track=track, arrangement_clip=1, to_time=10, move=True)
    assert moved["moved"] is True and moved["clip"]["start"]["beats"] == 10.0
    assert [C.get_clip(track=track, arrangement_clip=index)["start"]["beats"] for index in range(2)] == [4.0, 10.0]
    with pytest.raises(ToolError, match="out of range"):
        C.get_clip(track=track, arrangement_clip=2)

    C.create_clip(track=track, slot=0, length=2, name="S")
    C.create_clip(track=track, slot=1, length=2, name="S2")
    to_arrangement = C.duplicate_clip(track=track, slot=0, to_time="9.1.1")
    assert to_arrangement["clip"]["start"]["beats"] == 32.0 and to_arrangement["clip"]["length"] == 2
    moved = C.duplicate_clip(track=track, slot=1, to_time=40, move=True)
    assert moved["clip"]["start"]["beats"] == 40.0
    with pytest.raises(ToolError, match="empty"):
        C.get_clip(track=track, slot=1)
    session_copy = C.duplicate_clip(track=track, slot=0)
    assert session_copy["clip"]["slot"] == 1 and session_copy["clip"]["name"] == "S"
    with pytest.raises(ToolError, match="already holds"):
        C.duplicate_clip(track=track, slot=0, to_slot=1)
    assert C.duplicate_clip(track=track, slot=0, to_track=other, to_slot=3)["clip"]["slot"] == 3
    moved = C.duplicate_clip(track=track, slot=1, to_slot=4, move=True)
    assert moved["clip"]["slot"] == 4
    with pytest.raises(ToolError, match="Session slot"):
        C.duplicate_clip(track=track, arrangement_clip=0, to_slot=2)
    with pytest.raises(ToolError, match="to_slot"):
        C.duplicate_clip(track=track, slot=0, to_track=other)
    with pytest.raises(ToolError, match="Cannot copy a MIDI clip"):
        C.duplicate_clip(track=track, slot=0, to_track=audio, to_slot=0)

    deleted = C.delete_clip(track=track, arrangement_clip=0)
    assert deleted["deleted"]["arrangement_clip"] == 0 and deleted["deleted"]["name"] == "A1"
    assert C.get_clip(track=track, arrangement_clip=0)["start"]["beats"] == 10.0


# ---------------------------------------------------------------------------
# Audio clips
# ---------------------------------------------------------------------------


def test_audio_clips(scratch):
    track = scratch.track("audio", "audio")
    clip = C.create_clip(track=track, slot=0, file_path=PING, name="Ping")
    assert clip["kind"] == "audio" and clip["audio"]["file_path"] == PING and clip["audio"]["sample_rate"] == 48000
    assert clip["audio"]["gain_db"] == 0.0 and "notes" not in clip
    with pytest.raises(ToolError, match="pass file_path"):
        C.create_clip(track=track, slot=1)
    with pytest.raises(ToolError, match="not found"):
        C.create_clip(track=track, slot=1, file_path="/nonexistent/sound.wav")
    with pytest.raises(ToolError, match="length applies to MIDI"):
        C.create_clip(track=track, slot=1, file_path=PING, length=4)
    with pytest.raises(ToolError, match="needs a MIDI clip"):
        C.get_notes(track=track, slot=0)

    assert C.set_clip(track=track, slot=0, warping=True)["audio"]["warping"] is True
    info = C.set_clip(track=track, slot=0, pitch_coarse=-3, pitch_fine=12.5, warp_mode="complex", ram_mode=True)
    assert (info["audio"]["pitch_coarse"], info["audio"]["pitch_fine"], info["audio"]["warp_mode"], info["audio"]["ram_mode"]) == (-3, 12.5, "complex", True)
    for db in (-40, -18.5, -6, -0.5, 0, 3, 12, 24):
        assert C.set_clip(track=track, slot=0, gain_db=db)["audio"]["gain_db"] == pytest.approx(db, abs=0.01)
    assert C.set_clip(track=track, slot=0, gain_db=-55)["audio"]["gain_db"] == pytest.approx(-55, abs=0.11)
    assert C.set_clip(track=track, slot=0, gain_db="-inf")["audio"]["gain_db"] == "-inf"
    with pytest.raises(ToolError, match="24"):
        C.set_clip(track=track, slot=0, gain_db=30)
    with pytest.raises(ToolError, match="not available"):
        C.set_clip(track=track, slot=0, warp_mode="rex")
    with pytest.raises(ToolError, match="pitch_coarse"):
        C.set_clip(track=track, slot=0, pitch_coarse=49)
    with pytest.raises(ToolError, match="own set_clip call"):
        C.set_clip(track=track, slot=0, warping=False, loop_end=2)
    looped = C.set_clip(track=track, slot=0, looping=True, loop_start=0, loop_end=2)
    assert looped["loop"] == {"start": 0, "end": 2} and looped["time_unit"] == "beats"

    markers = C.clip_action(track=track, slot=0, action="add_warp_marker", args={"beat_time": 1.0})["clip"]["audio"]["warp_markers"]
    assert 1 in [marker["beat"] for marker in markers]
    markers = C.clip_action(track=track, slot=0, action="move_warp_marker", args={"beat_time": 1.0, "distance": 0.5})["clip"]["audio"]["warp_markers"]
    assert 1.5 in [marker["beat"] for marker in markers]
    markers = C.clip_action(track=track, slot=0, action="remove_warp_marker", args={"beat_time": 1.5})["clip"]["audio"]["warp_markers"]
    assert 1.5 not in [marker["beat"] for marker in markers]
    quantized = C.clip_action(track=track, slot=0, action="quantize", args={"grid": "1/16", "amount": 1.0})
    assert quantized["clip"]["audio"]["warp_markers"]

    arranged = C.create_clip(track=track, at="5.1.1", file_path=POP)
    assert arranged["arrangement_clip"] == 0 and arranged["start"]["beats"] == 16.0 and arranged["name"] == "Pop"


# ---------------------------------------------------------------------------
# Clip actions on MIDI clips and conversions
# ---------------------------------------------------------------------------


def test_midi_clip_actions(live, scratch, song_state):
    set_song(live, swing_amount=0.0)
    track = scratch.track("actions")
    C.create_clip(track=track, slot=0, length=8)
    C.write_notes(track=track, slot=0, notes=[{"pitch": 60 + index, "start": index, "duration": 0.5} for index in range(8)])
    C.set_clip(track=track, slot=0, loop_start=2, loop_end=6)
    cropped = C.clip_action(track=track, slot=0, action="crop")["clip"]
    assert cropped["loop"] == {"start": 0, "end": 4} and cropped["note_count"] == 4
    assert pitches(C.get_notes(track=track, slot=0)) == [62, 63, 64, 65]

    doubled = C.clip_action(track=track, slot=0, action="duplicate_loop")["clip"]
    assert doubled["loop"] == {"start": 0, "end": 8} and doubled["note_count"] == 8

    region = C.clip_action(track=track, slot=0, action="duplicate_region", args={"start": 0, "length": 1, "destination": 0.5, "transpose": 12})
    assert region["clip"]["note_count"] == 9 and 74 in pitches(C.get_notes(track=track, slot=0, start=0.5, end=0.75))

    C.edit_notes(track=track, slot=0, edits=[{"note_id": C.get_notes(track=track, slot=0, pitches=[63])["notes"][0]["note_id"], "start": 1.1}])
    C.clip_action(track=track, slot=0, action="quantize", args={"grid": "1/4", "pitch": 63})
    assert starts(C.get_notes(track=track, slot=0, pitches=[63])) == [1, 5]
    C.clip_action(track=track, slot=0, action="quantize", args={"grid": "1/8", "amount": 1.0})
    assert all(note["start"] * 2 == int(note["start"] * 2) for note in C.get_notes(track=track, slot=0)["notes"])

    with pytest.raises(ToolError, match="action must be one of"):
        C.clip_action(track=track, slot=0, action="explode")
    with pytest.raises(ToolError, match="takes args"):
        C.clip_action(track=track, slot=0, action="crop", args={"grid": "1/16"})
    with pytest.raises(ToolError, match="needs args.length"):
        C.clip_action(track=track, slot=0, action="duplicate_region", args={"start": 0, "destination": 4})
    with pytest.raises(ToolError, match="audio clips"):
        C.clip_action(track=track, slot=0, action="add_warp_marker", args={"beat_time": 1})
    with pytest.raises(ToolError, match="audio clips"):
        C.clip_action(track=track, slot=0, action="audio_to_midi")


def test_audio_conversions_create_named_tracks(live, scratch):
    track = scratch.track("convert", "audio")
    C.create_clip(track=track, slot=0, file_path=PING)
    C.set_clip(track=track, slot=0, warping=True)
    melody = C.clip_action(track=track, slot=0, action="audio_to_midi", args={"type": "melody", "name": scratch.name("melody")})
    assert melody["new_tracks"][0]["name"] == scratch.name("melody") and melody["new_tracks"][0]["kind"] == "midi", melody
    drums = C.clip_action(track=track, slot=0, action="drum_rack_from_audio", args={"name": scratch.name("drum rack")})
    simpler = C.clip_action(track=track, slot=0, action="simpler_track_from_audio", args={"name": scratch.name("simpler")})
    names = track_names(live)
    for result in (melody, drums, simpler):
        assert result["new_tracks"] and result["new_tracks"][0]["name"] in names
    with pytest.raises(ToolError, match="type must be one of"):
        C.clip_action(track=track, slot=0, action="audio_to_midi", args={"type": "speech"})
    with pytest.raises(AbletonError, match="not found"):
        live.send_command("clips_conversion_status", {"job": 987654})


# ---------------------------------------------------------------------------
# Launching
# ---------------------------------------------------------------------------


def test_fire_and_stop(live, scratch, song_state):
    set_song(live, clip_trigger_quantization=0)
    track = scratch.track("launch")
    C.create_clip(track=track, slot=0, length=4, name="Loop")
    fired = C.fire_clip(track=track, slot=0)
    assert fired["fired"]["name"] == "Loop" and fired["launch_quantization"] == "none"
    state = wait_for(lambda: C.get_clip(track=track, slot=0)["state"], lambda value: value == "playing")
    assert state == "playing"
    stopped = C.stop_clip(track=track, quantized=False)
    assert stopped["stopped"]["name"] == track and stopped["quantized"] is False
    assert wait_for(lambda: C.get_clip(track=track, slot=0)["state"], lambda value: value == "stopped") == "stopped"
    with pytest.raises(ToolError, match="empty"):
        C.fire_clip(track=track, slot=1)
    with pytest.raises(ToolError, match="master track"):
        C.stop_clip(track="master")


def test_music_theory_feeds_write_notes(scratch):
    track = scratch.track("theory")
    C.create_clip(track=track, slot=0, length="4 bars")
    progression = music_theory("progression", key="A minor", progression="i-VI-III-VII", octave=2, voice_leading=True)
    written = C.write_notes(track=track, slot=0, notes=progression["notes"])
    assert written["added"] == sum(len(note["pitches"]) for note in progression["notes"]) and "warnings" not in written
    scale = music_theory("scale", key="A", scale="minor pentatonic", octave=2)
    C.create_clip(track=track, slot=1, length=4)
    C.write_notes(track=track, slot=1, notes=[{"pitch": pitch, "start": index * 0.5, "duration": 0.5} for index, pitch in enumerate(scale["pitches"])])
    assert pitches(C.get_notes(track=track, slot=1)) == scale["pitches"]
