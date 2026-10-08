"""Offline tests for ears.images: the five PNG pictures for an agent that reads images but cannot listen.

Every picture must be a valid PNG no wider than requested, no taller than 1400 px and compact, and must
survive empty and degenerate input. The numbers behind the pictures (spectrogram levels, the seam's
high-frequency envelope, note names, ladder steps) are checked directly, and a few pixel checks confirm
that the colours mean what the legends say.
"""
import functools
import struct
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
import pytest

from ears import images
from ears.audio import Audio

ROOT = Path(__file__).resolve().parents[2]
SIGNATURE = b"\x89PNG\r\n\x1a\n"
RATE = 22050
GREEN, AMBER, RED = (0x1A, 0x98, 0x50), (0xF5, 0xA3, 0x00), (0xD6, 0x27, 0x28)
NO_DATA = (0xD4, 0xD7, 0xDC)


# ----------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------

def png_size(path):
    """(width, height) from the IHDR chunk, after checking the 8-byte signature."""
    with open(str(path), "rb") as handle:
        head = handle.read(24)
    assert head[:8] == SIGNATURE, "not a PNG"
    assert head[12:16] == b"IHDR"
    return struct.unpack(">II", head[16:24])


def check_png(path, width=1200, max_kb=300):
    w, h = png_size(path)
    assert w <= width
    assert 100 <= h <= 1400
    assert Path(path).stat().st_size < max_kb * 1024
    return w, h


def pixels(path):
    from PIL import Image
    return np.asarray(Image.open(str(path)).convert("RGB")).astype(int)


def count_color(array, rgb, tolerance=14):
    return int((np.abs(array - np.array(rgb)).sum(axis=2) <= tolerance).sum())


def tone(seconds, freq=220.0, amp=0.3, rate=RATE, channels=1):
    t = np.arange(int(seconds * rate)) / rate
    x = amp * np.sin(2.0 * np.pi * freq * t)
    return Audio(np.stack([x] * channels, axis=1) if channels > 1 else x, rate)


def thumps(seconds, every, rate=RATE):
    """A kick-like stem: a decaying 60 Hz thump every `every` seconds."""
    x = np.zeros(int(seconds * rate))
    n = int(0.25 * rate)
    t = np.arange(n) / rate
    hit = 0.8 * np.sin(2.0 * np.pi * 60.0 * t) * np.exp(-t / 0.08)
    for start in np.arange(0.0, seconds, every):
        s = int(start * rate)
        m = min(n, len(x) - s)
        x[s:s + m] += hit[:m]
    return Audio(x, rate)


@functools.lru_cache(maxsize=None)
def make_stems():
    """Three stems at 120 BPM: a 2-bar kick, a 4-bar bass and a 4-bar stereo lead (bar = 2 s)."""
    rng = np.random.default_rng(3)
    lead = tone(8.0, 880.0, 0.2, channels=2)
    lead.samples[:, 1] += 0.01 * rng.standard_normal(lead.frames)
    return [("kick", thumps(4.0, 0.5)), ("bass", tone(8.0, 55.0, 0.4)), ("lead", lead)]


def sample_roll():
    roll = []
    for bar in range(4):
        for beat in range(4):
            roll.append({"part": "bass", "pitch": 33, "name": "A0", "start": bar * 4 + beat, "duration": 0.8,
                         "status": "chord"})
        roll.append({"part": "lead", "pitch": 69 + bar, "name": "x", "start": bar * 4 + 1.5, "duration": 1.0,
                     "status": ("chord", "scale", "out", "scale")[bar]})
    return roll


def sample_series():
    bands = ["sub", "bass", "low-mid", "mid", "presence", "air"]
    series = {"this take": dict(zip(bands, [-31.0, -25.0, -29.5, -33.0, -40.0, -47.0])),
              "previous": dict(zip(bands, [-30.0, -26.0, -29.0, -34.0, -38.0, -55.0]))}     # air is under its floor
    envelope = dict(zip(bands, [[-34, -28], [-28, -22], [-32, -26], [-36, -30], [-42, -36], [-52, -45]]))
    return series, envelope


def seam_audio(click=True, rate=44100):
    t = np.arange(rate) / rate
    x = 0.3 * np.sin(2.0 * np.pi * 110.0 * t)
    stereo = np.stack([x, 0.8 * x], axis=1)
    if click:
        stereo[rate // 2 + 120, 0] += 0.25
    return Audio(stereo, rate), rate // 2


def draw(name, path, **kwargs):
    """One picture of each kind, by name, with typical input."""
    if name == "stems":
        return images.stems_spectrogram(make_stems(), 120, 4.0, ["Am", "Dm"], path=path, **kwargs)
    if name == "roll":
        return images.piano_roll(sample_roll(), 4, 4.0, ["Am", "Dm"], path=path, **kwargs)
    if name == "bands":
        series, envelope = sample_series()
        return images.band_chart(series, envelope, path=path, **kwargs)
    if name == "seam":
        audio, seam = seam_audio()
        return images.seam_zoom(audio, seam, path=path, **kwargs)
    if name == "ladder":
        return images.ladder_chart({"T1": -22.4, "T2": -19.7, "T3": -17.1, "T4": -15.2, "T5": -14.3}, -14.0,
                                   path=path, **kwargs)
    raise AssertionError(name)


NAMES = ["stems", "roll", "bands", "seam", "ladder"]


# ----------------------------------------------------------------------------------------------------------
# the contract shared by the five pictures
# ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", NAMES)
def test_typical_picture_is_a_compact_png(tmp_path, name):
    target = tmp_path / "nested" / "deeper" / (name + ".png")
    returned = draw(name, target, title="a title")
    assert returned == str(target) and isinstance(returned, str)
    w, h = check_png(returned)
    assert w == 1200                                  # the default width, exactly
    assert (w * h) <= 1200000 + 1200 * 5              # about 1.2 megapixels at most: no downscaling by a viewer
    assert list(tmp_path.rglob("*.part")) == []       # written atomically, nothing left behind


@pytest.mark.parametrize("width", [640, 1200])
@pytest.mark.parametrize("name", NAMES)
def test_width_is_respected(tmp_path, name, width):
    path = draw(name, tmp_path / "p.png", width=width)
    w, _ = check_png(path, width=width)
    assert w == width


def test_an_existing_file_is_replaced(tmp_path):
    target = tmp_path / "p.png"
    target.write_bytes(b"old")
    draw("ladder", target)
    check_png(target)


def test_a_picture_over_the_size_budget_is_re_saved_with_a_reduced_palette(tmp_path, monkeypatch):
    from PIL import Image
    full = draw("stems", tmp_path / "full.png")
    monkeypatch.setattr(images, "SIZE_BUDGET", 20 * 1024)
    small = draw("stems", tmp_path / "small.png")
    assert Path(small).stat().st_size < Path(full).stat().st_size
    assert png_size(small) == png_size(full)
    assert Image.open(small).mode == "P"                       # a palette PNG, still a valid PNG
    assert Image.open(full).mode == "RGB"


def test_matplotlib_is_imported_only_when_a_picture_is_drawn(tmp_path):
    code = (
        "import sys\n"
        "import ears.images as images\n"
        "assert 'matplotlib' not in sys.modules, 'importing ears.images imported matplotlib'\n"
        "images.ladder_chart({'T1': -20.0, 'T2': -14.0}, -14.0, path=sys.argv[1])\n"
        "assert 'matplotlib' in sys.modules\n"
        "assert 'matplotlib.pyplot' not in sys.modules, 'pictures must not go through pyplot (global state)'\n"
    )
    done = subprocess.run([sys.executable, "-c", code, str(tmp_path / "ladder.png")], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    check_png(tmp_path / "ladder.png")


def test_importing_the_module_alone_does_not_load_matplotlib():
    done = subprocess.run([sys.executable, "-c",
                           "import sys; import ears.images; sys.exit(1 if 'matplotlib' in sys.modules else 0)"],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr


def test_pictures_can_be_drawn_from_several_threads(tmp_path):
    errors = []

    def work(index):
        try:
            draw("ladder", tmp_path / "t{0}.png".format(index))
            draw("bands", tmp_path / "b{0}.png".format(index))
        except Exception as error:         # pragma: no cover - only on failure
            errors.append(error)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    for i in range(4):
        check_png(tmp_path / "t{0}.png".format(i))
        check_png(tmp_path / "b{0}.png".format(i))


def test_fonts_are_at_least_ten_points():
    assert min(images.FONT.values()) >= 10.0


@pytest.mark.parametrize("call", [
    lambda p: images.stems_spectrogram([], 0, path=p),
    lambda p: images.stems_spectrogram([], None, path=p),
    lambda p: images.stems_spectrogram([], 120, beats_per_bar=0, path=p),
    lambda p: images.piano_roll([], 4, beats_per_bar=-1, path=p),
    lambda p: images.seam_zoom(tone(1.0), 100, window_ms=0, path=p),
])
def test_impossible_numbers_are_refused(tmp_path, call):
    with pytest.raises(ValueError):
        call(tmp_path / "x.png")
    assert not (tmp_path / "x.png").exists()


@pytest.mark.parametrize("call", [
    lambda: images.stems_spectrogram([], 120),
    lambda: images.piano_roll([], 4),
    lambda: images.band_chart({}),
    lambda: images.seam_zoom(tone(1.0), 100),
    lambda: images.ladder_chart({}),
])
def test_path_is_required(call):
    with pytest.raises(ValueError):
        call()


# ----------------------------------------------------------------------------------------------------------
# stems_spectrogram
# ----------------------------------------------------------------------------------------------------------

def test_stems_spectrogram_degenerate_input_still_draws(tmp_path):
    cases = {
        "empty list": [],
        "zero length": [("kick", Audio(np.zeros((0, 2)), RATE))],
        "silent": [("pad", Audio(np.zeros((RATE, 2)), RATE))],
        "nan": [("bad", Audio(np.full((RATE, 1), np.nan), RATE))],
        "shorter than a bar": [("hit", tone(0.4, 60.0))],
        "one stem": [("lead", tone(2.0, 1000.0))],
    }
    for label, stems in cases.items():
        path = images.stems_spectrogram(stems, 120, path=tmp_path / (label.replace(" ", "_") + ".png"))
        check_png(path)


def test_stems_spectrogram_sample_rates_and_meters(tmp_path):
    for rate in (8000, 22050, 44100, 48000, 96000):
        check_png(images.stems_spectrogram([("a", tone(1.0, 440.0, rate=rate))], 93.5, 3.0, ["C", "G7", "Am"],
                                           path=tmp_path / "r{0}.png".format(rate)))


def white_margin(path, rows=12):
    """True when the last rows of the picture are plain white: nothing ran off the page."""
    return bool((pixels(path)[-rows:] > 240).all())


def test_stems_spectrogram_caps_the_height_with_many_stems(tmp_path):
    for count in (16, 40):
        stems = [("stem {0}".format(i), tone(1.0, 100.0 * (i % 40 + 1))) for i in range(count)]
        path = images.stems_spectrogram(stems, 120, path=tmp_path / "many{0}.png".format(count))
        w, h = check_png(path)
        assert h <= 1400
        assert white_margin(path), "the rows ran past the bottom of the page"


def test_stems_spectrogram_long_labels_and_chords_do_not_break_the_layout(tmp_path):
    stems = [("a_very_long_stem_label_that_does_not_fit_in_the_gutter_at_all", tone(2.0))]
    path = images.stems_spectrogram(stems, 120, chords=["Fmaj7/A", "Bbm7b5", "E7#9", "Abmaj13#11"],
                                    path=tmp_path / "long.png", title="a really long title " * 10)
    check_png(path)
    check_png(images.stems_spectrogram(stems, 120, path=tmp_path / "dollar.png", title="$x^2$"))


def test_a_shorter_stem_ends_where_its_audio_ends(tmp_path):
    equal = images.stems_spectrogram([("a", tone(4.0)), ("b", tone(4.0))], 120, path=tmp_path / "equal.png")
    unequal = images.stems_spectrogram([("a", tone(2.0)), ("b", tone(4.0))], 120, path=tmp_path / "unequal.png")
    assert count_color(pixels(equal), NO_DATA, 0) == 0
    assert count_color(pixels(unequal), NO_DATA, 0) > 15000       # the right half of the first row is grey


def test_a_louder_stem_is_brighter_on_the_shared_scale(tmp_path):
    def mean_brightness(amp):
        path = images.stems_spectrogram([("a", tone(4.0, 440.0, amp))], 120, path=tmp_path / "a{0}.png".format(amp))
        picture = pixels(path)
        h, w, _ = picture.shape
        return picture[h // 2 - 40:h // 2 + 40, 300:900].mean()
    loud, quiet = mean_brightness(0.5), mean_brightness(0.005)
    assert loud > quiet + 0.5


def levels_for(samples, rate=44100, ncols=200, nrows=270, seconds=2.0):
    audio = Audio(samples, rate)
    levels = images._spectrogram_levels(audio, seconds / ncols, ncols, nrows)
    edges = np.geomspace(images.SPEC_FMIN, images.SPEC_FMAX, nrows + 1)
    return levels, np.sqrt(edges[:-1] * edges[1:])


@pytest.mark.parametrize("freq", [45.0, 100.0, 440.0, 1000.0, 3300.0, 8000.0, 15000.0])
def test_a_sine_reads_its_dbfs_in_every_window_region(freq):
    t = np.arange(44100 * 2) / 44100.0
    levels, centres = levels_for(0.5 * np.sin(2.0 * np.pi * freq * t))
    column = levels[:, 100]
    assert column.max() == pytest.approx(20.0 * np.log10(0.5), abs=0.3)      # -6.02 dBFS
    assert abs(centres[int(np.argmax(column))] - freq) / freq < 0.07           # on the right row
    elsewhere = freq * 2.8 if freq * 2.8 < images.SPEC_FMAX else freq / 2.8
    assert column[np.abs(centres - elsewhere).argmin()] < -60.0                # and nowhere else


def test_levels_do_not_depend_on_the_sample_rate():
    reads = []
    for rate in (22050, 44100, 48000):
        t = np.arange(rate * 2) / float(rate)
        levels, centres = levels_for(0.25 * np.sin(2.0 * np.pi * 700.0 * t), rate=rate)
        reads.append(float(levels[:, 100].max()))
    assert max(reads) - min(reads) < 0.3


def test_an_antiphase_pair_keeps_its_energy():
    t = np.arange(44100 * 2) / 44100.0
    s = np.sin(2.0 * np.pi * 1000.0 * t)
    levels, _ = levels_for(np.stack([s, -s], axis=1))
    assert levels[:, 100].max() > -0.5


def test_silence_reads_the_floor():
    levels, _ = levels_for(np.zeros(44100 * 2))
    assert levels.max() <= images.SPEC_FLOOR_DB + 1e-3


def test_noise_has_no_steps_where_the_analysis_window_changes():
    noise = 0.1 * np.random.default_rng(1).standard_normal(44100 * 4)
    levels, centres = levels_for(noise, ncols=400, seconds=4.0)
    rows = levels[:, 20:-20].mean(axis=1)
    steps = np.abs(np.diff(rows[np.abs(centres - 40).argmin():]))
    assert steps.max() < 1.5
    # and the level is the one the band theory gives: -47 dBFS at 35 Hz, rising 3 dB per octave above 200 Hz
    assert rows[np.abs(centres - 5000).argmin()] > rows[np.abs(centres - 500).argmin()] + 5.0


def test_a_click_is_placed_in_time_sharply_in_the_highs_and_broadly_in_the_bass():
    x = np.zeros(44100 * 3)
    x[44100] = 0.5
    levels, centres = levels_for(x, ncols=600, seconds=3.0)
    expected = int(1.0 / (3.0 / 600))
    for freq, widest in ((12000.0, 4), (5000.0, 4), (500.0, 20)):
        row = levels[np.abs(centres - freq).argmin()]
        assert abs(int(np.argmax(row)) - expected) <= 1
        assert int((row > row.max() - 6.0).sum()) <= widest
    bass = levels[np.abs(centres - 50.0).argmin()]
    assert int((bass > bass.max() - 6.0).sum()) > 10               # long window: smeared, as documented


def test_analysis_windows_scale_with_the_sample_rate_and_cover_the_range():
    assert images._fft_sizes(44100) == [512, 1024, 2048, 4096, 8192]
    assert images._fft_sizes(88200) == [1024, 2048, 4096, 8192, 16384]
    sizes = images._fft_sizes(44100)
    assert images._pick_size(sizes, 44100, 30.0) == 8192
    assert images._pick_size(sizes, 44100, 16000.0) == 512
    picks = [images._pick_size(sizes, 44100, f) for f in np.geomspace(30, 16000, 50)]
    assert picks == sorted(picks, reverse=True)                      # shorter windows as frequency rises


def test_bar_axis_helpers_are_one_based_and_thin_out():
    assert images._bar_positions(4.0) == [0, 1, 2, 3, 4]
    assert images._bar_positions(3.5) == [0, 1, 2, 3]
    assert images._bar_positions(16.0, 4) == [0, 4, 8, 12, 16]
    assert images._label_step(100.0, 34) == 1
    assert images._label_step(10.0, 34) == 4
    assert images._label_step(0.1, 34) >= 256


# ----------------------------------------------------------------------------------------------------------
# piano_roll
# ----------------------------------------------------------------------------------------------------------

def test_note_names_follow_lives_convention():
    assert images._note_name(60) == "C3"
    assert images._note_name(61) == "C#3"
    assert images._note_name(69) == "A3"
    assert images._note_name(72) == "C4"
    assert images._note_name(0) == "C-2"
    assert images._note_name(12) == "C-1"
    assert images._note_name(127) == "G8"


def test_pitch_labels_thin_out_as_semitones_get_smaller():
    sets = [images._pitch_classes_to_label(px) for px in (16.0, 10.0, 6.0, 3.0)]
    assert sets[0] == set(range(12))
    assert all(later < earlier for earlier, later in zip(sets, sets[1:]))
    assert 0 in sets[-1]


def test_clean_roll_drops_junk_and_defaults_the_rest():
    notes = images._clean_roll([
        {"part": "a", "pitch": 60, "start": 0, "duration": 1, "status": "chord"},
        {"part": "a", "pitch": 61.4, "start": 1, "duration": 1},                       # no status: scale
        {"part": "a", "pitch": 62, "start": 2, "duration": 1, "status": "mystery"},    # unknown: other
        {"pitch": 63, "start": 3, "duration": -2, "status": "OUT"},                    # no part, negative length
        {"part": "a", "pitch": "x", "start": 0, "duration": 1},                        # junk
        {"part": "a", "pitch": 60, "start": float("nan"), "duration": 1},
        "not a dict", None,
    ])
    assert [n["pitch"] for n in notes] == [60, 61, 62, 63]
    assert [n["status"] for n in notes] == ["chord", "scale", "other", "out"]
    assert notes[3]["part"] == "notes" and notes[3]["duration"] == 0.0
    assert notes[0]["name"] == "C3"


def test_empty_piano_roll_still_draws_axes(tmp_path):
    path = images.piano_roll([], 4, path=tmp_path / "empty.png")
    w, h = check_png(path)
    assert h > 250
    picture = pixels(path)
    assert (picture.sum(axis=2) < 150).sum() > 500            # dark axes and lines, not a blank sheet
    check_png(images.piano_roll([], None, path=tmp_path / "none.png"))
    check_png(images.piano_roll([], 0, path=tmp_path / "zero.png"))


def test_piano_roll_colours_follow_the_status_legend(tmp_path):
    def plot_area(roll):
        picture = pixels(images.piano_roll(roll, 4, path=tmp_path / "r{0}.png".format(len(roll))))
        return picture[140:]                                     # below the legend
    only_chords = [n for n in sample_roll() if n["status"] == "chord"]
    quiet = plot_area(only_chords)
    assert count_color(quiet, GREEN) > 300
    assert count_color(quiet, AMBER) == 0 and count_color(quiet, RED) == 0
    mixed = plot_area(sample_roll())
    assert count_color(mixed, GREEN) > 300
    assert count_color(mixed, AMBER) > 100 and count_color(mixed, RED) > 100


def test_notes_beyond_the_bars_are_cut_and_do_not_widen_the_lanes(tmp_path):
    roll = [{"part": "a", "pitch": 60, "start": 2, "duration": 1, "status": "chord"},
            {"part": "a", "pitch": 100, "start": 40, "duration": 1, "status": "chord"},
            {"part": "b", "pitch": 20, "start": 41, "duration": 1, "status": "out"}]
    cut = images.piano_roll(roll, 2, path=tmp_path / "cut.png")
    alone = images.piano_roll(roll[:1], 2, path=tmp_path / "alone.png")
    assert png_size(cut) == png_size(alone)                     # same lanes: the hidden notes took no room


def test_piano_roll_many_parts_and_a_wide_range_stay_under_the_height_cap(tmp_path):
    roll = []
    for k in range(20):
        for i in range(8):
            roll.append({"part": "part{0}".format(k), "pitch": 20 + k * 5 + i * 3, "start": i * 0.5, "duration": 0.4,
                         "status": ("chord", "scale", "out")[(i + k) % 3]})
    path = images.piano_roll(roll, 4, path=tmp_path / "many.png")
    w, h = check_png(path)
    assert h <= 1400
    assert white_margin(path), "the lanes ran past the bottom of the page"
    wide = [{"part": "w", "pitch": p, "start": p / 8.0, "duration": 0.2, "status": "scale"} for p in range(0, 128, 3)]
    check_png(images.piano_roll(wide, 16, path=tmp_path / "wide.png"))


def test_piano_roll_chords_longer_shorter_and_odd_meters(tmp_path):
    roll = sample_roll()
    check_png(images.piano_roll(roll, 4, 4.0, ["Am"], path=tmp_path / "one.png"))
    check_png(images.piano_roll(roll, 4, 4.0, ["Am", "Dm", "G", "E", "Am", "Dm"], path=tmp_path / "more.png"))
    check_png(images.piano_roll(roll, 4, 4.0, ["Fmaj7/A", "Bbm7b5", "E7#9", "Abmaj13#11"], path=tmp_path / "long.png"))
    check_png(images.piano_roll(roll, 6, 3.0, None, path=tmp_path / "waltz.png"))
    check_png(images.piano_roll(roll, 64, 4.0, ["Am", "F"], path=tmp_path / "long64.png"))


def test_out_of_key_notes_are_named_without_hiding_other_notes(tmp_path):
    # a dense arpeggio of out-of-key notes: labels must find free spots or be left out, never crash
    roll = [{"part": "arp", "pitch": 60 + (i * 7) % 12, "start": i * 0.25, "duration": 0.25,
             "status": ("chord", "scale", "out")[i % 3]} for i in range(128)]
    check_png(images.piano_roll(roll, 8, path=tmp_path / "dense.png"))


# ----------------------------------------------------------------------------------------------------------
# band_chart
# ----------------------------------------------------------------------------------------------------------

def test_outside_envelope_lists_the_values_beyond_their_range():
    series, envelope = sample_series()
    env = dict((band, tuple(pair)) for band, pair in envelope.items())
    table = dict((label, dict(values)) for label, values in series.items())
    assert images._outside_envelope(table, env) == [("previous", "air")]
    table["this take"]["mid"] = -20.0
    assert images._outside_envelope(table, env) == [("this take", "mid"), ("previous", "air")]
    assert images._outside_envelope(table, {}) == []


def test_band_chart_variants_all_draw(tmp_path):
    series, envelope = sample_series()
    bands = list(next(iter(series.values())))
    many = ["band {0}".format(i) for i in range(30)]
    cases = {
        "empty": ({}, None),
        "series without values": ({"a": {}}, None),
        "one series": ({"T5": series["this take"]}, None),
        "outside": ({"T5": {"sub": -20.0, "bass": -30.0}}, {"sub": [-34, -28], "bass": [-28, -22]}),
        "none and nan": ({"a": {"x": 1.0, "y": None, "z": float("nan")}, "b": {"x": 2.0, "y": 3.0}}, None),
        "positive": ({"share": {"low": 12.0, "mid": 55.0, "high": 33.0}}, None),
        "mixed signs": ({"d": {"low": 2.0, "mid": -3.5, "high": 1.0}},
                         {"low": [-1, 1], "mid": [-1, 1], "high": [-1, 1]}),
        "envelope only": ({}, {"a": [-30, -20], "b": [-40, -30]}),
        "many bands as lines": ({"a": dict((b, -30.0 - i * 0.5) for i, b in enumerate(many)),
                                 "b": dict((b, -32.0 - (i % 5)) for i, b in enumerate(many))},
                                dict((b, [-40, -25]) for b in many)),
        "five series": (dict(("s{0}".format(k), dict(zip(bands, [-30.0 - k, -25.0, -29.0, -33.0, -40.0, -47.0])))
                             for k in range(5)), envelope),
        "long labels": ({"a": {"20-60 Hz sub bass region": -30.0, "60-250 Hz bass region": -25.0,
                               "very long band name number three": -28.0}}, None),
        "bad envelope": ({"a": {"x": -3.0}}, {"x": "oops", "y": [1], "z": [float("nan"), 2]}),
    }
    for label, (data, env) in cases.items():
        check_png(images.band_chart(data, env, path=tmp_path / (label.replace(" ", "_") + ".png")))
    check_png(images.band_chart(series, envelope, path=tmp_path / "units.png", unit="% of energy", title="T5"))
    check_png(images.band_chart(series, envelope, path=tmp_path / "narrow.png", width=640))


def test_band_chart_marks_values_outside_the_envelope_in_red(tmp_path):
    series, envelope = sample_series()
    inside = dict((label, dict((band, sum(envelope[band]) / 2.0) for band in values))
                  for label, values in series.items())
    quiet = pixels(images.band_chart(inside, envelope, path=tmp_path / "inside.png"))
    loud = pixels(images.band_chart(series, envelope, path=tmp_path / "outside.png"))
    assert count_color(quiet[120:], RED) == 0
    assert count_color(loud[120:], RED) > 200


# ----------------------------------------------------------------------------------------------------------
# seam_zoom
# ----------------------------------------------------------------------------------------------------------

def test_the_high_frequency_envelope_reads_dbfs_and_finds_a_click():
    rate = 44100
    t = np.arange(rate) / rate
    sine = 0.5 * np.sin(2.0 * np.pi * 10000.0 * t)
    env = images._hf_energy_db(sine, rate, 20000, 22000)
    assert env.shape == (2000,)
    assert float(np.median(env)) == pytest.approx(20.0 * np.log10(0.5), abs=1.0)    # about -6 dBFS
    base = 0.3 * np.sin(2.0 * np.pi * 110.0 * t)                  # nothing above 4 kHz
    clicked = base.copy()
    clicked[30000] += 0.25
    env = images._hf_energy_db(clicked, rate, 28000, 32000)
    assert abs(int(np.argmax(env)) - 2000) <= 45                  # within 1 ms of the click
    assert env.max() - float(np.median(env)) > 30.0
    flat = images._hf_energy_db(base, rate, 28000, 32000)
    assert flat.max() - float(np.median(flat)) < 3.0


def test_the_high_frequency_envelope_does_not_ring_at_the_left_edge():
    rate = 44100
    env = images._hf_energy_db(np.full(rate, 0.5), rate, 0, 2000)       # constant level: no HF at all
    assert env.max() < -100.0
    assert images._hf_energy_db(np.zeros(100), 8000, 0, 50) is None or True
    assert images._hf_energy_db(np.zeros(100), 8000, 0, 50) is None     # 4 kHz is Nyquist at 8 kHz: no band


def test_seam_zoom_shows_a_planted_click(tmp_path):
    with_click, seam = seam_audio(click=True)
    without, _ = seam_audio(click=False)
    a = pixels(images.seam_zoom(with_click, seam, path=tmp_path / "click.png"))
    b = pixels(images.seam_zoom(without, seam, path=tmp_path / "clean.png"))
    assert a.shape == b.shape
    changed = (np.abs(a - b).sum(axis=2) > 60).sum()
    assert changed > 300                                          # the spike and the peak marker are drawn


def test_seam_zoom_degenerate_input_still_draws(tmp_path):
    stereo, seam = seam_audio()
    rate = stereo.rate
    cases = {
        "mono": (Audio(stereo.mono(), rate), seam),
        "seam at start": (stereo, 100),
        "seam at end": (stereo, stereo.frames - 50),
        "seam outside": (stereo, stereo.frames * 3),
        "seam negative": (stereo, -50000),
        "tiny audio": (Audio(stereo.samples[:30], rate), 15),
        "no audio": (Audio(np.zeros((0, 2)), rate), 0),
        "silent": (Audio(np.zeros((rate, 2)), rate), rate // 2),
        "six channels": (Audio(np.tile(stereo.mono()[:, None], (1, 6)), rate), seam),
        "8 kHz": (Audio(stereo.mono()[:16000], 8000), 8000),
        "nan": (Audio(np.full((rate, 1), np.nan), rate), rate // 2),
    }
    for label, (audio, where) in cases.items():
        check_png(images.seam_zoom(audio, where, path=tmp_path / (label.replace(" ", "_") + ".png")))


def test_seam_zoom_options(tmp_path):
    stereo, seam = seam_audio()
    for label, kwargs in {"no crossfade": {"crossfade_ms": 0}, "crossfade before": {"crossfade_offset_ms": -10.0},
                          "wide": {"window_ms": 500.0}, "narrow": {"window_ms": 8.0, "crossfade_ms": 2.0}}.items():
        check_png(images.seam_zoom(stereo, seam, path=tmp_path / (label.replace(" ", "_") + ".png"), **kwargs))


# ----------------------------------------------------------------------------------------------------------
# ladder_chart
# ----------------------------------------------------------------------------------------------------------

def test_tier_steps_and_drops():
    steps, drops = images._tier_steps([-22.0, -19.0, -20.0, None, -14.0])
    assert steps == {1: pytest.approx(3.0), 2: pytest.approx(-1.0), 4: pytest.approx(6.0)}
    assert drops == {2}
    assert images._tier_steps([None, None]) == ({}, set())
    assert images._tier_steps([-14.0, -14.0, -14.0]) == ({1: 0.0, 2: 0.0}, set())     # equal is not a drop


def test_ladder_variants_all_draw(tmp_path):
    cases = {
        "empty": ({}, None),
        "all none": ({"T1": None, "T2": None}, -14.0),
        "no target": ({"T1": -20.0, "T2": -18.0, "T3": -16.0}, None),
        "target only": ({}, -14.0),
        "positive": ({"A": 3.2, "B": 5.5}, None),
        "drop and gap": ({"T1": -22.4, "T2": -19.7, "T3": -20.9, "T4": None, "T5": -14.3}, -14.0),
        "many tiers": (dict(("T{0}".format(i), -30.0 + i) for i in range(1, 13)), -14.0),
        "equal": ({"T1": -14.0, "T2": -14.0}, -14.0),
        "numeric keys": ({1: -20.0, 2: -15.0}, -14.0),
    }
    for label, (levels, target) in cases.items():
        check_png(images.ladder_chart(levels, target, path=tmp_path / (label.replace(" ", "_") + ".png")))
    check_png(images.ladder_chart({"T1": -20.0}, -14.0, path=tmp_path / "narrow.png", width=520), width=520)


def test_ladder_flags_a_tier_quieter_than_the_one_below_in_orange(tmp_path):
    orange = (0xE8, 0x71, 0x0A)
    rising = pixels(images.ladder_chart({"T1": -22.0, "T2": -19.0, "T3": -16.0}, -14.0, path=tmp_path / "up.png"))
    dropping = pixels(images.ladder_chart({"T1": -22.0, "T2": -19.0, "T3": -20.0}, -14.0, path=tmp_path / "down.png"))
    assert count_color(rising[60:], orange) < 100          # (the legend only names the colour when a tier drops)
    assert count_color(dropping[60:], orange) > 3000
