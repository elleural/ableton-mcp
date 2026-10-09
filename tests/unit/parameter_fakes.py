"""Fake DeviceParameters shaped like Live 12.4.6's, for the parameter unit tests.

Ranges, display strings and display_value behaviour were read from the real devices with str_for_value
(2026-10-08): stepped parameters such as Echo's L Synced reject display_value ("Invalid display value"),
and a ratio's display_value is its side other than 1 (Ratio "3.00 : 1" -> 3, Expansion Ratio "1 : 1.15" -> 1.15).
"""
import math

from AbletonMCP_Remote_Script import values


class Parameter(object):
    """A DeviceParameter that Live does not quantize. `show(raw)` is str_for_value; `from_display(number)` is
    the raw value a display_value write lands on (None: the write raises, as on Live's stepped parameters)."""

    is_quantized = False
    is_enabled = True

    def __init__(self, name, low, high, value, show, from_display=None):
        self.name = self.original_name = name
        self.min, self.max, self.value = float(low), float(high), float(value)
        self.show, self.from_display = show, from_display

    def str_for_value(self, raw):
        return self.show(raw)

    @property
    def display_value(self):
        if self.from_display is None:
            raise RuntimeError("Invalid display value")
        return values.parse_display_number(self.show(self.value))

    @display_value.setter
    def display_value(self, number):
        if self.from_display is None:
            raise RuntimeError("Invalid display value")
        self.value = min(max(float(self.from_display(number)), self.min), self.max)


def stepped(name, low, labels, value):
    """A parameter that steps through low .. low + len(labels) - 1 and shows labels[raw - low]."""
    return Parameter(name, low, low + len(labels) - 1, value, lambda raw: labels[int(round(raw)) - low])


NOTE_VALUES = ["1/64", "1/32", "1/16", "1/8", "1/4", "1/2", "1"]
# Auto Filter LFO Rate, Auto Pan-Tremolo Rate, Echo Mod Rate, Drift and Wavetable LFO rates, Delay LFO Synced
SYNCED_RATES = ["8", "6", "4", "3", "2", "1.5", "1", "3/4", "1/2", "3/8", "1/3", "5/16", "1/4", "3/16", "1/6", "1/8",
                "1/12", "1/16", "1/24", "1/32", "1/48", "1/64"]
HYBRID_TI_RATES = ["1/128 T", "1/128", "1/64 T", "1/128 D", "1/64", "1/32 T", "1/64 D", "1/32", "1/16 T", "1/32 D",
                   "1/16", "1/8 T", "1/16 D", "1/8", "1/4 T", "1/8 D", "1/4", "1/2 T", "1/4 D", "1/2", "1 T", "1/2 D", "1",
                   "2 T", "1 D", "2", "4 T", "2 D", "4", "4 D"]
ANALOG_SYNC_RATES = ["4d", "4", "4t", "2d", "2", "2t", "1d", "1", "1t", "1/2d", "1/2", "1/2t", "1/4d", "1/4", "1/4t",
                     "1/8d", "1/8", "1/8t", "1/16d", "1/16", "1/16t", "1/32d", "1/32", "1/32t"]


def echo_l_synced():
    return stepped("L Synced", -6, NOTE_VALUES, -3)


def roar_fb_synced():
    """Roar writes its note values with spaces around the slash."""
    return stepped("FB Synced", -7, ["1 / 128"] + [label.replace("/", " / ") for label in NOTE_VALUES], -4)


def auto_filter_lfo_rate():
    return stepped("LFO Rate", 0, SYNCED_RATES, 4)


def hybrid_ti_rate():
    return stepped("Ti Rate", 0, HYBRID_TI_RATES, 22)


def analog_lfo_rate():
    return stepped("LFO1 SncRate", 0, ANALOG_SYNC_RATES, 13)


def auto_filter_lfo_16th():
    """1..64 sixteenths shown as '8  / 16' (two spaces); display_value counts sixteenths."""
    return Parameter("LFO 16th", 1, 64, 32, lambda raw: "{0}  / 16".format(int(round(raw))), round)


def roar_fb_note():
    """MIDI notes 12..84 shown as note names, C-1 .. C5."""
    return stepped("FB Note", 12, [values.pitch_name(pitch) for pitch in range(12, 85)], 31)


def hybrid_vintage():
    return stepped("Vintage", 0, ["Off", "Subtle", "Old", "Older", "Extreme"], 0)


def drum_buss_transients():
    """-1..1 shown as a plain fraction ('0.15'), not a percentage; display_value is the raw value."""
    return Parameter("Transients", -1, 1, 0.15, "{0:.2f}".format, lambda number: number)


def compressor_output():
    """-36..36 dB with the raw value in dB (a stepped range with numeric labels)."""
    return Parameter("Output", -36, 36, 0, "{0:.1f} dB".format, lambda db: db)


def compressor_ratio():
    """Raw 0..1 shown as '1.00 : 1' .. 'inf : 1'."""
    def show(raw):
        return "inf : 1" if raw >= 1.0 else "{0:.2f} : 1".format(1.0 / (1.0 - raw))
    return Parameter("Ratio", 0, 1, 2.0 / 3.0, show, lambda ratio: 1.0 - 1.0 / ratio)


def compressor_expansion_ratio():
    return Parameter("Expansion Ratio", 1, 2, 1.15, lambda raw: "1 : {0:.2f}".format(raw), lambda ratio: ratio)


def frequency():
    """Raw 0..1 maps to 20 Hz .. 20 kHz; display_value is in Hz."""
    def show(raw):
        hertz = 20.0 * 1000.0 ** raw
        return "{0:.0f} Hz".format(hertz) if hertz < 999.5 else "{0:.2f} kHz".format(hertz / 1000.0)
    return Parameter("Frequency", 0, 1, 0.5, show, lambda hertz: math.log(max(hertz, 1e-9) / 20.0) / math.log(1000.0))


def percent(name="Dry/Wet"):
    return Parameter(name, 0, 1, 0.5, lambda raw: "{0:.0f} %".format(raw * 100.0), lambda amount: amount / 100.0)


def roar_blend():
    """A crossfade shown as '100 / 0' .. '0 / 100': fractions that are display values, not note values."""
    return Parameter("Blend", 0, 1, 0.5, lambda raw: "{0:.0f} / {1:.0f}".format(100.0 * (1.0 - raw), 100.0 * raw))


def pan():
    """Raw -1..1 shown as '50L' .. 'C' .. '50R'; display_value counts -50..50."""
    def show(raw):
        amount = int(round(abs(raw) * 50.0))
        return "C" if amount == 0 else "{0}{1}".format(amount, "L" if raw < 0 else "R")
    return Parameter("1 Pan", -1, 1, 0, show, lambda number: number / 50.0)


class TimeParameter(object):
    """A continuous time parameter like Reverb's Decay Time: raw 0..1 maps to 1 ms .. 60 s.

    It shows "xx.x ms" below one second and "x.xx s" above. display_value is in `unit_ms` milliseconds
    (1 = ms like Live; 1000 = a parameter whose display_value were seconds).
    """

    def __init__(self, unit_ms=1.0, accepts_display=True):
        self.min, self.max, self.value = 0.0, 1.0, 0.5
        self.name = self.original_name = "Decay Time"
        self.is_quantized, self.is_enabled = False, True
        self.unit_ms, self.accepts_display = unit_ms, accepts_display

    @staticmethod
    def ms(raw):
        return 60000.0 ** raw

    def str_for_value(self, raw):
        ms = self.ms(raw)
        return "{0:.1f} ms".format(ms) if ms < 1000 else "{0:.2f} s".format(ms / 1000.0)

    @property
    def display_value(self):
        return self.ms(self.value) / self.unit_ms

    @display_value.setter
    def display_value(self, target):
        if not self.accepts_display:
            raise RuntimeError("display_value is not settable")
        self.value = min(max(math.log(max(target * self.unit_ms, 1.0)) / math.log(60000.0), 0.0), 1.0)


class Quantized(object):
    min, max, value = 0.0, 2.0, 0.0
    name = original_name = "Size Smoothing"
    is_quantized, is_enabled = True, True
    value_items = ["None", "Slow", "Fast"]

    def str_for_value(self, raw):
        return self.value_items[int(raw)]
