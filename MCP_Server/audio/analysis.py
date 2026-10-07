"""Audio analysis for analyze_audio: EBU R128 loudness through ffmpeg, the rest with numpy.

Conventions: levels in dBFS where a full-scale sine peaks at 0 dBFS and has an RMS of -3.01 dBFS;
loudness in LUFS / LU (ITU-R BS.1770-4, EBU R128); true peak in dBTP (4x oversampled, by ffmpeg).
"""
import math
import re

import numpy as np

from .ffmpeg import AudioError, decode, probe, run, timeout_for

# Spectral bands (Hz). "sub" starts above DC; "high" runs to Nyquist.
BANDS = (("sub", 0.0, 60.0), ("low", 60.0, 250.0), ("low_mid", 250.0, 2000.0), ("high_mid", 2000.0, 6000.0), ("high", 6000.0, None))
CLIP_LEVEL = 0.9999         # |sample| at or above this counts as full scale (clipped)
ABSOLUTE_GATE = -70.0       # LUFS, BS.1770 gating
RELATIVE_GATE = 10.0        # LU below the ungated mean
MOMENTARY = 0.4             # s, BS.1770 block length
SHORT_TERM = 3.0            # s
CHUNK = 1 << 20

_NUMBER = r"(-?(?:\d+(?:\.\d*)?|inf)|nan)"
_FRAME = re.compile(r"t:\s*([\d.]+)\s+TARGET:.*?M:\s*" + _NUMBER + r"\s+S:\s*" + _NUMBER)


def _float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return float("nan")


def db(value):
    """20*log10 for amplitudes; -inf for zero."""
    return 20.0 * math.log10(value) if value > 0 else float("-inf")


def rounded(value, digits=2):
    """JSON-friendly number: None for -inf / nan."""
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


# ---------------------------------------------------------------------------
# Loudness (ffmpeg ebur128)
# ---------------------------------------------------------------------------


def parse_ebur128(text):
    """Integrated loudness, LRA, true peak and the 10 Hz frame log (t, M, S) from ebur128's output."""
    times, momentary, short = [], [], []
    for match in _FRAME.finditer(text):
        times.append(_float(match.group(1)))
        momentary.append(_float(match.group(2)))
        short.append(_float(match.group(3)))
    position = text.rfind("Summary:")
    if position < 0:
        raise AudioError("ffmpeg ebur128 printed no summary")
    summary = text[position:]

    def pick(pattern):
        match = re.search(pattern, summary, re.S)
        return _float(match.group(1)) if match else float("nan")

    integrated = pick(r"Integrated loudness:\s*I:\s*" + _NUMBER)
    if integrated <= ABSOLUTE_GATE:  # ffmpeg reports silence as -70 LUFS, the gate itself
        integrated = float("-inf")
    return {
        "integrated": integrated,
        "range": pick(r"Loudness range:\s*LRA:\s*" + _NUMBER),
        "true_peak": pick(r"True peak:\s*Peak:\s*" + _NUMBER),
        "t": np.array(times, dtype=float),
        "M": np.array(momentary, dtype=float),
        "S": np.array(short, dtype=float),
    }


def measure_loudness(path, info=None):
    """EBU R128 of a file: integrated (LUFS), range (LU), true peak (dBTP) and the frame log."""
    info = info or probe(path)
    options = "ebur128=peak=true" + (":dualmono=true" if info["channels"] == 1 else "")
    completed = run("ffmpeg", ["-nostats", "-i", info["path"], "-map", "0:a:0", "-af", options, "-f", "null", "-"],
                    timeout=timeout_for(info["duration"], 0.5))
    return parse_ebur128(completed.stderr.decode("utf-8", "replace"))


def gated_loudness(momentary):
    """BS.1770 integrated loudness from momentary (400 ms block) loudness values in LUFS."""
    blocks = np.asarray(momentary, dtype=float)
    blocks = blocks[np.isfinite(blocks) & (blocks > ABSOLUTE_GATE)]
    if not blocks.size:
        return float("-inf")
    threshold = 10.0 * math.log10(np.mean(10.0 ** (blocks / 10.0))) - RELATIVE_GATE
    blocks = blocks[blocks > threshold]
    if not blocks.size:
        return float("-inf")
    return 10.0 * math.log10(np.mean(10.0 ** (blocks / 10.0)))


# ---------------------------------------------------------------------------
# Statistics (numpy)
# ---------------------------------------------------------------------------


def _sum_squares(column):
    total = 0.0
    for offset in range(0, len(column), CHUNK):
        part = column[offset:offset + CHUNK].astype(np.float64)
        total += float(np.dot(part, part))
    return total


def levels(samples):
    """Sample peak, RMS, crest factor, DC offset and clipping counts of (frames, channels) samples."""
    if not samples.size:
        return {"sample_peak_dbfs": None, "rms_dbfs": None, "crest_factor_db": None, "dc_offset": 0.0, "clipped_samples": 0}
    magnitude = np.abs(samples)
    peak = float(magnitude.max())
    energy = sum(_sum_squares(samples[:, channel]) for channel in range(samples.shape[1]))
    rms = math.sqrt(energy / samples.size)
    dc = max(abs(float(np.mean(samples[:, channel], dtype=np.float64))) for channel in range(samples.shape[1]))
    out = {
        "sample_peak_dbfs": rounded(db(peak)),
        "rms_dbfs": rounded(db(rms)),
        "crest_factor_db": rounded(db(peak) - db(rms)) if rms > 0 else None,
        "dc_offset": round(dc, 6),
        "clipped_samples": int(np.count_nonzero(magnitude >= CLIP_LEVEL)),
    }
    over = int(np.count_nonzero(magnitude > 1.0))
    if over:
        out["samples_over_full_scale"] = over
    return out


def stereo_image(samples):
    """Correlation (+1 mono, 0 unrelated, -1 out of phase) and width (side RMS / mid RMS)."""
    if samples.shape[1] < 2:
        return {"channels": samples.shape[1], "correlation": None, "width": 0.0}
    left, right = samples[:, 0], samples[:, 1]
    ll, rr = _sum_squares(left), _sum_squares(right)
    lr = 0.0
    for offset in range(0, len(left), CHUNK):
        lr += float(np.dot(left[offset:offset + CHUNK].astype(np.float64), right[offset:offset + CHUNK].astype(np.float64)))
    mid, side = (ll + rr + 2 * lr) / 4.0, max(0.0, (ll + rr - 2 * lr) / 4.0)
    out = {"channels": samples.shape[1], "correlation": round(lr / math.sqrt(ll * rr), 3) if ll > 0 and rr > 0 else None}
    out["width"] = round(math.sqrt(side / mid), 3) if mid > 0 else None
    return out


def spectral_balance(samples, sample_rate, n_fft=8192, batch=128):
    """Share of spectral energy per band (Welch average over the mono sum), as percent and dB."""
    mono = samples.mean(axis=1, dtype=np.float64) if samples.shape[1] > 1 else samples[:, 0].astype(np.float64)
    if not mono.size or not np.any(mono):
        return dict((name, {"percent": 0.0, "db": None}) for name, _, _ in BANDS)
    mono = mono - mono.mean()
    if len(mono) < n_fft:
        mono = np.pad(mono, (0, n_fft - len(mono)))
    window = np.hanning(n_fft)
    frames = np.lib.stride_tricks.sliding_window_view(mono, n_fft)[:: n_fft // 2]
    power = np.zeros(n_fft // 2 + 1)
    for offset in range(0, len(frames), batch):
        spectrum = np.fft.rfft(frames[offset:offset + batch] * window, axis=1)
        power += np.sum(spectrum.real ** 2 + spectrum.imag ** 2, axis=0)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)
    power[0] = 0.0  # DC
    total = float(power.sum())
    out = {}
    for name, low, high in BANDS:
        mask = (freqs >= low) & ((freqs < high) if high else True)
        share = float(power[mask].sum()) / total if total > 0 else 0.0
        out[name] = {"percent": round(100.0 * share, 1), "db": rounded(10.0 * math.log10(share), 1) if share > 0 else None}
    return out


def dropouts(samples, sample_rate, longest=0.1, context=0.05, level_db=-40.0):
    """Short runs of exact digital silence inside audible material: the signature of a recording dropout."""
    if not samples.size:
        return []
    silent = np.all(samples == 0.0, axis=1).astype(np.int8)
    edges = np.flatnonzero(np.diff(np.concatenate(([0], silent, [0]))))
    starts, ends = edges[0::2], edges[1::2]
    span, limit, found = int(context * sample_rate), int(longest * sample_rate), []
    floor = 10.0 ** (level_db / 20.0)
    for begin, end in zip(starts, ends):
        if end - begin > limit or begin < span or end + span > len(samples) or end - begin < max(2, sample_rate // 2000):
            continue
        before = samples[begin - span:begin]
        after = samples[end:end + span]
        if math.sqrt(float(np.mean(before.astype(np.float64) ** 2))) > floor and math.sqrt(float(np.mean(after.astype(np.float64) ** 2))) > floor:
            found.append(round(begin / float(sample_rate), 3))
    return found


# ---------------------------------------------------------------------------
# Curves and sections
# ---------------------------------------------------------------------------


def loudness_curve(frames, duration, points=32):
    """Short-term loudness (LUFS, max per interval; momentary in the first 3 s), at most ``points`` values."""
    times, short, momentary = frames["t"], frames["S"], frames["M"]
    if not len(times) or duration <= 0:
        return None
    interval = max(1.0, duration / points)
    for nice in (1, 2, 3, 5, 10, 15, 20, 30, 60):
        if nice >= interval:
            interval = float(nice)
            break
    values = []
    for index in range(int(math.ceil(duration / interval))):
        mask = (times > index * interval) & (times <= (index + 1) * interval + 1e-6)
        # Short-term needs 3 s of audio; before that, momentary loudness stands in.
        chosen = np.where(times[mask] < SHORT_TERM - 1e-6, momentary[mask], short[mask])
        chosen = chosen[np.isfinite(chosen) & (chosen > ABSOLUTE_GATE)]
        values.append(rounded(float(chosen.max()), 1) if chosen.size else None)
    return {"interval_seconds": interval, "short_term_lufs": values}


def section_summary(section, frames, samples, sample_rate):
    """Loudness and level of one section {name, start, end} (seconds within the file)."""
    start, end = float(section["start"]), float(section["end"])
    times = frames["t"]
    inside = (times - MOMENTARY >= start - 1e-6) & (times <= end + 1e-6)
    if not np.any(inside):  # shorter than one block: take every block that ends inside
        inside = (times > start) & (times <= end + 1e-6)
    long_inside = (times - SHORT_TERM >= start - 1e-6) & (times <= end + 1e-6)
    if not np.any(long_inside):
        long_inside = inside
    momentary, short = frames["M"][inside], frames["S"][long_inside]
    momentary_live = momentary[np.isfinite(momentary) & (momentary > ABSOLUTE_GATE)]
    short_live = short[np.isfinite(short) & (short > ABSOLUTE_GATE)]
    first, last = int(round(start * sample_rate)), int(round(end * sample_rate))
    segment = samples[max(0, first):max(0, last)]
    level = levels(segment)
    out = {
        "name": section.get("name"),
        "start": round(start, 3),
        "end": round(end, 3),
        "integrated_lufs": rounded(gated_loudness(momentary), 1),
        "short_term_max_lufs": rounded(float(short_live.max()), 1) if short_live.size else None,
        "momentary_max_lufs": rounded(float(momentary_live.max()), 1) if momentary_live.size else None,
        "sample_peak_dbfs": level["sample_peak_dbfs"],
        "rms_dbfs": level["rms_dbfs"],
    }
    for key in ("bars", "start_bar"):
        if key in section:
            out[key] = section[key]
    return out


def normalize_sections(sections, duration):
    """Validate [{name, start, end?}] (seconds); a missing end runs to the next start or the file end."""
    if not isinstance(sections, list):
        raise AudioError("sections must be None, 'locators', or a list of {name, start, end} in seconds")
    items = []
    for position, section in enumerate(sections):
        if not isinstance(section, dict) or "start" not in section:
            raise AudioError("Section {0} needs at least 'start' (seconds), e.g. {{'name': 'Drop', 'start': 30, 'end': 60}}".format(position))
        try:
            start = float(section["start"])
            end = float(section["end"]) if section.get("end") is not None else None
        except (TypeError, ValueError):
            raise AudioError("Section {0}: start and end must be seconds".format(position))
        items.append(dict(section, name=str(section.get("name") or "Section {0}".format(position + 1)), start=start, end=end))
    items.sort(key=lambda item: item["start"])
    for position, item in enumerate(items):
        if item["end"] is None:
            item["end"] = items[position + 1]["start"] if position + 1 < len(items) else duration
        item["start"], item["end"] = max(0.0, item["start"]), min(duration, item["end"])
        if item["end"] <= item["start"]:
            raise AudioError("Section {0!r} is empty or outside the file (0..{1:.2f} s)".format(item["name"], duration))
    return items


# ---------------------------------------------------------------------------
# Whole-file analysis
# ---------------------------------------------------------------------------


def notes_for(result):
    """Plain-language flags an agent can act on without listening."""
    notes = []
    loud, level, stereo = result["loudness"], result["levels"], result["stereo"]
    if level["sample_peak_dbfs"] is None or level["sample_peak_dbfs"] < -90:
        notes.append("The file is silent.")
        return notes
    if loud["true_peak_dbtp"] is not None and loud["true_peak_dbtp"] > -1.0:
        notes.append("True peak {0} dBTP is above -1 dBTP (streaming recommendation).".format(loud["true_peak_dbtp"]))
    if level["clipped_samples"]:
        notes.append("{0} samples at full scale: clipping.".format(level["clipped_samples"]))
    if level.get("samples_over_full_scale"):
        notes.append("{0} samples exceed 0 dBFS (float file); they clip in 16/24-bit exports.".format(level["samples_over_full_scale"]))
    if level["dc_offset"] > 0.001:
        notes.append("DC offset {0}.".format(level["dc_offset"]))
    if stereo.get("correlation") is not None and stereo["correlation"] < 0:
        notes.append("Negative stereo correlation: phase problems and poor mono compatibility.")
    if loud["integrated_lufs"] is not None and loud["integrated_lufs"] < -30:
        notes.append("Very quiet ({0} LUFS).".format(loud["integrated_lufs"]))
    if result.get("dropouts"):
        notes.append("{0} possible dropouts (short digital silences inside audio) at {1} s.".format(len(result["dropouts"]), result["dropouts"][:5]))
    return notes


def analyze(path, sections=None):
    """Loudness, levels, stereo image, spectral balance, loudness curve and per-section loudness of a file.

    sections: None or a list of {name, start, end} in seconds (normalize_sections fills in ends).
    """
    samples, info = decode(path)
    rate = info["sample_rate"]
    duration = len(samples) / float(rate) if rate else info["duration"]
    loud = measure_loudness(path, info)
    short = loud["S"][np.isfinite(loud["S"]) & (loud["S"] > ABSOLUTE_GATE)]
    momentary = loud["M"][np.isfinite(loud["M"]) & (loud["M"] > ABSOLUTE_GATE)]
    result = {
        "file": info["path"],
        "format": {"codec": info["codec"], "sample_rate": rate, "channels": info["channels"], "bit_depth": info["bit_depth"]},
        "duration_seconds": round(duration, 3),
        "loudness": {
            "integrated_lufs": rounded(loud["integrated"], 1),
            "loudness_range_lu": rounded(loud["range"], 1),
            "true_peak_dbtp": rounded(loud["true_peak"], 1),
            "short_term_max_lufs": rounded(float(short.max()), 1) if short.size else None,
            "momentary_max_lufs": rounded(float(momentary.max()), 1) if momentary.size else None,
        },
        "levels": levels(samples),
        "stereo": stereo_image(samples),
        "spectrum": spectral_balance(samples, rate),
        "loudness_curve": loudness_curve(loud, duration),
        "dropouts": dropouts(samples, rate),
    }
    if sections:
        result["sections"] = [section_summary(section, loud, samples, rate) for section in normalize_sections(sections, duration)]
    result["notes"] = notes_for(result)
    return result
