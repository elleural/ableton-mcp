"""Command journal: what AbletonMCP asked Live to do, written as it happens (crash forensics).

Every request gets a "start" line when it arrives (socket thread), a "run" line when Live's main thread begins it,
and an "end" line with its status and duration. Batch items get "item" lines, and the capture and bounce engines
log their phase changes, since they act on Live from timer ticks rather than commands. Each line is flushed at
once, so when Live dies the last "run" or "item" without an "end" names what was running.

    ~/Library/Logs/AbletonMCP/live-commands.log   (rotated at 8 MB; the previous file is kept as .1)

ABLETON_MCP_JOURNAL overrides the path; "off" disables the journal (the offline tests do).
Columns (tab-separated): local time, event, sequence number, then event fields.
"""
import itertools
import json
import os
import threading
import time

DEFAULT_PATH = "~/Library/Logs/AbletonMCP/live-commands.log"
MAX_BYTES = 8 * 1024 * 1024
TEXT_CHARS = 300

_lock = threading.Lock()
_state = {"handle": None, "path": None}
_sequence = itertools.count(1)


def path():
    configured = os.environ.get("ABLETON_MCP_JOURNAL", DEFAULT_PATH)
    if configured.strip().lower() in ("", "off", "0", "false", "none"):
        return None
    return os.path.expanduser(configured)


def _handle(target):
    handle = _state["handle"]
    if handle is None or handle.closed or _state["path"] != target:
        if handle is not None and not handle.closed:
            handle.close()
        os.makedirs(os.path.dirname(target), exist_ok=True)
        handle = open(target, "a", encoding="utf-8")
        _state["handle"], _state["path"] = handle, target
    if handle.tell() >= MAX_BYTES:
        handle.close()
        os.replace(target, target + ".1")
        handle = open(target, "a", encoding="utf-8")
        _state["handle"] = handle
    return handle


def _stamp(now=None):
    now = time.time() if now is None else now
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)) + ".{0:03d}".format(int(now * 1000) % 1000)


def write(*fields):
    """Append one line (never raises: the journal must not break a command)."""
    target = path()
    if target is None:
        return
    line = "\t".join([_stamp()] + [str(field).replace("\t", " ").replace("\n", " ") for field in fields])
    try:
        with _lock:
            handle = _handle(target)
            handle.write(line + "\n")
            handle.flush()
    except Exception:
        pass


def shape(value, depth=0):
    """A small stand-in for a value: short scalars as they are, long text cut, big containers as their size
    (a 1.6 MB snapshot must not be copied into the journal)."""
    if isinstance(value, str):
        return value if len(value) <= 80 else value[:77] + "..."
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        if depth >= 2 or len(value) > 12:
            return "<object {0} keys>".format(len(value))
        return dict((str(key), shape(item, depth + 1)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        if depth >= 2 or len(value) > 8:
            return "<list {0}>".format(len(value))
        return [shape(item, depth + 1) for item in value]
    return "<{0}>".format(type(value).__name__)


def summary(params):
    try:
        text = json.dumps(shape(params or {}), separators=(",", ":"), sort_keys=True, default=str)
    except Exception:
        text = "<unprintable>"
    return text if len(text) <= TEXT_CHARS else text[:TEXT_CHARS - 3] + "..."


def start(command, params=None, client=None):
    """Log a request's arrival; returns its sequence number."""
    number = next(_sequence)
    write("start", number, client or "-", command, summary(params))
    return number


def run(number):
    write("run", number)


def item(number, index, command, params=None):
    write("item", "{0}.{1}".format(number, index), command, summary(params))


def end(number, status, started, detail=""):
    write("end", number, status, "{0:.1f}ms".format((time.time() - started) * 1000.0), str(detail)[:TEXT_CHARS])


def event(kind, text):
    write(kind, "-", str(text)[:TEXT_CHARS])
