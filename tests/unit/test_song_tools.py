"""Unit tests for WS-A's MCP tools (tools/status.py, tools/song.py, tools/project.py).

Live is a scripted fake `call`, time is a fake clock, and UI automation is mocked: nothing here
talks to Live, runs osascript or opens a set.
"""
import copy
import os

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server.tools import project, song as song_tools, status as status_tools


class Clock(object):
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def live_status(document="d1", path=None, dialog=None):
    return {
        "set": {"name": None, "path": path, "saved": bool(path), "document": document},
        "transport": {"playing": False, "loop": {"on": False, "start": {"beats": 8.0, "bar": "3.1.1"}, "length": 16.0}},
        "dialog": dialog,
        "jobs": [],
    }


class FakeLive(object):
    """A scripted Remote Script. statuses: successive get_status answers (None = Live busy)."""

    def __init__(self, statuses=None, answers=None):
        self.statuses = list(statuses or [live_status()])
        self.answers = answers or {}
        self.calls = []

    def __call__(self, command, timeout=None, **params):
        self.calls.append((command, params))
        if command == "get_status":
            item = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            if item is None:
                raise ToolError("Live did not finish within 3s")
            return copy.deepcopy(item)
        answer = self.answers.get(command, {})
        if callable(answer):
            return answer(**params)
        if isinstance(answer, Exception):
            raise answer
        return copy.deepcopy(answer)

    def commands(self, name=None):
        return [(command, params) for command, params in self.calls if name is None or command == name]


@pytest.fixture
def clock(monkeypatch):
    fake = Clock()
    monkeypatch.setattr(project, "_time", fake)
    monkeypatch.setattr(song_tools, "_time", fake)
    return fake


@pytest.fixture
def ui(monkeypatch):
    """Records UI automation actions; available unless a test says otherwise."""
    actions = []
    module = project.ui_automation
    monkeypatch.setattr(module, "require", lambda: actions.append("require"))
    monkeypatch.setattr(module, "open_document", lambda path: actions.append(("open", path)) or "/Applications/Ableton Live 12 Suite.app")
    monkeypatch.setattr(module, "new_set", lambda: actions.append("new"))
    monkeypatch.setattr(module, "save", lambda: actions.append("save"))
    monkeypatch.setattr(module, "save_as", lambda folder, name: actions.append(("save_as", folder, name)))
    monkeypatch.setattr(module, "export", lambda folder, name: actions.append(("export", folder, name)))
    return actions


def unavailable(*args):
    raise project.ui_automation.UIAutomationError("unsupported", "UI automation is unavailable: Accessibility access is off for Claude", "Turn on Claude in Accessibility")


# ---------------------------------------------------------------------------
# tools/status.py
# ---------------------------------------------------------------------------


def test_get_status_adds_capabilities_and_dialog_hint(monkeypatch):
    monkeypatch.setattr(status_tools, "call", FakeLive([live_status(dialog={"open": 1, "message": "Save?", "buttons": 3})]))
    monkeypatch.setattr(status_tools.ui_automation, "status", lambda: {"available": False, "detail": "off", "fix": "turn on"})
    out = status_tools.get_status()
    assert out["connected"] is True and out["server"]["version"] and "respond_to_dialog" in out["hint"]
    assert out["capabilities"]["ui_automation"] == {"available": False, "detail": "off", "fix": "turn on"}
    assert set(out["capabilities"]) == {"ffmpeg", "ffprobe", "ui_automation"}


def test_get_status_when_live_is_unreachable(monkeypatch):
    monkeypatch.setattr(status_tools, "call", FakeLive([None]))
    monkeypatch.setattr(status_tools.ui_automation, "status", lambda: {"available": True, "detail": "", "fix": ""})
    out = status_tools.get_status()
    assert out["connected"] is False and "did not finish" in out["error"] and "capabilities" in out


def test_find_executable_falls_back_to_homebrew(monkeypatch):
    monkeypatch.setattr(status_tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(status_tools.os.path, "isfile", lambda path: path == "/opt/homebrew/bin/ffmpeg")
    monkeypatch.setattr(status_tools.os, "access", lambda path, mode: True)
    assert status_tools.find_executable("ffmpeg") == "/opt/homebrew/bin/ffmpeg"
    assert status_tools.find_executable("ffprobe") is None


# ---------------------------------------------------------------------------
# tools/song.py
# ---------------------------------------------------------------------------


def test_until_done_passes_restore_back(clock):
    sent = []
    answers = [{"pending": "playhead", "restore": 3.5}, {"pending": "playhead", "restore": 3.5}, {"locator": 0}]

    def send(**extra):
        sent.append(extra)
        return answers.pop(0)

    assert song_tools.until_done(send) == {"locator": 0}
    assert sent == [{}, {"restore": 3.5}, {"restore": 3.5}]
    with pytest.raises(ToolError):
        song_tools.until_done(lambda **extra: {"pending": "playhead"}, attempts=3)


def test_set_song_reads_back_on_the_next_tick_and_warns(monkeypatch):
    state = {"tempo": 124.0, "link": False, "punch_in": True, "loop": True}
    live = FakeLive(answers={"set_song": lambda **params: dict(state, applied=sorted(params))})
    monkeypatch.setattr(song_tools, "call", live)
    out = song_tools.set_song(tempo=124, link=True, punch_in=True)
    assert live.commands("set_song") == [("set_song", {"tempo": 124, "link": True, "punch_in": True}), ("set_song", {})]
    assert out["applied"] == [] and len(out["warnings"]) == 1 and "Link toggle" in out["warnings"][0]
    live.calls = []
    song_tools.set_song()
    assert live.commands() == [("set_song", {})]


def test_transport_finishes_pending_phases_then_reads_the_transport(monkeypatch, clock):
    answers = [{"action": "play", "pending": "start_marker"}, {"action": "play"}]
    live = FakeLive([dict(live_status(), transport={"playing": True})], answers={"transport": lambda **params: answers.pop(0)})
    monkeypatch.setattr(song_tools, "call", live)
    out = song_tools.transport("play", position="5.1.1")
    assert out == {"action": "play", "transport": {"playing": True}}
    assert [command for command, _ in live.calls] == ["transport", "transport", "get_status"]
    assert all(params == {"action": "play", "position": "5.1.1"} for command, params in live.commands("transport"))


def test_locator_tools_use_the_two_phase_protocol(monkeypatch, clock):
    answers = [{"pending": "playhead", "restore": 1.0}, {"locator": 0, "name": "A"}]
    live = FakeLive(answers={"create_locator": lambda **params: answers.pop(0), "delete_locator": {"deleted": {}}})
    monkeypatch.setattr(song_tools, "call", live)
    assert song_tools.create_locator("5.1.1", "A") == {"locator": 0, "name": "A"}
    assert live.commands("create_locator")[1] == ("create_locator", {"time": "5.1.1", "name": "A", "restore": 1.0})
    assert song_tools.delete_locator("A") == {"deleted": {}}


# ---------------------------------------------------------------------------
# tools/project.py: open_set and new_set
# ---------------------------------------------------------------------------


@pytest.fixture
def als(tmp_path):
    path = tmp_path / "Song.als"
    path.write_bytes(b"als")
    return str(path)


def test_open_set_waits_for_the_new_document(monkeypatch, clock, ui, als):
    live = FakeLive([live_status("d1"), None, None, live_status("d2", als)])
    monkeypatch.setattr(project, "call", live)
    out = project.open_set(als)
    assert out["opened"] is True and out["set"]["path"] == als and ui == [("open", als)]
    assert live.commands("respond_to_dialog") == []


def test_open_set_refuses_unsaved_changes_and_leaves_the_prompt(monkeypatch, clock, ui, als):
    prompt = {"open": 1, "message": 'Save changes to "Untitled" before closing?', "buttons": 3}
    live = FakeLive([live_status("d1"), live_status("d1", dialog=prompt)])
    monkeypatch.setattr(project, "call", live)
    with pytest.raises(ToolError) as error:
        project.open_set(als)
    assert "unsaved changes" in str(error.value) and "discard_unsaved=True" in str(error.value)
    assert live.commands("respond_to_dialog") == []


def test_open_set_discards_when_asked(monkeypatch, clock, ui, als):
    prompt = {"open": 1, "message": 'Save changes to "Untitled" before closing?', "buttons": 3}
    live = FakeLive([live_status("d1"), live_status("d1", dialog=prompt), live_status("d1", dialog=prompt), None, live_status("d2", als)])
    monkeypatch.setattr(project, "call", live)
    assert project.open_set(als, discard_unsaved=True)["opened"] is True
    assert live.commands("respond_to_dialog") == [("respond_to_dialog", {"button": "dont_save"})]


def test_open_set_other_dialogs_and_timeouts(monkeypatch, clock, ui, als):
    other = {"open": 1, "message": "Some samples could not be found", "buttons": 1}
    monkeypatch.setattr(project, "call", FakeLive([live_status("d1"), live_status("d1", dialog=other)]))
    with pytest.raises(ToolError) as error:
        project.open_set(als, discard_unsaved=True)
    assert "could not be found" in str(error.value)
    monkeypatch.setattr(project, "call", FakeLive([live_status("d1")]))
    with pytest.raises(ToolError) as error:
        project.open_set(als)
    assert "did not switch sets" in str(error.value)


def test_open_set_validates_before_touching_live(monkeypatch, clock, ui, tmp_path, als):
    live = FakeLive([live_status("d1", als)])
    monkeypatch.setattr(project, "call", live)
    with pytest.raises(ToolError):
        project.open_set(str(tmp_path / "missing.als"))
    assert live.calls == [] and ui == []
    out = project.open_set(als)
    assert out["already_open"] is True and ui == []
    busy = FakeLive([live_status("d0", dialog={"open": 1, "message": "Hello", "buttons": 1})])
    monkeypatch.setattr(project, "call", busy)
    with pytest.raises(ToolError):
        project.open_set(als)


def test_new_set(monkeypatch, clock, ui):
    live = FakeLive([live_status("d1"), live_status("d2")])
    monkeypatch.setattr(project, "call", live)
    assert project.new_set()["created"] is True and ui == ["require", "new"]


def test_new_set_without_ui_automation_fails_fast_with_the_fix(monkeypatch, clock, ui):
    monkeypatch.setattr(project.ui_automation, "require", unavailable)
    monkeypatch.setattr(project, "call", FakeLive([live_status("d1")]))
    with pytest.raises(ToolError) as error:
        project.new_set()
    assert "Accessibility" in str(error.value) and "Turn on Claude" in str(error.value) and ui == []


# ---------------------------------------------------------------------------
# tools/project.py: save_set
# ---------------------------------------------------------------------------


def test_save_set_needs_a_path_for_a_new_set(monkeypatch, clock, ui):
    monkeypatch.setattr(project, "call", FakeLive([live_status("d1")]))
    with pytest.raises(ToolError) as error:
        project.save_set()
    assert "never been saved" in str(error.value) and ui == []


def test_save_set_in_place_is_verified_by_mtime(monkeypatch, clock, ui, als):
    monkeypatch.setattr(project, "call", FakeLive([live_status("d1", als)]))
    os.utime(als, (100.0, 100.0))

    def save():
        ui.append("save")
        written = os.path.getmtime(als) + 100.0
        os.utime(als, (written, written))

    monkeypatch.setattr(project.ui_automation, "save", save)
    assert project.save_set() == {"saved": True, "path": als}
    assert project.save_set(als) == {"saved": True, "path": als}
    monkeypatch.setattr(project.ui_automation, "save", lambda: None)
    with pytest.raises(ToolError) as error:
        project.save_set()
    assert "did not write" in str(error.value)


def test_save_as_follows_live_into_its_project_folder(monkeypatch, clock, ui, tmp_path):
    folder = tmp_path / "Music"
    saved = folder / "My Song Project" / "My Song.als"
    statuses = [live_status("d1")]
    live = FakeLive(statuses)
    monkeypatch.setattr(project, "call", live)

    def save_as(target_folder, name):
        ui.append(("save_as", target_folder, name))
        saved.parent.mkdir(parents=True)
        saved.write_bytes(b"als")
        live.statuses = [live_status("d1", str(saved))]

    monkeypatch.setattr(project.ui_automation, "save_as", save_as)
    out = project.save_set(str(folder / "My Song"))
    assert out == {"saved": True, "path": str(saved), "requested": str(folder / "My Song.als")}
    assert ui == ["require", ("save_as", str(folder), "My Song")]


def test_save_as_never_overwrites(monkeypatch, clock, ui, tmp_path, als):
    monkeypatch.setattr(project, "call", FakeLive([live_status("d1", str(tmp_path / "Other.als"))]))
    with pytest.raises(ToolError) as error:
        project.save_set(als)
    assert "already exists" in str(error.value) and ("save_as" not in str(ui))


def test_saved_as_and_paths(tmp_path):
    folder = tmp_path / "Music"
    (folder / "Song Project").mkdir(parents=True)
    assert project.saved_as(str(folder / "Song.als"), str(folder), "Song")
    assert project.saved_as(str(folder / "Song Project" / "Song.als"), str(folder), "Song")
    assert not project.saved_as(str(folder / "Other.als"), str(folder), "Song")
    assert not project.saved_as(None, str(folder), "Song")
    assert project.normalize_path("~/Music/Song").endswith("/Music/Song.als")
    assert project.normalize_path("mix.WAV", project.AUDIO_EXTENSIONS, ".wav").endswith("mix.WAV")
    assert project.is_save_prompt('Save changes to "Untitled" before closing?') and not project.is_save_prompt("Missing samples")
    with pytest.raises(ToolError):
        project.normalize_path("  ")


# ---------------------------------------------------------------------------
# tools/project.py: export_audio
# ---------------------------------------------------------------------------


def test_export_audio_sets_and_restores_the_loop(monkeypatch, clock, ui, tmp_path):
    live = FakeLive([live_status("d1")], answers={"set_song": {}})
    monkeypatch.setattr(project, "call", live)

    def export(folder, name):
        ui.append(("export", folder, name))
        with open(os.path.join(folder, name + ".wav"), "wb") as handle:
            handle.write(b"RIFF" + b"0" * 100)
        os.utime(os.path.join(folder, name + ".wav"), (clock.now, clock.now))

    monkeypatch.setattr(project.ui_automation, "export", export)
    out = project.export_audio(str(tmp_path / "Mix.wav"), "1.1.1", "9.1.1")
    assert out["exported"] and out["path"] == str(tmp_path / "Mix.wav") and out["bytes"] == 104 and out["experimental"]
    assert live.commands("set_song") == [
        ("set_song", {"loop_start": "1.1.1", "loop_end": "9.1.1"}),
        ("set_song", {"loop_start": 8.0, "loop_length": 16.0, "loop": False}),
    ]


def test_export_audio_restores_the_loop_when_the_ui_fails(monkeypatch, clock, ui, tmp_path):
    live = FakeLive([live_status("d1")], answers={"set_song": {}})
    monkeypatch.setattr(project, "call", live)
    monkeypatch.setattr(project.ui_automation, "export", unavailable)
    with pytest.raises(ToolError):
        project.export_audio(str(tmp_path / "Mix"), 0, 32)
    assert len(live.commands("set_song")) == 2


def test_export_audio_refuses_existing_files_and_missing_permission(monkeypatch, clock, ui, tmp_path):
    existing = tmp_path / "Mix.wav"
    existing.write_bytes(b"x")
    monkeypatch.setattr(project, "call", FakeLive([live_status("d1")]))
    with pytest.raises(ToolError):
        project.export_audio(str(existing), 0, 16)
    monkeypatch.setattr(project.ui_automation, "require", unavailable)
    live = FakeLive([live_status("d1")])
    monkeypatch.setattr(project, "call", live)
    with pytest.raises(ToolError) as error:
        project.export_audio(str(tmp_path / "New.wav"), 0, 16)
    assert "Accessibility" in str(error.value) and live.commands("set_song") == []
