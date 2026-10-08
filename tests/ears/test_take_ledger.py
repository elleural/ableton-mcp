"""Unit tests for ears/take.py (take folders, ingestion of a capture job, hand-exported takes) and ears/ledger.py (the
append-only history, verdict folding, best pointers).

Ingestion is tested with fake recordings: float or PCM WAV files whose content is noise plus impulses at known
positions, so the tests can tell exactly which sample of the recording ended up where in the take. Nothing here needs
Live or ffmpeg.
"""
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

from ears import analyze, audio, ledger, plan as planner, tiers
from ears import spec as specs
from ears import take as takes
from ears.take import TakeError
from tests.ears import nova_snapshot as ns

RATE = 48000
SAMPLES_PER_KEY = 37          # impulse spacing between the keys of one pass
PART_IDS = list(ns.TRACKS)


@pytest.fixture(scope="module")
def spec():
    return specs.load("nova")


def make_plan(spec, tempos=(120.0,), mode="tap", bars=1, snapshot=None, **kwargs):
    return planner.plan_capture(spec, snapshot or ns.nova_snapshot(), "neon", tempos=list(tempos), mode=mode, bars=bars, **kwargs)


def write_recordings(plan, folder, rate=RATE, depth=24, offsets=None, mix_gain=1.001, drop=(), cut_short=None, steady=True, seed=3):
    """Fake recordings for every pass of `plan`; returns (job, markers).

    Every recorded key gets noise (sigma 0.01) and, inside the window its cut keeps, an impulse of 0.25 at
    `cut start + 1000 + 37 * (position of the key in the pass)`. A decoy impulse (0.7) sits 500 frames before the cut
    start (it must not reach the take); on the first key of a pass a tail marker (0.5) sits 5 frames before the end of
    the kept window and an overrun marker (0.8) 5 frames after it (it must not reach the take either). The mix is the
    sum of the other recordings times `mix_gain`. Each file starts `offsets[key]` samples before clip beat 0.
    markers[(pass number, key)] = {"index": where the impulse must land in the cut file, "tail_index": ..., "frames": ...}.
    cut_short[key] = N makes that recording end N samples before the end of the window its cut keeps.
    """
    offsets = offsets or {}
    rng = np.random.default_rng(seed)
    results, markers = [], {}
    tail_s = 0.05
    for number, item in enumerate(plan["passes"]):
        tempo = item["tempo"]
        rate_beat = rate * 60.0 / tempo
        length = int(round(item["beats"] * rate_beat)) + rate // 2
        keys = [entry["key"] for entry in item["record"]]
        cuts = dict((cut["key"], cut) for cut in item["cuts"])
        ideal = {}
        for position, key in enumerate(keys):
            if key == "mix" and any(other != "mix" for other in keys):
                continue
            signal = rng.standard_normal((length, 2)) * 0.01
            cut = cuts[key]
            first = int(round(cut["start_beats"] * rate_beat))
            frames = int(round(cut["length_beats"] * rate_beat + tail_s * rate))
            index = 1000 + SAMPLES_PER_KEY * position
            signal[first + index, 0] += 0.25
            signal[first - 500 + SAMPLES_PER_KEY * position, 0] += 0.7
            if position == 0:
                signal[first + frames - 5, 0] += 0.5
                signal[first + frames + 5, 0] += 0.8
            ideal[key] = signal
            markers[(number, key)] = {"index": index, "tail_index": frames - 5, "frames": frames, "window_end": first + frames}
        if "mix" not in ideal:
            ideal["mix"] = mix_gain * sum(ideal.values())
        files = []
        for entry in item["record"]:
            key = entry["key"]
            if key in drop:
                continue
            offset = offsets.get(key, 0)
            signal = np.vstack([np.zeros((offset, 2)), ideal[key]])
            if cut_short and key in cut_short:                                  # the recording stops that many samples early
                signal = signal[:offset + markers[(number, key)]["window_end"] - cut_short[key]]
            path = Path(folder) / "p{0}_{1}.wav".format(number, key.replace("@", "_"))
            audio.write_wav(path, signal, rate, depth)
            files.append({"key": key, "file_path": str(path), "offset_samples": offset, "source": entry["source"], "tap": entry.get("tap")})
        results.append({"tempo": tempo, "tempo_steady": steady, "files": files})
    job = {"id": "capture-1", "live_version": "12.4.6", "set": {"name": "NOVA", "path": None}, "warnings": ["job warning"], "results": results}
    return job, markers


def peak_index(item, channel=0):
    return int(np.argmax(item.samples[:, channel]))


@pytest.fixture(autouse=True)
def remove_temp_files(tmp_path):
    """Fake recordings and takes are tens of megabytes a test."""
    yield
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture()
def home(tmp_path):
    return tmp_path / "ears-home"


@pytest.fixture()
def raw(tmp_path):
    folder = tmp_path / "raw"
    folder.mkdir()
    return folder


# ---------------------------------------------------------------------------
# ingest: folder layout and provenance
# ---------------------------------------------------------------------------


def test_ingest_builds_the_take_folder(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw)
    snapshot = ns.nova_snapshot()
    ids = takes.ingest(job, plan, spec, home, snapshot=snapshot, note="first take")
    assert ids == ["neon-120-AB-0001"]
    folder = home / "takes" / ids[0]
    names = sorted(str(path.relative_to(folder)) for path in folder.rglob("*") if path.is_file())
    assert names == sorted(["take.json", "snapshot.json", "mix.wav", "returns/A-Reverb.wav", "returns/B-Delay.wav"] +
                           ["stems/{0}.wav".format(part) for part in PART_IDS])
    meta = json.loads((folder / "take.json").read_text())
    assert meta["id"] == ids[0] and meta["set"] == "neon" and meta["tempo"] == 120.0 and meta["variation"] == "AB" and meta["variations"] == ["A", "B"]
    assert meta["mode"] == "tap" and meta["bars"] == 1 and meta["band"] == "LOW" and meta["spec"] == "nova" and meta["note"] == "first take"
    assert meta["live_version"] == "12.4.6" and meta["live_set"] == {"name": "NOVA", "path": None} and meta["capture_job"] == "capture-1"
    assert meta["sample_rate"] == 48000 and meta["gain_applied_db"] == 0.0 and meta["ears"] and meta["created"]
    assert list(meta["parts"]) == PART_IDS and list(meta["returns"]) == ["A-Reverb", "B-Delay"] and len(meta["mixes"]) == 1
    kick = meta["parts"]["kick"]
    assert kick["file"] == "stems/kick.wav" and kick["source"] == "kick" and kick["tap"] == "Post Mixer" and kick["pass"] == "120 BPM A+B tap"
    assert kick["bars"] == 2 and kick["track"] == "kick" and kick["start_beats"] == 4.0 and kick["length_beats"] == 4.0
    assert meta["mixes"][0]["source"] == "resampling" and meta["mixes"][0]["variations"] == ["A", "B"] and meta["mixes"][0]["file"] == "mix.wav"
    assert meta["returns"]["A-Reverb"]["variations"] == ["A", "B"]
    assert meta["clips"]["kick"] == {"track": "kick", "slot": 1, "scene": "NEON-LOW"}                 # 120 BPM: the LOW band's drums
    assert meta["passes"] == [{"label": "120 BPM A+B tap", "tempo": 120.0, "beats": pytest.approx(8.1), "cycle_bars": 1, "variations": ["A", "B"]}]
    assert json.loads((folder / "snapshot.json").read_text()) == snapshot


def test_ingest_writes_float_wavs_without_requantising(spec, home, raw):
    plan = make_plan(spec)
    job, _ = write_recordings(plan, raw)
    ids = takes.ingest(job, plan, spec, home)
    for path in (home / "takes" / ids[0]).rglob("*.wav"):
        item = audio.read_wav(path)
        assert item.format == "float" and item.bit_depth == 32 and item.rate == 48000 and item.channels == 2
    assert not (home / "takes" / ids[0] / "snapshot.json").exists()                                    # none was given


def impulses(cut):
    """Indices of the 0.25 impulses (0.19..0.31) in channel 0 of a cut file."""
    column = cut.samples[:, 0]
    return np.flatnonzero((column > 0.19) & (column < 0.31)).tolist()


@pytest.mark.parametrize("tempo", [120.0, 130.0, 140.0])
def test_cut_windows_land_every_impulse_at_the_right_sample(spec, home, raw, tempo):
    """Recordings with offsets 0, 37 and 100: an impulse N samples into the kept cycle is at index N of the cut."""
    plan = make_plan(spec, tempos=[tempo])
    keys = [entry["key"] for entry in plan["passes"][0]["record"]]
    job, markers = write_recordings(plan, raw, offsets={"kick": 100, "bassA": 100, "A-Reverb": 100, "pad": 37})
    item = takes.load(home, takes.ingest(job, plan, spec, home)[0])
    expected_frames = int(round(4 * RATE * 60.0 / tempo + 0.05 * RATE))
    cuts = dict(item.parts())
    cuts.update(item.returns())
    assert sorted(cuts) == sorted(key for key in keys if key != "mix")
    for key, cut in cuts.items():
        assert cut.frames == expected_frames, key
        assert impulses(cut) == [1000 + SAMPLES_PER_KEY * keys.index(key)] == [markers[(0, key)]["index"]], key


def test_nothing_from_the_first_cycle_or_after_the_window_reaches_the_cut(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, markers = write_recordings(plan, raw, offsets={"kick": 100})
    ids = takes.ingest(job, plan, spec, home)
    kick = takes.load(home, ids[0]).part("kick")
    marker = markers[(0, "kick")]
    assert kick.frames == marker["frames"] == int(round(4 * RATE * 0.5 + 0.05 * RATE))                 # one bar at 120 BPM plus the 50 ms tail
    assert 0.40 < kick.samples[marker["tail_index"], 0] < 0.60                                           # the tail marker, 5 frames from the end, is kept
    assert not np.any(kick.samples[:, 0] > 0.62)                                                         # but neither the decoy (0.7) nor the overrun (0.8)


def test_cuts_follow_the_recordings_offset_exactly(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw, offsets={"kick": 100, "perc": 0})
    ids = takes.ingest(job, plan, spec, home)
    meta = json.loads((home / "takes" / ids[0] / "take.json").read_text())
    assert meta["offsets"]["kick"] == {"offset_samples": 100, "cut_start_sample": 96100, "fraction": 0.0, "calibration_samples": 0}
    assert meta["offsets"]["perc"]["cut_start_sample"] == 96000 and meta["offsets"]["mix"]["offset_samples"] == 0
    item = takes.load(home, ids[0])
    assert impulses(item.part("kick")) == [1000] and impulses(item.part("perc")) == [1000 + SAMPLES_PER_KEY]    # kick's file starts 100 samples earlier


def test_a_fractional_start_is_rounded_and_the_fraction_recorded(spec, home, raw):
    plan = make_plan(spec, tempos=[130.0])                                          # a beat is 22153.846 samples
    job, _ = write_recordings(plan, raw)
    ids = takes.ingest(job, plan, spec, home)
    offsets = json.loads((home / "takes" / ids[0] / "take.json").read_text())["offsets"]["kick"]
    assert offsets["cut_start_sample"] == int(round(4 * 22153.846153)) == 88615 and offsets["fraction"] == pytest.approx(0.3846, abs=1e-3)


def test_sum_null_is_measured_on_the_raw_recordings_over_the_mix_window(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw, offsets={"kick": 100, "bassA": 100, "A-Reverb": 100}, mix_gain=1.001)
    ids = takes.ingest(job, plan, spec, home)
    meta = json.loads((home / "takes" / ids[0] / "take.json").read_text())
    assert list(meta["sum_null"]) == ["mix"]
    assert meta["sum_null"]["mix"] == pytest.approx(20 * np.log10(1.001 / 0.001), abs=0.3)              # residual is 0.1 % of the mix: 60 dB
    take = takes.load(home, ids[0])
    result = analyze.sum_null_checks(spec, take)
    assert len(result) == 1 and result[0]["status"] == "pass" and result[0]["subject"] == "mix" and result[0]["value"] == pytest.approx(60.0, abs=0.3)


def test_sum_null_fails_when_something_reaches_the_master_that_was_not_captured(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw, mix_gain=1.05)
    ids = takes.ingest(job, plan, spec, home)
    take = takes.load(home, ids[0])
    assert take.meta["sum_null"]["mix"] == pytest.approx(20 * np.log10(1.05 / 0.05), abs=0.3)          # 26 dB
    check = analyze.sum_null_checks(spec, take)[0]
    assert check["status"] == "fail" and "not captured" in check["summary"]


def test_misaligned_recordings_would_not_null_so_offsets_are_really_applied(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw, offsets={"kick": 100})
    for entry in job["results"][0]["files"]:
        if entry["key"] == "kick":
            entry["offset_samples"] = 0                                               # lie about the offset
    ids = takes.ingest(job, plan, spec, home)
    assert takes.load(home, ids[0]).meta["sum_null"]["mix"] < 30.0


# ---------------------------------------------------------------------------
# ingest: warnings
# ---------------------------------------------------------------------------


def warnings_of(home, take_id):
    return takes.load(home, take_id).meta["warnings"]


def test_job_and_plan_warnings_are_kept_and_a_clean_capture_has_no_others(spec, home, raw):
    snapshot = ns.nova_snapshot(muted=["kick"])
    plan = make_plan(spec, snapshot=snapshot)
    job, _ = write_recordings(plan, raw)
    ids = takes.ingest(job, plan, spec, home)
    assert warnings_of(home, ids[0]) == ["Muted part tracks record silence: kick", "job warning"]


def test_44k_recordings_warn_about_the_sample_rate(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw, rate=44100)
    ids = takes.ingest(job, plan, spec, home)
    meta = takes.load(home, ids[0]).meta
    assert any(w.startswith("Captured at 44100 Hz, not the spec's 48000 Hz") and "(C5)" in w for w in meta["warnings"])
    assert meta["sample_rate"] == 44100
    assert takes.load(home, ids[0]).part("kick").rate == 44100
    assert takes.load(home, ids[0]).part("kick").frames == int(round(4 * 44100 * 0.5 + 0.05 * 44100))   # cuts follow the file's own rate
    assert meta["formats"]["kick"] == {"sample_rate": 44100, "bit_depth": 24, "format": "pcm"}


def test_other_bit_depths_warn_and_mixed_rates_are_listed(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw, depth=16)
    ids = takes.ingest(job, plan, spec, home)
    assert "Recorded at 16-bit, not 24-bit (C5)" in warnings_of(home, ids[0])
    plan = make_plan(spec, tempos=[120.0])
    other = raw / "second"
    other.mkdir()
    job, _ = write_recordings(plan, other)
    odd = job["results"][0]["files"][0]
    audio.write_wav(odd["file_path"], audio.read_wav(odd["file_path"]).samples, 44100, 24)
    ids = takes.ingest(job, plan, spec, home)
    meta = takes.load(home, ids[0]).meta
    assert meta["sample_rate"] == [44100, 48000] and any("44100/48000 Hz" in w for w in meta["warnings"])


def test_a_recording_that_is_too_short_warns_with_the_missing_samples(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, markers = write_recordings(plan, raw, offsets={"kick": 100}, cut_short={"kick": 480})
    ids = takes.ingest(job, plan, spec, home)
    take = takes.load(home, ids[0])
    assert [w for w in take.meta["warnings"] if w.startswith("kick is ")] == ["kick is 480 samples short of its cut"]
    assert take.part("kick").frames == markers[(0, "kick")]["frames"] - 480
    assert take.part("perc").frames == markers[(0, "perc")]["frames"]                       # the others are complete
    assert [w for w in take.meta["warnings"] if "short of its cut" in w] == ["kick is 480 samples short of its cut"]


def test_a_missing_recording_is_a_warning_and_voids_the_sum_null(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw, drop={"leadB"})
    ids = takes.ingest(job, plan, spec, home)
    meta = takes.load(home, ids[0]).meta
    assert "Pass 120 BPM A+B tap recorded nothing for leadB" in meta["warnings"]
    assert "leadB" not in meta["parts"] and "sum_null" not in meta and len(meta["parts"]) == 8
    assert not (home / "takes" / ids[0] / "stems" / "leadB.wav").exists()


def test_a_tempo_that_moved_during_the_recording_is_flagged(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw, steady=False)
    ids = takes.ingest(job, plan, spec, home)
    assert "Pass 120 BPM A+B tap: the tempo moved during recording (C7); this take is unreliable" in warnings_of(home, ids[0])


def test_the_tempo_the_engine_measured_replaces_the_planned_one_in_the_cut(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw)
    job["results"][0]["tempo"] = 120.0
    ids = takes.ingest(job, plan, spec, home)
    assert takes.load(home, ids[0]).meta["passes"][0]["tempo"] == 120.0


def test_a_job_with_more_passes_than_the_plan_is_refused(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0, 140.0])
    job, _ = write_recordings(plan, raw)
    job["results"].append(job["results"][0])
    with pytest.raises(TakeError, match="recorded 3 passes, the plan has 2"):
        takes.ingest(job, plan, spec, home)
    assert takes.list_ids(home) == []


def test_only_the_takes_whose_passes_all_recorded_are_kept(spec, home, raw):
    """A later pass that failed leaves the earlier tempos' takes intact and drops the unfinished one (C7)."""
    plan = make_plan(spec, tempos=[120.0, 140.0])
    job, _ = write_recordings(plan, raw)
    job["results"].pop()
    ids = takes.ingest(job, plan, spec, home)
    assert ids == ["neon-120-AB-0001"] and takes.list_ids(home) == ids
    assert not (home / "takes" / "neon-140-AB-0002").exists()
    nothing = takes.ingest({}, plan, spec, home)
    assert nothing == [] and takes.list_ids(home) == ids


def test_a_take_of_two_passes_needs_both_of_them(spec, home, raw):
    snapshot = ns.nova_snapshot(sends={"bassA": {"A": -12.0, "B": None}})
    plan = make_plan(spec, tempos=[120.0], snapshot=snapshot)
    job, _ = write_recordings(plan, raw)
    job["results"].pop()                                                                                    # the B pass never finished
    assert takes.ingest(job, plan, spec, home) == []


# ---------------------------------------------------------------------------
# ingest: sources, several takes, modes
# ---------------------------------------------------------------------------


def test_the_recorded_sources_are_deleted_unless_asked_otherwise(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw)
    paths = [entry["file_path"] for entry in job["results"][0]["files"]]
    assert all(os.path.exists(path) for path in paths)
    takes.ingest(job, plan, spec, home)
    assert not any(os.path.exists(path) for path in paths) and os.listdir(raw) == []
    plan = make_plan(spec, tempos=[120.0])
    kept = raw / "kept"
    kept.mkdir()
    job, _ = write_recordings(plan, kept)
    takes.ingest(job, plan, spec, home, delete_sources=False)
    assert len(os.listdir(kept)) == 12


def test_keep_raw_copies_the_recordings_into_the_take(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0])
    job, _ = write_recordings(plan, raw)
    ids = takes.ingest(job, plan, spec, home, keep_raw=True)
    folder = home / "takes" / ids[0] / "raw"
    assert sorted(path.name for path in folder.iterdir()) == sorted("p0_{0}.wav".format(key) for key in
                                                                    [e["key"] for e in plan["passes"][0]["record"]])
    assert audio.read_wav(folder / "p0_kick.wav").frames > audio.read_wav(home / "takes" / ids[0] / "stems" / "kick.wav").frames


def test_one_take_per_tempo_with_consecutive_numbers(spec, home, raw):
    plan = make_plan(spec, tempos=[100.0, 140.0])
    job, _ = write_recordings(plan, raw)
    ids = takes.ingest(job, plan, spec, home)
    assert ids == ["neon-100-AB-0001", "neon-140-AB-0002"]
    low, mid = takes.load(home, ids[0]), takes.load(home, ids[1])
    assert low.tempo == 100.0 and mid.tempo == 140.0 and low.meta["band"] == "LOW" and mid.meta["band"] == "MID"
    assert low.part("kick").frames == int(round(4 * RATE * 0.6 + 0.05 * RATE)) and mid.part("kick").frames == int(round(4 * RATE * 60.0 / 140 + 0.05 * RATE))
    more_dir = raw / "more"
    more_dir.mkdir()
    more, _ = write_recordings(make_plan(spec, tempos=[140.0]), more_dir)
    assert takes.ingest(more, make_plan(spec, tempos=[140.0]), spec, home) == ["neon-140-AB-0003"]


def test_per_variation_passes_keep_two_mixes_and_suffixed_returns(spec, home, raw):
    snapshot = ns.nova_snapshot(sends={"bassA": {"A": -12.0, "B": None}})
    plan = make_plan(spec, tempos=[120.0], snapshot=snapshot)
    job, _ = write_recordings(plan, raw, mix_gain=1.001)
    ids = takes.ingest(job, plan, spec, home)
    take = takes.load(home, ids[0])
    assert [entry["file"] for entry in take.meta["mixes"]] == ["mix@A.wav", "mix@B.wav"]
    assert [entry["variations"] for entry in take.meta["mixes"]] == [["A"], ["B"]]
    assert sorted(take.meta["returns"]) == ["A-Reverb@A", "A-Reverb@B", "B-Delay@A", "B-Delay@B"]
    assert sorted(take.meta["sum_null"]) == ["mix@A", "mix@B"]
    assert all(depth == pytest.approx(60.0, abs=0.3) for depth in take.meta["sum_null"].values())
    assert sorted(take.meta["parts"]) == sorted(PART_IDS)
    assert [variations for variations, _ in take.mixes()] == [["A"], ["B"]]
    assert sorted(take.returns("A")) == ["A-Reverb@A", "B-Delay@A"] and sorted(take.returns("B")) == ["A-Reverb@B", "B-Delay@B"]
    assert len(take.returns()) == 4 and len(take.parts()) == 9
    checks = analyze.sum_null_checks(spec, take)
    assert [(c["subject"], c["status"]) for c in checks] == [("mix@A", "pass"), ("mix@B", "pass")]
    assert [p["label"] for p in take.meta["passes"]] == ["120 BPM A tap", "120 BPM B tap"]
    assert any("bassA send to returns" in w for w in take.meta["warnings"])


def test_a_shared_part_recorded_in_two_passes_keeps_the_first_recording(spec, home, raw):
    snapshot = ns.nova_snapshot(sends={"bassA": {"A": -12.0, "B": None}})
    plan = make_plan(spec, tempos=[120.0], snapshot=snapshot)
    job, markers = write_recordings(plan, raw)
    first_pass_kick = audio.read_wav(job["results"][0]["files"][0]["file_path"])                             # kick, as recorded in the A pass
    second_pass_kick = audio.read_wav(job["results"][1]["files"][0]["file_path"])
    assert job["results"][0]["files"][0]["key"] == "kick" and not np.array_equal(first_pass_kick.samples, second_pass_kick.samples)
    take = takes.load(home, takes.ingest(job, plan, spec, home)[0])
    start = int(round(plan["passes"][0]["cuts"][0]["start_beats"] * RATE * 0.5))
    frames = markers[(0, "kick")]["frames"]
    assert np.array_equal(take.part("kick").samples, first_pass_kick.samples[start:start + frames])           # the file is the A pass's cut
    assert take.meta["parts"]["kick"]["pass"] == "120 BPM A tap"                                              # and the metadata says so
    assert take.meta["offsets"]["kick"]["cut_start_sample"] == start


def test_quick_check_takes_remember_how_many_bars_each_file_holds(spec, home, raw):
    plan = make_plan(spec, tempos=[180.0], bars=4)
    job, _ = write_recordings(plan, raw)
    take = takes.load(home, takes.ingest(job, plan, spec, home)[0])
    assert take.meta["parts"]["kick"]["bars"] == 2 and take.meta["parts"]["kick"]["cut_bars"] == 2.0           # the kick's loop is 2 bars
    assert take.meta["parts"]["pad"]["bars"] == 16 and take.meta["parts"]["pad"]["cut_bars"] == 4.0           # the pad was cut to the 4-bar cycle
    assert take.part_bars() == {"kick": 2.0, "perc": 4.0, "pad": 4.0, "bassA": 4.0, "bassB": 4.0, "arpA": 4.0, "arpB": 4.0, "leadA": 4.0, "leadB": 4.0}
    bar = spec.bar_seconds(180.0)
    sums, missing = tiers.tier_sums(take.parts(), spec, "neon", "A", 180.0, bars=take.part_bars())
    assert missing == [] and abs(sums["T5"].frames - (int(round(4 * bar * RATE)) + int(round(0.05 * RATE)))) <= 1      # four bars, not sixteen
    too_long, _ = tiers.tier_sums(take.parts(), spec, "neon", "A", 180.0)                                      # the spec's loop lengths would stretch it
    assert too_long["T5"].frames > 3 * sums["T5"].frames


def test_part_bars_prefers_the_cut_length_and_skips_parts_without_one(tmp_path):
    folder = tmp_path / "takes" / "t"
    folder.mkdir(parents=True)
    meta = {"id": "t", "set": "neon", "tempo": 140, "parts": {"a": {"file": "a.wav", "bars": 8, "cut_bars": 4.0}, "b": {"file": "b.wav", "bars": 2},
                                                              "c": {"file": "c.wav"}, "d": {"file": "d.wav", "cut_bars": 0}}}
    (folder / "take.json").write_text(json.dumps(meta))
    assert takes.Take(folder).part_bars() == {"a": 4.0, "b": 2}
    assert takes.Take(folder).meta["parts"]["c"] == {"file": "c.wav"}


def test_every_recording_of_an_ingested_capture_is_deleted(spec, home, raw):
    snapshot = ns.nova_snapshot(sends={"bassA": {"A": -12.0, "B": None}})
    plan = make_plan(spec, tempos=[120.0], snapshot=snapshot)
    job, _ = write_recordings(plan, raw)
    assert len(os.listdir(raw)) == 18                                                                       # two passes of nine recordings
    takes.ingest(job, plan, spec, home)
    assert sorted(os.listdir(raw)) == []


def test_solo_takes_have_the_stems_but_no_mix_and_no_sum_null(spec, home, raw):
    plan = make_plan(spec, tempos=[120.0], mode="solo")
    job, markers = write_recordings(plan, raw)
    ids = takes.ingest(job, plan, spec, home)
    take = takes.load(home, ids[0])
    assert take.mode == "solo" and take.meta["mixes"] == [] and take.meta["returns"] == {} and "sum_null" not in take.meta
    assert sorted(take.parts()) == sorted(PART_IDS) and len(take.meta["passes"]) == 9
    for number, part in enumerate(PART_IDS):
        entry = take.meta["parts"][part]
        assert entry["file"] == "stems/{0}.wav".format(part) and entry["source"] == "resampling" and entry["pass"] == "120 BPM {0} solo".format(part)
        assert take.part(part).frames == markers[(number, "mix")]["frames"] == int(round(4 * 0.5 * RATE + 0.05 * RATE))
        assert impulses(take.part(part)) == [1000]                                                      # each pass recorded only the mix
    assert analyze.sum_null_checks(spec, take)[0]["status"] == "skip"


def test_take_accessors_and_snapshot(spec, home, raw):
    plan = make_plan(spec, tempos=[140.0])
    job, _ = write_recordings(plan, raw)
    snapshot = ns.nova_snapshot()
    ids = takes.ingest(job, plan, spec, home, snapshot=snapshot)
    take = takes.load(home, ids[0])
    assert take.id == "neon-140-AB-0001" and take.set == "neon" and take.tempo == 140.0 and take.variations == ["A", "B"] and take.mode == "tap"
    assert take.file("mix.wav") == home / "takes" / ids[0] / "mix.wav" and take.path == home / "takes" / ids[0]
    assert take.snapshot() == snapshot
    assert take.part("nope") is None and take.part("kick") is take.part("kick")                    # unknown part: None; reads are cached
    assert take.parts()["kick"] is take.part("kick")
    assert take.mixes()[0][0] == ["A", "B"] and take.mixes()[0][1].frames == take.part("pad").frames


def test_take_save_rewrites_take_json_with_clean_numbers(spec, home, raw):
    plan = make_plan(spec, tempos=[140.0])
    job, _ = write_recordings(plan, raw)
    take = takes.load(home, takes.ingest(job, plan, spec, home)[0])
    take.meta["note"] = "edited"
    take.meta["metric"] = float("nan")
    take.save()
    again = takes.load(home, take.id)
    assert again.meta["note"] == "edited" and again.meta["metric"] is None
    assert (take.path / "take.json").read_text().endswith("\n")


# ---------------------------------------------------------------------------
# take ids, listing, loading
# ---------------------------------------------------------------------------


def test_format_bpm():
    assert takes.format_bpm(140) == "140" and takes.format_bpm(140.0) == "140" and takes.format_bpm("140") == "140"
    assert takes.format_bpm(127.5) == "127.5" and takes.format_bpm(99.25) == "99.25"


def test_next_id_numbers_start_at_one_and_follow_the_highest_existing_number(tmp_path):
    assert takes.next_id(tmp_path / "nowhere", "neon", 140, "A") == "neon-140-A-0001"
    assert takes.next_id(tmp_path, "neon", 140, "A") == "neon-140-A-0001"
    folder = tmp_path / "takes"
    (folder / "neon-140-A-0001").mkdir(parents=True)
    assert takes.next_id(tmp_path, "neon", 140, "A") == "neon-140-A-0002"
    (folder / "mainframe-120-AB-0007").mkdir()
    assert takes.next_id(tmp_path, "neon", 100, "AB") == "neon-100-AB-0008"                         # the count is shared by every set
    (folder / "neon-127.5-all-0010").mkdir()
    (folder / "notes.txt").write_text("x")
    (folder / "neon-140-A-12").mkdir()                                                               # two digits: not a take number
    assert takes.next_id(tmp_path, "neon", 127.5, "A") == "neon-127.5-A-0011"
    assert takes.next_id(tmp_path, "mainframe", 120.0, "B") == "mainframe-120-B-0011"


def test_next_id_keeps_counting_past_nine_and_gaps(tmp_path):
    folder = tmp_path / "takes"
    for number in (1, 2, 9):
        (folder / "neon-140-A-{0:04d}".format(number)).mkdir(parents=True)
    assert takes.next_id(tmp_path, "neon", 140, "A") == "neon-140-A-0010"
    (folder / "neon-140-A-0010").mkdir()
    (folder / "neon-140-A-0099").mkdir()
    assert takes.next_id(tmp_path, "neon", 140, "A") == "neon-140-A-0100"
    (folder / "neon-140-A-9999").mkdir()
    assert takes.next_id(tmp_path, "neon", 140, "A") == "neon-140-A-10000"


@pytest.mark.parametrize("name, number", [
    ("neon-140-A-0001", 1), ("mainframe-120-AB-0042", 42), ("neon-127.5-A-0003", 3), ("neon-140-all-0001", 1), ("neon-140-A-10000", 10000),
    ("Neon-140-A-0007", 7), ("neon-2-140-AB-0123", 123), ("any thing-0009", 9),
])
def test_take_numbers_are_the_four_digit_suffix_of_the_folder_name(name, number):
    match = takes.TAKE_ID.search(name)
    assert match and int(match.group("number")) == number


@pytest.mark.parametrize("name", ["neon-140-A-1", "neon-140-A-123", "neon-140-A-0001-x", "takes", "0001", "neon_0001"])
def test_names_without_a_number_suffix_are_not_takes(name):
    assert takes.TAKE_ID.search(name) is None


def test_next_id_counts_takes_of_a_set_with_an_upper_case_or_hyphenated_name(tmp_path):
    for set_name in ("Neon", "neon-2", "MF"):
        first = takes.next_id(tmp_path, set_name, 140, "A")
        (tmp_path / "takes" / first).mkdir(parents=True)
        second = takes.next_id(tmp_path, set_name, 140, "A")
        assert second != first and (tmp_path / "takes" / second).exists() is False
    assert len(list((tmp_path / "takes").iterdir())) == 3 and takes.next_id(tmp_path, "x", 100, "A").endswith("-0004")


def test_take_path_and_load_errors(tmp_path):
    with pytest.raises(TakeError, match=r"No take 'neon-140-A-0001' in .*takes"):
        takes.take_path(tmp_path, "neon-140-A-0001")
    (tmp_path / "takes" / "neon-140-A-0001").mkdir(parents=True)
    with pytest.raises(TakeError, match="No take"):
        takes.load(tmp_path, "neon-140-A-0001")                                                   # a folder without take.json is not a take
    (tmp_path / "takes" / "neon-140-A-0001" / "take.json").write_text("{ broken")
    with pytest.raises(TakeError, match="Cannot read"):
        takes.load(tmp_path, "neon-140-A-0001")
    with pytest.raises(TakeError, match="Cannot read"):
        takes.Take(tmp_path / "takes" / "neon-140-A-0001" / "missing")


def test_list_ids_lists_only_folders_with_a_take_json(tmp_path):
    assert takes.list_ids(tmp_path) == []
    for name, complete in (("neon-140-A-0002", True), ("neon-140-A-0001", True), ("neon-140-A-0003", False)):
        folder = tmp_path / "takes" / name
        folder.mkdir(parents=True)
        if complete:
            (folder / "take.json").write_text("{}")
    (tmp_path / "takes" / "loose.txt").write_text("x")
    assert takes.list_ids(tmp_path) == ["neon-140-A-0001", "neon-140-A-0002"]


def test_returns_filter_by_variation(tmp_path):
    folder = tmp_path / "takes" / "t"
    folder.mkdir(parents=True)
    for name in ("shared", "only_a"):
        audio.write_wav(folder / "{0}.wav".format(name), np.zeros((10, 2)), 48000, 16)
    meta = {"id": "t", "set": "neon", "tempo": 140, "returns": {"shared": {"file": "shared.wav"}, "A-Rev": {"file": "only_a.wav", "variations": ["A"]}}}
    (folder / "take.json").write_text(json.dumps(meta))
    item = takes.Take(folder)
    assert sorted(item.returns()) == ["A-Rev", "shared"] and sorted(item.returns("A")) == ["A-Rev", "shared"] and sorted(item.returns("B")) == ["shared"]
    assert item.variations == [] and item.mode == "tap" and item.snapshot() is None and item.mixes() == []


# ---------------------------------------------------------------------------
# from_files
# ---------------------------------------------------------------------------


def make_files(folder, names, rate=48000, depth=24, seconds=0.5):
    out = {}
    for number, name in enumerate(names):
        t = np.arange(int(seconds * rate)) / float(rate)
        out[name] = str(audio.write_wav(folder / "src_{0}.wav".format(name.replace(":", "_")), 0.1 * np.sin(2 * np.pi * (220 + 55 * number) * t), rate, depth))
    return out


def test_from_files_copies_wavs_into_a_take(spec, home, tmp_path):
    files = make_files(tmp_path, ["kick", "bassA", "mix", "return:A-Reverb"])
    take_id = takes.from_files(home, "neon", 140, files, spec, note="hand export")
    assert take_id == "neon-140-AB-0001"
    take = takes.load(home, take_id)
    assert take.mode == "files" and take.variations == ["A", "B"] and take.meta["note"] == "hand export" and take.meta["spec"] == "nova"
    assert sorted(take.meta["parts"]) == ["bassA", "kick"] and take.meta["parts"]["kick"]["file"] == "stems/kick.wav"
    assert take.meta["parts"]["kick"]["source"] == files["kick"] and take.meta["parts"]["kick"]["frames"] == 24000
    assert take.meta["mixes"][0]["file"] == "mix.wav" and take.meta["mixes"][0]["variations"] == ["A", "B"]
    assert take.meta["returns"]["A-Reverb"]["file"] == "returns/A-Reverb.wav"
    assert (take.path / "stems" / "kick.wav").read_bytes() == Path(files["kick"]).read_bytes()          # a byte-for-byte copy
    assert take.meta["formats"]["kick"] == {"sample_rate": 48000, "bit_depth": 24, "format": "pcm"}
    assert take.part("kick").frames == 24000 and take.mixes()[0][1].frames == 24000 and "A-Reverb" in take.returns()


def test_from_files_one_variation_and_ids(spec, home, tmp_path):
    files = make_files(tmp_path, ["kick"])
    first = takes.from_files(home, "neon", 127.5, files, spec, variation="B")
    assert first == "neon-127.5-B-0001"
    assert takes.load(home, first).variations == ["B"] and takes.load(home, first).meta["variation"] == "B"
    assert takes.from_files(home, "neon", 140, files, spec) == "neon-140-AB-0002"
    assert takes.from_files(home, "mainframe", 120, files, spec, mode="tap") == "mainframe-120-AB-0003"
    assert takes.load(home, "mainframe-120-AB-0003").mode == "tap"


@pytest.mark.skipif(audio.find_ffmpeg() is None or audio.find_ffmpeg("ffprobe") is None, reason="ffmpeg is not installed")
def test_from_files_decodes_other_formats_into_float_wavs(spec, home, tmp_path):
    import subprocess
    wav = make_files(tmp_path, ["kick"])["kick"]
    flac = tmp_path / "kick.flac"
    subprocess.run([audio.find_ffmpeg(), "-v", "error", "-i", wav, "-c:a", "flac", "-sample_fmt", "s32", str(flac)], check=True)
    take = takes.load(home, takes.from_files(home, "neon", 140, {"kick": str(flac)}, spec))
    stored = audio.read_wav(take.path / "stems" / "kick.wav")
    assert stored.format == "float" and stored.rate == 48000 and stored.frames == 24000
    assert take.meta["formats"]["kick"]["format"] == "decoded"


def test_from_files_without_copying_reads_the_files_in_place(spec, home, tmp_path):
    files = make_files(tmp_path, ["kick", "mix", "return:A-Reverb"])
    take = takes.load(home, takes.from_files(home, "neon", 140, files, spec, copy=False))
    assert take.part("kick").frames == 24000 and take.mixes()[0][1].frames == 24000 and take.returns()["A-Reverb"].frames == 24000
    assert take.meta["parts"]["kick"]["file"] == str(Path(files["kick"]).resolve())                       # the original, not a copy
    assert not (take.path / "stems" / "kick.wav").exists() and not (take.path / "mix.wav").exists()


def test_analyze_files_reports_on_loose_files_without_leaving_a_take(spec, tmp_path):
    files = make_files(tmp_path, ["kick", "perc"], seconds=1.0)
    result = analyze.analyze_files(spec, "neon", 140.0, files, strict_mode=False)
    assert result["subject"] == "files" and result["kind"] == "audio" and result["mode"] == "files" and result["tempo"] == 140.0
    assert any(item["check"] == "audio.parts" and "pad" in item["summary"] for item in result["checks"])     # the other parts are reported missing
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(Path(p).name for p in files.values())     # no take next to the files


# ---------------------------------------------------------------------------
# where takes live
# ---------------------------------------------------------------------------


def test_safe_name_keeps_letters_digits_dot_dash_and_underscore():
    import ears
    assert ears.safe_name("My Set!") == "My_Set" and ears.safe_name("a/b\\c") == "a_b_c" and ears.safe_name("NOVA-v2.1_final") == "NOVA-v2.1_final"
    assert ears.safe_name("  .hidden.  ") == "hidden" and ears.safe_name("") == "untitled" and ears.safe_name(None) == "untitled"
    assert ears.safe_name("***", fallback="x") == "x" and ears.safe_name(" spaced   out ") == "spaced_out" and ears.safe_name("é") == "untitled"


def test_the_ears_home_follows_the_environment_then_the_saved_set_then_the_default(tmp_path, monkeypatch):
    import ears
    monkeypatch.delenv("EARS_HOME", raising=False)
    assert ears.home() == ears.DEFAULT_ROOT / "untitled" and ears.home(set_name="NOVA draft") == ears.DEFAULT_ROOT / "NOVA_draft"
    assert str(ears.DEFAULT_ROOT).endswith("Music/AbletonMCP/Ears")
    saved = tmp_path / "Sets" / "NOVA Project" / "nova.als"
    assert ears.home(set_path=str(saved)) == (tmp_path / "Sets" / "NOVA Project" / "ears").resolve()       # beside the set, not in git
    assert ears.home(set_path=str(saved), set_name="ignored") == ears.home(set_path=str(saved))
    monkeypatch.setenv("EARS_HOME", str(tmp_path / "elsewhere"))
    assert ears.home(set_path=str(saved), set_name="x") == tmp_path / "elsewhere"                          # EARS_HOME wins over everything
    monkeypatch.setenv("EARS_HOME", "~/ears-test-home")
    assert ears.home() == ears.Path("~/ears-test-home").expanduser()


# ---------------------------------------------------------------------------
# ledger
# ---------------------------------------------------------------------------


def meta_of(take_id, set_name="neon", tempo=140.0, variation="AB", **extra):
    return dict({"id": take_id, "set": set_name, "tempo": tempo, "variation": variation, "mode": "tap", "note": "n"}, **extra)


def test_append_adds_a_time_creates_the_file_and_writes_one_line_each(tmp_path):
    home = tmp_path / "deep" / "home"
    stored = ledger.append(home, {"type": "take", "id": "t1"})
    assert stored["time"] and ledger.path(home) == home / "ledger.jsonl" and ledger.path(home).is_file()
    ledger.append(home, {"type": "take", "id": "t2", "time": "2026-10-07T00:00:00+00:00"})
    lines = ledger.path(home).read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["time"] == "2026-10-07T00:00:00+00:00"
    assert ledger.lines(home)[0]["id"] == "t1" and ledger.lines(home)[1]["id"] == "t2"


def test_append_cleans_numbers_and_does_not_change_the_entry_it_is_given(tmp_path):
    entry = {"type": "x", "value": float("nan"), "numpy": np.float32(0.5)}
    ledger.append(tmp_path, entry)
    assert "time" not in entry
    assert json.loads(ledger.path(tmp_path).read_text()) == {"type": "x", "value": None, "numpy": 0.5, "time": json.loads(ledger.path(tmp_path).read_text())["time"]}


def test_lines_skips_blank_and_corrupt_lines_and_survives_a_missing_file(tmp_path):
    assert ledger.lines(tmp_path) == []
    ledger.path(tmp_path).write_text('{"type": "take", "id": "a"}\n\n   \nnot json\n{"type": "take", "id": "b"}\n{"half": \n')
    assert [entry["id"] for entry in ledger.lines(tmp_path)] == ["a", "b"]


def test_state_of_an_empty_ledger(tmp_path):
    assert ledger.state(tmp_path) == ([], {})
    assert ledger.query(tmp_path) == [] and ledger.best(tmp_path, "neon", 140, "AB") is None


def test_record_take_then_query_newest_first(tmp_path):
    for number in (1, 2, 3):
        ledger.record_take(tmp_path, meta_of("neon-140-AB-000{0}".format(number)), verdict="{0} fail, 0 warn, 3 pass".format(number),
                           snapshot="takes/x/snapshot.json")
    rows = ledger.query(tmp_path)
    assert [row["id"] for row in rows] == ["neon-140-AB-0003", "neon-140-AB-0002", "neon-140-AB-0001"]
    assert rows[0] == {"id": "neon-140-AB-0003", "time": rows[0]["time"], "set": "neon", "tempo": 140.0, "variation": "AB", "mode": "tap",
                       "note": "n", "verdict": "3 fail, 0 warn, 3 pass", "best": False}
    entry = ledger.state(tmp_path)[0][0]
    assert entry["snapshot"] == "takes/x/snapshot.json" and entry["type"] == "take"


def test_verdicts_fold_into_the_take_with_the_latest_one_winning(tmp_path):
    ledger.record_take(tmp_path, meta_of("t1"), verdict=None)
    ledger.record_verdict(tmp_path, "t1", "1 fail, 2 warn, 29 pass")                                    # audio, the default kind
    ledger.record_verdict(tmp_path, "t1", "0 fail, 4 warn, 12 pass", kind="notes")
    ledger.record_verdict(tmp_path, "t1", "0 fail, 2 warn, 29 pass")                                    # a later audio analysis
    ledger.record_verdict(tmp_path, "unknown", "9 fail, 9 warn, 9 pass")                               # no such take: ignored
    entries, best = ledger.state(tmp_path)
    assert len(entries) == 1 and best == {}
    assert entries[0]["verdicts"] == {"audio": "0 fail, 2 warn, 29 pass", "notes": "0 fail, 4 warn, 12 pass"}
    assert entries[0]["verdict"] == "0 fail, 2 warn, 29 pass"
    assert ledger.query(tmp_path)[0]["verdict"] == "0 fail, 2 warn, 29 pass"
    ledger.record_verdict(tmp_path, "t1", "0 fail, 0 warn, 1 pass", kind="notes")                      # a later notes verdict updates its own kind only
    entry = ledger.state(tmp_path)[0][0]
    assert entry["verdicts"]["notes"] == "0 fail, 0 warn, 1 pass" and entry["verdict"] == "0 fail, 2 warn, 29 pass"
    assert ledger.query(tmp_path)[0]["verdict"] == "0 fail, 2 warn, 29 pass"                            # the headline verdict is the measurement ear's


def test_a_verdict_written_before_its_take_is_ignored(tmp_path):
    ledger.record_verdict(tmp_path, "t1", "early")
    ledger.record_take(tmp_path, meta_of("t1"))
    assert ledger.state(tmp_path)[0][0].get("verdict") is None and "verdicts" not in ledger.state(tmp_path)[0][0]


def test_best_key_names_set_tempo_and_variation():
    assert ledger.best_key("neon", 140, "AB") == "neon-140-AB" and ledger.best_key("neon", 127.5, "A") == "neon-127.5-A"
    assert ledger.best_key("mainframe", 120.0, "B") == "mainframe-120-B"


def test_keep_moves_the_best_pointer_for_its_set_tempo_and_variation(tmp_path):
    for number in (1, 2):
        ledger.record_take(tmp_path, meta_of("neon-140-AB-000{0}".format(number)))
    ledger.record_take(tmp_path, meta_of("neon-100-AB-0003", tempo=100.0))
    assert ledger.best(tmp_path, "neon", 140, "AB") is None
    assert ledger.keep(tmp_path, meta_of("neon-140-AB-0001")) == "neon-140-AB"
    assert ledger.best(tmp_path, "neon", 140, "AB") == "neon-140-AB-0001"
    ledger.keep(tmp_path, meta_of("neon-140-AB-0002"))
    assert ledger.best(tmp_path, "neon", 140.0, "AB") == "neon-140-AB-0002"                               # the pointer moved
    ledger.keep(tmp_path, meta_of("neon-100-AB-0003", tempo=100.0))
    assert ledger.best(tmp_path, "neon", 100, "AB") == "neon-100-AB-0003" and ledger.best(tmp_path, "neon", 140, "AB") == "neon-140-AB-0002"
    assert ledger.best(tmp_path, "neon", 140, "A") is None and ledger.best(tmp_path, "mainframe", 140, "AB") is None
    assert ledger.state(tmp_path)[1] == {"neon-140-AB": "neon-140-AB-0002", "neon-100-AB": "neon-100-AB-0003"}
    assert len([line for line in ledger.lines(tmp_path) if line["type"] == "best"]) == 3                 # history is kept
    rows = dict((row["id"], row["best"]) for row in ledger.query(tmp_path))
    assert rows == {"neon-140-AB-0001": False, "neon-140-AB-0002": True, "neon-100-AB-0003": True}


def test_query_filters(tmp_path):
    ledger.record_take(tmp_path, meta_of("neon-140-AB-0001", note="bass reworked"), verdict="0 fail")
    ledger.record_take(tmp_path, meta_of("neon-140-A-0002", variation="A", note="PAD thinned"))
    ledger.record_take(tmp_path, meta_of("neon-100-AB-0003", tempo=100.0, note="lead rests"))
    ledger.record_take(tmp_path, meta_of("mainframe-120-AB-0004", set_name="mainframe", tempo=120.0, note="mf pad"))
    ids = lambda **kwargs: [row["id"] for row in ledger.query(tmp_path, **kwargs)]
    assert ids() == ["mainframe-120-AB-0004", "neon-100-AB-0003", "neon-140-A-0002", "neon-140-AB-0001"]
    assert ids(set_name="neon") == ["neon-100-AB-0003", "neon-140-A-0002", "neon-140-AB-0001"]
    assert ids(set_name="neon", tempo=140) == ["neon-140-A-0002", "neon-140-AB-0001"]
    assert ids(tempo=140.0000001) == ["neon-140-A-0002", "neon-140-AB-0001"] and ids(tempo=99) == []
    assert ids(variation="A") == ["neon-140-A-0002"] and ids(variation="AB", set_name="neon") == ["neon-100-AB-0003", "neon-140-AB-0001"]
    assert ids(text="pad") == ["mainframe-120-AB-0004", "neon-140-A-0002"]                                   # case-insensitive, any field
    assert ids(text="LEAD RESTS") == ["neon-100-AB-0003"] and ids(text="0 fail") == ["neon-140-AB-0001"] and ids(text="zzz") == []
    assert ids(limit=2) == ["mainframe-120-AB-0004", "neon-100-AB-0003"]
    assert ids(set_name="neon", tempo=100, variation="AB", text="lead") == ["neon-100-AB-0003"]


def test_query_returns_only_the_summary_fields(tmp_path):
    ledger.record_take(tmp_path, meta_of("t1"), snapshot="s.json")
    assert set(ledger.query(tmp_path)[0]) == {"id", "time", "set", "tempo", "variation", "mode", "note", "verdict", "best"}


def test_ledger_is_append_only_history(tmp_path):
    ledger.record_take(tmp_path, meta_of("t1"))
    before = ledger.path(tmp_path).read_text()
    ledger.keep(tmp_path, meta_of("t1"))
    ledger.record_verdict(tmp_path, "t1", "v")
    after = ledger.path(tmp_path).read_text()
    assert after.startswith(before) and len(after.splitlines()) == 3


def test_left_behind_points_at_the_untitled_home_after_a_first_save(tmp_path, monkeypatch):
    import ears
    monkeypatch.delenv("EARS_HOME", raising=False)
    monkeypatch.setattr(ears, "DEFAULT_ROOT", tmp_path / "Ears")
    set_path = tmp_path / "NOVA Project" / "NOVA.als"
    assert ears.left_behind(str(set_path), "NOVA") is None                 # nothing was recorded untitled
    (tmp_path / "Ears" / "untitled").mkdir(parents=True)
    (tmp_path / "Ears" / "untitled" / "ledger.jsonl").write_text("{}\n")
    assert ears.left_behind(str(set_path), "NOVA") == tmp_path / "Ears" / "untitled"
    assert ears.left_behind(None, None) is None                             # still unsaved: that is its home
    (tmp_path / "NOVA Project" / "ears").mkdir(parents=True)
    (tmp_path / "NOVA Project" / "ears" / "ledger.jsonl").write_text("{}\n")
    assert ears.left_behind(str(set_path), "NOVA") is None                 # the saved set has its own takes now
