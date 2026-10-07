"""Live tests for WS-B: tracks, mixer, routing, meters and buses (run against the running Live).

Every track these tests create is named "[test:tracks] ..." and removed afterwards. Audio tests stay
silent: tone tracks route their output to "Sends Only", and Live's track meters read before routing.
"""
import re
import time
import wave

import numpy as np
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server.tools.tracks import (create_bus, create_track, delete_track, duplicate_track, get_meters, get_mixer,
                                     get_routing_options, get_track, set_mixer, set_track)

PREFIX = "[test:tracks]"


def named(label):
    return "{0} {1}".format(PREFIX, label)


def error_message(function, *args, **kwargs):
    with pytest.raises(ToolError) as caught:
        function(*args, **kwargs)
    return str(caught.value)


def _items(live, collection):
    return live.send_command("lom_get", {"path": "live_set", "properties": [collection]})["values"][collection].get("items", [])


def _delete_scratch_returns(live):
    # Live prefixes return names with their letter ("C-[test:tracks] x"), which the shared scratch
    # cleanup does not match, so this module removes its own return tracks.
    names = _items(live, "return_tracks")
    for index in reversed(range(len(names))):
        if re.sub(r"^[A-Z]-", "", names[index]).startswith(PREFIX):
            live.send_command("lom_call", {"path": "live_set", "method": "delete_return_track", "args": [index]})


@pytest.fixture(autouse=True)
def scratch_returns(live):
    _delete_scratch_returns(live)
    yield
    _delete_scratch_returns(live)


@pytest.fixture(scope="module")
def tone_wav(tmp_path_factory):
    """20 s stereo 24-bit 44.1 kHz sine at 441 Hz with a 0 dBFS peak (100 samples per cycle)."""
    path = tmp_path_factory.mktemp("tracks") / "tone_0dbfs.wav"
    rate = 44100
    pcm = np.round(np.sin(2 * np.pi * 441.0 * np.arange(rate * 20) / rate) * 8388607).astype("<i4")
    frames = np.repeat(pcm[:, None], 2, axis=1).astype("<i4")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(3)
        handle.setframerate(rate)
        handle.writeframes(frames.view(np.uint8).reshape(-1, 4)[:, :3].tobytes())
    return str(path)


def _slot_path(name):
    return "live_set tracks {0} clip_slots 0".format(get_track(name)["track"])


def load_tone(live, name, wav):
    """Put the tone in Session slot 0 of an audio track, unwarped so it plays at the file's level."""
    path = _slot_path(name)
    live.send_command("lom_call", {"path": path, "method": "create_audio_clip", "args": [wav]})
    live.send_command("lom_set", {"path": path + " clip", "property": "warping", "value": False})


def _value(live, path, prop):
    return live.send_command("lom_get", {"path": path, "properties": [prop]})["values"][prop]["value"]


def play_until(live, player, tracks, accept, timeout=8.0):
    """Keep the player's clip running (other builders may stop the transport) until accept(meters).

    Skips when Live's audio engine is not running (no audio device): the transport then never advances.
    """
    deadline = time.time() + timeout
    meters, first = None, None
    while time.time() < deadline:
        path = _slot_path(player)
        if not _value(live, path, "is_playing"):
            live.send_command("lom_call", {"path": path, "method": "fire", "args": []})
            time.sleep(0.6)
        meters = dict((item["name"], item) for item in get_meters(tracks)["tracks"])
        if accept(meters):
            return meters
        position = _value(live, "live_set", "current_song_time")
        if first is None:
            first = (position, time.time())
        elif position == first[0] and time.time() - first[1] > 2.0:
            pytest.skip("Live's audio engine is not running: the transport does not advance "
                        "(select an audio device in Live's Settings > Audio)")
        time.sleep(0.25)
    raise AssertionError("Meters never reached the expected levels: {0}".format(meters))


def near(value, target, tolerance):
    return isinstance(value, (int, float)) and abs(value - target) <= tolerance


# --- create_track ---------------------------------------------------------------------------------


def test_create_track_kinds_devices_and_errors(scratch):
    keys = create_track("midi", name=named("keys"), color="#FF0000", device="operator")
    assert keys["kind"] == "midi" and keys["name"] == named("keys")
    assert keys["device"]["name"] == "Operator" and keys["device"]["on"] is True
    assert isinstance(keys["arm"], bool) and isinstance(keys["color_index"], int)
    assert "note" in keys and get_track(named("keys"))["output"]["type"]  # routing is readable from the next call

    audio = create_track("audio", name=named("audio"), color=12)
    assert audio["kind"] == "audio" and audio["color_index"] == 12 and audio["monitoring"] in ("in", "auto", "off")

    ret = create_track("return", name=named("ret"), device="Reverb")
    letter = ret["track"].split(":")[1]
    assert ret["kind"] == "return" and ret["name"] == "{0}-{1}".format(letter, named("ret"))
    assert ret["device"]["class"] == "Reverb" and "arm" not in ret

    assert "Available" in error_message(create_track, "audio", name=named("x"), device="No Such Device 42")
    assert "MIDI track" in error_message(create_track, "audio", name=named("x"), device="Operator")
    assert "kind must be one of" in error_message(create_track, "group", name=named("x"))
    assert "out of range" in error_message(create_track, "midi", name=named("x"), index=9999)
    assert named("x") not in _items(scratch.live, "tracks")


# --- get_track / get_routing_options ----------------------------------------------------------------


def test_get_track_brief_detail_and_unknown(scratch):
    name = scratch.track("get", "audio")
    state = get_track(name)
    for key in ("color_index", "mute", "solo", "arm", "monitoring", "input", "output", "frozen", "mixer", "devices",
                "slots", "slot_count", "arrangement"):
        assert key in state, key
    assert state["name"] == name and state["kind"] == "audio" and state["devices"] == [] and state["slots"] == []
    assert state["mixer"]["volume_db"] == 0.0 and {"A", "B"} <= set(state["mixer"]["sends"])
    assert state["arrangement"] == {"clip_count": 0}

    detail = get_track(name, detail=True)
    assert "active" in detail["mixer"] and "meters" in detail and "has_audio_output" in detail["state"]

    master = get_track("master")
    assert master["kind"] == "master" and "input" not in master and "mute" not in master
    assert get_track("return:A")["kind"] == "return"

    message = error_message(get_track, named("missing"))
    assert "not found" in message and "1-MIDI" in message and "master" in message


def test_get_routing_options(scratch):
    source = scratch.track("opts src", "audio")
    name = scratch.track("opts", "audio")
    options = get_routing_options(name)
    assert {"Main", "Sends Only"} <= set(options["output"]["types"])
    assert {"No Input", source} <= set(options["input"]["types"])
    set_track(name, input=source)
    options = get_routing_options(name)
    assert options["input"]["type"] == source and {"Pre FX", "Post FX", "Post Mixer"} <= set(options["input"]["channels"])
    returned = get_routing_options("return:A")
    assert "input" not in returned and "Main" in returned["output"]["types"]
    assert "input" not in get_routing_options("master")


# --- set_track ------------------------------------------------------------------------------------


def test_set_track_switches_and_routing(scratch):
    source = scratch.track("src", "audio")
    target = scratch.track("dst", "audio")
    keys = scratch.track("keys", "midi")

    out = set_track(source, name=named("src2"), color=12, monitoring="in", collapsed=True)
    source = named("src2")
    assert out["name"] == source and out["color_index"] == 12 and out["monitoring"] == "in" and out["collapsed"] is True
    assert set_track(keys, arm=True)["arm"] is True
    assert set_track(keys, arm=False)["arm"] is False

    # A routing type and its channel in one call (Live updates the channel list immediately).
    assert set_track(keys, input="All Ins", input_channel=1)["input"] == {"type": "All Ins", "channel": "Ch. 1"}
    assert set_track(target, input=source, input_channel="Post FX")["input"] == {"type": source, "channel": "Post FX"}
    assert set_track(target, output=get_track(source)["track"])["output"]["type"] == source  # by track index
    assert set_track(target, output="sends")["output"]["type"] == "Sends Only"
    assert set_track(target, output="master")["output"]["type"] == "Main"
    assert set_track(target, input="none")["input"]["type"] == "No Input"

    message = error_message(set_track, target, output="Nowhere")
    assert "not found" in message and "Main" in message and "Sends Only" in message
    message = error_message(set_track, target, input=source, input_channel="99")
    assert "not found" in message and "Post FX" in message
    assert get_track(target)["input"]["type"] == "No Input"  # the type is restored when the channel fails
    assert "not a group track" in error_message(set_track, target, fold=True)
    assert "Nothing to set" in error_message(set_track, target)
    assert "no input routing" in error_message(set_track, "return:A", input="No Input")


def test_show_chains_and_explicit_index(scratch):
    count = len(_items(scratch.live, "tracks"))
    rack = create_track("midi", name=named("rack"), index=count, device="Instrument Rack")
    assert rack["track"] == count and "showing_chains" not in rack
    assert "show chains" in error_message(set_track, named("rack"), show_chains=True)
    # Live offers chain display once an Instrument Rack has at least two chains.
    path = "live_set tracks {0} devices 0".format(rack["track"])
    for chain in range(2):
        scratch.live.send_command("lom_call", {"path": path, "method": "insert_chain", "args": []})
        scratch.live.send_command("lom_call", {"path": "{0} chains {1}".format(path, chain), "method": "insert_device", "args": ["Operator"]})
    assert set_track(named("rack"), show_chains=True)["showing_chains"] is True
    assert set_track(named("rack"), show_chains=False)["showing_chains"] is False
    assert get_track(named("rack"), detail=True)["devices"][0]["chain_count"] == 2


# --- duplicate_track / delete_track -----------------------------------------------------------------


def test_duplicate_and_delete(scratch):
    name = scratch.track("dup", "midi")
    copy = duplicate_track(name, name=named("dup copy"))
    assert copy["name"] == named("dup copy") and copy["track"] == copy["source"]["track"] + 1
    assert "only duplicate regular tracks" in error_message(duplicate_track, "return:A")

    deleted = delete_track(named("dup copy"))
    assert deleted["deleted"]["name"] == named("dup copy") and named("dup copy") not in _items(scratch.live, "tracks")
    assert "master track cannot be deleted" in error_message(delete_track, "master")
    assert "not found" in error_message(delete_track, named("never existed"))

    ret = create_track("return", name=named("gone"))
    out = delete_track(ret["name"])
    assert out["deleted"]["kind"] == "return" and "note" in out
    assert ret["name"] not in _items(scratch.live, "return_tracks")


# --- mixer ----------------------------------------------------------------------------------------


def test_set_mixer_and_get_mixer(scratch):
    name = scratch.track("mix", "audio")
    state = set_mixer(name, volume_db=-6, pan="25L", sends={"A": -12, "B": "-inf"})
    assert near(state["volume_db"], -6, 0.05) and state["pan"] == -0.5 and state["pan_display"] == "25L"
    assert near(state["sends"]["A"], -12, 0.05) and state["sends"]["B"] == "-inf"
    assert near(set_mixer(name, sends={"Reverb": -20})["sends"]["A"], -20, 0.05)  # a return by name
    assert near(set_mixer(name, volume=0.85)["volume_db"], 0, 0.05)
    assert set_mixer(name, volume_db="-inf")["volume_db"] == "-inf"

    state = set_mixer(name, mute=True, active=False, crossfade="A", pan_mode="split", left_pan=-1, right_pan=0.5)
    assert state["mute"] is True and state["active"] is False and state["crossfade"] == "A"
    assert state["pan_mode"] == "split" and state["left_pan"] == -1.0 and state["right_pan"] == 0.5
    try:
        assert set_mixer(name, solo=True)["solo"] is True
    finally:
        set_mixer(name, solo=False)

    mixer = get_mixer()["tracks"]
    names = [item["name"] for item in mixer]
    assert name in names and "A-Reverb" in names and names[-1] == "Main"
    assert "crossfader" in mixer[-1] and "cue_volume_db" in mixer[-1] and "sends" not in mixer[-1]
    assert [item["name"] for item in get_mixer([name, "master"])["tracks"]] == [name, "Main"]

    assert "maximum" in error_message(set_mixer, name, volume_db=7)
    assert "maximum" in error_message(set_mixer, name, sends={"A": 3})
    assert "not found" in error_message(set_mixer, name, sends={"Z": -6})
    assert "only on the master" in error_message(set_mixer, name, crossfader=0.5)
    assert "has no mute" in error_message(set_mixer, "master", mute=True)  # refused before touching the master
    assert "Nothing to set" in error_message(set_mixer, name)

    ret = create_track("return", name=named("fx"))
    assert "inactive" in error_message(set_mixer, ret["name"], sends={"A": -6})


# --- buses and meters -----------------------------------------------------------------------------


def test_create_bus_carries_audio(scratch, song_state, tone_wav):
    kick = scratch.track("kick", "audio")
    snare = scratch.track("snare", "audio")
    bus = named("Drum Bus")
    out = create_bus(bus, [kick, snare], color=5)
    assert out["bus"]["name"] == bus and out["bus"]["monitoring"] == "in" and out["bus"]["input"]["type"] == "No Input"
    assert [source["output"]["type"] for source in out["sources"]] == [bus, bus] and out["undo_steps"] == 2
    assert get_track(kick)["output"] == {"type": bus, "channel": "Track In"}

    midi = scratch.track("midi src", "midi")
    assert "no audio output" in error_message(create_bus, named("Bus 2"), [midi])
    assert "already exists" in error_message(create_bus, bus, [snare])
    assert "not found" in error_message(create_bus, named("Bus 2"), [named("missing")])
    assert named("Bus 2") not in _items(scratch.live, "tracks")

    set_track(bus, output="Sends Only")  # silent: the bus meter reads before its output routing
    set_mixer(kick, volume_db=-12)
    load_tone(scratch.live, kick, tone_wav)
    meters = play_until(scratch.live, kick, [kick, snare, bus],
                        lambda m: near(m[bus]["output"]["left_db"], -12, 0.5) and near(m[kick]["output"]["left_db"], -12, 0.5))
    assert meters[snare]["output"]["peak_db"] == "-inf"


def test_get_meters_reads_dbfs(scratch, song_state, tone_wav):
    """Live's meters map linearly to dBFS (dBFS = 76 * raw - 70); a 0 dBFS tone at -20 dB reads -20."""
    tone = scratch.track("tone", "audio")
    everything = get_meters()
    kinds = [item["kind"] for item in everything["tracks"]]
    assert "return" in kinds and kinds[-1] == "master" and isinstance(everything["playing"], bool)
    midi_track = next(item for item in everything["tracks"] if item["name"] == "1-MIDI")
    assert "midi" in midi_track["output"] and "midi" in midi_track["input"]
    assert set(get_meters([tone])["tracks"][0]) == {"track", "name", "kind", "output", "input"}
    assert "not found" in error_message(get_meters, [named("missing")])

    set_track(tone, output="Sends Only")
    set_mixer(tone, volume_db=-20)
    load_tone(scratch.live, tone, tone_wav)
    meters = play_until(scratch.live, tone, [tone], lambda m: near(m[tone]["output"]["left_db"], -20, 0.3))
    reading = meters[tone]
    assert near(reading["output"]["right_db"], -20, 0.3)
    assert abs(reading["output"]["raw"][0] - 50 / 76.0) < 0.005
    assert near(reading["input"]["left_db"], 0, 0.3)  # pre-fader: the file's own level
    assert "over_0db" not in reading["output"]
    assert get_meters([tone])["playing"] is True
