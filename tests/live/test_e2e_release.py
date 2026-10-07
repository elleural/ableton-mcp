"""End-to-end acceptance (docs/PRD.md section 11): an agent's whole path from empty set to release files.

Composes a short house track through the public MCP tools only, in the order an agent would use them:
musical context, sounds (a browser drum kit and native synths), parts (drum patterns, a bassline,
a chord progression from music_theory), two scenes, an arrangement with locators, a mix with a
reverb return and automation, a master limiter, a real-time bounce with stems, analysis, and a
release at -14 LUFS. Everything it creates is removed afterwards. Runs about a minute and is audible.
"""
import json
import math
import time
from pathlib import Path

import pytest

from MCP_Server.tools.arrangement import arrange_from_scenes, get_arrangement
from MCP_Server.tools.automation import write_automation
from MCP_Server.tools.browser import load_from_browser, search_browser
from MCP_Server.tools.clips import create_clip, write_drum_pattern, write_notes
from MCP_Server.tools.devices import add_device, delete_device, get_devices
from MCP_Server.tools.export import analyze_audio, bounce, cancel_bounce, create_release, get_bounce_status
from MCP_Server.tools.song import create_scene, delete_locator, set_song
from MCP_Server.tools.status import get_song_overview
from MCP_Server.tools.theory import music_theory
from MCP_Server.tools.tracks import create_track, set_mixer

TEMPO = 124.0
BARS_PER_SECTION = 4
SECTIONS = 2
TAIL_SECONDS = 2.0


def _locator_names():
    return [locator.get("name", "") for locator in get_song_overview().get("locators", [])]


def test_song_to_release(scratch, song_state, tmp_path):
    kit = search_browser("808 Core Kit", category="drums", limit=5).get("results", [])
    if not kit:
        pytest.skip("needs the Drum Essentials pack (808 Core Kit)")
    prefix = scratch.prefix
    name = scratch.name

    # 1. Musical context.
    set_song(tempo=TEMPO, key="A", scale="Minor")

    # 2. Sounds: a drum kit from the browser, native synths, and a reverb return.
    drums = create_track("midi", name("Drums"))["name"]
    load_from_browser(drums, query="808 Core Kit")
    bass = create_track("midi", name("Bass"), device="Operator")["name"]
    chords = create_track("midi", name("Chords"), device="Drift")["name"]
    verb = create_track("return", name("Verb"), device="Reverb")
    verb_letter = str(verb["track"]).split(":")[1]

    # 3. Sections as scenes, with clips per track.
    verse = create_scene(name=name("Verse"))["scene"]
    drop = create_scene(name=name("Drop"))["scene"]
    for slot in (verse, drop):
        for track in (drums, bass, chords):
            create_clip(track, slot=slot, length="2 bars")

    # 4. Parts.
    write_drum_pattern(drums, slot=verse, pattern={"kick": "x---x---x---x---", "closed hat": "--x---x---x---x-"})
    write_drum_pattern(drums, slot=drop, pattern={
        "kick": "x---x---x---x---", "clap": "----x-------x---", "closed hat": "--x-x-x-x-x-x-xX", "open hat": "------x-------x-"})
    line = ["A1", "A1", "C2", "A1", "G1", "A1", "E1", "G1"]
    bass_notes = [{"pitch": pitch, "start": index + 0.5, "duration": 0.4, "velocity": 110} for index, pitch in enumerate(line)]
    for slot in (verse, drop):
        write_notes(bass, bass_notes, slot=slot, mode="replace")
    progression = music_theory("progression", key="A minor", progression="i-VI-III-VII", beats_per_chord=2, octave=3, voice_leading=True)
    assert len(progression["chords"]) == 4
    write_notes(chords, progression["notes"], slot=drop, mode="replace")
    write_notes(chords, progression["notes"], slot=verse, mode="replace")
    write_automation(chords, "volume", slot=verse, shape={"type": "ramp", "from": -30, "to": -10})

    # 5. Mix.
    set_mixer(drums, volume_db=-4)
    set_mixer(bass, volume_db=-9)
    set_mixer(chords, volume_db=-12, sends={verb_letter: -14})

    # 6. Arrangement with named locators.
    sections = [{"scene": name("Verse"), "bars": BARS_PER_SECTION, "name": name("Verse")},
                {"scene": name("Drop"), "bars": BARS_PER_SECTION, "name": name("Drop")}]
    created_locators = []
    try:
        arrange_from_scenes(sections, start="1.1.1", tracks=[drums, bass, chords])
        created_locators = [locator for locator in _locator_names() if locator.startswith(prefix)]
        assert len(created_locators) == SECTIONS
        arrangement = get_arrangement(tracks=[drums, bass, chords])
        song_end_beats = SECTIONS * BARS_PER_SECTION * 4
        for track in arrangement["tracks"]:
            assert track["clips"], "{0} got no arrangement clips".format(track.get("name"))
            assert max(clip["end"]["beats"] for clip in track["clips"]) == pytest.approx(song_end_beats, abs=1e-3)

        # 7. Master, bounce, analysis, release.
        before_master = [device["name"] for device in get_devices("master").get("devices", [])]
        add_device("master", "Limiter")
        try:
            job = bounce(start=0, end="{0}.1.1".format(SECTIONS * BARS_PER_SECTION + 1), tail="{0} s".format(TAIL_SECONDS),
                         stems=[drums, bass], name="E2E House", output_dir=str(tmp_path / "bounce"))
            assert job.get("job") is not None, job
            deadline = time.time() + 180
            status = job
            while time.time() < deadline:
                status = get_bounce_status(wait=50)
                if status.get("phase") in ("done", "failed", "cancelled", "idle"):
                    break
            assert status.get("phase") == "done", status
        finally:
            if status.get("phase") not in ("done", "failed", "cancelled", "idle"):
                cancel_bounce()
            after_master = [device["name"] for device in get_devices("master").get("devices", [])]
            if len(after_master) > len(before_master):
                delete_device("master", len(after_master) - 1)

        files = dict((Path(item["path"]).name, item) for item in status["files"])
        master = next(item for item in status["files"] if item["stem"].lower() in ("master", "main"))
        expected_seconds = SECTIONS * BARS_PER_SECTION * 4 * 60.0 / TEMPO + TAIL_SECONDS
        assert master["duration_seconds"] == pytest.approx(expected_seconds, abs=0.05)
        assert not master["silent"]
        assert len(status["files"]) == 3, files

        analysis = analyze_audio(master["path"], sections="locators")
        loudness = analysis["loudness"]
        assert -40 < loudness["integrated_lufs"] < 0
        assert math.isfinite(loudness["true_peak_dbtp"])

        release = create_release(master["path"], title="E2E House", artist="AbletonMCP", year=2026, genre="House",
                                 formats=["wav16", "flac", "mp3"], output_dir=str(tmp_path / "release"), stems="auto")
        manifest = json.loads(Path(release["manifest"]).read_text())
        assert release["live"]["tempo"] == pytest.approx(TEMPO)
        assert manifest["live"]["tempo"] == pytest.approx(TEMPO)
        produced = release["files"]
        assert set(entry["format"] for entry in produced) >= {"wav16", "flac", "mp3"}
        for entry in produced:
            assert Path(entry["path"]).is_file()
            assert entry["integrated_lufs"] == pytest.approx(-14.0, abs=1.0)
            assert entry["true_peak_dbtp"] <= -1.0 + 0.15
    finally:
        for locator in [locator for locator in _locator_names() if locator.startswith(prefix)]:
            delete_locator(locator)
