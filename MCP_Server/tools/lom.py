"""Escape hatch: reach any property or function of Live's object model by path."""
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ..app import call, tool

PAGE = 1000  # lom_get's largest limit (MAX_LIST_LIMIT in AbletonMCP_Remote_Script/lom.py)


@tool(read_only=True)
def lom_get(path: str, properties: list[str] | None = None, offset: int = 0, limit: int = 32) -> dict:
    """Read an object of Live's object model by path, with all property values or only `properties`.

    Paths use Max for Live style: "live_set tracks 0 mixer_device volume", "live_set view selected_track",
    "live_app view". A list of objects (a property, or a path such as "live_set tracks") gives `count` and
    the names of up to `limit` items (1..1000) from index `offset`. When those are not the whole list, the
    result adds truncated: true, `offset` and `shown`: a name missing from `items` may still exist, so page
    on (offset + shown) or raise `limit` before concluding it is absent. Use the curated tools first; this
    reaches anything they do not cover.
    """
    return call("lom_get", path=path, properties=properties, offset=offset, limit=limit)


def lom_names(path, collection):
    """Every name in a list of Live objects (`collection` of the object at `path`), in Live's order.

    lom_get answers with a window of names, so code that looks a name up must page through all of them.
    """
    names = []
    while True:
        summary = call("lom_get", path=path, properties=[collection], offset=len(names), limit=PAGE)["values"][collection]
        if "error" in summary:
            raise ToolError("Cannot read '{0} {1}': {2}".format(path, collection, summary["error"]))
        page = summary.get("items") or []
        names += page
        if not page or len(names) >= summary.get("count", 0):
            return names


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
