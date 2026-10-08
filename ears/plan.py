"""Capture planning: which clips to fire, which taps to record, how long, and how to cut (PRD 6.3).

`plan_capture()` reads the spec and a snapshot of the Live Set (ears snapshot format, no notes or
parameters needed) and returns the passes for the Remote Script's capture engine plus the cut
windows that turn the recordings into takes.

- tap (default): one pass records every part at its track's Post Mixer tap, every return and the
  main mix by Resampling. All variations share one pass when each has its own tracks and no part
  uses a send; otherwise one pass per variation (returns and mix stay attributable).
- solo: one pass per part, that part soloed and the main mix recorded, so each stem carries its share
  of the return effects and the master chain. Every part of its variation is fired, so sidechain
  sources keep playing.

A pass records two cycles of its longest loop plus the tail; the second cycle is kept, so it already
holds the tail of the first (the folded tail of soundtrack PRD section 6). `bars` shortens a pass.
"""
from . import report
from .spec import SpecError

SEND_IN_USE_DB = -60.0


class PlanError(ValueError):
    """The set does not hold what the spec asks to capture."""


def _tracks_by_name(snapshot):
    out = {}
    for track in snapshot.get("tracks") or []:
        out.setdefault(track["name"], []).append(track)
    return out


def _scene_slots(snapshot):
    return dict((scene["name"], scene["index"]) for scene in snapshot.get("scenes") or [])


def find_clip(spec, set_name, part, track, band, scene_slots):
    """(slot, scene name, clip) of the part's clip for a band, or (None, None, None)."""
    clips = track.get("clips") or []
    by_slot = dict((clip["slot"], clip) for clip in clips)
    scenes = spec.scenes_for(set_name, band)
    if part.clip_name:
        named = [clip for clip in clips if clip.get("name") == part.clip_name]
        for scene in scenes:
            for clip in named:
                if clip.get("scene") == scene or clip["slot"] == scene_slots.get(scene):
                    return clip["slot"], scene, clip
        if named:
            return named[0]["slot"], named[0].get("scene"), named[0]
        return None, None, None
    for scene in scenes:
        slot = scene_slots.get(scene)
        if slot is not None and slot in by_slot:
            return slot, scene, by_slot[slot]
    return None, None, None


def sends_in_use(track):
    sends = (track.get("mixer") or {}).get("sends") or {}
    return sorted(letter for letter, value in sends.items() if value is not None and float(value) > SEND_IN_USE_DB)


def plan_capture(spec, snapshot, set_name=None, variation=None, tempos=None, mode="tap", bars=None):
    """Passes, takes and warnings for a capture. Raises PlanError when nothing can be captured."""
    if mode not in ("tap", "solo"):
        raise PlanError("mode must be 'tap' or 'solo'")
    set_name = spec.set_name(set_name)
    set_tempos = spec.tempos(set_name)
    if tempos is None or tempos == []:
        tempos = [spec.middle_tempo(set_name)]
    elif isinstance(tempos, str):
        if tempos.strip().lower() != "all":
            raise PlanError("tempos must be a list of BPM or 'all'")
        tempos = set_tempos
    elif not isinstance(tempos, (list, tuple)):
        tempos = [tempos]
    tempos = [float(value) for value in tempos]
    variations = spec.variations(set_name)
    if variation not in (None, "", "all", "AB"):
        if variation not in variations:
            raise PlanError("Set {0!r} has variations {1}, not {2!r}".format(set_name, ", ".join(variations), variation))
        variations = [variation]
    warnings = []
    if bars is not None:
        bars = int(bars)
        if bars <= 0:
            raise PlanError("bars must be a positive number of bars")
        off = sorted(set(part.id for part in spec.parts(set_name, variations=variations) if part.bars < bars and bars % part.bars))
        if off:
            warnings.append("bars={0} is not a whole number of loops of {1}: their kept cut starts mid-loop".format(bars, ", ".join(off)))
    unknown = [tempo for tempo in tempos if tempo not in set_tempos]
    if unknown:
        warnings.append("Tempo {0} is not one of the set's tempos ({1})".format(
            ", ".join("{0:g}".format(t) for t in unknown), ", ".join("{0:g}".format(t) for t in set_tempos)))
    tracks = _tracks_by_name(snapshot)
    scene_slots = _scene_slots(snapshot)
    returns = [entry["name"] for entry in snapshot.get("returns") or []]
    tail_beats = lambda tempo: spec.tail_seconds() * tempo / 60.0
    bpb = spec.beats_per_bar
    layout = spec.layout(set_name)
    passes, takes = [], []
    for tempo in tempos:
        try:
            band = spec.band(set_name, tempo)
        except SpecError as error:
            raise PlanError(str(error))
        resolved, missing = [], []
        for part in spec.parts(set_name, variations=variations):
            candidates = tracks.get(part.track) or []
            if len(candidates) != 1:
                missing.append("{0} (track {1!r} {2})".format(part.id, part.track, "missing" if not candidates else "is not unique"))
                continue
            track = candidates[0]
            slot, scene, clip = find_clip(spec, set_name, part, track, band, scene_slots)
            if slot is None:
                missing.append("{0} (no clip in {1} on {2!r})".format(part.id, " or ".join(spec.scenes_for(set_name, band)) or "any scene", part.track))
                continue
            resolved.append({"part": part, "track": track, "slot": slot, "scene": scene, "clip": clip})
        if missing:
            warnings.append("Not captured at {0:g} BPM: {1}".format(tempo, "; ".join(missing)))
        if not resolved:
            raise PlanError("Nothing to capture at {0:g} BPM: {1}".format(tempo, "; ".join(missing)))
        muted = [item["part"].id for item in resolved if item["track"].get("mute")]
        if muted:
            warnings.append("Muted part tracks record silence: " + ", ".join(muted))
        sending = dict((item["part"].id, sends_in_use(item["track"])) for item in resolved if sends_in_use(item["track"]))
        if sending and mode == "tap":
            warnings.append("{0} send to returns; tap stems lack those effects, so tier sums are approximate (use mode='solo')".format(
                ", ".join(sorted(sending))))
        groups = []
        if mode == "tap":
            if layout == "track" and not sending:
                groups.append(list(variations))
            else:
                groups.extend([v] for v in variations)
        take_passes = []
        if mode == "tap":
            for group in groups:
                members = [item for item in resolved if item["part"].variation in (None,) + tuple(group)]
                cycle = int(bars or max(item["part"].bars for item in members))
                suffix = "" if len(groups) == 1 else "@" + group[0]
                cuts = []
                for item in members:
                    part = item["part"]
                    cuts.append({"key": part.id, "kind": "part", "name": part.id, "bars": part.bars, "track": part.track,
                                 "start_beats": cycle * bpb, "length_beats": min(part.bars, cycle) * bpb, "file": "stems/{0}.wav".format(part.id)})
                record = [{"key": item["part"].id, "source": item["part"].track, "tap": "Post Mixer"} for item in members]
                for name in returns:
                    record.append({"key": name, "source": name, "tap": "Post Mixer"})
                    cuts.append({"key": name, "kind": "return", "name": name + suffix, "start_beats": cycle * bpb,
                                 "length_beats": cycle * bpb, "file": "returns/{0}{1}.wav".format(name, suffix)})
                record.append({"key": "mix", "source": "resampling"})
                cuts.append({"key": "mix", "kind": "mix", "name": "mix" + suffix, "start_beats": cycle * bpb,
                             "length_beats": cycle * bpb, "file": "mix{0}.wav".format(suffix)})
                take_passes.append(len(passes))
                passes.append({"label": "{0:g} BPM {1} tap".format(tempo, "+".join(group)), "tempo": tempo,
                               "fire": [{"track": item["part"].track, "slot": item["slot"]} for item in members],
                               "record": record, "solo": None, "mute_others": True,
                               "beats": round(2 * cycle * bpb + tail_beats(tempo), 6), "cycle_bars": cycle,
                               "variations": list(group), "cuts": cuts})
        else:
            for item in resolved:
                part = item["part"]
                context = part.variation or variations[0]
                members = [other for other in resolved if other["part"].variation in (None, context)]
                cycle = int(bars or part.bars)
                take_passes.append(len(passes))
                passes.append({"label": "{0:g} BPM {1} solo".format(tempo, part.id), "tempo": tempo,
                               "fire": [{"track": other["part"].track, "slot": other["slot"]} for other in members],
                               "record": [{"key": "mix", "source": "resampling"}], "solo": [part.track], "mute_others": False,
                               "beats": round(2 * cycle * bpb + tail_beats(tempo), 6), "cycle_bars": cycle, "variations": [context],
                               "cuts": [{"key": "mix", "kind": "part", "name": part.id, "bars": part.bars, "track": part.track,
                                         "start_beats": cycle * bpb, "length_beats": min(part.bars, cycle) * bpb,
                                         "file": "stems/{0}.wav".format(part.id)}]})
        takes.append({"set": set_name, "tempo": tempo, "variation": "".join(variations), "variations": list(variations),
                      "mode": mode, "bars": bars, "band": band["name"] if band else None, "passes": take_passes,
                      "parts": [item["part"].id for item in resolved],
                      "clips": dict((item["part"].id, {"track": item["part"].track, "slot": item["slot"], "scene": item["scene"]})
                                    for item in resolved)})
    seconds = sum(item["beats"] * 60.0 / item["tempo"] + 1.5 for item in passes)
    return report.clean({"set": set_name, "mode": mode, "tempos": tempos, "variations": variations, "passes": passes,
                         "takes": takes, "warnings": warnings, "seconds": round(seconds, 1)})


def engine_passes(plan):
    """The passes as the Remote Script's capture_start takes them (cut windows stay on this side)."""
    keys = ("label", "tempo", "fire", "record", "solo", "mute_others", "beats")
    return [dict((key, item[key]) for key in keys) for item in plan["passes"]]
