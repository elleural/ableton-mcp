"""Live tests for WS-D browser tools: index status and full_refresh listener, search, browse, and loading
onto tracks, device positions, drum pads and Session slots (run against the running Live).

Assertions rely only on native devices ("Operator", "Reverb", ...) and on samples found by searching,
never on pack content, because packs may be installed while the tests run. Nothing is previewed.
"""
import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server.tools.browser import browse, load_from_browser, search_browser
from MCP_Server.tools.devices import add_device, get_devices, set_device


def error_of(function, *args, **kwargs):
    with pytest.raises(ToolError) as caught:
        function(*args, **kwargs)
    return str(caught.value)


def names(track):
    return [device["name"] for device in get_devices(track)["devices"]]


def view_state(live):
    values = live.send_command("lom_get", {"path": "live_set view", "properties": ["selected_track", "selected_scene"]})["values"]
    focus = live.send_command("lom_get", {"path": "live_app view", "properties": ["focused_document_view"]})["values"]
    return values["selected_track"].get("name"), values["selected_scene"].get("name"), focus["focused_document_view"]["value"]


def track_path(live, name):
    tracks = live.send_command("lom_get", {"path": "live_set", "properties": ["tracks"]})["values"]["tracks"]["items"]
    return "live_set tracks {0}".format(tracks.index(name))


def a_sample(query="kick", category="drums"):
    for _ in range(40):
        samples = [item for item in search_browser(query, category, limit=50)["results"] if item["kind"] == "sample"]
        if samples:
            return samples[0]
        time.sleep(0.5)  # The index may still be building in the background.
    pytest.fail("No sample found in the browser for {0!r}".format(query))


def test_scan_status_listener_and_search(live):
    status = live.send_command("browser_scan_status", {"start": "instruments"})
    assert status["listener"] is True and "instruments" in status["categories"]
    found = search_browser("operator", "instruments", limit=5)
    first = found["results"][0]
    assert (first["name"], first["path"], first["kind"], first["uri"]) == ("Operator", "instruments/Operator", "device", "query:Synths#Operator")
    assert first["is_loadable"] and first["is_device"] and found["count"] == len(found["results"]) <= 5
    assert search_browser("REVERB", "audio_effects", limit=3)["results"][0]["path"] == "audio_effects/Reverb"
    anywhere = search_browser("operator", limit=3)
    assert anywhere["results"][0]["path"] == "instruments/Operator" and anywhere["matches"] >= 3
    refreshed = search_browser("operator", "Instruments", limit=1, refresh=True)
    assert refreshed["results"][0]["name"] == "Operator" and "truncated" not in refreshed
    assert search_browser("zzqqzz unlikely", "instruments")["results"] == []
    status = live.send_command("browser_scan_status", {})
    assert status["categories"]["instruments"]["complete"] and status["categories"]["instruments"]["items"] > 100
    assert "Available: all, instruments" in error_of(search_browser, "operator", category="synthesizers")
    assert "non-empty" in error_of(search_browser, "   ")
    assert "limit" in error_of(search_browser, "operator", limit=0)


def test_browse_folders():
    root = browse("")
    assert [item["name"] for item in root["items"]][:3] == ["instruments", "audio_effects", "midi_effects"]
    instruments = browse("instruments", limit=200)
    assert "Operator" in [item["name"] for item in instruments["items"]] and instruments["item"]["kind"] == "folder"
    operator = browse("Instruments/operator")
    assert operator["item"]["kind"] == "device" and operator["path"] == "instruments/Operator" and operator["count"] > 0
    page = browse("instruments", limit=2, offset=1)
    assert len(page["items"]) == 2 and page["offset"] == 1 and page["more"] is True
    assert page["items"][0]["name"] == instruments["items"][1]["name"]
    assert "Available:" in error_of(browse, "instruments/No Such Device")
    assert "category" in error_of(browse, "nowhere/at/all")


def test_load_devices_at_positions_and_restore_the_view(live, scratch):
    midi = scratch.track("load", "midi")
    audio = scratch.track("load fx", "audio")
    before = view_state(live)
    loaded = load_from_browser(midi, path="instruments/Operator")
    assert [device["name"] for device in loaded["devices"]] == ["Operator"] and loaded["loaded"]["kind"] == "device"
    assert view_state(live) == before  # selection and focused view are restored
    set_device(midi, "Operator", name="Old Op")
    uri = search_browser("operator", "instruments", limit=1)["results"][0]["uri"]
    again = load_from_browser(midi, uri=uri)  # an instrument replaces the track's instrument (here in place)
    assert again["replaced"] == ["Old Op"] and [device["name"] for device in again["devices"]] == ["Operator"]
    swapped = load_from_browser(midi, path="instruments/Wavetable")
    assert swapped["replaced"] == ["Operator"] and names(midi) == ["Wavetable"]
    load_from_browser(audio, path="audio_effects/EQ Eight")
    by_query = load_from_browser(audio, query="saturator")
    assert by_query["loaded"]["path"] == "audio_effects/Saturator" and "alternatives" in by_query
    first = load_from_browser(audio, path="audio_effects/Reverb", position=0)
    assert first["devices"][0]["index"] == 0 and names(audio) == ["Reverb", "EQ Eight", "Saturator"]
    middle = load_from_browser(audio, path="audio_effects/Utility", position=2)
    assert middle["devices"][0]["index"] == 2
    load_from_browser(audio, path="audio_effects/Auto Filter")  # no position: appended, not left of the selection
    assert names(audio) == ["Reverb", "EQ Eight", "Utility", "Saturator", "Auto Filter"]
    mode = live.send_command("lom_get", {"path": track_path(live, audio) + " view", "properties": ["device_insert_mode"]})
    assert mode["values"]["device_insert_mode"]["value"] is True  # Live reports the default mode as True
    assert view_state(live) == before


def test_load_samples_onto_pads_slots_and_simpler(live, scratch):
    sample = a_sample()
    drums = scratch.track("pads", "midi")
    add_device(drums, "Drum Rack")
    pad = load_from_browser(drums, uri=sample["uri"], drum_pad="C1")["pad"]
    assert pad["note"] == 36 and pad["note_name"] == "C1" and len(pad["chains"]) == 1
    second = load_from_browser(drums, uri=sample["uri"], drum_pad=38)["pad"]
    assert second["note_name"] == "D1" and second["chains"]
    assert [item["note"] for item in get_devices(drums)["devices"][0]["pads"]] == [36, 38]

    audio = scratch.track("clips", "audio")
    before = view_state(live)
    placed = load_from_browser(audio, uri=sample["uri"], slot=1)
    assert placed["slot"]["slot"] == 1 and placed["slot"]["has_clip"] and placed["loaded"]["kind"] == "sample"
    auto = load_from_browser(audio, path=sample["path"])  # default: the first empty slot
    assert auto["slot"]["slot"] == 0 and auto["slot"]["has_clip"]
    assert view_state(live) == before
    assert "already holds a clip" in error_of(load_from_browser, audio, uri=sample["uri"], slot=1)

    synth = scratch.track("sampler", "midi")
    simpler = load_from_browser(synth, uri=sample["uri"])
    assert simpler["devices"][0]["class"] == "Simpler"
    assert "Session slots of audio tracks" in error_of(load_from_browser, synth, uri=sample["uri"], slot=0)


def test_load_errors(scratch):
    midi = scratch.track("errors", "midi")
    assert "exactly one of uri, path or query" in error_of(load_from_browser, midi)
    assert "exactly one of uri, path or query" in error_of(load_from_browser, midi, path="instruments/Operator", query="operator")
    assert "at most one target" in error_of(load_from_browser, midi, path="instruments/Operator", position=0, slot=0)
    assert "is a folder" in error_of(load_from_browser, midi, path="instruments/Operator/Bass")
    assert "has no Drum Rack" in error_of(load_from_browser, midi, path="instruments/Operator", drum_pad="C1")
    assert "No browser item has URI" in error_of(load_from_browser, midi, uri="query:Synths#No%20Such%20Device")
    assert "No loadable browser item" in error_of(load_from_browser, midi, query="zzqqzz unlikely")
    audio = scratch.track("errors audio", "audio")
    assert "Session slots take samples" in error_of(load_from_browser, audio, path="audio_effects/Reverb", slot=0)
    assert "only loads on MIDI tracks" in error_of(load_from_browser, audio, path="instruments/Operator")
    assert "only loads on MIDI tracks" in error_of(load_from_browser, audio, path="midi_effects/Arpeggiator")
    assert names(audio) == []
    assert "not found" in error_of(load_from_browser, "no such track [test:browser]", path="instruments/Operator")
    assert names(midi) == []


def test_add_device_falls_back_to_the_browser_for_max_for_live(scratch):
    audio = scratch.track("m4l", "audio")
    add_device(audio, "Utility")
    out = add_device(audio, "LFO", position=0)
    assert out["loaded_via"].startswith("browser") and out["device"]["class_name"] == "MxDeviceAudioEffect"
    assert names(audio) == ["LFO", "Utility"]
