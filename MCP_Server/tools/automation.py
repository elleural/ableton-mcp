"""WS-F: clip automation envelopes (docs/PRD.md section 7.6). Owned by workstream F."""
from ..app import call, tool


@tool(destructive=True)
def write_automation(track: int | str, parameter: int | str, slot: int | None = None,
                     arrangement_clip: int | None = None, device: int | str | list[int | str] | None = None,
                     points: list[dict] | None = None, shape: dict | None = None,
                     start: float | str | None = None, end: float | str | None = None,
                     clear_range: bool = True, units: str = "display") -> dict:
    """Automate a parameter inside a clip (clip envelope) from points or a shape; returns sampled values.

    parameter: "volume", "pan", "send:A", or a device parameter with `device`. Times are clip beats or
    "bar.beat.sixteenth" (1.1.1 = clip start). points: [{time, value}]; two points at one time make a jump.
    shape: {type: ramp|sine|triangle|square|saw|steps, from, to, period ("1 bar"), steps: [values]} over
    start..end (default: the clip loop). units "display": dB, Hz, ms, %, pan -1..1, item names; "raw":
    internal values. clear_range replaces breakpoints in the range. Envelopes loop with the clip and
    travel into the arrangement; arrangement clips can only edit envelopes they already carry.
    Example: write_automation("Pad", "volume", slot=0, shape={"type": "ramp", "from": -24, "to": 0}).
    """
    return call("write_automation", track=track, parameter=parameter, slot=slot, arrangement_clip=arrangement_clip,
                device=device, points=points, shape=shape, start=start, end=end, clear_range=clear_range, units=units)


@tool(read_only=True)
def get_automation(track: int | str, slot: int | None = None, arrangement_clip: int | None = None,
                   parameter: int | str | None = None, device: int | str | list[int | str] | None = None,
                   samples: int = 16) -> dict:
    """List the parameters a clip automates; with `parameter`, also its breakpoints and `samples` values
    across the clip loop, in display units (dB, Hz, pan ...). Works for Session clips and for the envelopes
    arrangement clips carry. Example: get_automation("Pad", slot=0, parameter="volume").
    """
    return call("get_automation", track=track, slot=slot, arrangement_clip=arrangement_clip, parameter=parameter,
                device=device, samples=samples)


@tool(destructive=True)
def clear_automation(track: int | str, slot: int | None = None, arrangement_clip: int | None = None,
                     parameter: int | str | None = None, device: int | str | list[int | str] | None = None) -> dict:
    """Remove a clip's envelope for one parameter, or every envelope when `parameter` is omitted.
    Works for Session and arrangement clips. Example: clear_automation("Pad", slot=0, parameter="volume").
    """
    return call("clear_automation", track=track, slot=slot, arrangement_clip=arrangement_clip, parameter=parameter, device=device)
