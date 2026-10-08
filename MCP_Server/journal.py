"""Reading the Remote Script's command journal (AbletonMCP_Remote_Script/journal.py writes it).

`ableton-mcp journal` shows the last lines and what was in flight; `--crash` finds Live's last fatal error in
its Log.txt and shows what AbletonMCP was doing just before it.
"""
import datetime
import glob
import os
import re

DEFAULT_PATH = "~/Library/Logs/AbletonMCP/live-commands.log"
LIVE_PREFERENCES = "~/Library/Preferences/Ableton"
FATAL_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+): error: FatalError: (.*)$")


def journal_path():
    configured = os.environ.get("ABLETON_MCP_JOURNAL", DEFAULT_PATH)
    if configured.strip().lower() in ("", "off", "0", "false", "none"):
        configured = DEFAULT_PATH
    return os.path.expanduser(configured)


def _time(text):
    """A local timestamp with any fraction of a second (the journal writes milliseconds, Live microseconds)."""
    try:
        return datetime.datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        return None


def parse(lines):
    """Journal lines as dicts: time (datetime), event, number, fields (the rest)."""
    out = []
    for line in lines:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3:
            continue
        when = _time(parts[0])
        if when is None:
            continue
        out.append({"time": when, "event": parts[1], "number": parts[2], "fields": parts[3:], "line": line.rstrip("\n")})
    return out


def read(path=None, until=None):
    """Entries of the journal (and its rotated predecessor), oldest first, up to `until` (a datetime)."""
    path = path or journal_path()
    entries = []
    for name in (path + ".1", path):
        if os.path.isfile(name):
            with open(name, encoding="utf-8", errors="replace") as handle:
                entries.extend(parse(handle))
    entries.sort(key=lambda entry: entry["time"])
    if until is not None:
        entries = [entry for entry in entries if entry["time"] <= until]
    return entries


def in_flight(entries):
    """Requests that started (and maybe ran) without ending, with the batch item they were on.

    A core (re)load starts the numbering again, so it closes everything before it."""
    open_requests = {}
    for entry in entries:
        kind, number = entry["event"], entry["number"]
        if kind == "load":
            open_requests.clear()
        elif kind == "start":
            client, command, params = (entry["fields"] + ["", "", ""])[:3]
            open_requests[number] = {"number": number, "since": entry["time"], "client": client, "command": command,
                                     "params": params, "running": False, "item": None}
        elif kind == "run" and number in open_requests:
            open_requests[number]["running"] = True
        elif kind == "item":
            base = number.split(".")[0]
            if base in open_requests:
                open_requests[base]["item"] = {"index": number, "command": (entry["fields"] + [""])[0],
                                               "params": (entry["fields"] + ["", ""])[1]}
        elif kind == "end":
            open_requests.pop(number, None)
    return sorted(open_requests.values(), key=lambda item: item["since"])


def live_logs():
    return sorted(glob.glob(os.path.join(os.path.expanduser(LIVE_PREFERENCES), "Live *", "Log.txt")), key=os.path.getmtime)


def last_fatal(log_paths=None):
    """(time, message) of the newest crash in Live's logs, or None. Live writes several FatalError lines for one
    crash ("Uncaught exception", then the exception itself); lines within a second of each other are one crash."""
    lines = []
    for path in log_paths if log_paths is not None else live_logs():
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = FATAL_RE.match(line.strip())
                when = _time(match.group(1)) if match else None
                if when:
                    lines.append((when, match.group(2)))
    if not lines:
        return None
    lines.sort()
    group = [lines[-1]]
    for when, message in reversed(lines[:-1]):
        if (group[0][0] - when).total_seconds() > 1.0:
            break
        group.insert(0, (when, message))
    return group[0][0], " | ".join(message for _, message in group)


def _format(entry):
    return entry["line"]


def report(lines=40, crash=False, path=None, log_paths=None):
    """Text for `ableton-mcp journal`."""
    out = []
    path = path or journal_path()
    until = None
    if crash:
        fatal = last_fatal(log_paths)
        if not fatal:
            return "No FatalError in Live's logs."
        until = fatal[0]
        out.append("Live's last fatal error: {0}  {1}".format(fatal[0].isoformat(sep=" "), fatal[1]))
    entries = read(path, until=until)
    if not entries:
        out.append("The journal {0} has no entries{1}.".format(path, " before that time" if crash else ""))
        return "\n".join(out)
    if crash and (until - entries[-1]["time"]).total_seconds() > 600:
        out.append("The journal's last entry is {0}, long before the crash: AbletonMCP was idle.".format(entries[-1]["time"]))
    out.append("")
    out.extend(_format(entry) for entry in entries[-lines:])
    flying = in_flight(entries)
    out.append("")
    if not flying:
        out.append("Nothing was in flight" + (" when Live died." if crash else "."))
    for item in flying:
        state = "running" if item["running"] else "queued (not started on Live's main thread)"
        line = "In flight: #{0} {1} {2} from {3}, {4} since {5}".format(item["number"], item["command"], item["params"], item["client"],
                                                                     state, item["since"].isoformat(sep=" "))
        if item["item"]:
            line += "; at batch item {0}: {1} {2}".format(item["item"]["index"], item["item"]["command"], item["item"]["params"])
        out.append(line)
    return "\n".join(out)
