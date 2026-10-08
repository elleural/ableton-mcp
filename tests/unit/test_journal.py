"""The command journal: the Remote Script writes it (AbletonMCP_Remote_Script/journal.py), `ableton-mcp journal` reads
it (MCP_Server/journal.py). Offline: a fake control surface runs main-thread tasks at once."""
import datetime

import pytest

from AbletonMCP_Remote_Script import core
from AbletonMCP_Remote_Script import journal as writer
from MCP_Server import journal as reader


class FakeSong(object):
    def __init__(self):
        self.steps = 0

    def begin_undo_step(self):
        self.steps += 1

    def end_undo_step(self):
        pass


class FakeApplication(object):
    def get_version_string(self):
        return "12.4.6"


class FakeSurface(object):
    def __init__(self):
        self.mcp_state = {}
        self._song = FakeSong()
        self.core_report = {}

    def submit(self, task):
        task()

    def song(self):
        return self._song

    def application(self):
        return FakeApplication()

    def log_message(self, *args):
        pass

    def show_message(self, *args):
        pass


@pytest.fixture()
def journal_file(tmp_path, monkeypatch):
    target = tmp_path / "logs" / "live-commands.log"
    monkeypatch.setenv("ABLETON_MCP_JOURNAL", str(target))
    writer._state.update(handle=None, path=None)
    core.load_handlers()
    yield target
    if writer._state["handle"] is not None:
        writer._state["handle"].close()
    writer._state.update(handle=None, path=None)


def _events(target):
    return [line.split("\t") for line in target.read_text().splitlines()]


def test_a_command_is_logged_before_it_runs_and_when_it_ends(journal_file):
    core.dispatch(FakeSurface(), {"type": "ping", "params": {}, "client": "pytest:1"})
    rows = [row for row in _events(journal_file) if row[1] != "load"]
    assert [row[1] for row in rows] == ["start", "run", "end"]
    assert rows[0][3:] == ["pytest:1", "ping", "{}"] and rows[2][3] == "ok" and rows[2][4].endswith("ms")
    assert rows[0][2] == rows[1][2] == rows[2][2]


def test_errors_and_unknown_commands_end_with_their_message(journal_file):
    core.dispatch(FakeSurface(), {"type": "no_such_command", "params": {}})
    rows = [row for row in _events(journal_file) if row[1] != "load"]
    assert [row[1] for row in rows] == ["start", "end"]                       # never ran on the main thread
    assert rows[0][3] == "-" and rows[1][3] == "error" and "[not_found]" in rows[1][5]


def test_batch_items_are_logged_one_by_one(journal_file):
    commands = [{"type": "ping", "params": {}}, {"type": "get_commands", "params": {"include_failures": False}}]
    core.dispatch(FakeSurface(), {"type": "batch", "params": {"commands": commands}})
    rows = [row for row in _events(journal_file) if row[1] != "load"]
    assert [row[1] for row in rows] == ["start", "run", "item", "item", "end"]
    number = rows[0][2]
    assert rows[2][2] == number + ".1" and rows[2][3] == "ping"
    assert rows[3][2] == number + ".2" and rows[3][3] == "get_commands" and rows[3][4] == '{"include_failures":false}'


def test_big_parameters_are_summarised_not_copied():
    snapshot = {"tracks": [{"name": str(i)} for i in range(500)], "song": {"tempo": 140}}
    text = writer.summary({"snapshot": snapshot, "path": "live_set", "note": "x" * 500})
    assert len(text) <= writer.TEXT_CHARS and "<list 500>" in text and '"path":"live_set"' in text
    assert writer.shape("y" * 100).endswith("...") and writer.shape(list(range(20))) == "<list 20>"
    assert writer.shape({str(i): i for i in range(30)}) == "<object 30 keys>"


def test_the_journal_rotates_and_can_be_switched_off(journal_file, monkeypatch):
    monkeypatch.setattr(writer, "MAX_BYTES", 400)
    for index in range(20):
        writer.event("note", "line {0} ".format(index) + "x" * 40)
    assert journal_file.exists() and (journal_file.parent / "live-commands.log.1").exists()
    assert journal_file.stat().st_size < 1000
    monkeypatch.setenv("ABLETON_MCP_JOURNAL", "off")
    other = journal_file.parent / "elsewhere.log"
    writer.event("note", "not written")
    assert writer.path() is None and not other.exists()


def test_the_load_event_names_the_live_process(journal_file):
    rows = [row for row in _events(journal_file) if row[1] == "load"]
    assert rows and "commands" in rows[-1][3] and "pid" in rows[-1][3]


# ---------------------------------------------------------------------------
# Reading it back
# ---------------------------------------------------------------------------

LINES = """2026-10-07T23:49:40.100\tload\t-\tcore 2.0.0, 84 commands, 0 failed module(s), pid 31547
2026-10-07T23:49:45.000\tstart\t1\tpytest:9\tbatch\t{"commands":"<list 6>","stop_on_error":false}
2026-10-07T23:49:45.010\trun\t1
2026-10-07T23:49:45.011\titem\t1.1\tlom_call\t{"args":[30],"method":"delete_track","path":"live_set"}
2026-10-07T23:49:45.020\titem\t1.5\tlom_call\t{"args":[10],"method":"delete_scene","path":"live_set"}
2026-10-07T23:49:45.030\tstart\t2\tableton-mcp:7\tget_status\t{}
""".splitlines()


def test_in_flight_names_the_running_batch_item():
    flying = reader.in_flight(reader.parse(LINES))
    assert [item["number"] for item in flying] == ["1", "2"]
    assert flying[0]["running"] and flying[0]["command"] == "batch" and flying[0]["item"]["index"] == "1.5"
    assert '"delete_scene"' in flying[0]["item"]["params"] and not flying[1]["running"]
    done = reader.parse(LINES + ["2026-10-07T23:49:45.040\tend\t1\tok\t30.0ms\t"])
    assert [item["number"] for item in reader.in_flight(done)] == ["2"]
    reloaded = reader.parse(LINES + ["2026-10-07T23:49:46.000\tload\t-\tcore reloaded"])
    assert reader.in_flight(reloaded) == []


def test_the_crash_report_lines_the_journal_up_with_live_s_fatal_error(tmp_path):
    journal = tmp_path / "live-commands.log"
    journal.write_text("\n".join(LINES + ["2026-10-07T23:50:30.000\tstart\t3\tpytest:9\tping\t{}"]) + "\n")
    log = tmp_path / "Log.txt"
    log.write_text("2026-10-07T23:49:47.835415: error: FatalError: Uncaught exception\n"
                   "2026-10-07T23:49:47.835462: error: FatalError: [std::out_of_range] vector\n")
    assert reader.last_fatal([str(log)]) == (datetime.datetime(2026, 10, 7, 23, 49, 47, 835415),
                                            "Uncaught exception | [std::out_of_range] vector")
    text = reader.report(crash=True, path=str(journal), log_paths=[str(log)])
    assert "std::out_of_range" in text and "#1 batch" in text and "at batch item 1.5: lom_call" in text
    assert "23:50:30" not in text                                               # after the crash: not shown
    assert "has no entries" in reader.report(path=str(tmp_path / "missing.log"))
    log.write_text(log.read_text() + "2026-10-08T01:20:00.000001: error: FatalError: later crash\n")
    assert reader.last_fatal([str(log)])[1] == "later crash"                   # the newest crash, alone
