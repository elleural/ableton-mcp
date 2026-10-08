"""Takes: one capture of the set's state as a folder of files (PRD sections 4 and 9).

    <ears home>/takes/<set>-<bpm>-<variation>-<nnnn>/
        take.json      provenance (C6): set, tempo, variations, mode, bars, Live version, offsets and
                       gains applied, formats, warnings; parts -> files
        stems/<part>.wav   the kept cycle of each part plus the tail (float WAV, no requantization)
        returns/<name>.wav, mix.wav (tap mode; "@<variation>" suffixes when passes were per variation)
        snapshot.json  notes, mixer and device parameters at capture time (restore)
        report.json, images/

`ingest()` turns a finished capture job (the Remote Script's recorded files plus the plan's cut
windows) into take folders; `load()` reads one back for analysis. Analysis only needs file paths, so
hand-exported files work too (`from_files()`).
"""
import json
import os
import re
import shutil
from pathlib import Path

from . import __version__, audio, report

TAKE_ID = re.compile(r"-(?P<number>\d{4,})$")


class TakeError(ValueError):
    """A take folder is missing or malformed."""


def takes_dir(home):
    return Path(home) / "takes"


def format_bpm(bpm):
    value = float(bpm)
    return "{0:g}".format(value) if value != int(value) else str(int(value))


def next_id(home, set_name, bpm, variation):
    """<set>-<bpm>-<variation>-<nnnn>, numbered after every take in the home and never an existing folder."""
    folder = takes_dir(home)
    numbers = [0]
    if folder.is_dir():
        for child in folder.iterdir():
            match = TAKE_ID.search(child.name)
            if match:
                numbers.append(int(match.group("number")))
    number = max(numbers) + 1
    while True:
        take_id = "{0}-{1}-{2}-{3:04d}".format(set_name, format_bpm(bpm), variation, number)
        if not (folder / take_id).exists():
            return take_id
        number += 1


def take_path(home, take_id):
    path = takes_dir(home) / take_id
    if not (path / "take.json").is_file():
        raise TakeError("No take {0!r} in {1}".format(take_id, takes_dir(home)))
    return path


def list_ids(home):
    folder = takes_dir(home)
    if not folder.is_dir():
        return []
    return sorted(child.name for child in folder.iterdir() if (child / "take.json").is_file())


class Take(object):
    """A take folder: metadata plus lazily decoded audio."""

    def __init__(self, path):
        self.path = Path(path)
        try:
            self.meta = json.loads((self.path / "take.json").read_text())
        except (OSError, ValueError) as error:
            raise TakeError("Cannot read {0}: {1}".format(self.path / "take.json", error))
        self._cache = {}

    @property
    def id(self):
        return self.meta["id"]

    @property
    def set(self):
        return self.meta["set"]

    @property
    def tempo(self):
        return float(self.meta["tempo"])

    @property
    def variations(self):
        return list(self.meta.get("variations") or [])

    @property
    def mode(self):
        return self.meta.get("mode", "tap")

    def file(self, relative):
        return self.path / relative

    def _read(self, relative):
        if relative not in self._cache:
            self._cache[relative] = audio.read(self.path / relative)
        return self._cache[relative]

    def part_bars(self):
        """{part id: bars of loop in its file}: the spec's loop length, or less for a `bars` quick check."""
        return dict((part, entry.get("cut_bars") or entry.get("bars")) for part, entry in (self.meta.get("parts") or {}).items()
                    if entry.get("cut_bars") or entry.get("bars"))

    def parts(self):
        """{part id: Audio} of every captured stem."""
        return dict((part, self._read(entry["file"])) for part, entry in (self.meta.get("parts") or {}).items())

    def part(self, part_id):
        entry = (self.meta.get("parts") or {}).get(part_id)
        return self._read(entry["file"]) if entry else None

    def returns(self, variation=None):
        out = {}
        for name, entry in (self.meta.get("returns") or {}).items():
            if variation is None or entry.get("variations") is None or variation in entry["variations"]:
                out[name] = self._read(entry["file"])
        return out

    def mixes(self):
        """[(variations covered, Audio)] for every recorded main mix."""
        return [(entry.get("variations") or self.variations, self._read(entry["file"])) for entry in self.meta.get("mixes") or []]

    def snapshot(self):
        path = self.path / "snapshot.json"
        return json.loads(path.read_text()) if path.is_file() else None

    def save(self):
        (self.path / "take.json").write_text(json.dumps(report.clean(self.meta), indent=1) + "\n")


def load(home, take_id):
    return Take(take_path(home, take_id))


def _cut(source, offset_samples, start_beats, length_beats, tail_s, tempo):
    """Kept cycle of a recording: from `start_beats` after clip beat 0, `length_beats` plus the tail."""
    rate = source.rate
    beat = 60.0 / float(tempo)
    start = offset_samples + start_beats * beat * rate
    first = int(round(start))
    frames = int(round(length_beats * beat * rate + tail_s * rate))
    samples = source.samples[first:first + frames]
    short = frames - samples.shape[0]
    return audio.Audio(samples, rate), {"start_sample": first, "frames": frames, "short_frames": max(0, short),
                                        "fraction": round(start - first, 4)}


def _sum_null(item, files, tail_s, tempo):
    """(mix name, depth dB): the pass's part taps and returns summed over the mix's window, against the mix."""
    from .analyze import null_depth
    mixes = [cut for cut in item["cuts"] if cut["kind"] == "mix"]
    if not mixes or item.get("solo"):
        return None
    mix_cut = mixes[0]
    window = []
    for cut in item["cuts"]:
        if cut["kind"] == "mix":
            continue
        recorded = files.get(cut["key"])
        if recorded is None:
            return None
        source = audio.read(recorded["file_path"])
        kept, _ = _cut(source, recorded["offset_samples"], mix_cut["start_beats"], mix_cut["length_beats"], tail_s, tempo)
        window.append(kept.stereo())
    recorded = files.get(mix_cut["key"])
    if recorded is None or not window:
        return None
    mix, _ = _cut(audio.read(recorded["file_path"]), recorded["offset_samples"], mix_cut["start_beats"], mix_cut["length_beats"], tail_s, tempo)
    return mix_cut["name"], round(null_depth(mix.stereo(), window), 2)


def ingest(job, plan, spec, home, snapshot=None, note=None, keep_raw=False, delete_sources=True):
    """Cut a finished capture job into take folders; returns the list of take ids.

    job: the Remote Script's capture job (phase "recorded", with results per pass).
    plan: ears.plan.plan_capture() output; its takes name which pass and key gives which file.
    """
    results = job.get("results") or []
    if len(results) > len(plan["passes"]):
        raise TakeError("The capture recorded {0} passes, the plan has {1}".format(len(results), len(plan["passes"])))
    tail = spec.tail_seconds()
    bpb = spec.beats_per_bar
    created = []
    sources = set()
    for planned in plan["takes"]:
        if any(index >= len(results) for index in planned["passes"]):
            continue   # a later pass failed: only takes whose passes all recorded are kept (C7 fails the take)
        take_id = next_id(home, planned["set"], planned["tempo"], planned["variation"])
        folder = takes_dir(home) / take_id
        (folder / "stems").mkdir(parents=True, exist_ok=True)
        meta = {
            "id": take_id, "ears": __version__, "created": report.now(), "set": planned["set"], "tempo": planned["tempo"],
            "variation": planned["variation"], "variations": planned["variations"], "mode": planned["mode"],
            "bars": planned.get("bars"), "band": planned.get("band"), "spec": spec.name, "note": note,
            "live_version": job.get("live_version"), "live_set": job.get("set"), "capture_job": job.get("id"),
            "parts": {}, "returns": {}, "mixes": [], "passes": [], "warnings": list(plan.get("warnings") or []) + list(job.get("warnings") or []),
            "offsets": {}, "formats": {}, "clips": planned.get("clips"),
        }
        for pass_index in planned["passes"]:
            item = plan["passes"][pass_index]
            result = results[pass_index]
            if not result.get("tempo_steady", True):
                meta["warnings"].append("Pass {0}: the tempo moved during recording (C7); this take is unreliable".format(item["label"]))
            files = dict((entry["key"], entry) for entry in result["files"])
            null = _sum_null(item, files, tail, result.get("tempo") or planned["tempo"])
            if null is not None:
                meta.setdefault("sum_null", {})[null[0]] = null[1]
            meta["passes"].append({"label": item["label"], "tempo": result.get("tempo"), "beats": item["beats"],
                                   "cycle_bars": item["cycle_bars"], "variations": item.get("variations")})
            for cut in item["cuts"]:
                recorded = files.get(cut["key"])
                if recorded is not None:
                    sources.add(recorded["file_path"])
                if cut["kind"] == "part" and cut["name"] in meta["parts"]:
                    continue   # a shared part recorded again in a later pass: keep the first
                if recorded is None:
                    meta["warnings"].append("Pass {0} recorded nothing for {1}".format(item["label"], cut["key"]))
                    continue
                source = audio.read(recorded["file_path"])
                sources.add(recorded["file_path"])
                kept, info = _cut(source, recorded["offset_samples"], cut["start_beats"], cut["length_beats"], tail, result.get("tempo") or planned["tempo"])
                if info["short_frames"]:
                    meta["warnings"].append("{0} is {1} samples short of its cut".format(cut["name"], info["short_frames"]))
                relative = cut["file"]
                audio.write_wav(folder / relative, kept.samples, kept.rate, 32)
                entry = {"file": relative, "source": recorded["source"], "tap": recorded.get("tap"), "pass": item["label"],
                         "start_beats": cut["start_beats"], "length_beats": cut["length_beats"], "frames": kept.frames}
                if cut["kind"] == "part":
                    meta["parts"][cut["name"]] = dict(entry, bars=cut.get("bars"), track=cut.get("track"),
                                                      cut_bars=round(cut["length_beats"] / bpb, 6))
                elif cut["kind"] == "return":
                    meta["returns"][cut["name"]] = dict(entry, variations=item.get("variations"))
                else:
                    meta["mixes"].append(dict(entry, variations=item.get("variations")))
                meta["offsets"][cut["name"]] = {"offset_samples": recorded["offset_samples"], "cut_start_sample": info["start_sample"],
                                                "fraction": info["fraction"], "calibration_samples": 0}
                meta["formats"][cut["name"]] = {"sample_rate": source.rate, "bit_depth": source.bit_depth, "format": source.format}
                if keep_raw:
                    raw = folder / "raw" / os.path.basename(recorded["file_path"])
                    raw.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(recorded["file_path"], raw)
        rates = sorted(set(item["sample_rate"] for item in meta["formats"].values()))
        depths = sorted(set(item["bit_depth"] for item in meta["formats"].values() if item["bit_depth"]))
        target_rate, target_depth = spec.target("sample_rate"), spec.target("bit_depth")
        if target_rate and rates and rates != [int(target_rate)]:
            meta["warnings"].append("Captured at {0} Hz, not the spec's {1} Hz (Live's audio preference); delivery files still need {1} Hz (C5)".format(
                "/".join(str(rate) for rate in rates), int(target_rate)))
        if target_depth and depths and depths != [int(target_depth)]:
            meta["warnings"].append("Recorded at {0}-bit, not {1}-bit (C5)".format("/".join(str(d) for d in depths), int(target_depth)))
        meta["sample_rate"] = rates[0] if len(rates) == 1 else rates
        meta["gain_applied_db"] = 0.0
        (folder / "take.json").write_text(json.dumps(report.clean(meta), indent=1) + "\n")
        if snapshot is not None:
            (folder / "snapshot.json").write_text(json.dumps(snapshot, separators=(",", ":")) + "\n")
        created.append(take_id)
    if delete_sources:
        for path in sources:
            try:
                os.remove(path)   # Live's own copy of a temporary recording; the take keeps the cut
            except OSError:
                pass
    return created


def from_files(home, set_name, tempo, files, spec, variation=None, note=None, mode="files", copy=True):
    """A take from audio files on disk ({part id or "mix" or "return:<name>": path}), e.g. a hand export."""
    variations = [variation] if variation else spec.variations(set_name)
    label = variation or "".join(variations)
    take_id = next_id(home, set_name, tempo, label)
    folder = takes_dir(home) / take_id
    (folder / "stems").mkdir(parents=True, exist_ok=True)
    meta = {"id": take_id, "ears": __version__, "created": report.now(), "set": set_name, "tempo": float(tempo), "variation": label,
            "variations": variations, "mode": mode, "spec": spec.name, "note": note, "parts": {}, "returns": {}, "mixes": [],
            "passes": [], "warnings": [], "offsets": {}, "formats": {}}
    for key, path in files.items():
        decoded = audio.read(path)
        if key == "mix":
            relative = "mix.wav"
        elif key.startswith("return:"):
            relative = "returns/{0}.wav".format(key.split(":", 1)[1])
        else:
            relative = "stems/{0}.wav".format(key)
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if copy:
            shutil.copy2(path, target) if str(path).lower().endswith(".wav") else audio.write_wav(target, decoded.samples, decoded.rate, 32)
        else:
            relative = str(Path(path).resolve())   # read in place (acceptance runs over a delivery folder)
        entry = {"file": relative, "source": str(path), "frames": decoded.frames}
        if key == "mix":
            meta["mixes"].append(dict(entry, variations=variations))
        elif key.startswith("return:"):
            meta["returns"][key.split(":", 1)[1]] = entry
        else:
            meta["parts"][key] = entry
        meta["formats"][key] = {"sample_rate": decoded.rate, "bit_depth": decoded.bit_depth, "format": decoded.format}
    (folder / "take.json").write_text(json.dumps(report.clean(meta), indent=1) + "\n")
    return take_id
