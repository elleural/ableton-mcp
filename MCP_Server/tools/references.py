"""References and the meter (docs/listening-loop-prd.md section 11): numbers about outside music.

A streamed reference is played in the Spotify desktop app and measured through the audio interface's
loopback while it plays; only level-independent numbers are kept (ears.refs, ears.meter). Nothing from
an external source reaches disk, a log or a tool result as audio. `compare(take, "refs")` then compares a
take's shape against the references.
"""
import threading
import time

from mcp.server.mcpserver.exceptions import ToolError

from ears import meter as ears_meter
from ears import refs as ears_refs
from ears.player import PlayerError, Spotify, track_uri

from ..app import call, tool

MAX_WAIT = 600.0
MAX_METER_SECONDS = 120.0
_LOCK = threading.Lock()
_METER = threading.Lock()
_JOB = {}


def _live_playing():
    try:
        return bool(call("get_status").get("transport", {}).get("playing"))
    except ToolError:
        return False          # Live not running: nothing of it can reach the loopback


def _guard():
    """Checked every second while a reference plays: Live must stay silent, or it is measured too."""
    return "Live started playing during the measurement" if _live_playing() else None


def loopback_busy():
    """Why Live must not play now (a reference is being measured through the loopback), or None. Tools that start
    playback (capture, bounce, fire_scene, fire_clip, transport) refuse while this is set."""
    if _JOB.get("state") == "measuring":
        return ("A reference is being measured through the loopback ({0}); Live must stay silent until it ends: "
                "call ref() to wait or ref(action='cancel')".format(_JOB["id"]))
    return None


def _spotify_playing():
    """True or False when Spotify's state is known, None when it cannot be read (not permitted, not answering)."""
    player = Spotify(timeout=3.0)
    if not player.running():
        return False
    try:
        return player.status().get("state") == "playing"
    except PlayerError:
        return None


def _job_view(job):
    out = {"job": job["id"], "state": job["state"], "done": job["done"], "elapsed": round(time.time() - job["started"], 1)}
    if job.get("current") and job["state"] == "measuring":
        out["current"] = job["current"]
    if job.get("error"):
        out["error"] = job["error"]
    if job["state"] == "measuring":
        out["hint"] = "Measuring in real time; call ref() to keep waiting or ref(action='cancel') to stop."
    return out


def _run(job, uris, names, sections, refresh):
    try:
        player, source = Spotify(), ears_meter.LoopbackInput()
        for index, uri in enumerate(uris):
            if job["stop"].is_set():
                break
            job["current"] = {"uri": uri, "index": index + 1, "of": len(uris), "seconds": 0.0, "total": None}

            def progress(read, total):
                job["current"].update(seconds=round(read, 1), total=round(total, 1))

            name = names[index] if names and index < len(names) else None
            ref = ears_refs.measure_stream(uri, player, source, name=name, sections=sections, refresh=refresh,
                                           stop=job["stop"], progress=progress, guard=_guard)
            job["done"].append(dict(ears_refs.summary(ref), cached=bool(ref.get("cached")), warnings=ref.get("warnings") or []))
        job["state"] = "cancelled" if len(job["done"]) < len(uris) else "finished"
    except ears_refs.Cancelled as error:
        job["state"], job["error"] = "cancelled", str(error)
    except (ears_refs.RefError, ears_meter.MeterError, PlayerError) as error:
        job["state"], job["error"] = "failed", str(error)
    except Exception as error:   # keep the server alive; the agent sees the message
        job["state"], job["error"] = "failed", "{0}: {1}".format(type(error).__name__, error)


def _wait(job, wait):
    deadline = time.time() + max(0.0, min(float(wait), MAX_WAIT))
    while job["state"] == "measuring" and time.time() < deadline:
        time.sleep(0.5)
    return _job_view(job)


def _sections(sections):
    """{name: [start_s, end_s]} checked before any playback starts."""
    try:
        return ears_refs.check_sections(sections)
    except ears_refs.RefError as error:
        raise ToolError(str(error))


def _start(uris, names, sections, refresh, wait):
    with _LOCK:
        if _JOB.get("state") == "measuring":
            raise ToolError("A measurement is running ({0}); call ref() to wait or ref(action='cancel')".format(_JOB["id"]))
        if _METER.locked():
            raise ToolError("A meter call is reading the loopback; wait for it")
        if _live_playing():
            raise ToolError("Live is playing, and the loopback would measure it too: stop Live first (transport stop)")
        job = {"id": "ref-{0}".format(int(time.time() * 1000)), "state": "measuring", "done": [], "started": time.time(),
               "stop": threading.Event()}
        _JOB.clear()
        _JOB.update(job)
        thread = threading.Thread(target=_run, args=(_JOB, uris, names, sections, refresh), name="ears-ref", daemon=True)
        thread.start()
    return _wait(_JOB, wait)


@tool(destructive=True)
def ref(action: str = "status", name: str | None = None, uri: str | list[str] | None = None, file: str | None = None,
        sections: dict | None = None, refresh: bool = False, position: float | None = None, wait: float = 300.0) -> dict:
    """References the soundtrack is compared against: measured once, kept as numbers, never as audio.

    action:
    - "measure": play Spotify track(s) in the Spotify app (uri: spotify:track:..., an open.spotify.com/track
      link, or a list) and measure each through the audio interface's loopback. Takes as long as the music;
      waits up to `wait` s, then call ref() again. Cached per track (refresh=True re-measures).
      sections={"drop": [72, 102]} measures only those spans (seconds). Stop Live first.
    - "add": measure a file Frederic owns (file=path; sections optional).
    - "list": stored references, their sections (track, full, sparse) and the shared envelope.
    - "play" (uri, position s) / "pause": the Spotify app, for listening.
    - "setup": what is left of the one-time setup (Spotify's normalisation and crossfade off, volume 100,
      macOS alerts through another output). Only Frederic confirms it: `uv run ears ref setup --confirm`.
    - "status" (default) / "cancel": the running measurement. "delete": remove reference `name`.
    Then compare(take, "refs") compares a take's top tier against all references.
    """
    action = (action or "status").strip().lower()
    if action == "status":
        if not _JOB:
            return {"state": "idle", "references": len(ears_refs.all_refs())}
        return _wait(_JOB, wait if _JOB.get("state") == "measuring" else 0)
    if action == "cancel":
        if _JOB.get("state") != "measuring":
            raise ToolError("No measurement is running")
        _JOB["stop"].set()
        return _wait(_JOB, 15)
    if action == "measure":
        if not uri:
            raise ToolError("measure needs uri (a Spotify track, link or list of them)")
        items = uri if isinstance(uri, list) else [uri]
        try:
            uris = [track_uri(item) for item in items]
        except PlayerError as error:
            raise ToolError(str(error))
        names = [name] if name and len(uris) == 1 else None
        return _start(uris, names, _sections(sections), refresh, wait)
    if action == "add":
        if not file:
            raise ToolError("add needs file (a path to audio Frederic owns)")
        sections = _sections(sections)
        try:
            return {"added": ears_refs.summary(ears_refs.add_file(file, name=name, sections=sections))}
        except ears_refs.RefError as error:
            raise ToolError(str(error))
    if action == "list":
        items = ears_refs.all_refs()
        envelope = ears_refs.envelope(items, "full") if items else None
        return {"folder": str(ears_refs.folder()), "references": [ears_refs.summary(item) for item in items],
                "envelope": {"references": envelope["references"], "bands": len(envelope["third_octave"]),
                             "scalars": envelope["scalars"], "tempo": envelope["tempo"], "keys": envelope["keys"]} if envelope else None}
    if action in ("play", "pause"):
        if _JOB.get("state") == "measuring":
            raise ToolError("A reference is being measured; play and pause would cut it short (ref(action='cancel') first)")
        try:
            player = Spotify()
            if action == "pause":
                return player.pause()
            if not uri:
                raise ToolError("play needs uri")
            return player.play(uri if isinstance(uri, str) else uri[0], position=position)
        except PlayerError as error:
            raise ToolError(str(error))
    if action == "setup":
        state = ears_refs.setup_state()
        try:
            status = Spotify().status()
        except PlayerError as error:
            status = {"error": str(error)}
        try:
            chain = ears_meter.LoopbackInput().describe()
        except ears_meter.MeterError as error:
            chain = {"error": str(error)}
        return {"confirmed": state, "spotify": status, "loopback": chain,
                "warnings": ears_refs.setup_warnings(status if "error" not in status else None, chain if "error" not in chain else None)}
    if action == "delete":
        if not name:
            raise ToolError("delete needs name")
        try:
            ears_refs.delete(name)
        except ears_refs.RefError as error:
            raise ToolError(str(error))
        return {"deleted": name}
    raise ToolError("action must be measure, add, list, play, pause, setup, status, cancel or delete")


@tool(read_only=True)
def meter(seconds: float = 10.0, source: str = "live") -> dict:
    """Measure what the Mac is playing now, for `seconds` (at most 120), in memory; numbers only.

    source "live": Live's output through the same loopback as the references (start playback first, e.g.
    fire_scene); includes integrated loudness and true peak. source "external": another player such as
    Spotify; level-independent numbers only (its level depends on the player's volume and normalisation).
    """
    source = (source or "live").strip().lower()
    if source not in ("live", "external"):
        raise ToolError("source must be live or external")
    if not ears_meter.MIN_SECONDS <= float(seconds) <= MAX_METER_SECONDS:
        raise ToolError("seconds must be between {0:g} and {1:g}".format(ears_meter.MIN_SECONDS, MAX_METER_SECONDS))
    if not _METER.acquire(blocking=False):
        raise ToolError("Another meter call is reading the loopback; wait for it")
    try:
        busy = loopback_busy()
        if busy:
            raise ToolError(busy)
        playing = _live_playing()
        if source == "live" and not playing:
            raise ToolError("Live is not playing: start playback first (fire_scene, or transport play)")
        if source == "external" and playing:
            raise ToolError("Live is playing, and the loopback would measure it too: stop Live first")
        spotify = _spotify_playing() if source == "live" else False
        if spotify:
            raise ToolError("Spotify is playing, and the loopback would measure it with Live: pause it first (ref(action='pause'))")
        try:
            result = ears_meter.meter(ears_meter.LoopbackInput(), float(seconds), kind=source if spotify is False else "external")
        except ears_meter.MeterError as error:
            raise ToolError(str(error))
        if spotify is None:
            result["warning"] = ("Could not check whether Spotify is playing, so no absolute level is given (the loopback "
                                 "might hold Spotify's audio too)")
        return result
    finally:
        _METER.release()
