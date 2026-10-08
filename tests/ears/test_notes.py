"""Offline tests for the notes ear (ears/notes.py): the clean fixture, the planted defects of PRD 13.2, the
resolution of parts to tracks and clips, and each check's rule and level."""
import copy
import json
import random

import pytest

from ears import notes as notes_ear
from ears import report
from ears.fixtures import notes as fx
from ears.notes import CHECK_LEVELS, CHECKS, analyze_notes
from ears.spec import SpecError, load


@pytest.fixture(scope="module")
def spec():
    return load("nova")


@pytest.fixture(scope="module")
def clean(spec):
    return fx.clean_snapshot(spec)


def results(rep, check=None, status=None, subject=None):
    return [item for item in rep["checks"]
            if (check is None or item["check"] == check) and (status is None or item["status"] == status)
            and (subject is None or item.get("subject") == subject)]


def one(rep, check, subject):
    found = results(rep, check, subject=subject)
    assert len(found) == 1, (check, subject, [item.get("subject") for item in results(rep, check)])
    return found[0]


def flagged(rep):
    """Names of the checks that reported a fail or a warn."""
    return set(item["check"] for item in rep["checks"] if item["status"] in ("fail", "warn"))


def track_of(snap, name):
    return next(each for each in snap["tracks"] if each["name"] == name)


def clip_of(snap, track_name, scene="NEON-MID"):
    return next(each for each in track_of(snap, track_name)["clips"] if each["scene"] == scene)


# ---------------------------------------------------------------------------
# The clean fixture
# ---------------------------------------------------------------------------


def test_clean_snapshot_has_no_fail_and_no_warn(spec, clean):
    rep = analyze_notes(clean, spec)
    assert rep["counts"]["fail"] == 0 and rep["counts"]["warn"] == 0, [
        (item["check"], item.get("subject"), item["summary"]) for item in rep["checks"] if item["status"] in ("fail", "warn")]
    assert rep["verdict"].startswith("0 fail, 0 warn, ")
    assert rep["kind"] == "notes" and rep["set"] == "neon"
    assert "band" not in rep   # every band was analysed


def test_clean_snapshot_runs_every_rule_check(spec, clean):
    rep = analyze_notes(clean, spec)
    passed = set(item["check"] for item in rep["checks"] if item["status"] == "pass")
    rules = set(name for name, level in CHECK_LEVELS.items() if level in ("fail", "warn"))
    assert rules <= passed, rules - passed
    # Seven pitched parts, six of them with a single progression, one shared pad, two variations, two leads.
    assert len(results(rep, "notes.in_key")) == 7
    assert len(results(rep, "notes.chord_tones")) == 6
    assert len(results(rep, "notes.shared_stem")) == 1
    assert len(results(rep, "notes.clash")) == 2
    assert len(results(rep, "notes.lead_rests")) == 2
    assert len(results(rep, "notes.kick_pattern")) == 3
    assert len(results(rep, "notes.density")) == 3
    assert len(results(rep, "notes.motif")) == 1


def test_clean_snapshot_follows_the_plans_format(clean):
    assert set(clean) >= {"song", "scenes", "tracks", "returns", "master"}
    assert [scene["name"] for scene in clean["scenes"][:3]] == ["NEON-LOW", "NEON-MID", "NEON-HIGH"]
    names = [each["name"] for each in clean["tracks"]]
    assert names[:9] == ["kick", "perc", "pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB"]
    for each in clean["tracks"]:
        assert {"index", "name", "kind", "mute", "solo", "arm", "mixer", "devices", "clips"} <= set(each)
        for one_clip in each["clips"]:
            assert {"slot", "scene", "name", "is_midi", "length", "looping", "loop_start", "loop_end", "start_marker",
                    "end_marker", "warping", "muted", "notes"} <= set(one_clip)
            for entry in one_clip["notes"]:
                assert {"id", "pitch", "start", "duration", "velocity", "mute", "probability", "velocity_deviation"} <= set(entry)
    ids = [entry["id"] for each in clean["tracks"] for one_clip in each["clips"] for entry in one_clip["notes"]]
    assert len(ids) == len(set(ids))
    json.dumps(clean)   # plain data


def test_clean_snapshot_has_the_layout_of_the_real_set(clean):
    """Only kick and perc have a clip in every band's scene; the other stems live in NEON-MID."""
    for each in clean["tracks"]:
        scenes = [one_clip["scene"] for one_clip in each["clips"]]
        if each["name"] in ("kick", "perc"):
            assert scenes == ["NEON-LOW", "NEON-MID", "NEON-HIGH"], each["name"]
        elif each["name"] == "fill":
            assert scenes == ["NEON-FILL"]
        else:
            assert scenes == ["NEON-MID"], each["name"]
    for name, letter in (("bassA", "A"), ("bassB", "B"), ("arpA", "A"), ("leadB", "B")):
        assert [one_clip["name"] for one_clip in track_of(clean, name)["clips"]] == [letter]


def test_clean_snapshot_loop_lengths_and_content(clean):
    bars = {"kick": 2, "perc": 4, "pad": 16, "bassA": 8, "arpB": 8, "leadA": 8}
    for name, count in bars.items():
        for one_clip in track_of(clean, name)["clips"]:
            assert one_clip["length"] == one_clip["loop_end"] == count * 4.0
    # Live's naming: the A bass sits on A1 over Am and D1 over Dm
    bass = sorted(set(entry["pitch"] for entry in clip_of(clean, "bassA")["notes"]))
    assert bass == [38, 45]
    assert len(clip_of(clean, "arpA")["notes"]) == 128   # sixteenth notes for 8 bars
    assert len(clip_of(clean, "pad")["notes"]) == 32     # two notes a bar for 16 bars


def test_analysis_does_not_change_the_snapshot(spec, clean):
    before = copy.deepcopy(clean)
    analyze_notes(clean, spec)
    analyze_notes(clean, spec, band="LOW", parts=["bass"])
    assert clean == before


def test_the_clean_mainframe_set_passes_too(spec):
    """MAINFRAME's B plays progression C (Am Dm G E): the pad must be safe over A and C."""
    snap = fx.clean_snapshot(spec, "mainframe")
    assert [each["name"] for each in snap["tracks"]][:3] == ["mf_kick", "mf_perc", "mf_pad"]
    rep = analyze_notes(snap, spec, "mainframe")
    assert rep["set"] == "mainframe"
    assert rep["counts"]["fail"] == 0 and rep["counts"]["warn"] == 0
    assert len(results(rep, "notes.shared_stem", status="pass")) == 1


def test_spec_can_be_given_by_name_or_as_a_dict(spec, clean):
    assert analyze_notes(clean, "nova")["verdict"] == analyze_notes(clean, spec)["verdict"]
    assert analyze_notes(clean, spec.to_dict())["verdict"] == analyze_notes(clean, spec)["verdict"]


# ---------------------------------------------------------------------------
# Planted defects (PRD 13.2)
# ---------------------------------------------------------------------------

# The checks PRD 13.2 names for each defect.
NAMED = {
    "bass_semitone": {"notes.in_key", "notes.chord_tones"},
    "d_major": {"notes.in_key", "notes.chord_tones"},
    "clash": {"notes.clash"},
    "kick_late": {"notes.grid"},
    "lead_no_rests": {"notes.lead_rests"},
    "pad_a_over_e": {"notes.shared_stem"},
}
# A note a semitone from the chord, or a pad note held against the G# of E, also sits a semitone from the arp
# that plays the chord tone: notes.clash follows from the defect itself. No other check may react.
ALSO = {"bass_semitone": {"notes.clash"}, "pad_a_over_e": {"notes.clash"}}


def test_every_defect_has_a_planter():
    assert set(fx.DEFECTS) == set(NAMED)


@pytest.mark.parametrize("defect", sorted(NAMED))
def test_planted_defect_is_caught_by_the_named_checks(spec, clean, defect):
    rep = analyze_notes(fx.plant(clean, defect), spec)
    found = flagged(rep)
    assert NAMED[defect] <= found, (defect, found)
    assert found <= NAMED[defect] | ALSO.get(defect, set()), (defect, found - NAMED[defect])


@pytest.mark.parametrize("defect", sorted(NAMED))
def test_plant_returns_a_copy_and_changes_something(spec, clean, defect):
    before = copy.deepcopy(clean)
    planted = fx.plant(clean, defect)
    assert clean == before
    assert planted != clean
    json.dumps(planted)


def test_plant_rejects_an_unknown_defect(clean):
    with pytest.raises(ValueError, match="Unknown defect"):
        fx.plant(clean, "warp_drive")


@pytest.mark.parametrize("defect", sorted(NAMED))
def test_defects_can_be_planted_in_the_mainframe_set_too(spec, defect):
    """plant() finds the set from the snapshot's tracks: MAINFRAME's B plays progression C, bar 4 is still E."""
    snap = fx.clean_snapshot(spec, "mainframe")
    planted = fx.plant(snap, defect)
    assert planted != snap
    rep = analyze_notes(planted, spec, "mainframe")
    found = flagged(rep)
    assert NAMED[defect] <= found, (defect, found)
    assert found <= NAMED[defect] | ALSO.get(defect, set()), (defect, found - NAMED[defect])


def test_bass_semitone_is_a_fail_at_the_bass_with_places(spec, clean):
    rep = analyze_notes(fx.plant(clean, "bass_semitone"), spec)
    in_key = one(rep, "notes.in_key", "bassA@MID")
    chord = one(rep, "notes.chord_tones", "bassA@MID")
    assert in_key["status"] == "fail" and chord["status"] == "fail"       # chord_tones is a fail for the bass
    assert chord["level"] == "fail"
    assert [item["where"] for item in in_key["items"]] == ["3.1.1", "3.3.1"]
    assert [item["found"] for item in in_key["items"]] == ["D#1", "D#1"]
    assert chord["items"][0]["expected"] == "a tone of Dm (D F A)"
    assert in_key["value"] == pytest.approx(14 / 16.0)
    assert results(rep, "notes.in_key", status="fail") == [in_key]        # nothing else is out of key
    clash = results(rep, "notes.clash", status="fail")
    assert [item["subject"] for item in clash] == ["variation A@MID"]     # variation B is untouched


def test_d_major_is_in_key_fail_and_chord_tones_warn(spec, clean):
    rep = analyze_notes(fx.plant(clean, "d_major"), spec)
    assert sorted(item["subject"] for item in results(rep, "notes.in_key", status="fail")) == ["arpA@MID", "leadA@MID"]
    chord = results(rep, "notes.chord_tones", status="warn")
    assert [item["subject"] for item in chord] == ["leadA@MID"]          # the lead plays F# on beat 3; a warn off the bass
    assert chord[0]["items"][0]["found"] == "F#4"
    assert chord[0]["items"][0]["expected"] == "a tone of Dm (D F A)"
    assert not results(rep, "notes.chord_tones", status="fail")


def test_clash_defect_names_the_two_stems_and_the_beat(spec, clean):
    rep = analyze_notes(fx.plant(clean, "clash"), spec)
    [item] = results(rep, "notes.clash", status="fail")
    assert item["subject"] == "variation A@MID"
    assert item["items"][0]["where"] == "5.2.2"
    assert sorted(item["items"][0]["parts"]) == ["arpA", "leadA"]
    assert "B3" in item["items"][0]["found"] and "C4" in item["items"][0]["found"]
    assert all(entry["overlap_beats"] >= 0.25 for entry in item["items"])
    assert one(rep, "notes.clash", "variation B@MID")["status"] == "pass"
    assert not results(rep, "notes.in_key", status="fail")                # both notes are in A minor


def test_kick_late_is_a_grid_warn_in_milliseconds(spec, clean):
    rep = analyze_notes(fx.plant(clean, "kick_late"), spec)
    [item] = results(rep, "notes.grid", status="warn")
    assert item["subject"] == "kick@MID"
    assert item["tempo"] == 140.0                                         # the middle of the MID band
    assert item["value"] == pytest.approx(53.6, abs=0.1)                  # a thirty-second note at 140 BPM
    assert item["items"][0]["found"] == "late by 53.6 ms"
    assert item["items"][0]["where"] == "1.1.1"
    assert one(rep, "notes.grid", "kick@LOW")["status"] == "pass"
    assert one(rep, "notes.grid", "kick@HIGH")["status"] == "pass"
    # at 100 BPM the same offset is 75 ms
    slow = analyze_notes(fx.plant(clean, "kick_late"), spec, band="MID", tempo=100)
    assert results(slow, "notes.grid", status="warn")[0]["value"] == pytest.approx(75.0, abs=0.1)


def test_lead_without_rests_is_a_warn(spec, clean):
    rep = analyze_notes(fx.plant(clean, "lead_no_rests"), spec)
    [item] = results(rep, "notes.lead_rests", status="warn")
    assert item["subject"] == "leadA@MID"
    assert item["value"] == 0.0 and item["target"] == 0.4
    assert one(rep, "notes.lead_rests", "leadB@MID")["status"] == "pass"


def test_pad_holding_a_over_e_is_a_shared_stem_fail(spec, clean):
    rep = analyze_notes(fx.plant(clean, "pad_a_over_e"), spec)
    [item] = results(rep, "notes.shared_stem", status="fail")
    assert item["subject"] == "pad@MID"
    assert item["items"][0]["where"] == "4.1.1" and item["items"][0]["found"] == "A3"
    assert item["items"][0]["against"] == "G# of E (progression B)"
    assert "Dm (D F A) / E (E G# B)" in item["items"][0]["expected"]
    assert not results(rep, "notes.in_key", status="fail")                # A is in A minor
    clash = one(rep, "notes.clash", "variation B@MID")                    # and it meets the G# of arp B
    assert clash["status"] == "fail" and "pad" in clash["items"][0]["parts"]
    assert one(rep, "notes.clash", "variation A@MID")["status"] == "pass"


# ---------------------------------------------------------------------------
# Resolving parts to tracks and clips
# ---------------------------------------------------------------------------


def test_missing_track_is_a_set_names_fail_and_skips_the_dependent_checks(spec, clean):
    snap = copy.deepcopy(clean)
    snap["tracks"] = [each for each in snap["tracks"] if each["name"] != "bassB"]
    rep = analyze_notes(snap, spec)
    [names] = results(rep, "set.names", status="fail")
    assert names["subject"] == "bassB" and "no track named 'bassB'" in names["summary"]
    skipped = [item["check"] for item in results(rep, status="skip") if item.get("subject") == "bassB"]
    assert sorted(skipped) == ["notes.chord_tones", "notes.grid", "notes.in_key", "notes.loop_length", "set.unwarped"]
    assert rep["counts"]["fail"] == 1 and rep["counts"]["warn"] == 0      # nothing else broke
    clash = one(rep, "notes.clash", "variation B@MID")
    assert clash["status"] == "pass" and "bassB" in clash["summary"]      # said what it could not compare


def test_a_track_named_with_the_wrong_case_is_not_found_but_the_hint_says_so(spec, clean):
    snap = copy.deepcopy(clean)
    track_of(snap, "bassA")["name"] = "bassa"
    rep = analyze_notes(snap, spec)
    [names] = results(rep, "set.names", status="fail")
    assert names["subject"] == "bassA" and "'bassa'" in names["summary"] and "exactly" in names["summary"]


def test_duplicate_track_names_are_a_fail(spec, clean):
    snap = copy.deepcopy(clean)
    snap["tracks"].append(copy.deepcopy(track_of(clean, "leadB")))
    rep = analyze_notes(snap, spec)
    [names] = results(rep, "set.names", status="fail")
    assert names["subject"] == "leadB" and "2 tracks" in names["summary"]
    assert all(item["status"] == "skip" for item in results(rep, "notes.in_key", subject="leadB"))


def test_variation_clips_are_named_after_the_variation(spec, clean):
    snap = copy.deepcopy(clean)
    clip_of(snap, "arpB")["name"] = "arp B take 2"
    rep = analyze_notes(snap, spec)
    [names] = results(rep, "set.names", status="fail")
    assert names["subject"] == "arpB@MID"
    assert "'arp B take 2'" in names["summary"] and "'B'" in names["summary"]
    assert one(rep, "notes.in_key", "arpB@MID")["status"] == "pass"       # the notes are still read


def test_a_band_without_its_own_clip_falls_back_to_the_default_scene(spec, clean):
    snap = copy.deepcopy(clean)
    track_of(snap, "kick")["clips"] = [each for each in track_of(snap, "kick")["clips"] if each["scene"] != "NEON-LOW"]
    rep = analyze_notes(snap, spec)
    assert not results(rep, "set.names", status="fail")
    assert rep["counts"]["fail"] == 0 and rep["counts"]["warn"] == 0
    # LOW reads the MID clip: one analysis, labelled with the band that owns the scene, serving both bands
    assert not [item for item in results(rep, "set.names") if item["subject"] == "kick@LOW"]
    assert one(rep, "set.names", "kick@MID")["bands"] == ["LOW", "MID"]
    assert one(rep, "set.names", "kick@MID")["scene"] == "NEON-MID"
    # and the pattern shows up against LOW's half-time expectation, because LOW now plays four-on-the-floor
    low, mid = one(rep, "notes.kick_pattern", "kick@LOW"), one(rep, "notes.kick_pattern", "kick@MID")
    assert (low["value"], low["matches"], low["scene"]) == ("four-on-the-floor", False, "NEON-MID")
    assert (mid["value"], mid["matches"]) == ("four-on-the-floor", True)


def test_a_part_with_no_clip_in_any_scene_of_the_band_is_a_fail(spec, clean):
    snap = copy.deepcopy(clean)
    track_of(snap, "kick")["clips"] = [each for each in track_of(snap, "kick")["clips"] if each["scene"] == "NEON-HIGH"]
    rep = analyze_notes(snap, spec)
    failed = results(rep, "set.names", status="fail")
    assert sorted(item["subject"] for item in failed) == ["kick@LOW", "kick@MID"]
    assert "no clip in 'NEON-LOW' or 'NEON-MID'" in one(rep, "set.names", "kick@LOW")["summary"]
    assert one(rep, "set.names", "kick@HIGH")["status"] == "pass"
    assert one(rep, "notes.grid", "kick@LOW")["status"] == "skip"


def test_clips_are_matched_by_slot_when_the_snapshot_has_no_scene_names(spec, clean):
    snap = copy.deepcopy(clean)
    for each in snap["tracks"]:
        for one_clip in each["clips"]:
            one_clip["scene"] = None
    rep = analyze_notes(snap, spec)
    assert rep["counts"]["fail"] == 0 and rep["counts"]["warn"] == 0
    assert one(rep, "set.names", "kick@LOW")["status"] == "pass"


def test_a_snapshot_that_is_not_a_snapshot_never_raises(spec):
    for bad in (None, {}, [], "nothing", {"tracks": None}, {"tracks": [None, 3, "x"], "scenes": "oops"},
                {"tracks": [{"name": "kick", "clips": None}]}):
        rep = analyze_notes(bad, spec)
        assert rep["counts"]["fail"] >= 9
        assert set(item["status"] for item in rep["checks"]) <= {"fail", "skip", "info"}
        json.dumps(report.compact(rep))


def test_absurd_values_in_a_snapshot_do_not_hang_or_raise(spec, clean):
    """A corrupted snapshot is a finding or a skip, never a stall: huge or tiny loops, odd types, unhashable names."""
    def corrupt(change):
        snap = copy.deepcopy(clean)
        change(snap)
        return analyze_notes(snap, spec)

    def huge_loop(snap):
        clip_of(snap, "arpA")["length"] = clip_of(snap, "arpA")["loop_end"] = 1e308

    rep = corrupt(huge_loop)
    assert one(rep, "notes.loop_length", "arpA@MID")["status"] == "fail"
    assert any("only the first 4096" in text for text in rep["warnings"])

    def tiny_loop(snap):
        clip_of(snap, "bassA")["length"] = clip_of(snap, "bassA")["loop_end"] = 1e-9

    assert one(corrupt(tiny_loop), "notes.loop_length", "bassA@MID")["status"] == "fail"

    def odd_types(snap):
        snap["tracks"][3]["name"] = ["not", "a", "name"]
        snap["scenes"][0]["index"] = [1]
        low = clip_of(snap, "kick", "NEON-LOW")
        low["scene"], low["slot"] = None, {"x": 1}
        clip_of(snap, "pad")["notes"] = 7.5
        track_of(snap, "leadA")["devices"] = 3.5
        track_of(snap, "leadB")["clips"] = "none"

    rep = corrupt(odd_types)
    assert one(rep, "set.names", "bassA")["status"] == "fail"             # the track whose name is no string is not found
    assert one(rep, "notes.in_key", "pad@MID")["status"] == "skip"

    def bad_pitch(snap):
        notes = clip_of(snap, "arpA")["notes"]
        notes[0]["pitch"] = 1e308
        notes[1]["pitch"] = -3
        notes[2]["pitch"] = float("nan")

    rep = corrupt(bad_pitch)
    assert any("3 malformed notes" in text for text in rep["warnings"])
    assert one(rep, "notes.in_key", "arpA@MID")["status"] == "pass"


def test_a_clip_without_notes_in_the_snapshot_is_skipped(spec, clean):
    snap = copy.deepcopy(clean)
    del clip_of(snap, "bassA")["notes"]
    rep = analyze_notes(snap, spec)
    assert one(rep, "notes.in_key", "bassA@MID")["status"] == "skip"
    assert "no notes" in one(rep, "notes.in_key", "bassA@MID")["summary"]
    assert rep["counts"]["fail"] == 0


def test_an_empty_clip_has_nothing_to_check_but_its_rests(spec, clean):
    snap = copy.deepcopy(clean)
    clip_of(snap, "leadA")["notes"] = []
    rep = analyze_notes(snap, spec)
    assert one(rep, "notes.in_key", "leadA@MID")["status"] == "skip"
    assert one(rep, "notes.grid", "leadA@MID")["status"] == "skip"
    assert one(rep, "notes.lead_rests", "leadA@MID")["status"] == "warn"  # all rests


def test_malformed_notes_are_skipped_with_a_warning(spec, clean):
    snap = copy.deepcopy(clean)
    notes = clip_of(snap, "bassA")["notes"]
    notes.append({"id": 999, "pitch": None, "start": 0.0, "duration": 1.0})
    notes.append("not a note")
    rep = analyze_notes(snap, spec)
    assert rep["counts"]["fail"] == 0
    assert any("2 malformed notes" in text for text in rep["warnings"])


# ---------------------------------------------------------------------------
# set.unwarped
# ---------------------------------------------------------------------------


def test_warped_audio_stem_is_a_fail_and_unwarped_audio_passes(spec, clean):
    warped = copy.deepcopy(clean)
    audio = clip_of(warped, "arpA")
    audio.update(is_midi=False, warping=True)
    del audio["notes"]
    rep = analyze_notes(warped, spec)
    [item] = results(rep, "set.unwarped", status="fail")
    assert item["subject"] == "arpA@MID" and "warping on" in item["summary"]
    assert one(rep, "notes.in_key", "arpA@MID")["status"] == "skip"
    assert "audio clip" in one(rep, "notes.in_key", "arpA@MID")["summary"]
    audio["warping"] = False
    rep = analyze_notes(warped, spec)
    assert one(rep, "set.unwarped", "arpA@MID")["status"] == "pass"
    assert rep["counts"]["fail"] == 0


# ---------------------------------------------------------------------------
# notes.in_key and notes.chord_tones (hand-built set with one track and clips named A and B)
# ---------------------------------------------------------------------------

MINI = {
    "name": "mini", "key": "A minor", "meter": "4/4", "grid": 16,
    "progressions": {"A": ["Am", "F"], "B": ["Am", "E"]},
    "stems": {
        "kick": {"bars": 1, "pitched": False, "role": "kick"},
        "bass": {"bars": 2, "variations": ["A", "B"], "role": "bass"},
        "lead": {"bars": 2, "variations": ["A", "B"], "rest_share": 0.5, "role": "lead"},
    },
    "sets": {"mini": {"tempos": [120], "variations": {"A": "A", "B": "B"}}},
}


def mini_spec(**changes):
    data = copy.deepcopy(MINI)
    data.update(changes)
    return load(data)


def mini_snapshot():
    kick = fx.clip("kick", [fx.note(36, beat, 0.25) for beat in range(4)], 4.0, slot=0, scene="S1")
    bass_a = fx.clip("A", [fx.note(45, 0, 1.5), fx.note(45, 2, 1.5), fx.note(41, 4, 1.5), fx.note(41, 6, 1.5)], 8.0, slot=0, scene="S1")
    bass_b = fx.clip("B", [fx.note(45, 0, 1.5), fx.note(45, 2, 1.5), fx.note(40, 4, 1.5), fx.note(40, 6, 1.5)], 8.0, slot=1, scene="S2")
    lead_a = fx.clip("A", [fx.note(72, 0, 1), fx.note(76, 2, 1), fx.note(81, 4, 1), fx.note(84, 6, 1)], 8.0, slot=0, scene="S1")
    lead_b = fx.clip("B", [fx.note(72, 0, 1), fx.note(76, 2, 1), fx.note(80, 4, 1), fx.note(83, 6, 1)], 8.0, slot=1, scene="S2")
    tracks = [fx.track("kick", [kick], 0), fx.track("bass", [bass_a, bass_b], 1), fx.track("lead", [lead_a, lead_b], 2)]
    return fx.renumber(fx.snapshot(tracks, ["S1", "S2"], tempo=120.0, set_name="mini"))


def mini_clip(snap, track_name, clip_name):
    return next(each for each in track_of(snap, track_name)["clips"] if each["name"] == clip_name)


def test_one_track_layout_resolves_clips_by_name():
    spec = mini_spec()
    assert spec.layout("mini") == "clip"
    rep = analyze_notes(mini_snapshot(), spec)
    assert rep["counts"]["fail"] == 0 and rep["counts"]["warn"] == 0, [
        (item["check"], item.get("subject"), item["summary"]) for item in rep["checks"] if item["status"] in ("fail", "warn")]
    subjects = sorted(set(item["subject"] for item in results(rep, "set.names")))
    assert subjects == ["bassA", "bassB", "kick", "leadA", "leadB"]       # no bands: no "@band" in the label
    assert "band" not in rep
    assert (rep["stems"]["bassB"]["scene"], rep["stems"]["bassB"]["clip"]) == ("S2", "B")


def test_one_track_layout_reports_a_missing_variation_clip():
    snap = mini_snapshot()
    track_of(snap, "bass")["clips"] = [each for each in track_of(snap, "bass")["clips"] if each["name"] != "B"]
    rep = analyze_notes(snap, mini_spec())
    [names] = results(rep, "set.names", status="fail")
    assert names["subject"] == "bassB" and "no clip named 'B'" in names["summary"] and "'A'" in names["summary"]
    assert one(rep, "notes.in_key", "bassB")["status"] == "skip"
    assert one(rep, "notes.in_key", "bassA")["status"] == "pass"


def test_one_track_layout_prefers_the_clip_in_the_bands_scene_row():
    spec = mini_spec(sets={"mini": {
        "tempos": [100, 140], "variations": {"A": "A", "B": "B"},
        "bands": [{"name": "SLOW", "tempos": [100, 100], "scene": "S1", "kick": "half-time"},
                  {"name": "FAST", "tempos": [140, 140], "scene": "S2", "kick": "four-on-the-floor"}]}})
    snap = mini_snapshot()
    snap["scenes"].append({"index": 2, "name": "S3"})
    bass = track_of(snap, "bass")
    bass["clips"] = [mini_clip(snap, "bass", "A"), copy.deepcopy(mini_clip(snap, "bass", "A")), mini_clip(snap, "bass", "B")]
    bass["clips"][1].update(slot=1, scene="S2", notes=[fx.note(40, 0, 1.5)])        # another bass A, in the FAST row
    bass["clips"][2].update(slot=2, scene="S3")
    kick = track_of(snap, "kick")
    kick["clips"].append(copy.deepcopy(kick["clips"][0]))
    kick["clips"][1].update(slot=1, scene="S2")
    rep = analyze_notes(snap, spec)
    stems = rep["stems"]
    assert (stems["bassA@SLOW"]["scene"], stems["bassA@SLOW"]["clip"]) == ("S1", "A")
    assert (stems["bassA@FAST"]["scene"], stems["bassA@FAST"]["clip"]) == ("S2", "A")
    assert (stems["bassB@SLOW"]["scene"], stems["bassB@SLOW"]["clip"]) == ("S3", "B")   # not in a band row: found by its name
    assert stems["bassB@SLOW"]["bands"] == ["SLOW", "FAST"]
    assert one(rep, "notes.in_key", "bassA@FAST")["status"] == "pass"


def test_g_sharp_is_in_key_over_e_but_not_over_am():
    snap = mini_snapshot()
    mini_clip(snap, "bass", "B")["notes"] = [fx.note(45, 0, 1), fx.note(44, 1, 1), fx.note(40, 4, 1), fx.note(44, 5, 1)]
    rep = analyze_notes(fx.renumber(snap), mini_spec())
    item = one(rep, "notes.in_key", "bassB")
    assert item["status"] == "fail"
    assert [(entry["where"], entry["found"]) for entry in item["items"]] == [("1.2.1", "G#1")]   # bar 1 is Am; bar 2 is E
    assert "A minor" in item["items"][0]["expected"] and "Am (A C E)" in item["items"][0]["expected"]


def test_chord_tones_is_a_fail_for_the_bass_and_a_warn_for_other_stems():
    snap = mini_snapshot()
    mini_clip(snap, "bass", "A")["notes"][0]["pitch"] = 38       # D1 on beat 1 of the Am bar
    mini_clip(snap, "lead", "A")["notes"][0]["pitch"] = 86       # D5 on beat 1 of the Am bar
    rep = analyze_notes(snap, mini_spec())
    bass, lead = one(rep, "notes.chord_tones", "bassA"), one(rep, "notes.chord_tones", "leadA")
    assert (bass["status"], lead["status"]) == ("fail", "warn")
    assert one(rep, "notes.in_key", "bassA")["status"] == "pass"           # D is in A minor: only the chord test objects
    assert bass["items"][0] == {"where": "1.1.1", "found": "D1", "expected": "a tone of Am (A C E)"}
    assert one(rep, "notes.chord_tones", "bassB")["status"] == "pass"


def test_chord_tones_reads_only_beats_one_and_three():
    snap = mini_snapshot()
    mini_clip(snap, "lead", "A")["notes"] = [fx.note(72, 0, 0.5), fx.note(86, 1, 0.5), fx.note(86, 1.5, 0.5), fx.note(76, 2, 0.5), fx.note(86, 3, 0.5)]
    item = one(analyze_notes(fx.renumber(snap), mini_spec()), "notes.chord_tones", "leadA")
    assert item["status"] == "pass" and item["downbeat_notes"] == 2          # D5 on beats 2, 2.5 and 4 are not downbeats
    assert item["value"] == pytest.approx(1.0 / 2.5)                         # but they count in the sounding time


def test_chord_tones_share_of_sounding_time_is_reported():
    snap = mini_snapshot()
    # bar 1: C held for 3 beats (chord tone), D held for 1 beat (not): 75% of the sounding time on chord tones
    mini_clip(snap, "lead", "A")["notes"] = [fx.note(72, 0, 3), fx.note(86, 3, 1)]
    item = one(analyze_notes(fx.renumber(snap), mini_spec()), "notes.chord_tones", "leadA")
    assert item["status"] == "pass"
    assert item["value"] == pytest.approx(0.75)


def test_a_note_just_before_the_bar_line_belongs_to_the_next_bar():
    """A bass root played 20 ms early is still the next chord's root (here F, after Am)."""
    snap = mini_snapshot()
    early = mini_clip(snap, "bass", "A")["notes"][2]
    assert early["pitch"] == 41 and early["start"] == 4.0
    early["start"] = 3.97
    rep = analyze_notes(snap, mini_spec())
    assert one(rep, "notes.chord_tones", "bassA")["status"] == "pass"
    assert one(rep, "notes.in_key", "bassA")["status"] == "pass"


def test_muted_notes_do_not_count_and_unpitched_parts_have_no_pitch_checks():
    snap = mini_snapshot()
    mini_clip(snap, "bass", "A")["notes"].append(fx.note(61, 0.5, 1, mute=True))   # a wrong note, muted
    mini_clip(snap, "kick", "kick")["notes"][0]["pitch"] = 61                      # a "wrong" kick pitch means nothing
    rep = analyze_notes(snap, mini_spec())
    assert rep["counts"]["fail"] == 0
    assert not results(rep, "notes.in_key", subject="kick")
    assert not results(rep, "notes.chord_tones", subject="kick")
    assert not [entry for entry in rep["roll"] if entry["part"] == "kick"]
    assert not [entry for entry in rep["roll"] if entry["part"] == "bassA" and entry["pitch"] == 61]
    density = results(analyze_notes(snap, mini_spec()), "notes.density")[0]
    assert {entry["part"]: entry["onsets"] for entry in density["items"]}["bassA"] == 4


# ---------------------------------------------------------------------------
# notes.loop_length
# ---------------------------------------------------------------------------


def test_loop_length_must_equal_the_stems_bar_count(spec, clean):
    snap = copy.deepcopy(clean)
    short = clip_of(snap, "arpA")
    short["loop_end"] = short["length"] = 28.0
    rep = analyze_notes(snap, spec)
    [item] = results(rep, "notes.loop_length", status="fail")
    assert item["subject"] == "arpA@MID" and item["value"] == 7.0 and item["target"] == 8.0
    assert "7 bars" in item["summary"] and "8 bars" in item["summary"]
    assert item["items"][0]["found"] == "7 bars" and item["items"][0]["expected"] == "8 bars"
    # the notes of the missing bar are outside the loop and do not sound
    assert one(rep, "notes.in_key", "arpA@MID")["status"] == "pass"
    assert rep["stems"]["arpA@MID"]["bars"] == 7.0 and rep["stems"]["arpA@MID"]["notes"] == 112


def test_loop_length_uses_the_loop_braces_not_the_clip_length(spec, clean):
    snap = copy.deepcopy(clean)
    brace = clip_of(snap, "bassB")
    brace["loop_end"] = 16.0
    rep = analyze_notes(snap, spec)
    assert one(rep, "notes.loop_length", "bassB@MID")["status"] == "fail"
    brace["loop_end"] = 32.0
    brace["looping"] = False
    brace["end_marker"] = 32.0
    item = one(analyze_notes(snap, spec), "notes.loop_length", "bassB@MID")
    assert item["status"] == "pass" and "not looping" in item["summary"]


def test_a_clip_that_does_not_give_its_length_is_skipped_for_loop_length(spec, clean):
    snap = copy.deepcopy(clean)
    unknown = clip_of(snap, "bassB")
    for key in ("length", "loop_start", "loop_end", "start_marker", "end_marker"):
        del unknown[key]
    rep = analyze_notes(snap, spec)
    assert one(rep, "notes.loop_length", "bassB@MID")["status"] == "skip"
    assert one(rep, "notes.in_key", "bassB@MID")["status"] == "pass"      # the notes' extent stands in for the loop


# ---------------------------------------------------------------------------
# notes.grid
# ---------------------------------------------------------------------------


def test_grid_tolerance_is_milliseconds_converted_at_the_tempo():
    spec = mini_spec()   # 120 BPM: 10 ms is 0.02 beats
    snap = mini_snapshot()
    mini_clip(snap, "bass", "A")["notes"][2]["start"] = 4.015           # 7.5 ms late
    assert one(analyze_notes(snap, spec), "notes.grid", "bassA")["status"] == "pass"
    mini_clip(snap, "bass", "A")["notes"][2]["start"] = 4.03            # 15 ms late
    item = one(analyze_notes(snap, spec), "notes.grid", "bassA")
    assert item["status"] == "warn" and item["value"] == pytest.approx(15.0)
    assert item["items"][0]["found"] == "late by 15 ms" and item["items"][0]["where"] == "2.1.1"
    assert item["items"][0]["note"] == "F1" and item["tempo"] == 120.0 and item["unit"] == "ms"
    # at 240 BPM the same offset is 7.5 ms
    assert one(analyze_notes(snap, spec, tempo=240), "notes.grid", "bassA")["status"] == "pass"
    # an early note is reported as early
    mini_clip(snap, "bass", "A")["notes"][2]["start"] = 3.97
    early = one(analyze_notes(snap, spec), "notes.grid", "bassA")
    assert early["status"] == "warn" and early["items"][0]["found"] == "early by 15 ms"


def test_grid_tolerance_can_be_changed_in_the_spec():
    snap = mini_snapshot()
    mini_clip(snap, "bass", "A")["notes"][2]["start"] = 4.03
    loose = mini_spec(tolerances={"grid_ms": 20})
    assert one(analyze_notes(snap, loose), "notes.grid", "bassA")["status"] == "pass"


def test_grid_uses_the_bands_middle_tempo_unless_a_tempo_is_given(spec, clean):
    rep = analyze_notes(clean, spec)
    assert one(rep, "notes.grid", "kick@LOW")["tempo"] == 110.0
    assert one(rep, "notes.grid", "kick@MID")["tempo"] == 140.0
    assert one(rep, "notes.grid", "kick@HIGH")["tempo"] == 170.0
    assert one(rep, "notes.grid", "bassA@MID")["tempo"] == 110.0         # shared by every band: judged at the strictest grid
    assert one(analyze_notes(clean, spec, band="HIGH"), "notes.grid", "bassA@MID")["tempo"] == 170.0
    assert one(analyze_notes(clean, spec, tempo=95), "notes.grid", "kick@HIGH")["tempo"] == 95.0


def test_grid_is_skipped_for_a_stem_with_midi_effects(spec, clean):
    snap = copy.deepcopy(clean)
    track_of(snap, "arpA")["devices"].append(fx.device("Arpeggiator", kind="midi_effect", class_name="MidiArpeggiator", path="0.0"))
    track_of(snap, "arpA")["devices"].append(fx.device("Scale", kind="midi_effect", class_name="MidiScale", path="1", active=False))
    rep = analyze_notes(snap, spec)
    grid = one(rep, "notes.grid", "arpA@MID")
    assert grid["status"] == "skip" and "Arpeggiator" in grid["summary"] and "Scale" not in grid["summary"]
    assert grid["before_midi_effects"] is True
    assert one(rep, "notes.in_key", "arpA@MID")["before_midi_effects"] is True
    assert one(rep, "set.names", "arpA@MID")["before_midi_effects"] is True
    assert "before_midi_effects" not in one(rep, "notes.in_key", "arpB@MID")
    [info] = results(rep, "notes.midi_effects")
    assert info["status"] == "info" and info["subject"] == "arpA@MID" and "before MIDI effects" in info["summary"]
    assert info["items"][0]["found"] == "Arpeggiator"
    clash = one(rep, "notes.clash", "variation A@MID")
    assert clash["before_midi_effects"] is True
    assert rep["counts"]["fail"] == 0 and rep["counts"]["warn"] == 0


def test_midi_effect_type_is_read_in_the_forms_live_uses(spec, clean):
    for kind in ("midi_effect", "MIDI Effect", "midi-effect", "MidiEffect", 4):
        snap = copy.deepcopy(clean)
        track_of(snap, "leadB")["devices"].append(fx.device("Random", kind=kind))
        rep = analyze_notes(snap, spec)
        assert one(rep, "notes.grid", "leadB@MID")["status"] == "skip", kind
    snap = copy.deepcopy(clean)
    track_of(snap, "leadB")["devices"].append(fx.device("EQ Eight", kind="audio_effect"))
    assert one(analyze_notes(snap, spec), "notes.grid", "leadB@MID")["status"] == "pass"


# ---------------------------------------------------------------------------
# notes.lead_rests
# ---------------------------------------------------------------------------


def lead_with_sounding_steps(count):
    snap = mini_snapshot()
    mini_clip(snap, "lead", "A")["notes"] = [fx.note(72, step * 0.25, 0.25) for step in range(count)]
    return fx.renumber(snap)


@pytest.mark.parametrize("sounding, status", [(16, "pass"), (19, "pass"), (20, "warn"), (13, "pass"), (12, "warn"), (0, "warn"), (32, "warn")])
def test_lead_rests_within_ten_points_of_the_spec(sounding, status):
    # 32 sixteenth steps; the spec asks for 50% rests, plus or minus 10 points
    item = one(analyze_notes(lead_with_sounding_steps(sounding), mini_spec()), "notes.lead_rests", "leadA")
    assert item["status"] == status, item["summary"]
    assert item["value"] == pytest.approx((32 - sounding) / 32.0, abs=1e-3)   # reports round to three digits
    assert item["target"] == 0.5 and item["tolerance"] == 0.1


def test_lead_rest_tolerance_comes_from_the_spec():
    wide = mini_spec(tolerances={"lead_rest_points": 20})
    assert one(analyze_notes(lead_with_sounding_steps(20), wide), "notes.lead_rests", "leadA")["status"] == "pass"


def test_a_note_covering_part_of_a_step_makes_the_step_sound():
    snap = mini_snapshot()
    mini_clip(snap, "lead", "A")["notes"] = [fx.note(72, step * 0.5 + 0.1, 0.1) for step in range(16)]   # one short note in every other step
    item = one(analyze_notes(fx.renumber(snap), mini_spec()), "notes.lead_rests", "leadA")
    assert item["value"] == pytest.approx(0.5)


def test_only_stems_with_a_rest_share_are_checked_for_rests(spec, clean):
    rep = analyze_notes(clean, spec)
    assert sorted(item["subject"] for item in results(rep, "notes.lead_rests")) == ["leadA@MID", "leadB@MID"]


# ---------------------------------------------------------------------------
# notes.shared_stem
# ---------------------------------------------------------------------------


def pad_with(clean, *entries):
    snap = copy.deepcopy(clean)
    clip_of(snap, "pad")["notes"] = [fx.note(pitch, start, duration) for pitch, start, duration in entries]
    return fx.renumber(snap)


@pytest.mark.parametrize("pitch, safe", [
    (62, True),    # D: safe over Dm and E
    (71, True),    # B
    (69, False),   # A: a semitone from the G# of E
    (68, False),   # G#: in key over E, but a semitone from the A of Dm
    (65, False),   # F: a semitone from the E of E
    (64, False),   # E: a semitone from the F of Dm
    (60, False),   # C: a semitone from the B of E
    (63, False),   # D#: a semitone from D and E
])
def test_in_bar_four_only_d_and_b_are_safe_over_both_progressions(spec, clean, pitch, safe):
    rep = analyze_notes(pad_with(clean, (pitch, 12.0, 4.0)), spec)
    item = one(rep, "notes.shared_stem", "pad@MID")
    assert (item["status"] == "pass") is safe, item["summary"]
    assert item["value"] == (1.0 if safe else 0.0)


def test_shared_stem_looks_at_every_bar_a_note_is_held_in(spec, clean):
    # B held from bar 4 (safe) into bar 5 (Am, whose C is a semitone away)
    item = one(analyze_notes(pad_with(clean, (71, 12.0, 8.0)), spec), "notes.shared_stem", "pad@MID")
    assert item["status"] == "fail"
    assert [entry["where"] for entry in item["items"]] == ["5.1.1"]
    assert item["items"][0]["against"] == "C of Am (progressions A and B)"     # both progressions play Am in bar 5
    # an overhang shorter than a sixteenth is not held in the next bar
    assert one(analyze_notes(pad_with(clean, (71, 12.0, 4.1)), spec), "notes.shared_stem", "pad@MID")["status"] == "pass"


def test_shared_stem_is_not_applied_to_the_variation_stems(spec, clean):
    rep = analyze_notes(clean, spec)
    assert [item["subject"] for item in results(rep, "notes.shared_stem")] == ["pad@MID"]


def mini_with_pad(variations):
    data = copy.deepcopy(MINI)
    data["stems"]["pad"] = {"bars": 2, "role": "pad"}
    data["sets"]["mini"]["variations"] = variations
    snap = mini_snapshot()
    pad = fx.clip("pad", [fx.note(57, 0, 4), fx.note(61, 4, 4)], 8.0, slot=0, scene="S1")   # A over Am, then C# over F
    snap["tracks"].append(fx.track("pad", [pad], 3))
    return snap, load(data)


def test_a_pad_shared_by_two_progressions_has_shared_stem_but_no_chord_tones():
    snap, spec = mini_with_pad({"A": "A", "B": "B"})
    rep = analyze_notes(snap, spec)
    assert not results(rep, "notes.chord_tones", subject="pad")
    item = one(rep, "notes.shared_stem", "pad")
    assert item["status"] == "fail" and item["items"][0]["found"] == "C#3"          # a semitone from the C of F and the C of Am


def test_a_pad_that_follows_one_progression_gets_the_chord_tones_check():
    snap, spec = mini_with_pad({"A": "A", "B": "A"})                                # both variations play progression A
    rep = analyze_notes(snap, spec)
    chord = one(rep, "notes.chord_tones", "pad")
    assert chord["status"] == "warn" and chord["level"] == "warn"                   # C# is no tone of F, and the pad is not the bass
    assert chord["items"][0]["expected"] == "a tone of F (F A C)"
    assert one(rep, "notes.shared_stem", "pad")["status"] == "fail"


# ---------------------------------------------------------------------------
# notes.clash
# ---------------------------------------------------------------------------


def test_clash_needs_a_sixteenth_of_overlap():
    snap = mini_snapshot()
    spec = mini_spec()
    # bass A holds A1 on beat 1 (bar 1); a lead B-flat sounds against it for only a thirty-second note
    mini_clip(snap, "lead", "A")["notes"] = [fx.note(70 + 12, 0, 0.125)]          # A#: a semitone from the A of the bass
    assert one(analyze_notes(fx.renumber(snap), spec), "notes.clash", "variation A")["status"] == "pass"
    mini_clip(snap, "lead", "A")["notes"] = [fx.note(70 + 12, 0, 0.25)]
    item = one(analyze_notes(fx.renumber(snap), spec), "notes.clash", "variation A")
    assert item["status"] == "fail" and item["items"][0]["where"] == "1.1.1"
    assert sorted(item["items"][0]["parts"]) == ["bassA", "leadA"]


def test_clash_threshold_comes_from_the_spec():
    snap = mini_snapshot()
    mini_clip(snap, "lead", "A")["notes"] = [fx.note(82, 0, 0.25)]
    strict = mini_spec(tolerances={"clash_sixteenths": 2})
    assert one(analyze_notes(fx.renumber(snap), strict), "notes.clash", "variation A")["status"] == "pass"


def test_clash_counts_a_major_seventh_and_octaves_apart():
    snap = mini_snapshot()
    mini_clip(snap, "lead", "A")["notes"] = [fx.note(44 + 36, 0, 1)]     # G#5 over the bass A1: 35 semitones, interval class 1
    assert one(analyze_notes(fx.renumber(snap), mini_spec()), "notes.clash", "variation A")["status"] == "fail"


def test_clash_does_not_compare_a_stem_with_the_other_variation():
    snap = mini_snapshot()
    mini_clip(snap, "lead", "B")["notes"] = [fx.note(82, 0, 1)]          # A# in B's lead, a semitone from the A of both basses
    rep = analyze_notes(fx.renumber(snap), mini_spec())
    assert one(rep, "notes.clash", "variation A")["status"] == "pass"
    assert one(rep, "notes.clash", "variation B")["status"] == "fail"    # B's own bass plays A1 too


def test_clash_tiles_short_loops_over_the_longest_one(spec, clean):
    """The 8-bar bass meets the 16-bar pad twice; a clash in the second pass only shows when the loops are tiled."""
    snap = copy.deepcopy(clean)
    pad = clip_of(snap, "pad")
    # bar 9 (index 8) of the pad: Am. Put a G# (a semitone from the bass A and the arp A) there only.
    pad["notes"] = [entry for entry in pad["notes"] if not 32.0 <= entry["start"] < 36.0] + [fx.note(56, 32.0, 4.0)]
    rep = analyze_notes(fx.renumber(snap), spec)
    item = one(rep, "notes.clash", "variation A@MID")
    assert item["status"] == "fail"
    assert item["items"][0]["where"] == "9.1.1"           # the first clash is in the second pass of the 8-bar loops
    assert {entry["where"].split(".")[0] for entry in item["items"]} == {"9"}
    assert not results(analyze_notes(clean, spec), "notes.clash", status="fail")


def test_clash_group_reports_the_stems_it_compared(spec, clean):
    item = one(analyze_notes(clean, spec), "notes.clash", "variation A@MID")
    assert item["status"] == "pass"
    for name in ("pad", "bassA", "arpA", "leadA"):
        assert name in item["summary"]
    assert "bassB" not in item["summary"] and "16 bars" in item["summary"]
    assert item["bands"] == ["LOW", "MID", "HIGH"]                       # the pitched stems are the same clips in every band


# ---------------------------------------------------------------------------
# notes.kick_pattern, notes.density, notes.motif
# ---------------------------------------------------------------------------


def kick_clip(snap, pattern_bars, name="kick"):
    """Replace the mini kick with the given 16-step strings (one per bar)."""
    steps = []
    for bar, pattern in enumerate(pattern_bars):
        steps += [bar * 4.0 + index * 0.25 for index, char in enumerate(pattern) if char == "x"]
    target = mini_clip(snap, "kick", name)
    target["notes"] = [fx.note(36, start, 0.25) for start in steps]
    target["length"] = target["loop_end"] = target["end_marker"] = 4.0 * len(pattern_bars)
    return fx.renumber(snap)


@pytest.mark.parametrize("bars, label", [
    (["x---x---x---x---"], "four-on-the-floor"),
    (["x---x---x---x--x"], "four-on-the-floor"),            # a pickup on the last sixteenth
    (["x-------x-------"], "half-time"),
    (["x-------x-----x-"], "half-time"),
    (["x---------------"], "other"),
    (["x---x-------x---"], "other"),
    (["x---x---x---x---", "x-------x-------"], "other"),    # mixed bars
    (["----------------"], "none"),
])
def test_kick_pattern_classification(bars, label):
    spec = mini_spec(stems=dict(MINI["stems"], kick={"bars": len(bars), "pitched": False, "role": "kick"}))
    rep = analyze_notes(kick_clip(mini_snapshot(), bars), spec)
    item = one(rep, "notes.kick_pattern", "kick")
    assert item["status"] == "info" and item["value"] == label
    assert [entry["pattern"] for entry in item["items"]] == bars


def test_kick_pattern_is_compared_with_the_bands_expectation(spec, clean):
    rep = analyze_notes(clean, spec)
    low, mid, high = (one(rep, "notes.kick_pattern", "kick@" + band) for band in ("LOW", "MID", "HIGH"))
    assert (low["value"], low["target"], low["matches"]) == ("half-time", "half-time", True)
    assert (mid["value"], mid["target"], mid["matches"]) == ("four-on-the-floor", "four-on-the-floor", True)
    assert high["value"] == "four-on-the-floor" and "target" not in high and "matches" not in high   # HIGH: none is named
    assert "names no kick pattern for HIGH" in high["summary"]
    assert [entry["pattern"] for entry in low["items"]] == ["x-------x-------", "x-------x-------"]
    assert high["items"][1]["pattern"] == "x---x---x---x--x" and high["off_beat_hits"] == 1
    assert all(item["status"] == "info" for item in results(rep, "notes.kick_pattern"))


def test_kick_pattern_that_differs_from_the_brief_is_reported_not_failed(spec, clean):
    snap = copy.deepcopy(clean)
    clip_of(snap, "kick", "NEON-LOW")["notes"] = copy.deepcopy(clip_of(snap, "kick", "NEON-MID")["notes"])
    rep = analyze_notes(snap, spec)
    low = one(rep, "notes.kick_pattern", "kick@LOW")
    assert low["status"] == "info" and low["matches"] is False and "but the spec says half-time" in low["summary"]
    assert rep["counts"]["fail"] == 0 and rep["counts"]["warn"] == 0


def test_kick_pattern_reads_a_late_kick_as_the_step_it_was_meant_for(spec, clean):
    rep = analyze_notes(fx.plant(clean, "kick_late"), spec)
    assert one(rep, "notes.kick_pattern", "kick@MID")["value"] == "four-on-the-floor"


def test_density_is_onsets_per_bar_per_stem_by_band(spec, clean):
    rep = analyze_notes(clean, spec)
    per_band = dict((item["subject"], dict((entry["part"], entry["onsets_per_bar"]) for entry in item["items"]))
                    for item in results(rep, "notes.density"))
    assert set(per_band) == {"LOW", "MID", "HIGH"}
    assert per_band["LOW"]["kick"] == 2.0 and per_band["MID"]["kick"] == 4.0 and per_band["HIGH"]["kick"] == 4.5
    for band in per_band.values():
        assert band["arpA"] == 16.0 and band["bassA"] == 2.0 and band["pad"] == 1.0   # a chord is one onset
    assert "kick 4" in one(rep, "notes.density", "MID")["summary"]
    assert rep["stems"]["arpB@MID"]["onsets_per_bar"] == 16.0


def test_motif_says_when_every_band_uses_the_same_clip(spec, clean):
    snap = copy.deepcopy(clean)
    for name in ("kick", "perc"):
        track_of(snap, name)["clips"] = [each for each in track_of(snap, name)["clips"] if each["scene"] == "NEON-MID"]
    item = one(analyze_notes(snap, spec), "notes.motif", "neon")
    assert item["status"] == "info" and item["value"] == 1.0
    assert "same clip" in item["summary"] and "nothing to compare" in item["summary"]
    assert all(entry["same_clip"] for entry in item["items"])


def test_motif_compares_the_clips_that_differ_between_bands(spec, clean):
    item = one(analyze_notes(clean, spec), "notes.motif", "neon")
    assert item["status"] == "info"
    pairs = [entry for entry in item["items"] if "similarity" in entry]
    assert sorted(set(entry["part"] for entry in pairs)) == ["kick", "perc"]
    assert len([entry for entry in pairs if entry["part"] == "kick"]) == 3     # LOW/MID, LOW/HIGH, MID/HIGH
    by_bands = dict((entry["bands"], entry["similarity"]) for entry in pairs if entry["part"] == "kick")
    assert by_bands["MID vs HIGH"] > 0.8                                       # HIGH is MID plus a pickup
    assert by_bands["LOW vs MID"] < by_bands["MID vs HIGH"]
    assert "same clip in every band: pad, bassA" in item["summary"]
    same = [entry["part"] for entry in item["items"] if entry.get("same_clip")]
    assert same == ["pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB"]


def test_motif_identical_figures_in_different_clips_have_similarity_one(spec, clean):
    snap = copy.deepcopy(clean)
    for scene in ("NEON-LOW", "NEON-HIGH"):
        clip_of(snap, "perc", scene)["notes"] = copy.deepcopy(clip_of(snap, "perc", "NEON-MID")["notes"])
    item = one(analyze_notes(snap, spec), "notes.motif", "neon")
    perc = [entry for entry in item["items"] if entry["part"] == "perc" and "similarity" in entry]
    assert [entry["similarity"] for entry in perc] == [1.0, 1.0, 1.0]


def test_motif_compares_intervals_and_rhythm_of_pitched_stems():
    spec = mini_spec(sets={"mini": {
        "tempos": [100, 140], "variations": {"A": "A", "B": "B"},
        "bands": [{"name": "SLOW", "tempos": [100, 100], "scene": "S1"}, {"name": "FAST", "tempos": [140, 140], "scene": "S2"}]}})
    snap = mini_snapshot()
    snap["scenes"].append({"index": 2, "name": "S3"})
    bass = track_of(snap, "bass")
    second = copy.deepcopy(mini_clip(snap, "bass", "A"))
    second.update(slot=1, scene="S2")
    second["notes"] = [fx.note(45, 0, 1), fx.note(48, 1, 1), fx.note(52, 2, 1), fx.note(45, 3, 1)]   # another figure
    bass["clips"] = [mini_clip(snap, "bass", "A"), second, mini_clip(snap, "bass", "B")]
    bass["clips"][2].update(slot=2, scene="S3")
    kick = track_of(snap, "kick")
    kick["clips"].append(copy.deepcopy(kick["clips"][0]))
    kick["clips"][1].update(slot=1, scene="S2")
    item = one(analyze_notes(fx.renumber(snap), spec), "notes.motif", "mini")
    [pair] = [entry for entry in item["items"] if entry["part"] == "bassA"]
    assert 0.0 <= pair["similarity"] < 1.0 and pair["intervals"] is not None and pair["rhythm"] is not None
    assert pair["bands"] == "SLOW vs FAST"


def test_motif_is_skipped_when_one_band_is_asked_for(spec, clean):
    item = one(analyze_notes(clean, spec, band="MID"), "notes.motif", "neon")
    assert item["status"] == "skip" and "without a band" in item["summary"]
    skipped = one(analyze_notes(mini_snapshot(), mini_spec()), "notes.motif", "mini")
    assert skipped["status"] == "skip" and "fewer than two" in skipped["summary"]


# ---------------------------------------------------------------------------
# notes.probability
# ---------------------------------------------------------------------------


def test_notes_with_probability_below_one_are_reported(spec, clean):
    snap = copy.deepcopy(clean)
    notes = clip_of(snap, "leadA")["notes"]
    notes[0]["probability"] = 0.5
    notes[3]["probability"] = 0.75
    notes[4].update(probability=0.25, mute=True)       # muted: ignored
    rep = analyze_notes(snap, spec)
    [item] = results(rep, "notes.probability")
    assert item["status"] == "info" and item["subject"] == "leadA@MID" and item["value"] == 2
    assert "takes" in item["summary"]
    assert [entry["where"] for entry in item["items"]] == ["1.1.1", "1.4.2"]
    assert rep["counts"]["fail"] == 0 and rep["counts"]["warn"] == 0
    assert not results(analyze_notes(clean, spec), "notes.probability")


# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------


def test_band_by_name_and_by_tempo(spec, clean):
    low = analyze_notes(clean, spec, band="low")
    assert low["band"] == "LOW"
    assert sorted(set(item["subject"] for item in results(low, "notes.kick_pattern"))) == ["kick@LOW"]
    assert sorted(item["subject"] for item in results(low, "notes.density")) == ["LOW"]
    assert low["values"]["tempos"] == {"LOW": 110.0}
    by_tempo = analyze_notes(clean, spec, band=150)
    assert by_tempo["band"] == "MID"
    assert analyze_notes(clean, spec, band="140")["band"] == "MID"
    # the stems that live in NEON-MID are read for LOW as well, labelled with the band that owns their scene
    assert one(low, "set.names", "bassA@MID")["scene"] == "NEON-MID"
    assert one(low, "set.names", "kick@LOW")["scene"] == "NEON-LOW"
    assert one(low, "notes.grid", "bassA@MID")["tempo"] == 110.0                  # judged at the tempo of the band asked for


def test_unknown_band_set_or_tempo_raise_spec_errors(spec, clean):
    with pytest.raises(SpecError, match="no band"):
        analyze_notes(clean, spec, band="ULTRA")
    with pytest.raises(SpecError, match="in no band"):
        analyze_notes(clean, spec, band=90)
    with pytest.raises(SpecError, match="no set"):
        analyze_notes(clean, spec, set_name="moon")
    for bad in (0, -5, "fast"):
        with pytest.raises(ValueError, match="tempo"):
            analyze_notes(clean, spec, tempo=bad)


def test_a_set_without_bands_ignores_a_band_argument_with_a_warning():
    rep = analyze_notes(mini_snapshot(), mini_spec(), band="MID")
    assert "band" not in rep and any("no tempo bands" in text for text in rep["warnings"])
    assert rep["counts"]["fail"] == 0


def test_parts_limit_the_report(spec, clean):
    rep = analyze_notes(clean, spec, parts=["bassA", "leadB"])
    subjects = set(item["subject"] for item in rep["checks"] if item["check"].startswith(("set.", "notes.in_key", "notes.grid")))
    assert subjects == {"bassA@MID", "leadB@MID"}
    assert sorted(item["subject"] for item in results(rep, "notes.clash")) == ["variation A@MID", "variation B@MID"]
    assert not results(rep, "notes.shared_stem")                       # the pad was not asked for
    by_stem = analyze_notes(clean, spec, parts="bass, kick")
    assert set(item["subject"] for item in results(by_stem, "set.names")) == {
        "kick@LOW", "kick@MID", "kick@HIGH", "bassA@MID", "bassB@MID"}
    track_name = analyze_notes(clean, spec, parts=["pad"])
    assert [item["subject"] for item in results(track_name, "notes.shared_stem")] == ["pad@MID"]


def test_parts_keep_the_other_stems_as_context_for_clashes(spec, clean):
    planted = fx.plant(clean, "clash")
    rep = analyze_notes(planted, spec, parts=["arpA"])
    assert one(rep, "notes.clash", "variation A@MID")["status"] == "fail"           # arp A is one of the clashing stems
    assert not results(analyze_notes(planted, spec, parts=["bassA"]), "notes.clash", status="fail")   # the bass is not


def test_unknown_parts_are_warned_about(spec, clean):
    rep = analyze_notes(clean, spec, parts=["theremin", "bassA"])
    assert any("theremin" in text for text in rep["warnings"])
    assert one(rep, "set.names", "bassA@MID")["status"] == "pass"


def test_a_bad_chord_in_the_spec_is_a_spec_error():
    data = copy.deepcopy(MINI)
    data["progressions"]["A"] = ["Am", "Xyz"]
    with pytest.raises(SpecError, match="Progression A"):
        analyze_notes(mini_snapshot(), load(data))


def test_analysis_does_not_change_the_spec(spec, clean):
    before = copy.deepcopy(spec.to_dict())
    analyze_notes(clean, spec)
    assert spec.to_dict() == before


# ---------------------------------------------------------------------------
# The piano roll and the report
# ---------------------------------------------------------------------------


def test_roll_marks_chord_tones_scale_tones_and_out_of_key_notes(spec, clean):
    roll = analyze_notes(fx.plant(clean, "bass_semitone"), spec)["roll"]
    assert all(set(entry) >= {"part", "pitch", "name", "start", "duration", "status"} for entry in roll)
    assert {entry["status"] for entry in roll} == {"chord", "out"}          # the fixture's notes are all chord tones
    out = [entry for entry in roll if entry["status"] == "out"]
    assert {entry["part"] for entry in out} == {"bassA"} and len(out) == 2
    assert out[0]["name"] == "D#1" and out[0]["start"] == 8.0 and out[0]["duration"] == 1.5
    assert {entry["part"] for entry in roll} == {"pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB"}   # pitched parts only
    assert len([entry for entry in roll if entry["part"] == "arpA"]) == 128


def test_roll_marks_a_note_of_the_scale_that_is_not_in_the_chord():
    snap = mini_snapshot()
    mini_clip(snap, "lead", "A")["notes"] = [fx.note(72, 0, 1), fx.note(86, 1, 1), fx.note(85, 2, 1)]   # C (chord), D5 (scale), C#5 (out)
    roll = analyze_notes(fx.renumber(snap), mini_spec())["roll"]
    assert [(entry["name"], entry["status"]) for entry in roll if entry["part"] == "leadA"] == [
        ("C4", "chord"), ("D5", "scale"), ("C#5", "out")]


def test_roll_is_limited_to_the_parts_asked_for(spec, clean):
    roll = analyze_notes(clean, spec, parts=["leadA"])["roll"]
    assert {entry["part"] for entry in roll} == {"leadA"} and len(roll) == 32
    assert {entry["band"] for entry in roll} == {"MID"}


def test_the_report_is_a_report_with_compact_and_json_forms(spec, clean):
    rep = analyze_notes(fx.plant(clean, "bass_semitone"), spec)
    assert rep["kind"] == "notes" and rep["subject"] == "live set"
    assert rep["verdict"] == report.verdict(rep["checks"])
    assert rep["counts"] == report.counts(rep["checks"])
    json.dumps(rep)
    compact = report.compact(rep, full_report="notes.json")
    assert len(json.dumps(compact)) <= report.COMPACT_CHARS
    assert compact["verdict"] == rep["verdict"] and compact["full_report"] == "notes.json"
    assert {item["check"] for item in compact["fail"]} >= {"notes.in_key", "notes.chord_tones"}
    assert "roll" not in compact


def test_the_compact_report_fits_its_budget_even_with_every_defect_planted(spec, clean):
    snap = clean
    for defect in fx.DEFECTS:
        snap = fx.plant(snap, defect)
    rep = analyze_notes(snap, spec)
    assert flagged(rep) >= set().union(*NAMED.values())
    compact = report.compact(rep, full_report="notes.json")
    assert len(json.dumps(compact, separators=(",", ":"))) <= report.COMPACT_CHARS
    assert compact["verdict"] == rep["verdict"] and compact["fail"] and compact["warn"]


def test_values_are_small_and_stems_say_which_clip_was_read(spec, clean):
    rep = analyze_notes(clean, spec)
    values = rep["values"]
    assert set(values) == {"tempos", "chord_tone_share", "rest_share"}              # what the compact report carries
    assert values["tempos"] == {"LOW": 110.0, "MID": 140.0, "HIGH": 170.0}
    assert values["chord_tone_share"]["bassA@MID"] == 1.0
    assert values["rest_share"]["leadA@MID"] == pytest.approx(0.406, abs=0.001)
    assert "pad@MID" not in values["chord_tone_share"]                             # two progressions: no chord_tones check
    kick = rep["stems"]["kick@LOW"]
    assert kick == {"track": "kick", "scene": "NEON-LOW", "clip": "kick LOW", "bars": 2.0, "notes": 4, "onsets_per_bar": 2.0}
    pad = rep["stems"]["pad@MID"]
    assert (pad["scene"], pad["bars"], pad["notes"], pad["bands"]) == ("NEON-MID", 16.0, 32, ["LOW", "MID", "HIGH"])
    assert len(rep["stems"]) == 13
    assert rep["stems"]["arpB@MID"]["onsets_per_bar"] == 16.0


def test_every_check_has_a_level_from_the_prd_table():
    assert CHECKS == tuple(CHECK_LEVELS)
    assert dict(CHECK_LEVELS) == {
        "set.names": "fail", "set.unwarped": "fail", "notes.in_key": "fail", "notes.chord_tones": "warn",
        "notes.clash": "fail", "notes.shared_stem": "fail", "notes.loop_length": "fail", "notes.grid": "warn",
        "notes.lead_rests": "warn", "notes.kick_pattern": "report", "notes.density": "report", "notes.motif": "report",
        "notes.probability": "report", "notes.midi_effects": "report"}


def test_report_level_checks_never_fail_or_warn(spec, clean):
    for defect in list(NAMED) + [None]:
        snap = clean if defect is None else fx.plant(clean, defect)
        rep = analyze_notes(snap, spec)
        for item in rep["checks"]:
            if CHECK_LEVELS[item["check"]] == "report":
                assert item["status"] in ("info", "skip"), (defect, item["check"], item["status"])


# ---------------------------------------------------------------------------
# The algorithms underneath, against brute force
# ---------------------------------------------------------------------------


def random_notes(rng, count, span=16.0):
    out = []
    for _ in range(count):
        start = rng.choice([0.0, 0.25, 0.5, 1.0, 2.0, 3.5]) + rng.randint(0, int(span)) * 0.25
        end = start + rng.choice([0.125, 0.25, 0.5, 1.0, 4.0])
        pitch = rng.randint(40, 52)
        out.append({"pitch": pitch, "start": start, "end": end, "name": notes_ear.theory.note_name(pitch)})
    return out


def brute_force_overlaps(notes_a, notes_b, minimum):
    found = set()
    for a in notes_a:
        for b in notes_b:
            if notes_ear.theory.interval_class(a["pitch"], b["pitch"]) != 1:
                continue
            low, high = max(a["start"], b["start"]), min(a["end"], b["end"])
            if high - low >= minimum - notes_ear.EPS:
                found.add((id(a), id(b)))
    return found


@pytest.mark.parametrize("seed", range(40))
def test_semitone_overlaps_match_a_brute_force_search(seed):
    rng = random.Random(seed)
    notes_a, notes_b = random_notes(rng, rng.randint(0, 25)), random_notes(rng, rng.randint(0, 25))
    for minimum in (0.25, 0.5):
        found = notes_ear._semitone_overlaps(notes_a, notes_b, minimum)
        assert set((id(a), id(b)) for a, b, _, _ in found) == brute_force_overlaps(notes_a, notes_b, minimum)
        assert len(found) == len(set((id(a), id(b)) for a, b, _, _ in found))    # each pair once
        for a, b, low, high in found:
            assert low == max(a["start"], b["start"]) and high == min(a["end"], b["end"]) and high - low >= minimum - 1e-6


def test_notes_that_only_touch_do_not_overlap():
    a = [{"pitch": 60, "start": 0.0, "end": 1.0, "name": "C3"}]
    b = [{"pitch": 61, "start": 1.0, "end": 2.0, "name": "C#3"}]
    assert notes_ear._semitone_overlaps(a, b, 0.25) == []
    b[0]["start"] = 0.75
    assert len(notes_ear._semitone_overlaps(a, b, 0.25)) == 1


def test_tile_repeats_a_loop_and_cuts_notes_at_its_end():
    loop = [{"pitch": 60, "start": 0.0, "end": 2.0, "name": "C3"}, {"pitch": 62, "start": 3.0, "end": 6.0, "name": "D3"}]
    tiled = notes_ear._tile(loop, 4.0, 12.0)
    assert [(n["pitch"], n["start"], n["end"]) for n in tiled] == [
        (60, 0.0, 2.0), (62, 3.0, 4.0), (60, 4.0, 6.0), (62, 7.0, 8.0), (60, 8.0, 10.0), (62, 11.0, 12.0)]
    assert [n["start"] for n in notes_ear._tile(loop, 4.0, 4.0)] == [0.0, 3.0]            # one pass when it is already the longest
    assert len(notes_ear._tile(loop, 1e-9, 4096.0)) <= notes_ear.MAX_TILES * len(loop)    # a degenerate loop is bounded


@pytest.mark.parametrize("seed", range(20))
def test_rest_share_matches_a_step_by_step_count(seed):
    rng = random.Random(seed)
    spec = mini_spec()
    run = notes_ear._Run(spec, "mini")
    unit = notes_ear._Unit(spec.part("mini", "leadA"), ("leadA", 0, 0))
    unit.window_length = 8.0
    unit.notes = [dict(note, probability=1.0) for note in random_notes(rng, rng.randint(0, 12), span=4.0) if note["start"] < 8.0]
    for note in unit.notes:
        note["end"] = min(note["end"], 8.0)
    sounding = set()
    for note in unit.notes:
        for step in range(32):
            if note["start"] < (step + 1) * 0.25 - 1e-9 and note["end"] > step * 0.25 + 1e-9:
                sounding.add(step)
    assert notes_ear._rest_share(run, unit) == pytest.approx(1.0 - len(sounding) / 32.0)


def test_similarity_is_one_minus_the_normalised_edit_distance():
    assert notes_ear._edit_distance([], []) == 0
    assert notes_ear._edit_distance([1, 2, 3], [1, 2, 3]) == 0
    assert notes_ear._edit_distance([1, 2, 3], [1, 3]) == 1
    assert notes_ear._edit_distance([1, 2, 3], [4, 5, 6]) == 3
    assert notes_ear._edit_distance([], [1, 2]) == 2
    assert notes_ear._similarity([1, 2, 3], [1, 2, 3]) == 1.0
    assert notes_ear._similarity([1, 2, 3, 4], [1, 2, 3]) == pytest.approx(0.75)
    assert notes_ear._similarity([1, 2], [3, 4]) == 0.0
    assert notes_ear._similarity([], []) is None
