"""Unit tests for set_sidechain's Compressor settings (MCP_Server/tools/devices.py): the kick-ducking defaults on a
Compressor it adds, as-found settings on an existing one, and argument checks. app.call is replaced by a fake Live."""
import asyncio
import inspect
import json
import re

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from MCP_Server import server
from MCP_Server.tools import devices as tools

# A freshly added Compressor in Live 12.4.6 (docs/production/reference/live-12.4.6-device-parameters.json).
FRESH = {
    "S/C On": "Off", "Threshold": "0.00 dB", "Ratio": "4.00 : 1", "Attack": "1.00 ms", "Release": "30.0 ms",
    "Model": "RMS", "S/C EQ On": "On", "S/C EQ Type": "High pass", "S/C EQ Freq": "80.0 Hz", "S/C EQ Q": "0.71",
    "S/C EQ Gain": "0.00 dB",
}
OPERATOR = {"index": 0, "path": "0", "name": "Operator", "class": "Operator", "class_name": "Operator"}
COMPRESSOR = {"index": 1, "path": "1", "name": "Compressor", "class": "Compressor", "class_name": "Compressor2"}


class FakeLive(object):
    """Stands in for app.call: a track holding `devices`, whose Compressor shows `shown` (FRESH to start with)."""

    def __init__(self):
        self.devices = [OPERATOR]
        self.shown = dict(FRESH)
        self.failing = ()  # parameter names that set_device_parameters reports under "errors"
        self.calls = []

    def __call__(self, command, timeout=None, **params):
        params = dict((key, value) for key, value in params.items() if value is not None)
        self.calls.append((command, params))
        if command == "get_devices":
            return {"track": {"track": 1, "name": params["track"]}, "devices": self.devices}
        if command == "add_device":
            entry = dict(COMPRESSOR, index=len(self.devices), path=str(len(self.devices)))
            self.devices.append(entry)
            self.shown = dict(FRESH)
            return {"device": entry, "devices": self.devices}
        if command == "get_track":
            return {"track": 0, "name": params["track"]}
        if command == "set_device":
            properties = params["properties"]
            return {"device": COMPRESSOR, "properties": [{"name": key, "value": value} for key, value in properties.items()]}
        if command == "set_device_parameters":
            out = {"device": COMPRESSOR, "parameters": []}
            for name, value in params["values"].items():
                if name in self.failing:
                    error = {"parameter": name, "code": "invalid_argument", "error": "out of range"}
                    out.setdefault("errors", []).append(error)
                else:
                    self.shown[name] = value
                    out["parameters"].append({"name": name, "display": value})
            return out
        if command == "get_device":
            return {"name": "Compressor", "parameters": [{"index": index, "name": name, "display": display}
                                                         for index, (name, display) in enumerate(self.shown.items())]}
        raise AssertionError(command)

    def commands(self):
        return [command for command, _ in self.calls]

    def written(self, only=None):
        """Values of the last set_device_parameters call (only the `only` names when given)."""
        values = [params["values"] for command, params in self.calls if command == "set_device_parameters"][-1]
        return dict((name, value) for name, value in values.items() if only is None or name in only)


@pytest.fixture
def live(monkeypatch):
    fake = FakeLive()
    monkeypatch.setattr(tools, "call", fake)
    return fake


def test_signature_keeps_the_old_order_and_adds_model_and_sidechain_eq():
    assert list(inspect.signature(tools.set_sidechain).parameters) == [
        "track", "source", "channel", "threshold_db", "ratio", "attack_ms", "release_ms", "enabled", "device",
        "model", "sidechain_eq",
    ]


def test_kick_ducking_defaults_use_the_compressors_item_names():
    assert tools.KICK_DUCKING["Model"] in tools.COMPRESSOR_MODELS
    assert tools.KICK_DUCKING["S/C EQ Type"] in tools.SIDECHAIN_EQ_TYPES


def test_a_compressor_it_adds_gets_the_kick_ducking_defaults(live):
    out = tools.set_sidechain("Bass", "Kick")
    assert live.commands() == ["get_track", "get_devices", "add_device", "set_device", "set_device_parameters"]
    assert live.written() == {
        "S/C On": "On", "Threshold": "-24 dB", "Ratio": "4", "Attack": "1 ms", "Release": "120 ms",
        "Model": "Peak", "S/C EQ On": "On", "S/C EQ Type": "Low pass", "S/C EQ Freq": "120 Hz",
    }
    assert out["added_compressor"] is True and out["device"] == "1" and out["source"] == "Kick"
    assert "as_found" not in out and "errors" not in out


def test_arguments_override_the_defaults_on_a_compressor_it_adds(live):
    tools.set_sidechain("Bass", "Kick", model="rms", sidechain_eq={"freq": "150 Hz", "type": None, "q": None})
    assert live.written(set(tools.KICK_DUCKING) | {"S/C EQ Q"}) == {
        "Model": "RMS", "S/C EQ On": "On", "S/C EQ Type": "Low pass", "S/C EQ Freq": "150 Hz",
    }


def test_sidechain_eq_off_on_a_compressor_it_adds_leaves_type_and_frequency_alone(live):
    tools.set_sidechain("Bass", "Kick", sidechain_eq="OFF")
    assert live.written(tools.KICK_DUCKING) == {"Model": "Peak", "S/C EQ On": "Off"}


def test_an_existing_compressor_keeps_model_and_eq_and_reports_them(live):
    live.devices.append(COMPRESSOR)
    out = tools.set_sidechain("Bass", "Kick", threshold_db=-30.5, ratio=6, attack_ms=0.5, release_ms=150)
    assert "add_device" not in live.commands() and out["added_compressor"] is False and out["device"] == "1"
    assert live.written() == {"S/C On": "On", "Threshold": "-30.5 dB", "Ratio": "6", "Attack": "0.5 ms", "Release": "150 ms"}
    assert live.calls[-1] == ("get_device", {"track": "Bass", "device": "1"})
    assert out["as_found"] == {"Model": "RMS", "S/C EQ On": "On", "S/C EQ Type": "High pass", "S/C EQ Freq": "80.0 Hz"}


def test_explicit_arguments_change_an_existing_compressor_without_a_read_back(live):
    live.devices.append(COMPRESSOR)
    eq = {"type": "low PASS", "freq": 90, "q": 1.2, "gain": -3}
    out = tools.set_sidechain("Bass", "Kick", model=" peak", sidechain_eq=eq)
    assert live.written(set(tools.KICK_DUCKING) | {"S/C EQ Q", "S/C EQ Gain"}) == {
        "Model": "Peak", "S/C EQ On": "On", "S/C EQ Type": "Low pass", "S/C EQ Freq": "90 Hz", "S/C EQ Q": "1.2",
        "S/C EQ Gain": "-3 dB",
    }
    assert "get_device" not in live.commands() and "as_found" not in out


def test_a_partial_eq_on_an_existing_compressor_reports_what_it_left(live):
    live.devices.append(COMPRESSOR)
    out = tools.set_sidechain("Bass", "Kick", sidechain_eq={"freq": "1.5 kHz"})
    assert live.written(tools.KICK_DUCKING) == {"S/C EQ On": "On", "S/C EQ Freq": "1.5 kHz"}
    assert out["as_found"] == {"Model": "RMS", "S/C EQ Type": "High pass"}


def test_as_found_leaves_out_the_type_and_frequency_of_an_eq_that_is_off(live):
    live.devices.append(COMPRESSOR)
    live.shown["S/C EQ On"] = "Off"
    assert tools.set_sidechain("Bass", "Kick")["as_found"] == {"Model": "RMS", "S/C EQ On": "Off"}
    out = tools.set_sidechain("Bass", "Kick", sidechain_eq="off")
    assert live.written(tools.KICK_DUCKING) == {"S/C EQ On": "Off"} and out["as_found"] == {"Model": "RMS"}
    calls = len(live.calls)
    out = tools.set_sidechain("Bass", "Kick", model="Peak", sidechain_eq="off")
    assert "as_found" not in out and "get_device" not in live.commands()[calls:]


def test_a_device_path_is_used_as_given_and_treated_as_existing(live):
    out = tools.set_sidechain("Bass", "Kick", device="Audio Effect Rack/0/0")
    assert "get_devices" not in live.commands() and "add_device" not in live.commands()
    assert out["device"] == "Audio Effect Rack/0/0" and out["added_compressor"] is False
    assert out["as_found"]["Model"] == "RMS"


def test_turning_it_off_leaves_model_and_eq_alone(live):
    live.devices.append(COMPRESSOR)
    out = tools.set_sidechain("Bass", enabled=False)
    assert live.commands() == ["get_devices", "set_device_parameters"] and live.written() == {"S/C On": "Off"}
    assert out == {"track": "Bass", "device": "1", "enabled": False, "parameters": [{"name": "S/C On", "display": "Off"}]}
    tools.set_sidechain("Bass", enabled=False, sidechain_eq="off")
    assert live.written() == {"S/C On": "Off", "S/C EQ On": "Off"}


def test_turning_it_off_never_adds_a_compressor(live):
    with pytest.raises(ToolError, match="no Compressor"):
        tools.set_sidechain("Bass", enabled=False)
    assert live.commands() == ["get_devices"]


@pytest.mark.parametrize("kwargs, message", [
    ({"source": None}, "needs source"),
    ({"model": "Opto"}, "model must be one of Peak, RMS, Expand"),
    ({"model": 1}, "model must be one of"),
    ({"sidechain_eq": "on"}, 'sidechain_eq must be "off" or an object'),
    ({"sidechain_eq": ["Low pass", 120]}, 'sidechain_eq must be "off" or an object'),
    ({"sidechain_eq": {"type": "Lowpass"}}, "Low Shelf, Bell, High Shelf, Low pass, Peak, High pass; got 'Lowpass'"),
    ({"sidechain_eq": {"type": "Low pass", "frequency": 120}}, "takes type, freq, q and gain; got frequency"),
    ({"sidechain_eq": {"freq": True}}, "sidechain_eq freq must be a number or a display string"),
    ({"sidechain_eq": {"gain": [3]}}, "sidechain_eq gain must be a number or a display string"),
])
def test_bad_arguments_fail_before_anything_changes(live, kwargs, message):
    with pytest.raises(ToolError, match=re.escape(message)):
        tools.set_sidechain("Bass", **dict({"source": "Kick"}, **kwargs))
    assert live.calls == []


def test_parameter_errors_from_live_are_reported(live):
    live.failing = ("S/C EQ Freq",)
    out = tools.set_sidechain("Bass", "Kick", sidechain_eq={"type": "Low pass", "freq": "5 Hz"})
    assert out["errors"] == [{"parameter": "S/C EQ Freq", "code": "invalid_argument", "error": "out of range"}]
    assert {"name": "S/C EQ Type", "display": "Low pass"} in out["parameters"]


def test_the_server_accepts_sidechain_eq_as_an_object_or_a_string(live):
    result = asyncio.run(server.mcp.call_tool("set_sidechain", {
        "track": "Bass", "source": "Kick", "model": "Peak", "sidechain_eq": {"type": "Low pass", "freq": 150}}))
    assert not result.is_error and json.loads(result.content[0].text)["added_compressor"] is True
    assert live.written(tools.KICK_DUCKING)["S/C EQ Freq"] == "150 Hz"
    result = asyncio.run(server.mcp.call_tool("set_sidechain", {"track": "Bass", "source": "Kick", "sidechain_eq": "off"}))
    assert not result.is_error and live.written(tools.KICK_DUCKING) == {"S/C EQ On": "Off"}
