"""Live tests for WS-F arrangement tools: get_arrangement, arrange_from_scenes, clear_arrangement and the
internal arrangement_locator command. Scratch tracks and scenes only; material is placed from beat 800
("201.1.1"), far from anything else in the shared set, and every locator a test creates is removed.
"""
import math
import struct
import time
import wave

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server.connection import AbletonError
from MCP_Server.tools.arrangement import arrange_from_scenes, clear_arrangement, get_arrangement
from MCP_Server.tools.automation import get_automation, write_automation
from tests.live.conftest import lom_value, scene_names, track_names

BASE = 800.0
PREFIX = "[test:arrangement]"


# ---------------------------------------------------------------------------
# Helpers (setup goes through the generic LOM commands)
# ---------------------------------------------------------------------------


def tpath(live, name):
    return "live_set tracks {0}".format(track_names(live).index(name))


def scene_index(live, name):
    return scene_names(live).index(name)


def under(live, track, rest, command, **params):
    """Send a LOM command for a path under the named track (and scene). Other builders add and remove
    tracks and scenes meanwhile, so the path is resolved just before sending and again if it went stale."""
    for attempt in range(3):
        suffix = rest(live) if callable(rest) else rest
        path = " ".join(part for part in (tpath(live, track), suffix) if part)
        try:
            return live.send_command(command, dict(params, path=path))
        except AbletonError as error:
            if attempt == 2 or "out of range" not in str(error):
                raise


def slot_of(scene, tail=""):
    return lambda live: ("clip_slots {0} {1}".format(scene_index(live, scene), tail)).strip()


def lom_set(live, path, prop, value):
    live.send_command("lom_set", {"path": path, "property": prop, "value": value})


def lom_call(live, path, method, *args):
    return live.send_command("lom_call", {"path": path, "method": method, "args": list(args)})


def set_clip(live, track, scene, **props):
    for prop, value in props.items():
        under(live, track, slot_of(scene, "clip"), "lom_set", property=prop, value=value)


def session_clip(live, track, scene, length=4.0, **props):
    under(live, track, slot_of(scene), "lom_call", method="create_clip", args=[float(length)])
    set_clip(live, track, scene, **props)


def write_wav(path, seconds=4.0, rate=44100):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / rate))) for i in range(int(rate * seconds))))
    return str(path)


def audio_clip(live, track, scene, wav):
    """A warped audio clip looping 0..4 beats in the track's slot for `scene`."""
    under(live, track, slot_of(scene), "lom_call", method="create_audio_clip", args=[wav])
    set_clip(live, track, scene, warping=True)
    time.sleep(0.2)  # Live applies warping on a later tick
    set_clip(live, track, scene, looping=True, loop_start=0.0, loop_end=4.0)


def clips(track, **kwargs):
    return get_arrangement(tracks=[track], **kwargs)["tracks"][0]["clips"]


def spans(track):
    return [(clip["start"]["beats"], clip["end"]["beats"]) for clip in clips(track)]


def all_locators():
    return get_arrangement(tracks=[], limit=0)["locators"]


def remove_locator(live, at):
    for _ in range(8):
        if live.send_command("arrangement_locator", {"time": at, "remove": True})["status"] == "done":
            return
        time.sleep(0.12)
    raise AssertionError("could not remove the locator at beat {0}".format(at))


def arrangement_clip_props(live, track, index, *props):
    values = under(live, track, "arrangement_clips {0}".format(index), "lom_get", properties=list(props))["values"]
    return dict((name, entry.get("value")) for name, entry in values.items())


@pytest.fixture
def locators(live):
    """Times of locators a test creates. Removed afterwards (with any '[test:arrangement]' locator)."""
    before = [(item["time"]["beats"], item["name"]) for item in all_locators()]
    assert not any(BASE <= at < BASE + 400 for at, _ in before), "A locator already sits in the WS-F test range"
    created = []
    yield created
    try:
        live.send_command("lom_call", {"path": "live_set", "method": "stop_playing", "args": []})
    except AbletonError:
        pass
    for item in all_locators():
        at, name = item["time"]["beats"], item["name"]
        if name.startswith(PREFIX) or (at in created and (at, name) not in before):
            remove_locator(live, at)


# ---------------------------------------------------------------------------
# arrange_from_scenes
# ---------------------------------------------------------------------------


def test_sections_of_any_length_locators_envelopes_and_playhead(live, scratch, song_state, locators, tmp_path):
    midi = scratch.track("midi")
    audio = scratch.track("audio", kind="audio")
    verse, fill = scratch.scene("verse"), scratch.scene("fill")
    session_clip(live, midi, verse, 4.0)
    write_automation(midi, "volume", slot=scene_index(live, verse), shape={"type": "ramp", "from": -24, "to": 0})
    session_clip(live, midi, fill, 4.0, loop_end=6.0, loop_start=2.0)  # pre-roll: plays 0..6 once, then loops 2..6
    audio_clip(live, audio, verse, write_wav(tmp_path / "tone.wav"))
    lom_set(live, "live_set", "current_song_time", 3.0)
    time.sleep(0.15)

    started = time.time()
    result = arrange_from_scenes(
        [{"scene": verse, "bars": 2, "name": PREFIX + " Verse"}, {"scene": fill, "length": 6, "name": PREFIX + " Fill"}],
        start="201.1.1", tracks=[midi, audio])
    elapsed = time.time() - started
    locators.extend([BASE, BASE + 8])

    assert elapsed < 10
    assert [(s["start"]["beats"], s["end"]["beats"]) for s in result["sections"]] == [(BASE, BASE + 8), (BASE + 8, BASE + 14)]
    assert result["sections"][0]["tracks"] == [midi, audio] and result["sections"][1]["tracks"] == [midi]
    assert result["sections"][0]["automated"] == [midi] and "automated" not in result["sections"][1]
    assert result["sections"][1]["bars"] == 1.5 and result["clips_placed"] == 3
    assert [(item["name"], item["time"]["beats"]) for item in result["locators"]] == [(PREFIX + " Verse", BASE), (PREFIX + " Fill", BASE + 8)]
    assert "locator_errors" not in result and "warnings" not in result

    # One looping clip per track and section, exactly as long as the section (1.5 bars is not a
    # multiple of the 1-bar clip; the pre-roll clip keeps its loop region).
    midi_clips = clips(midi)
    assert [(c["start"]["beats"], c["end"]["beats"], c["looping"]) for c in midi_clips] == [(BASE, BASE + 8, True), (BASE + 8, BASE + 14, True)]
    assert midi_clips[0].get("envelopes") is True and "envelopes" not in midi_clips[1]
    assert arrangement_clip_props(live, midi, 1, "loop_start", "loop_end", "start_marker") == {"loop_start": 2.0, "loop_end": 6.0, "start_marker": 0.0}
    assert [(c["start"]["beats"], c["end"]["beats"], c["type"]) for c in clips(audio)] == [(BASE, BASE + 8, "audio")]
    assert arrangement_clip_props(live, audio, 0, "loop_start", "loop_end", "looping") == {"loop_start": 0.0, "loop_end": 4.0, "looping": True}

    # The Session envelope travelled into the arrangement and is readable there.
    automation = get_automation(midi, arrangement_clip=0, parameter="volume", samples=3)
    assert automation["has_envelopes"] and automation["automated"] == [{"parameter": "volume"}]
    assert automation["envelope"]["samples"][0]["display"].startswith("-24")

    names = [item["name"] for item in all_locators()]
    assert PREFIX + " Verse" in names and PREFIX + " Fill" in names
    time.sleep(0.15)
    assert lom_value(live, "live_set", "current_song_time") == 3.0  # pastes and locators moved it; it is back


def test_overwrite_without_clear_and_exact_clear(live, scratch, song_state, tmp_path):
    midi = scratch.track("midi")
    audio = scratch.track("audio", kind="audio")
    long_scene, short = scratch.scene("long"), scratch.scene("short")
    session_clip(live, midi, long_scene, 4.0)
    audio_clip(live, audio, long_scene, write_wav(tmp_path / "tone.wav"))
    session_clip(live, midi, short, 2.0)
    arrange_from_scenes([{"scene": long_scene, "bars": 4}], start=BASE, tracks=[midi, audio], locators=False)
    assert spans(midi) == [(BASE, BASE + 16)] and spans(audio) == [(BASE, BASE + 16)]

    # clear=False: a track with a clip overwrites exactly its section; a track with an empty slot keeps its material.
    result = arrange_from_scenes([{"scene": short, "length": 2}], start=BASE + 4, tracks=[midi, audio], locators=False)
    assert "cleared" not in result and result["sections"][0]["tracks"] == [midi]
    assert spans(midi) == [(BASE, BASE + 4), (BASE + 4, BASE + 6), (BASE + 6, BASE + 16)]
    assert spans(audio) == [(BASE, BASE + 16)]

    # clear=True: the whole range is emptied on every affected track first, cutting clips at its edges.
    result = arrange_from_scenes([{"scene": short, "length": 2}], start=BASE + 9, clear=True, tracks=[midi, audio], locators=False)
    assert result["cleared"] == {"deleted": 0, "trimmed": 2}
    assert spans(audio) == [(BASE, BASE + 9), (BASE + 11, BASE + 16)]
    assert spans(midi) == [(BASE, BASE + 4), (BASE + 4, BASE + 6), (BASE + 6, BASE + 9), (BASE + 9, BASE + 11), (BASE + 11, BASE + 16)]
    # The right-hand part keeps its place in the loop: 11 beats in, 3 beats into the 4-beat loop.
    assert arrangement_clip_props(live, audio, 1, "start_marker", "looping") == {"start_marker": 3.0, "looping": True}


def test_one_shot_clips_play_once_and_are_shortened(live, scratch, song_state):
    midi = scratch.track("midi")
    scene = scratch.scene("oneshot")
    session_clip(live, midi, scene, 4.0, looping=False)
    result = arrange_from_scenes([{"scene": scene, "bars": 2}, {"scene": scene, "length": 3}], start=BASE, tracks=[midi], locators=False)
    assert spans(midi) == [(BASE, BASE + 4), (BASE + 8, BASE + 11)]
    assert all(not item["looping"] for item in clips(midi))
    assert any("plays once" in warning for warning in result["warnings"])


def test_unwarped_audio_is_cut_to_the_section(live, scratch, song_state, tmp_path):
    audio = scratch.track("audio", kind="audio")
    scene = scratch.scene("raw")
    under(live, audio, slot_of(scene), "lom_call", method="create_audio_clip", args=[write_wav(tmp_path / "raw.wav", seconds=3.0)])
    set_clip(live, audio, scene, looping=False, warping=False)
    time.sleep(0.2)
    assert under(live, audio, slot_of(scene, "clip"), "lom_get", properties=["warping"])["values"]["warping"]["value"] is False
    # Live applies a new length of unwarped audio one tick late, so these take an extra call each.
    result = arrange_from_scenes([{"scene": scene, "length": 2}], start=BASE, tracks=[audio], locators=False)
    assert result["undo_steps"] == 2
    assert [(c["start"]["beats"], c["end"]["beats"], c["looping"]) for c in clips(audio)] == [(BASE, BASE + 2, False)]
    arrange_from_scenes([{"scene": scene, "length": 2.5}], start=BASE + 8, tracks=[audio], locators=False)
    cleared = clear_arrangement(tracks=[audio], start=BASE + 9, end=BASE + 10)
    assert cleared["trimmed"] == 1 and cleared["undo_steps"] == 2
    assert spans(audio) == [(BASE, BASE + 2), (BASE + 8, BASE + 9), (BASE + 10, BASE + 10.5)]


def test_locators_need_live_stopped(live, scratch, song_state, locators):
    """The raw locator command refuses while playing; arrange_from_scenes stops the transport first."""
    midi = scratch.track("midi")
    scene = scratch.scene("s")
    session_clip(live, midi, scene, 4.0)
    arrange_from_scenes([{"scene": scene, "bars": 2}], start=BASE, tracks=[midi], locators=False)  # song length reaches BASE
    lom_set(live, "live_set", "metronome", False)
    lom_set(live, "live_set", "start_time", BASE)
    lom_call(live, "live_set", "start_playing")
    try:
        time.sleep(0.3)
        with pytest.raises(AbletonError) as error:
            live.send_command("arrangement_locator", {"time": BASE})
        assert error.value.code == "busy"
        assert spans(midi) == [(BASE, BASE + 8)]  # the refused call changed nothing
        locators.append(BASE)
        result = arrange_from_scenes([{"scene": scene, "bars": 2, "name": PREFIX + " stopped"}], start=BASE, tracks=[midi])
        assert result.get("stopped_transport") is True
        playing = live.send_command("lom_get", {"path": "live_set", "properties": ["is_playing"]})["values"]["is_playing"]["value"]
        assert playing is False
    finally:
        lom_call(live, "live_set", "stop_playing")


def test_many_sections_stay_quick(live, scratch, song_state):
    tracks = [scratch.track("t{0}".format(k)) for k in range(3)]
    scenes = [scratch.scene("s{0}".format(k)) for k in range(2)]
    for track in tracks:
        for scene in scenes:
            session_clip(live, track, scene, 4.0)
    sections = [{"scene": scenes[k % 2], "length": 6 + k % 3} for k in range(8)]
    started = time.time()
    result = arrange_from_scenes(sections, start=BASE, tracks=tracks, locators=False)
    elapsed = time.time() - started
    assert result["clips_placed"] == 24 and elapsed < 5, elapsed
    expected, cursor = [], BASE
    for section in sections:
        expected.append((cursor, cursor + section["length"]))
        cursor += section["length"]
    assert spans(tracks[1]) == expected


def test_undo_steps_revert_clips_and_locators_exactly(live, scratch, song_state, locators):
    midi = scratch.track("midi")
    scene = scratch.scene("s")
    session_clip(live, midi, scene, 4.0)
    result = arrange_from_scenes([{"scene": scene, "bars": 1, "name": PREFIX + " U1"}, {"scene": scene, "bars": 1, "name": PREFIX + " U2"}],
                                 start=BASE, tracks=[midi])
    locators.extend([BASE, BASE + 4])
    assert result["undo_steps"] == 3  # one call for the clips, one per locator
    for _ in range(result["undo_steps"]):
        lom_call(live, "live_set", "undo")
    assert spans(midi) == []
    assert all(not item["name"].startswith(PREFIX) for item in all_locators())
    has_clip = under(live, midi, slot_of(scene), "lom_get", properties=["has_clip"])["values"]["has_clip"]["value"]
    assert has_clip is True  # nothing before the arrangement was undone


def test_resume_continues_from_a_work_unit(live, scratch, song_state):
    first, second = scratch.track("one"), scratch.track("two")
    scene = scratch.scene("s")
    for track in (first, second):
        session_clip(live, track, scene, 4.0)
    sections = [{"scene": scene, "bars": 1}, {"scene": scene, "bars": 1}]
    # units: (section 0, one), (section 0, two), (section 1, one), (section 1, two); start at unit 2
    params = {"sections": sections, "start": BASE, "tracks": [first, second], "locators": False}
    result = live.send_command("arrange_from_scenes", dict(params, resume=2))
    assert "resume" not in result and [(item["section"], item["track"]) for item in result["placed"]] == [(1, first), (1, second)]
    assert spans(first) == [(BASE + 4, BASE + 8)] and spans(second) == [(BASE + 4, BASE + 8)]
    with pytest.raises(AbletonError) as error:
        live.send_command("arrange_from_scenes", dict(params, resume=5))
    assert error.value.code == "invalid_argument" and "work-unit index 0..4" in str(error.value)


def test_existing_locator_is_renamed_not_toggled(live, scratch, song_state, locators):
    midi = scratch.track("midi")
    scene = scratch.scene("s")
    session_clip(live, midi, scene, 4.0)
    arrange_from_scenes([{"scene": scene, "bars": 1, "name": PREFIX + " first"}], start=BASE, tracks=[midi])
    locators.append(BASE)
    result = arrange_from_scenes([{"scene": scene, "bars": 1, "name": PREFIX + " second"}], start=BASE, tracks=[midi])
    locator = result["locators"][0]
    assert locator["existing"] is True and locator["renamed_from"] == PREFIX + " first" and locator["name"] == PREFIX + " second"
    assert [item["name"] for item in all_locators() if item["time"]["beats"] == BASE] == [PREFIX + " second"]


def test_arrangement_locator_steps(live, scratch, song_state, locators):
    midi = scratch.track("midi")
    scene = scratch.scene("s")
    session_clip(live, midi, scene, 4.0)
    arrange_from_scenes([{"scene": scene, "bars": 4}], start=BASE, tracks=[midi], locators=False)
    lom_set(live, "live_set", "current_song_time", BASE)
    time.sleep(0.15)
    at = BASE + 4
    first = live.send_command("arrangement_locator", {"time": at, "name": PREFIX + " step"})
    assert first == {"status": "pending", "time": at}  # the playhead had to move first
    locators.append(at)
    time.sleep(0.15)
    second = live.send_command("arrangement_locator", {"time": at, "name": PREFIX + " step", "then": BASE})
    assert second["status"] == "done" and second["created"] is True
    assert live.send_command("arrangement_locator", {"time": BASE + 2, "remove": True}) == {"status": "done", "removed": False}
    remove_locator(live, at)
    assert all(item["time"]["beats"] != at for item in all_locators())
    with pytest.raises(AbletonError) as error:
        live.send_command("arrangement_locator", {"time": 1500000.0})
    assert error.value.code == "invalid_argument" and "song length" in str(error.value)


BAD_SECTIONS = [
    ([], "non-empty list"),
    ([{"scene": "[test:arrangement] nope", "bars": 1}], "not found"),
    ([{"scene": 0}], "exactly one of 'bars'"),
    ([{"scene": 0, "bars": 1, "bar": 2}], "unknown keys"),
    ([{"bars": 1}], "needs a 'scene'"),
    ([{"scene": 0, "bars": 1}, {"scene": 0, "length": "two bars"}], "sections[1].length"),
]


def test_arrange_rejects_bad_sections_before_changing_anything(live, scratch, song_state):
    midi = scratch.track("midi")
    for sections, message in BAD_SECTIONS:
        with pytest.raises(ToolError) as error:
            arrange_from_scenes(sections, start=BASE, tracks=[midi], locators=False)
        assert message in str(error.value), (sections, str(error.value))
    assert spans(midi) == []


def test_arrange_rejects_tracks_without_arrangement(live, scratch, song_state):
    scene = scratch.scene("s")
    with pytest.raises(ToolError) as error:
        arrange_from_scenes([{"scene": scene, "bars": 1}], start=BASE, tracks=["return:A"], locators=False)
    assert "has no arrangement clips" in str(error.value)
    with pytest.raises(ToolError):
        arrange_from_scenes([{"scene": scene, "bars": 1}], start=-4, tracks=[], locators=False)


# ---------------------------------------------------------------------------
# clear_arrangement and get_arrangement
# ---------------------------------------------------------------------------


def _three_clips(midi, scene):
    clear_arrangement(tracks=[midi])
    for offset in (0, 8, 16):
        arrange_from_scenes([{"scene": scene, "bars": 1}], start=BASE + offset, tracks=[midi], locators=False)
    assert spans(midi) == [(BASE, BASE + 4), (BASE + 8, BASE + 12), (BASE + 16, BASE + 20)]


def test_clear_arrangement_modes(live, scratch, song_state):
    midi = scratch.track("midi")
    scene = scratch.scene("s")
    session_clip(live, midi, scene, 4.0)

    _three_clips(midi, scene)
    result = clear_arrangement(tracks=[midi], start=BASE + 6, end=BASE + 14, mode="inside")
    assert result["deleted"] == 1 and result["trimmed"] == 0 and result["tracks"][0]["remaining"] == 2
    assert spans(midi) == [(BASE, BASE + 4), (BASE + 16, BASE + 20)]

    _three_clips(midi, scene)
    result = clear_arrangement(tracks=[midi], start=BASE + 2, end=BASE + 10, mode="overlapping")
    assert result["deleted"] == 2
    assert spans(midi) == [(BASE + 16, BASE + 20)]

    _three_clips(midi, scene)
    result = clear_arrangement(tracks=[midi], start="201.3.1", end="205.3.1")  # trim: 802 .. 818
    assert result["mode"] == "trim" and result["deleted"] == 1 and result["trimmed"] == 2
    assert spans(midi) == [(BASE, BASE + 2), (BASE + 18, BASE + 20)]

    result = clear_arrangement(tracks=[midi])
    assert result["deleted"] == 2 and spans(midi) == []


def test_clear_arrangement_errors(live, scratch, song_state):
    midi = scratch.track("midi")
    with pytest.raises(ToolError) as error:
        clear_arrangement(tracks=[midi], mode="everything")
    assert "mode must be one of" in str(error.value)
    with pytest.raises(ToolError):
        clear_arrangement(tracks=[midi], start=BASE + 8, end=BASE)
    with pytest.raises(ToolError) as error:
        clear_arrangement(tracks=["master"])
    assert "has no arrangement clips" in str(error.value)


def test_get_arrangement_fields_ranges_and_limits(live, scratch, song_state):
    midi = scratch.track("midi")
    scene = scratch.scene("s")
    session_clip(live, midi, scene, 4.0, name="riff")
    for offset in range(0, 40, 8):
        arrange_from_scenes([{"scene": scene, "bars": 1}], start=BASE + offset, tracks=[midi], locators=False)

    full = get_arrangement(tracks=[midi])
    entry = full["tracks"][0]
    assert entry["name"] == midi and entry["kind"] == "midi" and len(entry["clips"]) == 5 and "clip_count" not in entry
    first = entry["clips"][0]
    assert first["index"] == 0 and first["name"] == "riff" and first["type"] == "midi" and first["looping"] is True
    assert first["start"] == {"beats": BASE, "bar": "201.1.1"} and first["end"]["bar"] == "202.1.1" and first["length"] == 4.0
    assert "color_index" in first and "color" in first
    assert set(full) >= {"song", "loop", "locators", "tracks"} and full["song"]["length"]["beats"] >= BASE + 36
    assert full["loop"]["end"]["beats"] > full["loop"]["start"]["beats"]

    ranged = get_arrangement(tracks=[midi], start=BASE + 8, end="205.2.1")  # 808 .. 817: clips 1 and 2
    assert [c["index"] for c in ranged["tracks"][0]["clips"]] == [1, 2] and ranged["tracks"][0]["clip_count"] == 5
    assert ranged["range"]["end"]["beats"] == BASE + 17
    edge = get_arrangement(tracks=[midi], start=BASE + 4, end=BASE + 8)  # half-open: touching clips excluded
    assert edge["tracks"][0]["clips"] == []

    limited = get_arrangement(tracks=[midi], limit=2)
    assert len(limited["tracks"][0]["clips"]) == 2 and limited["truncated"]["clips_omitted"] == 3

    with pytest.raises(ToolError):
        get_arrangement(tracks=["return:A"])
    with pytest.raises(ToolError):
        get_arrangement(start=BASE + 8, end=BASE)
