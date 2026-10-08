"""The profile of a mix: what a reference comparison measures (PRD section 11).

A profile describes the shape of a mix so that two mixes at different levels can be compared: band
balance relative to the mix's own loudness, dynamics as ratios and ranges, stereo width, low-end mono
safety, onset density, tempo and key. None of those depend on the playback level, which is what makes
a streamed reference comparable at all (PRD 11.2 M4: an external source's absolute level is uncalibrated).
Absolute figures (integrated loudness, true peak, peak and RMS) are added only when `absolute` is true,
which callers allow for the agent's own audio and for files, never for an external source.
"""
import numpy as np

from . import loudness, measure
from .audio import Audio

SHAPE_KEYS = ("seconds", "third_octave", "bands", "lra", "plr_db", "crest_db", "dynamics_spread", "width",
              "correlation", "mono_sub_loss_db", "onset_rate", "tempo", "key")
ABSOLUTE_KEYS = ("lufs_i", "true_peak_dbtp", "peak_dbfs", "rms_dbfs")
SCALAR_KEYS = ("lra", "plr_db", "crest_db", "dynamics_spread", "width", "correlation", "mono_sub_loss_db", "onset_rate")
BAND_FLOOR_DB = -60.0     # third-octave bands this far below the mix carry no balance information
MEASURE_LUFS = -14.0      # every shape measurement runs on the audio brought to this loudness


def _round(value, digits=2):
    return None if value is None else round(float(value), digits)


def profile(audio, a4_hz=440.0, crossover_hz=120.0, absolute=True):
    """Level-independent measurements of a mix, plus absolute ones when `absolute` is true.

    third_octave: dB of each band re the whole mix (the measurement ear's audio.balance uses the same);
    bands: dB of the broad bands re integrated loudness; lra: loudness range (LU); plr_db: true peak minus
    integrated loudness; crest_db: sample peak minus RMS; dynamics_spread: 90th minus 10th percentile of the
    short-term loudness (LU, gated 20 LU below the mix); width, correlation: stereo image; mono_sub_loss_db:
    what the mono sum loses below the crossover; onset_rate: onsets per second; tempo and key: estimates.
    A silent input gives {"seconds", "silent": True}.
    """
    out = {"seconds": _round(audio.duration)}
    levels = measure.levels(audio)
    if levels["silent"]:
        out["silent"] = True
        return out
    values = loudness.measure(audio, series=True)
    lufs = values["integrated"]
    # Onset, tempo and key detection have absolute floors, so the shape is measured at one loudness whatever
    # level the audio arrived at (a streamed reference's level is the player's choice).
    absolute_figures = (lufs, values["true_peak"], levels["peak_dbfs"], levels["rms_dbfs"])
    if lufs > loudness.SILENCE + 1:
        audio = Audio(audio.samples * 10.0 ** ((MEASURE_LUFS - lufs) / 20.0), audio.rate)
    third = measure.third_octave_levels(audio)
    out["third_octave"] = dict(("{0:g}".format(center), _round(value, 1))
                               for center, value in zip(third["centers"], third["relative_db"]) if value > BAND_FLOOR_DB)
    bands = measure.band_levels(audio)
    out["bands"] = dict((name, _round(item["db"] - lufs, 1)) for name, item in bands["bands"].items())
    out["lra"] = _round(values["range"], 1)
    out["plr_db"] = _round(values["true_peak"] - lufs, 1)
    out["crest_db"] = _round(levels["crest_db"], 1)
    gated = [value for value in values.get("short_term") or [] if value > lufs - 20.0]
    out["dynamics_spread"] = _round(np.percentile(gated, 90) - np.percentile(gated, 10), 1) if len(gated) >= 3 else 0.0
    stereo = measure.stereo(audio)
    out["width"] = _round(stereo["width"], 3)
    out["correlation"] = _round(stereo["correlation"], 3)
    out["mono_sub_loss_db"] = _round(measure.mono_sub(audio, crossover_hz)["loss_db"])
    out["onset_rate"] = _round(len(measure.onsets(audio)) / max(audio.duration, 1e-9))
    tempo = measure.tempo_estimate(audio)
    out["tempo"] = {"bpm": tempo["bpm"], "confidence": tempo["confidence"], "second": tempo["second"]["bpm"]}
    key = measure.key_estimate(audio, a4_hz)
    out["key"] = {"key": key["key"], "confidence": _round(key["confidence"], 3), "second": key["second"]["key"]}
    if absolute:
        out["lufs_i"] = absolute_figures[0]
        out["true_peak_dbtp"] = absolute_figures[1]
        out["peak_dbfs"] = _round(absolute_figures[2])
        out["rms_dbfs"] = _round(absolute_figures[3])
    return out


def shape_only(values):
    """The profile without any absolute figure (what an external source may keep)."""
    return dict((key, value) for key, value in values.items() if key not in ABSOLUTE_KEYS)


def same_tempo(a, b, tolerance=0.04):
    """True when two tempi agree within `tolerance` (relative) after folding octaves (60 and 120 agree)."""
    if not a or not b:
        return False
    ratio = float(a) / float(b)
    return any(abs(ratio * factor - 1.0) <= tolerance for factor in (0.5, 1.0, 2.0))
