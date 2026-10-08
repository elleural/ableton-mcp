"""Unit tests for ears/report.py: check results, verdict line, compact reports, JSON cleaning, bar.beat.sixteenth notation
(PRD section 9, plan section 5)."""
import copy
import datetime
import json
import math

import numpy as np
import pytest

from ears import report
from ears.report import check


def dump(value):
    """JSON text that refuses nan and infinity, the way a strict client parses it."""
    return json.dumps(value, allow_nan=False)


# ---------------------------------------------------------------------------
# check()
# ---------------------------------------------------------------------------


def test_check_shape_and_omitted_fields():
    plain = check("audio.loudness", "pass")
    assert plain == {"check": "audio.loudness", "status": "pass", "summary": ""}
    full = check("notes.chord_tones", "fail", "bassA", "2 downbeat notes are not chord tones",
                 items=[{"where": "3.1.1", "found": "G1", "expected": "a tone of Dm (D F A)"}], value=0.82, target=1.0,
                 tolerance=0.1, unit="x", detail=None)
    assert list(full)[:4] == ["check", "status", "subject", "summary"]
    assert full["items"] == [{"where": "3.1.1", "found": "G1", "expected": "a tone of Dm (D F A)"}]
    assert full["value"] == 0.82 and full["target"] == 1.0 and full["tolerance"] == 0.1 and full["unit"] == "x"
    assert "detail" not in full                                          # None extras are dropped
    assert "items" not in check("x", "pass", items=[]) and "items" not in check("x", "pass", items=None)


def test_check_keeps_falsy_but_real_values():
    out = check("x", "info", "s", "t", value=0, target=0.0, tolerance=0, flag=False)
    assert out["value"] == 0 and out["target"] == 0.0 and out["tolerance"] == 0 and out["flag"] is False


@pytest.mark.parametrize("status", ["fail", "warn", "info", "pass", "skip"])
def test_check_accepts_every_status(status):
    assert check("a.b", status)["status"] == status


@pytest.mark.parametrize("status", ["error", "ok", "PASS", "", None, "report"])
def test_check_rejects_unknown_status(status):
    with pytest.raises(ValueError, match="status must be one of"):
        check("a.b", status)


def test_check_cleans_nan_inf_and_numpy_scalars():
    out = check("audio.x", "fail", "s", "t",
                items=[{"found": np.float64(1.23456), "n": np.int64(7), "ok": np.bool_(True), "bad": float("nan"),
                        "nested": [np.float32(0.5), float("inf"), (1, 2)]}],
                value=np.float32(0.123456), target=float("-inf"), tolerance=np.nan, extra=np.array([1.0, np.nan]))
    assert out["items"][0]["found"] == 1.235 and out["items"][0]["n"] == 7 and out["items"][0]["ok"] is True
    assert out["items"][0]["bad"] is None and out["items"][0]["nested"] == [0.5, None, [1, 2]]
    assert out["value"] == 0.123 and out["target"] is None and out["tolerance"] is None and out["extra"] == [1.0, None]
    assert isinstance(out["items"][0]["n"], int) and isinstance(out["items"][0]["ok"], bool)
    dump(out)                                                             # strict JSON: no NaN, no Infinity


def test_clean_rounds_recurses_and_stringifies_keys():
    assert report.clean(1.23456789) == 1.235 and report.clean(1.23456789, 5) == 1.23457
    assert report.clean({"a": [float("nan"), np.array([1.0, np.nan]), (1, 2)], 3: np.bool_(True), "z": np.array(5.0)}) == {
        "a": [None, [1.0, None], [1, 2]], "3": True, "z": 5.0}
    assert report.clean(None) is None and report.clean("text") == "text" and report.clean(True) is True and report.clean(10 ** 30) == 10 ** 30
    assert report.clean(np.float64("inf")) is None and report.clean(np.int64(5)) == 5
    assert report.clean(np.array([[1, 2], [3, 4]])) == [[1, 2], [3, 4]]
    assert report.clean([]) == [] and report.clean({}) == {}


def test_violation_maps_a_check_level_to_a_status():
    assert report.violation("fail") == "fail" and report.violation("warn") == "warn"
    assert report.violation("report") == "info" and report.violation("anything else") == "info"


# ---------------------------------------------------------------------------
# verdict, counts, make
# ---------------------------------------------------------------------------


def checks_with(fail=0, warn=0, passed=0, info=0, skip=0):
    out = []
    for status, count in (("fail", fail), ("warn", warn), ("pass", passed), ("info", info), ("skip", skip)):
        out += [check("c.{0}{1}".format(status, n), status, "s{0}".format(n), "summary") for n in range(count)]
    return out


def test_verdict_line_format():
    assert report.verdict(checks_with(fail=1, warn=2, passed=29)) == "1 fail, 2 warn, 29 pass"
    assert report.verdict(checks_with(passed=3)) == "0 fail, 0 warn, 3 pass"
    assert report.verdict([]) == "0 fail, 0 warn, 0 pass"
    assert report.verdict(checks_with(fail=12, warn=10, passed=100)) == "12 fail, 10 warn, 100 pass"   # no pluralisation


def test_verdict_does_not_count_info_and_skip():
    assert report.verdict(checks_with(fail=1, warn=1, passed=1, info=9, skip=4)) == "1 fail, 1 warn, 1 pass"
    assert report.counts(checks_with(fail=1, warn=2, passed=3, info=4, skip=5)) == {"fail": 1, "warn": 2, "info": 4, "pass": 3, "skip": 5}
    assert report.counts([]) == {"fail": 0, "warn": 0, "info": 0, "pass": 0, "skip": 0}


def test_make_builds_a_full_report():
    items = checks_with(fail=1, passed=2)
    made = report.make("audio", "neon-140-AB-0001", items, take="neon-140-AB-0001", tempo=140.0, values={"a": 1}, images=None, mode=None)
    assert made["kind"] == "audio" and made["subject"] == "neon-140-AB-0001"
    assert made["verdict"] == "1 fail, 0 warn, 2 pass" and made["counts"]["fail"] == 1 and made["checks"] == items
    assert made["take"] == "neon-140-AB-0001" and made["tempo"] == 140.0 and made["values"] == {"a": 1}
    assert "images" not in made and "mode" not in made                   # None fields are left out
    assert made["checks"] is not items and len(made["checks"]) == 3


def test_now_is_an_iso_timestamp_with_a_utc_offset():
    stamp = report.now()
    parsed = datetime.datetime.fromisoformat(stamp)
    assert parsed.tzinfo is not None and abs((datetime.datetime.now().astimezone() - parsed).total_seconds()) < 60
    assert "." not in stamp                                               # whole seconds


# ---------------------------------------------------------------------------
# compact()
# ---------------------------------------------------------------------------


def big_report(fails=40, warns=40, infos=40, passes=29, items_per_check=5):
    checks = []
    for i in range(fails):
        checks.append(check("f.{0}".format(i), "fail", "stem{0}".format(i), "bad " * 10,
                            items=[{"where": "{0}.1.1".format(n + 1), "found": "x" * 20, "expected": "y" * 20} for n in range(items_per_check)]))
    for i in range(warns):
        checks.append(check("w.{0}".format(i), "warn", "stem{0}".format(i), "warn " * 10, items=[{"where": "1.1.1"}] * items_per_check))
    for i in range(infos):
        checks.append(check("i.{0}".format(i), "info", "stem{0}".format(i), "info " * 10, value={"k": list(range(30))}, items=[{"a": 1}] * 3))
    checks += [check("p.{0}".format(i), "pass", "stem{0}".format(i), "pass") for i in range(passes)]
    return report.make("audio", "neon-140-AB-0001", checks, take="neon-140-AB-0001", set="neon", tempo=140.0, variation="AB", mode="tap",
                       values=dict(("k{0}".format(i), {"a": list(range(50))}) for i in range(10)),
                       deltas=[{"metric": "m{0}".format(i), "from": 1, "to": 2, "delta": 1, "status": "x"} for i in range(30)],
                       images=["a.png", "b.png"], warnings=["w1", "w2"], deltas_vs="neon-140-AB-0000")


def size(compacted):
    return len(json.dumps(compacted, separators=(",", ":")))


def test_compact_small_report_is_complete():
    items = [check("audio.loudness", "fail", "T5@A", "-12.0 LUFS (target -14 ± 0.5)", value={"lufs_i": -12.0}, target={"lufs_i": -14.0}),
             check("audio.key", "warn", "bassA", "D major heard alone"),
             check("audio.tier_ladder", "info", "tiers@A", "T1 -16.2 < T2 -15.6"),
             check("audio.mono_sub", "pass", "T5@A", "ok"), check("audio.balance", "skip", "tiers", "no envelope")]
    full = report.make("audio", "neon-140-AB-0001", items, take="neon-140-AB-0001", set="neon", tempo=140.0, variation="AB", mode="tap")
    out = report.compact(full, "takes/neon-140-AB-0001/report.json")
    assert out["verdict"] == "1 fail, 1 warn, 1 pass" and out["subject"] == "neon-140-AB-0001" and out["kind"] == "audio"
    assert out["take"] == "neon-140-AB-0001" and out["set"] == "neon" and out["tempo"] == 140.0 and out["mode"] == "tap"
    assert out["fail"] == [{"check": "audio.loudness", "subject": "T5@A", "summary": "-12.0 LUFS (target -14 ± 0.5)",
                            "value": {"lufs_i": -12.0}, "target": {"lufs_i": -14.0}}]
    assert out["warn"] == [{"check": "audio.key", "subject": "bassA", "summary": "D major heard alone"}]
    assert out["info"] == [{"check": "audio.tier_ladder", "subject": "tiers@A", "summary": "T1 -16.2 < T2 -15.6"}]
    assert out["full_report"] == "takes/neon-140-AB-0001/report.json"
    assert "pass" not in out and "skip" not in out and "checks" not in out    # passes are only counted in the verdict
    dump(out)


def test_compact_without_a_stored_verdict_computes_one():
    out = report.compact({"checks": checks_with(fail=1, passed=2), "subject": "x", "kind": "notes"})
    assert out["verdict"] == "1 fail, 0 warn, 2 pass" and "full_report" not in out
    assert report.compact({"subject": "x"})["verdict"] == "0 fail, 0 warn, 0 pass"


def test_compact_full_report_path_may_be_a_path_object(tmp_path):
    assert report.compact(report.make("notes", "s", []), tmp_path / "r.json")["full_report"] == str(tmp_path / "r.json")


def test_compact_extra_fields_are_merged_last():
    out = report.compact(report.make("notes", "s", []), extra={"scope": "live", "note": "n"})
    assert out["scope"] == "live" and out["note"] == "n"


@pytest.mark.parametrize("max_chars", [6000, 4000, 3000, 2000])
def test_compact_stays_under_max_chars(max_chars):
    full = big_report()
    out = report.compact(full, "report.json", max_chars=max_chars)
    assert size(out) <= max_chars
    assert out["verdict"] == "40 fail, 40 warn, 29 pass" and out["full_report"] == "report.json"
    assert out["fail"] and out["warn"]                                   # trimmed, never emptied
    dump(out)


def test_compact_default_budget_is_about_1500_tokens():
    assert report.COMPACT_CHARS == 6000
    out = report.compact(big_report(), "report.json")
    assert size(out) <= report.COMPACT_CHARS
    assert size(out) > 2000                                              # a big report is not squeezed more than needed


def test_compact_trims_items_before_dropping_checks():
    full = big_report(fails=8, warns=8, infos=0, passes=0, items_per_check=5)
    roomy = report.compact(full, max_chars=60000)
    assert len(roomy["fail"]) == 8 and all(len(entry["items"]) == report.MAX_ITEMS_PER_CHECK for entry in roomy["fail"])
    assert roomy["fail"][0]["more_items"] == 2                           # 5 items, 3 shown
    tight = report.compact(full, max_chars=2500)
    assert size(tight) <= 2500
    assert all(len(entry.get("items", [])) <= 1 for entry in tight["fail"])


def test_compact_lists_fails_first_and_keeps_the_first_of_them():
    checks = checks_with(warn=20) + checks_with(fail=12) + checks_with(info=12)
    full = report.make("audio", "t", checks)
    out = report.compact(full)
    keys = list(out)
    assert keys.index("fail") < keys.index("warn") < keys.index("info")
    assert [entry["check"] for entry in out["fail"]] == ["c.fail{0}".format(n) for n in range(report.MAX_CHECKS_PER_STATUS)]
    assert out["fail_more"] == 12 - report.MAX_CHECKS_PER_STATUS and out["warn_more"] == 20 - report.MAX_CHECKS_PER_STATUS
    assert out["info_more"] == 12 - report.MAX_CHECKS_PER_STATUS
    assert "items" not in out["info"][0]                                  # infos are one line each


def test_compact_keeps_some_fails_whatever_the_budget():
    full = big_report()
    out = report.compact(full, max_chars=1000)
    assert len(out["fail"]) >= 2 and out["fail"][0]["check"] == "f.0"
    assert out["verdict"] == "40 fail, 40 warn, 29 pass"


def test_compact_caps_deltas_and_shows_where_they_came_from():
    out = report.compact(big_report())
    assert len(out["deltas"]) <= report.MAX_CHECKS_PER_STATUS and out["deltas_vs"] == "neon-140-AB-0000"
    assert out["deltas"][0]["metric"] == "m0"                             # the first (largest) deltas are the ones kept


def test_compact_keeps_value_and_target_even_when_zero():
    full = report.make("audio", "t", [check("a.b", "fail", "s", "x", value=0, target=0.0)])
    entry = report.compact(full)["fail"][0]
    assert entry["value"] == 0 and entry["target"] == 0.0


def test_compact_does_not_change_the_report_it_is_given():
    full = big_report()
    before = copy.deepcopy(full)
    report.compact(full, max_chars=1500)
    assert full == before


def test_compact_empty_report():
    assert report.compact(report.make("audio", "t", [])) == {"subject": "t", "kind": "audio", "verdict": "0 fail, 0 warn, 0 pass"}


def test_compact_stays_under_max_chars_with_many_warnings():
    full = report.make("audio", "t", checks_with(fail=3, warn=3), warnings=["Not captured at {0} BPM: leadB (track 'leadB' missing); ".format(n) * 6 for n in range(40)])
    assert size(report.compact(full)) <= report.COMPACT_CHARS


# ---------------------------------------------------------------------------
# write()
# ---------------------------------------------------------------------------


def test_write_creates_folders_and_cleans_the_json(tmp_path):
    full = report.make("audio", "t", [check("a.b", "fail", "s", "x", value=float("nan"))], values={"v": np.float64(1.23456), "w": float("inf")})
    target = report.write(full, tmp_path / "takes" / "t" / "report.json")
    assert target == tmp_path / "takes" / "t" / "report.json" and target.is_file()
    text = target.read_text()
    assert text.endswith("\n") and "\n " in text                          # indented
    loaded = json.loads(text)
    assert loaded["checks"][0]["value"] is None and loaded["values"] == {"v": 1.235, "w": None}
    assert loaded["verdict"] == "1 fail, 0 warn, 0 pass"
    assert "NaN" not in text and "Infinity" not in text


# ---------------------------------------------------------------------------
# where() and beats_to_where()
# ---------------------------------------------------------------------------


def test_where_formats_one_based_clip_time():
    assert report.where(3) == "3.1.1" and report.where(3, 2, 4) == "3.2.4" and report.where(3.9, 2.2, 4.7) == "3.2.4"


@pytest.mark.parametrize("beats, expected", [
    (0, "1.1.1"), (0.25, "1.1.2"), (0.5, "1.1.3"), (1, "1.2.1"), (3.75, "1.4.4"),
    (4, "2.1.1"), (4.25, "2.1.2"), (7.75, "2.4.4"), (8, "3.1.1"), (9, "3.2.1"), (12.5, "4.1.3"), (63.99, "16.4.4"), (64, "17.1.1"),
])
def test_beats_to_where_grid_16(beats, expected):
    assert report.beats_to_where(beats) == expected
    assert report.beats_to_where(beats, 4.0, 16) == expected


def test_beats_to_where_floors_to_the_sixteenth_and_absorbs_float_fuzz():
    assert report.beats_to_where(8.1) == "3.1.1"                           # 0.1 beat is inside the first sixteenth
    assert report.beats_to_where(8.26) == "3.1.2"
    assert report.beats_to_where(4 - 1e-10) == "2.1.1"                     # an onset a hair early is still on the barline
    assert report.beats_to_where(3.9999999999) == "2.1.1"
    assert report.beats_to_where(math.nextafter(8.0, 0.0)) == "3.1.1"      # one float below bar 3
    assert report.beats_to_where(math.nextafter(8.25, 0.0)) == "3.1.2"


def test_beats_to_where_other_meters_and_grids():
    assert report.beats_to_where(1.5, 3.0) == "1.2.3"                      # 3/4: bar 1 holds 3 beats
    assert report.beats_to_where(3.0, 3.0) == "2.1.1"
    assert report.beats_to_where(2.0, 6.0) == "1.3.1"
    assert report.beats_to_where(0.5, 4.0, 8) == "1.1.2"                   # grid 8: the unit is an eighth note
    assert report.beats_to_where(3.0, 4.0, 4) == "1.4.1"                   # grid 4: the unit is a beat
    assert report.beats_to_where(1.0, 4.0, 0) == "1.2.1"                   # grid 0 falls back to sixteenths
    assert math.isfinite(float(report.beats_to_where(2.5).split(".")[2]))


def test_beats_to_where_agrees_with_exact_arithmetic_on_random_positions():
    """Positions on a 1/480-beat grid (so bar lines and sixteenths are hit exactly) against Fraction arithmetic."""
    import random
    from fractions import Fraction
    rng = random.Random(5)
    for _ in range(4000):
        per_bar = rng.choice([3, 4, 5, 6])
        grid = rng.choice([4, 8, 16, 32])
        beats = Fraction(rng.randint(0, 64 * 480), 480)
        bar = int(beats // per_bar)
        in_bar = beats - bar * per_bar
        beat = int(in_bar // 1)
        step = int((in_bar - beat) // Fraction(4, grid))
        assert report.beats_to_where(float(beats), float(per_bar), grid) == "{0}.{1}.{2}".format(bar + 1, beat + 1, step + 1), (beats, per_bar, grid)
