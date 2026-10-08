"""Unit tests for ears/strict.py: the delivery-file checks (duration, loop seam, start, format) of PRD section 8.

Loop files come from ears.fixtures.audio at 48 kHz, written as 24-bit PCM and read back like a delivery file. The seam
defects are the fixture's own plants (a noise click in the head, a tail that was not folded); the duration defect is the
5 ms short file.
"""
import shutil

import numpy as np
import pytest

from ears import audio, strict
from ears import spec as specs
from ears.audio import Audio
from ears.fixtures import audio as fx

TEMPO = 140.0
RATE = 48000


@pytest.fixture(scope="module")
def spec():
    return specs.load("nova")


@pytest.fixture(scope="module")
def clean(spec):
    return fx.normalise(fx.render_parts(spec, "neon", TEMPO), spec, "neon", TEMPO)


@pytest.fixture(scope="module")
def delivery(tmp_path_factory, clean):
    """Delivery files on disk and read back: {key: Audio} for the clean parts and each planted defect."""
    folder = tmp_path_factory.mktemp("delivery")
    out = {}

    def store(key, item):
        path = audio.write_wav(folder / (key + ".wav"), item.samples, item.rate, 24)
        out[key] = audio.read_wav(path)

    for part_id in ("pad", "bassA", "kick", "arpA", "leadA"):
        store(part_id, clean[part_id])
    spec = specs.load("nova")
    for defect, part_id in (("seam_click", "pad"), ("unfolded", "pad"), ("short_5ms", "bassA")):
        planted, _ = fx.plant(clean, defect, spec, "neon", TEMPO)
        store(defect, planted[part_id])
    yield out
    shutil.rmtree(folder, ignore_errors=True)


def body_seconds(spec, part_id):
    return spec.part("neon", part_id).bars * spec.bar_seconds(TEMPO)


# ---------------------------------------------------------------------------
# file.duration
# ---------------------------------------------------------------------------


def test_expected_seconds_is_bars_times_bar_length_plus_the_tail():
    assert strict.expected_seconds(8, 140, 4.0, 0.05) == pytest.approx(8 * 4 * 60.0 / 140 + 0.05)
    assert strict.expected_seconds(2, 120, 4.0, 0.05) == pytest.approx(4.05)
    assert strict.expected_seconds(2, 120, 3.0, 0.0) == pytest.approx(3.0)


def silence(seconds, rate=RATE, channels=2):
    return Audio(np.zeros((int(round(seconds * rate)), channels)), rate)


@pytest.mark.parametrize("delta_frames, status", [
    (0, "pass"), (1, "pass"), (-1, "pass"), (47, "pass"), (-47, "pass"),        # 48 frames is 1 ms at 48 kHz
    (49, "fail"), (-49, "fail"), (240, "fail"), (-240, "fail"),                  # 5 ms
])
def test_duration_tolerance_is_one_millisecond(delta_frames, status):
    expected = strict.expected_seconds(2, 120, 4.0, 0.05)                       # 4.05 s: a whole number of frames at 48 kHz
    file = Audio(np.zeros((int(round(expected * RATE)) + delta_frames, 2)), RATE)
    result = strict.duration_check(file, "bassA", expected, 1.0)
    assert result["status"] == status and result["check"] == "file.duration" and result["subject"] == "bassA"
    assert result["error_ms"] == pytest.approx(delta_frames / 48.0, abs=0.001)
    assert result["value"] == pytest.approx(file.duration, abs=1e-3) and result["target"] == pytest.approx(expected, abs=1e-3)   # reports round to 3 decimals
    assert result["tolerance"] == 1.0 and result["unit"] == "s"
    assert ("ms from" in result["summary"]) and ("{0:+.2f} ms".format(delta_frames / 48.0) in result["summary"])


def test_duration_tolerance_is_a_parameter():
    expected = 4.05
    file = Audio(np.zeros((int(round(expected * RATE)) + 240, 2)), RATE)           # 5 ms long
    assert strict.duration_check(file, "x", expected, 1.0)["status"] == "fail"
    assert strict.duration_check(file, "x", expected, 6.0)["status"] == "pass"


def test_duration_of_the_clean_loops_and_the_5_ms_short_file(spec, delivery):
    for part_id in ("pad", "bassA", "kick", "arpA"):
        bars = spec.part("neon", part_id).bars
        result = strict.duration_check(delivery[part_id], part_id, strict.expected_seconds(bars, TEMPO, 4.0, 0.05), 1.0)
        assert result["status"] == "pass" and abs(result["error_ms"]) < 0.05
    bars = spec.part("neon", "bassA").bars
    short = strict.duration_check(delivery["short_5ms"], "bassA", strict.expected_seconds(bars, TEMPO, 4.0, 0.05), 1.0)
    assert short["status"] == "fail" and short["error_ms"] == pytest.approx(-5.0, abs=0.05)
    assert "-5.00 ms" in short["summary"] or "-4.99 ms" in short["summary"]


def test_a_file_without_the_tail_is_50_ms_short():
    expected = strict.expected_seconds(2, 120, 4.0, 0.05)
    body_only = silence(4.0)
    result = strict.duration_check(body_only, "x", expected, 1.0)
    assert result["status"] == "fail" and result["error_ms"] == pytest.approx(-50.0, abs=0.01)


# ---------------------------------------------------------------------------
# file.seam
# ---------------------------------------------------------------------------


def test_seam_passes_on_the_clean_pad(spec, delivery):
    measures = strict.seam_measures(delivery["pad"], body_seconds(spec, "pad"))
    assert measures["tail_ms"] == pytest.approx(50.0, abs=0.1)
    assert measures["fold_db"] is not None and measures["fold_db"] > -3.0         # the head carries the ringing of the last cycle
    assert measures["click_db"] < 0.0
    result = strict.seam_check(delivery["pad"], "pad", body_seconds(spec, "pad"), 30.0, 6.0)
    assert result["status"] == "pass" and result["check"] == "file.seam" and result["subject"] == "pad"
    assert result["value"] == measures and result["target"] == {"fold_db": -30.0, "click_db": 6.0}
    assert result["summary"].startswith("fold ") and "click" in result["summary"]


def test_seam_fails_on_a_click_at_the_seam(spec, delivery):
    measures = strict.seam_measures(delivery["seam_click"], body_seconds(spec, "pad"))
    assert measures["click_db"] > 20.0 and measures["fold_db"] > -3.0              # a click, but the tail is folded
    result = strict.seam_check(delivery["seam_click"], "pad", body_seconds(spec, "pad"), 30.0, 6.0)
    assert result["status"] == "fail" and "click" in result["summary"] and "not folded" not in result["summary"]


def test_seam_fails_on_a_tail_that_was_not_folded(spec, delivery):
    measures = strict.seam_measures(delivery["unfolded"], body_seconds(spec, "pad"))
    assert measures["fold_db"] < -30.0 and measures["click_db"] < 6.0              # the head starts from silence under a ringing end
    result = strict.seam_check(delivery["unfolded"], "pad", body_seconds(spec, "pad"), 30.0, 6.0)
    assert result["status"] == "fail" and "the tail is not folded" in result["summary"] and "click" not in result["summary"]


def test_seam_thresholds_are_parameters(spec, delivery):
    seconds = body_seconds(spec, "pad")
    assert strict.seam_check(delivery["unfolded"], "pad", seconds, 45.0, 6.0)["status"] == "pass"     # 40 dB is inside 45
    assert strict.seam_check(delivery["unfolded"], "pad", seconds, 20.0, 6.0)["status"] == "fail"
    assert strict.seam_check(delivery["seam_click"], "pad", seconds, 30.0, 60.0)["status"] == "pass"
    assert strict.seam_check(delivery["pad"], "pad", seconds, 30.0, -20.0)["status"] == "fail"


def test_seam_on_material_that_ends_in_silence_has_no_fold_to_check(spec, delivery):
    measures = strict.seam_measures(delivery["bassA"], body_seconds(spec, "bassA"))
    assert measures["fold_db"] is None and measures["click_db"] < 0.0
    result = strict.seam_check(delivery["bassA"], "bassA", body_seconds(spec, "bassA"), 30.0, 6.0)
    assert result["status"] == "pass" and "fold n/a" in result["summary"]


def test_seam_of_a_perfectly_periodic_loop_is_clean():
    body = 2.0
    t = np.arange(int(round((body + 0.05) * RATE))) / float(RATE)
    tone = 0.5 * np.sin(2 * np.pi * 500.0 * t)                  # 500 Hz: 96 samples a period, so the tail continues the head
    loop = Audio(np.stack([tone, tone], axis=1), RATE)
    measures = strict.seam_measures(loop, body)
    assert measures["fold_db"] == pytest.approx(0.0, abs=0.5) and measures["tail_ms"] == pytest.approx(50.0, abs=0.1)
    assert measures["click_db"] < 6.0          # a pure low tone has no high-frequency material to compare against: the floor is -80 dB
    assert strict.seam_check(loop, "tone", body, 30.0, 6.0)["status"] == "pass"


def test_seam_needs_a_tail_to_crossfade_into():
    t = np.arange(int(2.0 * RATE)) / float(RATE)
    body_only = Audio(np.stack([0.5 * np.sin(2 * np.pi * 500.0 * t)] * 2, axis=1), RATE)
    assert strict.seam_measures(body_only, 2.0) is None
    result = strict.seam_check(body_only, "x", 2.0, 30.0, 6.0)
    assert result["status"] == "fail" and "no tail to crossfade into" in result["summary"]
    stub = Audio(np.vstack([body_only.samples, np.zeros((int(0.005 * RATE), 2))]), RATE)       # 5 ms: shorter than the 10 ms crossfade
    assert strict.seam_measures(stub, 2.0) is None
    ok = Audio(np.vstack([body_only.samples, np.zeros((int(0.010 * RATE), 2))]), RATE)          # exactly one crossfade
    assert strict.seam_measures(ok, 2.0)["tail_ms"] == pytest.approx(10.0, abs=0.1)
    assert strict.seam_measures(ok, 0.0) is None                                                # no body at all


def test_seam_crossfade_length_is_a_parameter():
    t = np.arange(int(2.05 * RATE)) / float(RATE)
    loop = Audio(np.stack([0.5 * np.sin(2 * np.pi * 500.0 * t)] * 2, axis=1), RATE)
    assert strict.seam_measures(loop, 2.0, crossfade_ms=10.0) is not None
    assert strict.seam_measures(loop, 2.0, crossfade_ms=60.0) is None                           # the 50 ms tail is too short for 60 ms


def test_seam_works_on_mono_files():
    t = np.arange(int(2.05 * RATE)) / float(RATE)
    mono = Audio(0.5 * np.sin(2 * np.pi * 500.0 * t), RATE)
    assert mono.channels == 1 and strict.seam_check(mono, "mono", 2.0, 30.0, 6.0)["status"] == "pass"


# ---------------------------------------------------------------------------
# file.start
# ---------------------------------------------------------------------------


def test_start_check_with_a_note_on_beat_one(delivery):
    kick = delivery["kick"]
    assert strict.onset_ms(kick) < 1.0
    passed = strict.start_check(kick, "kick", True, 5.0)
    assert passed["status"] == "pass" and passed["check"] == "file.start" and passed["value"] < 1.0 and passed["target"] == 0.0
    assert passed["tolerance"] == 5.0 and passed["unit"] == "ms"
    padded = Audio(np.vstack([np.zeros((int(0.020 * RATE), 2)), kick.samples]), RATE)         # 20 ms of silence in front
    assert strict.onset_ms(padded) == pytest.approx(20.2, abs=0.5)
    failed = strict.start_check(padded, "kick", True, 5.0)
    assert failed["status"] == "fail" and "padding before bar 1" in failed["summary"] and failed["value"] == pytest.approx(20.2, abs=0.5)


def test_start_check_passes_notes_with_slow_attacks_that_begin_at_the_first_sample(delivery):
    for part in ("pad", "bassA", "leadA"):
        assert np.abs(delivery[part].samples[:48]).max() > 1e-4, part                       # the part really does start sounding at sample 0
        assert strict.start_check(delivery[part], part, True, 5.0)["status"] == "pass", part


def test_start_check_tolerance_is_a_parameter(delivery):
    padded = Audio(np.vstack([np.zeros((int(0.020 * RATE), 2)), delivery["kick"].samples]), RATE)
    assert strict.start_check(padded, "kick", True, 25.0)["status"] == "pass"
    near = Audio(np.vstack([np.zeros((int(0.004 * RATE), 2)), delivery["kick"].samples]), RATE)
    assert strict.start_check(near, "kick", True, 5.0)["status"] == "pass" and strict.start_check(near, "kick", True, 3.0)["status"] == "fail"


def test_start_check_without_a_note_on_beat_one_has_nothing_to_align(delivery):
    padded = Audio(np.vstack([np.zeros((int(0.020 * RATE), 2)), delivery["kick"].samples]), RATE)
    for item in (padded, delivery["kick"]):
        result = strict.start_check(item, "pad", False, 5.0)
        assert result["status"] == "pass" and "no note on beat 1" in result["summary"] and "value" not in result


def test_start_check_skips_when_the_notes_are_unknown(delivery):
    result = strict.start_check(delivery["kick"], "kick", None, 5.0)
    assert result["status"] == "skip" and "needs the clip's notes" in result["summary"]


def test_onset_of_a_silent_or_very_short_file_is_none_and_never_an_error():
    assert strict.onset_ms(Audio(np.zeros((3, 2)), RATE)) is None and strict.onset_ms(Audio(np.zeros((0, 2)), RATE)) is None
    assert strict.onset_ms(Audio(np.zeros((RATE, 2)), RATE)) is None                       # silence: there is no start to find
    strict.onset_ms(Audio(np.full((3, 2), 0.5), RATE))                                     # too short to measure, but no exception
    failed = strict.start_check(Audio(np.zeros((RATE, 2)), RATE), "kick", True, 5.0)
    assert failed["status"] == "fail" and "silent" in failed["summary"] and "padding before bar 1" in failed["summary"]


@pytest.mark.parametrize("attack", [0.02, 0.1, 0.3])
def test_a_note_that_swells_in_from_the_first_sample_is_not_padding(attack):
    t = np.arange(RATE) / float(RATE)
    swell = 0.3 * np.sin(2 * np.pi * 220.0 * t) * np.minimum(1.0, t / attack)
    assert strict.start_check(Audio(np.stack([swell, swell], axis=1), RATE), "pad", True, 5.0)["status"] == "pass"


def test_onset_finds_the_steepest_attack_in_the_first_60_ms():
    x = np.zeros((RATE // 2, 2))
    x[int(0.012 * RATE):int(0.012 * RATE) + 4800] = 0.5
    assert strict.onset_ms(Audio(x, RATE)) == pytest.approx(12.0, abs=0.6)
    assert strict.onset_ms(Audio(np.full((RATE // 2, 2), 0.5), RATE)) < 1.0      # a file that starts at full level has its attack at 0 ms


def test_start_check_fails_on_padding_longer_than_the_search_window(delivery):
    for padding_ms in (61, 100, 500):
        padded = Audio(np.vstack([np.zeros((int(padding_ms / 1000.0 * RATE), 2)), delivery["kick"].samples]), RATE)
        assert strict.start_check(padded, "kick", True, 5.0)["status"] == "fail", padding_ms


# ---------------------------------------------------------------------------
# file.format
# ---------------------------------------------------------------------------


def written(tmp_path, rate=RATE, depth=24, channels=2):
    path = audio.write_wav(tmp_path / "f{0}_{1}_{2}.wav".format(rate, depth, channels), np.zeros((4800, channels)) + 0.1, rate, depth)
    return audio.read_wav(path)


def test_format_check_passes_for_48k_24_bit_stereo(tmp_path):
    result = strict.format_check(written(tmp_path), "pad", 48000, 24, 2)
    assert result["status"] == "pass" and result["check"] == "file.format" and result["summary"] == "48000 Hz, 24-bit, 2 ch"


@pytest.mark.parametrize("rate, depth, channels, fragment", [
    (44100, 24, 2, "44100 Hz (want 48000)"),
    (96000, 24, 2, "96000 Hz (want 48000)"),
    (48000, 32, 2, "32-bit float (want 24-bit PCM)"),
    (48000, 16, 2, "16-bit pcm (want 24-bit PCM)"),
    (48000, 24, 1, "1 channels (want 2)"),
    (44100, 32, 1, "44100 Hz (want 48000); 32-bit float (want 24-bit PCM); 1 channels (want 2)"),
])
def test_format_check_names_every_difference(tmp_path, rate, depth, channels, fragment):
    result = strict.format_check(written(tmp_path, rate, depth, channels), "pad", 48000, 24, 2)
    assert result["status"] == "fail" and fragment in result["summary"]


def test_format_check_follows_the_arguments(tmp_path):
    cd = written(tmp_path, 44100, 16, 2)
    assert strict.format_check(cd, "x", 44100, 16, 2)["status"] == "pass"
    assert strict.format_check(cd, "x", "44100", "16", "2")["status"] == "pass"       # spec values may arrive as text
    flt = written(tmp_path, 48000, 32, 2)
    assert strict.format_check(flt, "x", 48000, 32, 2)["status"] == "fail"             # float is never the delivery format


# ---------------------------------------------------------------------------
# file_checks
# ---------------------------------------------------------------------------


def test_file_checks_for_a_clean_loop(spec, delivery):
    checks = strict.file_checks(delivery["pad"], "pad", spec, bpm=TEMPO, bars=16)
    assert [item["check"] for item in checks] == ["file.duration", "file.seam", "file.start", "file.format"]
    assert [item["status"] for item in checks] == ["pass", "pass", "skip", "pass"]
    assert all(item["subject"] == "pad" for item in checks)
    assert [item["status"] for item in strict.file_checks(delivery["pad"], "pad", spec, bpm=TEMPO, bars=16, has_downbeat_note=False)][2] == "pass"
    assert [item["status"] for item in strict.file_checks(delivery["kick"], "kick", spec, bpm=TEMPO, bars=2, has_downbeat_note=True)] == ["pass"] * 4


@pytest.mark.parametrize("key, part_id, bars, failing", [
    ("seam_click", "pad", 16, ["file.seam"]),
    ("unfolded", "pad", 16, ["file.seam"]),
    ("short_5ms", "bassA", 8, ["file.duration"]),
])
def test_file_checks_catch_each_planted_defect(spec, delivery, key, part_id, bars, failing):
    checks = strict.file_checks(delivery[key], part_id, spec, bpm=TEMPO, bars=bars)
    assert [item["check"] for item in checks if item["status"] == "fail"] == failing


def test_file_checks_use_the_specs_tolerances(spec, delivery):
    import copy
    data = copy.deepcopy(spec.data)
    data["tolerances"]["duration_ms"] = 10.0                                     # lenient: the 5 ms short file passes
    lenient = specs.Spec(data)
    assert [item["status"] for item in strict.file_checks(delivery["short_5ms"], "bassA", lenient, bpm=TEMPO, bars=8)][0] == "pass"
    data["targets"]["sample_rate"] = 44100
    assert [item["status"] for item in strict.file_checks(delivery["pad"], "pad", specs.Spec(data), bpm=TEMPO, bars=16)][-1] == "fail"


def test_file_checks_for_one_shots_and_fills(spec):
    t = np.arange(int(round((3.0 + 0.05) * RATE))) / float(RATE)
    looped = Audio(np.stack([0.2 * np.sin(2 * np.pi * 500.0 * t)] * 2, axis=1), RATE)
    checks = strict.file_checks(looped, "title", spec, seconds=3.0)               # a looped one-shot: seconds + the tail
    assert [item["check"] for item in checks] == ["file.duration", "file.seam", "file.start", "file.format"]
    assert checks[0]["status"] == "pass" and checks[0]["target"] == pytest.approx(3.05, abs=1e-3)
    no_tail = Audio(looped.samples[:int(round(3.0 * RATE))], RATE)
    one_shot = strict.file_checks(no_tail, "gameover", spec, seconds=3.0, loop=False)  # a one-shot keeps its natural end: no tail, no seam
    assert [item["check"] for item in one_shot] == ["file.duration", "file.start", "file.format"]
    assert one_shot[0]["status"] == "pass" and one_shot[0]["target"] == pytest.approx(3.0, abs=1e-3)
    fill = Audio(np.zeros((int(round(spec.bar_seconds(TEMPO) * RATE)), 2)), RATE)
    fill_checks = strict.file_checks(fill, "levelup_fill", spec, bpm=TEMPO, bars=1, loop=False)
    assert [item["check"] for item in fill_checks] == ["file.duration", "file.start", "file.format"]
    assert fill_checks[0]["target"] == pytest.approx(spec.bar_seconds(TEMPO) + spec.tail_seconds(), abs=1e-3)
    assert fill_checks[0]["status"] == "fail"                                      # this fill lacks its 50 ms tail


def test_file_checks_without_a_length_only_check_start_and_format(spec, delivery):
    checks = strict.file_checks(delivery["pad"], "pad", spec)
    assert [item["check"] for item in checks] == ["file.start", "file.format"]
    assert [item["check"] for item in strict.file_checks(delivery["pad"], "pad", spec, bars=16)] == ["file.start", "file.format"]    # bars without bpm


def test_every_strict_check_is_a_fail_level_check(spec, delivery):
    checks = strict.file_checks(delivery["short_5ms"], "bassA", spec, bpm=TEMPO, bars=8)
    assert {item["status"] for item in checks} <= {"pass", "fail", "skip"}          # never warn or info
