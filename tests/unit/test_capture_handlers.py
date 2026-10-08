"""Unit tests for the pure helpers of the Session capture engine (handlers/capture.py): validate_passes, wanted_states,
pass_seconds, mismatched and capture_track_name. They need neither Live nor a socket.

The planner in the `ears` package produces the passes these helpers receive, so a few tests feed them real plans.
"""
import math

import pytest

from AbletonMCP_Remote_Script.errors import CommandError
from AbletonMCP_Remote_Script.handlers import capture
from ears import plan as planner
from ears import spec as specs
from tests.ears import nova_snapshot as ns


def tap_pass(**changes):
    item = {"label": "140 BPM A+B tap", "tempo": 140.0,
            "fire": [{"track": "kick", "slot": 0}, {"track": "bassA", "slot": 0}],
            "record": [{"key": "kick", "source": "kick", "tap": "Post Mixer"}, {"key": "bassA", "source": "bassA", "tap": "Post Mixer"},
                       {"key": "mix", "source": "resampling"}],
            "solo": None, "mute_others": True, "beats": 128.0}
    item.update(changes)
    return item


def error_of(passes):
    with pytest.raises(CommandError) as caught:
        capture.validate_passes(passes)
    assert caught.value.code == "invalid_argument"
    return caught.value.message


# ---------------------------------------------------------------------------
# capture_track_name
# ---------------------------------------------------------------------------


def test_capture_track_names_carry_the_cap_prefix():
    assert capture.PREFIX == "cap:"
    assert capture.capture_track_name("kick") == "cap:kick" and capture.capture_track_name("mix") == "cap:mix"
    assert capture.capture_track_name("A-Reverb") == "cap:A-Reverb" and capture.capture_track_name(3) == "cap:3"
    assert capture.capture_track_name("") == "cap:"


# ---------------------------------------------------------------------------
# validate_passes: normalisation
# ---------------------------------------------------------------------------


def test_a_planned_tap_pass_comes_back_normalised():
    [item] = capture.validate_passes([tap_pass()])
    assert item == {
        "label": "140 BPM A+B tap", "tempo": 140.0,
        "fire": [{"track": "kick", "slot": 0}, {"track": "bassA", "slot": 0}],
        "record": [{"key": "kick", "source": "kick", "tap": "Post Mixer"}, {"key": "bassA", "source": "bassA", "tap": "Post Mixer"},
                   {"key": "mix", "source": "resampling", "tap": "Post Mixer"}],
        "solo": None, "mute_others": True, "beats": 128.0}


def test_defaults_labels_taps_and_mute_others():
    plain = {"fire": [{"track": "kick", "slot": 2}], "record": [{"key": "mix", "source": "resampling"}], "beats": 8}
    first, second = capture.validate_passes([plain, dict(plain, label="")])
    assert first["label"] == "pass 1" and second["label"] == "pass 2"                                   # numbered from 1
    assert first["tempo"] is None and first["solo"] is None and first["mute_others"] is True and first["beats"] == 8.0
    assert first["record"] == [{"key": "mix", "source": "resampling", "tap": "Post Mixer"}]
    solo = capture.validate_passes([dict(plain, solo=["kick"])])[0]
    assert solo["solo"] == ["kick"] and solo["mute_others"] is False                                    # a solo pass mutes nobody by default
    assert capture.validate_passes([dict(plain, solo=["kick"], mute_others=True)])[0]["mute_others"] is True
    assert capture.validate_passes([dict(plain, mute_others=False)])[0]["mute_others"] is False
    assert capture.validate_passes([dict(plain, solo=[])])[0]["solo"] is None and capture.validate_passes([dict(plain, solo=[])])[0]["mute_others"] is True


def test_values_are_coerced_to_their_types():
    item = capture.validate_passes([{"label": 7, "tempo": "128", "beats": "16.5", "fire": [{"track": 5, "slot": "3"}],
                                     "record": [{"key": 9, "source": 2}], "solo": [5, "kick"]}])[0]
    assert item["label"] == "7" and item["tempo"] == 128.0 and item["beats"] == 16.5
    assert item["fire"] == [{"track": "5", "slot": 3}] and item["record"] == [{"key": "9", "source": "2", "tap": "Post Mixer"}]
    assert item["solo"] == ["5", "kick"]


@pytest.mark.parametrize("tap", ["Pre FX", "Post FX", "Post Mixer"])
def test_every_known_tap_is_accepted(tap):
    item = tap_pass(record=[{"key": "kick", "source": "kick", "tap": tap}])
    assert capture.validate_passes([item])[0]["record"][0]["tap"] == tap


def test_keys_and_sources_are_stripped():
    item = capture.validate_passes([tap_pass(record=[{"key": "  kick ", "source": " kick  "}])])[0]
    assert item["record"] == [{"key": "kick", "source": "kick", "tap": "Post Mixer"}]


def test_the_inputs_are_not_changed():
    original = tap_pass()
    import copy
    before = copy.deepcopy(original)
    capture.validate_passes([original])
    assert original == before


def test_tuples_and_several_passes_are_accepted_in_order():
    passes = (tap_pass(label="first"), tap_pass(label="second", tempo=None), tap_pass(label="third", tempo=20, beats=0.25))
    out = capture.validate_passes(passes)
    assert [item["label"] for item in out] == ["first", "second", "third"] and out[1]["tempo"] is None
    assert out[2]["tempo"] == 20.0 and out[2]["beats"] == 0.25
    assert capture.validate_passes([tap_pass(tempo=999)])[0]["tempo"] == 999.0


@pytest.mark.parametrize("mode", ["tap", "solo"])
@pytest.mark.parametrize("sends", [False, True])
def test_real_plans_from_the_planner_validate_cleanly(mode, sends):
    spec = specs.load("nova")
    snapshot = ns.nova_snapshot(sends={"bassA": {"A": -12.0, "B": None}} if sends else None)
    plan = planner.plan_capture(spec, snapshot, "neon", tempos=[100, 140, 180], mode=mode)
    engine = planner.engine_passes(plan)
    out = capture.validate_passes(engine)
    assert len(out) == len(engine) and all(item["record"] and item["fire"] and item["beats"] > 0 for item in out)
    for given, normalised in zip(engine, out):
        assert normalised["label"] == given["label"] and normalised["tempo"] == given["tempo"] and normalised["beats"] == pytest.approx(given["beats"])
        assert normalised["solo"] == given["solo"] and normalised["mute_others"] == given["mute_others"]
        assert [(e["key"], e["source"]) for e in normalised["record"]] == [(e["key"], e["source"]) for e in given["record"]]
        assert [e["tap"] for e in normalised["record"] if e["source"] != "resampling"] == ["Post Mixer"] * sum(e["source"] != "resampling" for e in given["record"])


# ---------------------------------------------------------------------------
# validate_passes: every error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("passes", [None, [], (), "pass", {"fire": []}, 5, ""])
def test_passes_must_be_a_non_empty_list(passes):
    assert error_of(passes) == "passes must be a non-empty list"


@pytest.mark.parametrize("item", [None, "tap", 3, ["fire"]])
def test_every_pass_must_be_an_object(item):
    assert error_of([item]) == "pass 0 must be an object"
    assert error_of([tap_pass(), item]) == "pass 1 must be an object"                                   # the message numbers the pass


def test_a_pass_that_fires_nothing_is_an_error():
    for fire in (None, [], ()):
        assert error_of([tap_pass(fire=fire)]) == "pass 0 fires no clips"
    assert error_of([tap_pass(), tap_pass(fire=[])]) == "pass 1 fires no clips"
    item = tap_pass()
    del item["fire"]
    assert error_of([item]) == "pass 0 fires no clips"


def test_a_pass_that_records_nothing_is_an_error():
    for record in (None, [], ()):
        assert error_of([tap_pass(record=record)]) == "pass 0 records nothing"
    assert error_of([tap_pass(), tap_pass(record=[])]) == "pass 1 records nothing"
    assert error_of([tap_pass(fire=[], record=[])]) == "pass 0 fires no clips"                         # the first problem is the one named


def test_beats_are_required():
    assert error_of([tap_pass(beats=None)]) == "pass 0 needs beats (how long to record)"
    item = tap_pass()
    del item["beats"]
    assert error_of([item]) == "pass 0 needs beats (how long to record)"


@pytest.mark.parametrize("beats", ["abc", "", [], {}, "4 beats"])
def test_beats_must_be_a_number(beats):
    assert error_of([tap_pass(beats=beats)]).startswith("pass 0 beats must be a number")


@pytest.mark.parametrize("beats", [0, 0.0, -1, "-4", -0.001])
def test_beats_must_be_positive(beats):
    assert error_of([tap_pass(beats=beats)]) == "pass 0 beats must be positive"


@pytest.mark.parametrize("tempo", [0, 19.99, 5, -120, 999.01, 1000])
def test_a_tempo_outside_20_to_999_is_an_error(tempo):
    assert error_of([tap_pass(tempo=tempo)]) == "pass 0 tempo must be 20..999 BPM"


@pytest.mark.parametrize("tempo", [float("nan"), float("inf"), float("-inf")])
def test_a_tempo_that_is_not_finite_is_an_error(tempo):
    assert error_of([tap_pass(tempo=tempo)]).startswith("pass 0 tempo must be finite")


@pytest.mark.parametrize("entry, message", [
    ({"key": "", "source": "kick"}, "pass 0 record entries need key and source"),
    ({"key": "kick", "source": ""}, "pass 0 record entries need key and source"),
    ({"key": "kick"}, "pass 0 record entries need key and source"),
    ({"source": "kick"}, "pass 0 record entries need key and source"),
    ({"key": "  ", "source": "kick"}, "pass 0 record entries need key and source"),
    ({"key": None, "source": None}, "pass 0 record entries need key and source"),
    ({}, "pass 0 record entries need key and source"),
])
def test_record_entries_need_a_key_and_a_source(entry, message):
    assert error_of([tap_pass(record=[entry])]) == message


@pytest.mark.parametrize("tap", ["Post Fader", "post mixer", "Resampling", "Pre", "mix"])
def test_an_unknown_tap_is_an_error_that_lists_the_known_ones(tap):
    assert error_of([tap_pass(record=[{"key": "kick", "source": "kick", "tap": tap}])]) == "pass 0: tap must be one of Pre FX, Post FX, Post Mixer"


def test_the_same_key_twice_in_one_pass_is_an_error():
    record = [{"key": "kick", "source": "kick"}, {"key": "bass", "source": "bass"}, {"key": "kick", "source": "kick"}]
    assert error_of([tap_pass(record=record)]) == "pass 0 records key 'kick' twice"
    assert error_of([tap_pass(), tap_pass(record=record)]) == "pass 1 records key 'kick' twice"
    ok = capture.validate_passes([tap_pass(), tap_pass()])                                              # the same key in different passes is fine
    assert [item["record"][0]["key"] for item in ok] == ["kick", "kick"]


def test_the_first_problem_in_order_is_the_one_reported():
    broken = tap_pass(beats=-1, tempo=5, record=[{"key": "a", "source": "a"}, {"key": "a", "source": "a"}])
    assert error_of([broken]) == "pass 0 beats must be positive"
    assert error_of([tap_pass(tempo=5, record=[{"key": "a", "source": "a"}, {"key": "a", "source": "a"}])]) == "pass 0 tempo must be 20..999 BPM"


@pytest.mark.parametrize("tempo", ["fast", "120bpm", [140]])
def test_a_tempo_that_is_not_a_number_is_a_command_error(tempo):
    assert error_of([tap_pass(tempo=tempo)]).startswith("pass 0 tempo must be a number")


@pytest.mark.parametrize("changes", [
    {"record": ["kick"]},
    {"record": [None]},
    {"fire": [{"track": "kick"}]},
    {"fire": [{"slot": 0}]},
    {"fire": ["kick"]},
    {"fire": [{"track": "kick", "slot": "first"}]},
    {"fire": [{"track": "kick", "slot": None}]},
])
def test_malformed_fire_and_record_entries_are_command_errors(changes):
    with pytest.raises(CommandError) as caught:
        capture.validate_passes([tap_pass(**changes)])
    assert caught.value.code == "invalid_argument" and "pass 0" in caught.value.message


@pytest.mark.parametrize("slot", [-1, 1.5, "1.5", "-2"])
def test_a_slot_must_be_a_whole_scene_index(slot):
    assert error_of([tap_pass(fire=[{"track": "kick", "slot": slot}])]) == "pass 0 slot must be a scene index (0 or more)"
    assert capture.validate_passes([tap_pass(fire=[{"track": "kick", "slot": "2"}, {"track": "pad", "slot": 2.0}])])[0]["fire"] == [
        {"track": "kick", "slot": 2}, {"track": "pad", "slot": 2}]


@pytest.mark.parametrize("fire", [[{"track": "kick"}], [{"slot": 0}], ["kick"], [None], "kick"])
def test_fire_entries_need_a_track_and_a_slot(fire):
    assert "pass 0" in error_of([tap_pass(fire=fire)])


@pytest.mark.parametrize("solo", ["kick", 5, {"kick": 1}])
def test_solo_must_be_a_list_of_track_names(solo):
    assert error_of([tap_pass(solo=solo)]) == "pass 0 solo must be a list of track names"


@pytest.mark.parametrize("beats", [float("inf"), float("nan")])
def test_beats_must_be_finite(beats):
    with pytest.raises(CommandError):
        capture.validate_passes([tap_pass(beats=beats)])


# ---------------------------------------------------------------------------
# pass_seconds
# ---------------------------------------------------------------------------


def test_pass_seconds_is_the_beats_at_the_tempo_plus_the_stop_margin():
    assert capture.STOP_MARGIN_SECONDS == 0.5
    [item] = capture.validate_passes([tap_pass(beats=128.0, tempo=140.0)])
    assert capture.pass_seconds(item, 120.0) == pytest.approx(128 * 60.0 / 140.0 + 0.5)                  # the pass's own tempo wins
    [no_tempo] = capture.validate_passes([tap_pass(beats=64.0, tempo=None)])
    assert capture.pass_seconds(no_tempo, 120.0) == pytest.approx(64 * 60.0 / 120.0 + 0.5)               # otherwise the song's
    assert capture.pass_seconds(no_tempo, "90") == pytest.approx(64 * 60.0 / 90.0 + 0.5)
    assert capture.pass_seconds({"tempo": 60.0, "beats": 1.0}, 999) == pytest.approx(1.5)


def test_pass_seconds_of_the_prds_examples():
    """PRD 12: a tap pass of 32 bars takes 55 s at 140 BPM and 77 s at 100 BPM, a solo pad pass about the same."""
    thirty_two_bars = 32 * 4.0
    assert capture.pass_seconds({"tempo": 140.0, "beats": thirty_two_bars}, 0) - 0.5 == pytest.approx(54.857, abs=0.01)
    assert capture.pass_seconds({"tempo": 100.0, "beats": thirty_two_bars}, 0) - 0.5 == pytest.approx(76.8, abs=0.01)
    assert capture.pass_seconds({"tempo": 180.0, "beats": thirty_two_bars}, 0) - 0.5 == pytest.approx(42.667, abs=0.01)


def test_the_capture_length_limit_is_an_hour():
    assert capture.MAX_SECONDS == 3600.0
    spec = specs.load("nova")
    plan = planner.plan_capture(spec, ns.nova_snapshot(), "neon", tempos="all", mode="solo")
    total = sum(capture.pass_seconds(item, 140.0) for item in capture.validate_passes(planner.engine_passes(plan)))
    assert 24 * 60 < total < 40 * 60 < capture.MAX_SECONDS                                               # every NEON tempo in solo mode: about 25 minutes


# ---------------------------------------------------------------------------
# mismatched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("expected, actual, result", [
    (120.0, 120.0, False), (120.0, 120.0005, False), (120.0, 120.002, True), (120, 119.9995, False), (120, 119.998, True), (120, 119.99, True),
    (4, 4.0, False), (0, 0.0005, False), (0, 0.0011, True), (-1.5, -1.5004, False), (-1.5, -1.5, False), (1e-4, -1e-4, False),
    (True, True, False), (False, False, False), (True, False, True), (False, True, True),
    (True, 1, False), (False, 0, False), (True, 0, True), (1, True, False), (0, True, True), (False, 0.0, False), (True, 2, False),
    ("a", "a", False), ("a", "b", True), ("1", 1, True), (None, None, False), (None, 0, True), (0, None, True), ("x", None, True),
    ([1, 2], [1, 2], False), ([1, 2], [1, 3], True),
])
def test_mismatched(expected, actual, result):
    assert capture.mismatched(expected, actual) is result


def test_mismatched_tolerance_is_a_thousandth():
    assert capture.mismatched(140.0, 140.0009) is False and capture.mismatched(140.0, 140.0011) is True
    assert capture.mismatched(140.0, 139.9991) is False and capture.mismatched(140.0, 139.9989) is True
    assert capture.mismatched(0.0, 0.0) is False and capture.mismatched(1, 2) is True


# ---------------------------------------------------------------------------
# wanted_states
# ---------------------------------------------------------------------------

#            name          user mute  capture  group
ROWS = [("kick", False, False, False), ("bassA", False, False, False), ("pad", False, False, False), ("Drums", False, False, True),
        ("old take", True, False, False), ("cap:kick", False, True, False), ("cap:bassA", False, True, False), ("cap:mix", False, True, False),
        ("cap:A-Reverb", False, True, False)]


def states(rows, **changes):
    return capture.wanted_states(rows, capture.validate_passes([tap_pass(**changes)])[0])


def test_a_tap_pass_mutes_what_it_does_not_fire_and_arms_only_its_own_capture_tracks():
    wanted = states(ROWS)                                                                                # fires kick and bassA, records kick, bassA, mix
    assert wanted["kick"] == (False, False, False) and wanted["bassA"] == (False, False, False)           # fired: left as the user had them
    assert wanted["pad"] == (True, False, False)                                                         # not fired: muted for the pass
    assert wanted["old take"] == (True, False, False)
    assert wanted["cap:kick"] == (False, False, True) and wanted["cap:bassA"] == (False, False, True) and wanted["cap:mix"] == (False, False, True)
    assert wanted["cap:A-Reverb"] == (False, False, False)                                               # another pass's capture track: not armed
    assert set(wanted) == set(row[0] for row in ROWS)


def test_group_tracks_are_never_muted_by_a_pass():
    wanted = states(ROWS)
    assert wanted["Drums"] == (False, False, False)                                                      # muting a group would silence its children
    rows = [("Drums", True, False, True)]
    assert states(rows)["Drums"] == (True, False, False)                                                 # but the user's own mute stays
    assert states([("Bus", False, False, True)], mute_others=False)["Bus"] == (False, False, False)


def test_a_fired_track_keeps_the_users_own_mute():
    rows = [("kick", True, False, False), ("bassA", False, False, False)]
    wanted = states(rows)
    assert wanted["kick"] == (True, False, False)                                                        # a muted source records silence; planner warns
    assert wanted["bassA"] == (False, False, False)


def test_regular_tracks_are_always_disarmed():
    wanted = states(ROWS)
    assert all(state[2] is False for name, state in wanted.items() if not name.startswith("cap:"))
    solo = states(ROWS, solo=["kick"], record=[{"key": "mix", "source": "resampling"}])
    assert all(state[2] is False for name, state in solo.items() if not name.startswith("cap:")) and solo["cap:mix"][2] is True


def test_capture_tracks_are_never_muted_or_soloed():
    rows = [("cap:kick", True, True, False), ("cap:mix", False, True, True)]
    wanted = states(rows, solo=["cap:kick"])
    assert wanted["cap:kick"] == (False, False, True) and wanted["cap:mix"] == (False, False, True)


def test_a_solo_pass_solos_exactly_the_listed_tracks_and_mutes_nobody():
    wanted = states(ROWS, solo=["bassA"], record=[{"key": "mix", "source": "resampling"}], mute_others=False)
    assert wanted["bassA"] == (False, True, False)
    for name in ("kick", "pad", "Drums"):
        assert wanted[name] == (False, False, False)                                                     # not muted, not soloed
    assert wanted["old take"] == (True, False, False)                                                    # the user's own mute stays
    assert wanted["cap:mix"] == (False, False, True) and wanted["cap:kick"] == (False, False, False)
    two = states(ROWS, solo=["kick", "pad"], record=[{"key": "mix", "source": "resampling"}])
    assert [name for name, state in two.items() if state[1]] == ["kick", "pad"]


def test_a_solo_pass_defaults_to_muting_nobody_but_can_be_asked_to():
    bare = {"fire": [{"track": "kick", "slot": 0}], "record": [{"key": "mix", "source": "resampling"}], "beats": 8, "solo": ["kick"]}
    item = capture.validate_passes([bare])[0]                                                           # no mute_others given
    assert item["mute_others"] is False and capture.wanted_states(ROWS, item)["pad"] == (False, False, False)
    both = states(ROWS, solo=["kick"], mute_others=True, record=[{"key": "mix", "source": "resampling"}])
    assert both["kick"] == (False, True, False) and both["pad"] == (True, False, False) and both["bassA"] == (False, False, False)   # bassA is fired


def test_a_solo_name_that_is_not_in_the_set_is_ignored_and_no_tracks_is_fine():
    wanted = states(ROWS, solo=["not there"], mute_others=False)
    assert not any(state[1] for state in wanted.values())
    assert capture.wanted_states([], capture.validate_passes([tap_pass()])[0]) == {}


def test_a_later_pass_unmutes_what_an_earlier_one_muted():
    """The rows carry the user's mute (not the live one), so each pass starts from the user's set."""
    rows = [("kick", False, False, False), ("bassA", False, False, False)]
    first = capture.wanted_states(rows, capture.validate_passes([tap_pass(fire=[{"track": "kick", "slot": 0}])])[0])
    second = capture.wanted_states(rows, capture.validate_passes([tap_pass(fire=[{"track": "bassA", "slot": 0}])])[0])
    assert first["bassA"][0] is True and first["kick"][0] is False
    assert second["kick"][0] is True and second["bassA"][0] is False


def test_wanted_states_for_a_real_plan():
    spec = specs.load("nova")
    plan = planner.plan_capture(spec, ns.nova_snapshot(), "neon", tempos=[140], mode="tap", variation="A")
    item = capture.validate_passes(planner.engine_passes(plan))[0]
    rows = [(name, False, False, False) for name in ns.TRACKS] + [("cap:" + entry["key"], False, True, False) for entry in item["record"]]
    wanted = capture.wanted_states(rows, item)
    assert wanted["bassB"] == (True, False, False) and wanted["leadB"] == (True, False, False)           # variation B is not in the pass
    assert all(wanted[name] == (False, False, False) for name in ("kick", "perc", "pad", "bassA", "arpA", "leadA"))
    assert all(wanted["cap:" + entry["key"]] == (False, False, True) for entry in item["record"])
