"""Escape hatch: reach any property or function of Live's object model by path."""
from typing import Any

from ..app import call, tool


@tool(read_only=True)
def lom_get(path: str, properties: list[str] | None = None) -> dict:
    """Read an object of Live's object model by path, with all property values or only `properties`.

    Paths use Max for Live style: "live_set tracks 0 mixer_device volume", "live_set view selected_track",
    "live_app view". Lists are summarised as counts and names. Use the curated tools first; this reaches
    anything they do not cover.
    """
    return call("lom_get", path=path, properties=properties)


@tool(destructive=True)
def lom_set(path: str, property: str, value: Any) -> dict:
    """Set a writable property of the object at `path`. Pass {"path": "..."} as value to refer to an object."""
    return call("lom_set", path=path, property=property, value=value)


@tool(destructive=True)
def lom_call(path: str, method: str, args: list[Any] | None = None) -> dict:
    """Call a function of the object at `path` with positional `args` ({"path": "..."} refers to an object).

    Example: lom_call("live_set", "create_scene", [-1]). Returns the result, with a path for any object returned.
    """
    return call("lom_call", path=path, method=method, args=args)


@tool(read_only=True)
def lom_describe(path: str = "live_set") -> dict:
    """List the properties (with whether each is writable) and functions available at `path`, with Live's docs."""
    return call("lom_describe", path=path)


@tool()
def reload_remote_script(full: bool = False) -> dict:
    """Developer tool: hot-reload the Remote Script's code inside Live without restarting it.

    full=True also reloads the script's shell module. A module that fails to import is reported and the
    previous code keeps running.
    """
    return call("reload_remote_script", full=full)
