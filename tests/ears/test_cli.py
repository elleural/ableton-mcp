"""Tests for ears/cli.py: the `ears` command line (exit status 0 nothing failed, 1 a check failed, 2 usage or input error).

Commands run in-process through `cli.main(argv)` with the output captured; one smoke test runs `python -m ears.cli` as a
subprocess. Delivery files for `ears check` are the fixture stems written as <part>.wav at 48 kHz, 24-bit.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ears import analyze, audio, calibration, cli, ledger
from ears import spec as specs
from ears import take as takes
from ears.fixtures import audio as fx
from ears.fixtures import notes as notes_fx
from tests.ears.support import memoise_side_metrics

TEMPO = 140.0
PARTS = ["kick", "perc", "pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB"]


@pytest.fixture(autouse=True)
def remove_temp_files(tmp_path):
    yield
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture(scope="module")
def spec():
    return specs.load("nova")


@pytest.fixture(scope="module", autouse=True)
def memoised_side_metrics():
    with memoise_side_metrics() as real:
        yield real


@pytest.fixture(scope="module")
def clean_parts(spec):
    return fx.normalise(fx.render_parts(spec, "neon", TEMPO), spec, "neon", TEMPO)


def write_folder(folder, parts):
    folder.mkdir(parents=True, exist_ok=True)
    for part_id, item in parts.items():
        audio.write_wav(folder / (part_id + ".wav"), item.samples, item.rate, 24)
    return folder


@pytest.fixture(scope="module")
def clean_folder(tmp_path_factory, clean_parts):
    folder = write_folder(tmp_path_factory.mktemp("delivery") / "neon140", clean_parts)
    yield folder
    shutil.rmtree(folder.parent, ignore_errors=True)


@pytest.fixture(scope="module")
def short_folder(tmp_path_factory, spec, clean_parts):
    planted, _ = fx.plant(clean_parts, "short_5ms", spec, "neon", TEMPO)       # bassA is 5 ms short
    folder = write_folder(tmp_path_factory.mktemp("delivery") / "neon140", planted)
    yield folder
    shutil.rmtree(folder.parent, ignore_errors=True)


@pytest.fixture(scope="module")
def clean_run(clean_folder, tmp_path_factory):
    """`ears check` on the clean folder, run once for the tests that read its output."""
    capture = tmp_path_factory.mktemp("capture")
    import contextlib
    import io
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(["check", str(clean_folder), "--set", "neon", "--tempo", "140"])
    return code, out.getvalue(), err.getvalue(), capture


def run(capsys, *argv):
    """(exit status, stdout, stderr) of `ears <argv>`; argparse's own exits count as the status too."""
    try:
        code = cli.main(list(argv))
    except SystemExit as exit_:
        code = exit_.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# ---------------------------------------------------------------------------
# ears spec
# ---------------------------------------------------------------------------


def test_spec_prints_what_the_spec_defines(capsys, spec):
    code, out, err = run(capsys, "spec")
    assert code == 0 and err == ""
    data = json.loads(out)
    assert data["name"] == "nova" and data["key"] == "A minor" and data["path"].endswith("nova.spec.json")
    assert sorted(data["sets"]) == ["mainframe", "neon"]
    neon = data["sets"]["neon"]
    assert neon["layout"] == "track" and neon["tempos"][0] == 100.0 and neon["tempos"][-1] == 180.0 and len(neon["tempos"]) == 9
    assert neon["variations"] == {"A": ["Am", "Am", "Dm", "Dm"], "B": ["Am", "F", "Dm", "E"]}
    assert neon["parts"]["bassA"] == {"track": "bassA", "bars": 8} and neon["parts"]["pad"] == {"track": "pad", "bars": 16}
    assert data["sets"]["mainframe"]["parts"]["bassB"]["track"] == "mf_bassB" and data["sets"]["mainframe"]["variations"]["B"] == ["Am", "Dm", "G", "E"]
    assert neon["tiers"]["A"]["T1"] == ["pad", "arpA"] and neon["tiers"]["B"]["T5"][-1] == "leadB"
    assert [band["name"] for band in neon["bands"]] == ["LOW", "MID", "HIGH"]


def test_spec_with_a_spec_file_and_with_bad_names(capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("EARS_SPEC", raising=False)
    custom = tmp_path / "mine.spec.json"
    data = json.loads(specs.BUNDLED_DIR.joinpath("nova.spec.json").read_text())
    data["name"] = "mine"
    custom.write_text(json.dumps(data))
    code, out, _ = run(capsys, "--spec", str(custom), "spec")
    assert code == 0 and json.loads(out)["name"] == "mine" and json.loads(out)["path"] == str(custom)
    code, out, err = run(capsys, "--spec", "nope", "spec")
    assert code == 2 and out == "" and err.startswith("ears: No spec file 'nope'") and "nova" in err
    monkeypatch.setenv("EARS_SPEC", str(custom))
    assert json.loads(run(capsys, "spec")[1])["name"] == "mine"                        # $EARS_SPEC is the default
    assert json.loads(run(capsys, "--spec", "nova", "spec")[1])["name"] == "nova"      # the option wins


def test_usage_errors_exit_with_status_2(capsys):
    code, out, err = run(capsys)
    assert code == 2 and "arguments are required: command" in err
    code, out, err = run(capsys, "frobnicate")
    assert code == 2 and "invalid choice" in err
    code, out, err = run(capsys, "check", "somewhere")
    assert code == 2 and "--set" in err and "--tempo" in err
    code, out, err = run(capsys, "check", "somewhere", "--set", "neon", "--tempo", "fast")
    assert code == 2 and "invalid float value" in err


def test_version(capsys):
    code, out, err = run(capsys, "--version")
    assert code == 0 and out.strip() == "ears 0.1.0"


# ---------------------------------------------------------------------------
# ears check
# ---------------------------------------------------------------------------


def test_check_a_clean_folder_exits_0_and_prints_a_compact_report(clean_run, clean_folder):
    code, out, err = clean_run[:3]
    assert code == 0 and err == ""
    result = json.loads(out)
    assert result["subject"] == str(clean_folder) and result["kind"] == "audio" and result["set"] == "neon" and result["tempo"] == 140.0
    assert result["verdict"].startswith("0 fail, ") and "fail" not in result
    assert len(out) < 7000                                                                # a compact report, not the full one
    assert "full_report" not in result                                                    # nothing is written for `check`
    assert sorted(os.listdir(clean_folder)) == sorted(part + ".wav" for part in PARTS)    # the folder is untouched


def test_check_a_folder_with_a_defect_exits_1(capsys, short_folder):
    code, out, err = run(capsys, "check", str(short_folder), "--set", "neon", "--tempo", "140")
    assert code == 1 and err == ""
    result = json.loads(out)
    assert result["verdict"].startswith("1 fail")
    assert [(item["check"], item["subject"]) for item in result["fail"]] == [("file.duration", "bassA")]
    assert "-5.0" in result["fail"][0]["summary"] or "-4.99" in result["fail"][0]["summary"]


def test_check_without_strict_asks_the_measurement_ear_for_no_file_checks(capsys, short_folder, monkeypatch):
    seen = []

    def fake(spec, set_name, tempo, files, strict_mode=True, **kwargs):
        seen.append((set_name, tempo, sorted(files), strict_mode))
        return {"kind": "audio", "subject": "files", "checks": [], "verdict": "0 fail, 0 warn, 0 pass", "counts": {"fail": 0}}

    monkeypatch.setattr(cli.analyze, "analyze_files", fake)
    assert run(capsys, "check", str(short_folder), "--set", "NEON", "--tempo", "140", "--no-strict")[0] == 0
    assert run(capsys, "check", str(short_folder), "--set", "neon", "--tempo", "127.5")[0] == 0
    assert seen == [("NEON", 140.0, sorted(PARTS), False), ("neon", 127.5, sorted(PARTS), True)]       # the tempo is a float, strict is the default


def test_check_without_part_files_is_a_usage_error(capsys, tmp_path):
    code, out, err = run(capsys, "check", str(tmp_path), "--set", "neon", "--tempo", "140")
    assert code == 2 and out == "" and "No part files (e.g. bassA.wav)" in err
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "unrelated.wav").write_bytes(b"RIFF")
    (tmp_path / "bassA.mp3").write_bytes(b"x")                                              # a known name but not a .wav
    code, _, err = run(capsys, "check", str(tmp_path), "--set", "neon", "--tempo", "140")
    assert code == 2 and "No part files" in err


def test_check_with_an_unknown_set_or_a_missing_folder(capsys, tmp_path):
    code, _, err = run(capsys, "check", str(tmp_path), "--set", "tetris", "--tempo", "140")
    assert code == 2 and "no set 'tetris'" in err
    code, _, err = run(capsys, "check", str(tmp_path / "nowhere"), "--set", "neon", "--tempo", "140")
    assert code == 2 and "No part files" in err


def test_check_prints_json_either_way(capsys, tmp_path, clean_run):
    code, out, _ = run(capsys, "--json", "check", str(tmp_path / "empty"), "--set", "neon", "--tempo", "140")
    assert code == 2 and out == ""                                                          # nothing to print for an input error
    assert json.loads(clean_run[1])["kind"] == "audio"


def test_check_part_file_names_are_the_spec_part_ids(capsys, tmp_path, clean_parts):
    folder = write_folder(tmp_path / "mixed", {"kick": clean_parts["kick"], "kick_old": clean_parts["kick"], "levelup_fill": clean_parts["kick"]})
    known = cli._part_files(folder, specs.load("nova"), "neon")
    assert sorted(known) == ["kick", "levelup_fill"]                                      # parts and fills; anything else is ignored
    assert known["kick"] == str(folder / "kick.wav")
    assert cli._part_files(folder, specs.load("nova"), "mainframe") == known              # fills are named per set, ids are shared


# ---------------------------------------------------------------------------
# takes: analyze, compare, keep, ledger
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def world(tmp_path_factory, spec, clean_parts):
    home = tmp_path_factory.mktemp("ears-home")
    small = fx.normalise(fx.render_parts(spec, "neon", TEMPO, variations=["A"]), spec, "neon", TEMPO, variation="A")
    ids = [fx.write_take(home, spec, "neon", TEMPO, small, variations=["A"], bit_depth=24) for _ in range(2)]
    yield home, ids
    shutil.rmtree(home, ignore_errors=True)


def test_analyze_a_take_by_id_writes_the_full_report_and_prints_the_compact_one(capsys, world):
    home, ids = world
    code, out, err = run(capsys, "--home", str(home), "analyze", ids[0])
    assert code == 0 and err == ""
    result = json.loads(out)
    assert result["subject"] == ids[0] and result["take"] == ids[0] and result["verdict"].startswith("0 fail")
    assert result["full_report"] == str(home / "takes" / ids[0] / "report.json")
    full = json.loads((home / "takes" / ids[0] / "report.json").read_text())
    assert full["kind"] == "audio" and full["verdict"] == result["verdict"] and len(full["checks"]) > len(result.get("info", [])) + 5
    assert not [item for item in full["checks"] if item["check"].startswith("file.")]


def test_analyze_by_folder_path_and_strict(capsys, world):
    home, ids = world
    folder = home / "takes" / ids[1]
    code, out, _ = run(capsys, "analyze", str(folder), "--strict")                           # no --home: the folder path is enough
    assert code == 0
    result = json.loads(out)
    assert "images" not in result and result["full_report"] == str(folder / "report-strict.json")    # a strict run does not overwrite the plain report
    full = json.loads((folder / "report-strict.json").read_text())
    assert {item["check"] for item in full["checks"]} >= {"file.duration", "file.seam", "file.format"}
    assert not (folder / "report.json").exists()


def test_analyze_passes_strict_and_images_through(capsys, world, monkeypatch):
    home, ids = world
    seen = []

    def fake(take, spec, strict_mode=False, images_dir=None, **kwargs):
        seen.append((take.id, strict_mode, images_dir))
        return {"kind": "audio", "subject": take.id, "checks": [], "verdict": "0 fail, 0 warn, 0 pass", "counts": {"fail": 0}, "images": []}

    monkeypatch.setattr(cli.analyze, "analyze_take", fake)
    assert run(capsys, "--home", str(home), "analyze", ids[0])[0] == 0
    assert run(capsys, "--home", str(home), "analyze", ids[0], "--strict", "--images")[0] == 0
    assert seen == [(ids[0], False, None), (ids[0], True, home / "takes" / ids[0] / "images")]
    assert (home / "takes" / ids[0] / "report.json").is_file() and (home / "takes" / ids[0] / "report-strict.json").is_file()


def test_analyze_unknown_take_exits_2(capsys, world):
    home, _ = world
    code, out, err = run(capsys, "--home", str(home), "analyze", "neon-999-A-0042")
    assert code == 2 and out == "" and "No take 'neon-999-A-0042'" in err


def test_analyze_exits_1_when_a_check_fails(capsys, tmp_path, spec, clean_parts):
    hot = dict((key, audio.Audio(value.samples * 10 ** (6.0 / 20.0), value.rate)) for key, value in clean_parts.items() if not key.endswith("B"))
    home = tmp_path / "home"
    take_id = fx.write_take(home, spec, "neon", TEMPO, hot, variations=["A"], mode="files", bit_depth=24)
    code, out, _ = run(capsys, "--home", str(home), "analyze", take_id)
    assert code == 1 and [item["check"] for item in json.loads(out)["fail"]] == ["audio.loudness"]


def test_keep_ledger_and_compare_with_best(capsys, world, monkeypatch):
    home, ids = world
    code, out, _ = run(capsys, "--home", str(home), "ledger")
    assert code == 0 and json.loads(out) == []                                                # nothing recorded yet
    code, out, err = run(capsys, "--home", str(home), "compare", ids[1], "best")
    assert code == 2 and out == "" and "No best take for neon-140-A" in err
    code, out, _ = run(capsys, "--home", str(home), "keep", ids[0])
    assert code == 0 and json.loads(out) == {"kept": ids[0], "key": "neon-140-A"}
    assert ledger.best(home, "neon", 140, "A") == ids[0]
    code, out, _ = run(capsys, "--home", str(home), "compare", ids[1], "best")
    result = json.loads(out)
    assert code == 0 and result["a"] == ids[1] and result["b"] == ids[0] and result["variation"] == "A"
    assert {item["status"] for item in result["deltas"]} <= {"within noise", "within limits", "same"}
    # the environment variable names the home too, and --home wins over it
    monkeypatch.setenv("EARS_HOME", str(home))
    assert run(capsys, "compare", ids[1], ids[0])[0] == 0
    ledger.record_take(home, {"id": ids[0], "set": "neon", "tempo": 140.0, "variation": "A", "mode": "tap", "note": "first"}, verdict="0 fail")
    ledger.record_take(home, {"id": ids[1], "set": "neon", "tempo": 140.0, "variation": "A", "mode": "tap", "note": "second"})
    rows = json.loads(run(capsys, "ledger")[1])
    assert [row["id"] for row in rows] == [ids[1], ids[0]] and [row["best"] for row in rows] == [False, True]
    assert json.loads(run(capsys, "ledger", "--limit", "1")[1])[0]["id"] == ids[1]
    assert json.loads(run(capsys, "ledger", "--set", "mainframe")[1]) == []
    assert json.loads(run(capsys, "ledger", "--set", "neon")[1])[1]["verdict"] == "0 fail"
    elsewhere = home.parent / "other-home"
    assert json.loads(run(capsys, "--home", str(elsewhere), "ledger")[1]) == []


def test_compare_against_the_spec_and_blind(capsys, world):
    home, ids = world
    code, out, _ = run(capsys, "--home", str(home), "compare", ids[0], "spec")
    rows = dict((item["metric"], item) for item in json.loads(out)["deltas"])
    assert code == 0 and rows["T5@A integrated loudness"]["target"] == -14.0 and rows["T5@A integrated loudness"]["status"] == "ok"
    code, out, _ = run(capsys, "--home", str(home), "compare", ids[0], ids[1], "--blind")
    packet = json.loads(out)
    assert code == 0 and sorted(packet) == ["instructions", "key_file", "metrics"]
    key = json.loads(open(packet["key_file"]).read())
    assert sorted(key) == ["X", "Y"] and sorted(key.values()) == sorted(ids[:2])
    assert ids[0] not in out and ids[1] not in out and all("status" not in row and "delta" not in row for row in packet["metrics"])


def test_compare_unknown_take_exits_2(capsys, world):
    home, ids = world
    code, _, err = run(capsys, "--home", str(home), "compare", ids[0], "neon-1-A-0001")
    assert code == 2 and "No take 'neon-1-A-0001'" in err


def test_keep_unknown_take_exits_2(capsys, tmp_path):
    code, out, err = run(capsys, "--home", str(tmp_path), "keep", "neon-140-A-0001")
    assert code == 2 and out == "" and "No take" in err


def test_ledger_on_an_empty_home_is_an_empty_list(capsys, tmp_path, monkeypatch):
    code, out, err = run(capsys, "--home", str(tmp_path / "fresh"), "ledger")
    assert (code, json.loads(out), err) == (0, [], "")
    monkeypatch.delenv("EARS_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert run(capsys, "ledger")[1] == "[]\n"                                                  # no --home, no $EARS_HOME: the current directory
    assert not (tmp_path / "ledger.jsonl").exists()                                            # reading creates nothing


# ---------------------------------------------------------------------------
# notes, calibrate, acceptance
# ---------------------------------------------------------------------------


def test_notes_exit_status_follows_the_notes_checks(capsys, tmp_path, spec):
    snapshot = notes_fx.clean_snapshot(spec, "neon")
    clean = tmp_path / "clean.json"
    clean.write_text(json.dumps(snapshot))
    code, out, err = run(capsys, "notes", str(clean))
    assert code == 0 and err == "" and json.loads(out)["verdict"].startswith("0 fail")
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(notes_fx.plant(snapshot, "bass_semitone")))
    code, out, _ = run(capsys, "notes", str(broken), "--set", "neon")
    checks = {item["check"] for item in json.loads(out)["fail"]}
    assert code == 1 and {"notes.in_key", "notes.chord_tones"} <= checks
    code, out, _ = run(capsys, "notes", str(clean), "--band", "MID")
    assert code == 0 and json.loads(out)["band"] == "MID" if "band" in json.loads(out) else code == 0


def test_notes_input_errors_exit_2(capsys, tmp_path):
    code, _, err = run(capsys, "notes", str(tmp_path / "absent.json"))
    assert code == 2 and "No such file" in err
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json")
    code, _, err = run(capsys, "notes", str(bad))
    assert code == 2 and err.startswith("ears: ")
    good = tmp_path / "good.json"
    good.write_text("{}")
    code, _, err = run(capsys, "notes", str(good), "--set", "tetris")
    assert code == 2 and "no set 'tetris'" in err


def test_calibrate_prints_the_table_and_exits_by_the_rows(capsys, monkeypatch):
    seen = {}

    def fake(spec, set_name, tempo):
        seen.update(set=set_name, tempo=tempo, spec=spec.name)
        return [{"defect": "arp_3k", "expected": ["audio.balance"], "caught_by": ["audio.balance"], "ok": True}]

    monkeypatch.setattr(calibration, "planted_defects", fake)
    code, out, _ = run(capsys, "calibrate")
    assert code == 0 and "| arp_3k | audio.balance | audio.balance | yes |" in out and seen == {"set": "neon", "tempo": 140.0, "spec": "nova"}
    code, out, _ = run(capsys, "--json", "calibrate", "--set", "mainframe", "--tempo", "120")
    assert code == 0 and json.loads(out)[0]["defect"] == "arp_3k" and seen["set"] == "mainframe" and seen["tempo"] == 120.0
    monkeypatch.setattr(calibration, "planted_defects", lambda *args: [{"defect": "x", "expected": ["a"], "caught_by": [], "ok": False}])
    code, out, _ = run(capsys, "calibrate")
    assert code == 1 and "**no**" in out


MINI_SPEC = {
    "name": "mini", "key": "A minor", "progressions": {"A": ["Am", "Dm"]},
    "stems": {"kick": {"bars": 2, "pitched": False}, "pad": {"bars": 4}, "bass": {"bars": 2, "variations": ["A"]}},
    "tiers": {"T1": ["pad"], "T2": ["bass"], "T3": ["kick"]},
    "sets": {"mini": {"tempos": [120, 140], "variations": {"A": "A"}, "tracks": "{stem}{variation}"}},
    "targets": {"lufs_i": -14, "true_peak_dbtp": -1, "tail_ms": 50, "sample_rate": 48000, "bit_depth": 24, "channels": 2,
                "bass_crossover_hz": 120, "crossfade_ms": 10},
    "tolerances": {"mono_sub_db": 3.0},               # the short synthetic pad is wider in the lows than the full-length one
}


@pytest.fixture(scope="module")
def mini(tmp_path_factory):
    """A small spec (one set, two tempos, three stems) and clean delivery folders for it: <root>/mini/<bpm>/<part>.wav."""
    folder = tmp_path_factory.mktemp("acceptance")
    path = folder / "mini.spec.json"
    path.write_text(json.dumps(MINI_SPEC))
    small = specs.Spec(MINI_SPEC)
    parts = dict((tempo, fx.normalise(fx.render_parts(small, "mini", float(tempo)), small, "mini", float(tempo))) for tempo in (120, 140))
    return small, path, parts


def masters(root, parts, tempos=(120, 140), edit=None):
    for tempo in tempos:
        folder = root / "mini" / str(tempo)
        folder.mkdir(parents=True)
        for part_id, item in (edit(tempo, parts[tempo]) if edit else parts[tempo]).items():
            audio.write_wav(folder / (part_id + ".wav"), item.samples, item.rate, 24)
    return root


def test_acceptance_over_clean_masters_exits_0(capsys, mini, tmp_path):
    small, path, parts = mini
    root = masters(tmp_path / "clean", parts)
    code, out, err = run(capsys, "--spec", str(path), "acceptance", str(root))
    lines = out.splitlines()
    assert code == 0 and err == "" and len(lines) == 3
    assert lines[0].startswith("mini         120  0 fail, ") and lines[1].startswith("mini         140  0 fail, ")
    assert lines[2] == "0 of 2 tempo folders failed"


def test_acceptance_lists_each_fail_under_its_tempo(capsys, mini, tmp_path):
    small, path, parts = mini

    def short_bass(tempo, stems):
        if tempo != 140:
            return stems
        return dict(stems, bassA=audio.Audio(stems["bassA"].samples[:-int(0.005 * 48000)], 48000))

    root = masters(tmp_path / "short", parts, edit=short_bass)
    code, out, _ = run(capsys, "--spec", str(path), "acceptance", str(root))
    lines = out.splitlines()
    assert code == 1 and lines[0].startswith("mini         120  0 fail, ") and lines[1].startswith("mini         140  1 fail, ")
    assert lines[2].startswith("    file.duration bassA: ") and "-5.0" in lines[2] and lines[-1] == "1 of 2 tempo folders failed"


def test_acceptance_checks_loudness_consistency_across_the_tempo_folders(capsys, mini, tmp_path):
    small, path, parts = mini

    def louder_bass(tempo, stems):
        if tempo != 140:
            return stems
        return dict(stems, bassA=audio.Audio(stems["bassA"].samples * 10 ** (4.0 / 20.0), 48000))

    root = masters(tmp_path / "uneven", parts, edit=louder_bass)
    code, out, _ = run(capsys, "--spec", str(path), "--json", "acceptance", str(root))
    data = json.loads(out)
    assert code == 1 and data["failed"] == 2
    for row in data["rows"]:
        assert any(line.startswith("audio.tempo_consistency bassA: ") for line in row["fails"]), row


def test_acceptance_reports_missing_and_unreadable_folders(capsys, mini, tmp_path):
    small, path, parts = mini
    root = masters(tmp_path / "partial", parts, tempos=(140,))                                      # no 120 folder at all
    (root / "mini" / "120").mkdir()
    code, out, _ = run(capsys, "--spec", str(path), "acceptance", str(root))
    lines = out.splitlines()
    assert code == 1 and lines[0].startswith("mini         120  fail: no part files in ") and lines[0].endswith(str(root / "mini" / "120"))
    assert lines[1].startswith("mini         140  0 fail") and lines[-1] == "1 of 2 tempo folders failed"
    (root / "mini" / "120" / "kick.wav").write_bytes(b"this is not a wav file")
    code, out, _ = run(capsys, "--spec", str(path), "acceptance", str(root))
    assert code == 1 and out.splitlines()[0].startswith("mini         120  fail: unreadable file (")
    assert out.splitlines()[1].startswith("mini         140  0 fail")                                    # the other tempo is still analysed


def test_acceptance_with_the_bundled_spec_needs_all_thirteen_folders(capsys, tmp_path):
    code, out, _ = run(capsys, "acceptance", str(tmp_path))
    lines = out.splitlines()
    assert code == 1 and len(lines) == 14 and lines[-1] == "13 of 13 tempo folders failed"
    assert [line.split()[0] for line in lines[:13]] == ["neon"] * 9 + ["mainframe"] * 4
    assert all("fail: no part files in" in line for line in lines[:13])
    code, out, _ = run(capsys, "--json", "acceptance", str(tmp_path / "absent"))
    assert code == 1 and json.loads(out)["failed"] == 13 and len(json.loads(out)["rows"]) == 13


# ---------------------------------------------------------------------------
# as a program
# ---------------------------------------------------------------------------


def test_python_dash_m_runs_the_cli():
    done = subprocess.run([sys.executable, "-m", "ears.cli", "spec"], capture_output=True, text=True, timeout=120, cwd=str(Path(__file__).resolve().parents[2]))
    assert done.returncode == 0 and json.loads(done.stdout)["name"] == "nova"


def test_the_console_script_is_declared():
    tomllib = pytest.importorskip("tomllib")                                      # Python 3.11 and later
    project = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text())
    assert project["project"]["scripts"]["ears"] == "ears.cli:main" and cli.main is not None
    assert "ears*" in project["tool"]["setuptools"]["packages"]["find"]["include"]
    assert project["tool"]["setuptools"]["package-data"]["ears"] == ["specs/*.json"]
