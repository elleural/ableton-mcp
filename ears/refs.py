"""References: numbers that describe outside music the soundtrack is compared against (PRD section 11).

A reference is `<refs>/<name>.json` holding measurements, never audio: the track's windows (loudness
relative to its loudest part) and the profiles (ears.profile) of its sections: "track" (all of it),
"full" (windows within 3 LU of the loudest), "sparse" (3 to 12 LU below), and any named time ranges.
Streamed references are measured once while the Spotify app plays them, through the interface's loopback
(ears.meter), and keep only level-independent numbers (M4); owned files are read directly and may keep
absolute ones. The envelope is the range of each metric across references, per section kind; the
measurement ear's `audio.balance` and `compare` use it (full sections for the top tier, sparse ones for
lower tiers, PRD 11.1).

References describe music outside any one Live set, so they live in one store shared by all sets:
$EARS_REFS, else <$EARS_HOME>/refs, else ~/Music/AbletonMCP/Ears/refs.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

import numpy as np

from . import DEFAULT_ROOT, meter, safe_name
from .audio import Audio, read
from .player import PlayerError, track_uri

KINDS = ("full", "sparse", "track")
SETUP_FILE = "setup.json"
TAIL_SECONDS = 0.5           # stop this long before a streamed track ends, before the player moves on
# How far outside the references' own range a value may sit and still count as inside (the third-octave bands
# use margin_db): about what two captures of the same unchanged take differ by, rounded up.
SCALAR_MARGINS = {"lra": 1.0, "plr_db": 1.0, "crest_db": 1.0, "dynamics_spread": 1.0, "width": 0.05,
                  "correlation": 0.05, "mono_sub_loss_db": 0.5, "onset_rate": 0.15}


class RefError(Exception):
    """A reference cannot be measured, found or stored."""


def folder(path=None):
    if path:
        return Path(path).expanduser()
    if os.environ.get("EARS_REFS"):
        return Path(os.environ["EARS_REFS"]).expanduser()
    if os.environ.get("EARS_HOME"):
        return Path(os.environ["EARS_HOME"]).expanduser() / "refs"
    return DEFAULT_ROOT / "refs"


def ref_name(text):
    """A short file-safe name: "Closer - Nine Inch Noize Version" -> "closer"."""
    base = re.split(r"\s+[-–(]\s*", str(text or "").strip())[0]
    return safe_name(base.lower().replace("’", "").replace("'", ""), fallback="reference")


def _path(name, where=None):
    return folder(where) / "{0}.json".format(safe_name(name))


def _numbers_only(value, where="ref"):
    """Refuse anything that could hold audio: numpy arrays and long numeric lists."""
    if isinstance(value, np.ndarray):
        raise RefError("{0} holds an array; a reference keeps numbers only".format(where))
    if isinstance(value, dict):
        for key, item in value.items():
            _numbers_only(item, "{0}.{1}".format(where, key))
    elif isinstance(value, (list, tuple)):
        if len(value) > 2000 and all(isinstance(item, (int, float)) for item in value[:50]):
            raise RefError("{0} is a long list of numbers; a reference keeps summaries only".format(where))
        for index, item in enumerate(value):
            _numbers_only(item, "{0}[{1}]".format(where, index))


def save(ref, where=None):
    _numbers_only(ref)
    path = _path(ref["name"], where)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(ref, indent=1, sort_keys=True))
    os.replace(str(temporary), str(path))
    return path


def load(name, where=None):
    path = _path(name, where)
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def all_refs(where=None):
    base = folder(where)
    if not base.is_dir():
        return []
    out = []
    for path in sorted(base.glob("*.json")):
        if path.name == SETUP_FILE:
            continue
        try:
            item = json.loads(path.read_text())
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("sections"):
            out.append(item)
    return out


def find(uri=None, name=None, where=None):
    if name:
        found = load(ref_name(name), where) or load(name, where)
        if found:
            return found
    if uri:
        for item in all_refs(where):
            if item.get("uri") == uri:
                return item
    return None


def delete(name, where=None):
    path = _path(name, where)
    if not path.is_file():
        raise RefError("No reference named {0}".format(name))
    path.unlink()


def summary(ref):
    """The compact form for tool results: names, spans and a few headline numbers per section."""
    out = {"name": ref.get("name"), "source": ref.get("source"), "title": ref.get("title"), "artist": ref.get("artist"),
           "measured_at": ref.get("measured_at"), "seconds": ref.get("seconds"), "sections": {}}
    for kind, values in (ref.get("sections") or {}).items():
        tempo = (values.get("tempo") or {}).get("bpm")
        out["sections"][kind] = {"span": values.get("span"), "seconds": values.get("seconds"), "lra": values.get("lra"),
                                 "plr_db": values.get("plr_db"), "width": values.get("width"), "tempo": tempo,
                                 "key": (values.get("key") or {}).get("key")}
    return out


# ---------------------------------------------------------------------------
# Owned files (ref add)
# ---------------------------------------------------------------------------

def add_file(path, name=None, sections=None, where=None, a4_hz=440.0, crossover_hz=120.0):
    """Measure a file Frederic owns (lossless preferred) and store its reference."""
    try:
        audio = read(path)
    except Exception as error:
        raise RefError("Cannot read {0}: {1}".format(path, error))
    if audio.channels == 1:
        audio = Audio(np.repeat(audio.samples, 2, axis=1), audio.rate)
    measured = meter.measure_sections(Audio(audio.samples[:, :2], audio.rate), "file", sections, a4_hz, crossover_hz)
    ref = {"name": safe_name(name or ref_name(Path(path).stem)), "source": "file", "file": str(Path(path).resolve()),
           "title": Path(path).stem, "seconds": round(audio.duration, 2), "rate": audio.rate,
           "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    ref.update(measured)
    del audio
    save(ref, where)
    return ref


# ---------------------------------------------------------------------------
# Streamed references (ref measure): played in the Spotify app, measured through the loopback
# ---------------------------------------------------------------------------

def setup_state(where=None):
    path = folder(where) / SETUP_FILE
    return json.loads(path.read_text()) if path.is_file() else {}


def confirm_setup(where=None):
    """Frederic's one-time confirmation of M6 (normalisation and crossfade off in Spotify, alerts elsewhere)."""
    path = folder(where) / SETUP_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {"normalization_off": True, "crossfade_off": True, "alerts_elsewhere": True,
             "confirmed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    path.write_text(json.dumps(state, indent=1))
    return state


def alert_device():
    """Name of the macOS output that plays alert sounds, or None if it cannot be read."""
    try:
        text = subprocess.run(["system_profiler", "SPAudioDataType"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if line.startswith("        ") and not line.startswith("          ") and stripped.endswith(":"):
            current = stripped[:-1]
        if stripped == "Default System Output Device: Yes":
            return current
    return None


def setup_warnings(status, chain, where=None, alerts=None):
    """What still stands between this setup and PRD 11.2 M6, as short sentences."""
    warnings = []
    state = setup_state(where)
    if status and status.get("volume") is not None and status["volume"] < 100:
        warnings.append("Spotify's volume is {0:g}; set it to 100 (the level is not used, but low volume costs resolution)".format(status["volume"]))
    if not state.get("normalization_off"):
        warnings.append("Confirm once that Spotify > Settings > Playback has 'Normalize volume' and 'Crossfade songs' off "
                        "(the ref tool's setup action with confirm, or `ears ref setup --confirm`)")
    alerts = alert_device() if alerts is None else alerts
    if alerts and chain and alerts.split()[0].lower() in str(chain.get("device", "")).lower():
        warnings.append("macOS alert sounds play through {0}, which the meter reads; set System Settings > Sound > "
                        "'Play sound effects through' to another output".format(alerts))
    return warnings


def _record_track(player, source, uri, start, seconds, stop=None, progress=None):
    """Play `uri` from `start` and record `seconds` of it into memory; stop early if the player moves on."""
    state = {"checked": 0.0, "moved_on": False}

    def watch(read):
        if progress is not None and progress(read, seconds) is False:
            return False
        if read - state["checked"] >= 1.0:
            state["checked"] = read
            try:
                status = player.status()
            except PlayerError:
                return True
            track = status.get("track") or {}
            if status.get("state") != "playing" or track.get("uri") != uri:
                state["moved_on"] = True
                return False
        return True

    def begin():
        player.play(uri, position=start or None)

    recording = source.record(seconds, stop=stop, progress=watch, started=begin)
    try:
        player.pause()
    except PlayerError:
        pass
    return recording, state["moved_on"]


def measure_stream(uri, player, source, name=None, sections=None, where=None, refresh=False, stop=None, progress=None,
                   a4_hz=440.0, crossover_hz=120.0, alerts=None):
    """Measure a streamed track once and store its reference (cached per section: M5).

    sections None plays the whole track and finds its full and sparse parts; {name: [start, end]} plays only
    those spans. The samples stay in memory and are dropped after measuring (M1); only the level-independent
    profile is kept (M4).
    """
    uri = track_uri(uri)
    cached = find(uri=uri, name=name, where=where)
    wanted = set(sections or {}) or {"track"}
    if cached and not refresh and wanted <= set(cached.get("sections") or {}):
        return dict(cached, cached=True)
    status = player.status()
    if status.get("state") == "playing":
        player.pause()
        time.sleep(0.3)
    meter.check_silent(source)
    chain = source.describe()
    warnings = setup_warnings(status, chain, where, alerts=alerts)
    started = time.time()
    if not sections:
        info = player.play(uri)
        player.pause()
        track = info["track"]
        player.seek(0.0)
        seconds = max(1.0, float(track["duration"]) - TAIL_SECONDS)
        recording, moved_on = _record_track(player, source, uri, 0.0, seconds, stop, progress)
        if stop is not None and stop.is_set():
            raise RefError("Cancelled")
        samples, rate = recording.samples, recording.rate
        dropouts = recording.dropouts
        del recording
        begin = meter.signal_start(samples)
        if begin is None:
            raise RefError("No signal on {0} while Spotify played: is Spotify's output the device the meter reads "
                           "({1})?".format(chain["device"], chain))
        audio = Audio(samples[begin:], rate)
        del samples
        if moved_on and audio.duration < 0.9 * seconds:
            warnings.append("Spotify stopped or moved on after {0:.0f} s of {1:.0f} s".format(audio.duration, seconds))
        measured = meter.measure_sections(audio, "external", None, a4_hz, crossover_hz)
        length = round(audio.duration, 2)
        del audio
    else:
        track = player.status().get("track") or {}
        measured = {"windows": [], "sections": {}}
        dropouts, length = 0, 0.0
        for section, (start, end) in sections.items():
            seconds = float(end) - float(start)
            if seconds <= 0.5:
                raise RefError("Section {0} is shorter than half a second".format(section))
            recording, _ = _record_track(player, source, uri, float(start), seconds, stop, progress)
            if stop is not None and stop.is_set():
                raise RefError("Cancelled")
            samples, rate = recording.samples, recording.rate
            dropouts += recording.dropouts
            del recording
            begin = meter.signal_start(samples)
            if begin is None:
                raise RefError("No signal on {0} while Spotify played section {1}".format(chain["device"], section))
            audio = Audio(samples[begin:], rate)
            del samples
            part = meter.measure_sections(audio, "external", None, a4_hz, crossover_hz)["sections"]["track"]
            part["span"] = [[float(start), float(end)]]
            measured["sections"][str(section)] = part
            length += audio.duration
            del audio
        track = player.status().get("track") or track
    ref = dict(cached or {}) if not refresh else {}
    ref.update({"name": safe_name(name) if name else (cached or {}).get("name") or ref_name(track.get("name") or uri),
                "source": "external", "uri": uri, "title": track.get("name"), "artist": track.get("artist"),
                "album": track.get("album"), "duration": track.get("duration"), "chain": chain,
                "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "elapsed": round(time.time() - started, 1),
                "dropouts": dropouts, "warnings": warnings})
    if not sections:
        ref["seconds"] = length
        ref["windows"] = measured["windows"]
        ref["sections"] = measured["sections"]
    else:
        ref.setdefault("sections", {}).update(measured["sections"])
    save(ref, where)
    return ref


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

def envelope(refs, kind="full", margin_db=1.0):
    """The range of each metric across references for one section kind (a reference without that kind
    contributes its whole track). Third-octave ranges are widened by margin_db, scalars by SCALAR_MARGINS
    (onset rate by a share of itself).

    Returns {"kind", "references", "third_octave": {band: [low, high]}, "scalars": {metric: {low, high, typical}},
    "tempo": [bpm per reference], "keys": [key per reference]}.
    """
    chosen = []
    for ref in refs:
        sections = ref.get("sections") or {}
        section = sections.get(kind) or sections.get("track")
        if section and not section.get("silent"):
            chosen.append((ref.get("name"), section))
    out = {"kind": kind, "references": [name for name, _ in chosen], "third_octave": {}, "scalars": {}, "tempo": [], "keys": []}
    if not chosen:
        return out
    bands = {}
    for _, section in chosen:
        for band, value in (section.get("third_octave") or {}).items():
            bands.setdefault(band, []).append(value)
    for band, values in bands.items():
        if len(values) == len(chosen):          # a band some references do not reach carries no common target
            out["third_octave"][band] = [round(min(values) - margin_db, 1), round(max(values) + margin_db, 1)]
    from .profile import SCALAR_KEYS
    for key in SCALAR_KEYS:
        values = [section[key] for _, section in chosen if section.get(key) is not None]
        if values:
            low, high = min(values), max(values)
            margin = SCALAR_MARGINS.get(key, 0.0)
            if key == "onset_rate":
                low, high = low * (1.0 - margin), high * (1.0 + margin)
            else:
                low, high = low - margin, high + margin
            out["scalars"][key] = {"low": round(low, 3), "high": round(high, 3), "typical": round(float(np.median(values)), 3)}
    out["tempo"] = [(section.get("tempo") or {}).get("bpm") for _, section in chosen]
    out["keys"] = [(section.get("key") or {}).get("key") for _, section in chosen]
    return out


def balance_envelope(where=None, kind="full"):
    """The third-octave envelope for audio.balance, or None when no reference is stored."""
    refs = all_refs(where)
    if not refs:
        return None
    bands = envelope(refs, kind)["third_octave"]
    return dict((band, tuple(values)) for band, values in bands.items()) or None
