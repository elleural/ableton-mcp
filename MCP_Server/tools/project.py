"""WS-A: project lifecycle (save, new, open) and the experimental offline export (PRD 7.1, 7.9).

Owned by workstream A. Live's API cannot save, create sets or export, so:
- open_set opens the file through macOS (`open -a`), which needs no permission;
- save_set, new_set and export_audio drive Live's menus with UI automation (MCP_Server/ui_automation.py),
  which needs Accessibility and Automation permission for the app running the MCP server.
Results are verified through Live's API (Song.file_path, the open document) or the file system.
"""
import os
import time as _time

from mcp.server.mcpserver.exceptions import ToolError

from .. import ui_automation
from ..app import call, tool

POLL_INTERVAL = 0.25
STATUS_TIMEOUT = 3.0
OPEN_TIMEOUT = 90.0
NEW_TIMEOUT = 30.0
SAVE_TIMEOUT = 30.0
EXPORT_TIMEOUT = 900.0
AUDIO_EXTENSIONS = (".wav", ".aif", ".aiff", ".flac", ".mp3")


def _fail(message, hint=None):
    raise ToolError("{0} ({1})".format(message, hint) if hint else message)


def _ui(step, *args):
    """Run a ui_automation step; its errors become tool errors that carry the fix."""
    try:
        return step(*args)
    except ui_automation.UIAutomationError as error:
        _fail(error.message, error.hint)


def _poll_status():
    """get_status from Live, or None while Live is busy (loading, rendering, showing a modal dialog)."""
    try:
        return call("get_status", timeout=STATUS_TIMEOUT)
    except ToolError:
        return None


def _live_status():
    status = _poll_status()
    if status is None:
        _fail("Ableton Live is not answering", "Check get_status: Live may be busy, loading or not running")
    return status


def _no_dialog(status):
    dialog = status.get("dialog")
    if dialog:
        _fail("Live is showing a dialog: {0!r} ({1} buttons)".format(dialog.get("message"), dialog.get("buttons")),
              "Answer it first with respond_to_dialog, or ask the user")


def is_save_prompt(message):
    text = str(message or "").lower()
    return "save" in text and ("change" in text or "before" in text)


def normalize_path(path, extensions=(".als",), default_extension=".als"):
    """Absolute path with ~ expanded; appends default_extension when the path has no allowed extension."""
    if not isinstance(path, str) or not path.strip():
        _fail("path must be a file path such as '~/Music/My Song.als'")
    text = os.path.abspath(os.path.expanduser(path.strip()))
    if os.path.splitext(text)[1].lower() not in extensions:
        text += default_extension
    return text


def same_file(first, second):
    try:
        return os.path.samefile(first, second)
    except OSError:
        return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))


def saved_as(new_path, folder, name):
    """True when Live's file_path is name.als in folder, or in the "<name> Project" folder Live creates."""
    if not new_path:
        return False
    directory, base = os.path.split(new_path)
    if base.lower() != (name + ".als").lower():
        return False
    return any(same_file(directory, candidate) for candidate in (folder, os.path.join(folder, name + " Project")) if os.path.isdir(candidate))


def await_document(before, discard_unsaved=False, timeout=OPEN_TIMEOUT, expect_path=None):
    """Poll Live until a different set is open, answering Live's save prompt on the way.

    While Live loads it may be busy or restart its control surface, so failed polls just continue.
    With discard_unsaved=False a save prompt is left open (nothing is discarded) and reported.
    """
    deadline = _time.monotonic() + timeout
    pressed = False
    while _time.monotonic() < deadline:
        status = _poll_status()
        if status is not None:
            current = status.get("set", {})
            changed = current.get("document") != before["set"].get("document")
            if expect_path and current.get("path") and same_file(current["path"], expect_path):
                changed = True
            if changed:
                return status
            dialog = status.get("dialog")
            if dialog:
                if not is_save_prompt(dialog.get("message")):
                    _fail("Live shows a dialog: {0!r} ({1} buttons)".format(dialog.get("message"), dialog.get("buttons")),
                          "Answer it with respond_to_dialog, then check get_status")
                if not discard_unsaved:
                    _fail("Live asks {0!r}: the current set has unsaved changes. Nothing was discarded and the prompt is still open".format(dialog.get("message")),
                          "Ask the user, then respond_to_dialog('save' / 'dont_save' / 'cancel'); or save_set first; or retry with discard_unsaved=True")
                if not pressed:
                    call("respond_to_dialog", button="dont_save")
                    pressed = True
        _time.sleep(POLL_INTERVAL)
    _fail("Live did not switch sets within {0:g}s".format(timeout), "Check get_status: Live may still be loading or showing a dialog")


def _set_summary(status):
    return {"set": status.get("set"), "transport": status.get("transport"), "dialog": status.get("dialog")}


@tool(destructive=True)
def open_set(path: str, discard_unsaved: bool = False) -> dict:
    """Open a Live Set (.als) in the running Live, replacing the current set. No UI permission needed.

    If the current set has unsaved changes Live asks to save them: with discard_unsaved=False (default)
    nothing is discarded, the prompt stays open and the call fails with what to do; discard_unsaved=True
    answers "Don't Save". Destructive with discard_unsaved: confirm with the user first. Waits until the
    set has loaded and returns it; then call get_song_overview.
    """
    target = normalize_path(path)
    if not os.path.isfile(target):
        _fail("No Live Set at {0}".format(target), "Pass the path of an existing .als file")
    before = _live_status()
    _no_dialog(before)
    current = before["set"].get("path")
    if current and same_file(current, target):
        return dict({"opened": False, "already_open": True}, **_set_summary(before))
    _ui(ui_automation.open_document, target)
    status = await_document(before, discard_unsaved, OPEN_TIMEOUT, expect_path=target)
    return dict({"opened": True}, **_set_summary(status))


@tool(destructive=True)
def new_set(discard_unsaved: bool = False) -> dict:
    """[UI automation] Start a new empty Live Set (File > New Live Set), replacing the current one.

    Unsaved changes are refused unless discard_unsaved=True (then Live's save prompt is answered
    "Don't Save"). Needs macOS UI automation: get_status shows whether it is available and how to enable
    it. Destructive with discard_unsaved: confirm with the user first.
    """
    before = _live_status()
    _no_dialog(before)
    _ui(ui_automation.require)
    _ui(ui_automation.new_set)
    status = await_document(before, discard_unsaved, NEW_TIMEOUT)
    return dict({"created": True}, **_set_summary(status))


def _await_mtime(path, previous, timeout):
    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        try:
            if os.path.getmtime(path) > previous:
                return True
        except OSError:
            pass
        _time.sleep(POLL_INTERVAL)
    return False


def _await_saved_as(folder, name, timeout):
    deadline = _time.monotonic() + timeout
    status = None
    while _time.monotonic() < deadline:
        status = _poll_status()
        if status is not None and saved_as(status.get("set", {}).get("path"), folder, name):
            return status
        _time.sleep(POLL_INTERVAL)
    return status


@tool(destructive=True)
def save_set(path: str | None = None) -> dict:
    """[UI automation] Save the current Live Set; with `path`, save it as a new file ("~/Music/My Song.als").

    Without path the set must already have a file. Save-as never overwrites an existing file; Live may
    put the set in a new "<name> Project" folder. Verified through Live's file path or the file's
    modification time. Needs macOS UI automation (see get_status).
    """
    before = _live_status()
    _no_dialog(before)
    current = before["set"].get("path")
    if path is None:
        if not current:
            _fail("This set has never been saved, so it has no file yet", "Pass a path, e.g. save_set(path='~/Music/My Song.als')")
        target = current
    else:
        target = normalize_path(path)
    _ui(ui_automation.require)
    if current and same_file(target, current):
        previous = os.path.getmtime(current) if os.path.exists(current) else 0.0
        _ui(ui_automation.save)
        if not _await_mtime(current, previous, SAVE_TIMEOUT):
            _fail("Live did not write {0} within {1:g}s".format(current, SAVE_TIMEOUT), "Check get_status for a dialog; Live may also skip saving an unchanged set")
        return {"saved": True, "path": current}
    if os.path.exists(target):
        _fail("{0} already exists".format(target), "Choose another path: save_set never overwrites another file")
    folder, filename = os.path.split(target)
    name = os.path.splitext(filename)[0]
    os.makedirs(folder, exist_ok=True)
    _ui(ui_automation.save_as, folder, name)
    status = _await_saved_as(folder, name, SAVE_TIMEOUT)
    saved = (status or {}).get("set", {}).get("path")
    if not saved_as(saved, folder, name):
        _fail("Live did not report the set as saved at {0} within {1:g}s (its path is {2!r})".format(target, SAVE_TIMEOUT, saved),
              "Check get_status for a dialog, and whether the file was written")
    out = {"saved": True, "path": saved}
    if not same_file(saved, target):
        out["requested"] = target
    return out


# ---------------------------------------------------------------------------
# Experimental offline export
# ---------------------------------------------------------------------------


def find_export(folder, stem, since):
    """The newest audio file named stem.* in folder written after `since`, or None."""
    best = None
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    for filename in names:
        base, extension = os.path.splitext(filename)
        if base != stem or extension.lower() not in AUDIO_EXTENSIONS:
            continue
        candidate = os.path.join(folder, filename)
        try:
            modified = os.path.getmtime(candidate)
        except OSError:
            continue
        if modified >= since and (best is None or modified > best[0]):
            best = (modified, candidate)
    return best[1] if best else None


def await_export(folder, stem, since, timeout=EXPORT_TIMEOUT, settle=1.0):
    """Wait for the rendered file to appear and stop growing; returns (path, bytes)."""
    deadline = _time.monotonic() + timeout
    last_size, stable_since = None, None
    while _time.monotonic() < deadline:
        found = find_export(folder, stem, since)
        if found:
            size = os.path.getsize(found)
            if size > 0 and size == last_size:
                if stable_since is None:
                    stable_since = _time.monotonic()
                if _time.monotonic() - stable_since >= settle:
                    return found, size
            else:
                stable_since = None
            last_size = size
        _time.sleep(POLL_INTERVAL)
    _fail("No finished export named {0}.* appeared in {1} within {2:g}s".format(stem, folder, timeout),
          "Check get_status for a dialog; Live's export settings (format) apply")


@tool()
def export_audio(path: str, start: float | str, end: float | str) -> dict:
    """[UI automation, EXPERIMENTAL] Render the arrangement from `start` to `end` (beats or
    "bar.beat.sixteenth") with Live's own offline File > Export Audio/Video, to `path` (".wav").

    Sets the arrangement loop to the range (Live exports the loop brace) and restores it afterwards. The
    file format and rendered track follow the Export dialog's last settings. Never overwrites a file.
    Prefer bounce, which needs no UI permission. Needs macOS UI automation (see get_status).
    """
    target = normalize_path(path, AUDIO_EXTENSIONS, ".wav")
    if os.path.exists(target):
        _fail("{0} already exists".format(target), "Choose another path: export_audio never overwrites a file")
    folder, filename = os.path.split(target)
    stem = os.path.splitext(filename)[0]
    if not os.path.isdir(folder):
        _fail("Folder {0} does not exist".format(folder))
    _ui(ui_automation.require)
    before = _live_status()
    _no_dialog(before)
    loop = before["transport"]["loop"]
    call("set_song", loop_start=start, loop_end=end)
    since = _time.time() - 1.0
    try:
        _ui(ui_automation.export, folder, stem)
        found, size = await_export(folder, stem, since)
    finally:
        try:
            call("set_song", loop_start=loop["start"]["beats"], loop_length=loop["length"], loop=loop["on"])
        except ToolError:
            pass
    out = {"exported": True, "path": found, "bytes": size, "experimental": True}
    if not same_file(found, target):
        out["requested"] = target
    return out
