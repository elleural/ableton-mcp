"""WS-A: song settings, transport, scenes, locators, grooves and selection (docs/PRD.md 7.2, 7.7, 7.8).

Owned by workstream A.

Live applies playhead and transport changes on its next tick, so some Remote Script commands answer
{"pending": ...} and are called again (see AbletonMCP_Remote_Script/handlers/song.py), and settings are
read back with a second call.
"""
import time as _time

from mcp.server.mcpserver.exceptions import ToolError

from ..app import call, tool
from .references import loopback_busy

PENDING_ATTEMPTS = 20
PENDING_DELAY = 0.03

# set_song flags Live may silently ignore, and why.
_IGNORED_REASON = {
    "link": "Live ignores it unless the Link toggle is shown in the transport bar (Settings > Link, Tempo & MIDI)",
    "tempo_follower": "Live ignores it unless the Tempo Follower toggle is shown (Settings > Link, Tempo & MIDI)",
}
_FLAGS = (
    "scale_mode", "metronome", "loop", "punch_in", "punch_out", "follow", "record_mode", "session_record",
    "arrangement_overdub", "session_automation_record", "link", "tempo_follower",
)


def until_done(send, attempts=PENDING_ATTEMPTS):
    """Repeat a two-phase command while it answers {"pending": ...}, passing back its `restore`."""
    result = send()
    extra = {}
    for _ in range(attempts):
        if not (isinstance(result, dict) and result.get("pending")):
            return result
        if "restore" in result:
            extra["restore"] = result["restore"]
        _time.sleep(PENDING_DELAY)
        result = send(**extra)
    raise ToolError("Live did not apply the {0} move in time; check get_status and try again".format(result.get("pending")))


def unapplied(requested, state):
    """Warnings for requested flags that Live did not take."""
    warnings = []
    for name in _FLAGS:
        if name in requested and name in state and bool(requested[name]) != bool(state[name]):
            reason = _IGNORED_REASON.get(name, "Live did not accept it in the current state")
            warnings.append("{0} is still {1}: {2}".format(name, state[name], reason))
    return warnings


@tool(idempotent=True)
def set_song(
    tempo: float | None = None,
    time_signature: str | None = None,
    key: str | int | None = None,
    scale: str | None = None,
    scale_mode: bool | None = None,
    swing: float | None = None,
    groove_amount: float | None = None,
    metronome: bool | None = None,
    loop: bool | None = None,
    loop_start: float | str | None = None,
    loop_length: float | str | None = None,
    loop_end: float | str | None = None,
    punch_in: bool | None = None,
    punch_out: bool | None = None,
    launch_quantization: str | None = None,
    record_quantization: str | None = None,
    follow: bool | None = None,
    record_mode: bool | None = None,
    session_record: bool | None = None,
    arrangement_overdub: bool | None = None,
    session_automation_record: bool | None = None,
    link: bool | None = None,
    tempo_follower: bool | None = None,
) -> dict:
    """Set song-wide settings in one undo step; returns every setting as Live now reports it.

    tempo 20..999 BPM; time_signature "3/4"; key a root ("F#") or root plus scale ("A minor"); scale one of
    Live's scales ("Minor", "Dorian", ...); swing 0..1; groove_amount 0..1.31; loop_start/loop_end times and
    loop_length a length ("8 bars"), giving the arrangement loop (also the export range);
    launch_quantization "none".."1/32" ("1 bar", "1/16"); record_quantization "none", "1/16", "1/8T"...;
    follow = arrangement follows the playhead. record_mode arms arrangement recording. Example:
    set_song(tempo=124, key="A minor", time_signature="4/4"). No arguments: read the settings.
    """
    requested = dict((name, value) for name, value in (
        ("tempo", tempo), ("time_signature", time_signature), ("key", key), ("scale", scale), ("scale_mode", scale_mode),
        ("swing", swing), ("groove_amount", groove_amount), ("metronome", metronome), ("loop", loop),
        ("loop_start", loop_start), ("loop_length", loop_length), ("loop_end", loop_end), ("punch_in", punch_in),
        ("punch_out", punch_out), ("launch_quantization", launch_quantization), ("record_quantization", record_quantization),
        ("follow", follow), ("record_mode", record_mode), ("session_record", session_record),
        ("arrangement_overdub", arrangement_overdub), ("session_automation_record", session_automation_record),
        ("link", link), ("tempo_follower", tempo_follower),
    ) if value is not None)
    state = call("set_song", **requested)
    if not requested:
        return state
    state = call("set_song")  # Live shows some settings (punch, loop) only on its next tick
    warnings = unapplied(requested, state)
    if warnings:
        state["warnings"] = warnings
    return state


@tool()
def transport(action: str, position: float | str | None = None) -> dict:
    """Control playback. action: "play" (from `position` if given), "continue", "stop", "jump" (to
    `position`), "jump_to_next_locator", "jump_to_prev_locator", "play_selection", "stop_all_clips",
    "back_to_arrangement" (stop Session clips overriding the arrangement and resume it), "tap_tempo",
    "capture_midi" (recently played MIDI into a clip), "capture_scene" (playing clips into a new scene).

    position: beats, "bar.beat.sixteenth" or a locator name. While stopped, play/jump move the start
    marker. Returns the action plus the transport state read on Live's next tick.
    Example: transport("play", position="17.1.1").
    """
    if str(action).strip().lower() in ("play", "continue", "play_selection"):
        busy = loopback_busy()
        if busy:
            raise ToolError(busy)
    result = until_done(lambda **extra: call("transport", action=action, position=position, **extra))
    try:
        result["transport"] = call("get_status")["transport"]
    except (ToolError, KeyError, TypeError):
        pass
    return result


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------


@tool()
def create_scene(
    index: int = -1,
    name: str | None = None,
    color: int | str | None = None,
    tempo: float | None = None,
    time_signature: str | None = None,
) -> dict:
    """Create a Session scene (a song section) at `index` (-1 = at the end), optionally named and coloured
    (Live colour index 0..69 or "#RRGGBB"). tempo (BPM) and time_signature ("3/4") make Live switch to them
    when the scene fires. Example: create_scene(name="Chorus", tempo=128).
    """
    return call("create_scene", index=index, name=name, color=color, tempo=tempo, time_signature=time_signature)


@tool(idempotent=True)
def set_scene(
    scene: int | str,
    name: str | None = None,
    color: int | str | None = None,
    tempo: float | str | None = None,
    time_signature: str | None = None,
) -> dict:
    """Change a scene (index or name): name, color (0..69 or "#RRGGBB"), tempo in BPM, time_signature
    ("7/8"). Pass tempo="off" or time_signature="off" so the scene keeps the song's tempo or meter.
    """
    return call("set_scene", scene=scene, name=name, color=color, tempo=tempo, time_signature=time_signature)


@tool()
def fire_scene(scene: int | str, force_legato: bool = False) -> dict:
    """Launch a scene (index or name): every clip in its row starts at the launch quantization, and its
    tempo or time signature applies. Starts the transport. force_legato launches clips immediately in
    legato. Audition with get_meters; stop with transport("stop_all_clips") or transport("stop").
    """
    busy = loopback_busy()
    if busy:
        raise ToolError(busy)
    return call("fire_scene", scene=scene, force_legato=force_legato)


@tool(destructive=True)
def delete_scene(scene: int | str) -> dict:
    """Delete a scene (index or name) together with every clip in its row. Destructive: confirm with the
    user before deleting their material. A set keeps at least one scene.
    """
    return call("delete_scene", scene=scene)


@tool()
def duplicate_scene(scene: int | str) -> dict:
    """Duplicate a scene (index or name) with its clips into a new scene right below it, and select it.
    Returns the new scene; later scene indices shift by one.
    """
    return call("duplicate_scene", scene=scene)


# ---------------------------------------------------------------------------
# Locators
# ---------------------------------------------------------------------------


@tool()
def create_locator(time: float | str, name: str | None = None) -> dict:
    """Add an arrangement locator (cue point) at `time` (beats or "bar.beat.sixteenth"), optionally named.
    The transport must be stopped. Live snaps locators to the 1/16 grid, and only places them within the
    song length. Locators are indexed in time order. Example: create_locator("17.1.1", "Chorus").
    """
    return until_done(lambda **extra: call("create_locator", time=time, name=name, **extra))


@tool(idempotent=True)
def set_locator(locator: int | str, name: str) -> dict:
    """Rename a locator, addressed by index (time order) or by name. To move one, delete it and create it
    again at the new time.
    """
    return call("set_locator", locator=locator, name=name)


@tool(destructive=True)
def delete_locator(locator: int | str) -> dict:
    """Delete a locator, addressed by index (time order) or by name. The transport must be stopped; the
    playhead is put back afterwards.
    """
    return until_done(lambda **extra: call("delete_locator", locator=locator, **extra))


# ---------------------------------------------------------------------------
# Grooves
# ---------------------------------------------------------------------------


@tool(read_only=True)
def get_grooves() -> dict:
    """The groove pool: each groove's index, name, base grid and amounts (percent), plus the global groove
    amount (0..1.31). Assign a groove to a clip with set_clip(groove=...).
    """
    return call("get_grooves")


@tool(idempotent=True)
def set_groove(
    groove: int | str,
    name: str | None = None,
    base: str | None = None,
    quantize: float | None = None,
    random: float | None = None,
    timing: float | None = None,
    velocity: float | None = None,
) -> dict:
    """Edit a groove of the groove pool (index or name). base is the grid: "1/4", "1/8", "1/8T", "1/16",
    "1/16T" or "1/32". Amounts are percent: quantize, timing and random 0..100, velocity -100..100.
    The global amount is set_song(groove_amount=...).
    """
    return call("set_groove", groove=groove, name=name, base=base, quantize=quantize, random=random, timing=timing, velocity=velocity)


# ---------------------------------------------------------------------------
# Selection and feedback
# ---------------------------------------------------------------------------


@tool(idempotent=True)
def select(
    track: int | str | None = None,
    scene: int | str | None = None,
    device: int | str | list[int | str] | None = None,
    slot: int | None = None,
    view: str | None = None,
) -> dict:
    """Select in Live's UI so the user sees what you are working on: a track, a scene, a clip slot of
    `track` (shows its clip in the Detail view), or a device of `track` (index, name or rack path); and
    show a view: "Session", "Arrangement", "Detail", "Clip", "Devices" or "Browser". Pass slot or scene,
    not both. With no arguments, returns the current selection and focused view.
    """
    return call("select", track=track, scene=scene, device=device, slot=slot, view=view)


@tool(idempotent=True)
def show_message(text: str) -> dict:
    """Show a short message in Live's status bar (bottom of the window), e.g. to tell the user what the
    agent is doing. It does not open a dialog.
    """
    return call("show_message", text=text)
