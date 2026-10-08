"""Calibration (PRD section 13): do the checks catch planted defects, and how noisy are the numbers?

planted_defects() runs every defect of PRD 13.2 in fixture form and records which checks fail or warn;
the rows feed docs/listening-loop-calibration.md. repeatability() measures the take-to-take spread of
several captures of one unchanged state (13.1) and writes calibration/noise.json, which compare uses
as its noise floor.
"""
import copy
import json
import math
import tempfile
from pathlib import Path

import numpy as np

from . import analyze, compare, notes, report, take as takes
from .fixtures import audio as fx

# PRD 13.2: defect -> checks that must catch it.
AUDIO_EXPECTED = {
    "arp_3k": ["audio.balance", "compare"],
    "sub_out_of_phase": ["audio.mono_sub"],
    "stem_louder": ["audio.tempo_consistency"],
    "master_reverb": ["audio.sum_null"],
    "seam_click": ["file.seam"],
    "unfolded": ["file.seam"],
    "short_5ms": ["file.duration"],
}
NOTES_EXPECTED = {
    "bass_semitone": ["notes.in_key", "notes.chord_tones"],
    "d_major": ["notes.in_key", "notes.chord_tones"],
    "clash": ["notes.clash"],
    "kick_late": ["notes.grid"],
    "lead_no_rests": ["notes.lead_rests"],
    "pad_a_over_e": ["notes.shared_stem"],
}


def _flagged(result):
    return sorted(set(item["check"] for item in result["checks"] if item["status"] in ("fail", "warn")))


def synthetic_envelope(parts, spec, set_name, tempo, margin_db=2.0):
    """A reference envelope from the clean fixture's own top tiers: each third octave's range over the
    variations, widened by margin_db."""
    from . import measure, tiers
    ranges = {}
    for variation in spec.variations(set_name):
        sums, _ = tiers.tier_sums(parts, spec, set_name, variation, tempo)
        bands = measure.third_octave_levels(sums[list(sums)[-1]])
        for center, value in zip(bands["centers"], bands["relative_db"]):
            if value > -60:
                low, high = ranges.get("{0:g}".format(center), (value, value))
                ranges["{0:g}".format(center)] = (min(low, value), max(high, value))
    return dict((band, (low - margin_db, high + margin_db)) for band, (low, high) in ranges.items())


def planted_defects(spec, set_name="neon", tempo=140.0, rate=fx.RATE):
    """Rows {defect, expected, caught_by, ok} for every audio and notes defect in fixture form."""
    rows = []
    with tempfile.TemporaryDirectory() as home:
        clean = fx.normalise(fx.render_parts(spec, set_name, tempo, rate), spec, set_name, tempo)
        envelope = synthetic_envelope(clean, spec, set_name, tempo)
        clean_id = fx.write_take(home, spec, set_name, tempo, clean, bit_depth=24 if rate == 48000 else 32)
        clean_take = takes.load(home, clean_id)
        baseline = analyze.analyze_take(clean_take, spec, strict_mode=True, envelope=envelope)
        rows.append({"defect": "none (clean fixture)", "expected": [], "caught_by": _flagged(baseline),
                     "ok": not [c for c in baseline["checks"] if c["status"] == "fail"]})
        others = {}
        for other in (tempo - 10.0, tempo + 10.0):
            parts = fx.normalise(fx.render_parts(spec, set_name, other, rate), spec, set_name, other)
            others[other] = takes.load(home, fx.write_take(home, spec, set_name, other, parts))
        for defect, expected in AUDIO_EXPECTED.items():
            parts, mix = fx.plant(clean, defect, spec, set_name, tempo)
            take_id = fx.write_take(home, spec, set_name, tempo, parts, mix=mix, bit_depth=24 if rate == 48000 else 32)
            planted = takes.load(home, take_id)
            result = analyze.analyze_take(planted, spec, strict_mode=True, envelope=envelope, others=list(others.values()))
            caught = _flagged(result)
            if "compare" in expected:
                delta = compare.compare_takes(planted, clean_take, spec)
                if any(item["status"] in ("regressed", "changed") and "arp" in item["metric"] and "Hz" in item["metric"] and abs(item.get("delta") or 0) >= 3
                       for item in delta["deltas"]):
                    caught.append("compare")
            rows.append({"defect": defect, "expected": expected, "caught_by": sorted(set(caught)),
                         "ok": all(check in caught for check in expected)})
    snapshot = notes_fixture(spec, set_name)
    baseline = notes.analyze_notes(snapshot, spec, set_name)
    rows.append({"defect": "none (clean notes)", "expected": [], "caught_by": _flagged(baseline),
                 "ok": not [c for c in baseline["checks"] if c["status"] == "fail"]})
    from .fixtures import notes as notes_fx
    for defect, expected in NOTES_EXPECTED.items():
        result = notes.analyze_notes(notes_fx.plant(snapshot, defect), spec, set_name)
        caught = _flagged(result)
        rows.append({"defect": defect, "expected": expected, "caught_by": caught, "ok": all(check in caught for check in expected)})
    return rows


def notes_fixture(spec, set_name):
    from .fixtures import notes as notes_fx
    return notes_fx.clean_snapshot(spec, set_name)


def repeatability(take_list, spec, home=None):
    """Spread (max - min) of each compare metric over takes of one unchanged state; writes noise.json."""
    if len(take_list) < 2:
        raise ValueError("repeatability needs at least two takes of the same state")
    series = {}
    for item in take_list:
        metrics = compare.side_metrics(item, spec)
        for tier, values in metrics["tiers"].items():
            for key, value in values.items():
                series.setdefault(key if tier == metrics.get("top") else "{0}_{1}".format(tier, key), []).append(value)
        for band, value in metrics.get("bands", {}).items():
            series.setdefault("band", []).append(value)
        for part_id, values in metrics["parts"].items():
            series.setdefault("part_lufs:" + part_id, []).append(values["lufs_i"])
    spread = {}
    for key, values in series.items():
        if key == "band":
            continue
        spread[key] = round(float(np.max(values) - np.min(values)), 3)
    per_part = [value for key, value in spread.items() if key.startswith("part_lufs:")]
    out = {"takes": [item.id for item in take_list], "created": report.now(), "metrics": {
        "lufs_i": spread.get("lufs_i"), "true_peak_dbtp": spread.get("true_peak_dbtp"), "lra": spread.get("lra"),
        "part_lufs": max(per_part) if per_part else None}, "detail": spread, "default": 0.5}
    if home:
        path = Path(home) / "calibration" / "noise.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.clean(out), indent=1) + "\n")
        out["path"] = str(path)
    return out


def markdown_table(rows):
    lines = ["| Defect | Must be caught by | Caught by | OK |", "| --- | --- | --- | --- |"]
    for row in rows:
        lines.append("| {0} | {1} | {2} | {3} |".format(row["defect"], ", ".join(row["expected"]) or "—",
                                                     ", ".join(row["caught_by"]) or "—", "yes" if row["ok"] else "**no**"))
    return "\n".join(lines)
