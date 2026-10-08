"""Tests for ears/calibration.py: the planted-defect run (PRD 13.2) and the repeatability measurement (PRD 13.1).

`calibration.planted_defects(spec)` renders the NOVA fixture at 48 kHz, plants each PRD defect in turn and analyses every
variant (about a minute). It is the PRD's Phase 1 exit criterion, so it runs here in full, once, and the tests below
read its rows.
"""
import json
import shutil

import numpy as np
import pytest

from ears import calibration, compare, report
from ears import spec as specs
from ears import take as takes
from ears.audio import Audio
from ears.fixtures import audio as fx
from tests.ears.support import memoise_side_metrics

TEMPO = 140.0

# PRD 13.2: defect -> the checks that must catch it (written out here, not read from calibration.py)
PRD_13_2 = {
    "bass_semitone": {"notes.in_key", "notes.chord_tones"},
    "d_major": {"notes.in_key", "notes.chord_tones"},
    "clash": {"notes.clash"},
    "kick_late": {"notes.grid"},
    "lead_no_rests": {"notes.lead_rests"},
    "arp_3k": {"audio.balance", "compare"},
    "sub_out_of_phase": {"audio.mono_sub"},
    "stem_louder": {"audio.tempo_consistency"},
    "master_reverb": {"audio.sum_null"},
    "seam_click": {"file.seam"},
    "unfolded": {"file.seam"},
    "short_5ms": {"file.duration"},
}


@pytest.fixture(scope="module")
def spec():
    return specs.load("nova")


@pytest.fixture(scope="module")
def rows(spec):
    # This is the one slow test of the suite (about 50 s): it renders and analyses the whole planted-defect set at 48 kHz.
    # It is the PRD's Phase 1 exit criterion ("every PRD 13.2 defect caught in fixture form"), so it is not skipped.
    return calibration.planted_defects(spec)


@pytest.fixture(scope="module", autouse=True)
def memoised_side_metrics():
    with memoise_side_metrics() as real:
        yield real


# ---------------------------------------------------------------------------
# planted_defects
# ---------------------------------------------------------------------------


def test_every_planted_defect_row_is_ok(rows):
    failed = [row for row in rows if not row["ok"]]
    assert failed == [], failed
    assert rows and all(set(row) == {"defect", "expected", "caught_by", "ok"} for row in rows)


def test_every_prd_defect_is_planted_and_caught_by_the_check_the_prd_names(rows):
    by_defect = dict((row["defect"], row) for row in rows)
    for defect, required in PRD_13_2.items():
        assert defect in by_defect, defect
        row = by_defect[defect]
        assert required <= set(row["expected"]), (defect, row["expected"])           # the run expects what the PRD says
        assert required <= set(row["caught_by"]), (defect, row["caught_by"])         # and the checks really flagged it
        assert row["ok"] is True


def test_the_clean_fixtures_have_no_fail(rows):
    baselines = [row for row in rows if row["defect"].startswith("none")]
    assert [row["defect"] for row in baselines] == ["none (clean fixture)", "none (clean notes)"]
    assert all(row["ok"] and row["expected"] == [] for row in baselines)
    assert baselines[1]["caught_by"] == []                                         # the clean notes raise nothing at all
    assert all(not name.startswith(("notes.", "file.")) for name in baselines[0]["caught_by"])      # the clean audio trips no notes or file check


def test_rows_are_json_and_markdown_ready(rows):
    json.dumps(rows, allow_nan=False)
    table = calibration.markdown_table(rows)
    lines = table.splitlines()
    assert lines[0] == "| Defect | Must be caught by | Caught by | OK |" and lines[1] == "| --- | --- | --- | --- |"
    assert len(lines) == 2 + len(rows) and all(line.startswith("| ") and line.endswith(" |") for line in lines)
    assert "**no**" not in table and lines[2].startswith("| none (clean fixture) | — |")
    assert any(line.startswith("| arp_3k | audio.balance, compare | ") and line.endswith("| yes |") for line in lines)


def test_the_expected_checks_in_the_module_cover_the_prd_table():
    covered = {}
    covered.update(calibration.AUDIO_EXPECTED)
    covered.update(calibration.NOTES_EXPECTED)
    for defect, required in PRD_13_2.items():
        assert required <= set(covered[defect]), defect


def test_markdown_table_marks_failures_and_empty_cells():
    table = calibration.markdown_table([
        {"defect": "none", "expected": [], "caught_by": [], "ok": True},
        {"defect": "arp_3k", "expected": ["audio.balance", "compare"], "caught_by": ["audio.balance"], "ok": False}])
    assert table.splitlines()[2:] == ["| none | — | — | yes |", "| arp_3k | audio.balance, compare | audio.balance | **no** |"]


# ---------------------------------------------------------------------------
# synthetic envelope
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def small_parts(spec):
    return fx.normalise(fx.render_parts(spec, "neon", TEMPO, variations=["A"]), spec, "neon", TEMPO, variation="A")


def test_the_synthetic_envelope_is_the_fixtures_own_range_widened_by_the_margin(spec, small_parts):
    tight = calibration.synthetic_envelope(small_parts, spec, "neon", TEMPO, margin_db=0.0)
    wide = calibration.synthetic_envelope(small_parts, spec, "neon", TEMPO, margin_db=2.0)
    assert set(tight) == set(wide) and "1000" in tight and "100" in tight
    for band, (low, high) in tight.items():
        assert low <= high and wide[band][0] == pytest.approx(low - 2.0) and wide[band][1] == pytest.approx(high + 2.0)
        assert -60.0 < low                                                              # bands without energy are left out
    assert all(float(band) >= 25.0 for band in tight)


def test_the_synthetic_envelope_accepts_the_clean_fixture_and_rejects_the_boosted_arp(spec, small_parts):
    from ears import analyze
    envelope = calibration.synthetic_envelope(small_parts, spec, "neon", TEMPO)
    boosted, _ = fx.plant(small_parts, "arp_3k", spec, "neon", TEMPO)
    clean_checks = analyze.balance_checks(spec, {"T5@A": _top(small_parts, spec)}, envelope)
    boost_checks = analyze.balance_checks(spec, {"T5@A": _top(boosted, spec)}, envelope)
    assert clean_checks[0]["status"] == "pass" and boost_checks[0]["status"] == "warn"
    assert any(2000 <= float(item["band_hz"]) <= 4000 for item in boost_checks[0]["items"])


def _top(parts, spec):
    from ears import tiers
    sums, _ = tiers.tier_sums(parts, spec, "neon", "A", TEMPO)
    return sums[list(sums)[-1]]


def test_notes_fixture_is_a_clean_snapshot_of_the_set(spec):
    snapshot = calibration.notes_fixture(spec, "neon")
    names = [track["name"] for track in snapshot["tracks"]]
    assert {"kick", "perc", "pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB"} <= set(names)
    assert any(scene["name"] == "NEON-MID" for scene in snapshot["scenes"])


# ---------------------------------------------------------------------------
# repeatability
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def home(tmp_path_factory):
    folder = tmp_path_factory.mktemp("ears-home")
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


@pytest.fixture(scope="module")
def twins(spec, home, small_parts):
    return [takes.load(home, fx.write_take(home, spec, "neon", TEMPO, small_parts, variations=["A"], mode="files", bit_depth=24)) for _ in range(2)]


def test_two_identical_takes_have_no_spread_and_write_noise_json(spec, twins, home):
    result = calibration.repeatability(twins, spec, home=home)
    assert result["takes"] == [item.id for item in twins] and result["default"] == 0.5 and result["created"]
    assert result["metrics"] == {"lufs_i": 0.0, "true_peak_dbtp": 0.0, "lra": 0.0, "part_lufs": 0.0}
    assert result["detail"] and all(value == 0.0 for value in result["detail"].values())
    assert {"lufs_i", "true_peak_dbtp", "lra", "T1_lufs_i", "T4_true_peak_dbtp", "part_lufs:kick", "part_lufs:leadA"} <= set(result["detail"])
    path = home / "calibration" / "noise.json"
    assert result["path"] == str(path) and path.is_file()
    stored = json.loads(path.read_text())
    assert stored["metrics"] == result["metrics"] and stored["takes"] == result["takes"] and stored["detail"] == result["detail"]
    assert path.read_text().endswith("\n") and "NaN" not in path.read_text()


def test_the_noise_file_is_what_compare_reads_as_its_floor(twins, home, spec):
    calibration.repeatability(twins, spec, home=home)
    assert compare.noise_floor(home, "lufs_i") == 0.05                              # a spread of 0 is floored at 0.05 dB
    assert compare.noise_floor(home, "part_lufs") == 0.05 and compare.noise_floor(home, "lra") == 0.05
    assert compare.noise_floor(home, "band") == 0.5                                 # not measured: the file's default
    result = compare.compare_takes(twins[0], twins[1], spec, home=home)
    assert {item["status"] for item in result["deltas"]} <= {"within noise", "within limits", "same"}


def test_no_home_means_no_file(twins, spec):
    result = calibration.repeatability(twins, spec)
    assert "path" not in result and result["metrics"]["lufs_i"] == 0.0


def test_the_spread_is_the_largest_minus_the_smallest_over_all_takes(spec, home, twins, small_parts):
    louder = dict((key, Audio(value.samples * 10 ** (0.3 / 20.0), value.rate)) for key, value in small_parts.items())
    take_loud = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, louder, variations=["A"], mode="files", bit_depth=32))
    result = calibration.repeatability([twins[0], take_loud, twins[1]], spec)                 # the order does not matter: max minus min
    assert result["metrics"]["lufs_i"] == pytest.approx(0.3, abs=0.02)
    assert result["metrics"]["true_peak_dbtp"] == pytest.approx(0.3, abs=0.02)
    assert result["metrics"]["part_lufs"] == pytest.approx(0.3, abs=0.02)
    assert result["metrics"]["lra"] == pytest.approx(0.0, abs=0.02)                           # loudness range does not depend on level
    assert result["detail"]["T1_lufs_i"] == pytest.approx(0.3, abs=0.02)
    assert result["detail"]["part_lufs:kick"] == pytest.approx(0.3, abs=0.02)
    assert result["takes"] == [twins[0].id, take_loud.id, twins[1].id]
    assert json.loads(json.dumps(result, allow_nan=False))["metrics"] == report.clean(result["metrics"])


def test_repeatability_needs_two_takes(twins, spec):
    for few in ([], twins[:1]):
        with pytest.raises(ValueError, match="at least two takes"):
            calibration.repeatability(few, spec)
