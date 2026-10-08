"""Live tests for the listening loop's snapshot and restore commands (handlers/listening.py), run against the
running Live.

Every track these tests create is a "[test:listening] ..." scratch track, removed afterwards, and every snapshot
they restore holds only scratch tracks: the open set's own tracks are never read or written here.
"""
import copy

import pytest

from MCP_Server.connection import AbletonError
from MCP_Server.tools.clips import create_clip, delete_notes, edit_notes, get_notes, set_clip, write_notes
from MCP_Server.tools.devices import add_device, delete_device, set_device_parameters
from MCP_Server.tools.status import redo, undo
from MCP_Server.tools.tracks import set_mixer

NOTES = [
    {"pitch": 57, "start": 0, "duration": 1, "velocity": 100},
    {"pitch": 60, "start": 1, "duration": 0.5, "velocity": 90, "probability": 0.5},
    {"pitch": 64, "start": 2, "duration": 1, "velocity": 80, "velocity_deviation": 20, "release_velocity": 30},
    {"pitch": 67, "start": 3, "duration": 1, "velocity": 70, "mute": True},
    {"pitch": 69, "start": 13 / 3.0, "duration": 1 / 3.0, "velocity": 99},
]


def snapshot(live, tracks, **params):
    return live.send_command("listening_snapshot", dict(params, tracks=tracks))


def restore(live, snap, **params):
    return live.send_command("listening_restore", dict(params, snapshot=snap))


def entry(snap, name):
    return next(track for track in snap["tracks"] if track["name"] == name)


def without_ids(track):
    out = copy.deepcopy(track)
    for clip in out["clips"] + out.get("arrangement_clips", []):
        for note in clip.get("notes", []):
            note.pop("id")
    return out


def parameter(track, device_name, name):
    device = next(item for item in track["devices"] if item["name"] == device_name)
    return next(item for item in device["parameters"] if item["name"] == name)


def test_snapshot_restore_round_trip_and_undo(live, scratch):
    name = scratch.track("synth", "midi")
    add_device(name, "Operator")
    add_device(name, "Auto Filter")
    add_device(name, "Audio Effect Rack")
    add_device(name, "Saturator", chain="Audio Effect Rack/new")
    create_clip(name, slot=0, length=8, name="A", notes=NOTES)
    set_device_parameters(name, "Operator", {"Algorithm": 3, "Transpose": 5, "Tone": 0.4, "Glide Time": 0.25})
    set_device_parameters(name, "Auto Filter", {"Frequency": 0.6, "Resonance": 0.5, "Filter Type": 2})
    set_device_parameters(name, "Audio Effect Rack/0/Saturator", {"Drive": 0.7, "Type": 3})
    set_mixer(name, volume_db=-7.5, pan=-0.3, sends={"A": -12})

    before = entry(snapshot(live, [name], parameters=True), name)
    assert before["kind"] == "midi" and before["mixer"] == {"volume_db": -7.5, "pan": -0.3, "sends": {"A": -12, "B": None}}
    assert [(item["path"], item["name"], item["class_name"], item["type"]) for item in before["devices"]] == [
        ("0", "Operator", "Operator", "instrument"), ("1", "Auto Filter", "AutoFilter2", "audio_effect"),
        ("2", "Audio Effect Rack", "AudioEffectGroupDevice", "audio_effect"), ("2/0/0", "Saturator", "Saturator", "audio_effect")]
    assert parameter(before, "Operator", "Algorithm")["value"] == 3 and parameter(before, "Saturator", "Drive")["value"] == pytest.approx(0.7)
    clip = before["clips"][0]
    assert (clip["slot"], clip["name"], clip["is_midi"], clip["length"], clip["warping"]) == (0, "A", True, 8, None)
    notes = clip["notes"]
    assert [(item["pitch"], item["probability"], item["mute"]) for item in notes] == [
        (57, 1, False), (60, 0.5, False), (64, 1, False), (67, 1, True), (69, 1, False)]
    assert (notes[2]["velocity_deviation"], notes[2]["release_velocity"], notes[4]["start"]) == (20, 30, pytest.approx(13 / 3.0))

    # Change notes, parameters (one inside the rack, one switching a device off) and the mixer.
    ids = [item["id"] for item in notes]
    edit_notes(name, [{"note_id": ids[0], "pitch": 59}, {"note_id": ids[1], "probability": 1.0}], slot=0)
    delete_notes(name, slot=0, note_ids=[ids[2]])
    write_notes(name, [{"pitch": 72, "start": 5, "duration": 1}], slot=0)
    set_device_parameters(name, "Operator", {"Algorithm": 7, "Transpose": -12, "Tone": 0.9})
    set_device_parameters(name, "Auto Filter", {"Device On": 0, "Frequency": 0.2})
    set_device_parameters(name, "Audio Effect Rack/0/Saturator", {"Drive": 0.1})
    set_mixer(name, volume_db=-20, pan=0.4, sends={"A": -3})
    changed = entry(snapshot(live, [name], parameters=True), name)
    assert next(item for item in changed["devices"] if item["name"] == "Auto Filter")["active"] is False

    plan = restore(live, {"tracks": [before]}, dry_run=True)
    counts = (plan["tracks"], plan["clips"], plan["notes"], plan["parameters"], plan["mixer"])
    assert plan["dry_run"] is True and counts == (1, 1, 4, 6, 3)
    assert {"track": name, "slot": 0, "clip": "A", "notes": {"added": 1, "removed": 1, "modified": 2}} in plan["changes"]
    assert {"track": name, "device": "2/0/0", "name": "Saturator", "parameters": ["Drive"]} in plan["changes"]
    assert plan["skipped"] == [] and plan["added_devices"] == [] and plan["removed_devices"] == []
    assert entry(snapshot(live, [name], parameters=True), name) == changed  # the dry run wrote nothing

    done = restore(live, {"tracks": [before]})
    assert done["dry_run"] is False and (done["tracks"], done["clips"], done["notes"], done["parameters"], done["mixer"]) == counts
    after = entry(snapshot(live, [name], parameters=True), name)
    assert without_ids(after) == without_ids(before)
    kept = [item["id"] for item in after["clips"][0]["notes"]]
    assert kept[:2] == ids[:2] and ids[2] not in kept  # edited notes kept their ids; the deleted one came back anew
    assert restore(live, {"tracks": [before]}, dry_run=True)["changes"] == []

    # The restore is one undo step: undo brings back the changed state.
    undo()
    reverted = entry(snapshot(live, [name], parameters=True), name)
    if without_ids(reverted) == without_ids(after):
        redo()  # undo reverted something else (another client acted in between): put it back
        pytest.fail("undo did not revert the restore")
    assert without_ids(reverted) == without_ids(changed)


def test_restore_reports_device_and_clip_changes(live, scratch):
    name = scratch.track("structure", "midi")
    add_device(name, "Operator")
    add_device(name, "Auto Filter")
    create_clip(name, slot=0, length=4, name="A", notes=NOTES[:2])
    set_device_parameters(name, "Operator", {"Tone": 0.4})
    before = entry(snapshot(live, [name], parameters=True), name)

    delete_device(name, "Auto Filter")
    add_device(name, "Utility")
    add_device(name, "EQ Eight")
    set_device_parameters(name, "Operator", {"Tone": 0.8})
    set_clip(name, slot=0, name="A2")
    out = restore(live, {"tracks": [before, {"name": scratch.name("ghost")}]})
    assert out["parameters"] == 1 and out["notes"] == 0
    assert out["removed_devices"] == [{"track": name, "path": "1", "name": "Auto Filter", "class_name": "AutoFilter2"}]
    assert out["added_devices"] == [{"track": name, "path": "1", "name": "Utility", "class_name": "StereoGain"},
                                    {"track": name, "path": "2", "name": "EQ Eight", "class_name": "Eq8"}]
    assert {"track": name, "slot": 0, "clip": "A", "reason": "the clip in this slot is named 'A2'"} in out["skipped"]
    assert {"track": scratch.name("ghost"), "reason": "track not found"} in out["skipped"]
    assert parameter(entry(snapshot(live, [name], parameters=True), name), "Operator", "Tone")["value"] == pytest.approx(0.4)


def test_drum_paths_arrangement_clips_filters_and_errors(live, scratch):
    name = scratch.track("drums", "midi")
    add_device(name, "Drum Rack")
    add_device(name, "Operator", chain="Drum Rack/C1")
    add_device(name, "Simpler", chain="Drum Rack/D1")
    create_clip(name, slot=1, length=4, name="pad", notes=NOTES[:1])
    create_clip(name, at=0, length=4, name="arr", notes=NOTES[:3])
    snap = snapshot(live, [name], scenes=[1], arrangement=True)
    track = entry(snap, name)
    assert sorted((item["path"], item["class_name"]) for item in track["devices"]) == [
        ("0", "DrumGroupDevice"), ("0/0/0", "Operator"), ("0/1/0", "OriginalSimpler")]
    assert len(snap["scenes"]) == 1 and snap["scenes"][0]["index"] == 1
    assert [(item["slot"], item["name"]) for item in track["clips"]] == [(1, "pad")]
    arranged = track["arrangement_clips"]
    assert [(item["index"], item["name"], item["start"], item["end"], len(item["notes"])) for item in arranged] == [(0, "arr", 0, 4, 3)]
    assert snap["returns"] == [] and snap["master"] is None
    assert set(snap["song"]) == {"tempo", "time_signature", "set_name", "set_path", "live_version", "root_note", "scale_name"}

    first = get_notes(name, arrangement_clip=0)["notes"][0]
    edit_notes(name, [{"note_id": first["note_id"], "pitch": 40, "velocity": 50}], arrangement_clip=0)
    out = restore(live, snap)
    assert (out["clips"], out["notes"]) == (1, 1)
    assert {"track": name, "arrangement_clip": 0, "clip": "arr", "notes": {"added": 0, "removed": 0, "modified": 1}} in out["changes"]
    assert without_ids(entry(snapshot(live, [name], scenes=[1], arrangement=True), name)) == without_ids(track)

    with pytest.raises(AbletonError) as error:
        snapshot(live, [scratch.name("nope")])
    assert error.value.code == "not_found"
    with pytest.raises(AbletonError) as error:
        restore(live, {"tracks": []})
    assert error.value.code == "invalid_argument"
    broken = copy.deepcopy(snap)
    entry(broken, name)["arrangement_clips"][0]["notes"][0]["velocity"] = 0
    with pytest.raises(AbletonError) as error:
        restore(live, broken)
    assert error.value.code == "invalid_argument" and "velocity" in error.value.message
