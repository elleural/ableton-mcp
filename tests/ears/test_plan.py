"""Unit tests for ears/plan.py: which clips to fire, which taps to record, how long, and how to cut (PRD 6.3).

The snapshot is a fake of the real NOVA set (tests/ears/nova_snapshot.py): tracks kick, perc, pad, bassA, bassB, arpA,
arpB, leadA, leadB; scenes NEON-MID (0), NEON-LOW (1), NEON-HIGH (2); kick and perc have clips in all three scenes, the
rest only in NEON-MID; returns A-Reverb and B-Delay.
"""
import copy
import json

import pytest

from ears import plan as planner
from ears import spec as specs
from ears.plan import PlanError
from tests.ears import nova_snapshot as ns

PARTS = ["kick", "perc", "pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB"]
TAIL_BEATS_AT_140 = 0.05 * 140.0 / 60.0


@pytest.fixture(scope="module")
def spec():
    return specs.load("nova")


@pytest.fixture()
def snapshot():
    return ns.nova_snapshot()


def make(spec, snapshot, **kwargs):
    kwargs.setdefault("set_name", "neon")
    return planner.plan_capture(spec, snapshot, **kwargs)


def slots_of(a_pass):
    return dict((item["track"], item["slot"]) for item in a_pass["fire"])


# ---------------------------------------------------------------------------
# tap mode
# ---------------------------------------------------------------------------


def test_tap_at_140_is_one_pass_with_everything_fired_from_slot_0(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140], mode="tap")
    assert plan["set"] == "neon" and plan["mode"] == "tap" and plan["tempos"] == [140.0] and plan["variations"] == ["A", "B"]
    assert len(plan["passes"]) == 1 and plan["warnings"] == []
    a_pass = plan["passes"][0]
    assert a_pass["label"] == "140 BPM A+B tap" and a_pass["tempo"] == 140.0 and a_pass["variations"] == ["A", "B"]
    assert [item["track"] for item in a_pass["fire"]] == PARTS
    assert slots_of(a_pass) == dict((track, 0) for track in PARTS)
    assert a_pass["solo"] is None and a_pass["mute_others"] is True


def test_tap_records_every_part_every_return_and_the_mix(spec, snapshot):
    a_pass = make(spec, snapshot, tempos=[140])["passes"][0]
    record = a_pass["record"]
    assert [item["key"] for item in record] == PARTS + ["A-Reverb", "B-Delay", "mix"]
    assert len(record) == 9 + 2 + 1
    for item in record[:9]:
        assert item == {"key": item["key"], "source": item["key"], "tap": "Post Mixer"}
    assert record[9] == {"key": "A-Reverb", "source": "A-Reverb", "tap": "Post Mixer"}
    assert record[10] == {"key": "B-Delay", "source": "B-Delay", "tap": "Post Mixer"}
    assert record[11] == {"key": "mix", "source": "resampling"}


def test_tap_pass_length_is_two_cycles_of_the_longest_loop_plus_the_tail(spec, snapshot):
    a_pass = make(spec, snapshot, tempos=[140])["passes"][0]
    assert a_pass["cycle_bars"] == 16
    assert a_pass["beats"] == pytest.approx(2 * 16 * 4 + TAIL_BEATS_AT_140, abs=1e-3)
    other = make(spec, snapshot, tempos=[100])["passes"][0]
    assert other["beats"] == pytest.approx(2 * 16 * 4 + 0.05 * 100.0 / 60.0, abs=1e-3)       # the tail is 50 ms, so more beats at a faster tempo


def test_tap_cuts_keep_the_second_cycle_and_name_their_files(spec, snapshot):
    a_pass = make(spec, snapshot, tempos=[140])["passes"][0]
    cuts = dict((cut["key"], cut) for cut in a_pass["cuts"])
    assert len(a_pass["cuts"]) == 12 and list(cuts) == PARTS + ["A-Reverb", "B-Delay", "mix"]
    bars = {"kick": 2, "perc": 4, "pad": 16, "bassA": 8, "bassB": 8, "arpA": 8, "arpB": 8, "leadA": 8, "leadB": 8}
    for part_id, bar_count in bars.items():
        cut = cuts[part_id]
        assert cut["kind"] == "part" and cut["name"] == part_id and cut["bars"] == bar_count and cut["track"] == part_id
        assert cut["start_beats"] == 64.0                                               # the second cycle of 16 bars
        assert cut["length_beats"] == bar_count * 4.0                                   # the part's own loop length
        assert cut["file"] == "stems/{0}.wav".format(part_id)
    assert cuts["A-Reverb"] == {"key": "A-Reverb", "kind": "return", "name": "A-Reverb", "start_beats": 64.0, "length_beats": 64.0,
                                "file": "returns/A-Reverb.wav"}
    assert cuts["B-Delay"]["file"] == "returns/B-Delay.wav"
    assert cuts["mix"] == {"key": "mix", "kind": "mix", "name": "mix", "start_beats": 64.0, "length_beats": 64.0, "file": "mix.wav"}


def test_one_take_per_tempo_describes_the_band_and_where_each_clip_came_from(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140])
    assert len(plan["takes"]) == 1
    take = plan["takes"][0]
    assert take["set"] == "neon" and take["tempo"] == 140.0 and take["variation"] == "AB" and take["variations"] == ["A", "B"]
    assert take["mode"] == "tap" and take["bars"] is None and take["band"] == "MID" and take["passes"] == [0] and take["parts"] == PARTS
    assert take["clips"]["bassB"] == {"track": "bassB", "slot": 0, "scene": "NEON-MID"}
    assert take["clips"]["kick"] == {"track": "kick", "slot": 0, "scene": "NEON-MID"}


@pytest.mark.parametrize("tempo, band, scene, slot", [
    (100, "LOW", "NEON-LOW", 1), (110, "LOW", "NEON-LOW", 1), (120, "LOW", "NEON-LOW", 1),
    (130, "MID", "NEON-MID", 0), (140, "MID", "NEON-MID", 0), (150, "MID", "NEON-MID", 0),
    (160, "HIGH", "NEON-HIGH", 2), (170, "HIGH", "NEON-HIGH", 2), (180, "HIGH", "NEON-HIGH", 2),
])
def test_the_drums_come_from_the_tempo_bands_scene_and_the_rest_from_the_default(spec, snapshot, tempo, band, scene, slot):
    plan = make(spec, snapshot, tempos=[tempo])
    a_pass, take = plan["passes"][0], plan["takes"][0]
    assert take["band"] == band
    assert slots_of(a_pass)["kick"] == slot and slots_of(a_pass)["perc"] == slot           # per-band clips
    for track in ("pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB"):
        assert slots_of(a_pass)[track] == 0                                                 # the MID row holds the other stems
    assert take["clips"]["kick"]["scene"] == scene and take["clips"]["pad"]["scene"] == "NEON-MID"


def test_a_band_scene_without_a_clip_falls_back_to_the_default_scene(spec):
    snapshot = ns.nova_snapshot(slots={"kick": [0], "perc": [0, 2]})                          # no kick in LOW, perc only in MID and HIGH
    plan = make(spec, snapshot, tempos=[100])
    assert slots_of(plan["passes"][0])["kick"] == 0 and slots_of(plan["passes"][0])["perc"] == 0
    assert plan["warnings"] == []


def test_default_tempo_is_the_middle_one_and_scalars_and_tuples_work(spec, snapshot):
    assert make(spec, snapshot)["tempos"] == [140.0]
    assert make(spec, snapshot, tempos=None)["tempos"] == [140.0] and make(spec, snapshot, tempos=[])["tempos"] == [140.0]
    assert make(spec, snapshot, tempos=150)["tempos"] == [150.0]
    assert make(spec, snapshot, tempos=(130, 150))["tempos"] == [130.0, 150.0]
    assert make(spec, snapshot, set_name=None)["set"] == "neon"
    assert make(spec, snapshot, set_name="NEON")["set"] == "neon"


def test_tempos_all_makes_one_take_per_tempo_of_the_set(spec, snapshot):
    plan = make(spec, snapshot, tempos="all")
    assert plan["tempos"] == [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0]
    assert len(plan["takes"]) == 9 and len(plan["passes"]) == 9
    assert [take["tempo"] for take in plan["takes"]] == plan["tempos"]
    assert [take["band"] for take in plan["takes"]] == ["LOW"] * 3 + ["MID"] * 3 + ["HIGH"] * 3
    assert [take["passes"] for take in plan["takes"]] == [[index] for index in range(9)]
    assert make(spec, snapshot, tempos=" ALL ")["tempos"] == plan["tempos"]


def test_bars_shortens_every_pass_and_cut(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140], bars=4)
    a_pass = plan["passes"][0]
    assert a_pass["cycle_bars"] == 4 and a_pass["beats"] == pytest.approx(2 * 4 * 4 + TAIL_BEATS_AT_140, abs=1e-3)
    cuts = dict((cut["key"], cut) for cut in a_pass["cuts"])
    assert cuts["kick"]["start_beats"] == 16.0 and cuts["kick"]["length_beats"] == 8.0        # the kick loop is 2 bars: shorter than the cycle
    assert cuts["perc"]["length_beats"] == 16.0 and cuts["pad"]["length_beats"] == 16.0       # everything else is cut to the 4-bar cycle
    assert cuts["mix"]["start_beats"] == 16.0 and cuts["mix"]["length_beats"] == 16.0
    assert plan["takes"][0]["bars"] == 4
    assert make(spec, snapshot, tempos=[140], bars="3")["passes"][0]["cycle_bars"] == 3


def test_tempo_that_is_not_in_the_set_is_a_warning_when_a_band_covers_it(spec, snapshot):
    plan = make(spec, snapshot, tempos=[135])
    assert plan["warnings"] == ["Tempo 135 is not one of the set's tempos (100, 110, 120, 130, 140, 150, 160, 170, 180)"]
    assert plan["takes"][0]["band"] == "MID" and plan["passes"][0]["tempo"] == 135.0


@pytest.mark.parametrize("tempo", [125, 99, 190])
def test_tempo_outside_every_band_is_a_plan_error(spec, snapshot, tempo):
    with pytest.raises(PlanError, match="in no band of set 'neon'"):
        make(spec, snapshot, tempos=[tempo])


def test_a_variation_limits_the_parts_the_passes_and_the_take(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140], variation="A")
    a_pass, take = plan["passes"][0], plan["takes"][0]
    assert plan["variations"] == ["A"] and take["variation"] == "A" and take["variations"] == ["A"]
    assert take["parts"] == ["kick", "perc", "pad", "bassA", "arpA", "leadA"]
    assert a_pass["label"] == "140 BPM A tap" and [item["track"] for item in a_pass["fire"]] == take["parts"]
    assert plan["passes"][0]["cycle_bars"] == 16                                               # the shared pad is still 16 bars
    b_only = make(spec, snapshot, tempos=[140], variation="B")
    assert b_only["takes"][0]["parts"] == ["kick", "perc", "pad", "bassB", "arpB", "leadB"]
    for everything in (None, "", "all", "AB"):
        assert make(spec, snapshot, tempos=[140], variation=everything)["takes"][0]["variation"] == "AB"


def test_unknown_variation_is_a_plan_error(spec, snapshot):
    with pytest.raises(PlanError, match=r"has variations A, B, not 'Z'"):
        make(spec, snapshot, tempos=[140], variation="Z")


def test_bad_mode_and_bad_tempos_are_plan_errors(spec, snapshot):
    with pytest.raises(PlanError, match="mode must be 'tap' or 'solo'"):
        make(spec, snapshot, mode="stems")
    with pytest.raises(PlanError, match="tempos must be a list of BPM or 'all'"):
        make(spec, snapshot, tempos="some")


def test_unknown_set_is_a_spec_error(spec, snapshot):
    with pytest.raises(specs.SpecError, match="no set 'tetris'"):
        make(spec, snapshot, set_name="tetris")


# ---------------------------------------------------------------------------
# sends: one pass per variation
# ---------------------------------------------------------------------------


def test_sends_in_use_on_a_track_make_one_pass_per_variation_and_a_warning(spec):
    snapshot = ns.nova_snapshot(sends={"bassA": {"A": -12.0, "B": None}})
    plan = make(spec, snapshot, tempos=[140], mode="tap")
    assert plan["warnings"] == ["bassA send to returns; tap stems lack those effects, so tier sums are approximate (use mode='solo')"]
    assert [item["label"] for item in plan["passes"]] == ["140 BPM A tap", "140 BPM B tap"]
    first, second = plan["passes"]
    assert [item["track"] for item in first["fire"]] == ["kick", "perc", "pad", "bassA", "arpA", "leadA"]
    assert [item["track"] for item in second["fire"]] == ["kick", "perc", "pad", "bassB", "arpB", "leadB"]
    assert first["variations"] == ["A"] and second["variations"] == ["B"]
    assert [item["key"] for item in first["record"]] == ["kick", "perc", "pad", "bassA", "arpA", "leadA", "A-Reverb", "B-Delay", "mix"]
    assert plan["takes"][0]["passes"] == [0, 1] and plan["takes"][0]["variation"] == "AB"
    assert plan["takes"][0]["parts"] == PARTS


def test_per_variation_passes_suffix_the_returns_and_the_mix(spec):
    snapshot = ns.nova_snapshot(sends={"leadB": {"A": None, "B": -6.0}})
    plan = make(spec, snapshot, tempos=[140])
    files_a = [cut["file"] for cut in plan["passes"][0]["cuts"]]
    files_b = [cut["file"] for cut in plan["passes"][1]["cuts"]]
    assert "returns/A-Reverb@A.wav" in files_a and "returns/B-Delay@A.wav" in files_a and "mix@A.wav" in files_a
    assert "returns/A-Reverb@B.wav" in files_b and "mix@B.wav" in files_b
    cut_names = [cut["name"] for cut in plan["passes"][1]["cuts"]]
    assert "A-Reverb@B" in cut_names and "mix@B" in cut_names and "kick" in cut_names       # shared parts keep their plain names
    assert plan["passes"][0]["beats"] == plan["passes"][1]["beats"]                          # both include the 16-bar pad


@pytest.mark.parametrize("level, in_use", [(None, False), (-70.0, False), (-60.0, False), (-59.9, True), (-12.0, True), (0.0, True)])
def test_send_threshold(spec, level, in_use):
    plan = make(spec, ns.nova_snapshot(sends={"pad": {"A": level, "B": None}}), tempos=[140])
    assert (len(plan["passes"]) == 2) is in_use and bool(plan["warnings"]) is in_use


def test_sends_in_use_helper():
    assert planner.sends_in_use({"mixer": {"sends": {"A": -60.0, "B": -59.9}}}) == ["B"]
    assert planner.sends_in_use({"mixer": {"sends": {"A": 0.0, "B": -3}}}) == ["A", "B"]
    assert planner.sends_in_use({"mixer": {"sends": {"A": None, "B": None}}}) == []
    assert planner.sends_in_use({"mixer": {"sends": {"A": "-6"}}}) == ["A"]
    assert planner.sends_in_use({}) == [] and planner.sends_in_use({"mixer": {}}) == [] and planner.sends_in_use({"mixer": None}) == []


def test_sends_only_matter_for_the_captured_variations(spec):
    snapshot = ns.nova_snapshot(sends={"bassB": {"A": -12.0, "B": None}})
    plan = make(spec, snapshot, tempos=[140], variation="A")
    assert len(plan["passes"]) == 1 and plan["warnings"] == []                              # bassB is not captured, so its send is moot


# ---------------------------------------------------------------------------
# solo mode
# ---------------------------------------------------------------------------


def test_solo_makes_one_pass_per_part_recording_only_the_mix(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140], mode="solo")
    assert len(plan["passes"]) == 9 and plan["warnings"] == []
    assert [item["label"] for item in plan["passes"]] == ["140 BPM {0} solo".format(part) for part in PARTS]
    for part, a_pass in zip(PARTS, plan["passes"]):
        assert a_pass["solo"] == [part] and a_pass["mute_others"] is False
        assert a_pass["record"] == [{"key": "mix", "source": "resampling"}]
        assert len(a_pass["cuts"]) == 1
        cut = a_pass["cuts"][0]
        assert cut["key"] == "mix" and cut["kind"] == "part" and cut["name"] == part and cut["file"] == "stems/{0}.wav".format(part)
    assert plan["takes"][0]["passes"] == list(range(9)) and plan["takes"][0]["mode"] == "solo"


def test_solo_fires_the_parts_of_the_soloed_parts_variation(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140], mode="solo")
    by_label = dict((item["label"], item) for item in plan["passes"])
    assert [f["track"] for f in by_label["140 BPM bassB solo"]["fire"]] == ["kick", "perc", "pad", "bassB", "arpB", "leadB"]
    assert [f["track"] for f in by_label["140 BPM leadA solo"]["fire"]] == ["kick", "perc", "pad", "bassA", "arpA", "leadA"]
    assert by_label["140 BPM bassB solo"]["variations"] == ["B"]
    assert [f["track"] for f in by_label["140 BPM kick solo"]["fire"]] == ["kick", "perc", "pad", "bassA", "arpA", "leadA"]   # shared stems: the first variation
    assert by_label["140 BPM kick solo"]["variations"] == ["A"]


def test_solo_pass_length_follows_the_soloed_stems_own_loop(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140], mode="solo")
    by_part = dict((item["cuts"][0]["name"], item) for item in plan["passes"])
    expected_bars = {"kick": 2, "perc": 4, "pad": 16, "bassA": 8, "leadB": 8}
    for part, bars in expected_bars.items():
        a_pass = by_part[part]
        assert a_pass["cycle_bars"] == bars
        assert a_pass["beats"] == pytest.approx(2 * bars * 4 + TAIL_BEATS_AT_140, abs=1e-3)
        cut = a_pass["cuts"][0]
        assert cut["start_beats"] == bars * 4.0 and cut["length_beats"] == bars * 4.0
    short = make(spec, snapshot, tempos=[140], mode="solo", bars=4)
    by_part = dict((item["cuts"][0]["name"], item) for item in short["passes"])
    assert by_part["pad"]["cycle_bars"] == 4 and by_part["pad"]["cuts"][0]["length_beats"] == 16.0
    assert by_part["kick"]["cuts"][0]["start_beats"] == 16.0 and by_part["kick"]["cuts"][0]["length_beats"] == 8.0


def test_solo_ignores_sends_and_mutes_nothing(spec):
    snapshot = ns.nova_snapshot(sends={"bassA": {"A": -12.0, "B": None}})
    plan = make(spec, snapshot, tempos=[140], mode="solo")
    assert plan["warnings"] == [] and all(item["mute_others"] is False for item in plan["passes"])


def test_solo_of_one_variation(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140], mode="solo", variation="B")
    assert [item["label"] for item in plan["passes"]] == ["140 BPM {0} solo".format(part) for part in
                                                           ["kick", "perc", "pad", "bassB", "arpB", "leadB"]]


# ---------------------------------------------------------------------------
# missing tracks, clips, mutes
# ---------------------------------------------------------------------------


def test_a_missing_track_is_a_warning_and_the_part_is_skipped(spec):
    plan = make(spec, ns.nova_snapshot(without=["leadB"]), tempos=[140])
    assert plan["warnings"] == ["Not captured at 140 BPM: leadB (track 'leadB' missing)"]
    assert plan["takes"][0]["parts"] == PARTS[:-1]
    assert "leadB" not in [item["track"] for item in plan["passes"][0]["fire"]]
    assert "leadB" not in [item["key"] for item in plan["passes"][0]["record"]] and "leadB" not in [cut["key"] for cut in plan["passes"][0]["cuts"]]
    assert "leadB" not in plan["takes"][0]["clips"]


def test_a_track_name_that_appears_twice_is_not_captured(spec):
    plan = make(spec, ns.nova_snapshot(duplicate=["pad"]), tempos=[140])
    assert plan["warnings"] == ["Not captured at 140 BPM: pad (track 'pad' is not unique)"]
    assert "pad" not in plan["takes"][0]["parts"]


def test_a_track_without_a_clip_in_the_scene_is_skipped(spec):
    plan = make(spec, ns.nova_snapshot(slots={"bassB": []}), tempos=[140])
    assert plan["warnings"] == ["Not captured at 140 BPM: bassB (no clip in NEON-MID on 'bassB')"]
    plan = make(spec, ns.nova_snapshot(slots={"bassB": [1]}), tempos=[140])               # a clip, but in the LOW scene only
    assert plan["warnings"] == ["Not captured at 140 BPM: bassB (no clip in NEON-MID on 'bassB')"]
    low = make(spec, ns.nova_snapshot(slots={"bassB": [1]}), tempos=[100])                 # at 100 BPM the LOW scene is searched first
    assert low["warnings"] == [] and low["takes"][0]["clips"]["bassB"] == {"track": "bassB", "slot": 1, "scene": "NEON-LOW"}


def test_missing_parts_are_judged_per_tempo(spec):
    plan = make(spec, ns.nova_snapshot(slots={"leadB": [1]}), tempos=[100, 140])
    assert plan["warnings"] == ["Not captured at 140 BPM: leadB (no clip in NEON-MID on 'leadB')"]
    assert plan["takes"][0]["parts"] == PARTS and "leadB" not in plan["takes"][1]["parts"]


def test_every_part_missing_is_a_plan_error_that_lists_why(spec):
    with pytest.raises(PlanError) as caught:
        make(spec, ns.nova_snapshot(without=PARTS), tempos=[140])
    message = str(caught.value)
    assert message.startswith("Nothing to capture at 140 BPM: ") and "kick (track 'kick' missing)" in message and "leadB (track 'leadB' missing)" in message
    with pytest.raises(PlanError, match="Nothing to capture"):
        make(spec, {}, tempos=[140])
    no_scenes = ns.nova_snapshot()
    no_scenes["scenes"] = []
    with pytest.raises(PlanError, match=r"kick \(no clip in NEON-MID on 'kick'\)"):
        make(spec, no_scenes, tempos=[140])


def test_one_missing_part_does_not_stop_the_plan(spec):
    plan = make(spec, ns.nova_snapshot(without=["kick"]), tempos=[140])
    assert plan["takes"][0]["parts"] == PARTS[1:] and len(plan["warnings"]) == 1                # only a warning
    assert plan["passes"][0]["cycle_bars"] == 16


def test_muted_part_tracks_are_warned_about(spec):
    plan = make(spec, ns.nova_snapshot(muted=["kick", "pad"]), tempos=[140])
    assert plan["warnings"] == ["Muted part tracks record silence: kick, pad"]
    assert len(plan["passes"]) == 1 and plan["takes"][0]["parts"] == PARTS


def test_warnings_accumulate_in_a_sensible_order(spec):
    snapshot = ns.nova_snapshot(without=["leadB"], muted=["kick"], sends={"bassA": {"A": -12.0, "B": None}})
    plan = make(spec, snapshot, tempos=[135])
    assert [warning.split(" ")[0] for warning in plan["warnings"]] == ["Tempo", "Not", "Muted", "bassA"]


# ---------------------------------------------------------------------------
# MAINFRAME and the clip layout
# ---------------------------------------------------------------------------


def test_mainframe_uses_its_prefixed_tracks_and_scenes(spec):
    snapshot = ns.nova_snapshot(prefix="mf_", scenes=ns.MAINFRAME_SCENES)
    low = make(spec, snapshot, set_name="mainframe", tempos=[100])
    assert low["takes"][0]["band"] == "LOW" and low["takes"][0]["set"] == "mainframe"
    assert [item["track"] for item in low["passes"][0]["fire"]][:4] == ["mf_kick", "mf_perc", "mf_pad", "mf_bassA"]
    assert slots_of(low["passes"][0])["mf_kick"] == 1 and slots_of(low["passes"][0])["mf_pad"] == 0
    assert low["passes"][0]["label"] == "100 BPM A+B tap"
    mid = make(spec, snapshot, set_name="mainframe", tempos=[130])
    assert mid["takes"][0]["band"] == "MID" and slots_of(mid["passes"][0])["mf_kick"] == 0
    assert make(spec, snapshot, set_name="mainframe")["tempos"] == [120.0]                  # the middle tempo of 100..130


def test_neon_tracks_are_not_found_in_a_mainframe_snapshot(spec):
    with pytest.raises(PlanError, match=r"Nothing to capture at 120 BPM: kick \(track 'mf_kick' missing\)"):
        make(spec, ns.nova_snapshot(), set_name="mainframe")


@pytest.fixture(scope="module")
def clip_spec():
    return specs.Spec(ns.clip_layout_data())


def test_clip_layout_fires_the_clip_named_after_the_variation(clip_spec):
    snapshot = ns.clip_layout_snapshot()
    low = planner.plan_capture(clip_spec, snapshot, "demo", tempos=[110])
    assert [item["label"] for item in low["passes"]] == ["110 BPM A tap", "110 BPM B tap"]       # one track: always one pass per variation
    assert low["passes"][0]["fire"] == [{"track": "kick", "slot": 0}, {"track": "bass", "slot": 0}]
    assert low["passes"][1]["fire"] == [{"track": "kick", "slot": 0}, {"track": "bass", "slot": 2}]
    assert [item["key"] for item in low["passes"][0]["record"]] == ["kick", "bassA", "A-Reverb", "mix"]
    assert low["passes"][0]["record"][1] == {"key": "bassA", "source": "bass", "tap": "Post Mixer"}
    assert low["passes"][1]["record"][1] == {"key": "bassB", "source": "bass", "tap": "Post Mixer"}
    assert low["takes"][0]["clips"]["bassB"] == {"track": "bass", "slot": 2, "scene": "S-ALT"}
    assert low["warnings"] == []


def test_clip_layout_prefers_the_bands_scene_among_clips_with_the_same_name(clip_spec):
    high = planner.plan_capture(clip_spec, ns.clip_layout_snapshot(), "demo", tempos=[135])
    assert high["takes"][0]["band"] == "HIGH"
    assert high["takes"][0]["clips"]["bassA"] == {"track": "bass", "slot": 1, "scene": "S-HIGH"}      # A exists in LOW and HIGH
    assert high["takes"][0]["clips"]["bassB"]["slot"] == 2 and high["takes"][0]["clips"]["kick"]["slot"] == 1


def test_clip_layout_solo_solos_the_shared_track(clip_spec):
    plan = planner.plan_capture(clip_spec, ns.clip_layout_snapshot(), "demo", tempos=[135], mode="solo")
    assert [(item["label"], item["solo"]) for item in plan["passes"]] == [
        ("135 BPM kick solo", ["kick"]), ("135 BPM bassA solo", ["bass"]), ("135 BPM bassB solo", ["bass"])]
    assert [f["slot"] for f in plan["passes"][2]["fire"] if f["track"] == "bass"] == [2]


def test_find_clip_by_name_and_by_scene(clip_spec):
    snapshot = ns.clip_layout_snapshot()
    track = [item for item in snapshot["tracks"] if item["name"] == "bass"][0]
    slots = dict((scene["name"], scene["index"]) for scene in snapshot["scenes"])
    band_high = clip_spec.band("demo", 135)
    band_low = clip_spec.band("demo", 110)
    part_a, part_b = clip_spec.part("demo", "bassA"), clip_spec.part("demo", "bassB")
    assert planner.find_clip(clip_spec, "demo", part_a, track, band_high, slots)[:2] == (1, "S-HIGH")
    assert planner.find_clip(clip_spec, "demo", part_a, track, band_low, slots)[:2] == (0, "S-LOW")
    slot, scene, found = planner.find_clip(clip_spec, "demo", part_b, track, band_low, slots)        # B is not in the band's scene
    assert (slot, scene, found["name"]) == (2, "S-ALT", "B")
    assert planner.find_clip(clip_spec, "demo", part_b, {"clips": [track["clips"][0]]}, band_low, slots) == (None, None, None)   # no clip B at all
    assert planner.find_clip(clip_spec, "demo", part_a, {"name": "bass"}, band_low, slots) == (None, None, None)                  # no clips key


def test_find_clip_by_scene_for_the_track_layout(spec):
    snapshot = ns.nova_snapshot()
    kick = [item for item in snapshot["tracks"] if item["name"] == "kick"][0]
    slots = dict((scene["name"], scene["index"]) for scene in snapshot["scenes"])
    part = spec.part("neon", "kick")
    assert planner.find_clip(spec, "neon", part, kick, spec.band("neon", 100), slots)[:2] == (1, "NEON-LOW")
    assert planner.find_clip(spec, "neon", part, kick, spec.band("neon", 140), slots)[:2] == (0, "NEON-MID")
    assert planner.find_clip(spec, "neon", part, kick, None, slots)[:2] == (0, "NEON-MID")
    assert planner.find_clip(spec, "neon", part, kick, spec.band("neon", 140), {}) == (None, None, None)     # scene names unknown


# ---------------------------------------------------------------------------
# totals and engine_passes
# ---------------------------------------------------------------------------


def test_seconds_adds_each_pass_plus_a_second_and_a_half_of_overhead(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140])
    assert plan["seconds"] == pytest.approx(plan["passes"][0]["beats"] * 60.0 / 140.0 + 1.5, abs=0.1)
    plan = make(spec, snapshot, tempos="all")
    expected = sum(item["beats"] * 60.0 / item["tempo"] + 1.5 for item in plan["passes"])
    assert plan["seconds"] == pytest.approx(expected, abs=0.1)
    solo = make(spec, snapshot, tempos=[140], mode="solo")
    assert 240 < solo["seconds"] < 270                                                        # PRD 12: about 4 minutes of stems at 140 BPM


def test_tap_with_both_variations_in_one_pass_is_faster_than_per_variation(spec):
    one = make(spec, ns.nova_snapshot(), tempos=[140])["seconds"]
    two = make(spec, ns.nova_snapshot(sends={"pad": {"A": -6.0, "B": None}}), tempos=[140])["seconds"]
    assert two == pytest.approx(2 * one, abs=1.0)


def test_engine_passes_drops_the_cut_windows(spec, snapshot):
    plan = make(spec, snapshot, tempos=[140, 100], mode="tap")
    engine = planner.engine_passes(plan)
    assert len(engine) == 2
    for original, trimmed in zip(plan["passes"], engine):
        assert set(trimmed) == {"label", "tempo", "fire", "record", "solo", "mute_others", "beats"}
        for key in trimmed:
            assert trimmed[key] == original[key]
        assert "cuts" not in trimmed and "cycle_bars" not in trimmed and "variations" not in trimmed
    assert "cuts" in plan["passes"][0]                                                         # the plan itself keeps them


def test_the_plan_is_plain_json(spec, snapshot):
    for mode in ("tap", "solo"):
        plan = make(spec, snapshot, tempos="all", mode=mode)
        assert json.loads(json.dumps(plan, allow_nan=False)) == plan
    assert planner.engine_passes(make(spec, snapshot))[0]["beats"] == pytest.approx(128.117, abs=1e-3)


SCENARIOS = [
    dict(tempos=[140], mode="tap"), dict(tempos="all", mode="tap"), dict(tempos=[100, 180], mode="solo"), dict(tempos=[120], mode="tap", bars=4),
    dict(tempos=[160], mode="solo", bars=2), dict(tempos=[140], mode="tap", variation="B"), dict(tempos=[110, 150], mode="tap", sends=True),
    dict(tempos=[170], mode="solo", variation="A", sends=True), dict(tempos=[130], mode="tap", bars=1),
]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: "-".join(str(value) for value in scenario.values()))
def test_every_plan_is_self_consistent(spec, scenario):
    scenario = dict(scenario)
    snapshot = ns.nova_snapshot(sends={"leadA": {"A": -6.0, "B": None}} if scenario.pop("sends", False) else None)
    plan = make(spec, snapshot, **scenario)
    tracks = dict((track["name"], track) for track in snapshot["tracks"])
    assert [index for take in plan["takes"] for index in take["passes"]] == list(range(len(plan["passes"])))        # takes partition the passes
    assert len(set(item["label"] for item in plan["passes"])) == len(plan["passes"])
    for take in plan["takes"]:
        tail_beats = 0.05 * take["tempo"] / 60.0
        recorded_parts = set()
        for index in take["passes"]:
            item = plan["passes"][index]
            keys = [entry["key"] for entry in item["record"]]
            assert item["tempo"] == take["tempo"] and len(set(keys)) == len(keys) and keys[-1] == "mix" or item["solo"]
            for fired in item["fire"]:
                assert any(clip["slot"] == fired["slot"] for clip in tracks[fired["track"]]["clips"])         # only clips that exist
            for cut in item["cuts"]:
                assert cut["key"] in keys
                assert cut["start_beats"] + cut["length_beats"] + tail_beats <= item["beats"] + 1e-3              # the recording holds the cut and its tail (beats are rounded to 3 places)
                assert cut["start_beats"] == item["cycle_bars"] * 4.0 and 0 < cut["length_beats"] <= item["cycle_bars"] * 4.0
                if cut["kind"] == "part":
                    recorded_parts.add(cut["name"])
                    assert cut["length_beats"] <= cut["bars"] * 4.0
                    if not scenario.get("bars"):
                        assert cut["start_beats"] % (cut["bars"] * 4.0) == 0                                   # the kept cycle starts on the part's loop start
        assert recorded_parts == set(take["parts"])                                                            # every part of the take is cut once or more
    assert plan["seconds"] > 0 and len(planner.engine_passes(plan)) == len(plan["passes"])


def test_planning_does_not_change_the_snapshot_or_the_spec(spec, snapshot):
    before_snapshot, before_spec = copy.deepcopy(snapshot), copy.deepcopy(spec.data)
    make(spec, snapshot, tempos="all", mode="solo")
    make(spec, snapshot, tempos=[140], mode="tap")
    assert snapshot == before_snapshot and spec.data == before_spec
