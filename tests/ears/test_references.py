"""References and the meter (PRD section 11): profiles, the in-memory meter, streamed and owned references,
the envelope and comparisons against it. M1 (no audio to disk), M2 (no route out), M4 (no absolute level for
an external source) and M5 (each section plays once) are tested here without a device or Spotify; M3 and the
calibration tone run on the Mac (tests/live/test_meter.py)."""
import json
import os
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import numpy as np
import pytest

from ears import analyze, compare, measure, meter, refs, tiers
from ears import profile as profiles
from ears import spec as specs
from ears import take as takes
from ears.audio import Audio, write_wav
from ears.fixtures import audio as fx
from ears.player import PlayerError, Spotify, track_uri

RATE = 44100
TEMPO = 140.0
URI = "spotify:track:32ZmFcP0qeEIuXtO6TDZ1K"
ROOT = Path(__file__).resolve().parents[2]


def groove(bpm, seconds, rate=RATE, hats=4, seed=1):
    """Kick on the beat, hi-hats on the other sixteenths (hats=4) or eighths (hats=2), a bass tone, noise."""
    rng = np.random.default_rng(seed)
    n = int(rate * seconds)
    x = np.zeros(n)
    step = 60.0 / bpm / hats
    for k in range(int(seconds / step)):
        i = int(k * step * rate)
        env = np.exp(-np.arange(min(int(0.05 * rate), n - i)) / (0.01 * rate))
        if k % hats == 0:
            x[i:i + len(env)] += 0.8 * env * np.sin(2 * np.pi * 55 * np.arange(len(env)) / rate)
        else:
            x[i:i + len(env)] += 0.2 * env * rng.standard_normal(len(env))
    t = np.arange(n) / float(rate)
    x += 0.1 * np.sin(2 * np.pi * 110 * t) + 0.01 * rng.standard_normal(n)
    return np.column_stack([x, 0.8 * x + 0.05 * rng.standard_normal(n)])


class FakePlayer(object):
    """The Spotify interface ears.refs uses, without Spotify. moves_on_after: after that many status calls while
    playing, the player reports the next track (as Spotify does when a track ends)."""

    def __init__(self, duration, name="Closer - Nine Inch Noize Version", volume=100.0, moves_on_after=None):
        self.duration, self.name, self.volume = duration, name, volume
        self.state, self.uri, self.position, self.calls = "paused", None, 0.0, []
        self.moves_on_after, self.polls = moves_on_after, 0

    def status(self):
        if self.state == "playing" and self.moves_on_after is not None:
            self.polls += 1
            if self.polls > self.moves_on_after:
                self.uri, self.name = "spotify:track:0000000000000000000000", "Next Track"
        track = None
        if self.uri:
            track = {"uri": self.uri, "name": self.name, "artist": "Nine Inch Nails, Boys Noize", "album": "Nine Inch Noize",
                     "duration": self.duration}
        return {"state": self.state, "volume": self.volume, "position": self.position, "track": track}

    def running(self):
        return True

    def play(self, uri, position=None):
        self.calls.append(("play", uri, position))
        self.uri, self.state, self.position = uri, "playing", float(position or 0.0)
        return self.status()

    def resume(self):
        self.calls.append(("resume",))
        self.state = "playing"
        return self.status()

    def pause(self):
        self.calls.append(("pause",))
        self.state = "paused"
        return self.status()

    def seek(self, position):
        self.calls.append(("seek", position))
        self.position = float(position)
        return self.status()


def silence(seconds=0.5):
    return np.zeros((int(seconds * RATE), 2))


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("EARS_REFS", str(tmp_path / "refs"))
    return tmp_path / "refs"


@pytest.fixture(scope="module")
def spec():
    return specs.load("nova")


@pytest.fixture(scope="module")
def song():
    """A 50 s "track": a 20 s intro 9 dB down (a sparse section), then 30 s of the full groove."""
    full = groove(124.0, 30.0)
    intro = groove(124.0, 20.0, seed=2) * 10 ** (-9 / 20.0)
    return np.concatenate([intro, full])


# ---------------------------------------------------------------------------
# Profiles and tempo
# ---------------------------------------------------------------------------

def test_a_profile_does_not_depend_on_level(song):
    loud = profiles.profile(Audio(song, RATE), absolute=False)
    quiet = profiles.profile(Audio(song * 10 ** (-14 / 20.0), RATE), absolute=False)
    assert set(loud) == set(profiles.SHAPE_KEYS) and not set(loud) & set(profiles.ABSOLUTE_KEYS)
    for band, value in loud["third_octave"].items():
        assert quiet["third_octave"][band] == pytest.approx(value, abs=0.15)
    for band, value in loud["bands"].items():
        assert quiet["bands"][band] == pytest.approx(value, abs=0.15), band       # re the audio's own loudness
    for key in ("lra", "plr_db", "crest_db", "dynamics_spread", "width", "correlation", "mono_sub_loss_db", "onset_rate"):
        assert quiet[key] == pytest.approx(loud[key], abs=0.15), key
    assert quiet["tempo"]["bpm"] == pytest.approx(loud["tempo"]["bpm"], abs=0.3) and quiet["key"] == loud["key"]


def test_absolute_figures_only_when_allowed(song):
    values = profiles.profile(Audio(song, RATE), absolute=True)
    assert set(profiles.ABSOLUTE_KEYS) <= set(values)
    assert not set(profiles.shape_only(values)) & set(profiles.ABSOLUTE_KEYS)
    assert profiles.profile(Audio(np.zeros((RATE * 2, 2)), RATE)) == {"seconds": 2.0, "silent": True}
    # below the loudness gate (too quiet, or shorter than one 400 ms block): nothing relative is meaningful
    assert profiles.profile(Audio(song * 10 ** (-60 / 20.0), RATE)) == {"seconds": 50.0, "silent": True}
    assert profiles.profile(Audio(song[:int(0.3 * RATE)], RATE), absolute=False) == {"seconds": 0.3, "silent": True}
    damaged = song[:RATE * 10].copy()
    damaged[1000, 0] = np.nan
    assert np.isfinite(profiles.profile(Audio(damaged, RATE))["true_peak_dbtp"])


@pytest.mark.parametrize("bpm,hats", [(90, 2), (100, 4), (124, 4), (128, 2), (140, 4), (150, 2)])
def test_tempo_of_synthetic_grooves(bpm, hats):
    result = measure.tempo_estimate(Audio(groove(bpm, 20.0, hats=hats), RATE))
    assert result["bpm"] == pytest.approx(bpm, abs=1.0)


def test_tempo_reports_none_without_a_pulse():
    assert measure.tempo_estimate(Audio(np.zeros((RATE * 6, 2)), RATE))["bpm"] is None
    assert measure.tempo_estimate(Audio(groove(120, 2.0), RATE))["bpm"] is None          # too short
    tone = 0.3 * np.sin(2 * np.pi * 220 * np.arange(RATE * 8) / RATE)
    assert measure.tempo_estimate(Audio(np.column_stack([tone, tone]), RATE))["bpm"] is None


def test_same_tempo_folds_octaves():
    assert profiles.same_tempo(140, 70) and profiles.same_tempo(124, 124.8) and profiles.same_tempo(87, 174)
    assert not profiles.same_tempo(140, 93.3) and not profiles.same_tempo(None, 120)


# ---------------------------------------------------------------------------
# The meter
# ---------------------------------------------------------------------------

def test_meter_keeps_no_absolute_level_for_an_external_source(song):
    source = meter.ArrayInput(np.concatenate([silence(0.3), song]), RATE)
    result = meter.meter(source, 30.0, kind="external")
    assert result["source"] == "external" and result["lead_in_seconds"] == pytest.approx(0.3, abs=0.001)
    assert not set(result["profile"]) & set(profiles.ABSOLUTE_KEYS)
    text = json.dumps(result, allow_nan=False)
    assert "lufs" not in text and "true_peak" not in text and "rms_dbfs" not in text


def test_meter_of_live_keeps_absolute_level(song):
    result = meter.meter(meter.ArrayInput(song, RATE), 10.0, kind="live")
    assert result["profile"]["lufs_i"] < 0 and "true_peak_dbtp" in result["profile"]


def test_meter_refuses_silence_short_quiet_input_and_a_busy_loopback(song):
    with pytest.raises(meter.MeterError, match="No signal"):
        meter.meter(meter.ArrayInput(silence(4.0), RATE), 4.0)
    with pytest.raises(meter.MeterError, match="at least 3 s"):
        meter.meter(meter.ArrayInput(song, RATE), 2.0)
    with pytest.raises(meter.MeterError, match="Only 2.0 s of signal"):
        meter.meter(meter.ArrayInput(np.concatenate([silence(1.5), song]), RATE), 3.5)
    with pytest.raises(meter.MeterError, match="too quiet"):
        meter.meter(meter.ArrayInput(song * 10 ** (-60 / 20.0), RATE), 10.0)
    with pytest.raises(meter.MeterError, match="already playing"):
        meter.check_silent(meter.ArrayInput(song, RATE))
    assert meter.check_silent(meter.ArrayInput(silence(), RATE)) <= meter.SILENCE_DBFS
    with pytest.raises(meter.MeterError):
        meter.meter(meter.ArrayInput(song, RATE), 4.0, kind="file")


def test_windows_label_full_sparse_and_quiet():
    loud = groove(124.0, 20.0)
    track = np.concatenate([loud * 10 ** (-20 / 20.0), loud * 10 ** (-6 / 20.0), loud])
    items = meter.windows(Audio(track, RATE), window=10.0)
    assert [item["kind"] for item in items] == ["quiet", "quiet", "sparse", "sparse", "full", "full"]
    assert items[-1]["loudness_lu"] == pytest.approx(0.0, abs=0.3) and items[2]["loudness_lu"] == pytest.approx(-6.0, abs=0.5)
    assert meter._spans(items, "full") == [[40.0, 60.0]]


def test_sections_of_a_recording(song):
    measured = meter.measure_sections(Audio(song, RATE), "external", sections={"drop": [25.0, 45.0]})
    assert sorted(measured["sections"]) == ["drop", "full", "sparse", "track"]
    assert measured["sections"]["full"]["span"] == [[20.0, 50.0]] and measured["sections"]["drop"]["span"] == [[25.0, 45.0]]
    for values in measured["sections"].values():
        assert not set(values) & set(profiles.ABSOLUTE_KEYS)
    owned = meter.measure_sections(Audio(song, RATE), "file")
    assert "lufs_i" in owned["sections"]["track"]


_AUDIT = r"""
import io, json, logging, os, sys, threading
import numpy as np
from ears import meter, refs
from ears.audio import Audio
sys.path.insert(0, os.environ["TEST_DIR"])
from test_references import FakePlayer, groove
from MCP_Server.tools import references as tools
rate = 44100
song = groove(124.0, 24.0)
lead = np.zeros((int(0.6 * rate), 2))
meter.meter(meter.ArrayInput(song, rate), 6.0, kind="external")          # warm up lazy imports before the hook
refs.alert_device = lambda: None                                          # the setup check would run system_profiler
tools._live_playing = lambda: False
tools.Spotify = lambda timeout=None: FakePlayer(24.5)
tools.ears_meter.LoopbackInput = lambda: meter.ArrayInput(np.concatenate([lead, song]), rate)


class Counting(io.TextIOBase):
    def __init__(self):
        self.count = 0

    def write(self, text):
        self.count += len(text)
        return len(text)


records = []


class Collect(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


root = logging.getLogger()
root.addHandler(Collect())
root.setLevel(logging.DEBUG)
events = []
WRITE = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
FILES = ("os.rename", "os.replace", "os.remove", "os.unlink", "os.truncate", "os.link", "os.symlink", "shutil.copyfile",
         "shutil.move")
PROCESSES = ("subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.fork", "os.forkpty", "os.spawn")


def hook(event, args):
    if event == "open":
        path, mode, flags = (list(args) + [None, None, None])[:3]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & WRITE):
            events.append(["write", str(path)])
    elif event in FILES:
        events.append(["write", str(args[1] if event in ("os.rename", "os.replace", "os.link", "os.symlink") else args[0])])
    elif event.startswith("socket.") and event not in ("socket.__new__",):
        events.append(["network", event])
    elif event in PROCESSES:
        events.append(["process", event])


sys.addaudithook(hook)
out, err = Counting(), Counting()
real_out, real_err = sys.stdout, sys.stderr
sys.stdout, sys.stderr = out, err
try:
    meter.meter(meter.ArrayInput(song, rate), 24.0, kind="external")
    meter.measure_sections(Audio(song, rate), "external")
    phase_one = list(events)
    refs.measure_stream("spotify:track:32ZmFcP0qeEIuXtO6TDZ1K", FakePlayer(24.5), meter.ArrayInput(np.concatenate([lead, song]), rate))
    phase_two = events[len(phase_one):]
    job = {"id": "audit", "state": "measuring", "done": [], "started": 0.0, "stop": threading.Event()}
    tools._run(job, ["spotify:track:2brRKInIh1aJ2r0dcZtNzm"], None, None, False)
    phase_three = events[len(phase_one) + len(phase_two):]
finally:
    sys.stdout, sys.stderr = real_out, real_err
print(json.dumps({"meter": phase_one, "stream": phase_two, "job": phase_three, "job_state": job["state"],
                  "job_error": job.get("error"), "printed": out.count + err.count, "logged": records, "refs": str(refs.folder())}))
"""


def test_external_audio_never_reaches_disk_the_network_or_the_console(tmp_path):
    """M1 and M2: during an external measurement an audit hook sees every file opened for writing, file move,
    network call and child process, and stdout, stderr and logging are counted. The meter itself does none of it;
    a streamed reference (directly and through the ref tool's job) writes only its JSON of numbers."""
    env = dict(os.environ, TEST_DIR=str(Path(__file__).parent), EARS_REFS=str(tmp_path / "refs"), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run([sys.executable, "-c", _AUDIT], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = done.stdout.strip().splitlines()
    assert len(lines) == 1, done.stdout[-2000:]                         # nothing else reached stdout
    found = json.loads(lines[0])
    assert found["meter"] == [] and found["printed"] == 0 and found["logged"] == []
    assert found["job_state"] == "finished", found["job_error"]
    for phase in ("stream", "job"):
        writes = [path for kind, path in found[phase] if kind == "write"]
        assert writes and all(path.startswith(found["refs"]) and path.endswith((".json", ".json.tmp")) for path in writes), phase
        assert [item for item in found[phase] if item[0] != "write"] == [], phase
    stored = sorted(path.name for path in (tmp_path / "refs").glob("*.json"))
    assert stored == ["closer-cztnzm.json", "closer.json"]            # two tracks titled alike keep two names
    for path in (tmp_path / "refs").glob("*.json"):
        text = path.read_text()
        assert "lufs_i" not in text and '"external"' in text


# ---------------------------------------------------------------------------
# Streamed references (M5) and owned files
# ---------------------------------------------------------------------------

def test_a_streamed_reference_is_measured_once(store, song):
    player = FakePlayer(duration=50.9)                          # 0.5 s preflight, 0.4 s lead-in, the 50 s song
    source = meter.ArrayInput(np.concatenate([silence(), silence(0.4), song]), RATE)
    ref = refs.measure_stream(URI, player, source, alerts="MacBook Pro Speakers")
    assert ref["name"] == "closer" and ref["uri"] == URI and ref["source"] == "external"
    assert sorted(ref["sections"]) == ["full", "sparse", "track"] and ref["chain"]["device"] == "array"
    assert ref["seconds"] == pytest.approx(50.0, abs=0.05)      # lead-in trimmed, 0.5 s tail left unplayed
    assert [call[0] for call in player.calls] == ["play", "pause", "seek", "resume", "pause"]   # seek while paused
    plays = len(player.calls)
    again = refs.measure_stream("https://open.spotify.com/track/32ZmFcP0qeEIuXtO6TDZ1K?si=abc", player, source)
    assert again["cached"] and len(player.calls) == plays                               # M5: no second playback
    assert (store / "closer.json").is_file() and json.loads((store / "closer.json").read_text())["name"] == "closer"


def test_sections_play_only_what_is_not_stored_and_survive_other_runs(store, song):
    player = FakePlayer(duration=50.5)
    source = meter.ArrayInput(np.concatenate([silence(), song[int(25 * RATE):]]), RATE)
    ref = refs.measure_stream(URI, player, source, name="closer-drop", sections={"drop": [25.0, 45.0]}, alerts="none")
    assert sorted(ref["sections"]) == ["drop"] and ("seek", 25.0) in player.calls and ("resume",) in player.calls
    assert ref["sections"]["drop"]["seconds"] == pytest.approx(20.0, abs=0.05) and ref["title"].startswith("Closer")
    seeks = [call for call in player.calls if call[0] == "seek"]
    source = meter.ArrayInput(np.concatenate([silence(), song]), RATE)
    both = refs.measure_stream(URI, player, source, name="closer-drop", sections={"drop": [25.0, 45.0], "intro": [0.0, 10.0]},
                               alerts="none")
    assert sorted(both["sections"]) == ["drop", "intro"]
    assert [call for call in player.calls if call[0] == "seek"][len(seeks):] == [("seek", 0.0)]   # only the missing one
    assert refs.measure_stream(URI, player, source, name="closer-drop", sections={"intro": [0.0, 10.0]})["cached"]
    whole = refs.measure_stream(URI, FakePlayer(duration=50.5), meter.ArrayInput(np.concatenate([silence(), song]), RATE),
                                name="closer-drop", alerts="none")
    assert sorted(whole["sections"]) == ["drop", "full", "intro", "sparse", "track"]          # named ones re-cut, kept
    again = refs.measure_stream(URI, FakePlayer(duration=50.5), meter.ArrayInput(np.concatenate([silence(), song[int(25 * RATE):]]), RATE),
                                name="closer-drop", sections={"drop": [25.0, 45.0]}, refresh=True, alerts="none")
    assert sorted(again["sections"]) == ["drop", "full", "intro", "sparse", "track"]          # refresh: only that one


def test_sections_are_checked_before_anything_plays(store):
    player = FakePlayer(duration=50.5)
    for bad, message in (({"track": [0, 10]}, "taken"), ({"blip": [30, 31]}, "at least 3 s"), ({"x": [10]}, "start, end"),
                         ({"x": [-1, 5]}, "start at 0"), (["drop"], "must map")):
        with pytest.raises(refs.RefError, match=message):
            refs.measure_stream(URI, player, meter.ArrayInput(silence(), RATE), sections=bad)
    assert player.calls == []
    with pytest.raises(refs.RefError, match="past the track's end"):
        refs.measure_stream(URI, player, meter.ArrayInput(silence(), RATE), sections={"tail": [40.0, 55.0]}, alerts="none")
    assert not any(call[0] in ("seek", "resume") for call in player.calls) and not list(store.glob("*.json"))


def test_a_cut_short_interrupted_or_cancelled_span_stores_nothing(store, song):
    full = np.concatenate([silence(), song])
    with pytest.raises(refs.RefError, match="nothing was stored"):                # the player moved on to the next track
        refs.measure_stream(URI, FakePlayer(duration=50.9, moves_on_after=3), meter.ArrayInput(full, RATE), alerts="none")
    count = {"calls": 0}

    def guard():
        count["calls"] += 1
        return "Live started playing during the measurement" if count["calls"] >= 2 else None

    with pytest.raises(refs.RefError, match="Live started playing"):
        refs.measure_stream(URI, FakePlayer(duration=50.9), meter.ArrayInput(full, RATE), guard=guard, alerts="none")
    stop = threading.Event()
    with pytest.raises(refs.Cancelled):
        refs.measure_stream(URI, FakePlayer(duration=50.9), meter.ArrayInput(full, RATE), stop=stop, alerts="none",
                            progress=lambda read, total: stop.set() if read > 3.0 else None)
    assert not list(store.glob("*.json"))


def test_sections_measured_before_a_failure_stay_stored(store, song):
    source = meter.ArrayInput(np.concatenate([silence(), song[:int(12 * RATE)]]), RATE)     # enough for "a" only
    with pytest.raises(refs.RefError, match="cut short"):
        refs.measure_stream(URI, FakePlayer(duration=50.5), source, name="two", sections={"a": [0.0, 8.0], "b": [20.0, 30.0]},
                            alerts="none")
    assert sorted(refs.load("two")["sections"]) == ["a"]


def test_reference_identity_names_and_collisions(store):
    other = "spotify:track:2brRKInIh1aJ2r0dcZtNzm"
    refs.save({"name": "closer", "uri": URI, "title": "Closer", "sections": {"track": {"seconds": 1.0}}})
    with pytest.raises(refs.RefError, match="choose another name"):
        refs.find(uri=other, name="closer")
    with pytest.raises(refs.RefError, match="choose another name"):
        refs.save({"name": "closer", "uri": other, "sections": {"track": {"seconds": 1.0}}})
    player = FakePlayer(duration=50.5)
    with pytest.raises(refs.RefError, match="choose another name"):
        refs.measure_stream(other, player, meter.ArrayInput(silence(), RATE), name="closer")
    assert player.calls == []
    assert refs.unique_name("closer", ("external", other)) == "closer-cztnzm"
    assert refs.unique_name("closer", ("external", URI)) == "closer"
    assert refs.unique_name("closer", ("file", "/music/Closer.flac")) == "closer-erflac"
    assert refs.find(uri=URI)["name"] == "closer" and refs.find(name="Closer")["uri"] == URI      # names ignore case
    assert refs.find(uri=URI, name="closer-again")["name"] == "closer"         # one reference per track


def test_setup_warnings_name_what_is_left_of_m6(store):
    warnings = refs.setup_warnings({"volume": 60.0}, {"device": "Scarlett Solo 4th Gen"}, alerts="Scarlett Solo 4th Gen")
    assert len(warnings) == 3 and "volume is 60" in warnings[0] and "Normalize volume" in warnings[1] and "alert" in warnings[2]
    refs.confirm_setup()
    assert refs.setup_warnings({"volume": 100.0}, {"device": "Scarlett Solo 4th Gen"}, alerts="MacBook Pro Speakers") == []


def test_owned_files_keep_absolute_figures(store, tmp_path, song):
    path = tmp_path / "mine.wav"
    write_wav(path, song, RATE, bit_depth=24)
    ref = refs.add_file(path, name="mine")
    assert ref["source"] == "file" and "lufs_i" in ref["sections"]["track"] and refs.load("mine")["name"] == "mine"
    assert [item["name"] for item in refs.all_refs()] == ["mine"]
    refs.delete("mine")
    assert refs.all_refs() == [] and refs.find(name="mine") is None
    with pytest.raises(refs.RefError):
        refs.add_file(tmp_path / "missing.wav")


def test_a_reference_refuses_anything_that_could_hold_audio(store):
    with pytest.raises(refs.RefError, match="array"):
        refs.save({"name": "x", "sections": {"track": {"samples": np.zeros(10)}}})
    with pytest.raises(refs.RefError, match="long list"):
        refs.save({"name": "x", "sections": {"track": {"samples": [0.0] * 5000}}})
    assert not (store / "x.json").exists()


def test_reference_names_and_the_store(store, monkeypatch, tmp_path):
    assert refs.ref_name("Closer - Nine Inch Noize Version") == "closer"
    assert refs.ref_name("She’s Gone Away - Nine Inch Noize Version") == "shes_gone_away"
    assert refs.folder() == store
    monkeypatch.delenv("EARS_REFS")
    monkeypatch.setenv("EARS_HOME", str(tmp_path / "home"))
    assert refs.folder() == tmp_path / "home" / "refs"


# ---------------------------------------------------------------------------
# Envelope, comparison, audio.balance
# ---------------------------------------------------------------------------

def _ref(name, values):
    return {"name": name, "sections": {"full": values, "track": values}}


def test_the_envelope_spans_the_references_with_margins(song):
    a = profiles.profile(Audio(song, RATE), absolute=False)
    b = dict(a, lra=a["lra"] + 3.0, third_octave=dict((band, value + 2.0) for band, value in a["third_octave"].items()))
    b["third_octave"].pop("25", None)
    env = refs.envelope([_ref("a", a), _ref("b", b)], "full", margin_db=1.0)
    band = next(iter(set(a["third_octave"]) - {"25"}))
    assert env["third_octave"][band] == [round(a["third_octave"][band] - 1.0, 1), round(a["third_octave"][band] + 3.0, 1)]
    assert "25" not in env["third_octave"]                   # a band one reference lacks is no common target
    assert env["scalars"]["lra"]["low"] == pytest.approx(a["lra"] - 1.0) and env["scalars"]["lra"]["high"] == pytest.approx(a["lra"] + 4.0)
    assert env["references"] == ["a", "b"] and len(env["tempo"]) == 2
    assert refs.envelope([], "full")["third_octave"] == {}


@pytest.fixture(scope="module")
def take_and_ref(spec, tmp_path_factory):
    home = tmp_path_factory.mktemp("refs-home")
    parts = fx.normalise(fx.render_parts(spec, "neon", TEMPO, rate=RATE, variations=["A"]), spec, "neon", TEMPO, variation="A")
    take = takes.load(home, fx.write_take(home, spec, "neon", TEMPO, parts, variations=["A"], bit_depth=24))
    sums, _ = tiers.tier_sums(take.parts(), spec, "neon", "A", TEMPO, bars=take.part_bars())
    reference = profiles.profile(Audio(np.tile(sums["T5"].samples, (3, 1)) * 0.5, RATE), absolute=False)
    return take, reference


def test_a_take_inside_its_own_envelope_and_outside_a_brighter_one(spec, take_and_ref):
    take, reference = take_and_ref
    same = compare.compare_envelope(take, refs.envelope([_ref("self", reference)]), spec)
    assert [row for row in same["bands"] if row["status"] != "inside"] == [] and same["outside"] == 0
    assert same["tier"] == "T5" and same["information"]["key"]["take"] == "A minor"
    assert same["information"]["tempo"]["same_as"]                                     # 140 against itself
    brighter = dict(reference, third_octave=dict((band, value + (8.0 if float(band) >= 2000 else 0.0))
                                                  for band, value in reference["third_octave"].items()))
    result = compare.compare_envelope(take, refs.envelope([_ref("bright", brighter)]), spec)
    top = result["bands"][0]
    assert top["status"] == "below" and float(top["metric"].split()[0]) >= 2000 and top["delta"] == pytest.approx(-7.0, abs=0.3)
    outside = sum(1 for row in result["bands"] if row["status"] != "inside")
    assert result["summary"].startswith("{0} of {1} bands".format(outside, len(result["bands"]))) and result["outside"] == outside
    json.dumps(result, allow_nan=False)


def test_against_masters_dynamics_are_information_and_missing_bands_are_absent(spec, take_and_ref):
    take, reference = take_and_ref
    master = dict(reference, plr_db=reference["plr_db"] - 7.0, crest_db=reference["crest_db"] - 7.0, lra=reference["lra"] - 3.0,
                  third_octave=dict(reference["third_octave"], **{"20000": -20.0}))
    env = refs.envelope([_ref("master", master)])
    env["third_octave"]["20000"] = [-21.0, -19.0]
    result = compare.compare_envelope(take, env, spec)
    dynamics = dict((row["metric"], row) for row in result["dynamics"])
    assert dynamics["peak to loudness (dB)"]["status"] == "information (above)" and len(dynamics) == 4
    assert result["outside"] == sum(1 for row in result["bands"] + result["shape"] if row["status"] != "inside")
    assert "peak to loudness" not in result["summary"] and "crest" not in result["summary"]
    absent = [row for row in result["bands"] if row["status"] == "absent"]
    assert [row["metric"] for row in absent] == ["20000 Hz band (dB re mix)"] and absent[0]["take"] is None
    sparse = compare.compare_envelope(take, dict(refs.envelope([_ref("self", reference)], "sparse"), kind="sparse"), spec)
    assert sparse["tier"] == "T2"                                                     # PRD 11.1: lower tiers vs sparse


def test_audio_balance_uses_the_stored_references(spec, take_and_ref, store):
    take, reference = take_and_ref
    refs.save(_ref("self", reference))
    envelope = refs.balance_envelope()
    assert envelope and all(isinstance(value, tuple) for value in envelope.values())
    result = analyze.analyze_take(take, spec, envelope=envelope)
    balance = [check for check in result["checks"] if check["check"] == "audio.balance"]
    assert balance and balance[0]["status"] == "pass"


def test_compare_reference_against_a_reference_at_another_level(spec, take_and_ref):
    take, reference = take_and_ref                        # the reference is the take's top tier 6 dB down
    result = compare.compare_reference(take, reference, spec)
    rows = dict((row["metric"], row) for row in result["deltas"])
    bands = [row for name, row in rows.items() if name.endswith("band (rel. loudness)")]
    assert bands and all(abs(row["delta"]) <= 0.2 for row in bands) and all(row["status"] == "information" for row in bands)
    assert rows["stereo width"]["delta"] == pytest.approx(0.0, abs=0.02)


# ---------------------------------------------------------------------------
# The loopback input itself, against a stand-in for the sounddevice module
# ---------------------------------------------------------------------------

class _Status(object):
    input_overflow = False


class FakeSoundDevice(types.ModuleType):
    """One Scarlett-like device with 4 inputs: 1-2 carry "room noise", 3-4 the loopback signal. Streams deliver
    1024-frame blocks from a thread; stall_after stops delivering after that many blocks; fail_start fails start()."""

    class CallbackStop(Exception):
        pass

    def __init__(self, loopback, noise=0.5, stall_after=None, fail_start=False):
        types.ModuleType.__init__(self, "sounddevice")
        self.loopback, self.noise, self.stall_after, self.fail_start = loopback, noise, stall_after, fail_start
        self.streams = []

    def query_devices(self):
        return [{"name": "MacBook Pro Microphone", "max_input_channels": 1, "max_output_channels": 0, "default_samplerate": 44100.0},
                {"name": "Scarlett Solo 4th Gen", "max_input_channels": 4, "max_output_channels": 2, "default_samplerate": 44100.0}]

    class CoreAudioSettings(object):
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def InputStream(self, **kwargs):
        stream = _FakeStream(self, **kwargs)
        self.streams.append(stream)
        return stream


class _FakeStream(object):
    def __init__(self, module, device, channels, samplerate, dtype, blocksize, extra_settings, callback, finished_callback):
        self.module, self.channels, self.blocksize = module, channels, blocksize
        self.map = (extra_settings.kwargs.get("channel_map") if extra_settings else None)
        self.callback, self.finished = callback, finished_callback
        self.active = self.closed = False
        self._halt = threading.Event()

    def start(self):
        if self.module.fail_start:
            raise RuntimeError("PortAudio: device unavailable")
        self.active = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        position, blocks = 0, 0
        while not self._halt.is_set():
            if self.module.stall_after is not None and blocks >= self.module.stall_after:
                time.sleep(0.01)
                continue
            frame = self.module.loopback[position:position + self.blocksize]
            if len(frame) < self.blocksize:
                frame = np.vstack([frame, np.zeros((self.blocksize - len(frame), 2))])
            full = np.column_stack([np.full((self.blocksize, 2), self.module.noise), frame]).astype(np.float32)
            data = full[:, self.map] if self.map else full[:, :self.channels]
            position, blocks = position + self.blocksize, blocks + 1
            try:
                self.callback(data, self.blocksize, None, _Status())
            except FakeSoundDevice.CallbackStop:
                break
        self.active = False
        self.finished()

    def abort(self):
        self._halt.set()
        self.active = False

    def close(self):
        self._halt.set()
        self.closed = True


def test_the_loopback_input_reads_inputs_3_and_4_only(monkeypatch, song):
    fake = FakeSoundDevice(song)
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    monkeypatch.delenv("EARS_METER_DEVICE", raising=False)
    monkeypatch.delenv("EARS_METER_CHANNELS", raising=False)
    source = meter.LoopbackInput()
    assert source.describe() == {"device": "Scarlett Solo 4th Gen", "channels": [3, 4], "rate": 44100}
    recording = source.record(1.0)
    assert recording.samples.shape == (44100, 2) and np.allclose(recording.samples, song[:44100].astype(np.float32))
    assert fake.streams[-1].closed and not fake.streams[-1].active


def test_a_stalled_or_failing_input_raises_and_closes_its_stream(monkeypatch, song):
    monkeypatch.setattr(meter, "STALL_SECONDS", 0.5)
    stalled = FakeSoundDevice(song, stall_after=5)
    monkeypatch.setitem(sys.modules, "sounddevice", stalled)
    with pytest.raises(meter.MeterError, match="stopped delivering audio"):
        meter.LoopbackInput().record(10.0)
    assert stalled.streams[-1].closed
    broken = FakeSoundDevice(song, fail_start=True)
    monkeypatch.setitem(sys.modules, "sounddevice", broken)
    with pytest.raises(meter.MeterError, match="Cannot start"):
        meter.LoopbackInput().record(1.0)
    assert broken.streams[-1].closed
    with pytest.raises(meter.MeterError, match="No input device matches"):
        meter.LoopbackInput(device="BlackHole 16ch")


# ---------------------------------------------------------------------------
# The Spotify player (AppleScript replies faked)
# ---------------------------------------------------------------------------

def test_track_uris():
    assert track_uri(URI) == URI
    assert track_uri("https://open.spotify.com/track/32ZmFcP0qeEIuXtO6TDZ1K?si=a5vt") == URI
    assert track_uri("https://open.spotify.com/intl-fr/track/32ZmFcP0qeEIuXtO6TDZ1K") == URI
    assert track_uri("32ZmFcP0qeEIuXtO6TDZ1K") == URI
    for bad in ("spotify:album:7lcpCG4RBy3njzxHXlhOnp", "closer", None):
        with pytest.raises(PlayerError):
            track_uri(bad)


def test_player_status_parsing_and_errors():
    replies = ["playing\n100\n12,5\nspotify:track:32ZmFcP0qeEIuXtO6TDZ1K\nCloser - Nine Inch Noize Version\nNine Inch Nails, Boys Noize\nNine Inch Noize\n344400"]
    player = Spotify(runner=lambda script: replies[0])
    status = player.status()
    assert status["state"] == "playing" and status["position"] == 12.5 and status["volume"] == 100.0
    assert status["track"]["duration"] == pytest.approx(344.4) and status["track"]["artist"] == "Nine Inch Nails, Boys Noize"
    assert Spotify(runner=lambda script: "stopped\n50\n0").status() == {"state": "stopped", "volume": 50.0, "position": 0.0, "track": None}
    scripts = []

    def runner(script):
        scripts.append(script)
        return replies[0]

    Spotify(runner=runner).play(URI, position=72)
    assert 'play track "{0}"'.format(URI) in scripts[0] and "set player position to 72.000" in scripts[0]
