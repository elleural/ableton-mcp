"""Unit tests for WS-F automation shapes and display-unit conversion (handlers/automation.py)."""
import math

import pytest

from AbletonMCP_Remote_Script.errors import CommandError
from AbletonMCP_Remote_Script.handlers import automation
from AbletonMCP_Remote_Script.handlers.automation import shape_events


def times(points):
    return [round(time, 9) for time, _ in points]


def levels(points):
    return [value for _, value in points]


def test_ramp_is_two_breakpoints():
    assert shape_events("ramp", 0.0, 4.0, low=-24, high=0) == [(0.0, -24), (4.0, 0)]


def test_ramp_ignores_period():
    assert shape_events("ramp", 1.0, 3.0, low=0, high=1, period=0.5) == [(1.0, 0), (3.0, 1)]


def test_sine_starts_low_peaks_mid_cycle_and_samples_evenly():
    points = shape_events("sine", 0.0, 4.0, low=0.0, high=1.0, period=4.0, resolution=8)
    assert times(points) == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    assert levels(points)[0] == pytest.approx(0.0)
    assert levels(points)[4] == pytest.approx(1.0)       # half way through the cycle
    assert levels(points)[2] == pytest.approx(0.5)       # quarter cycle: half way up
    assert levels(points)[-1] == pytest.approx(0.0)      # cycle complete


def test_sine_default_resolution_and_partial_last_cycle():
    points = shape_events("sine", 0.0, 6.0, low=-1.0, high=1.0, period=4.0)
    assert len(points) == 6 / (4.0 / automation.SINE_POINTS_PER_CYCLE) + 1
    assert points[-1][0] == 6.0
    assert points[-1][1] == pytest.approx(1.0)           # 1.5 cycles: at the peak


def test_triangle_breakpoints_every_half_cycle():
    points = shape_events("triangle", 0.0, 8.0, low=0, high=10, period=4)
    assert points == [(0.0, 0), (2.0, 10), (4.0, 0), (6.0, 10), (8.0, 0.0)]


def test_triangle_ends_with_interpolated_value():
    points = shape_events("triangle", 0.0, 3.0, low=0.0, high=10.0, period=4.0)
    assert points[:2] == [(0.0, 0.0), (2.0, 10.0)]
    assert points[-1] == (3.0, pytest.approx(5.0))       # 3/4 through the cycle: half way down


def test_saw_rises_then_drops_with_a_vertical_jump():
    points = shape_events("saw", 0.0, 4.0, low=-24.0, high=0.0, period=2.0)
    assert points == [(0.0, -24.0), (2.0, 0.0), (2.0, -24.0), (4.0, 0.0)]


def test_saw_truncated_last_cycle():
    points = shape_events("saw", 0.0, 3.0, low=0.0, high=1.0, period=2.0)
    assert points[-2:] == [(2.0, 0.0), (3.0, pytest.approx(0.5))]


def test_square_holds_low_then_high_with_jumps():
    points = shape_events("square", 0.0, 4.0, low="50L", high="50R", period=2.0)
    assert points == [(0.0, "50L"), (1.0, "50L"), (1.0, "50R"), (2.0, "50R"), (2.0, "50L"), (3.0, "50L"), (3.0, "50R"), (4.0, "50R")]


def test_steps_cycle_over_the_period_and_merge_repeats():
    points = shape_events("steps", 0.0, 4.0, steps=[0, 1, 1, 0.5], period=2.0)
    # each step lasts 0.5 beats; the repeated 1 continues without a joint
    assert points == [(0.0, 0), (0.5, 0), (0.5, 1), (1.5, 1), (1.5, 0.5), (2.0, 0.5),
                      (2.0, 0), (2.5, 0), (2.5, 1), (3.5, 1), (3.5, 0.5), (4.0, 0.5)]


def test_steps_default_period_spans_the_range():
    points = shape_events("steps", 2.0, 6.0, steps=["Off", "On"])
    assert points == [(2.0, "Off"), (4.0, "Off"), (4.0, "On"), (6.0, "On")]


def test_grid_has_no_floating_drift():
    points = shape_events("steps", 0.0, 1.0, steps=[0, 1, 2], period=0.3)
    assert all(abs(time * 10 - round(time * 10)) < 1e-9 for time in times(points))
    assert points[-1] == (1.0, 0)


@pytest.mark.parametrize("kind, kwargs, message", [
    ("wobble", {"low": 0, "high": 1}, "type must be one of"),
    ("ramp", {"low": 0}, "needs 'from' and 'to'"),
    ("steps", {"steps": []}, "non-empty 'steps'"),
    ("sine", {"low": 0, "high": 1, "period": 0}, "period must be positive"),
    ("sine", {"low": 0, "high": 1, "period": 0.001}, "breakpoints"),
])
def test_shape_errors(kind, kwargs, message):
    with pytest.raises(CommandError) as error:
        shape_events(kind, 0.0, 16.0, **kwargs)
    assert error.value.code == "invalid_argument"
    assert message in error.value.message


def test_empty_range_is_rejected():
    with pytest.raises(CommandError):
        shape_events("ramp", 2.0, 2.0, low=0, high=1)


# ---------------------------------------------------------------------------
# Display units -> raw values (fake parameters)
# ---------------------------------------------------------------------------


class FakeParameter(object):
    """Minimal DeviceParameter: raw range plus a display mapping."""

    def __init__(self, name, low, high, display, quantized=False, items=None):
        self.name = name
        self.min = low
        self.max = high
        self._display = display
        self.is_quantized = quantized
        self.value_items = items or []
        self.is_enabled = True
        self.value = low

    def str_for_value(self, value):
        return self._display(value)


def volume():
    # raw 0..1 mapped linearly to -70..+6 dB, with -inf at 0
    def show(value):
        if value <= 0:
            return "-inf dB"
        return "{0:.1f} dB".format(-70.0 + 76.0 * value)
    return FakeParameter("Track Volume", 0.0, 1.0, show)


def pan():
    def show(value):
        amount = int(round(abs(value) * 50))
        return "C" if amount == 0 else "{0}{1}".format(amount, "L" if value < 0 else "R")
    return FakeParameter("Track Panning", -1.0, 1.0, show)


def frequency():
    def show(value):  # raw 0..1 -> 20 Hz .. 20 kHz, exponential
        hz = 20.0 * (1000.0 ** value)
        return "{0:.0f} Hz".format(hz) if hz < 1000 else "{0:.2f} kHz".format(hz / 1000.0)
    return FakeParameter("Frequency", 0.0, 1.0, show)


def test_display_db_converts_without_touching_the_parameter():
    parameter = volume()
    raw = automation.raw_value(parameter, -6, "display")
    assert abs((-70.0 + 76.0 * raw) - (-6.0)) <= 0.05 + 1e-9   # within one display step (0.1 dB here)
    assert parameter.value == 0.0
    assert automation.raw_value(parameter, "-6 dB", "display") == pytest.approx(raw)
    assert automation.raw_value(parameter, "-inf", "display") == 0.0


def test_display_khz_strings():
    parameter = frequency()
    raw = automation.raw_value(parameter, "2 kHz", "display")
    assert 20.0 * (1000.0 ** raw) == pytest.approx(2000.0, rel=0.01)


def test_pan_uses_minus_one_to_one_and_strings():
    parameter = pan()
    assert automation.is_pan(parameter)
    assert automation.raw_value(parameter, -0.5, "display") == pytest.approx(-0.5)
    assert automation.raw_value(parameter, "25R", "display") == pytest.approx(0.5)
    assert automation.raw_value(parameter, "C", "display") == pytest.approx(0.0)
    with pytest.raises(CommandError):
        automation.raw_value(parameter, 25, "display")  # pan is -1..1, not -50..50


def test_quantized_items_and_numbers():
    parameter = FakeParameter("Filter Type", 0.0, 3.0, lambda value: str(value), quantized=True, items=["Lowpass", "Highpass", "Bandpass", "Notch"])
    assert automation.raw_value(parameter, "bandpass", "display") == 2.0
    assert automation.raw_value(parameter, 1, "display") == 1.0
    with pytest.raises(CommandError) as error:
        automation.raw_value(parameter, "Comb", "display")
    assert "Options: Lowpass" in error.value.message


def test_out_of_range_display_values_are_errors_not_clamps():
    with pytest.raises(CommandError) as error:
        automation.raw_value(volume(), 12, "display")
    assert "outside the range" in error.value.message


def test_raw_units_are_range_checked():
    parameter = volume()
    assert automation.raw_value(parameter, 0.25, "raw") == 0.25
    with pytest.raises(CommandError):
        automation.raw_value(parameter, 1.5, "raw")
    with pytest.raises(CommandError):
        automation.raw_value(parameter, "-6 dB", "raw")


def test_conversion_cache_reuses_results():
    parameter = volume()
    calls = []
    original = parameter._display
    parameter._display = lambda value: calls.append(value) or original(value)
    cache = {}
    first = automation.raw_value(parameter, -12, "display", cache)
    count = len(calls)
    assert automation.raw_value(parameter, -12, "display", cache) == first
    assert len(calls) == count


def test_shape_levels_read_strings_in_the_parameters_units():
    assert automation._level(volume(), "-6 dB", "display", "from") == -6.0
    assert automation._level(pan(), "25L", "display", "from") == pytest.approx(-0.5)
    assert automation._level(volume(), 0.5, "raw", "from") == 0.5
    assert math.isinf(automation._level(volume(), "-inf dB", "display", "from"))
