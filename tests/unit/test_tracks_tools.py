"""Unit tests for WS-B's MCP tools: busy retries and the create_bus composition (no Live needed)."""
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server.connection import AbletonError
from MCP_Server.tools import tracks as tools


def tool_error(code, message):
    """A ToolError chained the way app.call raises it from an AbletonError."""
    try:
        try:
            raise AbletonError(code, message)
        except AbletonError as error:
            raise ToolError(str(error))
    except ToolError as error:
        return error


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(tools, "ROUTING_DELAY", 0.0)


def test_is_busy():
    assert tools.is_busy(tool_error("busy", "Routing options are not ready"))
    assert not tools.is_busy(tool_error("not_found", "Track 'x' not found"))
    assert tools.is_busy(ToolError("Track 'a' does not offer 'Bus' yet (not ready yet ...)"))


def test_retry_busy_retries_then_succeeds():
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise tool_error("busy", "not offered yet")
        return "ok"

    assert tools.retry_busy(flaky) == "ok" and len(attempts) == 3


def test_retry_busy_does_not_retry_other_errors():
    attempts = []

    def broken():
        attempts.append(1)
        raise tool_error("not_found", "nope")

    with pytest.raises(ToolError):
        tools.retry_busy(broken)
    assert len(attempts) == 1


def test_retry_busy_gives_up():
    attempts = []

    def never():
        attempts.append(1)
        raise tool_error("busy", "never ready")

    with pytest.raises(ToolError):
        tools.retry_busy(never, attempts=4)
    assert len(attempts) == 4


class FakeCall(object):
    def __init__(self, route_failures=0, route_error=None):
        self.calls = []
        self.route_failures = route_failures
        self.route_error = route_error

    def __call__(self, command, timeout=None, **params):
        params = dict((key, value) for key, value in params.items() if value is not None)
        self.calls.append((command, params))
        if command == "create_bus":
            return {"bus": {"track": 5, "name": params["name"], "kind": "audio"},
                    "sources": [{"track": 1, "name": "Kick", "kind": "audio", "ref": "Kick"},
                                {"track": 2, "name": "Snare", "kind": "audio", "ref": 2}]}
        if command == "tracks_route_to_bus":
            if self.route_error is not None:
                raise self.route_error
            if self.route_failures:
                self.route_failures -= 1
                raise tool_error("busy", "not offered yet")
            return {"bus": {"track": 5, "name": params["bus"], "monitoring": "in", "input": {"type": "No Input"}},
                    "sources": [{"track": 1, "name": "Kick", "output": {"type": params["bus"], "channel": "Track In"}}]}
        if command == "delete_track":
            return {"deleted": {"name": params["track"]}}
        raise AssertionError(command)


def test_create_bus_routes_on_a_later_call(monkeypatch):
    fake = FakeCall(route_failures=2)
    monkeypatch.setattr(tools, "call", fake)
    out = tools.create_bus("Drums", ["Kick", 2], color=4)
    assert fake.calls[0] == ("create_bus", {"name": "Drums", "sources": ["Kick", 2], "color": 4})
    assert fake.calls[1:] == [("tracks_route_to_bus", {"bus": "Drums", "sources": ["Kick", 2]})] * 3
    assert out["bus"]["monitoring"] == "in" and out["sources"][0]["output"]["type"] == "Drums" and out["undo_steps"] == 2


def test_create_bus_removes_the_bus_when_routing_fails(monkeypatch):
    fake = FakeCall(route_error=tool_error("invalid_argument", "Track 'Kick' has no audio output"))
    monkeypatch.setattr(tools, "call", fake)
    with pytest.raises(ToolError):
        tools.create_bus("Drums", ["Kick", 2])
    assert fake.calls[-1] == ("delete_track", {"track": "Drums"})


def test_tool_signatures_match_the_catalogue():
    import inspect

    expected = {
        "create_track": ["kind", "name", "index", "color", "device"],
        "get_track": ["track", "detail"],
        "set_track": ["track", "name", "color", "arm", "monitoring", "fold", "collapsed", "input", "input_channel",
                      "output", "output_channel", "show_chains"],
        "delete_track": ["track"],
        "duplicate_track": ["track", "name"],
        "get_routing_options": ["track"],
        "create_bus": ["name", "sources", "color"],
        "get_mixer": ["tracks"],
        "set_mixer": ["track", "volume_db", "volume", "pan", "sends", "mute", "solo", "active", "crossfade", "pan_mode",
                      "left_pan", "right_pan", "crossfader", "cue_volume_db"],
        "get_meters": ["tracks"],
    }
    for name, params in expected.items():
        assert list(inspect.signature(getattr(tools, name)).parameters) == params, name


def test_set_track_retries_while_routing_is_not_ready(monkeypatch):
    calls = []

    def fake(command, timeout=None, **params):
        calls.append(command)
        if len(calls) == 1:
            raise tool_error("busy", "Routing options of track 'Bus' are not ready yet")
        return {"name": params["track"], "output": {"type": params["output"]}}

    monkeypatch.setattr(tools, "call", fake)
    assert tools.set_track("Bass", output="Bus")["output"]["type"] == "Bus"
    assert calls == ["set_track", "set_track"]


def test_get_routing_options_rereads_until_ready(monkeypatch):
    answers = [{"output": {"types": [], "note": "Not ready yet"}}, {"output": {"types": ["Main"]}}]
    monkeypatch.setattr(tools, "call", lambda command, **params: answers.pop(0))
    assert tools.get_routing_options("Bass") == {"output": {"types": ["Main"]}}
