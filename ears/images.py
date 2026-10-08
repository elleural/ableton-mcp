"""PNG pictures for an agent that can read images but cannot listen (PRD section 8, "Images").

Five pictures, one function each, all with the same contract: draw, write the PNG to `path` (parent
folders are created), close the figure, return the path as a string. The width is at most `width` pixels
(default 1200, the PRD's cap) and the height at most 1400; pictures aim for 1.2 megapixels or less (1000 px
tall at 1200 wide) because a vision model downscales larger images, which would shrink the text.

    stems_spectrogram   one row per stem on one time axis in bars, log frequency, a fixed dBFS scale
    piano_roll          notes coloured by chord-tone status, one lane group per part
    band_chart          energy per band, per series, against a reference envelope
    seam_zoom           a loop seam: waveform per channel plus a click-revealing high-frequency envelope
    ladder_chart        loudness of each tier T1..T5 with the target

Made for a vision model, not for beauty: every text is at least 10 pt at 100 dpi, colours are few and
strong, labels say what the axes are, and files stay small (about 100 to 250 KB).

matplotlib is imported on first use only, so importing this module costs nothing. Figures are made with
the object-oriented API (Figure and the Agg canvas), not pyplot, so there is no global figure list to leak
and the functions are safe to call from worker threads.
"""
import io
import math
import os
import re
import threading
import types
from pathlib import Path

import numpy as np

__all__ = ["stems_spectrogram", "piano_roll", "band_chart", "seam_zoom", "ladder_chart"]

DPI = 100
MIN_WIDTH = 360
MAX_WIDTH = 4000
MAX_HEIGHT = 1400                 # hard cap on the height in pixels
PIXEL_BUDGET = 1200000            # soft cap on width * height (about 1,600 vision tokens)
SIZE_BUDGET = 300 * 1024          # bytes; a larger file is re-saved with a reduced palette

# Font sizes in points at 100 dpi. Everything that carries information is at least 10.
FONT = {"title": 15.0, "label": 12.0, "tick": 10.5, "note": 10.5, "value": 11.0, "chord": 11.5}

ELLIPSIS = "\u2026"

INK = "#111111"
MUTED = "#444444"
PANEL = "#eef1f5"
GRID = "#c4cad3"
NO_DATA = "#d4d7dc"
RED = "#d62728"
BLUE = "#2f6db5"
ORANGE = "#e8710a"

# Okabe-Ito: distinguishable by people with colour-vision deficiencies, and by a vision model.
SERIES_COLORS = ("#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#7a6f00", "#222222")

STATUS_COLORS = {"chord": "#1a9850", "scale": "#f5a300", "out": "#d62728", "other": "#8a8f98"}
STATUS_LABELS = {"chord": "chord tone", "scale": "scale tone", "out": "out of key", "other": "unclassified"}

# Spectrogram
SPEC_FMIN = 30.0
SPEC_FMAX = 16000.0
SPEC_DB = (-90.0, -10.0)
SPEC_STEP_DB = 2.5                               # levels are drawn in steps of this size (32 colours)
SPEC_CMAP = "magma"
SPEC_FFT_SIZES = (512, 1024, 2048, 4096, 8192)   # at 44.1 kHz; scaled with the sample rate
SPEC_HALF_WIDTH = 0.0578                         # +/- 1/12 octave around a row's centre: a 1/6-octave band
SPEC_FLOOR_DB = -120.0
FREQ_TICKS_FULL = ((50, "50"), (100, "100"), (200, "200"), (500, "500"), (1000, "1k"), (2000, "2k"),
                   (5000, "5k"), (10000, "10k"))
FREQ_TICKS_MEDIUM = ((100, "100"), (300, "300"), (1000, "1k"), (3000, "3k"), (10000, "10k"))
FREQ_TICKS_FEW = ((100, "100"), (1000, "1k"), (10000, "10k"))

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
BLACK_KEYS = (1, 3, 6, 8, 10)

_RC = {"font.family": "DejaVu Sans", "font.size": 11.0, "axes.unicode_minus": False, "axes.linewidth": 1.0,
       "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
       "axes.edgecolor": INK, "figure.dpi": DPI, "savefig.dpi": DPI, "text.usetex": False}

_MPL = None
_LOCK = threading.RLock()      # matplotlib's rcParams and font caches are global: one picture at a time


# ----------------------------------------------------------------------------------------------------------
# Plumbing: lazy matplotlib, a page laid out in pixels, argument checks
# ----------------------------------------------------------------------------------------------------------

def _mpl():
    """matplotlib on first use: Agg backend, no pyplot."""
    global _MPL
    if _MPL is None:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import colors, patheffects, patches, collections, ticker
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.cm import ScalarMappable
        from matplotlib.figure import Figure
        _MPL = types.SimpleNamespace(
            Figure=Figure, FigureCanvasAgg=FigureCanvasAgg, ScalarMappable=ScalarMappable,
            BoundaryNorm=colors.BoundaryNorm, Patch=patches.Patch, Rectangle=patches.Rectangle,
            PatchCollection=collections.PatchCollection, FixedLocator=ticker.FixedLocator,
            withStroke=patheffects.withStroke, colormap=matplotlib.colormaps.__getitem__,
            rc_context=matplotlib.rc_context)
    return _MPL


class _Page(object):
    """A figure laid out in pixels, origin top-left, saved as a PNG exactly `width` pixels wide.

    Plan the layout first (`measure` and `fit` are for that), call `resize(height)` once, then draw.
    """

    def __init__(self, mpl, width):
        self.mpl = mpl
        self.width = int(width)
        self.height = MAX_HEIGHT
        self.fig = mpl.Figure(figsize=(self._inches(self.width), self._inches(self.height)), dpi=DPI,
                              facecolor="white")
        mpl.FigureCanvasAgg(self.fig)

    @staticmethod
    def _inches(pixels):
        return (pixels + 0.01) / DPI        # +0.01 px so int(figsize * dpi) never loses a pixel

    def resize(self, height):
        if self.fig.axes or self.fig.texts or self.fig.legends:
            raise RuntimeError("resize the page before drawing on it")
        self.height = int(min(max(math.ceil(height), 100), MAX_HEIGHT))
        self.fig.set_size_inches(self._inches(self.width), self._inches(self.height))

    def axes(self, left, top, width, height, **kwargs):
        return self.fig.add_axes([left / float(self.width), 1.0 - (top + height) / float(self.height),
                                  width / float(self.width), height / float(self.height)], **kwargs)

    def text(self, x, y, s, **kwargs):
        kwargs.setdefault("ha", "left")
        kwargs.setdefault("va", "top")
        return self.fig.text(x / float(self.width), 1.0 - y / float(self.height), s, **kwargs)

    def legend(self, handles, x, y, **kwargs):
        """A legend whose top-left corner is at pixel (x, y)."""
        options = dict(loc="upper left", fontsize=FONT["value"], frameon=False, handlelength=1.6,
                       columnspacing=1.8, borderpad=0.1, borderaxespad=0.0)
        options.update(kwargs)
        return self.fig.legend(handles=handles, bbox_to_anchor=(x / float(self.width), 1.0 - y / float(self.height)),
                               **options)

    def measure(self, s, size=FONT["tick"], weight="normal"):
        """(width, height) in pixels of a text."""
        artist = self.fig.text(0, 0, s, fontsize=size, fontweight=weight)
        box = artist.get_window_extent(self.fig.canvas.get_renderer())
        artist.remove()
        return box.width, box.height

    def fit(self, s, max_px, size, weight="normal", min_size=10.0):
        """The text and font size that fit in max_px: shrink to min_size, then cut with an ellipsis."""
        s = _plain(s)
        while size > min_size and self.measure(s, size, weight)[0] > max_px:
            size -= 0.5
        while len(s) > 1 and self.measure(s, size, weight)[0] > max_px:
            s = s[:-2].rstrip() + ELLIPSIS
        return s, size

    def save(self, target):
        """Write the PNG: RGB, optimized; the largest palette that fits the size budget if it is too big."""
        canvas = self.fig.canvas
        canvas.draw()
        from PIL import Image
        rgb = np.ascontiguousarray(np.asarray(canvas.buffer_rgba())[:, :, :3])
        image = Image.fromarray(rgb)
        data = _encode(image)
        if len(data) > SIZE_BUDGET:
            median_cut = getattr(getattr(Image, "Quantize", Image), "MEDIANCUT")      # Pillow 8 has no Image.Quantize
            no_dither = getattr(getattr(Image, "Dither", Image), "NONE")
            for colors in (256, 128, 96, 64, 48, 32):
                reduced = _encode(image.quantize(colors=colors, method=median_cut, dither=no_dither))
                if len(reduced) < len(data):
                    data = reduced
                if len(data) <= SIZE_BUDGET:
                    break
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        part.write_bytes(data)
        os.replace(str(part), str(target))
        return str(target)

    def close(self):
        self.fig.clear()


def _encode(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _plain(text):
    """Text for matplotlib: no mathtext surprises."""
    return str(text).replace("$", "\\$")


def _target(path):
    if path is None or str(path) == "":
        raise ValueError("path is required: where to write the PNG")
    return Path(str(path)).expanduser()


def _positive(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("{0} must be a positive number, got {1!r}".format(name, value))
    if not math.isfinite(number) or number <= 0:
        raise ValueError("{0} must be a positive number, got {1!r}".format(name, value))
    return number


def _clamp_width(width):
    try:
        number = int(round(float(width)))
    except (TypeError, ValueError):
        number = 1200
    return max(MIN_WIDTH, min(MAX_WIDTH, number))


def _soft_height(width):
    """The height that keeps width * height within the pixel budget."""
    return int(min(MAX_HEIGHT, max(480, PIXEL_BUDGET // width)))


def _fit_height(units, blocks, top, bottom, width, ideal, floors, gaps):
    """How tall a unit (a spectrogram row, a semitone) can be so that `units` units, in `blocks` blocks, fit.

    Returns (pixels per unit, pixels between blocks, spare pixels). The ideal size if there is room; else
    the largest that keeps the picture within the soft height budget (floors[0] at least); else the hard
    1400 px cap (floors[1]); else the cap with smaller gaps and any size. Content never runs off the page.
    """
    attempts = ((_soft_height(width), floors[0], gaps[0]), (MAX_HEIGHT, floors[1], gaps[0]), (MAX_HEIGHT, 0.0, gaps[1]))
    for budget, floor, gap in attempts:
        avail = budget - top - bottom - gap * (blocks - 1)
        if avail > 0:
            scale = min(ideal, avail / float(units))
            if scale >= floor:
                return scale, gap, avail - scale * units
    avail = MAX_HEIGHT - top - bottom - (blocks - 1)
    return max(avail / float(units), 0.05), 1, 0.0


def _number(value):
    """A finite float, or None."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fmt(value, digits=1):
    text = "{0:.{1}f}".format(value, digits)
    return "0.0" if text in ("-0.0", "-0") else text


def _g(value):
    return "{0:g}".format(value)


def _style_axes(ax, bottom=True):
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)
        spine.set_color(INK)
    ax.tick_params(axis="both", which="major", labelsize=FONT["tick"], length=4, width=1, colors=INK)
    ax.tick_params(axis="x", which="minor", length=2, width=0.8)
    if not bottom:
        ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)


def _message(ax, text):
    ax.text(0.5, 0.5, text, transform=ax.transAxes, ha="center", va="center", fontsize=FONT["label"],
            color=MUTED, zorder=10)


def _wrap(page, text, max_px, size, limit=3):
    """Word-wrap a text into lines no wider than max_px (at most `limit` lines)."""
    lines = []
    line = ""
    for word in _plain(text).split():
        trial = (line + " " + word).strip()
        if line and page.measure(trial, size)[0] > max_px:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    if len(lines) > limit:
        lines = lines[:limit]
        lines[-1] = lines[-1].rstrip(" .,;") + ELLIPSIS
    return lines


def _legend_layout(page, texts, avail):
    """(columns, rows) for a legend of these entries in `avail` pixels: one row if it fits, else wrapped."""
    if not texts:
        return 0, 0
    widths = [page.measure(_plain(text), FONT["value"])[0] + 66 for text in texts]
    columns = len(texts) if sum(widths) <= avail else max(1, min(len(texts), int(avail // max(widths))))
    return columns, int(math.ceil(len(texts) / float(columns)))


def _subtitle_lines(page, subtitle):
    return _wrap(page, subtitle, page.width - 28, FONT["note"]) if subtitle else []


def _header_height(lines):
    return 10 + 25 + 19 * len(lines) + 4


def _header(page, title, lines, left=14, top=10):
    """Title and subtitle lines at the top-left; returns the y in pixels where content can start."""
    text, size = page.fit(title, page.width - 2 * left, FONT["title"], "bold", min_size=11.0)
    page.text(left, top, text, fontsize=size, fontweight="bold", color=INK)
    for i, line in enumerate(lines):
        page.text(left, top + 25 + 19 * i, line, fontsize=FONT["note"], color=MUTED)
    return top + _header_height(lines) - 10


# ----------------------------------------------------------------------------------------------------------
# Time axis in bars (stems and piano roll)
# ----------------------------------------------------------------------------------------------------------

RULER_NUMBERS_H = 22
RULER_CHORDS_H = 28


def _label_step(px_per_unit, min_px):
    """1, 2, 4, 8 ...: the smallest step that leaves min_px between labels."""
    step = 1
    while step * px_per_unit < min_px and step < 65536:
        step *= 2
    return step


def _bar_positions(x_end, step=1):
    last = int(math.floor(x_end + 1e-9))
    return list(range(0, last + 1, step))


def _bar_lines(ax, x_end, px_per_bar, color, alpha, width):
    """Vertical bar lines over a whole axes; every fourth bar is heavier."""
    step = 1 if px_per_bar >= 6 else _label_step(px_per_bar, 6)
    xs = _bar_positions(x_end, step)
    if not xs:
        return
    ax.vlines(xs, 0, 1, transform=ax.get_xaxis_transform(), colors=color, linewidths=width, alpha=alpha,
              zorder=4)
    heavy = [x for x in xs if x > 0 and x % 4 == 0]
    if heavy and x_end > 4:
        ax.vlines(heavy, 0, 1, transform=ax.get_xaxis_transform(), colors=color, linewidths=width * 1.9,
                  alpha=min(1.0, alpha + 0.25), zorder=4)


def _bar_axis(ax, x_end, px_per_bar, beats_per_bar, px_per_beat):
    """Bottom axis in bars: tick at the start of each bar, labelled 1-based; beats as minor ticks.

    Returns True when the beat ticks are drawn.
    """
    step = _label_step(px_per_bar, 34)
    ticks = _bar_positions(x_end, step)
    ax.set_xticks(ticks)
    ax.set_xticklabels([("end" if b >= x_end - 1e-6 and b > 0 else str(b + 1)) for b in ticks],
                       fontsize=FONT["tick"])
    beats = px_per_beat >= 9 and beats_per_bar >= 1
    if beats:
        count = int(math.ceil(x_end * beats_per_bar))
        minor = [k / float(beats_per_bar) for k in range(0, count + 1) if k / float(beats_per_bar) <= x_end + 1e-9]
        ax.xaxis.set_minor_locator(_mpl().FixedLocator(minor))
    ax.set_xlim(0, x_end)
    return beats


def _bar_label(beats):
    return "bar (1-based; the small ticks are beats)" if beats else "bar (1-based)"


def _chord_names(chords):
    if not chords:
        return []
    if isinstance(chords, str):
        chords = [name for name in re.split(r"[\s,|]+", chords) if name]
    return ["" if name is None else str(name) for name in chords]


def _ruler_height(chords):
    return RULER_NUMBERS_H + (RULER_CHORDS_H if _chord_names(chords) else 0)


def _ruler(page, left, top, plot_w, x_end, chords):
    """Bar numbers (1-based, at each bar's start) and chord names (centred in their bars) above a plot.

    Returns the y in pixels under the strip.
    """
    px_per_bar = plot_w / float(x_end)
    nbars = int(math.ceil(x_end - 1e-9))
    step = _label_step(px_per_bar, 30)
    ax = page.axes(left, top, plot_w, RULER_NUMBERS_H)
    ax.set_xlim(0, x_end)
    ax.set_ylim(0, 1)
    ax.axis("off")
    for b in range(0, nbars, step):
        ax.plot([b, b], [0.0, 0.55], color=INK, lw=1.0, clip_on=False, solid_capstyle="butt")
        ax.text(b, 0.45, str(b + 1), ha="left", va="bottom", fontsize=FONT["tick"], color=INK, clip_on=False)
    y = top + RULER_NUMBERS_H
    names = _chord_names(chords)
    if names:
        strip = page.axes(left, y, plot_w, RULER_CHORDS_H)
        strip.set_xlim(0, x_end)
        strip.set_ylim(0, 1)
        strip.set_facecolor(PANEL)
        strip.set_xticks([])
        strip.set_yticks([])
        for spine in strip.spines.values():
            spine.set_color(GRID)
        labels = [names[b % len(names)] for b in range(nbars)]
        widest = max(page.measure(_plain(name), FONT["chord"], "bold")[0] for name in labels) if labels else 0
        if widest > px_per_bar - 8:
            # no room for every bar: name a chord where it changes
            labels = [name if (i == 0 or name != labels[i - 1]) else "" for i, name in enumerate(labels)]
        edge = -1e9
        for b, name in enumerate(labels):
            span = min(1.0, x_end - b)
            if not name or span < 0.3:
                continue
            centre = b + span / 2.0
            half = page.measure(_plain(name), FONT["chord"], "bold")[0] / 2.0
            x_px = centre * px_per_bar
            if x_px - half < edge + 4:
                continue
            edge = x_px + half
            strip.text(centre, 0.5, _plain(name), ha="center", va="center", fontsize=FONT["chord"],
                       fontweight="bold", color=INK, clip_on=True)
        _bar_lines(strip, x_end, px_per_bar, GRID, 1.0, 1.0)
        y += RULER_CHORDS_H
    return y


# ----------------------------------------------------------------------------------------------------------
# Spectrogram numerics
# ----------------------------------------------------------------------------------------------------------

def _duration(audio):
    samples = getattr(audio, "samples", None)
    rate = getattr(audio, "rate", 0)
    if samples is None or not rate:
        return 0.0
    return int(np.asarray(samples).shape[0]) / float(rate)


def _channels(audio, limit):
    """Up to `limit` channels of an Audio as 1-D float arrays (NaN and infinity removed)."""
    samples = np.asarray(getattr(audio, "samples", np.zeros((0, 1))), dtype=np.float64)
    if samples.ndim == 1:
        samples = samples[:, None]
    samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
    return [np.ascontiguousarray(samples[:, c]) for c in range(min(samples.shape[1], limit))]


def _channel_count(audio):
    samples = np.asarray(getattr(audio, "samples", np.zeros((0, 1))))
    return 1 if samples.ndim == 1 else int(samples.shape[1])


def _fft_sizes(rate):
    """The analysis windows, scaled with the sample rate so they last the same time."""
    scale = rate / 44100.0
    return sorted(set(int(2 ** int(round(math.log2(size * scale)))) for size in SPEC_FFT_SIZES))


def _pick_size(sizes, rate, centre):
    """The shortest window whose frequency resolution is finer than a 1/6-octave band at `centre`.

    A Hann window of n samples resolves about 4 * rate / n Hz; the band is 2 * SPEC_HALF_WIDTH * centre wide.
    Below the longest window's reach the longest is used.
    """
    for size in sizes:
        if 4.0 * rate / size <= 2.0 * SPEC_HALF_WIDTH * centre:
            return size
    return sizes[-1]


def _band_power(channels, rate, size, dt, ncols, centres):
    """Mean-square power in a band around each centre frequency, for each time column.

    Returns (ncols, len(centres)). The power of a full-scale sine is 0.5, so 10*log10(2*power) is its
    level in dBFS. Each column averages the frames inside it (so a click is not skipped when the column is
    wider than the window); a column narrower than the hop gets one frame centred on it.
    """
    bins = size // 2 + 1
    df = rate / float(size)
    window = 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(size) / size)
    scale = 1.0 / (size * float(np.sum(window * window)))
    fold = np.full(bins, 2.0)
    fold[0] = 1.0
    if size % 2 == 0:
        fold[-1] = 1.0
    # band edges in "edge index" space: bin k covers edges k..k+1; power is spread evenly inside a bin
    half = np.maximum(SPEC_HALF_WIDTH * centres, 2.0 * df)
    pos = np.clip(np.stack([(centres - half) / df + 0.5, (centres + half) / df + 0.5]), 0.0, bins - 1e-9)
    lo = np.floor(pos).astype(np.int64)
    frac = pos - lo
    per_column = max(1, int(math.ceil(dt / (size / 4.0))))
    result = np.zeros((ncols, len(centres)))
    pad = size + int(dt) + 2
    chunk_columns = max(1, 2000000 // (size * per_column))
    offsets = np.arange(size)
    for samples in channels:
        padded = np.concatenate([np.zeros(pad), samples, np.zeros(pad + size)])
        for first in range(0, ncols, chunk_columns):
            last = min(ncols, first + chunk_columns)
            columns = np.arange(first, last, dtype=np.float64)
            centre = (columns[:, None] + (np.arange(per_column)[None, :] + 0.5) / per_column) * dt
            starts = np.round(centre - size / 2.0).astype(np.int64).reshape(-1) + pad
            frames = padded[starts[:, None] + offsets[None, :]] * window
            spectrum = np.fft.rfft(frames, axis=1)
            power = (spectrum.real ** 2 + spectrum.imag ** 2) * (scale * fold)
            cumulative = np.concatenate([np.zeros((power.shape[0], 1)), np.cumsum(power, axis=1)], axis=1)
            upper = cumulative[:, lo[1]] * (1.0 - frac[1]) + cumulative[:, lo[1] + 1] * frac[1]
            lower = cumulative[:, lo[0]] * (1.0 - frac[0]) + cumulative[:, lo[0] + 1] * frac[0]
            band = np.maximum(upper - lower, 0.0).reshape(last - first, per_column, len(centres)).mean(axis=1)
            result[first:last] += band
    return result / max(1, len(channels))


def _spectrogram_levels(audio, dt, ncols, nrows, fmin=SPEC_FMIN, fmax=SPEC_FMAX):
    """Level of every cell in dBFS, shape (nrows, ncols), row 0 = lowest frequency, log-spaced rows.

    A cell is the power in the 1/6-octave band around its row (widened to the analysis resolution
    below about 190 Hz) during its time column; a full-scale sine reads 0 dBFS. Windows get shorter with
    frequency (8192 samples for the bass down to 512 for the highs) so bass notes are told apart and
    hi-hat hits are placed in time.
    """
    channels = _channels(audio, 2)
    rate = int(audio.rate)
    edges = np.geomspace(fmin, fmax, nrows + 1)
    centres = np.sqrt(edges[:-1] * edges[1:])
    levels = np.full((nrows, ncols), SPEC_FLOOR_DB, dtype=np.float32)
    if not channels or channels[0].size == 0 or ncols <= 0:
        return levels
    sizes = _fft_sizes(rate)
    chosen = np.array([_pick_size(sizes, rate, c) for c in centres])
    dt_samples = dt * rate
    for size in sorted(set(chosen.tolist())):
        rows = np.nonzero(chosen == size)[0]
        power = _band_power(channels, rate, size, dt_samples, ncols, centres[rows])
        levels[rows, :] = (10.0 * np.log10(2.0 * power.T + 1e-12)).astype(np.float32)
    return levels


# ----------------------------------------------------------------------------------------------------------
# 1. Stem spectrograms
# ----------------------------------------------------------------------------------------------------------

def stems_spectrogram(stems, bpm, beats_per_bar=4.0, chords=None, path=None, width=1200, title=None):
    """One spectrogram row per stem, stacked on one time axis in bars (1-based), PNG at `path`.

    stems: list of (label, Audio). Each row is log frequency from 30 Hz to 16 kHz; the colour is the level
    of a 1/6-octave band in dBFS (steps of 2.5 dB) on one fixed scale, -90 to -10, for every row, so stems
    are comparable. A stem shorter than the longest ends where its audio ends (grey beyond). Vertical lines
    mark bars (every fourth is heavier). `chords` is a list of chord names, one per bar, drawn along the
    top and repeated when shorter than the audio.
    """
    target = _target(path)
    bpm = _positive(bpm, "bpm")
    beats_per_bar = _positive(beats_per_bar, "beats_per_bar")
    width = _clamp_width(width)
    items = [(str(label), audio) for label, audio in list(stems or [])]
    bar_s = beats_per_bar * 60.0 / bpm
    durations = [_duration(audio) for _, audio in items]
    x_end = max([d / bar_s for d in durations] + [1.0])
    mpl = _mpl()
    with _LOCK, mpl.rc_context(_RC):
        page = _Page(mpl, width)
        try:
            # ---- plan (pixels)
            captions = ["{0} bars".format(_fmt(d / bar_s, 1)) for d in durations]
            label_w = max([page.measure(_plain(name), FONT["label"], "bold")[0] for name, _ in items]
                          + [page.measure(text, FONT["note"])[0] for text in captions] + [40.0])
            left = int(min(max(label_w + 10 + 8 + 38, 96), max(0.22 * width, 110)))
            right = int(min(92, max(64, 0.1 * width)))
            plot_w = width - left - right
            subtitle = ("{0} BPM, {1} beats per bar (1 bar = {2:.2f} s). Frequency in Hz, log scale. "
                        "Colour = level in dBFS per 1/6-octave band (a full-scale sine reads 0).").format(
                _g(bpm), _g(beats_per_bar), bar_s)
            head = _subtitle_lines(page, subtitle)
            rows_top = _header_height(head) + _ruler_height(chords) + 4
            n = max(1, len(items))
            bottom = 72
            scale, gap, _ = _fit_height(n, n, rows_top, bottom, width, 200.0, (90.0, 40.0), (6, 2))
            row_h = int(max(2, scale))
            if not items:
                row_h = 120
            rows_h = n * row_h + (n - 1) * gap
            page.resize(rows_top + rows_h + bottom)
            # ---- draw
            _header(page, title or "Stem spectrograms", head)
            _ruler(page, left, _header_height(head), plot_w, x_end, chords)
            ncols = int(plot_w)
            dt = x_end * bar_s / ncols
            px_per_bar = plot_w / x_end
            px_per_beat = px_per_bar / beats_per_bar
            boundaries = np.arange(SPEC_DB[0], SPEC_DB[1] + SPEC_STEP_DB / 2.0, SPEC_STEP_DB)
            colors = len(boundaries) - 1
            norm = mpl.BoundaryNorm(boundaries, ncolors=colors, clip=True)
            cmap = mpl.colormap(SPEC_CMAP).resampled(colors)
            ylo, yhi = math.log10(SPEC_FMIN), math.log10(SPEC_FMAX)
            octaves = math.log2(SPEC_FMAX / SPEC_FMIN)
            per_octave = row_h / octaves
            if per_octave >= 16:
                ticks = FREQ_TICKS_FULL
            elif per_octave >= 10.5:
                ticks = FREQ_TICKS_MEDIUM
            elif row_h >= 40:
                ticks = FREQ_TICKS_FEW
            elif row_h >= 20:
                ticks = ((1000, "1k"),)
            else:
                ticks = ()
            if not items:
                ax = page.axes(left, rows_top, plot_w, row_h)
                ax.set_facecolor(NO_DATA)
                _message(ax, "no stems to draw")
                _style_axes(ax)
                beats = _bar_axis(ax, x_end, px_per_bar, beats_per_bar, px_per_beat)
                ax.set_xlabel(_bar_label(beats), fontsize=FONT["label"])
                ax.set_yticks([])
            for i, (name, audio) in enumerate(items):
                top = rows_top + i * (row_h + gap)
                ax = page.axes(left, top, plot_w, row_h)
                ax.set_facecolor(NO_DATA)
                duration = durations[i]
                if duration > 0:
                    ncols_stem = min(ncols, max(1, int(math.ceil(duration / dt - 1e-9))))
                    levels = _spectrogram_levels(audio, dt, ncols_stem, row_h)
                    ax.imshow(levels, origin="lower", aspect="auto", interpolation="nearest", cmap=cmap, norm=norm,
                              extent=(0, ncols_stem * dt / bar_s, ylo, yhi))
                else:
                    _message(ax, "empty")
                ax.set_xlim(0, x_end)
                ax.set_ylim(ylo, yhi)
                ax.set_yticks([math.log10(f) for f, _ in ticks])
                ax.set_yticklabels([text for _, text in ticks], fontsize=FONT["tick"])
                for f, _ in ticks:
                    ax.axhline(math.log10(f), color="white", alpha=0.22, lw=0.7, ls=(0, (4, 4)), zorder=3)
                _bar_lines(ax, x_end, px_per_bar, "white", 0.45, 0.8)
                last = i == len(items) - 1
                _style_axes(ax, bottom=last)
                if last:
                    beats = _bar_axis(ax, x_end, px_per_bar, beats_per_bar, px_per_beat)
                    ax.set_xlabel(_bar_label(beats), fontsize=FONT["label"])
                text, size = page.fit(name, left - 38 - 14, FONT["label"], "bold")
                if duration > 0 and row_h >= 40:
                    page.text(10, top + row_h / 2.0 - 2, text, fontsize=size, fontweight="bold", va="bottom")
                    page.text(10, top + row_h / 2.0, captions[i], fontsize=FONT["note"], color=MUTED, va="top")
                else:
                    page.text(10, top + row_h / 2.0, text, fontsize=size, fontweight="bold", va="center")
            cax = page.axes(width - right + 22, rows_top, 18, rows_h)
            colorbar = page.fig.colorbar(mpl.ScalarMappable(norm=norm, cmap=cmap), cax=cax)
            colorbar.set_ticks([-90, -70, -50, -30, -10])
            cax.tick_params(labelsize=FONT["tick"], length=4, width=1)
            colorbar.outline.set_linewidth(1.0)
            page.text(width - right + 14, rows_top - 20, "dBFS", fontsize=FONT["label"], fontweight="bold")
            return page.save(target)
        finally:
            page.close()


# ----------------------------------------------------------------------------------------------------------
# 2. Piano roll
# ----------------------------------------------------------------------------------------------------------

def _note_name(pitch):
    """Live's convention: MIDI 60 is C3 (so 0 is C-2)."""
    pitch = int(pitch)
    return "{0}{1}".format(NOTE_NAMES[pitch % 12], pitch // 12 - 2)


def _pitch_classes_to_label(px_per_semitone):
    """Which pitch classes get a label so that labels are at least 15 px apart."""
    if px_per_semitone >= 15:
        return set(range(12))
    if px_per_semitone >= 7.5:
        return {0, 2, 4, 7, 9}
    if px_per_semitone >= 5:
        return {0, 4, 7}
    return {0}


def _clean_roll(roll):
    notes = []
    for entry in list(roll or []):
        if not isinstance(entry, dict):
            continue
        pitch = _number(entry.get("pitch"))
        start = _number(entry.get("start"))
        duration = _number(entry.get("duration"))
        if pitch is None or start is None:
            continue
        status = str(entry.get("status") or "").lower()
        if status not in STATUS_COLORS:
            status = "other" if status else "scale"
        part = entry.get("part")
        notes.append({"part": str(part) if part not in (None, "") else "notes",
                      "pitch": int(round(pitch)), "start": start,
                      "duration": max(duration if duration is not None else 0.0, 0.0), "status": status,
                      "name": str(entry.get("name") or _note_name(int(round(pitch))))})
    return notes


def piano_roll(roll, bars, beats_per_bar=4.0, chords=None, path=None, width=1200, title=None):
    """Notes as rectangles coloured by chord-tone status, one lane group per part, PNG at `path`.

    roll: list of {part, pitch (MIDI), name, start (beats), duration (beats), status}, status being
    "chord" (green), "scale" (amber) or "out" (red, named on the picture). Lanes follow the order in
    which parts first appear and share one semitone height; pitches are labelled in Live's convention
    (C3 = 60). `bars` is the number of bars drawn (notes beyond it are cut; None or 0 fits the notes).
    Bar numbers and chord names (one per bar, repeated when shorter) run along the top.
    """
    target = _target(path)
    beats_per_bar = _positive(beats_per_bar, "beats_per_bar")
    width = _clamp_width(width)
    notes = _clean_roll(roll)
    bars_value = _number(bars)
    if bars_value is None or bars_value <= 0:
        longest = max([n["start"] + n["duration"] for n in notes] + [0.0])
        bars_value = max(1.0, math.ceil(longest / beats_per_bar - 1e-9))
    x_end = float(bars_value)
    total_beats = x_end * beats_per_bar
    drawn = [n for n in notes if n["start"] < total_beats - 1e-9 and n["start"] + max(n["duration"], 1e-6) > 0]
    hidden = len(notes) - len(drawn)
    notes = drawn
    parts = []
    for note in notes:
        if note["part"] not in parts:
            parts.append(note["part"])
    mpl = _mpl()
    with _LOCK, mpl.rc_context(_RC):
        page = _Page(mpl, width)
        try:
            # ---- plan
            counts = dict((status, 0) for status in STATUS_COLORS)
            for note in notes:
                counts[note["status"]] += 1
            label_w = max([page.measure(_plain(p), FONT["label"], "bold")[0] for p in parts] + [30.0])
            left = int(min(label_w + 10 + 8 + 44, 0.32 * width))
            right = 22
            plot_w = width - left - right
            subtitle = "{0} bars of {1} beats, {2} note{3}{4}. Pitch names follow Live (C3 = MIDI 60).".format(
                _g(x_end), _g(beats_per_bar), len(notes), "" if len(notes) == 1 else "s",
                " ({0} more fall outside these bars and are not drawn)".format(hidden) if hidden else "")
            head = _subtitle_lines(page, subtitle)
            legend_y = _header_height(head)
            entries = [(s, "{0} ({1})".format(STATUS_LABELS[s], counts[s])) for s in ("chord", "scale", "out")]
            if counts["other"]:
                entries.append(("other", "{0} ({1})".format(STATUS_LABELS["other"], counts["other"])))
            ncol, legend_rows = _legend_layout(page, [text for _, text in entries], width - 28)
            ruler_y = legend_y + legend_rows * 22 + 6
            lanes_top = ruler_y + _ruler_height(chords) + 4
            lanes = []
            for part in parts:
                pitches = [n["pitch"] for n in notes if n["part"] == part]
                lanes.append([min(pitches) - 1, max(pitches) + 1])
            if not lanes:
                lanes = [[48, 72]]
            bottom = 72
            semitone, gap, slack = _fit_height(sum(hi - lo + 1 for lo, hi in lanes), len(lanes), lanes_top, bottom,
                                               width, 12.0, (5.0, 2.5), (12, 4))
            for lane in lanes:
                # a short lane gets padding up to 90 px, as far as the spare height allows
                rows = int(math.ceil(max(0.0, 90.0 - (lane[1] - lane[0] + 1) * semitone) / semitone))
                rows += rows % 2
                if rows and rows * semitone <= slack:
                    slack -= rows * semitone
                    lane[0] = max(lane[0] - rows // 2, -2)
                    lane[1] = min(lane[1] + rows // 2, 127)
            heights = [max(4, int(round((hi - lo + 1) * semitone))) for lo, hi in lanes]
            page.resize(lanes_top + sum(heights) + gap * (len(lanes) - 1) + bottom)
            note_h = 0.86 if semitone >= 8 else 1.0                    # small lanes: notes fill their row
            edge = 0.8 if semitone >= 8 else (0.5 if semitone >= 4 else 0.0)
            # ---- draw
            _header(page, title or "Piano roll by chord-tone status", head)
            handles = [mpl.Patch(facecolor=STATUS_COLORS[s], edgecolor=INK, linewidth=1.0, label=text)
                       for s, text in entries]
            page.legend(handles, 14, legend_y, ncol=ncol, handleheight=1.1)
            _ruler(page, left, ruler_y, plot_w, x_end, chords)
            px_per_bar = plot_w / x_end
            px_per_beat = px_per_bar / beats_per_bar
            label_set = _pitch_classes_to_label(semitone)
            top = lanes_top
            for index, (lo, hi) in enumerate(lanes):
                last = index == len(lanes) - 1
                ax = page.axes(left, top, plot_w, heights[index])
                _style_axes(ax, bottom=last)
                ax.set_xlim(0, x_end)
                ax.set_ylim(lo - 0.5, hi + 0.5)
                for pitch in range(lo, hi + 1):
                    if pitch % 12 in BLACK_KEYS:
                        ax.axhspan(pitch - 0.5, pitch + 0.5, facecolor="#eceff3", edgecolor="none", zorder=0)
                for pitch in range(lo, hi + 2):
                    if pitch % 12 == 0:
                        ax.axhline(pitch - 0.5, color="#8e96a3", lw=1.0, zorder=1)
                    elif semitone >= 6 and pitch % 12 == 5:
                        ax.axhline(pitch - 0.5, color=GRID, lw=0.7, zorder=1)
                tick_pitches = [p for p in range(lo, hi + 1) if p % 12 in label_set]
                ax.set_yticks(tick_pitches)
                ax.set_yticklabels([_note_name(p) for p in tick_pitches], fontsize=FONT["tick"])
                if px_per_beat >= 9:
                    whole = int(max(1, round(beats_per_bar)))
                    beat_x = [k / float(beats_per_bar) for k in range(1, int(math.ceil(x_end * beats_per_bar)))
                              if k % whole != 0 and k / float(beats_per_bar) < x_end]
                    if beat_x:
                        ax.vlines(beat_x, 0, 1, transform=ax.get_xaxis_transform(), colors=GRID, linewidths=0.6,
                                  zorder=1)
                _bar_lines(ax, x_end, px_per_bar, "#5d6673", 0.9, 0.9)
                if last:
                    beats = _bar_axis(ax, x_end, px_per_bar, beats_per_bar, px_per_beat)
                    ax.set_xlabel(_bar_label(beats), fontsize=FONT["label"])
                if not parts:
                    _message(ax, "no notes")
                    break
                part = parts[index]
                text, size = page.fit(part, left - 44 - 18, FONT["label"], "bold")
                page.text(10, top + heights[index] / 2.0, text, fontsize=size, fontweight="bold", va="center")
                mine = [n for n in notes if n["part"] == part]
                for status in ("chord", "scale", "other", "out"):
                    rects = []
                    for n in mine:
                        if n["status"] != status:
                            continue
                        x0 = n["start"] / beats_per_bar
                        w = max(n["duration"] / beats_per_bar, 1.6 / px_per_bar)
                        if x0 >= x_end or x0 + w <= 0 or not lo <= n["pitch"] <= hi:
                            continue
                        rects.append(mpl.Rectangle((x0, n["pitch"] - note_h / 2.0), w, note_h))
                    if rects:
                        ax.add_collection(mpl.PatchCollection(
                            rects, facecolor=STATUS_COLORS[status], edgecolor=INK,
                            linewidth=(1.4 if semitone >= 8 else edge) if status == "out" else edge, zorder=6))
                # name the out-of-key notes, each in a free spot (above, below, right, left), never over a note
                taken = [(n["start"] / beats_per_bar,
                          n["start"] / beats_per_bar + max(n["duration"] / beats_per_bar, 1.6 / px_per_bar),
                          n["pitch"] - note_h / 2.0, n["pitch"] + note_h / 2.0) for n in mine]
                label_h = (FONT["note"] * DPI / 72.0 + 3.0) / semitone
                marked = 0
                for n in sorted((n for n in mine if n["status"] == "out"), key=lambda item: item["start"]):
                    if semitone < 6 or marked >= 14:
                        break
                    name = _plain(n["name"])
                    label_w = (page.measure(name, FONT["note"], "bold")[0] + 4.0) / px_per_bar
                    x0 = n["start"] / beats_per_bar
                    w = max(n["duration"] / beats_per_bar, 1.6 / px_per_bar)
                    p = n["pitch"]
                    nudge = 2.0 / px_per_bar
                    options = [
                        (x0, p + 0.5, "left", "bottom", (x0, x0 + label_w, p + 0.5, p + 0.5 + label_h)),
                        (x0, p - 0.5, "left", "top", (x0, x0 + label_w, p - 0.5 - label_h, p - 0.5)),
                        (x0 + w + nudge, p, "left", "center",
                         (x0 + w, x0 + w + label_w, p - label_h / 2, p + label_h / 2)),
                        (x0 - nudge, p, "right", "center", (x0 - label_w, x0, p - label_h / 2, p + label_h / 2)),
                    ]
                    for x, y, ha, va, box in options:
                        if box[0] < 0 or box[1] > x_end or box[2] < lo - 0.5 or box[3] > hi + 0.5:
                            continue
                        if any(box[0] < t[1] and t[0] < box[1] and box[2] < t[3] and t[2] < box[3] for t in taken):
                            continue
                        ax.text(x, y, name, fontsize=FONT["note"], fontweight="bold", color="#8b0000", ha=ha, va=va,
                                zorder=8, path_effects=[mpl.withStroke(linewidth=2.5, foreground="white")])
                        taken.append(box)
                        marked += 1
                        break
                top += heights[index] + gap
            return page.save(target)
        finally:
            page.close()


# ----------------------------------------------------------------------------------------------------------
# 3. Band chart
# ----------------------------------------------------------------------------------------------------------

def _outside_envelope(table, env):
    """(series label, band) for every value that falls outside its band's [low, high] range."""
    return [(label, band) for label, row in table.items() for band, value in row.items()
            if band in env and not env[band][0] - 1e-9 <= value <= env[band][1] + 1e-9]


def band_chart(series, envelope=None, path=None, width=1200, title=None, unit="dB"):
    """Energy per band for one or more series, against a reference envelope, PNG at `path`.

    series: {label: {band_name: value}}, bands in insertion order. Grouped bars (lines when there are more
    than 40 bars). envelope: {band_name: [low, high]} is drawn as a shaded range behind each band; a value
    outside its range gets a red outline. Values that are all negative (levels in dB) are drawn as bars
    rising from the axis minimum, so higher is louder.
    """
    target = _target(path)
    width = _clamp_width(width)
    unit = str(unit if unit is not None else "")
    labels = []
    table = {}
    bands = []
    for label, values in dict(series or {}).items():
        row = {}
        for band, value in dict(values or {}).items():
            band = str(band)
            if band not in bands:
                bands.append(band)
            number = _number(value)
            if number is not None:
                row[band] = number
        labels.append(str(label))
        table[str(label)] = row
    env = {}
    for band, pair in dict(envelope or {}).items():
        try:
            low, high = sorted(float(v) for v in pair)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(low) and math.isfinite(high)):
            continue
        band = str(band)
        env[band] = (low, high)
        if band not in bands:
            bands.append(band)
    mpl = _mpl()
    with _LOCK, mpl.rc_context(_RC):
        page = _Page(mpl, width)
        try:
            # ---- plan
            use_bars = len(labels) * len(bands) <= 40
            everything = [v for row in table.values() for v in row.values()]
            everything += [v for pair in env.values() for v in pair]
            floor_baseline = bool(everything) and max(everything) <= 0 and use_bars
            if everything:
                vmin, vmax = min(everything), max(everything)
                span = max(vmax - vmin, 1.0)
                if floor_baseline:
                    ymin = 5.0 * math.floor((vmin - max(5.0, 0.15 * span)) / 5.0)
                    ymax = vmax + max(0.16 * span, 2.0)
                elif use_bars:
                    ymin = 0.0 if vmin >= 0 else vmin - 0.12 * span
                    ymax = max(0.0, vmax + 0.16 * span)
                else:
                    ymin, ymax = vmin - 0.1 * span, vmax + 0.1 * span
            else:
                ymin, ymax = 0.0, 1.0
            baseline = ymin if floor_baseline else 0.0
            subtitle = "Bars start at the axis minimum; read the value at the bar top." if floor_baseline else None
            outside = _outside_envelope(table, env)
            entries = [(text, SERIES_COLORS[i % len(SERIES_COLORS)], "series") for i, text in enumerate(labels)]
            if env:
                entries.append(("reference envelope (low to high)", "#9aa5b1", "envelope"))
            if outside:
                entries.append(("outside the envelope", RED, "outside"))
            left, right = 92, 26
            plot_w = width - left - right
            ncol, legend_rows = _legend_layout(page, [text for text, _, _ in entries], plot_w)
            head = _subtitle_lines(page, subtitle)
            legend_y = _header_height(head)
            plot_top = legend_y + (legend_rows * 22 + 8 if entries else 0)
            band_px = plot_w / float(max(1, len(bands)))
            label_widths = [page.measure(_plain(b), FONT["tick"])[0] for b in bands]
            rotate = bool(bands) and max(label_widths) > band_px - 8
            bottom = (24 + max(label_widths) * 0.5 + 34) if rotate else 64
            plot_h = 380
            page.resize(plot_top + plot_h + bottom)
            # ---- draw
            _header(page, title or "Band balance ({0})".format(unit or "level"), head)
            if entries:
                handles = []
                for text, color, kind in entries:
                    if kind == "outside":
                        handles.append(mpl.Patch(facecolor="white", edgecolor=color, linewidth=2.5, label=_plain(text)))
                    elif kind == "envelope":
                        handles.append(mpl.Patch(facecolor=color, edgecolor="#5f6b7a", alpha=0.6, label=_plain(text)))
                    else:
                        handles.append(mpl.Patch(facecolor=color, edgecolor=INK, linewidth=0.8, label=_plain(text)))
                page.legend(handles, left, legend_y, ncol=ncol)
            ax = page.axes(left, plot_top, plot_w, plot_h)
            _style_axes(ax)
            ax.set_ylim(ymin, ymax)
            ax.set_xlim(-0.5, max(len(bands), 1) - 0.5)
            ax.yaxis.grid(True, color=GRID, lw=0.8)
            ax.set_axisbelow(True)
            ax.set_ylabel(_plain(unit), fontsize=FONT["label"])
            if not bands or not everything:
                _message(ax, "no data")
            ax.set_xticks(range(len(bands)))
            if rotate:
                ax.set_xticklabels([_plain(b) for b in bands], fontsize=FONT["tick"], rotation=30, ha="right",
                                   rotation_mode="anchor")
            else:
                ax.set_xticklabels([_plain(b) for b in bands], fontsize=FONT["tick"])
            if use_bars:
                for i, band in enumerate(bands):
                    if band in env:
                        low, high = env[band]
                        ax.bar(i, high - low, bottom=low, width=0.94, color="#9aa5b1", alpha=0.45,
                               edgecolor="#5f6b7a", linewidth=1.3, zorder=1)
            else:
                run = []
                for i, band in enumerate(bands + [None]):
                    if band in env:
                        run.append(i)
                        continue
                    if run:
                        edges = np.arange(run[0] - 0.5, run[-1] + 1.0, 1.0)
                        lows = np.array([env[bands[k]][0] for k in run])
                        highs = np.array([env[bands[k]][1] for k in run])
                        ax.stairs(highs, edges, baseline=lows, fill=True, facecolor="#9aa5b1", edgecolor="none",
                                  alpha=0.45, zorder=1)
                        ax.stairs(highs, edges, color="#5f6b7a", linewidth=1.2, zorder=1)
                        ax.stairs(lows, edges, color="#5f6b7a", linewidth=1.2, zorder=1)
                        run = []
            if use_bars and labels:
                slot = 0.8 / len(labels)
                bar_px = slot * band_px
                for j, label in enumerate(labels):
                    color = SERIES_COLORS[j % len(SERIES_COLORS)]
                    xs, heights, edges, widths = [], [], [], []
                    for i, band in enumerate(bands):
                        if band in table[label]:
                            xs.append(i + (j - (len(labels) - 1) / 2.0) * slot)
                            heights.append(table[label][band] - baseline)
                            flagged = (label, band) in outside
                            edges.append(RED if flagged else INK)
                            widths.append(2.6 if flagged else 0.8)
                    if xs:
                        ax.bar(xs, heights, bottom=baseline, width=slot * 0.92, color=color, edgecolor=edges,
                               linewidth=widths, zorder=3)
                    for x, h, edge in zip(xs, heights, edges):
                        value = baseline + h
                        text = _fmt(value, 1 if (bar_px >= 34 or abs(value) < 10) else 0)
                        vertical = page.measure(text, FONT["note"])[0] > bar_px - 2
                        below = value < 0 and not floor_baseline
                        ax.annotate(text, (x, value), xytext=(0, -3 if below else 3), textcoords="offset points",
                                    ha="center", va="top" if below else "bottom", fontsize=FONT["note"],
                                    fontweight="bold" if edge == RED else "normal",
                                    color=RED if edge == RED else INK, rotation=90 if vertical else 0, zorder=7)
            else:
                for j, label in enumerate(labels):
                    color = SERIES_COLORS[j % len(SERIES_COLORS)]
                    points = [(i, table[label][b]) for i, b in enumerate(bands) if b in table[label]]
                    if points:
                        ax.plot([p[0] for p in points], [p[1] for p in points], color=color, lw=2.4, marker="o",
                                markersize=6, markeredgecolor=INK, markeredgewidth=0.6, zorder=3)
                    for i, value in points:
                        if (label, bands[i]) in outside:
                            ax.plot([i], [value], marker="o", markersize=11, markerfacecolor="none",
                                    markeredgecolor=RED, markeredgewidth=2.4, zorder=4)
            if not floor_baseline and everything and ymin < 0 < ymax:
                ax.axhline(0, color=INK, lw=1.0, zorder=2)
            return page.save(target)
        finally:
            page.close()


# ----------------------------------------------------------------------------------------------------------
# 4. Seam zoom
# ----------------------------------------------------------------------------------------------------------

def _hf_energy_db(samples, rate, first, last, cutoff=4000.0, window_ms=1.0, warmup_ms=100.0):
    """Level of the part above `cutoff` Hz over `window_ms` windows, in dBFS, for samples[first:last].

    A causal 4th-order high-pass (so a click shows where it happens, not before it), started in steady
    state on a lead-in of `warmup_ms` so the filter does not ring at the left edge. A full-scale sine
    reads 0 dBFS. Returns None when the sample rate is too low for the cutoff.
    """
    from scipy import signal
    if cutoff >= rate / 2.0 or last <= first:
        return None
    sos = signal.butter(4, cutoff / (rate / 2.0), btype="highpass", output="sos")
    begin = max(0, first - int(round(warmup_ms * rate / 1000.0)))
    segment = samples[begin:last]
    filtered, _ = signal.sosfilt(sos, segment, zi=signal.sosfilt_zi(sos) * segment[0])
    size = max(1, int(round(window_ms * rate / 1000.0)))
    squared = filtered * filtered
    mean = np.convolve(squared, np.ones(size) / size, mode="same")[first - begin:]
    return 10.0 * np.log10(2.0 * mean + 1e-12)


def seam_zoom(audio, seam_frame, path=None, window_ms=60.0, crossfade_ms=10.0, width=1200, title=None,
              crossfade_offset_ms=0.0):
    """A zoom on a loop seam, PNG at `path`.

    audio: an Audio holding the loop as the game plays it round the seam. seam_frame is the sample index
    where the next iteration starts. The picture covers window_ms centred on the seam (time axis in ms
    relative to the seam): one waveform lane per channel (same scale in every lane), and under them a
    short-window (1 ms) energy envelope of the part above 4 kHz in dBFS, where a click stands out as a
    spike. The seam is the red line; the crossfade window (crossfade_ms, starting crossfade_offset_ms
    after the seam, so 0 means the window runs from the seam forward) is shaded.
    """
    target = _target(path)
    width = _clamp_width(width)
    window_ms = _positive(window_ms, "window_ms")
    crossfade_ms = max(0.0, _number(crossfade_ms) or 0.0)
    offset_ms = _number(crossfade_offset_ms) or 0.0
    rate = int(getattr(audio, "rate", 0) or 0)
    channels = _channels(audio, 4)
    frames = channels[0].size if channels else 0
    seam = int(round(_number(seam_frame) or 0))
    mpl = _mpl()
    with _LOCK, mpl.rc_context(_RC):
        page = _Page(mpl, width)
        try:
            # ---- plan
            half_ms = window_ms / 2.0
            half = int(round(half_ms * rate / 1000.0)) if rate else 0
            first, last = max(0, seam - half), min(frames, seam + half + 1)
            usable = rate > 0 and last > first
            if len(channels) == 2:
                names = ["L", "R"]
            elif len(channels) == 1:
                names = ["mono"]
            else:
                names = ["ch {0}".format(c + 1) for c in range(len(channels))]
            subtitle = ("{0} ms around the seam (time in ms; 0 = the next iteration starts), {1} Hz. "
                        "Crossfade {2} ms.").format(_g(window_ms), rate, _g(crossfade_ms))
            if _channel_count(audio) > len(channels):
                subtitle += " The first {0} of {1} channels are shown.".format(len(channels), _channel_count(audio))
            lanes = max(1, len(channels))
            lane_h = 150 if lanes <= 2 else 110
            gap = 14
            energy_h = 230
            head = _subtitle_lines(page, subtitle)
            lanes_top = _header_height(head) + 24
            lanes_h = lanes * lane_h + (lanes - 1) * gap
            energy_top = lanes_top + lanes_h + 56
            bottom = 74
            page.resize(energy_top + energy_h + bottom)
            left, right = 108, 26
            plot_w = width - left - right
            # ---- draw
            _header(page, title or "Loop seam zoom", head)
            axes = []
            time_ms = (np.arange(first, last) - seam) * 1000.0 / rate if usable else np.zeros(0)
            peak = max([float(np.max(np.abs(c[first:last]))) for c in channels] + [0.0]) if usable else 0.0
            limit = max(peak * 1.15, 1e-4)
            for j in range(lanes):
                top = lanes_top + j * (lane_h + gap)
                ax = page.axes(left, top, plot_w, lane_h)
                axes.append(ax)
                _style_axes(ax, bottom=False)
                ax.set_xlim(-half_ms, half_ms)
                ax.set_ylim(-limit, limit)
                ax.axhline(0, color=GRID, lw=0.9, zorder=1)
                if usable and j < len(channels):
                    color = SERIES_COLORS[j % 2] if len(channels) == 2 else SERIES_COLORS[j % len(SERIES_COLORS)]
                    ax.plot(time_ms, channels[j][first:last], color=color, lw=1.3, zorder=3)
                    ax.set_yticks([-limit * 0.87, 0.0, limit * 0.87])
                    ax.set_yticklabels([_fmt(-limit * 0.87, 3), "0", _fmt(limit * 0.87, 3)], fontsize=FONT["tick"])
                else:
                    _message(ax, "seam is outside the audio" if j == 0 else "")
                    ax.set_yticks([])
                page.text(10, top + lane_h / 2.0, names[j] if j < len(names) else "no audio",
                          fontsize=FONT["label"], fontweight="bold", va="center")
            ax = page.axes(left, energy_top, plot_w, energy_h)
            axes.append(ax)
            _style_axes(ax)
            ax.set_xlim(-half_ms, half_ms)
            ax.yaxis.grid(True, color=GRID, lw=0.8)
            ax.set_axisbelow(True)
            note = "High-frequency energy (above 4 kHz, 1 ms window), dBFS"
            curve = None
            if usable:
                traces = [t for t in (_hf_energy_db(c, rate, first, last) for c in channels) if t is not None]
                if traces:
                    curve = np.max(np.stack(traces), axis=0)
            if curve is not None and curve.size == time_ms.size and curve.size:
                top_db = float(np.max(curve))
                ymax = 5.0 * math.ceil((top_db + 3.0) / 5.0)
                ymin = max(ymax - 70.0, -130.0)
                if ymax - ymin < 30.0:
                    ymax = ymin + 30.0
                median = float(np.median(curve))
                where = int(np.argmax(curve))
                ax.plot(time_ms, np.clip(curve, ymin, None), color="#222222", lw=1.6, zorder=3)
                ax.axhline(median, color=MUTED, lw=1.0, ls=(0, (5, 4)), zorder=2)
                ax.plot([time_ms[where]], [top_db], marker="o", markersize=9, markerfacecolor=RED,
                        markeredgecolor=INK, markeredgewidth=1.0, zorder=6, clip_on=False)
                ax.set_ylim(ymin, ymax)
                if top_db <= -100.0:
                    note += ": nothing above 4 kHz (peak {0})".format(_fmt(top_db, 1))
                else:
                    note += ": peak {0} at {1} ms, {2} dB above the median (dashed)".format(
                        _fmt(top_db, 1), ("+" if time_ms[where] >= 0 else "") + _fmt(float(time_ms[where]), 1),
                        _fmt(top_db - median, 1))
            else:
                ax.set_ylim(-100, -30)
                _message(ax, "no high-frequency data" if usable else "seam is outside the audio")
            ax.set_ylabel("dBFS", fontsize=FONT["label"])
            ax.set_xlabel("ms relative to the seam", fontsize=FONT["label"])
            text, size = page.fit(note, width - 2 * 14, FONT["note"], "bold")
            page.text(left, energy_top - 26, text, fontsize=size, fontweight="bold")
            for index, ax in enumerate(axes):
                if usable:
                    for a, b in ((-half_ms, float(time_ms[0])), (float(time_ms[-1]), half_ms)):
                        if b - a > 0.1:
                            ax.axvspan(a, b, facecolor=NO_DATA, edgecolor="none", zorder=0)
                            if index == 0 and (b - a) / window_ms * plot_w > 90:
                                ax.text((a + b) / 2.0, 0, "no audio", ha="center", va="center", fontsize=FONT["note"],
                                        color=MUTED, zorder=2)
                ax.axvline(0, color=RED, lw=2.2, zorder=5)
                if crossfade_ms > 0:
                    ax.axvspan(offset_ms, offset_ms + crossfade_ms, facecolor="#1f77b4", alpha=0.16, zorder=0)
            axes[0].annotate("seam: the next iteration starts", (0, 1.0), xycoords=("data", "axes fraction"),
                             xytext=(-6, 5), textcoords="offset points", ha="right", va="bottom",
                             fontsize=FONT["note"], fontweight="bold", color=RED, annotation_clip=False)
            if crossfade_ms > 0:
                axes[0].annotate("crossfade {0} ms".format(_g(crossfade_ms)), (offset_ms, 1.0),
                                 xycoords=("data", "axes fraction"), xytext=(6, 5), textcoords="offset points",
                                 ha="left", va="bottom", fontsize=FONT["note"], fontweight="bold", color="#1f5f99",
                                 annotation_clip=False)
            return page.save(target)
        finally:
            page.close()


# ----------------------------------------------------------------------------------------------------------
# 5. Loudness ladder
# ----------------------------------------------------------------------------------------------------------

def _tier_steps(values):
    """({index: step in LU from the previous tier that has a value}, indices quieter than that tier)."""
    steps = {}
    drops = set()
    previous = None
    for index, value in enumerate(values):
        if value is None:
            continue
        if previous is not None:
            steps[index] = value - previous
            if value < previous - 1e-9:
                drops.add(index)
        previous = value
    return steps, drops


def ladder_chart(levels, target=None, path=None, width=1200, title=None):
    """Loudness of each tier as a bar with its value on top, and the target as a dashed line, PNG at `path`.

    levels: {tier: LUFS or None} (None draws "no data"). Under each tier's name is the step from the tier
    before it; a tier quieter than the one below it is drawn in orange and flagged (it points to
    cancellation). Bars start at the axis minimum, so read the printed values, not the bar lengths.
    """
    file_path = _target(path)
    width = _clamp_width(width)
    goal = _number(target)
    tiers = [(str(name), _number(value)) for name, value in dict(levels or {}).items()]
    mpl = _mpl()
    with _LOCK, mpl.rc_context(_RC):
        page = _Page(mpl, width)
        try:
            # ---- plan
            known = [v for _, v in tiers if v is not None]
            everything = known + ([goal] if goal is not None else [])
            if everything:
                lo, hi = min(everything), max(everything)
                span = max(hi - lo, 2.0)
                ymin = 2.0 * math.floor((lo - max(4.0, 0.3 * span)) / 2.0)
                ymax = hi + max(2.5, 0.18 * span)
            else:
                ymin, ymax = -30.0, -10.0
            subtitle = "Integrated loudness in LUFS; bars start at the axis minimum, so read the printed values."
            steps, drops = _tier_steps([value for _, value in tiers])
            entries = [("tier loudness", BLUE, "bar")]
            if drops:
                entries.append(("quieter than the tier below", ORANGE, "bar"))
            if goal is not None:
                entries.append(("target {0} LUFS".format(_fmt(goal, 1)), RED, "line"))
            left, right = 92, int(min(110, max(70, 0.12 * width)))
            plot_w = width - left - right
            head = _subtitle_lines(page, subtitle)
            legend_y = _header_height(head)
            ncol, legend_rows = _legend_layout(page, [text for text, _, _ in entries], width - left - 14)
            plot_top = legend_y + legend_rows * 22 + 12
            plot_h = 360
            bottom = 90
            page.resize(plot_top + plot_h + bottom)
            # ---- draw
            _header(page, title or "Tier ladder (integrated loudness, LUFS)", head)
            handles = []
            for text, color, kind in entries:
                if kind == "line":
                    handles.append(mpl.Patch(facecolor="white", edgecolor=color, linewidth=2.0, linestyle="--",
                                             label=text))
                else:
                    handles.append(mpl.Patch(facecolor=color, edgecolor=INK, linewidth=0.8, label=text))
            page.legend(handles, left, legend_y, ncol=ncol, handlelength=1.8)
            ax = page.axes(left, plot_top, plot_w, plot_h)
            _style_axes(ax)
            count = max(1, len(tiers))
            ax.set_xlim(-0.6, count - 0.4)
            ax.set_ylim(ymin, ymax)
            ax.yaxis.grid(True, color=GRID, lw=0.8)
            ax.set_axisbelow(True)
            ax.set_ylabel("LUFS", fontsize=FONT["label"])
            labels = []
            for index, (name, value) in enumerate(tiers):
                if value is None:
                    ax.bar(index, ymax - ymin, bottom=ymin, width=0.62, facecolor="white", edgecolor=MUTED,
                           linewidth=1.2, linestyle="--", zorder=2)
                    ax.text(index, (ymin + ymax) / 2.0, "no data", ha="center", va="center", fontsize=FONT["value"],
                            color=MUTED, zorder=5)
                else:
                    ax.bar(index, value - ymin, bottom=ymin, width=0.62, facecolor=ORANGE if index in drops else BLUE,
                           edgecolor=INK, linewidth=1.0, zorder=3)
                    ax.annotate(_fmt(value, 1), (index, value), xytext=(0, 4), textcoords="offset points",
                                ha="center", va="bottom", fontsize=FONT["label"] + 1, fontweight="bold", color=INK,
                                zorder=7)
                step = steps.get(index)
                note = "" if step is None else "\n{0}{1}{2}".format("+" if step >= 0 else "", _fmt(step, 1),
                                                                      " LU" if plot_w / count >= 100 else "")
                labels.append(_plain(name) + note)
            ax.set_xticks(range(len(tiers)))
            ax.set_xticklabels(labels, fontsize=FONT["value"] + 0.5, linespacing=1.5)
            for index, tick in enumerate(ax.get_xticklabels()):
                if index in drops:
                    tick.set_color(RED)
                    tick.set_fontweight("bold")
            if goal is not None:
                ax.axhline(goal, color=RED, lw=2.2, ls=(0, (6, 4)), zorder=6)
                ax.annotate("target\n{0}".format(_fmt(goal, 1)), (count - 0.4, goal), xytext=(6, 0),
                            textcoords="offset points", ha="left", va="center", fontsize=FONT["value"],
                            fontweight="bold", color=RED, annotation_clip=False)
            if not tiers:
                _message(ax, "no tiers")
            return page.save(file_path)
        finally:
            page.close()
