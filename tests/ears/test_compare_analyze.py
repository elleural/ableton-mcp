"""Unit tests for ears/analyze.py (the measurement ear) and ears/compare.py (deltas, blind packets, spec and reference
comparisons) on synthetic NOVA stems from ears.fixtures.audio at 48 kHz.

Rendering is shared through module-scoped fixtures: the full A+B set at 140 BPM (clean, identical copy, +6 dB at 3 kHz on
the arp) and a smaller variation-A set for the cheaper checks.
"""
import copy
import json
import re
import shutil

import numpy as np
import pytest

from ears import analyze, compare, loudness, measure, report
from ears import spec as specs
from ears import take as takes
from ears.audio import Audio
from ears.fixtures import audio as fx
from tests.ears import nova_snapshot as ns
from tests.ears.support import memoise_side_metrics

TEMPO = 140.0
RATE = 48000


@pytest.fixture(scope="module")
def spec():
    return specs.load("nova")


@pytest.fixture(scope="module", autouse=True)
def memoised_side_metrics():
    with memoise_side_metrics() as real:
        yield real


@pytest.fixture(scope="module")
def home(tmp_path_factory):
    folder = tmp_path_factory.mktemp("ears-home")
    yield folder
    shutil.rmtree(folder, ignore_errors=True)               # a few hundred MB of takes


@pytest.fixture(scope="module")
def clean_parts(spec):
    return fx.normalise(fx.render_parts(spec, "neon", TEMPO), spec, "neon", TEMPO)


@pytest.fixture(scope="module")
def clean_take(spec, home, clean_parts):
    return takes.load(home, fx.write_take(home, spec, "neon", TEMPO, clean_parts, bit_depth=24))


@pytest.fixture(scope="module")
def same_take(spec, home, clean_parts, clean_take):
    return takes.load(home, fx.write_take(home, spec, "neon", TEMPO, clean_parts, bit_depth=24))


@pytest.fixture(scope="module")
def arp_take(spec, home, clean_parts):
    parts, mix = fx.plant(clean_parts, "arp_3k", spec, "neon", TEMPO)
    return takes.load(home, fx.write_take(home, spec, "neon", TEMPO, parts, mix=mix, bit_depth=24))


@pytest.fixture(scope="module")
def clean_report(spec, clean_take):
    return analyze.analyze_take(clean_take, spec, strict_mode=True)


@pytest.fixture(scope="module")
def arp_vs_clean(spec, home, arp_take, clean_take):
    return compare.compare_takes(arp_take, clean_take, spec)


@pytest.fixture(scope="module")
def same_vs_clean(spec, same_take, clean_take):
    return compare.compare_takes(same_take, clean_take, spec)


@pytest.fixture(scope="module")
def small_parts(spec):
    return fx.normalise(fx.render_parts(spec, "neon", TEMPO, variations=["A"]), spec, "neon", TEMPO, variation="A")


@pytest.fixture(scope="module")
def small_take(spec, home, small_parts):
    return takes.load(home, fx.write_take(home, spec, "neon", TEMPO, small_parts, variations=["A"], bit_depth=24))


@pytest.fixture(scope="module")
def small_images(tmp_path_factory):
    folder = tmp_path_factory.mktemp("images")
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


ARPEGGIATOR = {"path": "1", "name": "Arpeggiator", "class_name": "MidiArpeggiator", "type": "midi_effect", "active": True}


@pytest.fixture(scope="module")
def small_report(spec, small_take, small_images):
    """One non-strict analysis of the variation-A take, with images and a snapshot whose arp track carries a MIDI effect."""
    snapshot = ns.nova_snapshot(devices={"arpA": [ARPEGGIATOR], "kick": [dict(ARPEGGIATOR, type="instrument")]})
    return analyze.analyze_take(small_take, spec, images_dir=small_images, snapshot=snapshot)


def by_check(result, name, subject=None):
    return [item for item in result["checks"] if item["check"] == name and (subject is None or item.get("subject") == subject)]


def sine(dbfs, seconds, freq=1000.0, channels=2, rate=RATE):
    t = np.arange(int(round(seconds * rate))) / float(rate)
    x = 10 ** (dbfs / 20.0) * np.sin(2 * np.pi * freq * t)
    return Audio(np.repeat(x[:, None], channels, axis=1) if channels > 1 else x[:, None], rate)


# ---------------------------------------------------------------------------
# analyze_take on the clean fixture
# ---------------------------------------------------------------------------


def test_the_clean_fixture_has_no_fail(clean_report):
    assert clean_report["counts"]["fail"] == 0
    assert clean_report["verdict"].startswith("0 fail, ")
    assert [item["check"] for item in clean_report["checks"] if item["status"] == "fail"] == []


def test_the_report_is_labelled_with_the_take(clean_report, clean_take):
    assert clean_report["kind"] == "audio" and clean_report["subject"] == clean_take.id and clean_report["take"] == clean_take.id
    assert clean_report["set"] == "neon" and clean_report["tempo"] == 140.0 and clean_report["variation"] == "AB" and clean_report["mode"] == "tap"
    assert sorted(clean_report["values"]) == ["tiers@A", "tiers@B"] and sorted(clean_report["values"]["tiers@A"]) == ["T1", "T2", "T3", "T4", "T5"]
    assert clean_report["counts"] == report.counts(clean_report["checks"]) and clean_report["verdict"] == report.verdict(clean_report["checks"])
    json.dumps(clean_report, allow_nan=False)


def test_loudness_of_the_top_tier_is_checked_for_each_variation(clean_report):
    for variation in ("A", "B"):
        [loud] = by_check(clean_report, "audio.loudness", "T5@" + variation)
        assert loud["status"] == "pass" and loud["value"]["lufs_i"] == pytest.approx(-14.0, abs=0.1) and loud["value"]["true_peak_dbtp"] < -1.0
        assert loud["target"] == {"lufs_i": -14.0, "true_peak_dbtp": -1.0} and loud["tolerance"] == 0.5
        assert clean_report["values"]["tiers@" + variation]["T5"]["lufs"] == pytest.approx(-14.0, abs=0.1)
    ladder = by_check(clean_report, "audio.tier_ladder")
    assert [item["status"] for item in ladder] == ["info", "info"] and "T1" in ladder[0]["summary"] and "T5" in ladder[0]["summary"]
    steps = ladder[0]["value"]["steps"]
    assert [step["tier"] for step in steps] == ["T2", "T3", "T4", "T5"] and all(step["step_lu"] >= -0.05 for step in steps)


def test_key_mono_sub_and_sum_null_pass_on_the_clean_fixture(clean_report):
    assert [item["status"] for item in by_check(clean_report, "audio.key", "T5@A")] == ["pass"]
    assert [item["status"] for item in by_check(clean_report, "audio.key", "T5@B")] == ["pass"]
    assert by_check(clean_report, "audio.key", "T5@A")[0]["value"] == "A minor" and by_check(clean_report, "audio.key", "T5@A")[0]["target"] == "A minor"
    alone = [item["subject"] for item in by_check(clean_report, "audio.key") if "@" not in item["subject"]]
    assert not set(alone) & {"kick", "perc", "bassA", "bassB", "leadA", "leadB"}                                  # only the harmony stems are judged alone
    mono = by_check(clean_report, "audio.mono_sub")
    assert {item["subject"] for item in mono} >= {"T5@A", "T5@B", "kick", "bassA", "bassB"} and all(item["status"] == "pass" for item in mono)
    [null] = by_check(clean_report, "audio.sum_null")
    assert null["status"] == "pass" and null["subject"] == "mix" and null["value"] > 100.0 and null["target"] == 40.0
    assert null["parts"] == 9 and null["returns"] == 0


def test_report_level_checks_are_info_and_the_rest_are_skipped_honestly(clean_report):
    for name in ("audio.masking", "audio.reactivity", "audio.phone", "audio.tier_ladder"):
        assert all(item["status"] == "info" for item in by_check(clean_report, name)), name
    assert [item["status"] for item in by_check(clean_report, "audio.balance")] == ["skip", "skip"]            # no reference envelope yet
    assert [item["status"] for item in by_check(clean_report, "audio.tempo_consistency")] == ["skip"]       # no other tempos given
    assert "T5" in by_check(clean_report, "audio.reactivity")[0]["summary"]
    assert by_check(clean_report, "audio.masking")[0]["items"]
    phone = by_check(clean_report, "audio.phone", "parts@A")[0]
    assert phone["value"]["kick"] < 10.0 and "T5" in phone["value"]                                              # the kick barely survives a phone speaker


def test_strict_mode_adds_the_file_checks_for_every_part(clean_report):
    names = [item["check"] for item in clean_report["checks"] if item["check"].startswith("file.")]
    assert set(names) == {"file.duration", "file.seam", "file.start", "file.format"}
    for part in ns.TRACKS:
        assert [item["status"] for item in by_check(clean_report, "file.duration", part)] == ["pass"]
        assert [item["status"] for item in by_check(clean_report, "file.format", part)] == ["pass"]
        assert [item["status"] for item in by_check(clean_report, "file.seam", part)] == ["pass"]
        assert [item["status"] for item in by_check(clean_report, "file.start", part)] == ["skip"]               # no snapshot: notes unknown
    assert len(by_check(clean_report, "file.duration")) == 9


def test_without_strict_mode_there_are_no_file_checks(small_report):
    result = small_report
    assert not [item for item in result["checks"] if item["check"].startswith("file.")]
    assert result["variation"] == "A" and sorted(result["values"]) == ["tiers@A"] and result["counts"]["fail"] == 0
    assert len(by_check(result, "audio.loudness")) == 1 and by_check(result, "audio.loudness")[0]["subject"] == "T5@A"


def test_float_delivery_files_fail_the_format_check_only_in_strict_mode(spec, home, small_parts):
    take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, small_parts, variations=["A"], mode="files", bit_depth=32))
    strict = {"checks": analyze.strict_checks(spec, take)}
    assert {item["subject"] for item in by_check(strict, "file.format") if item["status"] == "fail"} == {"kick", "perc", "pad", "bassA", "arpA", "leadA"}
    assert all(item["status"] == "pass" for item in by_check(strict, "file.duration"))
    assert not [item for item in analyze.silence_checks(take.parts())]


# ---------------------------------------------------------------------------
# analyze_take: planted defects, snapshots and missing parts
# ---------------------------------------------------------------------------


def test_a_part_that_is_missing_is_a_warning_and_the_rest_is_still_measured(spec, home, small_parts):
    partial = dict((key, value) for key, value in small_parts.items() if key != "leadA")
    take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, partial, variations=["A"], bit_depth=24))
    result = analyze.analyze_take(take, spec)
    [missing] = by_check(result, "audio.parts")
    assert missing["status"] == "warn" and missing["subject"] == "A" and missing["summary"] == "missing from the take: leadA"
    assert by_check(result, "audio.loudness")[0]["subject"] == "T5@A"


def test_a_silent_part_is_a_warning(spec, home, small_parts):
    silent = dict(small_parts)
    silent["leadA"] = Audio(np.zeros_like(small_parts["leadA"].samples), RATE)
    take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, silent, variations=["A"], mode="files"))
    [warning] = by_check(analyze.analyze_take(take, spec), "audio.silent")
    assert warning["status"] == "warn" and warning["subject"] == "leadA" and "silent" in warning["summary"]


def test_the_snapshot_decides_which_file_start_checks_run(spec, home, small_parts):
    take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, small_parts, variations=["A"], bit_depth=24))
    on_beat_one = {"id": 1, "pitch": 36, "start": 0.0, "duration": 0.25, "velocity": 100, "mute": False, "probability": 1.0, "velocity_deviation": 0.0}
    muted = dict(on_beat_one, mute=True)
    later = dict(on_beat_one, start=1.0)
    snapshot = ns.nova_snapshot(notes={"kick": [on_beat_one], "perc": [muted, later], "bassA": [later], "arpA": [on_beat_one]})
    snapshot["tracks"][ns.TRACKS.index("pad")]["clips"][0].pop("notes", None)                                # pad: notes not read
    checks = {item["subject"]: item for item in analyze.strict_checks(spec, take, snapshot) if item["check"] == "file.start"}
    assert checks["kick"]["status"] == "pass" and "transient at" in checks["kick"]["summary"]                  # a note on beat 1 and the kick starts at once
    assert checks["perc"]["status"] == "pass" and "no note on beat 1" in checks["perc"]["summary"]            # a muted note does not count
    assert checks["bassA"]["status"] == "pass" and "no note on beat 1" in checks["bassA"]["summary"]
    assert checks["arpA"]["status"] == "pass"
    assert checks["pad"]["status"] == "skip" and checks["leadA"]["status"] == "skip"                          # unknown: skipped, not failed
    # without a snapshot every one is skipped
    assert {item["status"] for item in analyze.strict_checks(spec, take) if item["check"] == "file.start"} == {"skip"}


def test_a_note_on_beat_one_needs_the_clip_the_take_captured(spec, home, small_parts):
    take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, small_parts, variations=["A"], bit_depth=24))
    note = {"id": 1, "pitch": 36, "start": 0.0, "duration": 0.25, "velocity": 100, "mute": False, "probability": 1.0, "velocity_deviation": 0.0}
    snapshot = ns.nova_snapshot(notes={"kick": [note]}, slots={"kick": [0, 1]})
    snapshot["tracks"][0]["clips"][1]["notes"] = []                                                           # the LOW clip is empty, MID has the note
    take.meta["clips"] = {"kick": {"track": "kick", "slot": 0, "scene": "NEON-MID"}}
    assert [i["status"] for i in analyze.strict_checks(spec, take, snapshot) if i["check"] == "file.start" and i["subject"] == "kick"] == ["pass"]
    assert "no note on beat 1" not in by_check({"checks": analyze.strict_checks(spec, take, snapshot)}, "file.start", "kick")[0]["summary"]
    take.meta["clips"] = {"kick": {"track": "kick", "slot": 1, "scene": "NEON-LOW"}}
    assert "no note on beat 1" in by_check({"checks": analyze.strict_checks(spec, take, snapshot)}, "file.start", "kick")[0]["summary"]


def test_parts_with_midi_effects_get_an_onset_report(small_report, clean_report):
    [onsets] = by_check(small_report, "audio.onsets")                                     # only arpA: the kick's device is an instrument
    assert onsets["status"] == "info" and onsets["subject"] == "arpA" and "onsets" in onsets["summary"] and "on the grid" in onsets["summary"]
    assert onsets["value"]["count"] > 20                                                  # the 16th-note arp
    assert not by_check(clean_report, "audio.onsets")                                     # no snapshot, no MIDI effects, no onset report


def test_fills_are_checked_without_a_seam(spec, home):
    fill = Audio(np.zeros((int(round((spec.bar_seconds(TEMPO) + spec.tail_seconds()) * RATE)), 2)), RATE)
    fill.samples[100:2000, 0] = 0.5
    take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, {"levelup_fill": fill}, mode="files", bit_depth=24))
    checks = analyze.strict_checks(spec, take)
    assert [item["check"] for item in checks] == ["file.duration", "file.start", "file.format"] and checks[0]["status"] == "pass"


def test_images_are_written_and_listed(small_report, small_images):
    assert [path.rsplit("/", 1)[-1] for path in small_report["images"]] == ["stems.png", "ladder.png"]
    for path in small_report["images"]:
        assert path.startswith(str(small_images)) and open(path, "rb").read(8) == b"\x89PNG\r\n\x1a\n"


def test_no_images_are_made_unless_a_folder_is_given(clean_report):
    assert "images" not in clean_report


# ---------------------------------------------------------------------------
# analyze: the single checks
# ---------------------------------------------------------------------------


def test_null_depth_is_the_residual_below_the_mix():
    rng = np.random.default_rng(1)
    signals = [rng.standard_normal((4800, 2)) * 0.1 for _ in range(3)]
    mix = sum(signals)
    assert analyze.null_depth(mix, signals) == 200.0                                                       # a perfect null
    assert analyze.null_depth(mix * 1.01, signals) == pytest.approx(20 * np.log10(1.01 / 0.01), abs=0.01)
    assert analyze.null_depth(mix * 1.1, signals) == pytest.approx(20 * np.log10(1.1 / 0.1), abs=0.01)
    assert analyze.null_depth(mix, signals[:2]) == pytest.approx(10 * np.log10(np.mean(mix ** 2) / np.mean(signals[2] ** 2)), abs=0.01)
    assert analyze.null_depth(np.zeros((100, 2)), [np.zeros((100, 2))]) == 200.0                          # nothing to cancel


def test_null_depth_compares_only_the_common_length():
    a = np.ones((100, 2)) * 0.3
    b = np.ones((150, 2)) * 0.3
    assert analyze.null_depth(a, [b]) == 200.0 and analyze.null_depth(b, [a]) == 200.0


def test_sum_null_check_computes_the_null_itself_for_takes_without_a_stored_depth(spec, home, small_parts):
    parts, mix = fx.plant(small_parts, "master_reverb", spec, "neon", TEMPO)
    clean = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, small_parts, variations=["A"], bit_depth=24))
    planted = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, parts, mix=mix, variations=["A"], bit_depth=24))
    [ok] = analyze.sum_null_checks(spec, clean)
    [bad] = analyze.sum_null_checks(spec, planted)
    assert ok["status"] == "pass" and ok["value"] > 100.0
    assert bad["status"] == "fail" and bad["value"] < 20.0 and "something reaches the master that was not captured" in bad["summary"]


def test_sum_null_check_uses_the_depth_stored_at_ingestion(spec, home, small_parts):
    take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, small_parts, variations=["A"], bit_depth=24))
    take.meta["sum_null"] = {"mix": 12.5}
    [bad] = analyze.sum_null_checks(spec, take)
    assert bad["status"] == "fail" and bad["value"] == 12.5
    take.meta["sum_null"] = {"mix": 40.0}
    assert analyze.sum_null_checks(spec, take)[0]["status"] == "pass"                                      # the limit itself passes
    take.meta["sum_null"] = {"mix": 39.9}
    assert analyze.sum_null_checks(spec, take)[0]["status"] == "fail"


def test_sum_null_check_is_skipped_for_solo_takes_and_takes_without_a_mix(spec, home, small_parts):
    solo = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, small_parts, variations=["A"], mode="solo"))
    [skipped] = analyze.sum_null_checks(spec, solo)
    assert skipped["status"] == "skip" and "only tap captures" in skipped["summary"]
    files = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, small_parts, variations=["A"], mode="files"))
    [none] = analyze.sum_null_checks(spec, files)
    assert none["status"] == "skip" and none["summary"] == "the take has no main mix"


def test_loudness_checks_decide_pass_fail_and_the_ladder(spec):
    ok = {"T1": sine(-20.0, 6.0), "T5": sine(-14.0, 6.0)}
    checks, measured = analyze.loudness_checks(spec, "A", ok)
    assert [item["check"] for item in checks] == ["audio.loudness", "audio.tier_ladder"] and checks[0]["status"] == "pass" and checks[1]["status"] == "info"
    assert sorted(measured) == ["T1", "T5"] and measured["T5"]["integrated"] == pytest.approx(-14.0, abs=0.1)
    for dbfs, status in ((-13.6, "pass"), (-14.4, "pass"), (-13.3, "fail"), (-14.7, "fail"), (-20.0, "fail")):
        assert analyze.loudness_checks(spec, "A", {"T5": sine(dbfs, 6.0)})[0][0]["status"] == status, dbfs
    loud_peak = sine(-14.0, 6.0)
    loud_peak.samples[24000, 0] = 0.95                                                                        # -0.4 dBFS
    [verdict, _] = analyze.loudness_checks(spec, "A", {"T5": loud_peak})[0]
    assert verdict["status"] == "fail" and "true peak" in verdict["summary"] and "LUFS" not in verdict["summary"]
    dropped = {"T1": sine(-20.0, 6.0), "T2": sine(-18.0, 6.0), "T3": sine(-19.5, 6.0), "T4": sine(-17.0, 6.0), "T5": sine(-14.0, 6.0)}
    ladder = analyze.loudness_checks(spec, "B", dropped)[0][-1]
    assert ladder["status"] == "warn" and ladder["subject"] == "tiers@B" and "T3 is 1.5 LU quieter than T2" in ladder["summary"] and "cancellation" in ladder["summary"]
    assert [step["tier"] for step in ladder["value"]["steps"]] == ["T2", "T3", "T4", "T5"]


def test_loudness_target_and_tolerance_come_from_the_spec(spec):
    data = copy.deepcopy(spec.data)
    data["targets"]["lufs_i"] = -16.0
    data["tolerances"]["lufs_i_lu"] = 2.0
    custom = specs.Spec(data)
    assert analyze.loudness_checks(custom, "A", {"T5": sine(-17.5, 6.0)})[0][0]["status"] == "pass"
    assert analyze.loudness_checks(custom, "A", {"T5": sine(-14.0, 6.0)})[0][0]["status"] == "fail"


def sub_tone(seconds=4.0, freq=55.0, level=0.3, phase=0.0):
    t = np.arange(int(seconds * RATE)) / float(RATE)
    return level * np.sin(2 * np.pi * freq * t + phase), t


def test_mono_sub_check_passes_an_in_phase_sub_and_fails_one_that_partly_cancels(spec):
    sub, t = sub_tone()
    in_phase = Audio(np.stack([sub, sub], axis=1), RATE)
    decorrelated = Audio(np.stack([sub, 0.3 * np.sin(2 * np.pi * 55.0 * t + 2.0)], axis=1), RATE)           # a 115 degree phase difference
    mono = Audio(sub[:, None], RATE)
    highs = Audio(np.stack([0.3 * np.sin(2 * np.pi * 3000.0 * t)] * 2, axis=1) * np.array([[1.0, -1.0]]), RATE)   # no sub: nothing to check
    checks = analyze.mono_checks(spec, {"in": in_phase, "partial": decorrelated, "mono": mono, "highs": highs})
    by_subject = dict((item["subject"], item) for item in checks)
    assert sorted(by_subject) == ["in", "partial"]                                                           # mono and sub-less files are skipped
    assert by_subject["in"]["status"] == "pass" and by_subject["in"]["value"] == pytest.approx(0.0, abs=0.1) and by_subject["in"]["target"] == 1.0
    assert by_subject["partial"]["status"] == "fail" and by_subject["partial"]["value"] > 3.0 and "below 120 Hz" in by_subject["partial"]["summary"]
    assert by_subject["in"]["correlation"] > 0.99 and by_subject["partial"]["correlation"] < 0.5


def test_mono_sub_check_tolerance_comes_from_the_spec(spec):
    sub, t = sub_tone()
    slightly_off = Audio(np.stack([sub, 0.3 * np.sin(2 * np.pi * 55.0 * t + 0.6)], axis=1), RATE)          # about 0.4 dB lost in mono
    [tight] = analyze.mono_checks(spec, {"x": slightly_off})
    assert 0.0 < tight["value"] < 1.0 and tight["status"] == "pass"
    data = copy.deepcopy(spec.data)
    data["tolerances"]["mono_sub_db"] = 0.1
    [strict] = analyze.mono_checks(specs.Spec(data), {"x": slightly_off})
    assert strict["status"] == "fail"


def test_mono_sub_check_fails_a_sub_that_cancels_completely_in_mono(spec):
    sub, _ = sub_tone()
    out_of_phase = Audio(np.stack([sub, -sub], axis=1), RATE)
    [verdict] = analyze.mono_checks(spec, {"out": out_of_phase})
    assert verdict["status"] == "fail" and verdict["value"] > 20.0


def chord(freqs, level=0.1, seconds=8):
    t = np.arange(RATE * seconds) / float(RATE)
    x = sum(level * np.sin(2 * np.pi * f * t) for f in freqs)
    return Audio(np.stack([x, x], axis=1), RATE)


D_MAJOR = [293.66, 369.99, 440.0, 587.33, 739.99, 880.0]          # D F# A: nothing like A minor
A_MINOR = [220.0, 261.63, 329.63, 440.0, 523.25, 659.25]


def test_key_checks_fail_the_mix_and_warn_the_stem(spec):
    d_major, a_minor = chord(D_MAJOR), chord(A_MINOR)
    [bad] = analyze.key_checks(spec, "A", {"T5": d_major}, {}, set())
    assert bad["check"] == "audio.key" and bad["status"] == "fail" and bad["subject"] == "T5@A" and bad["target"] == "A minor" and bad["value"] != "A minor"
    [good] = analyze.key_checks(spec, "A", {"T5": a_minor}, {}, set())
    assert good["status"] == "pass" and good["value"] == "A minor"
    checks = analyze.key_checks(spec, "A", {"T5": a_minor}, {"bassA": d_major, "kick": d_major, "arpA": a_minor}, {"bassA", "arpA"})
    assert [(item["subject"], item["status"]) for item in checks] == [("T5@A", "pass"), ("bassA", "warn")]       # the kick is not a harmony stem, the arp is in key
    assert "heard alone" in checks[1]["summary"]


def test_key_checks_skip_silent_stems_and_cope_with_a_silent_mix(spec):
    silent = Audio(np.zeros((RATE * 3, 2)), RATE)
    checks = analyze.key_checks(spec, "A", {"T5": silent}, {"pad": silent, "arpA": chord(A_MINOR)}, {"pad", "arpA"})
    assert [(item["subject"], item["status"]) for item in checks] == [("T5@A", "fail")]                          # no key in silence; the silent pad is audio.silent's job
    assert "None" in checks[0]["summary"] and analyze.key_checks(spec, "A", {}, {}, set()) == []


@pytest.mark.parametrize("found, expected", [
    ({"tonic": "A", "mode": "minor"}, True), ({"tonic": "a", "mode": "minor"}, True), ({"tonic": "A", "mode": "major"}, False),
    ({"tonic": "C", "mode": "minor"}, False), ({"tonic": None, "mode": None}, False), ({"tonic": "A", "mode": None}, False),
    ({"tonic": "H", "mode": "minor"}, False), ({}, False), (None, False),
    ({"key": "A minor"}, True), ({"key": "C major"}, False), ({"key": None}, False), ({"key": "not a key"}, False),      # a runner-up may carry only its name
])
def test_same_key_is_a_plain_yes_or_no(spec, found, expected):
    assert analyze._same_key(found, spec) is expected


def test_a_top_tier_key_miss_by_a_hair_is_uncertain_not_failed(spec, monkeypatch):
    def estimate(confidence, runner_up, second_key="A minor"):
        tonic, _, mode = second_key.partition(" ")
        return {"key": "C major", "tonic": "C", "mode": "major", "confidence": confidence,
                "second": {"key": second_key, "tonic": tonic, "mode": mode, "confidence": runner_up}}

    sums = {"T5": Audio(np.zeros((RATE, 2)), RATE)}

    def status_for(found):
        monkeypatch.setattr(analyze.measure, "key_estimate", lambda audio, a4: found)
        [item] = analyze.key_checks(spec, "A", sums, {}, set())
        return item

    close = analyze.KEY_UNCERTAIN / 2.0
    uncertain = status_for(estimate(0.80, 0.80 - close))
    assert uncertain["status"] == "warn" and "uncertain" in uncertain["summary"] and uncertain["value"] == "C major"
    assert status_for(estimate(0.80, 0.80 - 2 * analyze.KEY_UNCERTAIN))["status"] == "fail"                    # a clear miss
    assert status_for(estimate(0.80, 0.79, second_key="E minor"))["status"] == "fail"                         # close, but the runner-up is not the spec's key
    assert status_for(dict(estimate(0.80, 0.79), key="A minor", tonic="A", mode="minor"))["status"] == "pass"


def test_balance_checks_compare_third_octave_levels_with_the_envelope(spec):
    tone = sine(-14.0, 5.0, freq=1000.0)
    skipped = analyze.balance_checks(spec, {"T5@A": tone}, None)
    assert skipped[0]["status"] == "skip" and analyze.balance_checks(spec, {"T5@A": tone}, {})[0]["status"] == "skip"
    inside = analyze.balance_checks(spec, {"T5@A": tone}, {"1000": (-3.0, 3.0), "63": (-200.0, 0.0)})
    assert inside[0]["status"] == "pass" and inside[0]["summary"] == "inside the reference envelope" and inside[0]["subject"] == "T5@A"
    outside = analyze.balance_checks(spec, {"T5@A": tone}, {"1000": (-30.0, -20.0), "63": (-10.0, 0.0), "9999": (0.0, 1.0)})
    [warn] = outside
    assert warn["status"] == "warn" and warn["summary"] == "2 bands outside the reference envelope"
    assert {item["band_hz"] for item in warn["items"]} == {"1000", "63"} and "9999" not in {item["band_hz"] for item in warn["items"]}   # unknown band: ignored
    one = [item for item in warn["items"] if item["band_hz"] == "1000"][0]
    assert one["envelope"] == [-30.0, -20.0] and one["value"] == pytest.approx(0.0, abs=1.0)


def test_silence_checks():
    assert analyze.silence_checks({"a": sine(-20.0, 1.0)}) == []
    assert analyze.silence_checks({"a": sine(-70.0, 1.0)}) == []                                            # quiet is not silent
    [warn] = analyze.silence_checks({"a": sine(-20.0, 1.0), "b": Audio(np.zeros((4800, 2)), RATE)})
    assert warn["check"] == "audio.silent" and warn["status"] == "warn" and warn["subject"] == "b" and "silent" in warn["summary"]
    both = analyze.silence_checks({"b": Audio(np.zeros((4800, 2)), RATE), "c": sine(-90.0, 1.0)})            # peak below -80 dBFS
    assert [item["subject"] for item in both] == ["b", "c"] and all(item["status"] == "warn" for item in both)


def test_tempo_consistency_flags_the_part_that_is_louder_at_one_tempo(spec, home):
    others, parts = [], {}
    for tempo in (130.0, 140.0, 150.0):
        parts[tempo] = fx.normalise(fx.render_parts(spec, "neon", tempo, variations=["A"]), spec, "neon", tempo, variation="A")
        if tempo != 140.0:
            others.append(takes.load(home, fx.write_take(home, spec, "neon", tempo, parts[tempo], variations=["A"], mode="files", bit_depth=24)))
    clean = takes.load(home, fx.write_take(home, spec, "neon", 140.0, parts[140.0], variations=["A"], mode="files", bit_depth=24))
    checks = analyze.tempo_checks(spec, clean, others)
    assert sorted(item["subject"] for item in checks) == ["arpA", "bassA", "kick", "leadA", "pad", "perc"] and all(item["status"] == "pass" for item in checks)
    assert all(item["tolerance"] == 1.0 and set(item["value"]) == {"130", "140", "150"} for item in checks)
    louder, _ = fx.plant(parts[140.0], "stem_louder", spec, "neon", 140.0)                                  # arpA +3 dB at 140 BPM only
    planted = takes.load(home, fx.write_take(home, spec, "neon", 140.0, louder, variations=["A"], mode="files", bit_depth=24))
    checks = analyze.tempo_checks(spec, planted, others)
    failing = [item for item in checks if item["status"] == "fail"]
    assert [item["subject"] for item in failing] == ["arpA"] and re.search(r"\+3\.[01] LU at 140 BPM", failing[0]["summary"]) and "median over 3 tempos" in failing[0]["summary"]
    one_other = analyze.tempo_checks(spec, planted, others[:1])                                              # two tempos are enough to compare
    assert [item["subject"] for item in one_other if item["status"] == "fail"] == ["arpA"]


def test_tempo_consistency_needs_other_tempos(spec, small_take):
    [skipped] = analyze.tempo_checks(spec, small_take, [])
    assert skipped["status"] == "skip" and skipped["summary"] == "needs takes at other tempos of the set"
    [alone] = analyze.tempo_checks(spec, small_take, [small_take])                                          # the same tempo again is not another tempo
    assert alone["status"] == "skip" and alone["summary"] == "no part appears at another tempo"


# ---------------------------------------------------------------------------
# compare_takes
# ---------------------------------------------------------------------------


def delta(result, prefix, suffix=""):
    found = [item for item in result["deltas"] if item["metric"].startswith(prefix) and item["metric"].endswith(suffix)]
    assert found, (prefix, [item["metric"] for item in result["deltas"]])
    return found[0]


def test_both_variations_are_compared_and_labelled(arp_vs_clean):
    assert arp_vs_clean["variations"] == ["A", "B"] and arp_vs_clean["variation"] == "AB"
    metrics = [item["metric"] for item in arp_vs_clean["deltas"]]
    for name in ("T5@A integrated loudness", "T5@B integrated loudness", "T5@A true peak", "T5@B true peak", "mono sub loss@A", "mono sub loss@B", "key@A", "key@B"):
        assert name in metrics, name
    assert "T5 integrated loudness" not in metrics                                                          # with two variations every metric is suffixed
    assert len(metrics) == len(set(metrics))


def test_the_planted_arp_boost_shows_as_a_third_octave_delta_near_plus_6_db(arp_vs_clean):
    shifts = [item for item in arp_vs_clean["deltas"] if item["metric"].startswith("arp") and "Hz third octave" in item["metric"]]
    assert {item["metric"].split()[0] for item in shifts} == {"arpA", "arpB"}
    for item in shifts:
        band = float(item["metric"].split()[1])
        assert 2000.0 <= band <= 4000.0                                                                     # the +6 dB peak sits at 3 kHz
        assert 3.0 <= item["delta"] <= 7.0 and item["to"] > item["from"]                                     # loudness-matched, so a little under +6
        assert item["status"] not in ("within noise", "same")                                                # it is marked: "changed"
        assert item["status"] == "changed" and item["unit"] == "dB"
    others = [item for item in arp_vs_clean["deltas"] if "third octave" in item["metric"] and not item["metric"].startswith("arp")]
    assert others and all(item["status"] == "within noise" for item in others)                               # no other stem moved


def test_the_boost_also_moves_the_arps_loudness_and_the_top_tier(arp_vs_clean):
    assert delta(arp_vs_clean, "arpA loudness")["delta"] == pytest.approx(2.4, abs=0.6) and delta(arp_vs_clean, "arpA loudness")["status"] == "changed"
    for variation in ("A", "B"):
        top = delta(arp_vs_clean, "T5@" + variation + " integrated loudness")
        assert top["from"] == pytest.approx(-14.0, abs=0.1) and top["delta"] > 0.5 and top["target"] == -14.0 and top["unit"] == "LUFS"
        assert top["status"] == "regressed"                                                                  # further from the -14 LUFS target
        assert delta(arp_vs_clean, "T1@" + variation + " integrated loudness")["status"] == "changed"
        assert "target" not in delta(arp_vs_clean, "T1@" + variation + " integrated loudness")
        peak = delta(arp_vs_clean, "T5@" + variation + " true peak")
        assert peak["delta"] > 0.3 and peak["ceiling"] == -1.0 and peak["to"] < -1.0 and peak["status"] == "within limits"     # closer, still under -1 dBTP
    assert delta(arp_vs_clean, "kick loudness")["status"] == "within noise"
    assert arp_vs_clean["regressed"] == 2 and arp_vs_clean["improved"] == 0
    assert delta(arp_vs_clean, "key@A")["status"] == "same"


def test_deltas_are_sorted_regressions_first_then_the_largest(arp_vs_clean):
    order = {"regressed": 0, "improved": 1, "new": 2, "removed": 2, "changed": 3, "within limits": 4, "within noise": 5, "same": 6}
    keys = [(order[item["status"]], -abs(item.get("delta") or 0)) for item in arp_vs_clean["deltas"]]
    assert keys == sorted(keys)
    assert arp_vs_clean["deltas"][0]["status"] == "regressed" and arp_vs_clean["deltas"][-1]["status"] == "same"
    assert [item["status"] for item in arp_vs_clean["deltas"][:2]] == ["regressed", "regressed"]
    json.dumps(arp_vs_clean, allow_nan=False)


def test_an_identical_take_is_within_noise(same_vs_clean):
    assert {item["status"] for item in same_vs_clean["deltas"]} <= {"within noise", "within limits", "same"}
    assert same_vs_clean["regressed"] == 0 and same_vs_clean["improved"] == 0
    assert all(abs(item.get("delta", 0)) < 0.01 for item in same_vs_clean["deltas"])
    assert delta(same_vs_clean, "T5@A integrated loudness")["status"] == "within noise" and delta(same_vs_clean, "key@A")["status"] == "same"
    assert delta(same_vs_clean, "T5@A true peak")["status"] == "within limits" and delta(same_vs_clean, "mono sub loss@A")["status"] == "within limits"


def test_noise_floor_defaults_and_the_calibration_file(tmp_path):
    assert compare.noise_floor(tmp_path, "lufs_i") == 0.5 and compare.noise_floor(tmp_path, "lufs_i", default=0.8) == 0.8
    path = tmp_path / "calibration" / "noise.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"metrics": {"lufs_i": 0.2, "lra": 0.0, "true_peak_dbtp": None}, "default": 0.4}))
    assert compare.noise_floor(tmp_path, "lufs_i") == 0.2
    assert compare.noise_floor(tmp_path, "lra") == 0.05                                                      # never below 0.05 dB
    assert compare.noise_floor(tmp_path, "true_peak_dbtp") == 0.4 and compare.noise_floor(tmp_path, "band") == 0.4      # unknown metric: the file's default
    path.write_text("{ broken")
    assert compare.noise_floor(tmp_path, "lufs_i") == 0.5
    path.write_text(json.dumps({"metrics": {}}))
    assert compare.noise_floor(tmp_path, "lufs_i") == 0.5


def test_a_measured_noise_floor_decides_what_counts_as_a_change(spec, arp_take, clean_take, tmp_path):
    (tmp_path / "calibration").mkdir()
    noise = {"metrics": {"lufs_i": 3.0, "true_peak_dbtp": 3.0, "lra": 3.0, "part_lufs": 3.0}, "default": 5.0}
    (tmp_path / "calibration" / "noise.json").write_text(json.dumps(noise))
    noisy = compare.compare_takes(arp_take, clean_take, spec, home=tmp_path)
    for variation in ("A", "B"):
        assert delta(noisy, "T5@" + variation + " integrated loudness")["status"] == "within noise"
    assert delta(noisy, "arpA loudness")["status"] == "within noise" and noisy["regressed"] == 0
    third = delta(noisy, "arpA", "Hz third octave (rel.)")
    assert third["delta"] > 3.0 and third["status"] == "within noise"                                        # the file's default (5 dB) covers metrics it does not list
    precise = dict(noise, default=0.5)
    (tmp_path / "calibration" / "noise.json").write_text(json.dumps(precise))
    assert delta(compare.compare_takes(arp_take, clean_take, spec, home=tmp_path), "arpA", "Hz third octave (rel.)")["status"] == "changed"


def test_check_counts_add_fail_and_warn_deltas(spec, same_take, clean_take):
    result = compare.compare_takes(same_take, clean_take, spec, check_counts={"a": {"fail": 0, "warn": 3}, "b": {"fail": 2, "warn": 1}})
    fails, warns = delta(result, "fail checks"), delta(result, "warn checks")
    assert (fails["from"], fails["to"], fails["status"], fails["unit"]) == (2, 0, "improved", "count")
    assert (warns["from"], warns["to"], warns["status"]) == (1, 3, "regressed")
    assert result["improved"] == 1 and result["regressed"] == 1
    same = compare.compare_takes(same_take, clean_take, spec, check_counts={"a": {"fail": 1}, "b": {"fail": 1}})
    assert delta(same, "fail checks")["status"] == "within noise" and delta(same, "warn checks")["status"] == "within noise"


def test_compare_covers_the_variations_both_takes_hold(spec, small_take, clean_take):
    result = compare.compare_takes(small_take, clean_take, spec)                   # an A-only take against an A+B take: just A
    assert result["variations"] == ["A"] and result["variation"] == "A"
    assert delta(result, "T5 integrated loudness")["status"] == "within noise"      # one variation: the metric names carry no suffix
    assert not [item for item in result["deltas"] if "@" in item["metric"]]


def test_compare_can_be_limited_to_one_variation(spec, arp_take, clean_take):
    result = compare.compare_takes(arp_take, clean_take, spec, variation="A")
    assert result["variations"] == ["A"] and result["variation"] == "A" and not [item for item in result["deltas"] if "@" in item["metric"]]
    assert delta(result, "T5 integrated loudness")["status"] == "regressed"
    with pytest.raises(ValueError, match="share no variation"):
        compare.compare_takes(arp_take, clean_take, spec, variation="Z")


def test_takes_without_a_common_variation_cannot_be_compared(spec, small_take):
    only_b = copy.copy(small_take)
    only_b.meta = dict(small_take.meta, variations=["B"], variation="B")
    with pytest.raises(ValueError, match=r"\(B\).*\(A\) share no variation"):
        compare.compare_takes(only_b, small_take, spec)


def test_new_parts_are_listed_as_new(spec, home, small_parts, small_take):
    partial = dict((key, value) for key, value in small_parts.items() if key != "leadA")
    before = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, partial, variations=["A"], mode="files"))
    result = compare.compare_takes(small_take, before, spec)
    new = delta(result, "leadA loudness")
    assert new["status"] == "new" and new["from"] is None and new["to"] == pytest.approx(-21.3, abs=0.5) and "delta" not in new


def test_status_rules():
    assert compare._status("lufs_i", None, 1.0, None, 0.5) == "changed" and compare._status("lufs_i", 1.0, None, None, 0.5) == "changed"
    assert compare._status("lufs_i", -14.0, -14.3, None, 0.5) == "within noise"
    assert compare._status("lufs_i", -15.0, -14.2, -14.0, 0.5) == "improved" and compare._status("lufs_i", -14.2, -15.0, -14.0, 0.5) == "regressed"
    assert compare._status("true_peak_dbtp", -2.0, -1.0, None, 0.5) == "regressed" and compare._status("true_peak_dbtp", -1.0, -2.0, None, 0.5) == "improved"
    assert compare._status("sum_null_db", 40.0, 50.0, None, 0.5) == "improved" and compare._status("key_confidence", 0.9, 0.5, None, 0.1) == "regressed"
    assert compare._status("band", 1.0, 3.0, None, 0.5) == "changed" and compare._status("unknown", 1.0, 3.0, None, 0.5) == "changed"
    assert compare._status("fails", 2, 0, None, 0.0) == "improved" and compare._status("warns", 0, 1, None, 0.0) == "regressed"
    assert compare._status("fails", 1, 1, None, 0.0) == "within noise"


def test_a_ceiling_is_a_limit_not_a_direction():
    status = lambda before, after, noise=0.5: compare._status("true_peak_dbtp", before, after, None, noise, ceiling=-1.0)
    assert status(-2.2, -1.5) == "within limits" and status(-2.2, -2.2) == "within limits" and status(-1.5, -6.0) == "within limits"   # moving under it is fine
    assert status(-2.0, -0.5) == "regressed" and status(-1.0, -0.99) == "regressed" and status(-1.0, -1.0) == "within limits"            # crossing it is not
    assert status(-0.5, -2.0) == "improved" and status(-0.5, -1.0) == "improved"                                                        # coming back under it is
    assert status(-0.5, -0.4) == "within noise" and status(-0.5, 0.5) == "regressed" and status(0.5, -0.5) == "improved"            # both over: by direction
    assert status(None, -2.0) == "changed"


def test_peak_and_mono_sub_regress_only_when_they_cross_their_limits(spec, home, small_parts, small_take):
    hot = dict((key, Audio(value.samples * 10 ** (6.0 / 20.0), value.rate)) for key, value in small_parts.items())
    hot_take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, hot, variations=["A"], mode="files", bit_depth=32))
    worse = compare.compare_takes(hot_take, small_take, spec)
    peak = delta(worse, "T5 true peak")
    assert peak["from"] < -1.0 < peak["to"] and peak["ceiling"] == -1.0 and peak["status"] == "regressed"    # -2.2 dBTP to +3.8 dBTP
    better = delta(compare.compare_takes(small_take, hot_take, spec), "T5 true peak")
    assert better["status"] == "improved"
    sub = delta(worse, "mono sub loss")
    assert sub["ceiling"] == 1.0 and sub["status"] == "within limits"


# ---------------------------------------------------------------------------
# blind_packet
# ---------------------------------------------------------------------------


def test_blind_packet_hides_ids_times_and_statuses(arp_vs_clean, arp_take, clean_take):
    out = compare.blind_packet(arp_vs_clean, arp_take.id, clean_take.id, seed=3)
    text = json.dumps(out["packet"])
    assert arp_take.id not in text and clean_take.id not in text and "neon-140" not in text
    rows = json.dumps(out["packet"]["metrics"])
    for forbidden in ("improved", "regressed", "within noise", "changed", "same", "new", '"status"', '"delta"', '"from"', '"to"', "time", "created"):
        assert forbidden not in rows, forbidden
    assert set(out) == {"packet", "key"} and set(out["packet"]) == {"instructions", "metrics"} and "which you would keep" in out["packet"]["instructions"]
    assert all(set(row) <= {"metric", "X", "Y", "target", "unit"} and {"metric", "X", "Y"} <= set(row) for row in out["packet"]["metrics"])
    assert sorted(out["key"]) == ["X", "Y"] and sorted(out["key"].values()) == sorted([arp_take.id, clean_take.id])


def test_blind_packet_key_maps_x_and_y_back_to_the_takes(arp_vs_clean, arp_take, clean_take):
    seen = set()
    for seed in range(12):
        out = compare.blind_packet(arp_vs_clean, arp_take.id, clean_take.id, seed=seed)
        seen.add(out["key"]["X"])
        by_metric = dict((row["metric"], row) for row in out["packet"]["metrics"])
        for item in arp_vs_clean["deltas"]:
            if item.get("from") is None and item.get("to") is None:
                continue
            row = by_metric[item["metric"]]
            after, before = item.get("to"), item.get("from")                                                 # to = the new take (a), from = the old one (b)
            expected = {out["key"]["X"]: row["X"], out["key"]["Y"]: row["Y"]}
            assert expected[arp_take.id] == after and expected[clean_take.id] == before, (seed, item["metric"])
    assert seen == {arp_take.id, clean_take.id}                                                              # both orders occur


def test_blind_packet_is_deterministic_for_a_seed_and_shuffled(arp_vs_clean, arp_take, clean_take):
    first = compare.blind_packet(arp_vs_clean, arp_take.id, clean_take.id, seed=7)
    again = compare.blind_packet(arp_vs_clean, arp_take.id, clean_take.id, seed=7)
    assert first == again
    metrics = [row["metric"] for row in first["packet"]["metrics"]]
    assert metrics != [item["metric"] for item in arp_vs_clean["deltas"] if item.get("from") is not None or item.get("to") is not None]    # shuffled
    assert sorted(metrics) == sorted(item["metric"] for item in arp_vs_clean["deltas"] if item.get("from") is not None or item.get("to") is not None)
    assert any(compare.blind_packet(arp_vs_clean, "a", "b", seed=s)["key"] != first["key"] for s in range(20))


def test_blind_packet_keeps_the_target_and_unit_but_drops_rows_with_no_values():
    result = {"deltas": [
        {"metric": "T5 integrated loudness", "from": -15.0, "to": -14.0, "delta": 1.0, "target": -14.0, "status": "improved", "unit": "LUFS"},
        {"metric": "gone", "from": None, "to": None, "status": "changed"},
        {"metric": "leadA loudness", "from": None, "to": -20.0, "status": "new"},
        {"metric": "key", "from": "A minor", "to": "A minor", "status": "same"}]}
    packet = compare.blind_packet(result, "new-take", "old-take", seed=0)
    rows = dict((row["metric"], row) for row in packet["packet"]["metrics"])
    assert sorted(rows) == ["T5 integrated loudness", "key", "leadA loudness"]
    assert rows["T5 integrated loudness"]["target"] == -14.0 and rows["T5 integrated loudness"]["unit"] == "LUFS" and "target" not in rows["key"]
    assert {rows["key"]["X"], rows["key"]["Y"]} == {"A minor"}
    lead = rows["leadA loudness"]
    assert sorted([str(lead["X"]), str(lead["Y"])]) == ["-20.0", "None"]


# ---------------------------------------------------------------------------
# compare_spec and compare_reference
# ---------------------------------------------------------------------------


def test_compare_spec_reports_loudness_against_minus_14_and_the_peak_ceiling(spec, clean_take, arp_take):
    result = compare.compare_spec(clean_take, spec)
    rows = dict((item["metric"], item) for item in result["deltas"])
    assert sorted(rows) == ["T5@A integrated loudness", "T5@A key", "T5@A true peak", "T5@B integrated loudness", "T5@B key", "T5@B true peak"]
    loud = rows["T5@A integrated loudness"]
    assert loud["target"] == -14.0 and loud["value"] == pytest.approx(-14.0, abs=0.1) and loud["delta"] == pytest.approx(0.0, abs=0.1) and loud["status"] == "ok"
    peak = rows["T5@A true peak"]
    assert peak["ceiling"] == -1.0 and peak["value"] < -1.0 and peak["delta"] == pytest.approx(peak["value"] + 1.0, abs=0.01) and peak["status"] == "ok"
    assert rows["T5@A key"]["value"] == "A minor" and rows["T5@A key"]["target"] == "A minor"
    hot = dict((item["metric"], item) for item in compare.compare_spec(arp_take, spec)["deltas"])
    assert hot["T5@A integrated loudness"]["status"] == "off target" and hot["T5@A integrated loudness"]["delta"] == pytest.approx(0.83, abs=0.2)
    assert hot["T5@A true peak"]["status"] == "ok"
    json.dumps(result, allow_nan=False)


def test_compare_spec_flags_a_peak_over_the_ceiling_and_follows_the_spec(spec, home, small_parts):
    hot = dict((key, Audio(value.samples * 10 ** (4.0 / 20.0), value.rate)) for key, value in small_parts.items())
    take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, hot, variations=["A"], mode="files"))
    rows = dict((item["metric"], item) for item in compare.compare_spec(take, spec)["deltas"])
    assert rows["T5@A true peak"]["status"] == "over" and rows["T5@A true peak"]["delta"] > 0
    assert rows["T5@A integrated loudness"]["status"] == "off target" and sorted(rows) == ["T5@A integrated loudness", "T5@A key", "T5@A true peak"]
    lenient = copy.deepcopy(spec.data)
    lenient["tolerances"]["lufs_i_lu"] = 6.0
    assert dict((item["metric"], item) for item in compare.compare_spec(take, specs.Spec(lenient))["deltas"])["T5@A integrated loudness"]["status"] == "ok"


def test_compare_reference_is_information_for_shape_and_never_judges_dynamics(spec, small_take):
    metrics = compare.side_metrics(small_take, spec)
    ref = {"bands": dict(metrics["bands"], sub=metrics["bands"]["sub"] + 6.0), "width": metrics["stereo"]["width"] + 0.1, "crest_db": 9.0, "lra": 5.0}
    result = compare.compare_reference(small_take, ref, spec)
    rows = dict((item["metric"], item) for item in result["deltas"])
    assert rows["sub band (rel. loudness)"]["status"] == "different" and rows["sub band (rel. loudness)"]["delta"] == pytest.approx(-6.0, abs=0.01)
    assert rows["low band (rel. loudness)"]["status"] == "information" and rows["low band (rel. loudness)"]["delta"] == pytest.approx(0.0, abs=0.01)
    assert rows["stereo width"]["delta"] == pytest.approx(-0.1, abs=0.01)
    for key in ("crest_db", "lra"):
        assert rows[key]["reference"] == ref[key] and rows[key]["status"].startswith("information only") and "delta" not in rows[key]
    assert result["deltas"][0]["metric"] == "sub band (rel. loudness)"                                       # the largest difference comes first
    assert compare.compare_reference(small_take, {}, spec)["deltas"] == []


def test_side_metrics_shape(spec, small_take, memoised_side_metrics):
    metrics = memoised_side_metrics(small_take, spec)
    assert metrics["top"] == "T5" and sorted(metrics["tiers"]) == ["T1", "T2", "T3", "T4", "T5"]
    assert sorted(metrics["parts"]) == ["arpA", "bassA", "kick", "leadA", "pad", "perc"]
    assert metrics["tiers"]["T5"]["lufs_i"] == pytest.approx(-14.0, abs=0.1) and set(metrics["bands"]) == {"sub", "low", "low_mid", "high_mid", "high"}
    assert metrics["key"]["key"] == "A minor" and 0.0 < metrics["key"]["confidence"] <= 1.0
    assert set(metrics["stereo"]) == {"width", "correlation"} and metrics["mono_sub_loss_db"] == pytest.approx(0.0, abs=0.2) and metrics["crest_db"] > 3.0
    assert "1000" in metrics["third_octave"] and "1000" in metrics["parts"]["arpA"]["third_octave"]
    assert metrics["parts"]["arpA"]["lufs_i"] == pytest.approx(loudness.measure(small_take.part("arpA"), peaks=False)["integrated"], abs=0.01)
    assert compare.side_metrics(small_take, spec, variation="A") == metrics                                  # the memoised function agrees with the real one
