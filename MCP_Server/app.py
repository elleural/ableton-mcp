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
create_track (with device) / load_from_browser -> create_scene per section -> create_clip + write_notes / \
write_drum_pattern -> fire_scene to audition -> arrange_from_scenes -> set_mixer / write_automation -> \
master chain on "master" -> bounce -> get_bounce_status(wait=50) -> analyze_audio -> create_release.

Conventions:
- track: name (preferred), index, "return:A" or "master". Give every track you create an explicit name: \
Live renumbers default names such as "3-Audio" when tracks move.
- device: index, name, or a rack path like "Drum Rack/Kick/Simpler". parameter: index or name; with no \
device it means the track mixer: volume, pan, send:A.
- clip: slot (Session scene index) or arrangement_clip (index from get_arrangement), never both.
- Time: beats (quarter notes) or "bar.beat.sixteenth", 1-based ("17.1.1"). Lengths: beats or "8 bars".
- Pitch: MIDI number or note name in Live's convention, C3 = 60.
- Volume and sends in dB, pan -1..1, quantization like "1/16" or "1 bar". Parameter values: numbers are \
raw, strings are display values ("-6 dB", "800 Hz", "2 s") or item names ("Sine").

Sounds: add_device and create_track(device=...) take any Live device by name ("Operator", "Drift", \
"Glue Compressor", "DS Kick"). For presets, drum kits, samples and plug-ins, search_browser then \
load_from_browser (drum_pad= loads a sample onto a pad).

Arranging and automation: compose sections as scenes, then arrange_from_scenes places them with named \
locators. Automate inside Session clips (write_automation): envelopes travel into the arrangement, but \
arrangement clips cannot get new envelopes.

Rendering: Live has no export API, so bounce records the arrangement in real time (the song plays \
audibly) and returns a job; poll get_bounce_status(wait=50) until phase is "done". create_release then \
normalises loudness (default -14 LUFS, -1 dBTP) and encodes WAV, FLAC, MP3 and AAC with tags.

Saving: save_set needs macOS UI-automation permission; if it reports unavailable, ask the user to \
press Cmd+S in Live.

Habits: prefer names over indices; read before you write (get_track, get_device, get_notes show values \
and valid options); each mutating call is one undo step, so undo reverts mistakes; tools marked \
destructive delete material, so confirm before deleting the user's work; lom_get / lom_set / lom_call / \
lom_describe reach anything else in Live's object model.
"""

mcp = MCPServer(name="ableton", title="Ableton Live", instructions=INSTRUCTIONS, version=__version__)


class LiveToolError(ToolError):
    """A failed tool call that keeps the Remote Script's error code ("busy", "not_found", ...) and hint."""

    def __init__(self, error):
        ToolError.__init__(self, str(error))
        self.code = getattr(error, "code", "live_error")
        self.hint = getattr(error, "hint", None)


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
            return to_text(func(*args, **kwargs))

        mcp.tool(annotations=annotations, structured_output=False)(wrapper)
        REGISTERED_TOOLS.append((func, annotations))
        return func

    return decorator
