"""Compare: differences the agent can act on (PRD section 9).

compare(a, b) measures both sides the same way and returns deltas, each marked improved, regressed or
within noise. Sides are takes (any id, or "best" for the kept take of a's set, tempo and variation),
the spec ("spec": the brief's targets), or a reference section ("ref:<name>:<section>").

- Spectral and stereo metrics are loudness-matched: band levels are relative to the side's own
  integrated loudness, so level never passes for quality.
- Noise: the take-to-take spread measured by the repeatability run (calibration/noise.json, PRD 13.1);
  until then a default floor of 0.5 dB.
- blind=True returns a packet for a judge that must not know which take is new: X and Y in random
  order, no ids, times or statuses.
- Against a mastered reference, crest factor and loudness range are information only (a master is
  denser than an unlimited stem sum; the brief's -14 LUFS and -1 dBTP win).
- Against the references' envelope ("refs"): the take's tier profile (ears.profile, level-independent)
  inside, above or below the range the references span, band by band and metric by metric.
"""
import json
import math
import random
from pathlib import Path

from . import loudness, measure, report, tiers
from . import profile as profiles

# metric -> (better direction: +1 higher is better, -1 lower is better, 0 closer to target / no direction)
DIRECTIONS = {
    "lufs_i": 0, "true_peak_dbtp": -1, "lra": 0, "sum_null_db": 1, "mono_sub_loss_db": -1, "key_confidence": 1,
    "width": 0, "correlation": 0, "crest_db": 0, "fails": -1, "warns": -1,
}


def noise_floor(home, metric, default=0.5):
    path = Path(home) / "calibration" / "noise.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            value = data.get("metrics", {}).get(metric)
            if value is not None:
                return max(float(value), 0.05)
            return float(data.get("default", default))
        except (OSError, ValueError):
            pass
    return default


def side_metrics(take, spec, variation=None):
    """The measured metrics of a take for one variation (default: its first)."""
    set_name = spec.set_name(take.set)
    variation = variation or take.variations[0]
    parts = take.parts()
    sums, _ = tiers.tier_sums(parts, spec, set_name, variation, take.tempo, bars=take.part_bars())
    out = {"tiers": {}, "parts": {}, "bands": {}}
    for tier, audio in sums.items():
        values = loudness.measure(audio)
        out["tiers"][tier] = {"lufs_i": values["integrated"], "true_peak_dbtp": values["true_peak"], "lra": values["range"]}
    if sums:
        top_tier = list(sums)[-1]
        top = sums[top_tier]
        out["top"] = top_tier
        bands = measure.band_levels(top)
        lufs = out["tiers"][top_tier]["lufs_i"]
        out["bands"] = dict((name, round(item["db"] - lufs, 2)) for name, item in bands["bands"].items())
        third = measure.third_octave_levels(top)
        out["third_octave"] = dict(("{0:g}".format(center), round(value, 2)) for center, value in zip(third["centers"], third["relative_db"]))
        stereo = measure.stereo(top)
        out["stereo"] = {"width": stereo["width"], "correlation": stereo["correlation"]}
        out["mono_sub_loss_db"] = measure.mono_sub(top, float(spec.target("bass_crossover_hz", 120.0)))["loss_db"]
        key = measure.key_estimate(top, spec.a4_hz)
        out["key"] = {"key": key["key"], "confidence": key["confidence"]}
        levels = measure.levels(top)
        out["crest_db"] = levels["crest_db"]
    for part_id, audio in parts.items():
        values = loudness.measure(audio, peaks=False)
        part_bands = measure.third_octave_levels(audio)
        out["parts"][part_id] = {"lufs_i": values["integrated"],
                                 "third_octave": dict(("{0:g}".format(center), round(value, 2))
                                                      for center, value in zip(part_bands["centers"], part_bands["relative_db"]))}
    return out


def _status(metric, before, after, target, noise, ceiling=None):
    """improved, regressed, within noise, within limits or changed.

    A ceiling (true peak, mono-sub loss) is a limit, not a direction: moving while staying under it is
    "within limits", crossing it is a regression, coming back under it an improvement.
    """
    if before is None or after is None:
        return "changed"
    delta = after - before
    if ceiling is not None:
        if after <= ceiling:
            return "improved" if before > ceiling else "within limits"
        if before <= ceiling:
            return "regressed"
        if abs(delta) <= noise:
            return "within noise"
        return "improved" if delta < 0 else "regressed"
    if abs(delta) <= noise:
        return "within noise"
    direction = DIRECTIONS.get(metric, 0)
    if target is not None:
        return "improved" if abs(after - target) < abs(before - target) else "regressed"
    if direction == 0:
        return "changed"
    return "improved" if delta * direction > 0 else "regressed"


def _delta(metric, label, before, after, target=None, noise=0.5, unit="dB", ceiling=None):
    entry = {"metric": label, "from": before, "to": after}
    if before is not None and after is not None:
        entry["delta"] = round(after - before, 2)
    if target is not None:
        entry["target"] = target
    if ceiling is not None:
        entry["ceiling"] = ceiling
    entry["status"] = _status(metric, before, after, target, noise, ceiling)
    entry["unit"] = unit
    return entry


def _variation_deltas(after, before, spec, noise, suffix):
    target_lufs = spec.target("lufs_i")
    ceiling = spec.target("true_peak_dbtp")
    mono_limit = spec.tolerance("mono_sub_db", 1.0)
    deltas = []
    for tier in after["tiers"]:
        if tier not in before["tiers"]:
            continue
        top = tier == after.get("top")
        deltas.append(_delta("lufs_i", "{0}{1} integrated loudness".format(tier, suffix), before["tiers"][tier]["lufs_i"],
                             after["tiers"][tier]["lufs_i"], target_lufs if top else None, noise("lufs_i"), "LUFS"))
        if top:
            deltas.append(_delta("true_peak_dbtp", "{0}{1} true peak".format(tier, suffix), before["tiers"][tier]["true_peak_dbtp"],
                                 after["tiers"][tier]["true_peak_dbtp"], None, noise("true_peak_dbtp"), "dBTP", ceiling=ceiling))
            deltas.append(_delta("lra", "{0}{1} loudness range".format(tier, suffix), before["tiers"][tier]["lra"], after["tiers"][tier]["lra"],
                                 None, noise("lra"), "LU"))
    for band, value in after.get("bands", {}).items():
        deltas.append(_delta("band", "{0} band{1} (rel. loudness)".format(band, suffix), before.get("bands", {}).get(band), value, None, noise("band")))
    if after.get("stereo") and before.get("stereo"):
        deltas.append(_delta("width", "{0}{1} stereo width".format(after["top"], suffix), before["stereo"]["width"], after["stereo"]["width"],
                             None, 0.05, "ratio"))
    if after.get("mono_sub_loss_db") is not None and before.get("mono_sub_loss_db") is not None:
        deltas.append(_delta("mono_sub_loss_db", "mono sub loss" + suffix, before["mono_sub_loss_db"], after["mono_sub_loss_db"], None, 0.3,
                             ceiling=mono_limit))
    if after.get("key") and before.get("key"):
        deltas.append({"metric": "key" + suffix, "from": before["key"]["key"], "to": after["key"]["key"],
                       "status": "same" if before["key"]["key"] == after["key"]["key"] else "changed"})
    return deltas


def compare_takes(a, b, spec, home=None, variation=None, check_counts=None):
    """Deltas from take b (before) to take a (after), regressions first.

    Every variation both takes hold is compared (tier loudness, true peak, bands, width, mono sub,
    key), plus each part's loudness and its largest third-octave shift.
    """
    shared = [v for v in a.variations if v in b.variations]
    if variation:
        shared = [variation] if variation in shared else []
    if not shared:
        raise ValueError("Takes {0} ({1}) and {2} ({3}) share no variation".format(
            a.id, "".join(a.variations), b.id, "".join(b.variations)))
    noise = lambda metric: noise_floor(home, metric) if home else 0.5
    deltas = []
    parts_after = parts_before = None
    for name in shared:
        after, before = side_metrics(a, spec, name), side_metrics(b, spec, name)
        suffix = "@" + name if len(shared) > 1 else ""
        deltas += _variation_deltas(after, before, spec, noise, suffix)
        parts_after, parts_before = after["parts"], before["parts"]
    for part_id in sorted(set(parts_after) | set(parts_before)):
        values, old = parts_after.get(part_id), parts_before.get(part_id)
        if values is None:
            deltas.append({"metric": "{0} loudness".format(part_id), "from": old["lufs_i"], "to": None, "status": "removed"})
            continue
        if old is None:
            deltas.append({"metric": "{0} loudness".format(part_id), "from": None, "to": values["lufs_i"], "status": "new"})
            continue
        deltas.append(_delta("part_lufs", "{0} loudness".format(part_id), old["lufs_i"], values["lufs_i"], None, noise("part_lufs"), "LUFS"))
        shifts = []
        for band, level in values["third_octave"].items():
            prior = old["third_octave"].get(band)
            if prior is not None and level > -60 and prior > -60:
                shifts.append((abs(level - prior), band, prior, level))
        if shifts:
            size, band, prior, level = max(shifts)
            deltas.append(_delta("band", "{0} {1} Hz third octave (rel.)".format(part_id, band), prior, level, None, max(1.0, noise("band"))))
    if check_counts:
        for status in ("fail", "warn"):
            deltas.append(_delta(status + "s", "{0} checks".format(status), check_counts["b"].get(status, 0), check_counts["a"].get(status, 0),
                                 None, 0.0, "count"))
    order = {"regressed": 0, "improved": 1, "new": 2, "removed": 2, "changed": 3, "within limits": 4, "within noise": 5, "same": 6}
    deltas.sort(key=lambda item: (order.get(item["status"], 9), -abs(item.get("delta") or 0)))
    return {"variation": "".join(shared), "variations": shared, "deltas": report.clean(deltas), "noise_default": 0.5,
            "regressed": sum(1 for item in deltas if item["status"] == "regressed"),
            "improved": sum(1 for item in deltas if item["status"] == "improved")}


def compare_spec(a, spec):
    """The take against the brief's targets: loudness and true peak of every variation's top tier."""
    deltas = []
    for variation in a.variations:
        metrics = side_metrics(a, spec, variation)
        top = metrics.get("top")
        if not top:
            continue
        lufs, peak = metrics["tiers"][top]["lufs_i"], metrics["tiers"][top]["true_peak_dbtp"]
        target, ceiling = spec.target("lufs_i"), spec.target("true_peak_dbtp")
        deltas.append({"metric": "{0}@{1} integrated loudness".format(top, variation), "value": lufs, "target": target,
                       "delta": round(lufs - target, 2), "status": "ok" if abs(lufs - target) <= spec.tolerance("lufs_i_lu") else "off target"})
        deltas.append({"metric": "{0}@{1} true peak".format(top, variation), "value": peak, "ceiling": ceiling,
                       "delta": round(peak - ceiling, 2), "status": "ok" if peak <= ceiling else "over"})
        deltas.append({"metric": "{0}@{1} key".format(top, variation), "value": metrics["key"]["key"],
                       "target": "{0} {1}".format(spec.key_name, spec.mode)})
    return {"deltas": report.clean(deltas)}


def compare_reference(a, ref, spec, variation=None):
    """Shape against a reference section (loudness-matched band levels, width, dynamics as information)."""
    metrics = side_metrics(a, spec, variation)
    deltas = []
    for band, value in metrics.get("bands", {}).items():
        target = (ref.get("bands") or {}).get(band)
        if target is not None:
            deltas.append({"metric": "{0} band (rel. loudness)".format(band), "take": value, "reference": target,
                           "delta": round(value - target, 2), "status": "information" if abs(value - target) <= 3 else "different"})
    if metrics.get("stereo") and ref.get("width") is not None:
        deltas.append({"metric": "stereo width", "take": metrics["stereo"]["width"], "reference": ref["width"],
                       "delta": round(metrics["stereo"]["width"] - ref["width"], 3)})
    for key in ("crest_db", "lra"):
        if ref.get(key) is not None:
            mine = metrics.get("crest_db") if key == "crest_db" else metrics["tiers"][metrics["top"]]["lra"]
            deltas.append({"metric": key, "take": mine, "reference": ref[key], "status": "information only (a master is denser than a stem sum)"})
    deltas.sort(key=lambda item: -abs(item.get("delta") or 0))
    return {"deltas": report.clean(deltas)}


ENVELOPE_LABELS = {
    "lra": "loudness range (LU)", "plr_db": "peak to loudness (dB)", "crest_db": "crest factor (dB)",
    "dynamics_spread": "short-term loudness spread (LU)", "width": "stereo width", "correlation": "stereo correlation",
    "mono_sub_loss_db": "mono sub loss (dB)", "onset_rate": "onsets per second",
}


def tier_profile(a, spec, variation=None, tier=None):
    """The level-independent profile of one tier sum of a take (default: its top tier)."""
    set_name = spec.set_name(a.set)
    variation = variation or a.variations[0]
    sums, _ = tiers.tier_sums(a.parts(), spec, set_name, variation, a.tempo, bars=a.part_bars())
    if not sums:
        raise ValueError("Take {0} has no tier sums for variation {1}".format(a.id, variation))
    tier = tier or list(sums)[-1]
    if tier not in sums:
        raise ValueError("Take {0} has no tier {1} (it has {2})".format(a.id, tier, ", ".join(sums)))
    values = profiles.profile(sums[tier], spec.a4_hz, float(spec.target("bass_crossover_hz", 120.0)), absolute=False)
    return tier, variation, values


def _place(value, low, high):
    if value < low:
        return "below", round(value - low, 2)
    if value > high:
        return "above", round(value - high, 2)
    return "inside", 0.0


def compare_envelope(a, env, spec, variation=None, tier=None, profile=None):
    """A take's tier against the range the references span (ears.refs.envelope): every third-octave band and
    shape metric marked inside, above or below, largest excess first. Tempo and key are information."""
    if profile is None:
        tier, variation, profile = tier_profile(a, spec, variation, tier)
    deltas = []
    bands = profile.get("third_octave") or {}
    for band, (low, high) in (env.get("third_octave") or {}).items():
        value = bands.get(band, profiles.BAND_FLOOR_DB)
        status, delta = _place(value, low, high)
        deltas.append({"metric": "{0} Hz band (dB re mix)".format(band), "take": value, "low": low, "high": high,
                       "delta": delta, "status": status})
    for key, span in (env.get("scalars") or {}).items():
        value = profile.get(key)
        if value is None:
            continue
        status, delta = _place(value, span["low"], span["high"])
        deltas.append({"metric": ENVELOPE_LABELS.get(key, key), "take": value, "low": span["low"], "high": span["high"],
                       "typical": span.get("typical"), "delta": delta, "status": status})
    deltas.sort(key=lambda item: (item["status"] == "inside", -abs(item["delta"])))
    take_tempo = getattr(a, "tempo", None) or (profile.get("tempo") or {}).get("bpm")
    ref_tempi = [value for value in env.get("tempo") or [] if value]
    information = {"tempo": {"take": take_tempo, "references": ref_tempi,
                             "same_as": [value for value in ref_tempi if profiles.same_tempo(take_tempo, value)]},
                   "key": {"take": (profile.get("key") or {}).get("key"), "references": env.get("keys") or []}}
    bands_out = [item for item in deltas if item["metric"].endswith("(dB re mix)") and item["status"] != "inside"]
    others_out = [item for item in deltas if not item["metric"].endswith("(dB re mix)") and item["status"] != "inside"]
    band_count = sum(1 for item in deltas if item["metric"].endswith("(dB re mix)"))
    summary = "{0} of {1} bands outside the references".format(len(bands_out), band_count)
    if bands_out:
        worst = max(bands_out, key=lambda item: abs(item["delta"]))
        summary += " (largest {0:+.1f} dB at {1})".format(worst["delta"], worst["metric"].split(" Hz")[0] + " Hz")
    if others_out:
        summary += "; outside on " + ", ".join(item["metric"] for item in others_out[:4])
    return {"tier": tier, "variation": variation, "kind": env.get("kind"), "references": env.get("references") or [],
            "summary": summary, "outside": len(bands_out) + len(others_out), "deltas": report.clean(deltas),
            "information": information}


def blind_packet(result, a_id, b_id, seed=None):
    """X/Y packet for a judge that must not know which take is new: no ids, times or statuses."""
    rng = random.Random(seed)
    swap = rng.random() < 0.5
    labels = {"X": b_id if swap else a_id, "Y": a_id if swap else b_id}
    rows = []
    for item in result["deltas"]:
        before, after = item.get("from"), item.get("to")
        x, y = (after, before) if not swap else (before, after)
        if x is None and y is None:
            continue
        row = {"metric": item["metric"], "X": x, "Y": y}   # a part on one side only shows as null on the other
        if item.get("target") is not None:
            row["target"] = item["target"]
        if item.get("unit"):
            row["unit"] = item["unit"]
        rows.append(row)
    rng.shuffle(rows)
    return {"packet": {"instructions": "Two takes, X and Y, measured the same way and loudness-matched where it matters. "
                                       "Say which you would keep and why, or that there is no reliable difference.",
                       "metrics": rows}, "key": labels}
