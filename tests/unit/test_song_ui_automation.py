"""Unit tests for MCP_Server/ui_automation.py. Every subprocess and permission check is mocked:
no osascript ever runs, so no macOS permission prompt can appear."""
import subprocess

import pytest

from MCP_Server import ui_automation as ui

HOST = ("Claude", "/Applications/Claude.app")


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """Fresh cache, macOS, no env switch, and a tripwire on any real subprocess."""
    ui.reset()
    monkeypatch.setattr(ui.sys, "platform", "darwin")
    monkeypatch.delenv(ui.ENV_SWITCH, raising=False)
    monkeypatch.setattr(ui.os.path, "exists", lambda path: True if path == ui.OSASCRIPT else _exists(path))
    monkeypatch.setattr(ui, "host_app", lambda: HOST)

    def tripwire(*args, **kwargs):
        raise AssertionError("unexpected subprocess: {0}".format(args))

    monkeypatch.setattr(ui.subprocess, "run", tripwire)
    yield
    ui.reset()


_exists = ui.os.path.exists


class Probe(object):
    """Stands in for ui._run (the osascript runner)."""

    def __init__(self, outcome="1"):
        self.outcome = outcome
        self.scripts = []

    def __call__(self, script, timeout):
        self.scripts.append((script, timeout))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def permissions(monkeypatch, trusted, automation, probe=None):
    monkeypatch.setattr(ui, "accessibility_trusted", lambda: trusted)
    monkeypatch.setattr(ui, "automation_permission", lambda bundle_id=ui.SYSTEM_EVENTS_BUNDLE_ID: automation)
    probe = probe or Probe()
    monkeypatch.setattr(ui, "_run", probe)
    return probe


# ---------------------------------------------------------------------------
# status() / require()
# ---------------------------------------------------------------------------


def test_accessibility_off_is_decided_without_osascript(monkeypatch):
    probe = permissions(monkeypatch, False, ui.NO_ERR)
    status = ui.status()
    assert status["available"] is False and set(status) == {"available", "detail", "fix"}
    assert "Accessibility" in status["detail"] and "Claude" in status["detail"]
    assert "Privacy & Security > Accessibility" in status["fix"] and "/Applications/Claude.app" in status["fix"]
    assert probe.scripts == []


def test_automation_denied(monkeypatch):
    probe = permissions(monkeypatch, True, ui.NOT_PERMITTED)
    status = ui.status()
    assert not status["available"] and "System Events" in status["detail"] and "Automation" in status["fix"]
    assert probe.scripts == []


def test_granted_permissions_are_confirmed_by_one_probe_and_cached(monkeypatch):
    probe = permissions(monkeypatch, True, ui.NO_ERR)
    assert ui.status()["available"] is True
    assert ui.status()["available"] is True
    ui.require()
    assert len(probe.scripts) == 1 and probe.scripts[0][1] <= ui.MAX_TIMEOUT
    assert "System Events" in probe.scripts[0][0]


def test_probe_timeout_is_cached_as_unavailable(monkeypatch):
    probe = permissions(monkeypatch, None, None, Probe(ui.UIAutomationError("timeout", "osascript did not finish within 4s")))
    status = ui.status()
    assert not status["available"] and "did not answer" in status["detail"]
    with pytest.raises(ui.UIAutomationError) as error:
        ui.require()
    assert error.value.code == "unsupported" and error.value.hint == status["fix"]
    assert len(probe.scripts) == 1  # never retried


def test_consent_prompt_is_shown_once_by_require_not_by_status(monkeypatch):
    probe = permissions(monkeypatch, True, ui.WOULD_REQUIRE_CONSENT, Probe(ui.UIAutomationError("timeout", "slow")))
    status = ui.status()
    assert not status["available"] and "not yet asked" in status["detail"] and probe.scripts == []
    for _ in range(3):
        with pytest.raises(ui.UIAutomationError):
            ui.require()
    assert len(probe.scripts) == 1


def test_consent_granted_during_the_prompt(monkeypatch):
    permissions(monkeypatch, True, ui.WOULD_REQUIRE_CONSENT)
    ui.require()
    assert ui.status()["available"] is True


def test_system_events_not_running_is_started_quietly(monkeypatch):
    answers = [ui.PROC_NOT_FOUND, ui.PROC_NOT_FOUND, ui.NOT_PERMITTED]
    launched = []
    monkeypatch.setattr(ui, "accessibility_trusted", lambda: True)
    monkeypatch.setattr(ui, "automation_permission", lambda bundle_id=ui.SYSTEM_EVENTS_BUNDLE_ID: answers.pop(0))
    monkeypatch.setattr(ui, "_launch_system_events", lambda: launched.append(True))
    monkeypatch.setattr(ui, "_run", Probe())
    status = ui.status()
    assert launched == [True] and not status["available"] and "System Events" in status["detail"]


def test_probe_permission_errors_are_classified(monkeypatch):
    error = ui.UIAutomationError("live_error", "System Events got an error: osascript is not allowed assistive access. (-1719)")
    permissions(monkeypatch, None, None, Probe(error))
    assert "Accessibility" in ui.status()["fix"]


def test_env_switch_and_other_platforms(monkeypatch):
    monkeypatch.setenv(ui.ENV_SWITCH, "0")
    status = ui.status()
    assert not status["available"] and "Disabled" in status["detail"]
    monkeypatch.delenv(ui.ENV_SWITCH)
    monkeypatch.setattr(ui.sys, "platform", "win32")
    assert "macOS-only" in ui.status(refresh=True)["detail"]


# ---------------------------------------------------------------------------
# run_script
# ---------------------------------------------------------------------------


class Completed(object):
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def test_run_script_caps_the_timeout_and_returns_output(monkeypatch):
    seen = []

    def run(args, **kwargs):
        seen.append((args, kwargs))
        return Completed(0, "ok\n")

    monkeypatch.setattr(ui.subprocess, "run", run)
    assert ui.run_script("return 1", timeout=60) == "ok"
    args, kwargs = seen[0]
    assert args == [ui.OSASCRIPT, "-"] and kwargs["input"] == "return 1" and kwargs["timeout"] == ui.MAX_TIMEOUT


def test_run_script_timeout(monkeypatch):
    def run(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(ui.subprocess, "run", run)
    with pytest.raises(ui.UIAutomationError) as error:
        ui.run_script("delay 10", timeout=2)
    assert error.value.code == "timeout" and "2s" in error.value.message


def test_run_script_permission_failure_disables_ui_automation(monkeypatch):
    monkeypatch.setattr(ui.subprocess, "run", lambda args, **kwargs: Completed(1, "", "36:52: execution error: System Events got an error: osascript is not allowed to send keystrokes. (1002)"))
    with pytest.raises(ui.UIAutomationError) as error:
        ui.run_script('tell application "System Events" to keystroke "s"')
    assert error.value.code == "unsupported" and "Accessibility" in error.value.hint
    assert ui._cached["available"] is False  # later calls fail fast without osascript


def test_permission_problem():
    assert ui.permission_problem("Not authorized to send Apple events to System Events. (-1743)") == "automation"
    assert ui.permission_problem("osascript is not allowed assistive access. (-25211)") == "accessibility"
    assert ui.permission_problem("Can't get window 1. (-1728)") is None


# ---------------------------------------------------------------------------
# AppleScript construction
# ---------------------------------------------------------------------------


def test_applescript_string_escapes():
    assert ui.applescript_string('My "Best" \\ Song') == '"My \\"Best\\" \\\\ Song"'
    with pytest.raises(ValueError):
        ui.applescript_string("two\nlines")


def test_key_statements():
    assert ui.key_statement("s", ["command", "shift"]) == 'keystroke "s" using {command down, shift down}'
    assert ui.key_statement("return") == "key code 36"
    assert ui.key_statement("/Users/me/Music") == 'keystroke "/Users/me/Music"'
    with pytest.raises(ValueError):
        ui.key_statement("s", ["hyper"])


def test_live_script_targets_live_by_bundle_id():
    script = ui.live_script(ui.key_statement("n", ["command"]), "delay 0.5")
    assert 'first application process whose bundle identifier is "com.ableton.live"' in script
    assert "set frontmost of liveProcess to true" in script
    assert '\t\tkeystroke "n" using {command down}\n\t\tdelay 0.5' in script
    assert script.strip().endswith('return "ok"')


def test_file_panel_statements_fill_name_then_folder():
    statements = ui.file_panel_statements("/Users/me/Music", 'Song "1"')
    assert statements[1] == 'keystroke "Song \\"1\\""'
    assert statements.index('keystroke "g" using {command down, shift down}') < statements.index('keystroke "/Users/me/Music"')
    assert statements[-1] == "key code 36"


def test_actions_require_permission_first(monkeypatch):
    monkeypatch.setattr(ui, "require", lambda: (_ for _ in ()).throw(ui.UIAutomationError("unsupported", "no", "fix it")))
    ran = []
    monkeypatch.setattr(ui, "run_script", lambda script, timeout=ui.MAX_TIMEOUT: ran.append(script))
    for action, args in ((ui.save, ()), (ui.new_set, ()), (ui.save_as, ("/tmp", "x")), (ui.export, ("/tmp", "x"))):
        with pytest.raises(ui.UIAutomationError):
            action(*args)
    assert ran == []


def test_actions_send_the_right_shortcuts(monkeypatch):
    monkeypatch.setattr(ui, "require", lambda: None)
    ran = []
    monkeypatch.setattr(ui, "run_script", lambda script, timeout=ui.MAX_TIMEOUT: ran.append(script) or "ok")
    ui.save()
    ui.new_set()
    ui.save_as("/Users/me/Music", "Song")
    ui.export("/Users/me/Music", "Mix")
    assert 'keystroke "s" using {command down}' in ran[0]
    assert 'keystroke "n" using {command down}' in ran[1]
    assert 'keystroke "s" using {command down, shift down}' in ran[2] and "No file panel appeared" in ran[2]
    assert 'keystroke "Song"' in ran[3] and 'keystroke "/Users/me/Music"' in ran[3]
    assert 'keystroke "r" using {command down, shift down}' in ran[4] and 'keystroke "Mix"' in ran[6]


# ---------------------------------------------------------------------------
# Host app, Live app, open_document
# ---------------------------------------------------------------------------


def test_app_bundle_skips_framework_python():
    assert ui.app_bundle("/Applications/Claude.app/Contents/MacOS/Claude") == "/Applications/Claude.app"
    assert ui.app_bundle("/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python") is None
    assert ui.app_bundle("/bin/zsh") is None


def test_host_app_walks_up_the_parent_processes(monkeypatch):
    monkeypatch.undo()  # use the real host_app, with a fake process table
    table = {
        "100": "50 /Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python",
        "50": "40 /bin/zsh",
        "40": "1 /Applications/Claude.app/Contents/MacOS/Claude",
    }
    monkeypatch.setattr(ui.os, "getpid", lambda: 100)
    monkeypatch.setattr(ui.subprocess, "run", lambda args, **kwargs: Completed(0, table[args[-1]]))
    assert ui.host_app() == ("Claude", "/Applications/Claude.app")


def test_live_app_path_prefers_the_running_live(monkeypatch):
    output = "/usr/sbin/cfprefsd\n/Applications/Ableton Live 12 Suite.app/Contents/MacOS/Live\n"
    monkeypatch.setattr(ui.subprocess, "run", lambda args, **kwargs: Completed(0, output))
    assert ui.live_app_path() == "/Applications/Ableton Live 12 Suite.app"
    monkeypatch.setattr(ui.subprocess, "run", lambda args, **kwargs: Completed(0, ""))
    monkeypatch.setattr(ui.glob, "glob", lambda pattern: ["/Applications/Ableton Live 11 Suite.app", "/Applications/Ableton Live 12 Suite.app"] if pattern.startswith("/Applications") else [])
    assert ui.live_app_path() == "/Applications/Ableton Live 12 Suite.app"


def test_open_document_uses_open_a(monkeypatch):
    seen = []
    monkeypatch.setattr(ui, "live_app_path", lambda: "/Applications/Ableton Live 12 Suite.app")
    monkeypatch.setattr(ui.subprocess, "run", lambda args, **kwargs: seen.append((args, kwargs["timeout"])) or Completed(0))
    assert ui.open_document("/Users/me/Song.als") == "/Applications/Ableton Live 12 Suite.app"
    assert seen == [(["open", "-a", "/Applications/Ableton Live 12 Suite.app", "/Users/me/Song.als"], ui.MAX_TIMEOUT)]
    monkeypatch.setattr(ui.subprocess, "run", lambda args, **kwargs: Completed(1, "", "The file does not exist."))
    with pytest.raises(ui.UIAutomationError):
        ui.open_document("/nope.als")
    monkeypatch.setattr(ui, "live_app_path", lambda: None)
    with pytest.raises(ui.UIAutomationError) as error:
        ui.open_document("/Users/me/Song.als")
    assert error.value.code == "unsupported"
