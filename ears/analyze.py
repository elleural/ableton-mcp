"""The measurement ear: audio checks on a take (PRD section 8).

`analyze_take()` builds the tier sums of every variation (each part tiled to the longest loop as the
game plays it), measures them and the parts, and returns a full report (ears.report). Levels follow the
PRD's table: audio.loudness, audio.tempo_consistency, audio.key (mix), audio.mono_sub and
audio.sum_null fail; audio.key per stem and audio.balance warn; the rest report (info). strict=True adds
the delivery-file checks of ears.strict for every file.
"""
import math

import numpy as np

from . import loudness, measure, report, strict, tiers
from .audio import Audio

SUB_PRESENT_DB = -45.0      # stereo level below the bass crossover under which a stem has no sub to check
SILENT_DBFS = -80.0
KEY_ROLES = ("pad", "arp")  # stems that carry the harmony; a bass or lead line alone often reads as another key
KEY_UNCERTAIN = 0.03        # correlation margin over the runner-up below which a key estimate is a coin toss


def _db_sum(values):
    """Sum of signals' powers given in dB."""
    finite = [10 ** (value / 10.0) for value in values if value is not None and value > -150]
    return 10 * math.log10(sum(finite)) if finite else None


def _key_name(spec):
    return "{0} {1}".format(spec.key_name, spec.mode)


def _same_key(found, spec):
    """Whether a key estimate names the spec's key (False for silent or atonal audio)."""
    from .spec import SpecError, parse_key, pitch_class
    if not isinstance(found, dict):
        return False
    tonic, mode = found.get("tonic"), found.get("mode")
    try:
        if (tonic is None or mode is None) and found.get("key"):
            _, pc, mode = parse_key(found["key"])     # a runner-up may carry only its name ("A minor")
            return pc == spec.tonic and mode == spec.mode
        if tonic is None or mode is None:
            return False
        return pitch_class(tonic) == spec.tonic and mode == spec.mode
    except SpecError:
        return False


def loudness_checks(spec, variation, sums):
    checks = []
    target = float(spec.target("lufs_i", -14.0))
    tolerance = float(spec.tolerance("lufs_i_lu", 0.5))
    ceiling = float(spec.target("true_peak_dbtp", -1.0))
    measured = {}
    for tier, audio in sums.items():
        measured[tier] = loudness.measure(audio)
    top = list(sums)[-1] if sums else None
    if top:
        value = measured[top]
        problems = []
        if abs(value["integrated"] - target) > tolerance:
            problems.append("{0:.1f} LUFS (target {1:g} ± {2:g})".format(value["integrated"], target, tolerance))
        if value["true_peak"] > ceiling:
            problems.append("true peak {0:+.1f} dBTP (ceiling {1:g})".format(value["true_peak"], ceiling))
        checks.append(report.check("audio.loudness", "fail" if problems else "pass", "{0}@{1}".format(top, variation),
                                   "; ".join(problems) or "{0:.1f} LUFS, {1:+.1f} dBTP".format(value["integrated"], value["true_peak"]),
                                   value={"lufs_i": value["integrated"], "true_peak_dbtp": value["true_peak"], "lra": value["range"]},
                                   target={"lufs_i": target, "true_peak_dbtp": ceiling}, tolerance=tolerance))
    ladder = [(tier, measured[tier]["integrated"]) for tier in sums]
    steps, drops = [], []
    for (low_tier, low), (tier, high) in zip(ladder, ladder[1:]):
        step = high - low
        steps.append({"tier": tier, "step_lu": round(step, 2)})
        if step < -0.05:
            drops.append("{0} is {1:.1f} LU quieter than {2}".format(tier, -step, low_tier))
    checks.append(report.check("audio.tier_ladder", "warn" if drops else "info", "tiers@{0}".format(variation),
                               "; ".join(drops) + " (cancellation?)" if drops else
                               " < ".join("{0} {1:.1f}".format(tier, value) for tier, value in ladder),
                               value={"lufs": dict(ladder), "steps": steps}))
    return checks, measured


def key_checks(spec, variation, sums, parts, harmony):
    """audio.key: the top tier must read in the spec's key (fail); harmony stems alone warn.

    A miss by less than KEY_UNCERTAIN of correlation with the spec's key as runner-up is reported as
    a warn ("uncertain"), not a fail.
    """
    checks = []
    expected = _key_name(spec)
    top = list(sums)[-1] if sums else None
    if top:
        found = measure.key_estimate(sums[top], spec.a4_hz)
        ok = _same_key(found, spec)
        second = found.get("second") or {}
        margin = (found.get("confidence") or 0.0) - (second.get("confidence") or 0.0)
        status = "pass" if ok else ("warn" if _same_key(second, spec) and margin < KEY_UNCERTAIN else "fail")
        summary = "{0} (confidence {1:.2f}; second {2})".format(found.get("key"), found.get("confidence") or 0.0, second.get("key"))
        if status == "warn":
            summary += ": uncertain, {0} is within {1:.2f}".format(expected, margin)
        checks.append(report.check("audio.key", status, "{0}@{1}".format(top, variation), summary,
                                   value=found.get("key"), target=expected, confidence=found.get("confidence")))
    for part_id, audio in parts.items():
        if part_id not in harmony or measure.levels(audio)["silent"]:
            continue
        found = measure.key_estimate(audio, spec.a4_hz)
        if found.get("key") and not _same_key(found, spec):
            checks.append(report.check("audio.key", "warn", part_id, "{0} heard alone (confidence {1:.2f})".format(
                found["key"], found.get("confidence") or 0.0), value=found["key"], target=expected))
    return checks


def mono_checks(spec, subjects):
    checks = []
    tolerance = float(spec.tolerance("mono_sub_db", 1.0))
    cutoff = float(spec.target("bass_crossover_hz", 120.0))
    for subject, audio in subjects.items():
        if audio.channels < 2:
            continue
        # Whether there is a sub is judged on the stereo low end (level_db), never on the mono sum:
        # an out-of-phase sub cancels in mono, which is exactly the defect this check is for.
        result = measure.mono_sub(audio, cutoff)
        if result.get("level_db") is None or result["level_db"] < SUB_PRESENT_DB:
            continue
        ok = result["loss_db"] <= tolerance
        checks.append(report.check("audio.mono_sub", "pass" if ok else "fail", subject,
                                   "mono sum below {0:g} Hz loses {1:.1f} dB".format(cutoff, result["loss_db"]),
                                   value=result["loss_db"], target=tolerance, correlation=result["correlation"]))
    return checks


def null_depth(mix, signals):
    """How far (dB) the sum of `signals` cancels `mix`: 10*log10(mix power / residual power)."""
    frames = min([mix.shape[0]] + [signal.shape[0] for signal in signals])
    if frames == 0:
        return 0.0   # nothing to compare is no cancellation, never a perfect null
    total = np.sum([signal[:frames] for signal in signals], axis=0)
    residual = mix[:frames] - total
    mix_power = float(np.mean(mix[:frames] ** 2))
    res_power = float(np.mean(residual ** 2))
    return 10 * math.log10(mix_power / res_power) if res_power > 0 and mix_power > 0 else 200.0


def sum_null_checks(spec, take):
    """Tap self-check (PRD 6.3): the parts and returns of a pass cancel against its main mix.

    Captures measure it at ingest on the raw recordings over the mix's window (take.json
    "sum_null"); other takes tile each part game-style to the mix's length.
    """
    checks = []
    if take.mode not in ("tap", "files"):
        return [report.check("audio.sum_null", "skip", "mix", "only tap captures record the stems and the mix in one pass")]
    tolerance = float(spec.tolerance("sum_null_db", 40.0))
    stored = take.meta.get("sum_null") or {}
    part_meta = take.meta.get("parts") or {}
    bar = spec.bar_seconds(take.tempo)
    bars = dict((part.id, part.bars) for part in spec.parts(spec.set_name(take.set)))
    bars.update(take.part_bars())
    for entry in take.meta.get("mixes") or []:
        subject = entry["file"].rsplit("/", 1)[-1].replace(".wav", "")
        label = entry.get("pass")
        members = [name for name, meta in part_meta.items() if label is None or meta.get("pass") == label]
        returns = [meta for meta in (take.meta.get("returns") or {}).values() if label is None or meta.get("pass") == label]
        if subject in stored:
            depth = float(stored[subject])
        else:
            mix = take._read(entry["file"])
            total_s = mix.duration - spec.tail_seconds()
            signals = []
            for name in members:
                part = take._read(part_meta[name]["file"])
                signals.append(tiers.tile(part, bars.get(name, 1) * bar, total_s).samples if name in bars else part.stereo())
            signals += [take._read(meta["file"]).stereo() for meta in returns]
            if not signals:
                continue
            depth = null_depth(mix.stereo(), signals)
        ok = depth >= tolerance
        checks.append(report.check("audio.sum_null", "pass" if ok else "fail", subject,
                                   "stems + returns cancel the mix to {0:.1f} dB below it".format(depth) +
                                   ("" if ok else ": something reaches the master that was not captured (a master effect, or a track outside the spec)"),
                                   value=round(depth, 1), target=tolerance, parts=len(members), returns=len(returns)))
    if not checks:
        checks.append(report.check("audio.sum_null", "skip", "mix", "the take has no main mix"))
    return checks


def tempo_checks(spec, take, others):
    """Each part's loudness across the tempos of its set stays within ±1 LU of its median (PRD 8)."""
    if not others:
        return [report.check("audio.tempo_consistency", "skip", "parts", "needs takes at other tempos of the set")]
    tolerance = float(spec.tolerance("tempo_consistency_lu", 1.0))
    by_part = {}
    for item in [take] + list(others):
        for part_id, audio in item.parts().items():
            value = loudness.integrated(audio.samples, audio.rate)
            if value > -150:
                by_part.setdefault(part_id, {})[item.tempo] = value
    checks = []
    for part_id, values in sorted(by_part.items()):
        if len(values) < 2 or take.tempo not in values:
            continue
        # This take's own tempo against the part's median over every tempo it was captured at, so each
        # tempo's report names only its own jump (the level-up the player would hear).
        median = float(np.median(list(values.values())))
        deviation = values[take.tempo] - median
        ok = abs(deviation) <= tolerance
        checks.append(report.check("audio.tempo_consistency", "pass" if ok else "fail", part_id,
                                   "{0:+.1f} LU at {1:g} BPM against its median over {2} tempos".format(deviation, take.tempo, len(values)),
                                   value=dict(("{0:g}".format(tempo), round(value, 2)) for tempo, value in sorted(values.items())),
                                   tolerance=tolerance))
    return checks or [report.check("audio.tempo_consistency", "skip", "parts", "no part appears at another tempo")]


def balance_checks(spec, subjects, envelope):
    """Band energy (third octaves, loudness-matched) against the reference envelope (warn outside)."""
    if not envelope:
        return [report.check("audio.balance", "skip", "tiers", "no reference envelope yet (references come in Phase 4)")]
    checks = []
    for subject, audio in subjects.items():
        bands = measure.third_octave_levels(audio)
        relative = dict(("{0:g}".format(center), value) for center, value in zip(bands["centers"], bands["relative_db"]))
        outside = []
        for band, (low, high) in envelope.items():
            value = relative.get(band)
            if value is None:
                continue
            if value < low or value > high:
                outside.append({"band_hz": band, "value": round(value, 1), "envelope": [round(low, 1), round(high, 1)]})
        checks.append(report.check("audio.balance", "warn" if outside else "pass", subject,
                                   "{0} bands outside the reference envelope".format(len(outside)) if outside else "inside the reference envelope",
                                   items=outside[:6]))
    return checks


def report_checks(spec, variation, sums, parts, midi_effect_parts, bpm):
    checks = []
    top = list(sums)[-1] if sums else None
    if len(parts) > 1:
        overlaps = measure.masking(parts, top=5)
        checks.append(report.check("audio.masking", "info", "{0}@{1}".format(top or "parts", variation),
                                   "largest overlap: {0}".format(", ".join("{0}/{1} at {2:g} Hz {3:.0f}% of the time".format(
                                       item["a"], item["b"], item["band_hz"], item["overlap_share"]) for item in overlaps[:3])) if overlaps else "no overlaps",
                                   items=overlaps))
    for part_id in midi_effect_parts:
        if part_id in parts:
            stats = measure.grid_stats(measure.onsets(parts[part_id]), bpm, spec.grid, beats_per_bar=spec.beats_per_bar,
                                       tolerance_ms=float(spec.tolerance("grid_ms", 10.0)))
            checks.append(report.check("audio.onsets", "info", part_id, "{0} onsets, {1:.0%} on the grid, mean {2:.1f} ms off".format(
                stats["count"], stats["on_grid_share"], stats["mean_abs_ms"]), value=stats))
    reactive = {}
    dead = []
    for tier, audio in sums.items():
        result = measure.reactivity(audio, spec.analyser or None)
        reactive[tier] = dict((band, round(values["movement"], 3)) for band, values in result.items())
        if tier == top:
            dead = [band for band, values in result.items() if values["movement"] < 0.02]
    checks.append(report.check("audio.reactivity", "info", "tiers@{0}".format(variation),
                               ("bands that barely move in {0}: {1}".format(top, ", ".join(dead)) if dead else "every analyser band moves in {0}".format(top)),
                               value=reactive))
    survival = {}
    highpass = float(spec.tolerance("phone_highpass_hz", 200.0))
    for subject, audio in list(parts.items()) + ([(top, sums[top])] if top else []):
        survival[subject] = round(measure.phone(audio, highpass)[1]["survival_share"], 1)
    weakest = sorted(survival.items(), key=lambda item: item[1])[:3]
    checks.append(report.check("audio.phone", "info", "parts@{0}".format(variation),
                               "least on a phone speaker: {0}".format(", ".join("{0} {1:.0f}%".format(name, share) for name, share in weakest)),
                               value=survival))
    return checks


def silence_checks(parts):
    checks = []
    for part_id, audio in parts.items():
        stats = measure.levels(audio)
        if stats["silent"]:
            checks.append(report.check("audio.silent", "warn", part_id, "the part is silent (muted track, empty clip, or no instrument?)"))
    return checks


def analyze_take(take, spec, strict_mode=False, others=None, envelope=None, snapshot=None, images_dir=None):
    """Full measurement-ear report of a take (ears.take.Take)."""
    checks, values, images = [], {}, []
    set_name = spec.set_name(take.set)
    parts = take.parts()
    snapshot = snapshot if snapshot is not None else take.snapshot()
    harmony = set(part.id for part in spec.parts(set_name) if part.pitched and part.role in KEY_ROLES)
    midi_effect_parts = _midi_effect_parts(spec, set_name, snapshot)
    checks += silence_checks(parts)
    for variation in take.variations:
        sums, missing = tiers.tier_sums(parts, spec, set_name, variation, take.tempo, bars=take.part_bars())
        if missing:
            # Missing deliverables fail a strict (delivery) check; a capture of some parts only warns.
            checks.append(report.check("audio.parts", "fail" if strict_mode else "warn", variation,
                                       "missing from the take: " + ", ".join(missing)))
        if not sums:
            continue
        lchecks, measured = loudness_checks(spec, variation, sums)
        checks += lchecks
        values["tiers@" + variation] = dict((tier, {"lufs": item["integrated"], "tp": item["true_peak"]}) for tier, item in measured.items())
        members = dict((part_id, audio) for part_id, audio in parts.items() if part_id in sum(spec.tier_parts(set_name, variation).values(), []))
        checks += key_checks(spec, variation, sums, members if variation == take.variations[0] else {}, harmony)
        top = list(sums)[-1]
        mono_subjects = {"{0}@{1}".format(top, variation): sums[top]}
        if variation == take.variations[0]:
            mono_subjects.update(parts)
        checks += mono_checks(spec, mono_subjects)
        # The envelope describes full mixes, so it applies to the top tier (PRD 11.1: lower tiers go
        # against a reference's sparser sections, which come with references in Phase 4).
        checks += balance_checks(spec, {"{0}@{1}".format(top, variation): sums[top]}, envelope)
        checks += report_checks(spec, variation, sums, members, midi_effect_parts, take.tempo)
        if images_dir is not None and variation == take.variations[0]:
            images += _images(spec, set_name, variation, take, members, sums, measured, images_dir)
    checks += sum_null_checks(spec, take)
    checks += tempo_checks(spec, take, others)
    if strict_mode:
        checks += strict_checks(spec, take, snapshot)
    return report.make("audio", take.id, checks, take=take.id, set=set_name, tempo=take.tempo, variation=take.meta.get("variation"),
                       mode=take.mode, values=values, images=images or None, warnings=take.meta.get("warnings") or None)


def strict_checks(spec, take, snapshot=None):
    """Delivery-file checks for every part file of the take (fills are not looped)."""
    set_name = spec.set_name(take.set)
    bars = dict((part.id, part.bars) for part in spec.parts(set_name))
    fills = spec.fills(set_name)
    downbeats = _downbeat_notes(spec, set_name, snapshot, take)
    checks = []
    for part_id, audio in take.parts().items():
        if part_id in fills:
            checks += strict.file_checks(audio, part_id, spec, bpm=take.tempo, bars=fills[part_id].get("bars", 1), loop=False,
                                         has_downbeat_note=downbeats.get(part_id))
        elif part_id in bars:
            checks += strict.file_checks(audio, part_id, spec, bpm=take.tempo, bars=bars[part_id], has_downbeat_note=downbeats.get(part_id))
    return checks


def _midi_effect_parts(spec, set_name, snapshot):
    if not snapshot:
        return []
    names = dict((part.track, part.id) for part in spec.parts(set_name))
    out = []
    for track in snapshot.get("tracks") or []:
        if track.get("name") in names and any(device.get("type") == "midi_effect" for device in track.get("devices") or []):
            out.append(names[track["name"]])
    return out


def _downbeat_notes(spec, set_name, snapshot, take):
    """{part id: True/False} whether the part's captured clip has a note on bar 1 beat 1 (None unknown)."""
    if not snapshot:
        return {}
    clips = (take.meta.get("clips") or {})
    out = {}
    for track in snapshot.get("tracks") or []:
        for part in spec.parts(set_name):
            if part.track != track.get("name"):
                continue
            wanted = clips.get(part.id, {}).get("slot")
            for clip in track.get("clips") or []:
                if wanted is not None and clip.get("slot") != wanted:
                    continue
                notes = [note for note in clip.get("notes") or [] if not note.get("mute")]
                if clip.get("notes") is not None:
                    start = float(clip.get("loop_start") or 0.0)
                    out[part.id] = any(abs(float(note["start"]) - start) < 1e-3 for note in notes)
                break
    return out


def _chords(spec, set_name, variation, bars):
    try:
        progression = spec.progression(set_name, variation)
    except Exception:
        return None
    return [progression[index % len(progression)] for index in range(bars)]


def _images(spec, set_name, variation, take, members, sums, measured, folder):
    from . import images
    out = []
    order = sum(spec.tier_parts(set_name, variation).values(), [])
    seen, stems = set(), []
    for part_id in order:
        if part_id in members and part_id not in seen:
            seen.add(part_id)
            stems.append((part_id, members[part_id]))
    if not stems:
        return out
    longest = max(part.bars for part in spec.parts(set_name, variations=[variation]))
    try:
        path = images.stems_spectrogram(stems, take.tempo, spec.beats_per_bar, _chords(spec, set_name, variation, longest),
                                        path=str(folder / "stems.png"), title="{0} {1} stems".format(take.id, variation))
        out.append(path)
        path = images.ladder_chart(dict((tier, item["integrated"]) for tier, item in measured.items()),
                                   target=spec.target("lufs_i"), path=str(folder / "ladder.png"),
                                   title="{0} {1} tier loudness (LUFS)".format(take.id, variation))
        out.append(path)
    except Exception as error:   # images are a convenience; never fail the analysis for them
        out.append("images failed: {0}".format(error))
    return out


def analyze_files(spec, set_name, tempo, files, variation=None, strict_mode=True, snapshot=None):
    """Measurement ear on loose files ({part id: path}) without a take folder: tier sums and strict checks."""
    import tempfile
    from . import take as takes
    with tempfile.TemporaryDirectory() as home:
        take_id = takes.from_files(home, spec.set_name(set_name), tempo, files, spec, variation=variation)
        loaded = takes.load(home, take_id)
        result = analyze_take(loaded, spec, strict_mode=strict_mode, snapshot=snapshot)
        result["subject"] = "files"
        return result
