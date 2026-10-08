"""The ledger: one JSON line per take, plus "best" pointers (PRD section 9).

    {"type": "take", "id", "time", "set", "tempo", "variation", "mode", "note", "verdict", "snapshot"}
    {"type": "verdict", "take", "time", "verdict", "kind"}        a later analysis of a take
    {"type": "best", "key": "<set>-<bpm>-<variation>", "take", "time"}   keep(take) moves the pointer

The file is append-only, so history survives; readers fold the lines into the current state.
"""
import json
from pathlib import Path

from . import report
from .take import format_bpm


def path(home):
    return Path(home) / "ledger.jsonl"


def append(home, entry):
    entry = dict(entry)
    entry.setdefault("time", report.now())
    target = path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a") as handle:
        handle.write(json.dumps(report.clean(entry), separators=(",", ":")) + "\n")
    return entry


def lines(home):
    target = path(home)
    if not target.is_file():
        return []
    out = []
    for line in target.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def best_key(set_name, tempo, variation):
    return "{0}-{1}-{2}".format(set_name, format_bpm(tempo), variation)


def state(home):
    """(takes in order with their latest verdicts, {best key: take id})."""
    takes, best = {}, {}
    order = []
    for entry in lines(home):
        kind = entry.get("type")
        if kind == "take":
            takes[entry["id"]] = dict(entry)
            order.append(entry["id"])
        elif kind == "verdict" and entry.get("take") in takes:
            verdicts = takes[entry["take"]].setdefault("verdicts", {})
            verdicts[entry.get("kind", "audio")] = entry.get("verdict")
            if entry.get("kind", "audio") == "audio":
                takes[entry["take"]]["verdict"] = entry.get("verdict")
        elif kind == "best":
            best[entry["key"]] = entry["take"]
    return [takes[take_id] for take_id in order], best


def record_take(home, meta, verdict=None, snapshot=None):
    return append(home, {"type": "take", "id": meta["id"], "set": meta["set"], "tempo": meta["tempo"], "variation": meta["variation"],
                         "mode": meta.get("mode"), "note": meta.get("note"), "verdict": verdict, "snapshot": snapshot})


def record_verdict(home, take_id, verdict, kind="audio"):
    return append(home, {"type": "verdict", "take": take_id, "verdict": verdict, "kind": kind})


def keep(home, meta):
    key = best_key(meta["set"], meta["tempo"], meta["variation"])
    append(home, {"type": "best", "key": key, "take": meta["id"]})
    return key


def best(home, set_name, tempo, variation):
    return state(home)[1].get(best_key(set_name, tempo, variation))


def query(home, set_name=None, tempo=None, variation=None, text=None, limit=20):
    """Takes, newest first, filtered; each marked best when a pointer names it."""
    takes, pointers = state(home)
    kept = set(pointers.values())
    out = []
    for entry in reversed(takes):
        if set_name and entry.get("set") != set_name:
            continue
        if tempo is not None and abs(float(entry.get("tempo", 0)) - float(tempo)) > 1e-6:
            continue
        if variation and entry.get("variation") != variation:
            continue
        if text and text.lower() not in json.dumps(entry).lower():
            continue
        item = dict((key, entry.get(key)) for key in ("id", "time", "set", "tempo", "variation", "mode", "note", "verdict"))
        item["best"] = entry["id"] in kept
        out.append(item)
        if len(out) >= limit:
            break
    return out
