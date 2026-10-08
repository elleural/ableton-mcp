"""Check results and reports (PRD section 9).

Every check returns plain dicts made by `check()`:

    {"check": "notes.chord_tones", "status": "fail", "subject": "bassA",
     "summary": "2 downbeat notes are not chord tones",
     "items": [{"where": "3.1.1", "found": "G1", "expected": "a tone of Dm (D F A)"}],
     "value": 0.82, "target": 1.0}

`status` is one of pass, fail, warn, info, skip. A check's *level* (the PRD's tables: fail, warn or
report) decides how a violation is reported: `violation(level)` gives fail, warn or info.

A report is a dict with "kind", "subject", "checks" and optional "values", "deltas", "images",
"warnings". `compact(report)` is what tools return (about 1,500 tokens at most); the full report is
written to disk with `write()`.
"""
import datetime
import json
import math
from pathlib import Path

STATUSES = ("fail", "warn", "info", "pass", "skip")
LEVELS = ("fail", "warn", "report")
COMPACT_CHARS = 6000          # about 1,500 tokens of JSON
MAX_ITEMS_PER_CHECK = 3
MAX_CHECKS_PER_STATUS = 8


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def violation(level):
    """The status a violated check reports at its level: fail, warn, or info for report-level checks."""
    if level == "fail":
        return "fail"
    if level == "warn":
        return "warn"
    return "info"


def clean(value, digits=3):
    """JSON-safe numbers: round floats, None for nan and infinities, recurse into lists and dicts."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, digits)
    if hasattr(value, "item") and callable(value.item) and getattr(value, "shape", None) == ():
        return clean(value.item(), digits)
    if isinstance(value, dict):
        return dict((str(key), clean(item, digits)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return [clean(item, digits) for item in value]
    if hasattr(value, "tolist"):
        return clean(value.tolist(), digits)
    return value


def check(name, status, subject=None, summary="", items=None, value=None, target=None, **extra):
    """One check result. Extra keyword fields (tolerance, unit, detail, ...) are kept as given."""
    if status not in STATUSES:
        raise ValueError("status must be one of {0}, got {1!r}".format(STATUSES, status))
    out = {"check": name, "status": status}
    if subject is not None:
        out["subject"] = subject
    out["summary"] = summary
    if items:
        out["items"] = clean(list(items))
    if value is not None:
        out["value"] = clean(value)
    if target is not None:
        out["target"] = clean(target)
    for key, item in extra.items():
        if item is not None:
            out[key] = clean(item)
    return out


def counts(checks):
    out = dict((status, 0) for status in STATUSES)
    for item in checks:
        out[item["status"]] = out.get(item["status"], 0) + 1
    return out


def verdict(checks):
    """"1 fail, 2 warn, 29 pass" (info and skip are not counted; the full report lists them)."""
    tally = counts(checks)
    return "{0} fail, {1} warn, {2} pass".format(tally["fail"], tally["warn"], tally["pass"])


def make(kind, subject, checks, **fields):
    """A full report: kind ("notes", "audio", "compare"), subject (take id or "live set") and checks."""
    report = {"kind": kind, "subject": subject, "created": now(), "verdict": verdict(checks),
              "counts": counts(checks), "checks": list(checks)}
    for key, value in fields.items():
        if value is not None:
            report[key] = value
    return report


MAX_SUMMARY_CHARS = 300
MAX_WARNINGS = 5


def _short(text, limit=MAX_SUMMARY_CHARS):
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _brief(item, max_items):
    out = {"check": item["check"]}
    for key in ("subject", "summary", "value", "target"):
        if item.get(key) not in (None, ""):
            out[key] = _short(item[key]) if key == "summary" else item[key]
    items = item.get("items") or []
    if items and max_items:
        out["items"] = items[:max_items]
        if len(items) > max_items:
            out["more_items"] = len(items) - max_items
    return out


def compact(report, full_report=None, max_chars=COMPACT_CHARS, extra=None):
    """The agent-facing view of a report: verdict, fails, warns, a few infos, deltas, images, path.

    Trims items, then whole entries, until the JSON fits in max_chars (about 1,500 tokens).
    """
    checks = report.get("checks") or []
    by_status = dict((status, [item for item in checks if item["status"] == status]) for status in STATUSES)
    max_items = MAX_ITEMS_PER_CHECK
    max_checks = MAX_CHECKS_PER_STATUS
    while True:
        out = {"subject": report.get("subject"), "kind": report.get("kind"), "verdict": report.get("verdict") or verdict(checks)}
        for key in ("take", "set", "tempo", "variation", "band", "mode", "scope"):
            if report.get(key) is not None:
                out[key] = report[key]
        for status in ("fail", "warn"):
            entries = by_status[status]
            if entries:
                out[status] = [_brief(item, max_items) for item in entries[:max_checks]]
                if len(entries) > max_checks:
                    out[status + "_more"] = len(entries) - max_checks
        infos = by_status["info"]
        if infos:
            out["info"] = [_brief(item, 0) for item in infos[:max_checks]]
            if len(infos) > max_checks:
                out["info_more"] = len(infos) - max_checks
        if report.get("deltas_vs"):
            out["deltas_vs"] = report["deltas_vs"]
        if report.get("deltas"):
            out["deltas"] = report["deltas"][:max(3, max_checks)]
        if report.get("values"):
            out["values"] = report["values"]
        warnings = report.get("warnings") or []
        if warnings:
            out["warnings"] = [_short(text, 200) for text in warnings[:MAX_WARNINGS]]
            if len(warnings) > MAX_WARNINGS:
                out["warnings_more"] = len(warnings) - MAX_WARNINGS
        if report.get("images"):
            out["images"] = list(report["images"])[:2]
        if extra:
            out.update(extra)
        if full_report:
            out["full_report"] = str(full_report)
        text = json.dumps(clean(out), separators=(",", ":"))
        if len(text) <= max_chars:
            return clean(out)
        if max_items > 1:
            max_items -= 1
        elif max_checks > 2:
            max_checks -= 2
        elif isinstance(report.get("values"), dict) and len(report["values"]) > 2:
            report = dict(report, values=dict(list(report["values"].items())[:2]))
        elif report.get("values"):
            report = dict(report, values=None)
        else:
            out.pop("info", None)
            out.pop("deltas", None)
            return clean(out)


def write(report, path):
    """Write the full report as indented JSON; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(report), indent=1) + "\n")
    return path


def where(bar, beat=1, sixteenth=1):
    """Clip time in the MCP's notation, 1-based: "3.1.1"."""
    return "{0}.{1}.{2}".format(int(bar), int(beat), int(sixteenth))


def beats_to_where(beats, beats_per_bar=4.0, grid=16):
    """Clip time in beats to "bar.beat.sixteenth" (1-based), rounding down to the sixteenth."""
    sixteenth_beats = 4.0 / grid if grid else 0.25   # grid 16 = sixteenth notes = 0.25 beat
    bar = int(math.floor(beats / beats_per_bar + 1e-9))
    in_bar = beats - bar * beats_per_bar
    beat = int(math.floor(in_bar + 1e-9))
    sixteenth = int(math.floor((in_bar - beat) / sixteenth_beats + 1e-9))
    return where(bar + 1, beat + 1, sixteenth + 1)
