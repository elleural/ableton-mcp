"""Unit tests for ears/tiers.py: loop playback as the game does it (equal-power 10 ms crossfade over the loop seam,
the old voice cut after it) and the cumulative tier sums (PRD section 8, soundtrack PRD section 8).

Everything here uses constant or two-level signals at a low sample rate, so the arithmetic is exact and fast.
"""
import math

import numpy as np
import pytest

from ears import spec as specs
from ears import tiers
from ears.audio import Audio

RATE = 8000
FADE = 80                                  # 10 ms at 8 kHz


@pytest.fixture(scope="module")
def spec():
    return specs.load("nova")


def constant(value, seconds, rate=RATE, channels=2):
    return Audio(np.full((int(round(seconds * rate)), channels), float(value)), rate)


# ---------------------------------------------------------------------------
# crossfade_curves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("frames", [1, 2, 80, 480, 4800])
def test_crossfade_curves_are_equal_power(frames):
    fade_out, fade_in = tiers.crossfade_curves(frames)
    assert len(fade_out) == len(fade_in) == frames
    assert np.allclose(fade_out ** 2 + fade_in ** 2, 1.0)
    assert np.all(np.diff(fade_out) <= 0) and np.all(np.diff(fade_in) >= 0)
    assert np.all((fade_out >= 0) & (fade_out <= 1) & (fade_in >= 0) & (fade_in <= 1))


def test_crossfade_curves_start_at_the_old_voice_and_end_at_the_new_one():
    fade_out, fade_in = tiers.crossfade_curves(480)
    assert fade_out[0] > 0.9999 and fade_in[0] < 0.002 and fade_out[-1] < 0.002 and fade_in[-1] > 0.9999
    mid_out, mid_in = tiers.crossfade_curves(481)
    assert mid_out[240] == pytest.approx(math.sqrt(0.5)) and mid_in[240] == pytest.approx(math.sqrt(0.5))   # -3 dB each at the centre


def test_crossfade_curves_of_nothing_are_empty():
    for frames in (0, -5):
        fade_out, fade_in = tiers.crossfade_curves(frames)
        assert len(fade_out) == 0 and len(fade_in) == 0


# ---------------------------------------------------------------------------
# tile()
# ---------------------------------------------------------------------------


def seam_windows(body_frames, count):
    return [(k * body_frames, k * body_frames + FADE) for k in range(1, count)]


def test_a_constant_signal_stays_constant_apart_from_the_crossfade_bump():
    body_s, tail_s, level = 0.5, 0.05, 0.25
    out = tiers.tile(constant(level, body_s + tail_s), body_s, 2.0, crossfade_ms=10.0)
    body_frames = int(round(body_s * RATE))
    assert out.rate == RATE and out.channels == 2
    assert out.frames == int(round(2.0 * RATE)) + int(round(tail_s * RATE))      # the last iteration keeps its natural end
    x = out.samples[:, 0]
    keep = np.ones(out.frames, dtype=bool)
    windows = seam_windows(body_frames, 4)                                       # four iterations: three seams
    assert len(windows) == 3
    for start, end in windows:
        keep[start:end] = False
    assert np.allclose(x[keep], level, atol=1e-12)
    for start, end in windows:
        inside = x[start:end]
        assert inside.max() <= level * math.sqrt(2.0) + 1e-9                       # at most +3.01 dB
        assert inside.max() >= level * 1.40                                        # and the bump is really there
        assert inside.min() >= level - 1e-9                                        # equal power never dips below one voice at full level
        assert 20 * math.log10(inside.max() / level) <= 3.02
    assert np.array_equal(out.samples[:, 0], out.samples[:, 1])


def test_the_seam_follows_the_equal_power_formula():
    """Old voice: the file's tail faded out; new voice: the head faded in; they add."""
    body_s, tail_s = 0.5, 0.05
    body_frames = int(round(body_s * RATE))
    body_level, tail_level = 1.0, 0.5
    file = np.vstack([np.full((body_frames, 2), body_level), np.full((int(round(tail_s * RATE)), 2), tail_level)])
    out = tiers.tile(Audio(file, RATE), body_s, 1.0, crossfade_ms=10.0)
    fade_out, fade_in = tiers.crossfade_curves(FADE)
    x = out.samples[:, 0]
    assert np.allclose(x[body_frames:body_frames + FADE], tail_level * fade_out + body_level * fade_in)
    assert np.allclose(x[:body_frames], body_level)                                # nothing fades in on the first iteration
    assert np.allclose(x[body_frames + FADE:2 * body_frames], body_level)         # the old voice's tail is gone after the fade
    assert np.allclose(x[2 * body_frames:], tail_level)                           # the last iteration keeps its tail
    assert out.frames == 2 * body_frames + int(round(tail_s * RATE))


def test_the_old_voice_stops_after_the_crossfade_even_when_its_tail_is_loud():
    body_s, tail_s = 0.5, 0.05
    body_frames = int(round(body_s * RATE))
    tail_frames = int(round(tail_s * RATE))
    file = np.vstack([np.zeros((body_frames, 2)), np.full((tail_frames, 2), 0.9)])       # silence, then a loud tail
    x = tiers.tile(Audio(file, RATE), body_s, 1.5, crossfade_ms=10.0).samples[:, 0]
    for k in (1, 2):                                                                     # seams after iterations 0 and 1
        seam = k * body_frames
        assert x[seam + FADE:seam + tail_frames].max() == 0.0                           # the tail past the fade does not sound
        assert x[seam:seam + FADE].max() > 0.85                                         # but it is heard while it fades out
    assert x[3 * body_frames:].max() == pytest.approx(0.9)                              # the final iteration's tail rings out


def test_tile_hard_cuts_when_the_crossfade_is_zero():
    body_s = 0.5
    body_frames = int(round(body_s * RATE))
    file = np.vstack([np.full((body_frames, 2), 1.0), np.full((400, 2), 0.5)])
    x = tiers.tile(Audio(file, RATE), body_s, 1.0, crossfade_ms=0.0).samples[:, 0]
    assert np.all(x[:body_frames] == 1.0) and np.all(x[body_frames:2 * body_frames] == 1.0) and np.all(x[2 * body_frames:] == 0.5)


def test_tile_starts_each_iteration_on_its_own_bar_clock_without_drift():
    rate, body_s = 48000, 60.0 / 140 * 4 * 2             # two bars at 140 BPM: 3.428571... s, not a whole number of samples
    body = body_s * rate
    marker = np.zeros((int(round(body)) + 2400, 2))
    marker[:, 0] = 0.0
    marker[100, 0] = 1.0                                  # a click 100 frames into every iteration
    out = tiers.tile(Audio(marker, rate), body_s, body_s * 8, crossfade_ms=0.0)
    clicks = np.flatnonzero(out.samples[:, 0] > 0.5)
    expected = [int(round(k * body)) + 100 for k in range(8)]
    assert clicks.tolist() == expected                    # each at k * body, rounded once, never accumulated


def test_tile_turns_mono_into_stereo_and_keeps_the_rate():
    mono = Audio(np.full((int(0.55 * RATE), 1), 0.3), RATE)
    out = tiers.tile(mono, 0.5, 1.0)
    assert out.channels == 2 and out.rate == RATE and np.allclose(out.samples[0], 0.3)
    assert tiers.tile(Audio(np.full((int(0.55 * 44100), 2), 0.3), 44100), 0.5, 1.0).rate == 44100


def test_tile_for_less_than_one_iteration_plays_the_file_once():
    out = tiers.tile(constant(0.3, 0.55), 0.5, 0.25)
    assert out.frames == int(round(0.25 * RATE)) + int(round(0.55 * RATE)) - int(round(0.5 * RATE))
    assert np.allclose(out.samples[:, 0], 0.3)                                       # no seam inside it, no fade-in on iteration 0


def test_tile_when_the_total_is_not_a_whole_number_of_loops_rounds_up():
    out = tiers.tile(constant(0.3, 0.55), 0.5, 1.2)                                  # 2.4 loops: three iterations, the third cut at 1.2 s + tail
    assert out.frames == int(round(1.2 * RATE)) + int(round(0.55 * RATE)) - int(round(0.5 * RATE))
    x = out.samples[:, 0]
    assert x[int(1.0 * RATE) + FADE:].min() == pytest.approx(0.3)
    assert x.max() <= 0.3 * math.sqrt(2.0) + 1e-9


def test_tile_does_not_modify_its_input():
    source = constant(0.25, 0.55)
    before = source.samples.copy()
    tiers.tile(source, 0.5, 2.0)
    assert np.array_equal(source.samples, before)


# ---------------------------------------------------------------------------
# tier_sums
# ---------------------------------------------------------------------------

BAR = 2.0                                                         # one bar at 120 BPM
LEVELS = {"pad": 0.01, "arpA": 0.02, "bassA": 0.04, "kick": 0.08, "perc": 0.16, "leadA": 0.32,
          "arpB": 0.5, "bassB": 0.25, "leadB": 0.125}


def parts_at_120(spec, only=None, rate=RATE):
    """Constant parts of the right file length (bars x bar + tail), each at its own level."""
    bars = dict((part.id, part.bars) for part in spec.parts("neon"))
    out = {}
    for part_id, level in LEVELS.items():
        if only is not None and part_id not in only:
            continue
        out[part_id] = constant(level, bars[part_id] * BAR + spec.tail_seconds(), rate)
    return out


def middle(sum_audio, seconds):
    return float(sum_audio.samples[int(seconds * RATE), 0])


def test_tier_sums_are_cumulative(spec):
    sums, missing = tiers.tier_sums(parts_at_120(spec), spec, "neon", "A", 120.0)
    assert missing == [] and list(sums) == ["T1", "T2", "T3", "T4", "T5"]
    # one bar in: far from every seam (kick seams are at 0, 2, 4 ... bars)
    expected = {"T1": 0.01 + 0.02, "T2": 0.01 + 0.02 + 0.04, "T3": 0.01 + 0.02 + 0.04 + 0.08,
                "T4": 0.01 + 0.02 + 0.04 + 0.08 + 0.16, "T5": 0.01 + 0.02 + 0.04 + 0.08 + 0.16 + 0.32}
    for tier, value in expected.items():
        assert middle(sums[tier], 1.0 * BAR) == pytest.approx(value, abs=1e-9), tier
        assert middle(sums[tier], 9.0 * BAR) == pytest.approx(value, abs=1e-9), tier
    assert [middle(sums[tier], BAR) for tier in sums] == sorted(middle(sums[tier], BAR) for tier in sums)    # each tier adds to the last


def test_tier_sums_are_stereo_audio_of_the_longest_loop_plus_the_tail(spec):
    sums, _ = tiers.tier_sums(parts_at_120(spec), spec, "neon", "A", 120.0)
    expected_frames = int(round(16 * BAR * RATE)) + int(round(spec.tail_seconds() * RATE))
    for audio in sums.values():
        assert isinstance(audio, Audio) and audio.channels == 2 and audio.rate == RATE
        assert abs(audio.frames - expected_frames) <= 1
    assert len(set(audio.frames for audio in sums.values())) == 1


def test_tier_sums_play_each_part_at_its_own_loop_length(spec):
    sums, _ = tiers.tier_sums(parts_at_120(spec), spec, "neon", "A", 120.0)
    t5 = sums["T5"].samples[:, 0]
    kick_seam = int(round(2 * BAR * RATE))                                          # the kick loops every 2 bars: the only seam here
    steady = t5[kick_seam + FADE + 100]
    assert steady == pytest.approx(0.63, abs=1e-9)
    bump = t5[kick_seam:kick_seam + FADE]
    assert bump.max() == pytest.approx(0.63 - 0.08 + 0.08 * math.sqrt(2.0), abs=1e-3)   # only the kick's own equal-power bump
    assert bump.min() >= 0.63 - 1e-9
    perc_seam = int(round(4 * BAR * RATE))                                          # 4 bars: the perc's seam, and the kick's again
    assert t5[perc_seam:perc_seam + FADE].max() == pytest.approx(0.63 - 0.24 + 0.24 * math.sqrt(2.0), abs=1e-3)
    assert t5[perc_seam - 1000:perc_seam - 100].std() < 1e-9                        # steady just before it: no seam anywhere else
    all_seam = int(round(8 * BAR * RATE))                                           # 8 bars: everything but the 16-bar pad loops
    assert t5[all_seam:all_seam + FADE].max() == pytest.approx(0.01 + 0.62 * math.sqrt(2.0), abs=1e-3)


def test_tier_sums_for_the_other_variation_use_its_parts(spec):
    sums_b, missing = tiers.tier_sums(parts_at_120(spec), spec, "neon", "B", 120.0)
    assert missing == [] and list(sums_b) == ["T1", "T2", "T3", "T4", "T5"]
    assert middle(sums_b["T1"], BAR) == pytest.approx(0.01 + 0.5, abs=1e-9)           # pad + arpB
    assert middle(sums_b["T2"], BAR) == pytest.approx(0.01 + 0.5 + 0.25, abs=1e-9)    # + bassB
    assert middle(sums_b["T5"], BAR) == pytest.approx(0.01 + 0.5 + 0.25 + 0.08 + 0.16 + 0.125, abs=1e-9)


def test_missing_parts_are_listed_and_the_rest_still_sums(spec):
    present = parts_at_120(spec, only={"pad", "arpA", "kick", "perc", "leadA"})       # bassA is missing
    sums, missing = tiers.tier_sums(present, spec, "neon", "A", 120.0)
    assert missing == ["bassA"]
    assert list(sums) == ["T1", "T2", "T3", "T4", "T5"]
    assert middle(sums["T1"], BAR) == pytest.approx(0.03, abs=1e-9)
    assert middle(sums["T2"], BAR) == pytest.approx(0.03, abs=1e-9)                   # T2 adds a part that is not there
    assert middle(sums["T3"], BAR) == pytest.approx(0.03 + 0.08, abs=1e-9)
    assert middle(sums["T5"], BAR) == pytest.approx(0.03 + 0.08 + 0.16 + 0.32, abs=1e-9)


def test_missing_parts_are_reported_in_spec_order(spec):
    present = parts_at_120(spec, only={"pad", "arpA", "leadA"})
    sums, missing = tiers.tier_sums(present, spec, "neon", "A", 120.0)
    assert missing == ["kick", "perc", "bassA"]
    assert middle(sums["T5"], BAR) == pytest.approx(0.01 + 0.02 + 0.32, abs=1e-9)


def test_tiers_with_no_parts_are_left_out(spec):
    only_bass_and_up = parts_at_120(spec, only={"bassA", "kick", "perc", "leadA"})
    sums, missing = tiers.tier_sums(only_bass_and_up, spec, "neon", "A", 120.0)
    assert missing == ["pad", "arpA"]
    assert list(sums) == ["T2", "T3", "T4", "T5"]                                      # T1 (pad + arp) has nothing
    assert middle(sums["T2"], BAR) == pytest.approx(0.04, abs=1e-9)


def test_no_parts_at_all_gives_no_sums(spec):
    sums, missing = tiers.tier_sums({}, spec, "neon", "A", 120.0)
    assert sums == {} and missing == ["kick", "perc", "pad", "bassA", "arpA", "leadA"]


def test_variation_b_does_not_count_the_a_parts_as_missing(spec):
    only_a = parts_at_120(spec, only={"pad", "arpA", "bassA", "kick", "perc", "leadA"})
    sums, missing = tiers.tier_sums(only_a, spec, "neon", "B", 120.0)
    assert missing == ["bassB", "arpB", "leadB"]
    assert middle(sums["T1"], BAR) == pytest.approx(0.01, abs=1e-9)                    # only the shared pad is there


def test_total_bars_shortens_the_sums(spec):
    sums, _ = tiers.tier_sums(parts_at_120(spec), spec, "neon", "A", 120.0, total_bars=8)
    assert abs(sums["T5"].frames - (int(round(8 * BAR * RATE)) + int(round(spec.tail_seconds() * RATE)))) <= 1


def test_tier_sums_take_the_sample_rate_from_the_parts(spec):
    parts = parts_at_120(spec, rate=16000)
    sums, _ = tiers.tier_sums(parts, spec, "neon", "A", 120.0)
    assert all(audio.rate == 16000 for audio in sums.values())


def test_tier_sums_mainframe_follows_the_same_tier_ladder(spec):
    bars = dict((part.id, part.bars) for part in spec.parts("mainframe"))
    parts = dict((part_id, constant(level, bars[part_id] * BAR + spec.tail_seconds()))
                 for part_id, level in LEVELS.items() if part_id in bars)
    sums, missing = tiers.tier_sums(parts, spec, "mainframe", "B", 120.0)
    assert missing == [] and middle(sums["T2"], BAR) == pytest.approx(0.01 + 0.5 + 0.25, abs=1e-9)


# ---------------------------------------------------------------------------
# loop_body
# ---------------------------------------------------------------------------


def test_loop_body_drops_the_tail():
    file = constant(0.5, 2.0 + 0.05)                                                  # 1 bar at 120 BPM x 1 + tail
    body = tiers.loop_body(file, 1, 120.0)
    assert body.frames == int(round(2.0 * RATE)) and body.rate == RATE
    assert tiers.loop_body(constant(0.5, 4.05), 1, 120.0).frames == int(round(2.0 * RATE))
    assert tiers.loop_body(file, 1, 120.0, beats_per_bar=3.0).frames == int(round(1.5 * RATE))
