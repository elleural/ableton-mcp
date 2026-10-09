"""Listening loop (docs/listening-loop-prd.md): capture takes, check notes and audio, compare, keep, restore.

Thin wrappers around the standalone `ears` package. The Remote Script only drives Live
(capture_* records Session clips, listening_* reads and writes notes, mixer and parameters);
planning, cutting, measuring and the ledger happen here, in ears.
"""
import json
import os
import threading
import time
from pathlib import Path

from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError

import ears
from ears import analyze as ears_analyze
from ears import compare as ears_compare
from ears import ledger
from ears import notes as ears_notes
from ears import plan as ears_plan
from ears import refs as ears_refs
from ears import report
from ears import spec as ears_spec
from ears import take as ears_take

from ..app import call, tool
from .lom import lom_names
from .references import loopback_busy

ACTIVE = ("route", "prepare", "fire", "starting", "recording", "collect", "restore", "verifying", "aborting")
MAX_WAIT = 600.0
POLL_SECONDS = 0.5
PENDING = "capture-pending.json"


def _home(song=None):
    song = song or call("bounce_song_info")
    return ears.home(song.get("set_path"), song.get("set_name"))


def _spec(name, home):
    """The spec: the argument, $EARS_SPEC, <ears home>/spec.json, else the bundled NOVA spec."""
    if not name and not os.environ.get("EARS_SPEC") and not (Path(home) / "spec.json").is_file():
        name = "nova"
    try:
        return ears_spec.load(name, home)
    except ears_spec.SpecError as error:
        raise ToolError(str(error))


def _pending_dir():
    """Pending captures live in one fixed folder keyed by job id, so saving the set mid-capture (which
    moves the ears home) cannot lose the plan."""
    return Path(os.environ.get("EARS_PENDING") or (ears.DEFAULT_ROOT / ".pending")).expanduser()


def _pending_file(job_id, suffix="json"):
    return _pending_dir() / "{0}.{1}".format(job_id, suffix)


def _save_pending(job_id, data, snapshot):
    folder = _pending_dir()
    folder.mkdir(parents=True, exist_ok=True)
    _pending_file(job_id, "snapshot.json").write_text(json.dumps(snapshot, separators=(",", ":")))
    _pending_file(job_id).write_text(json.dumps(data, separators=(",", ":")))


def _load_pending(job_id):
    path = _pending_file(job_id)
    if not job_id or not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def _finish_pending(job_id, result):
    """Keep the outcome (so a later capture() call can report it) and drop the plan and snapshot."""
    for suffix in ("json", "snapshot.json"):
        try:
            os.remove(_pending_file(job_id, suffix))
        except OSError:
            pass
    try:
        _pending_file(job_id, "result.json").write_text(json.dumps(result, separators=(",", ":"), default=str))
    except OSError:
        pass


def _last_result(job_id):
    path = _pending_file(job_id, "result.json")
    if job_id and path.is_file():
        try:
            return json.loads(path.read_text())
        except ValueError:
            return None
    return None


def _job_view(job, hint=None):
    out = {"job": job.get("id"), "phase": job.get("phase")}
    passes = job.get("passes") or []
    if passes:
        out["pass"] = "{0}/{1}".format(min(job.get("pass_index", 0) + 1, len(passes)), len(passes))
    for key in ("progress", "eta_seconds", "error", "warnings", "removed_tracks"):
        if job.get(key) not in (None, [], ""):
            out[key] = job[key]
    if hint:
        out["hint"] = hint
    return out


def _others(home, item):
    """The latest take of the same set and variation at every other tempo (for audio.tempo_consistency)."""
    latest = {}
    for entry in ledger.query(home, set_name=item.set, variation=item.meta.get("variation"), limit=200):
        if abs(float(entry["tempo"]) - item.tempo) > 1e-6 and entry["tempo"] not in latest and entry.get("mode") == item.mode:
            latest[entry["tempo"]] = entry["id"]
    out = []
    for take_id in latest.values():
        try:
            other = ears_take.load(home, take_id)
        except ears_take.TakeError:
            continue
        if not other.meta.get("bars") and not item.meta.get("bars"):   # bars quick checks are not comparable
            out.append(other)
    return out


def _analyze(home, spec, item, strict=False, images=True):
    folder = item.path / "images" if images else None
    result = ears_analyze.analyze_take(item, spec, strict_mode=strict, others=_others(home, item), images_dir=folder,
                                       envelope=ears_refs.balance_envelope())
    full = report.write(result, item.path / ("report-strict.json" if strict else "report.json"))
    ledger.record_verdict(home, item.id, result["verdict"], "strict" if strict else "audio")
    return result, full


_INGEST = threading.Lock()


def _single_take_result(home, item, result, full):
    out = report.compact(result, full)
    out["folder"] = str(item.path)
    paths = [path for path in result.get("images") or [] if str(path).endswith(".png") and os.path.isfile(path)][:2]
    if not paths:
        return out
    return [json.dumps(out, separators=(",", ":"))] + [Image(data=Path(path).read_bytes(), format="png") for path in paths]


def _ingest(job, analyze):
    """Cut a recorded (or partly recorded) job into takes, ledger them, clean Live up, then analyze."""
    with _INGEST:
        current = call("capture_status")
        if current.get("id") != job.get("id"):
            raise ToolError("Capture {0} is no longer the current job".format(job.get("id")))
        if current.get("phase") == "done":
            return _last_result(job["id"]) or _job_view(current)
        job = current
        pending = _load_pending(job["id"])
        if pending is None:
            if job.get("phase") == "recorded":
                call("capture_cleanup", job_id=job["id"])
            raise ToolError("Capture {0} recorded, but its plan was lost; capture again".format(job["id"]))
        home = Path(pending["home"])
        spec = _spec(pending.get("spec"), home)
        snapshot_file = _pending_file(job["id"], "snapshot.json")
        snapshot = json.loads(snapshot_file.read_text()) if snapshot_file.is_file() else None
        try:
            take_ids = ears_take.ingest(job, pending["plan"], spec, home, snapshot=snapshot, note=pending.get("note"))
        except (ears_take.TakeError, OSError, ValueError) as error:
            raise ToolError("Cutting capture {0} into takes failed: {1}. Its recordings are still in Live; capture(cancel=True) "
                            "removes the capture tracks.".format(job["id"], error))
        items = [ears_take.load(home, take_id) for take_id in take_ids]
        for item in items:
            ledger.record_take(home, item.meta, snapshot=str(item.path / "snapshot.json") if snapshot is not None else None)
        if job.get("phase") == "recorded":
            call("capture_cleanup", job_id=job["id"], outputs={"takes": take_ids})
        partial = job.get("phase") in ("failed", "cancelled")
        results = []
        for item in items:
            entry = {"item": item, "result": None, "full": None, "error": None}
            if analyze:
                try:
                    entry["result"], entry["full"] = _analyze(home, spec, item)
                except Exception as error:   # the take is kept; analyze_audio(take=...) can retry
                    entry["error"] = "{0}: {1}".format(type(error).__name__, error)
            results.append(entry)
        if len(results) == 1 and not partial and results[0]["result"] is not None:
            out = _single_take_result(home, results[0]["item"], results[0]["result"], results[0]["full"])
        else:
            rows = []
            for entry in results:
                row = {"take": entry["item"].id, "tempo": entry["item"].tempo, "folder": str(entry["item"].path)}
                if entry["result"] is not None:
                    row["verdict"] = entry["result"]["verdict"]
                    row["fail"] = [check["check"] + " " + str(check.get("subject")) + ": " + check["summary"]
                                   for check in entry["result"]["checks"] if check["status"] == "fail"][:3]
                if entry["error"]:
                    row["analysis_error"] = entry["error"]
                rows.append(row)
            out = {"takes": rows, "home": str(home), "hint": "analyze_audio(take=...) gives one take's full report"}
            if partial:
                out.update({"phase": job["phase"], "error": job.get("error"),
                            "note": "the capture stopped early; only takes whose passes all recorded were kept"})
        _finish_pending(job["id"], out if isinstance(out, dict) else json.loads(out[0]))
        return out


def _wait(job, wait, analyze):
    deadline = time.time() + max(0.0, min(MAX_WAIT, float(wait or 0)))
    while job.get("phase") in ACTIVE and time.time() < deadline:
        time.sleep(POLL_SECONDS)
        job = call("capture_status")
    phase = job.get("phase")
    if phase in ACTIVE:
        return _job_view(job, "Still recording: call capture() with no arguments to keep waiting, or capture(cancel=True).")
    if phase == "recorded":
        return _ingest(job, analyze)
    if phase in ("failed", "cancelled"):
        if job.get("results") and _load_pending(job.get("id")):
            return _ingest(job, analyze)   # keep the takes whose passes completed (C7 fails only the take)
        out = _job_view(job)
        if _load_pending(job.get("id")):
            _finish_pending(job["id"], out)
        return out
    return _last_result(job.get("id")) or _job_view(job)


@tool()
def capture(set: str | None = None, variation: str | None = None, tempo: float | None = None,
            tempos: list[float] | str | None = None, mode: str = "tap", bars: int | None = None, note: str | None = None,
            spec: str | None = None, wait: float = 300, cancel: bool = False, analyze: bool = True) -> list | dict:
    """Record the set's stems and mix in real time (audible) into a take, then analyze it (listening loop).

    Plans from the spec (default "nova"): each part's Session clip for the tempo's band is fired and recorded
    from its track output with every return and the main mix; the second cycle is kept, so tails are folded.
    tempo (default: the set's middle tempo) or tempos=[...]/"all" for a sweep (one take per tempo).
    variation: "A", "B" or all. mode "solo" records each part soloed (with return effects; slower).
    bars shortens the loop for quick checks. note: what changed (ledger). Leaves the set as found.
    Waits up to `wait` s (max 600); call capture() with no arguments to keep waiting for it or get its result.
    """
    if cancel:
        job = call("capture_cancel")
        deadline = time.time() + 10.0
        while job.get("phase") == "aborting" and time.time() < deadline:
            time.sleep(0.2)
            job = call("capture_status")
        if _load_pending(job.get("id")):
            _finish_pending(job["id"], _job_view(job))
        return _job_view(job)
    job = call("capture_status")
    starting = any(value is not None for value in (set, variation, tempo, tempos, bars, note, spec)) or mode != "tap"
    if job.get("phase") in ACTIVE + ("recorded",):
        if starting:
            raise ToolError("[busy] Capture {0} is {1}. Call capture() with no arguments to wait for it, or capture(cancel=True).".format(
                job.get("id"), job.get("phase")))
        return _wait(job, wait, analyze)
    if not starting and job.get("id") and (_load_pending(job["id"]) or _last_result(job["id"])):
        return _wait(job, 0, analyze)   # the outcome of the capture an earlier call started
    busy = loopback_busy()
    if busy:
        raise ToolError(busy)
    song = call("bounce_song_info")
    home = _home(song)
    spec_obj = _spec(spec, home)
    snapshot = call("listening_snapshot", notes=True, parameters=True, timeout=60)
    chosen = tempos if tempos is not None else ([tempo] if tempo is not None else None)
    try:
        plan = ears_plan.plan_capture(spec_obj, snapshot, set_name=set, variation=variation, tempos=chosen, mode=mode, bars=bars)
    except (ears_plan.PlanError, ears_spec.SpecError) as error:
        raise ToolError(str(error))
    job = call("capture_start", passes=ears_plan.engine_passes(plan), name=note, timeout=40)
    _save_pending(job["id"], {"job": job["id"], "home": str(home), "plan": plan, "spec": spec_obj.path or spec_obj.name, "note": note},
                  snapshot)
    out = _wait(job, wait, analyze)
    if isinstance(out, dict) and out.get("phase") in ACTIVE:
        out["seconds"] = plan["seconds"]
        if plan["warnings"]:
            out["plan_warnings"] = plan["warnings"]
    return out


def take_report(take_ref, strict=False, images=False, spec=None):
    """analyze_audio(take=...): the measurement ear on a take, compact, with up to two PNGs."""
    home = _home()
    spec_obj = _spec(spec, home)
    item = _resolve(home, take_ref)
    try:
        result, full = _analyze(home, spec_obj, item, strict=strict, images=images)
    except (ears_spec.SpecError, ears_take.TakeError, ValueError) as error:
        raise ToolError(str(error))
    compact = report.compact(result, full)
    paths = [path for path in result.get("images") or [] if str(path).endswith(".png") and os.path.isfile(path)][:2]
    if not images or not paths:
        return compact
    return [json.dumps(compact, separators=(",", ":"))] + [Image(data=Path(path).read_bytes(), format="png") for path in paths]


def _roll_band(result, band):
    roll = result.get("roll") or []
    bands = [item.get("band") for item in roll]
    if band and any(str(value).lower() == str(band).lower() for value in bands):
        chosen = next(value for value in bands if str(value).lower() == str(band).lower())
    elif "MID" in bands:
        chosen = "MID"
    else:
        chosen = bands[0] if bands else None
    return chosen, [item for item in roll if item.get("band") == chosen]


@tool(read_only=True)
def analyze_notes(set: str | None = None, band: str | None = None, parts: list[str] | None = None,
                  tempo: float | None = None, spec: str | None = None, image: bool = True) -> list | dict:
    """Check the stem clips' notes against the spec (no audio, under a second): run after every note edit.

    Fails: set.names, set.unwarped, notes.in_key (A minor, G# over E), notes.chord_tones (bass), notes.clash
    (stems a semitone apart), notes.shared_stem (the shared pad over every progression), notes.loop_length.
    Warns: grid, lead rests. Reports kick pattern, density, motif. band: "LOW"/"MID"/"HIGH" or a tempo
    (default every band). parts: ids like "bassA". image adds a piano roll coloured by chord-tone status.
    """
    song = call("bounce_song_info")
    home = _home(song)
    spec_obj = _spec(spec, home)
    snapshot = call("listening_snapshot", notes=True, parameters=False, timeout=30)
    try:
        result = ears_notes.analyze_notes(snapshot, spec_obj, set, band=band, parts=parts, tempo=tempo)
    except (ears_spec.SpecError, ValueError) as error:
        raise ToolError(str(error))
    folder = Path(home) / "notes"
    full = report.write(result, folder / "notes-{0}.json".format(time.strftime("%Y%m%d-%H%M%S")))
    compact = report.compact(dict(result, roll=None), full)
    if not image:
        return compact
    chosen, roll = _roll_band(result, band)
    if not roll:
        return compact
    from ears import images
    set_name = spec_obj.set_name(set)
    longest = max(part.bars for part in spec_obj.parts(set_name))
    variation = spec_obj.variations(set_name)[0]
    progression = spec_obj.progression(set_name, variation)
    path = images.piano_roll(roll, longest, spec_obj.beats_per_bar, [progression[i % len(progression)] for i in range(longest)],
                             path=str(folder / "roll.png"), title="{0} notes, band {1} (chords of {2})".format(set_name, chosen, variation))
    compact["images"] = [path]
    return [json.dumps(compact, separators=(",", ":")), Image(data=Path(path).read_bytes(), format="png")]


def _resolve(home, ref, against=None):
    """A Take from an id, "latest" or "best" (best of `against`'s set, tempo and variation)."""
    text = str(ref or "latest").strip()
    if text == "latest":
        entries = ledger.query(home, limit=1)
        if not entries:
            raise ToolError("No takes yet: capture first")
        return ears_take.load(home, entries[0]["id"])
    if text == "best":
        if against is None:
            raise ToolError("'best' needs the other side to say which set, tempo and variation")
        best = ledger.best(home, against.set, against.tempo, against.meta.get("variation"))
        if not best:
            raise ToolError("No kept take for {0}: takes(action='keep', take=...) marks one".format(
                ledger.best_key(against.set, against.tempo, against.meta.get("variation"))))
        return ears_take.load(home, best)
    try:
        return ears_take.load(home, text)
    except ears_take.TakeError as error:
        raise ToolError(str(error))


# A check whose verdict depends on what else was stored when the take was analysed: audio.balance changes as
# references are added, so its warns say nothing about the take itself.
CONTEXT_CHECKS = ("audio.balance",)


def _checks(item):
    path = item.path / "report.json"
    if not path.is_file():
        return None
    try:
        checks = json.loads(path.read_text()).get("checks")
    except ValueError:
        return None
    return dict(((check.get("check"), check.get("subject")), check.get("status")) for check in checks or [])


def comparable_counts(first, second):
    """Fail and warn counts of two takes over the checks both ran (neither skipped), leaving out CONTEXT_CHECKS,
    so a check that one report could not run, or that depends on the stored references, cannot pass for a
    regression. None when either report is missing."""
    a, b = _checks(first), _checks(second)
    if a is None or b is None:
        return None
    keys = [key for key in a if key in b and key[0] not in CONTEXT_CHECKS and "skip" not in (a[key], b[key])]
    count = lambda checks: dict((status, sum(1 for key in keys if checks[key] == status)) for status in ("fail", "warn"))
    return {"a": count(a), "b": count(b)}


@tool(read_only=True)
def compare(a: str = "latest", b: str = "best", blind: bool = False, variation: str | None = None,
            spec: str | None = None) -> dict:
    """Differences between two takes, or a take and the spec: what improved, regressed or is within noise.

    a: take id or "latest"; b: take id, "best" (the kept take of a's set, tempo and variation), "spec",
    "refs" (the top tier against the range of every stored reference's full sections), "refs:sparse" (tier T2
    against their sparse sections), "refs:<kind>:<tier>" (any tier), or "ref:<name>[:<section>]" (one
    reference, default section "full"). Against references, dynamics are information only.
    Spectral metrics are loudness-matched. Keep a change only when nothing regressed beyond noise.
    blind=True returns an X/Y packet without ids or statuses for a fresh judge subagent (the key is saved).
    """
    home = _home()
    spec_obj = _spec(spec, home)
    first = _resolve(home, a)
    if str(b).strip() == "spec":
        return dict(ears_compare.compare_spec(first, spec_obj), a=first.id, b="spec")
    if str(b).strip() == "refs" or str(b).strip().startswith("refs:"):
        parts = str(b).strip().split(":")
        kind = parts[1] if len(parts) > 1 and parts[1] else "full"
        tier = parts[2] if len(parts) > 2 and parts[2] else None
        if kind not in ears_refs.KINDS:
            raise ToolError("Unknown section kind {0!r}: use refs, refs:sparse, refs:track or refs:<kind>:<tier>".format(kind))
        stored = ears_refs.all_refs()
        if not stored:
            raise ToolError("No references stored yet: ref(action='measure', uri=...) or ref(action='add', file=...)")
        try:
            result = ears_compare.compare_envelope(first, ears_refs.envelope(stored, kind), spec_obj, variation=variation, tier=tier)
        except ValueError as error:
            raise ToolError(str(error))
        bands = result.pop("bands")
        return dict(result, a=first.id, b=str(b), bands=bands[:10], more_bands=max(0, len(bands) - 10))
    if str(b).startswith("ref:"):
        _, _, rest = str(b).partition(":")
        name, _, section = rest.partition(":")
        stored = ears_refs.find(name=name)
        if not stored:
            raise ToolError("No reference named {0}; ref(action='list') shows them".format(name))
        sections = stored.get("sections") or {}
        chosen = section or ("full" if "full" in sections else "track")
        if chosen not in sections:
            raise ToolError("Reference {0} has no section {1} (it has {2})".format(name, chosen, ", ".join(sections)))
        result = ears_compare.compare_reference(first, sections[chosen], spec_obj, variation)
        return dict(result, a=first.id, b="ref:{0}:{1}".format(stored["name"], chosen))
    second = _resolve(home, b, against=first)
    if first.id == second.id:
        raise ToolError("Both sides are take {0}".format(first.id))
    result = ears_compare.compare_takes(first, second, spec_obj, home=home, variation=variation,
                                        check_counts=comparable_counts(first, second))
    if blind:
        packet = ears_compare.blind_packet(result, first.id, second.id)
        key_path = Path(home) / "blind" / "{0}.json".format(time.strftime("%Y%m%d-%H%M%S"))
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(json.dumps(packet["key"]))
        return {"packet": packet["packet"], "key_file": str(key_path),
                "hint": "Give only the packet to a fresh subagent; read key_file after its verdict."}
    deltas = result["deltas"]
    return {"a": first.id, "b": second.id, "variation": result["variation"], "regressed": result["regressed"],
            "improved": result["improved"], "deltas": deltas[:12], "more_deltas": max(0, len(deltas) - 12),
            "noise_floor_db": ears_compare.noise_floor(home, "default")}


@tool(destructive=True)
def takes(action: str = "list", take: str | None = None, set: str | None = None, tempo: float | None = None,
          variation: str | None = None, limit: int = 10, notes: bool = True, parameters: bool = True,
          dry_run: bool = False) -> dict:
    """The take history (ledger), the kept best take, and restoring an earlier take's notes and parameters.

    action "list": newest takes (filter by set, tempo, variation) with verdicts and which is best.
    "keep": mark `take` as the best of its set, tempo and variation (compare(b="best") uses it).
    "restore": write `take`'s snapshot back into its part tracks: clip notes, device parameters, mixer
    (one undo step). Devices added or removed since are listed, not undone; plugin state is not covered.
    Destructive: restore overwrites the current notes and settings (dry_run=True previews).
    """
    song = call("bounce_song_info")
    home = _home(song)
    action = (action or "list").strip().lower()
    if action == "list":
        entries = ledger.query(home, set_name=set, tempo=tempo, variation=variation, limit=max(1, min(50, int(limit))))
        out = {"home": str(home), "takes": entries, "best": ledger.state(home)[1]}
        behind = None
        if song.get("set_path") and not entries:
            behind = ears.left_behind(song.get("set_path"), song.get("set_name"), lom_names("live_set", "tracks"))
        if behind:
            out["hint"] = ("Takes recorded before this set was first saved seem to be in {0} (their tracks match this "
                           "set's); ask the user before moving that folder to {1}".format(behind, home))
        return out
    if not take:
        raise ToolError("action {0!r} needs take=<take id>".format(action))
    item = _resolve(home, take)
    if action == "keep":
        key = ledger.keep(home, item.meta)
        return {"kept": item.id, "key": key, "verdict": next((e.get("verdict") for e in ledger.query(home, text=item.id, limit=1)), None)}
    if action == "restore":
        snapshot = item.snapshot()
        if not snapshot:
            raise ToolError("Take {0} has no snapshot to restore".format(item.id))
        wanted = {entry.get("track") for entry in (item.meta.get("parts") or {}).values() if entry.get("track")}
        if wanted:
            snapshot = dict(snapshot, tracks=[track for track in snapshot.get("tracks") or [] if track.get("name") in wanted])
        result = call("listening_restore", snapshot=snapshot, notes=notes, parameters=parameters, mixer=True, dry_run=dry_run, timeout=60)
        result["take"] = item.id
        return result
    raise ToolError("action must be list, keep or restore, not {0!r}".format(action))
