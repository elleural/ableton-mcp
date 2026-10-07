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
see Live's screen: read state back with get_* tools and use analyze_audio on bounced files.

Typical flow: get_status -> get_song_overview -> set_song (tempo, time_signature, key, scale) -> \
create_track (+ add_device / load_from_browser) -> create_clip + write_notes / write_drum_pattern -> \
fire_scene to audition -> arrange_from_scenes -> set_mixer / write_automation -> master chain on \
"master" -> bounce -> get_bounce_status -> analyze_audio -> create_release -> save_set.

Conventions:
- track: index of a regular track, its name, "return:A" (letter, index or name), or "master".
- device: index, name, or a rack path such as "Drum Rack/Kick/Simpler". parameter: index or name. \
With no device, parameter means the track mixer: volume, pan, send:A.
- clip: pass slot (Session scene index) or arrangement_clip (index from get_arrangement), not both.
- Time: beats (quarter notes) or "bar.beat.sixteenth", 1-based ("17.1.1"). Lengths: beats or "8 bars".
- Pitch: MIDI number or note name in Live's convention, where C3 = 60.
- Volume and sends in dB; pan -1..1; quantization like "1/16", "1/8T", "1 bar".
- Parameter values: numbers are raw values; strings are display values ("-6 dB", "800 Hz") or item \
names ("Sine").

Tips:
- Prefer names over indices; indices shift when tracks, scenes or clips are added or removed.
- Read before you write: get_track, get_device and get_notes show current values and valid options.
- Each mutating call is one undo step; call undo to revert a mistake.
- Rendering is real time: bounce returns a job; poll get_bounce_status(wait=...) until it is done.
- lom_get / lom_set / lom_call / lom_describe reach anything else in Live's object model.
- Destructive tools delete material; confirm with the user before deleting their own work.
"""

mcp = MCPServer(name="ableton", title="Ableton Live", instructions=INSTRUCTIONS, version=__version__)


def call(command, timeout=None, **params):
    """Send a command to the Remote Script and return its result.

    None-valued parameters are omitted so the Remote Script applies its defaults.
    Remote Script errors become ToolError, which the agent sees as a failed tool call.
    """
    params = dict((key, value) for key, value in params.items() if value is not None)
    try:
        return get_connection().send_command(command, params, timeout=timeout)
    except AbletonError as error:
        raise ToolError(str(error))


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
        return func

    return decorator
