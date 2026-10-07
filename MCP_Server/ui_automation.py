"""Optional macOS UI automation for what Live's API cannot do: save, new set and offline export.

AppleScript drives Live through System Events (menu shortcuts and the native file panel). macOS must
allow the app that runs the MCP server (Claude, Terminal, an IDE, ...) both:

- System Settings > Privacy & Security > Accessibility, and
- System Settings > Privacy & Security > Automation > System Events.

status() works out availability without prompting wherever macOS allows it: Accessibility through
AXIsProcessTrusted and Automation through AEDeterminePermissionToAutomateTarget. Only when those are
granted (or cannot be read) does it confirm with one osascript probe. The result is cached for the
process, because a probe can pop a permission dialog, or hang until killed while a permission is
missing; nothing here ever retries in a loop. Every osascript call has a hard timeout of at most 5 s.

open_document() uses `open -a` (LaunchServices) and needs no permission. Importing this module has no
side effects.
"""
import ctypes
import glob
import os
import re
import subprocess
import sys
import threading

LIVE_BUNDLE_ID = "com.ableton.live"
SYSTEM_EVENTS_BUNDLE_ID = "com.apple.systemevents"
OSASCRIPT = "/usr/bin/osascript"
MAX_TIMEOUT = 5.0
PROBE_TIMEOUT = 4.0
ENV_SWITCH = "ABLETON_MCP_UI_AUTOMATION"

# AEDeterminePermissionToAutomateTarget results
NO_ERR, NOT_PERMITTED, WOULD_REQUIRE_CONSENT, PROC_NOT_FOUND = 0, -1743, -1744, -600

_AX_FRAMEWORK = "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
_CS_FRAMEWORK = "/System/Library/Frameworks/CoreServices.framework/CoreServices"
_SETTINGS = "System Settings > Privacy & Security"


class UIAutomationError(Exception):
    """A UI automation step failed. code follows the PRD's error codes (unsupported, timeout, live_error)."""

    def __init__(self, code, message, hint=None):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.hint = hint

    def __str__(self):
        return "{0} ({1})".format(self.message, self.hint) if self.hint else self.message


# ---------------------------------------------------------------------------
# Passive permission checks (never prompt)
# ---------------------------------------------------------------------------


def accessibility_trusted():
    """AXIsProcessTrusted() for this process (macOS attributes it to the host app); None if unknown."""
    try:
        library = ctypes.cdll.LoadLibrary(_AX_FRAMEWORK)
        library.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(library.AXIsProcessTrusted())
    except Exception:
        return None


def _fourcc(text):
    return int.from_bytes(text.encode("ascii"), "big")


class _AEDesc(ctypes.Structure):
    _fields_ = [("descriptorType", ctypes.c_uint32), ("dataHandle", ctypes.c_void_p)]


def automation_permission(bundle_id=SYSTEM_EVENTS_BUNDLE_ID):
    """Whether this process may send Apple Events to an app, asked without prompting the user.

    Returns NO_ERR (allowed), NOT_PERMITTED (denied), WOULD_REQUIRE_CONSENT (never asked) or
    PROC_NOT_FOUND (the app is not running), or None when the check itself is unavailable.
    """
    try:
        library = ctypes.cdll.LoadLibrary(_CS_FRAMEWORK)
        library.AECreateDesc.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_long, ctypes.POINTER(_AEDesc)]
        library.AECreateDesc.restype = ctypes.c_int16
        library.AEDeterminePermissionToAutomateTarget.argtypes = [ctypes.POINTER(_AEDesc), ctypes.c_uint32, ctypes.c_uint32, ctypes.c_bool]
        library.AEDeterminePermissionToAutomateTarget.restype = ctypes.c_int32
        library.AEDisposeDesc.argtypes = [ctypes.POINTER(_AEDesc)]
        library.AEDisposeDesc.restype = ctypes.c_int16
        target = _AEDesc()
        data = bundle_id.encode("utf-8")
        if library.AECreateDesc(_fourcc("bund"), data, len(data), ctypes.byref(target)) != 0:
            return None
        try:
            return int(library.AEDeterminePermissionToAutomateTarget(ctypes.byref(target), _fourcc("****"), _fourcc("****"), False))
        finally:
            library.AEDisposeDesc(ctypes.byref(target))
    except Exception:
        return None


def _launch_system_events():
    """Start System Events in the background through LaunchServices (no Apple Event, no prompt)."""
    try:
        subprocess.run(["open", "-g", "-j", "-b", SYSTEM_EVENTS_BUNDLE_ID], capture_output=True, timeout=2.0)
    except (OSError, subprocess.SubprocessError):
        pass


def _automation_after_launch(wait=1.5, step=0.1):
    import time
    _launch_system_events()
    deadline = time.monotonic() + wait
    result = automation_permission()
    while result == PROC_NOT_FOUND and time.monotonic() < deadline:
        time.sleep(step)
        result = automation_permission()
    return result


# ---------------------------------------------------------------------------
# Which app needs the permission
# ---------------------------------------------------------------------------


def app_bundle(command):
    """The .app bundle a process executable belongs to, ignoring framework-embedded Python.app."""
    match = re.match(r"^(.*?\.app)/Contents/MacOS/", command or "")
    if not match or ".framework/" in match.group(1):
        return None
    return match.group(1)


def host_app():
    """(name, bundle path) of the nearest application bundle among this process's ancestors.

    That app (Claude, Terminal, Cursor, ...) is the one macOS lists under Privacy & Security. Best
    effort: None when no bundle is found.
    """
    pid = os.getpid()
    for _ in range(32):
        try:
            output = subprocess.run(["ps", "-o", "ppid=,comm=", "-p", str(pid)], capture_output=True, text=True, timeout=2).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
        parts = output.split(None, 1)
        if len(parts) != 2:
            return None
        bundle = app_bundle(parts[1])
        if bundle:
            return os.path.basename(bundle)[:-4], bundle
        pid = int(parts[0])
        if pid <= 1:
            return None
    return None


def _who(host):
    return "{0} ({1})".format(host[0], host[1]) if host else "the app that runs the MCP server"


def _name(host):
    return host[0] if host else "the app that runs the MCP server (Claude, Terminal, ...)"


def fix_accessibility(host):
    path = " (use + to add {0} if it is not listed)".format(host[1]) if host else ""
    return "{0} > Accessibility: turn on {1}{2}. Then restart the MCP server.".format(_SETTINGS, _name(host), path)


def fix_automation(host):
    return "{0} > Automation > {1}: turn on System Events. Then restart the MCP server.".format(_SETTINGS, _name(host))


def fix_both(host):
    return "Allow {0} in {1} > Accessibility and in > Automation (System Events), answer any macOS prompt, then restart the MCP server.".format(_name(host), _SETTINGS)


# ---------------------------------------------------------------------------
# status() and require(): cached per process
# ---------------------------------------------------------------------------

_lock = threading.RLock()
_cached = None
_probed = False

PROBE_SCRIPT = 'tell application "System Events" to count (menu bar items of menu bar 1 of (first application process whose frontmost is true))'


def _result(available, detail, fix, state):
    return {"available": bool(available), "detail": detail, "fix": fix, "_state": state}


def _public(result):
    return dict((key, value) for key, value in result.items() if not key.startswith("_"))


def _evaluate():
    if sys.platform != "darwin":
        return _result(False, "UI automation is macOS-only", "Use bounce to render, and save or open sets in Live yourself.", "unsupported")
    switch = os.environ.get(ENV_SWITCH, "").strip().lower()
    if switch in ("0", "off", "false", "no", "disabled"):
        return _result(False, "Disabled by {0}={1}".format(ENV_SWITCH, os.environ.get(ENV_SWITCH)), "Unset {0} to enable it.".format(ENV_SWITCH), "disabled")
    if not os.path.exists(OSASCRIPT):
        return _result(False, "{0} is missing".format(OSASCRIPT), "UI automation needs macOS's osascript.", "unsupported")
    host = host_app()
    trusted = accessibility_trusted()
    if trusted is False:
        return _result(False, "Accessibility access is off for {0}".format(_who(host)), fix_accessibility(host), "denied")
    permission = automation_permission()
    if permission == PROC_NOT_FOUND:
        permission = _automation_after_launch()
    if permission == NOT_PERMITTED:
        return _result(False, "{0} is not allowed to control System Events".format(_who(host)), fix_automation(host), "denied")
    if permission == WOULD_REQUIRE_CONSENT:
        return _result(
            False,
            "macOS has not yet asked whether {0} may control System Events".format(_who(host)),
            "The first save_set, new_set or export_audio call shows that macOS prompt once; click OK. Or allow it in {0} > Automation.".format(_SETTINGS),
            "consent",
        )
    return _probe(host)


def _probe(host):
    """The one osascript probe per process; bounded by PROBE_TIMEOUT."""
    global _probed
    _probed = True
    try:
        _run(PROBE_SCRIPT, PROBE_TIMEOUT)
    except UIAutomationError as error:
        if error.code == "timeout":
            return _result(False, "osascript to System Events did not answer within {0:g}s; macOS is probably waiting on a permission prompt for {1}".format(PROBE_TIMEOUT, _who(host)), fix_both(host), "timeout")
        kind = permission_problem(error.message)
        if kind == "accessibility":
            return _result(False, "Accessibility access is off for {0}: {1}".format(_who(host), error.message), fix_accessibility(host), "denied")
        if kind == "automation":
            return _result(False, "{0} is not allowed to control System Events: {1}".format(_who(host), error.message), fix_automation(host), "denied")
        return _result(False, "osascript failed: {0}".format(error.message), fix_both(host), "error")
    return _result(True, "Ready: {0} may control System Events and use Accessibility".format(_who(host)), "", "granted")


def status(refresh=False):
    """{"available": bool, "detail": str, "fix": str} for UI automation, cached for the process.

    Never prompts while macOS can answer passively. Bounded: about 0.2 s for the passive checks, at most
    3.5 s more to start System Events when it is not running, and PROBE_TIMEOUT for the one osascript
    probe (only when the passive checks pass or cannot be read). refresh=True re-evaluates once.
    """
    global _cached
    with _lock:
        if _cached is None or refresh:
            _cached = _evaluate()
        return _public(_cached)


def require():
    """Raise UIAutomationError("unsupported", detail, fix) unless UI automation can run.

    If macOS has never asked for the Automation permission, this runs the single probe of the
    process, which shows macOS's prompt (still bounded by PROBE_TIMEOUT).
    """
    global _cached
    with _lock:
        status()
        if _cached.get("_state") == "consent" and not _probed:
            _cached = _probe(host_app())
        current = _public(_cached)
    if not current["available"]:
        raise UIAutomationError("unsupported", "UI automation is unavailable: " + current["detail"], current["fix"])


def _mark_unavailable(detail, fix, state="denied"):
    """Remember a permission failure seen during a real run, so later calls fail fast."""
    global _cached
    with _lock:
        _cached = _result(False, detail, fix, state)


def reset():
    """Forget the cached status (tests)."""
    global _cached, _probed
    with _lock:
        _cached = None
        _probed = False


# ---------------------------------------------------------------------------
# Running AppleScript
# ---------------------------------------------------------------------------


def permission_problem(message):
    """'accessibility', 'automation' or None for an osascript error message."""
    text = str(message or "").lower()
    if "-1743" in text or "not authorized to send apple events" in text or "not allowed to send apple events" in text:
        return "automation"
    if "assistive" in text or "-25211" in text or "not allowed to send keystrokes" in text or "(1002)" in text or "accessibility" in text:
        return "accessibility"
    return None


def _clean_error(stderr):
    text = " ".join(str(stderr or "").split())
    return re.sub(r"^\d+:\d+:\s*", "", text) or "osascript failed"


def _run(script, timeout):
    timeout = min(float(timeout), MAX_TIMEOUT)
    try:
        completed = subprocess.run([OSASCRIPT, "-"], input=script, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise UIAutomationError("timeout", "osascript did not finish within {0:g}s".format(timeout))
    except OSError as error:
        raise UIAutomationError("unsupported", "Cannot run osascript: {0}".format(error))
    if completed.returncode != 0:
        raise UIAutomationError("live_error", _clean_error(completed.stderr))
    return completed.stdout.strip()


def run_script(script, timeout=MAX_TIMEOUT):
    """Run AppleScript source with a hard timeout (at most 5 s); returns its output.

    A permission failure marks UI automation unavailable for the rest of the process.
    """
    try:
        return _run(script, timeout)
    except UIAutomationError as error:
        kind = permission_problem(error.message)
        if kind is not None:
            host = host_app()
            fix = fix_accessibility(host) if kind == "accessibility" else fix_automation(host)
            _mark_unavailable(error.message, fix)
            raise UIAutomationError("unsupported", "UI automation is not permitted: " + error.message, fix)
        if error.code == "timeout":
            error.hint = "Live may be showing a dialog or busy; check get_status"
        raise


# ---------------------------------------------------------------------------
# AppleScript construction (pure; unit-tested)
# ---------------------------------------------------------------------------

_MODIFIERS = {
    "command": "command down", "cmd": "command down", "shift": "shift down", "option": "option down",
    "alt": "option down", "control": "control down", "ctrl": "control down",
}
_KEY_CODES = {"return": 36, "enter": 76, "escape": 53, "tab": 48, "delete": 51}

LIVE_TEMPLATE = """tell application "System Events"
\tset liveProcess to first application process whose bundle identifier is {bundle}
\tset frontmost of liveProcess to true
\trepeat 20 times
\t\tif frontmost of liveProcess then exit repeat
\t\tdelay 0.05
\tend repeat
\ttell liveProcess
{body}
\tend tell
end tell
return "ok\""""

WAIT_FOR_FILE_PANEL = """set panel to missing value
repeat 30 times
\ttry
\t\tif exists sheet 1 of window 1 then
\t\t\tset panel to sheet 1 of window 1
\t\telse
\t\t\tset dialogs to (windows whose subrole is "AXDialog")
\t\t\tif (count of dialogs) > 0 then set panel to item 1 of dialogs
\t\tend if
\tend try
\tif panel is not missing value then exit repeat
\tdelay 0.1
end repeat
if panel is missing value then error "No file panel appeared in Live" number 1001"""


def applescript_string(text):
    """An AppleScript string literal; rejects control characters, which keystroke cannot type safely."""
    text = str(text)
    if any(ord(character) < 32 for character in text):
        raise ValueError("Text for AppleScript must not contain control characters: {0!r}".format(text))
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def key_statement(key, modifiers=()):
    """`keystroke "s" using {command down}` or `key code 36` for named keys."""
    using = ""
    if modifiers:
        try:
            using = " using {" + ", ".join(_MODIFIERS[item.lower()] for item in modifiers) + "}"
        except KeyError as error:
            raise ValueError("Unknown modifier {0}; use {1}".format(error, ", ".join(sorted(_MODIFIERS))))
    if key.lower() in _KEY_CODES:
        return "key code {0}{1}".format(_KEY_CODES[key.lower()], using)
    return "keystroke {0}{1}".format(applescript_string(key), using)


def live_script(*statements):
    """A script that brings Live to the front and runs `statements` inside its process."""
    lines = []
    for statement in statements:
        lines += ["\t\t" + line for line in statement.splitlines()]
    return LIVE_TEMPLATE.format(bundle=applescript_string(LIVE_BUNDLE_ID), body="\n".join(lines))


def file_panel_statements(folder, name):
    """Fill a native save panel: file name, Go to Folder (Cmd+Shift+G) with the folder, then Save."""
    return [
        key_statement("a", ["command"]),
        key_statement(name),
        "delay 0.2",
        key_statement("g", ["command", "shift"]),
        "delay 0.6",
        key_statement(folder),
        "delay 0.4",
        key_statement("return"),
        "delay 0.6",
        key_statement("return"),
    ]


# ---------------------------------------------------------------------------
# Live actions
# ---------------------------------------------------------------------------


def save():
    """File > Save Live Set (Cmd+S)."""
    require()
    return run_script(live_script(key_statement("s", ["command"])))


def save_as(folder, name):
    """File > Save Live Set As (Cmd+Shift+S) into folder/name.als through the native panel."""
    require()
    run_script(live_script(key_statement("s", ["command", "shift"]), WAIT_FOR_FILE_PANEL))
    return run_script(live_script(*file_panel_statements(folder, name)))


def new_set():
    """File > New Live Set (Cmd+N). Live may then ask whether to save the current set."""
    require()
    return run_script(live_script(key_statement("n", ["command"])))


def export(folder, name):
    """EXPERIMENTAL: File > Export Audio/Video (Cmd+Shift+R), confirm with Return, then the save panel."""
    require()
    run_script(live_script(key_statement("r", ["command", "shift"]), "delay 1.5", key_statement("return")))
    run_script(live_script(WAIT_FOR_FILE_PANEL))
    return run_script(live_script(*file_panel_statements(folder, name)))


# ---------------------------------------------------------------------------
# Opening sets through LaunchServices (no permission needed)
# ---------------------------------------------------------------------------

_LIVE_EXECUTABLE = re.compile(r"^(/.*?\.app)/Contents/MacOS/Live$")


def live_app_path():
    """Bundle path of the running Live, else the newest Live in /Applications; None if absent."""
    try:
        output = subprocess.run(["ps", "-axo", "comm="], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        output = ""
    for line in output.splitlines():
        match = _LIVE_EXECUTABLE.match(line.strip())
        if match and "Ableton" in match.group(1):
            return match.group(1)
    candidates = glob.glob("/Applications/Ableton Live*.app") + glob.glob(os.path.expanduser("~/Applications/Ableton Live*.app"))
    return sorted(candidates)[-1] if candidates else None


def open_document(path):
    """Open a file in the running Live with `open -a` (Live then loads it and may ask to save)."""
    app = live_app_path()
    if app is None:
        raise UIAutomationError("unsupported", "Ableton Live was not found (not running and not in /Applications)")
    try:
        completed = subprocess.run(["open", "-a", app, path], capture_output=True, text=True, timeout=MAX_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise UIAutomationError("timeout", "`open -a` did not return within {0:g}s".format(MAX_TIMEOUT))
    except OSError as error:
        raise UIAutomationError("unsupported", "Cannot run `open`: {0}".format(error))
    if completed.returncode != 0:
        raise UIAutomationError("live_error", "open failed: {0}".format(_clean_error(completed.stderr)))
    return app
