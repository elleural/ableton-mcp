"""WS-A: status, overview, undo/redo and dialogs (docs/PRD.md section 7.1). Owned by workstream A."""
import os
import shutil

from mcp.server.mcpserver.exceptions import ToolError

from .. import __version__, ui_automation
from ..app import call, tool

# Where Homebrew and friends put ffmpeg when the MCP client starts the server with a minimal PATH.
_EXTRA_BIN_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin")


def find_executable(name):
    """Path of an executable on PATH or in the usual Homebrew locations; None if absent."""
    path = shutil.which(name)
    if path:
        return path
    for directory in _EXTRA_BIN_DIRS:
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def capabilities():
    return {
        "ffmpeg": find_executable("ffmpeg"),
        "ffprobe": find_executable("ffprobe"),
        "ui_automation": ui_automation.status(),
    }


@tool(read_only=True)
def get_status() -> dict:
    """Start here. Connection, Live and Remote Script versions, the open set (name, path), transport
    (playing, position, tempo, loop), any open Live dialog with its message, active background jobs,
    and capabilities: ffmpeg (needed by analyze_audio and create_release) and macOS UI automation
    (needed by save_set, new_set and export_audio; `fix` says how to enable it).

    When Live is unreachable it still answers, with connected: false and how to fix it. If `dialog`
    is set, Live is waiting for an answer: respond_to_dialog.
    """
    out = {"connected": True, "server": {"version": __version__}}
    try:
        out.update(call("get_status"))
    except ToolError as error:
        out["connected"] = False
        out["error"] = str(error)
    if out.get("dialog"):
        out["hint"] = "Live is showing a dialog and waits for an answer: respond_to_dialog(button)"
    out["capabilities"] = capabilities()
    return out


@tool(read_only=True)
def get_song_overview(detail: bool = False) -> dict:
    """One-call map of the project: tempo, meter, key and scale, swing, loop, song length; every track
    (index, name, kind, colour, mute/solo/arm, devices, non-empty Session slots with name and length,
    arrangement clip count and extent); returns and master; scenes (name, tempo, signature, empty);
    locators; the selection. Times come as beats plus "bar.beat.sixteenth".

    detail=True adds every set_song setting, mixer levels (dB), pan and sends, device classes and
    on/off, clip colours and arrangement clip lists. Use get_track or get_notes for more.
    """
    return call("get_song_overview", detail=detail)


@tool()
def undo(steps: int = 1) -> dict:
    """Undo the last `steps` actions in Live (1..100). Every AbletonMCP call that changes the set is one
    undo step, so undo() reverts the previous call. Returns how many steps were undone plus can_undo and
    can_redo. Live's history is shared with the user's own edits in Live.
    """
    return call("undo", steps=steps)


@tool()
def redo(steps: int = 1) -> dict:
    """Redo `steps` actions previously undone with undo (1..100). Returns how many were redone plus
    can_undo and can_redo. Any new change clears the redo history.
    """
    return call("redo", steps=steps)


@tool(destructive=True)
def respond_to_dialog(button: int | str) -> dict:
    """Press a button on the dialog Live is showing (get_status reports its message and button count).

    button: an index (0 = first button), or a name where Live's layout is known: "ok" on one-button
    dialogs; "save", "dont_save" or "cancel" on Live's save-changes prompt. Destructive: "dont_save"
    discards unsaved work, so confirm with the user first.
    """
    return call("respond_to_dialog", button=button)
