"""References and the meter (PRD section 11): profiles, the in-memory meter, streamed and owned references,
the envelope and comparisons against it. M1 (no audio to disk), M2 (no route out), M4 (no absolute level for
an external source) and M5 (each section plays once) are tested here without a device or Spotify; M3 and the
calibration tone run on the Mac (tests/live/test_meter.py)."""
import json
import os
import subprocess
import sys
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
    """The Spotify interface ears.refs uses, without Spotify."""

    def __init__(self, duration, name="Closer - Nine Inch Noize Version", volume=100.0):
        self.duration, self.name, self.volume = duration, name, volume
        self.state, self.uri, self.calls = "paused", None, []

    def status(self):
        track = None
        if self.uri:
            track = {"uri": self.uri, "name": self.name, "artist": "Nine Inch Nails, Boys Noize", "album": "Nine Inch Noize",
                     "duration": self.duration}
        return {"state": self.state, "volume": self.volume, "position": 0.0, "track": track}

    def play(self, uri, position=None):
        self.calls.append(("play", uri, position))
        self.uri, self.state = uri, "playing"
        return self.status()

    def pause(self):
        self.calls.append(("pause",))
        self.state = "paused"
        return self.status()

    def seek(self, position):
        self.calls.append(("seek", position))
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
    for key in ("lra", "plr_db", "crest_db", "dynamics_spread", "width", "correlation", "mono_sub_loss_db", "onset_rate"):
        assert quiet[key] == pytest.approx(loud[key], abs=0.15), key
    assert quiet["tempo"]["bpm"] == pytest.approx(loud["tempo"]["bpm"], abs=0.3) and quiet["key"] == loud["key"]


def test_absolute_figures_only_when_allowed(song):
    values = profiles.profile(Audio(song, RATE), absolute=True)
    assert set(profiles.ABSOLUTE_KEYS) <= set(values)
    assert not set(profiles.shape_only(values)) & set(profiles.ABSOLUTE_KEYS)
    assert profiles.profile(Audio(np.zeros((RATE * 2, 2)), RATE)) == {"seconds": 2.0, "silent": True}


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


def test_meter_refuses_silence_and_a_busy_loopback(song):
    with pytest.raises(meter.MeterError, match="No signal"):
        meter.meter(meter.ArrayInput(silence(2.0), RATE), 2.0)
    with pytest.raises(meter.MeterError, match="already playing"):
        meter.check_silent(meter.ArrayInput(song, RATE))
    assert meter.check_silent(meter.ArrayInput(silence(), RATE)) <= meter.SILENCE_DBFS
    with pytest.raises(meter.MeterError):
        meter.meter(meter.ArrayInput(song, RATE), 2.0, kind="file")


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
import json, os, sys
import numpy as np
from ears import meter, refs
from ears.audio import Audio
sys.path.insert(0, os.environ["TEST_DIR"])
from test_references import FakePlayer, groove
rate = 44100
song = groove(124.0, 24.0)
lead = np.zeros((int(0.6 * rate), 2))
meter.meter(meter.ArrayInput(song, rate), 6.0, kind="external")          # warm up lazy imports before the hook
events = []
WRITE = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
def hook(event, args):
    if event == "open":
        path, mode, flags = (list(args) + [None, None, None])[:3]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & WRITE):
            events.append(["write", str(path)])
    elif event in ("os.rename", "os.replace", "os.remove", "os.unlink", "os.truncate", "shutil.copyfile", "shutil.move"):
        events.append(["write", str(args[1] if event in ("os.rename", "os.replace") else args[0])])
    elif event in ("socket.connect", "socket.sendto", "socket.sendmsg", "socket.bind", "socket.getaddrinfo"):
        events.append(["network", str(args[1:2])])
    elif event == "subprocess.Popen":
        events.append(["process", str(args[1])])
sys.addaudithook(hook)
result = meter.meter(meter.ArrayInput(song, rate), 24.0, kind="external")
measured = meter.measure_sections(Audio(song, rate), "external")
phase_one = list(events)
source = meter.ArrayInput(np.concatenate([lead, song]), rate)
ref = refs.measure_stream("spotify:track:32ZmFcP0qeEIuXtO6TDZ1K", FakePlayer(24.5), source, alerts="MacBook Pro Speakers")
print(json.dumps({"meter_events": phase_one, "stream_events": events[len(phase_one):], "refs": str(refs.folder())}))
"""


def test_external_audio_never_reaches_disk_or_the_network(tmp_path):
    """M1 and M2: an audit hook sees every file write, network call and child process during an external
    measurement; the meter makes none, and a streamed reference writes only its JSON of numbers."""
    env = dict(os.environ, TEST_DIR=str(Path(__file__).parent), EARS_REFS=str(tmp_path / "refs"), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run([sys.executable, "-c", _AUDIT], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr[-2000:]
    found = json.loads(done.stdout.strip().splitlines()[-1])
    assert found["meter_events"] == []
    writes = [path for kind, path in found["stream_events"] if kind == "write"]
    assert writes and all(path.startswith(found["refs"]) and path.endswith((".json", ".json.tmp")) for path in writes)
    assert [item for item in found["stream_events"] if item[0] != "write"] == []
    stored = json.loads((tmp_path / "refs" / "closer.json").read_text())
    assert "lufs_i" not in json.dumps(stored) and stored["source"] == "external"


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
    assert [call[0] for call in player.calls] == ["play", "pause", "seek", "play", "pause"]
    plays = len(player.calls)
    again = refs.measure_stream("https://open.spotify.com/track/32ZmFcP0qeEIuXtO6TDZ1K?si=abc", player, source)
    assert again["cached"] and len(player.calls) == plays                               # M5: no second playback
    assert (store / "closer.json").is_file() and json.loads((store / "closer.json").read_text())["name"] == "closer"


def test_sections_of_a_streamed_reference_play_only_those_spans(store, song):
    player = FakePlayer(duration=50.5)
    source = meter.ArrayInput(np.concatenate([silence(), song[int(25 * RATE):]]), RATE)
    ref = refs.measure_stream(URI, player, source, name="closer-drop", sections={"drop": [25.0, 45.0]}, alerts="none")
    assert sorted(ref["sections"]) == ["drop"] and ("play", URI, 25.0) in player.calls
    assert ref["sections"]["drop"]["seconds"] == pytest.approx(20.0, abs=0.05)
    cached = refs.measure_stream(URI, player, source, name="closer-drop", sections={"drop": [25.0, 45.0]})
    assert cached["cached"]


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
    bands_out = [row for row in same["deltas"] if row["metric"].endswith("(dB re mix)") and row["status"] != "inside"]
    assert bands_out == [] and same["tier"] == "T5" and same["information"]["key"]["take"] == "A minor"
    assert same["information"]["tempo"]["same_as"]                                     # 140 against itself
    brighter = dict(reference, third_octave=dict((band, value + (8.0 if float(band) >= 2000 else 0.0))
                                                  for band, value in reference["third_octave"].items()))
    result = compare.compare_envelope(take, refs.envelope([_ref("bright", brighter)]), spec)
    top = result["deltas"][0]
    assert top["status"] == "below" and float(top["metric"].split()[0]) >= 2000 and top["delta"] == pytest.approx(-7.0, abs=0.3)
    assert result["summary"].startswith("{0} of".format(sum(1 for row in result["deltas"] if row["status"] != "inside" and row["metric"].endswith("(dB re mix)"))))
    json.dumps(result, allow_nan=False)


def test_audio_balance_uses_the_stored_references(spec, take_and_ref, store):
    take, reference = take_and_ref
    refs.save(_ref("self", reference))
    envelope = refs.balance_envelope()
    assert envelope and all(isinstance(value, tuple) for value in envelope.values())
    result = analyze.analyze_take(take, spec, envelope=envelope)
    balance = [check for check in result["checks"] if check["check"] == "audio.balance"]
    assert balance and balance[0]["status"] == "pass"


def test_compare_reference_reads_a_reference_section(spec, take_and_ref):
    take, reference = take_and_ref
    result = compare.compare_reference(take, reference, spec)
    rows = dict((row["metric"], row) for row in result["deltas"])
    assert rows["stereo width"]["delta"] == pytest.approx(0.0, abs=0.02) and "sub band (rel. loudness)" in rows


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
