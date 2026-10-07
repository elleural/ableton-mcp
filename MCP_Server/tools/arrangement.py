"""WS-F: arrangement timeline, arrange_from_scenes and clear_arrangement (docs/PRD.md section 7.7). Owned by workstream F.

Long arrangement edits run as several short Remote Script calls (each about 0.75 s of Live's main thread,
resumed with `resume`), so Live never freezes. Locators need one call each: Live creates a locator at
the playhead, which moves one main-thread tick after it is written (see handlers/arrangement.py).
"""
from mcp.server.mcpserver.exceptions import ToolError

from ..app import call, tool

LOCATOR_ATTEMPTS = 4
MAX_CALLS = 500


@tool(read_only=True)
def get_arrangement(start: float | str | None = None, end: float | str | None = None,
                    tracks: list[int | str] | None = None, limit: int = 200) -> dict:
    """The arrangement timeline: each track's clips (index for arrangement_clip refs, name, start and end in
    beats and bars, length, looping, type, colour, envelopes), plus locators, loop region and song length.

    start/end keep only clips overlapping that range (beats or "bar.beat.sixteenth"); tracks limits the
    tracks. At most `limit` clips are listed. Example: get_arrangement(start="9.1.1", end="17.1.1").
    """
    return call("get_arrangement", start=start, end=end, tracks=tracks, limit=limit)


@tool(destructive=True)
def arrange_from_scenes(sections: list[dict], start: float | str = "1.1.1", clear: bool = False,
                        tracks: list[int | str] | None = None, locators: bool = True) -> dict:
    """Build the arrangement from scenes: sections play one after another from `start`, each placing
    every track's clip from its scene for the section's length.

    sections: [{scene (index or name), bars (or length: beats / "8 bars"), name?}]. Looping clips loop
    to fill a section exactly, at any length; one-shot clips play once. Clip envelopes travel along.
    A track's range is overwritten where it has a clip; clear=True first empties the whole range on the
    affected tracks (default: all). locators=True adds a locator per section, named after it (Live must
    be stopped). Returns undo_steps for undo. Example: arrange_from_scenes([{"scene": "Intro", "bars": 4},
    {"scene": "Verse", "bars": 8}]). Verify with get_arrangement.
    """
    placed, warnings, cleared = [], [], {"deleted": 0, "trimmed": 0}
    resume, calls = 0, 0
    while True:
        result = call("arrange_from_scenes", timeout=60, sections=sections, start=start, clear=clear, tracks=tracks,
                      locators=locators, resume=resume)
        calls += 1
        placed += result.pop("placed", [])
        warnings += result.pop("warnings", [])
        part = result.pop("cleared", None) or {}
        cleared["deleted"] += part.get("deleted", 0)
        cleared["trimmed"] += part.get("trimmed", 0)
        resume = result.pop("resume", None)
        if resume is None or calls >= MAX_CALLS:
            break
    for section in result["sections"]:
        section["tracks"] = [item["track"] for item in placed if item["section"] == section["index"]]
        automated = [item["track"] for item in placed if item["section"] == section["index"] and item["automated"]]
        if automated:
            section["automated"] = automated
    result["clips_placed"] = len(placed)
    if clear:
        result["cleared"] = cleared
    pending = result.pop("locators_pending", None)
    restore = result.pop("playhead_restore", None)
    changed = 0
    if pending:
        result["locators"], errors = _add_locators(pending, restore)
        changed = sum(1 for item in result["locators"] if not item.get("existing") or item.get("renamed_from"))
        if errors:
            result["locator_errors"] = errors
    if warnings:
        result["warnings"] = warnings
    if resume is not None:
        result["unfinished"] = "Stopped after {0} calls; call again to continue".format(calls)
    result["undo_steps"] = calls + changed
    return result


def _add_locators(pending, restore):
    """Create the queued locators one call (tick) at a time, then put the playhead back."""
    created, errors = [], []
    for position, item in enumerate(pending):
        then = pending[position + 1]["time"] if position + 1 < len(pending) else restore
        outcome = None
        try:
            for _ in range(LOCATOR_ATTEMPTS):
                outcome = call("arrangement_locator", time=item["time"], name=item["name"], then=then)
                if outcome.get("status") == "done":
                    break
        except ToolError as error:
            errors.append({"name": item["name"], "time": item["time"], "error": str(error)})
            if getattr(error, "code", None) == "busy":  # Live is playing: the rest would fail too
                break
            continue
        if not outcome or outcome.get("status") != "done":
            errors.append({"name": item["name"], "time": item["time"], "error": "the playhead did not settle on the locator time"})
            continue
        locator = outcome["locator"]
        if not outcome.get("created"):
            locator["existing"] = True
        if outcome.get("renamed_from") is not None:
            locator["renamed_from"] = outcome["renamed_from"]
        created.append(locator)
    return created, errors


@tool(destructive=True)
def clear_arrangement(tracks: list[int | str] | None = None, start: float | str | None = None,
                      end: float | str | None = None, mode: str = "trim") -> dict:
    """Delete arrangement clips by track and time range. Destructive: confirm before deleting the user's work.

    mode "trim" (default) empties exactly start..end: clips inside are deleted and clips crossing an edge
    are cut there. "overlapping" deletes every clip touching the range, whole; "inside" deletes only clips
    entirely within it. Omit start/end for the whole timeline and tracks for every track. Times are beats
    or "bar.beat.sixteenth". Example: clear_arrangement(tracks=["Bass"], start="9.1.1", end="17.1.1").
    """
    total, reports, resume, calls = None, {}, 0, 0
    while True:
        result = call("clear_arrangement", tracks=tracks, start=start, end=end, mode=mode, resume=resume)
        calls += 1
        for entry in result.pop("tracks", []):
            if entry["name"] in reports:  # a track whose cuts finished on a later call
                merged = reports[entry["name"]]
                merged.update(deleted=merged["deleted"] + entry["deleted"], trimmed=merged["trimmed"] + entry["trimmed"], remaining=entry["remaining"])
            else:
                reports[entry["name"]] = entry
        if total is None:
            total = result
        else:
            total["deleted"] += result["deleted"]
            total["trimmed"] += result["trimmed"]
        resume = result.pop("resume", None)
        if resume is None or calls >= MAX_CALLS:
            break
    total["tracks"] = list(reports.values())
    total["undo_steps"] = calls
    return total
