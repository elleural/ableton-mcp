"""The AbletonMCP server instance and the helpers every tool module uses.

Tool modules (MCP_Server/tools/*.py) define tools like this:

    from ..app import call, tool

    @tool(read_only=True)
    def get_track(track: int | str) -> dict:
        \"\"\"Docstring shown to the agent.\"\"\"
        return call("get_track", track=track)

`call` drops None-valued parameters and turns Remote Script errors into MCP tool errors.
Tools return JSON-safe data, which `tool` sends to the agent as compact JSON text.
Do not use `from __future__ import annotations` in tool modules: the MCP server reads the
annotations of the wrapped function at registration time.
"""
import functools
import json

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__
from .connection import AbletonError, get_connection

INSTRUCTIONS = """\
Control Ableton Live to compose, produce, mix, master and release music. You cannot hear audio or \
see Live's screen: read state back with get_* tools, and judge mixes with analyze_audio on bounces.

Typical flow: get_status -> get_song_overview -> set_song (tempo, time_signature, key, scale) -> \
create_track (with device) / load_from_browser -> one scene per section (create_scene, or set_scene to \
reuse empty ones) -> create_clip with notes or pattern (music_theory turns scales and chord progressions \
into notes) -> write_automation in those Session clips -> fire_scene to audition -> arrange_from_scenes \
-> set_mixer, returns, set_sidechain -> master chain on "master" -> bounce -> get_bounce_status(wait=50) \
-> analyze_audio -> create_release.

Conventions:
- track: name (preferred), index, "return:A" or "master". Name every track you create (names must be \
unique); Live renumbers default names such as "3-Audio" when tracks move.
- Indices are 0-based (slot = scene index, device index); bar notation is 1-based.
- device: index, name, or a rack path like "Drum Rack/Kick/Simpler". In the automation tools a parameter \
with no device means the track mixer: volume, pan, send:A.
- clip: slot (Session scene index) or arrangement_clip (index from get_arrangement, which shifts after \
edits), never both.
- Time: bare numbers are beats (quarter notes); "17.1.1" is bar 17; locator names ("Chorus") work as times. \
Clip tools use clip time (1.1.1 = clip start); arrangement tools use song time.
- Pitch: MIDI number or note name in Live's convention, C3 = 60.
- Mixer: volume and sends in dB, pan -1..1. Quantization: "1/16", "1/8T", "1 bar".
- set_device_parameters: numbers are raw values (get_device shows min/max; out of range is an error); \
strings are display values ("-6 dB", "800 Hz", "30 %", "2 s") or item names ("Sine"). write_automation \
takes display units by default.

Sounds: add_device and create_track(device=...) take any Live device by name ("Operator", "Drift", \
"Glue Compressor", "DS Kick"). Presets, drum kits, samples and plug-ins: search_browser, then \
load_from_browser (drum_pad= puts a sample on a pad). Returns: create_track(kind="return", \
device="Reverb"), then set_mixer(sends={"A": -12}). Sidechain: set_sidechain(track, source). Buses: \
create_bus. transform_notes quantizes, humanizes and transposes.

Arranging: arrangement clips are independent copies of the Session clips. Finish notes and automation in \
the Session clips first, then arrange_from_scenes; after later Session edits, re-run it with clear=True. \
Arrangement clips cannot get new envelopes.

Rendering: Live has no export API, so bounce records the arrangement in real time (the song plays \
audibly) and returns a job; poll get_bounce_status(wait=50) until phase is "done", "failed" or \
"cancelled". Polling also delivers the files and removes the temporary tracks. create_release normalises \
loudness (default -14 LUFS, -1 dBTP) and encodes WAV, FLAC, MP3 and AAC with tags.

Listening loop (you cannot hear, so check): after note edits run analyze_notes; after sound or mix \
changes run capture (one tempo; it returns the audio checks). Clear fails first. Keep a change only when \
compare("latest", "best") shows nothing regressed beyond noise (takes(action="keep")), else \
takes(action="restore"). Against outside music: ref(action="measure", uri=<Spotify track>) measures it \
once (numbers only), then compare(take, "refs"). Passing checks is not "sounds good": say so.

Saving: save_set needs macOS UI-automation permission; if unavailable, ask the user to press Cmd+S.

Habits: read before you write (get_track, get_device and get_notes show values and valid options). Errors \
start with a code such as [not_found] or [busy] and say what is valid. Most mutating calls are one undo \
step; multi-step tools report undo_steps. Destructive tools can delete or overwrite: ask first only when \
that would remove material you did not create in this session. lom_get / lom_set / lom_call / \
lom_describe reach anything else in Live.
"""

mcp = MCPServer(name="ableton", title="Ableton Live", instructions=INSTRUCTIONS, version=__version__)


class LiveToolError(ToolError):
    """A failed tool call that keeps the Remote Script's error code ("busy", "not_found", ...) and hint."""

    def __init__(self, error):
        self.code = getattr(error, "code", "live_error")
        self.hint = getattr(error, "hint", None)
        message = "[{0}] {1}".format(self.code, getattr(error, "message", None) or str(error))
        if self.hint:
            message += " Hint: " + self.hint
        ToolError.__init__(self, message)


# (function, annotations) for every registered tool, in registration order; used to generate docs.
REGISTERED_TOOLS = []


def call(command, timeout=None, **params):
    """Send a command to the Remote Script and return its result.

    None-valued parameters are omitted so the Remote Script applies its defaults.
    Remote Script errors become LiveToolError (a ToolError carrying `code` and `hint`), which the
    agent sees as a failed tool call.
    """
    params = dict((key, value) for key, value in params.items() if value is not None)
    try:
        return get_connection().send_command(command, params, timeout=timeout)
    except AbletonError as error:
        raise LiveToolError(error) from error


def to_text(result):
    """Compact JSON for structured results; strings and content lists (images) pass through."""
    if isinstance(result, (str, list)):
        return result
    return json.dumps(result, separators=(",", ":"), ensure_ascii=False, default=str)


def tool(read_only=False, destructive=False, idempotent=False, title=None):
    """Register an MCP tool whose function returns JSON-safe data.

    read_only: never changes the Live Set. destructive: may delete or overwrite material.
    idempotent: repeating the call with the same arguments has no further effect.
    Returns the undecorated function so tests can call it directly.
    """
    annotations = ToolAnnotations(
        title=title,
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent or read_only,
        open_world_hint=False,
    )

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return to_text(func(*args, **kwargs))
            except ToolError:
                raise
            except Exception as error:  # Surface the cause; the SDK would otherwise hide it.
                raise ToolError("{0} failed: {1}: {2}".format(func.__name__, type(error).__name__, error)) from error

        mcp.tool(annotations=annotations, structured_output=False)(wrapper)
        REGISTERED_TOOLS.append((func, annotations))
        return func

    return decorator
