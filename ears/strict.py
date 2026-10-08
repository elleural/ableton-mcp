"""Strict mode: the delivery-file checks of soundtrack PRD sections 6 and 7.5 (PRD section 8, all fail level).

- file.duration  length is bars x 240 / BPM + 0.050 s, within 1 ms (one-shots: the spec's seconds)
- file.seam      the loop seam as the game plays it (the tail crossfaded into the head over 10 ms,
                 equal power). Both measures are relative to the material, so a downbeat is not a
                 click and a sidechain duck is not a level jump:
                   fold   what rings at the end of the body (reverb, delay, held notes) carries over
                          into the head's first 3 ms: an unfolded head starts from silence, more
                          than 30 dB below the ringing.
                          The tail itself is not compared: a render that continued into another
                          scene after the loop (the NOVA masters) has a tail unlike the head
                   click  high-frequency (> 4 kHz) energy at the seam stays within 6 dB of the
                          loudest transient inside the body (the equal-power crossfade alone adds
                          up to 3 dB on a downbeat)
- file.start     no padding before bar 1: where the clip has a note on beat 1, the transient is at
                 the start of the file (within 5 ms)
- file.format    48 kHz, 24-bit, stereo
"""
import numpy as np
from scipy import signal as sps

from . import report
from .tiers import crossfade_curves

SEAM_WINDOW_MS = 40.0
ENVELOPE_MS = 1.0
CLICK_HIGHPASS_HZ = 4000.0
FLOOR_DB = -100.0
RINGING_DB = -60.0   # dBFS: below this the body ends in silence and there is nothing to fold


def expected_seconds(bars, bpm, beats_per_bar, tail_s):
    return bars * beats_per_bar * 60.0 / float(bpm) + tail_s


def duration_check(audio, subject, expected, tolerance_ms):
    actual = audio.duration
    error_ms = (actual - expected) * 1000.0
    ok = abs(error_ms) <= tolerance_ms
    return report.check("file.duration", "pass" if ok else "fail", subject,
                        "{0:.4f} s, {1:+.2f} ms from {2:.4f} s".format(actual, error_ms, expected),
                        value=round(actual, 6), target=round(expected, 6), tolerance=tolerance_ms, unit="s",
                        error_ms=round(error_ms, 3))


def _envelope_db(samples, rate, window_ms=ENVELOPE_MS):
    """RMS envelope in dB of a mono signal, one value per sample (centered moving window)."""
    size = max(1, int(round(window_ms / 1000.0 * rate)))
    power = np.convolve(samples * samples, np.ones(size) / size, mode="same")
    return 10.0 * np.log10(np.maximum(power, 10 ** (FLOOR_DB / 10.0)))


def _level_db(samples):
    if not samples.size:
        return FLOOR_DB
    value = float(np.mean(samples * samples))
    return 10.0 * np.log10(value) if value > 10 ** (FLOOR_DB / 10.0) else FLOOR_DB


def seam_measures(audio, body_seconds, crossfade_ms=10.0, bar_seconds=None):  # bar_seconds: kept for callers
    """Seam measures of a loop file (None when it has no tail to crossfade into).

    fold_db   level of the head's first 3 ms minus the level of the body's last 20 ms. A folded head
              carries the previous cycle's ringing (reverb, delay, held notes) over the seam; an
              unfolded one starts from silence while the body still rings, a drop of tens of dB.
              None when the body ends in silence (below -60 dBFS)
    click_db  high-frequency energy at the seam as the game plays it (the tail crossfaded into the
              head) above the loudest high-frequency transient inside the body
    tail_ms   length of the tail past the loop body
    """
    rate = audio.rate
    x = audio.stereo().mean(axis=1)
    body = int(round(body_seconds * rate))
    tail_frames = x.shape[0] - body
    fade = int(round(crossfade_ms / 1000.0 * rate))
    if tail_frames < fade or fade <= 0 or body <= 0:
        return None
    window = min(tail_frames, int(round(SEAM_WINDOW_MS / 1000.0 * rate)))
    ringing = _level_db(x[body - int(0.020 * rate):body])          # what still sounds at the end of the body
    start = _level_db(x[:max(1, int(0.003 * rate))])                 # what the head carries over in its first 3 ms
    fold = start - ringing if ringing > RINGING_DB else None
    head, tail = x[:window], x[body:body + window]
    fade_out, fade_in = crossfade_curves(fade)
    seamed = head.copy()
    seamed[:fade] = tail[:fade] * fade_out + head[:fade] * fade_in
    pre = x[max(0, body - window):body]
    game = np.concatenate([pre, seamed])          # what the player hears across the seam
    sos = sps.butter(4, CLICK_HIGHPASS_HZ, "highpass", fs=rate, output="sos")
    game_hf = _envelope_db(sps.sosfilt(sos, game), rate)
    body_hf = _envelope_db(sps.sosfilt(sos, x[:body]), rate)
    zone = game_hf[max(0, len(pre) - int(0.001 * rate)):len(pre) + fade + int(0.005 * rate)]
    inner = body_hf[int(SEAM_WINDOW_MS / 1000.0 * rate):max(0, body - int(SEAM_WINDOW_MS / 1000.0 * rate))]
    material = float(np.max(inner)) if inner.size else FLOOR_DB
    click = float(np.max(zone)) - max(material, FLOOR_DB + 20.0)
    return {"fold_db": None if fold is None else round(float(fold), 2), "click_db": round(click, 2),
            "tail_ms": round(tail_frames / rate * 1000.0, 2)}


def seam_check(audio, subject, body_seconds, level_db, click_db, crossfade_ms=10.0, bar_seconds=None):
    measures = seam_measures(audio, body_seconds, crossfade_ms, bar_seconds)
    if measures is None:
        return report.check("file.seam", "fail", subject, "the file has no tail to crossfade into (shorter than {0:g} ms past the loop)".format(crossfade_ms))
    problems = []
    if measures["fold_db"] is not None and measures["fold_db"] < -level_db:
        problems.append("the loop starts {0:.0f} dB below the ringing at its end: the tail is not folded".format(-measures["fold_db"]))
    if measures["click_db"] > click_db:
        problems.append("{0:.1f} dB of high-frequency energy above the material's own transients at the seam (click)".format(measures["click_db"]))
    summary = "; ".join(problems) or "fold {0}, click {1:+.1f} dB".format(
        "n/a" if measures["fold_db"] is None else "{0:+.1f} dB".format(measures["fold_db"]), measures["click_db"])
    return report.check("file.seam", "fail" if problems else "pass", subject, summary, value=measures,
                        target={"fold_db": -level_db, "click_db": click_db})


def onset_ms(audio, search_ms=60.0, silence_db=-60.0):
    """Where sound starts in the opening `search_ms` of the file, in ms (None if that window is silent).

    The start is the first sample above 1 % of the window's peak (and above -80 dBFS), so a note that
    swells in from the first sample starts at 0 whatever its attack time, and leading digital silence
    (padding before bar 1) is measured exactly. None when the whole window stays below `silence_db`.
    """
    x = np.abs(audio.samples).max(axis=1)[:int(search_ms / 1000.0 * audio.rate)]
    if x.size < 4:
        return None
    peak = float(x.max())
    if peak <= 10 ** (silence_db / 20.0):
        return None
    return float(np.argmax(x >= max(10 ** (-80.0 / 20.0), 0.01 * peak))) / audio.rate * 1000.0


def start_check(audio, subject, has_downbeat_note, tolerance_ms):
    if has_downbeat_note is None:
        return report.check("file.start", "skip", subject, "needs the clip's notes to know whether bar 1 beat 1 sounds")
    if not has_downbeat_note:
        return report.check("file.start", "pass", subject, "no note on beat 1; nothing to align")
    position = onset_ms(audio)
    if position is None:
        return report.check("file.start", "fail", subject, "the clip has a note on beat 1 but the file's first 60 ms are silent "
                            "(padding before bar 1)", target=0.0, tolerance=tolerance_ms, unit="ms")
    ok = position <= tolerance_ms
    return report.check("file.start", "pass" if ok else "fail", subject,
                        "beat-1 transient at {0:.1f} ms".format(position) + ("" if ok else " (padding before bar 1)"),
                        value=round(position, 2), target=0.0, tolerance=tolerance_ms, unit="ms")


def format_check(audio, subject, rate, bit_depth, channels):
    problems = []
    if audio.rate != int(rate):
        problems.append("{0} Hz (want {1})".format(audio.rate, int(rate)))
    if audio.bit_depth != int(bit_depth) or audio.format == "float":
        problems.append("{0}-bit {1} (want {2}-bit PCM)".format(audio.bit_depth, audio.format, int(bit_depth)))
    if audio.channels != int(channels):
        problems.append("{0} channels (want {1})".format(audio.channels, int(channels)))
    return report.check("file.format", "fail" if problems else "pass", subject,
                        "; ".join(problems) or "{0} Hz, {1}-bit, {2} ch".format(audio.rate, audio.bit_depth, audio.channels))


def file_checks(audio, subject, spec, bpm=None, bars=None, seconds=None, loop=True, has_downbeat_note=None):
    """All strict checks for one delivery file. Loops give bars and bpm; one-shots give seconds."""
    tolerances = spec.tolerances
    tail = spec.tail_seconds()
    checks = []
    if bars is not None and bpm:
        expected = expected_seconds(bars, bpm, spec.beats_per_bar, tail)
        body = expected - tail
    elif seconds is not None:
        expected = float(seconds) + (tail if loop else 0.0)
        body = float(seconds)
    else:
        expected = body = None
    if expected is not None:
        checks.append(duration_check(audio, subject, expected, float(tolerances["duration_ms"])))
    if loop and body is not None:
        checks.append(seam_check(audio, subject, body, float(tolerances["seam_fold_db"]), float(tolerances["seam_click_db"]),
                                 float(spec.target("crossfade_ms", 10.0)), spec.bar_seconds(bpm) if bpm else None))
    checks.append(start_check(audio, subject, has_downbeat_note, float(tolerances["start_ms"])))
    checks.append(format_check(audio, subject, spec.target("sample_rate", 48000), spec.target("bit_depth", 24), spec.target("channels", 2)))
    return checks
