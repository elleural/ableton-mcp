"""`ableton-mcp` command line.

    ableton-mcp                 run the MCP server over stdio (what MCP clients launch)
    ableton-mcp install         link (or copy) the Remote Script into Live's User Library
    ableton-mcp doctor          check every link in the chain and say how to fix what is broken
"""
import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

REMOTE_SCRIPT_NAME = "AbletonMCP"
PORT = int(os.environ.get("ABLETON_MCP_PORT", "9877"))


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


def remote_script_source():
    """The Remote Script folder shipped next to this package (repo checkout or installed wheel)."""
    return Path(__file__).resolve().parent.parent / "AbletonMCP_Remote_Script"


def _preferences_dirs():
    if platform.system() == "Darwin":
        base = Path.home() / "Library" / "Preferences" / "Ableton"
    else:
        base = Path(os.environ.get("APPDATA", Path.home())) / "Ableton"
    if not base.is_dir():
        return []
    return sorted((path for path in base.glob("Live *") if path.is_dir()), key=lambda path: _version_key(path.name), reverse=True)


def _version_key(name):
    return tuple(int(part) for part in re.findall(r"\d+", name))


def user_library():
    """Live's User Library: $ABLETON_USER_LIBRARY, the location in Library.cfg, or the OS default."""
    override = os.environ.get("ABLETON_USER_LIBRARY")
    if override:
        return Path(override).expanduser()
    for prefs in _preferences_dirs():
        config = prefs / "Library.cfg"
        if config.is_file():
            text = config.read_text(errors="ignore")
            block = re.search(r"<UserLibrary>.*?</UserLibrary>", text, re.S)
            if block:
                location = re.search(r'<ProjectLocation Value="([^"]*)"', block.group(0))
                name = re.search(r'<ProjectName Value="([^"]*)"', block.group(0))
                if location and location.group(1):
                    return Path(location.group(1)) / (name.group(1) if name else "User Library")
            break
    documents = Path.home() / ("Music" if platform.system() == "Darwin" else "Documents")
    return documents / "Ableton" / "User Library"


def installed_script_path():
    return user_library() / "Remote Scripts" / REMOTE_SCRIPT_NAME


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def install(copy=False, force=False):
    source = remote_script_source()
    if not (source / "__init__.py").is_file():
        print("Remote Script source not found at {0}".format(source))
        return 2
    target = installed_script_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    use_link = not copy and (source.parent / ".git").exists()

    if target.is_symlink():
        if target.resolve() == source.resolve() and use_link:
            print("Already installed: {0} -> {1}".format(target, source))
            return _next_steps(already=True)
        target.unlink()
    elif target.exists():
        if not force:
            print("{0} already exists and is not a link to this checkout. Re-run with --force to replace it "
                  "(the old folder is kept as a backup).".format(target))
            return 1
        backup = target.with_name("{0}.backup-{1}".format(REMOTE_SCRIPT_NAME, time.strftime("%Y%m%d-%H%M%S")))
        target.rename(backup)
        print("Moved the previous Remote Script to {0}".format(backup))

    if use_link:
        target.symlink_to(source, target_is_directory=True)
        print("Linked {0} -> {1}".format(target, source))
    else:
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print("Copied the Remote Script to {0}".format(target))
    return _next_steps(already=False)


def _next_steps(already):
    print("")
    if not already:
        print("Next: restart Ableton Live (it only discovers Remote Scripts at launch), then")
    else:
        print("If Live does not list it yet, restart Live, then")
    print("  Settings > Link, Tempo & MIDI > Control Surface: choose 'AbletonMCP' (Input and Output: None).")
    print("Run `ableton-mcp doctor` to verify the whole chain.")
    return 0


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def _check(results, label, ok, detail="", fix=""):
    results.append({"check": label, "ok": bool(ok), "detail": detail, "fix": "" if ok else fix})
    return ok


def _live_running():
    if platform.system() == "Darwin":
        output = subprocess.run(["pgrep", "-fl", "Ableton Live"], capture_output=True, text=True).stdout
        return "Live" in output, output.strip().splitlines()[0] if output.strip() else ""
    output = subprocess.run(["tasklist"], capture_output=True, text=True).stdout
    return "Ableton" in output, ""


def doctor(as_json=False):
    from . import __version__
    from .connection import AbletonConnection, AbletonError

    results = []
    _check(results, "AbletonMCP server package", True, "version {0}, Python {1}".format(__version__, sys.version.split()[0]))

    running, detail = _live_running()
    _check(results, "Ableton Live running", running, detail, "Start Ableton Live 12.")

    target = installed_script_path()
    source = remote_script_source()
    if target.is_symlink():
        linked = target.resolve() == source.resolve()
        _check(results, "Remote Script installed", True, "{0} -> {1}".format(target, target.resolve()))
        _check(results, "Remote Script is this checkout", linked, "",
               "The installed link points elsewhere; run `ableton-mcp install` from the checkout you want Live to use.")
    else:
        _check(results, "Remote Script installed", target.exists(), str(target), "Run `ableton-mcp install`, then restart Live.")

    reachable = False
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=2):
            reachable = True
    except OSError:
        pass
    _check(results, "Remote Script listening on port {0}".format(PORT), reachable, "",
           "In Live: Settings > Link, Tempo & MIDI > Control Surface = AbletonMCP. If it is not listed, restart Live.")

    if reachable:
        try:
            ping = AbletonConnection().send_command("ping", timeout=10)
            _check(results, "Remote Script responds", True, "script {0}, Live {1}, Python {2}, {3} commands".format(
                ping.get("script_version"), ping.get("live_version"), ping.get("python_version"), ping.get("command_count")))
            failed = ping.get("handlers_failed") or []
            _check(results, "All handler modules loaded", not failed, ", ".join(failed),
                   "Call reload_remote_script (or `ableton-mcp-debug send get_commands '{\"include_failures\": true}'`) to see the import errors.")
        except AbletonError as error:
            _check(results, "Remote Script responds", False, str(error),
                   "An older AbletonMCP Remote Script may be loaded; run `ableton-mcp install --force` and restart Live.")

    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        _check(results, "{0} available (analysis and release)".format(tool), path, path or "",
               "Install ffmpeg (macOS: `brew install ffmpeg`) to enable analyze_audio and create_release.")

    try:
        from . import ui_automation
        status = ui_automation.status() if hasattr(ui_automation, "status") else None
    except Exception as error:  # Optional feature: never fail the doctor on it.
        status = {"available": False, "detail": str(error)}
    if status is not None:
        _check(results, "UI automation (optional: save/new/export via menus)", status.get("available"), status.get("detail", ""),
               status.get("fix", "Grant the app running the MCP server Automation (System Events) and Accessibility access "
                              "in System Settings > Privacy & Security."))

    claude = shutil.which("claude")
    if claude:
        output = subprocess.run([claude, "mcp", "get", "ableton"], capture_output=True, text=True, timeout=30)
        registered = output.returncode == 0
        _check(results, "Registered with Claude Code", registered, "", "Run: claude mcp add --scope user ableton -- uv run --directory {0} ableton-mcp".format(source.parent))

    if as_json:
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            mark = "OK " if result["ok"] else "!! "
            line = "{0} {1}".format(mark, result["check"])
            if result["detail"]:
                line += ": " + result["detail"]
            print(line)
            if result["fix"]:
                print("      fix: " + result["fix"])
    optional = ("ffmpeg", "ffprobe", "UI automation", "Claude Code")
    critical = [result for result in results if not result["ok"] and not result["check"].startswith(optional)]
    return 1 if critical else 0


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ableton-mcp", description="Ableton Live for AI agents over MCP")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Run the MCP server over stdio (the default)")
    install_parser = sub.add_parser("install", help="Install the Remote Script into Live's User Library")
    install_parser.add_argument("--copy", action="store_true", help="Copy instead of linking to this checkout")
    install_parser.add_argument("--force", action="store_true", help="Replace an existing AbletonMCP Remote Script (kept as a backup)")
    doctor_parser = sub.add_parser("doctor", help="Diagnose the Live / Remote Script / MCP chain")
    doctor_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "install":
        return install(copy=args.copy, force=args.force)
    if args.command == "doctor":
        return doctor(as_json=args.json)
    from .server import main as serve
    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
