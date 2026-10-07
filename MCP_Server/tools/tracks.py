"""WS-B: tracks, mixer, routing, meters and buses (docs/PRD.md section 7.3). Owned by workstream B."""
import time

from mcp.server.mcpserver.exceptions import ToolError

from ..app import call, tool

ROUTING_ATTEMPTS = 20
ROUTING_DELAY = 0.05  # seconds; Live offers a new track as a routing target from its next tick (~100 ms)


def is_busy(error):
    """True when a tool error came from a Remote Script 'busy' error (worth retrying shortly)."""
    cause = error.__cause__ or error.__context__
    if getattr(cause, "code", None) == "busy":
        return True
    return "not ready yet" in str(error)


def retry_busy(function, attempts=None, delay=None):
    """Call function until it stops failing with a 'busy' error (routing lists Live has not filled yet)."""
    attempts = ROUTING_ATTEMPTS if attempts is None else attempts
    delay = ROUTING_DELAY if delay is None else delay
    for attempt in range(attempts):
        try:
            return function()
        except ToolError as error:
            if attempt == attempts - 1 or not is_busy(error):
                raise
            time.sleep(delay)


@tool()
def create_track(kind: str, name: str | None = None, index: int = -1, color: int | str | None = None,
                 device: str | None = None) -> dict:
    """Create a track: kind "midi", "audio" or "return", optionally named, coloured and with a native device.

    index: position among regular tracks (-1 = end; returns always go last). color: Live colour index
    0..69 or "#RRGGBB". device: a native Live device by name, case-insensitive ("Operator", "eq eight");
    instruments and MIDI effects need a MIDI track. Pack and Max for Live devices go through
    load_from_browser. Returns the new track's ref, routing and arm state (MIDI tracks can come up armed).
    Example: create_track("midi", "Bass", device="Operator").
    """
    return call("create_track", kind=kind, name=name, index=index, color=color, device=device)


@tool(read_only=True)
def get_track(track: int | str, detail: bool = False) -> dict:
    """Read one track: kind, colour, mute/solo/arm, monitoring, group membership, freeze state, input and
    output routing, mixer (volume dB, pan, sends in dB by return letter), top-level devices (index, name,
    class, on), non-empty Session slots, arrangement clip count and extent, and take lanes.

    detail=True adds everything else: every slot and arrangement clip, full mixer, meters and flags.
    track: index, name, "return:A" or "master".
    """
    return call("get_track", track=track, detail=detail)


@tool(idempotent=True)
def set_track(track: int | str, name: str | None = None, color: int | str | None = None, arm: bool | None = None,
              monitoring: str | None = None, fold: bool | None = None, collapsed: bool | None = None,
              input: int | str | None = None, input_channel: int | str | None = None,
              output: int | str | None = None, output_channel: int | str | None = None,
              show_chains: bool | None = None) -> dict:
    """Change a track: name, colour, arm, monitoring ("in", "auto", "off"), fold (group tracks), collapsed
    (Arrangement), show_chains (Instrument Rack), and input/output routing.

    Routing takes display names from get_routing_options, matched case-insensitively ("Main", "Sends Only",
    "Resampling", "No Input", a track name such as "Drum Bus" or a track index); channels like "1/2",
    "Post FX" or a MIDI channel number. Set the type and its channel in one call.
    Example: set_track("Vox", input="Ext. In", input_channel="1", monitoring="auto").
    """
    # Routing right after a track was created can hit lists Live has not filled yet; that is reported as
    # "busy" before anything changes, so the call is simply repeated.
    return retry_busy(lambda: call("set_track", track=track, name=name, color=color, arm=arm, monitoring=monitoring,
                                   fold=fold, collapsed=collapsed, input=input, input_channel=input_channel,
                                   output=output, output_channel=output_channel, show_chains=show_chains))


@tool(destructive=True)
def delete_track(track: int | str) -> dict:
    """Delete a regular or return track with all its clips and devices. The master cannot be deleted.

    Deleting a return also removes every track's send to it, and later returns move up a letter.
    Destructive: confirm with the user before deleting their own work (undo reverts it).
    """
    return call("delete_track", track=track)


@tool()
def duplicate_track(track: int | str, name: str | None = None) -> dict:
    """Duplicate a regular track with its devices, clips and mixer settings; the copy goes right after it
    and is selected. Optionally name the copy. Live cannot duplicate return or master tracks.
    """
    return call("duplicate_track", track=track, name=name)


@tool(read_only=True)
def get_routing_options(track: int | str) -> dict:
    """Current input and output routing of a track, with the available types and channels.

    Channels belong to the current type: after choosing another type with set_track, read again to see
    its channels. Return, group and master tracks have output routing only.
    """
    options = call("get_routing_options", track=track)
    for _ in range(ROUTING_ATTEMPTS):
        if not any("note" in (options.get(direction) or {}) for direction in ("input", "output")):
            break
        time.sleep(ROUTING_DELAY)
        options = call("get_routing_options", track=track)
    return options


@tool()
def create_bus(name: str, sources: list[int | str], color: int | str | None = None) -> dict:
    """Create a bus, Live's substitute for group tracks: a new audio track (monitoring "In", input
    "No Input") at the end of the set, with every source track's output routed into it.

    Mix the bus like any track (set_mixer, add_device). name must be unique. Sources need audio
    output (a MIDI track needs an instrument). Reverting takes two undo steps.
    Example: create_bus("Drum Bus", ["Kick", "Snare", "Hats"], color="#FF8800").
    """
    created = call("create_bus", name=name, sources=sources, color=color)
    bus = created["bus"]["name"]
    refs = [source["ref"] for source in created["sources"]]
    try:
        routed = retry_busy(lambda: call("tracks_route_to_bus", bus=bus, sources=refs))
    except ToolError:
        try:
            call("delete_track", track=bus)
        except ToolError:
            pass
        raise
    return {"bus": routed["bus"], "sources": routed["sources"], "undo_steps": 2}


@tool(read_only=True)
def get_mixer(tracks: list[int | str] | None = None) -> dict:
    """Mixer state of every regular, return and master track (or only `tracks`) in one call: volume_db,
    pan (-1..1 plus display), sends in dB keyed by return letter, mute, solo, arm, active (track
    activator), crossfade, pan_mode and split pans; the master adds crossfader and cue_volume_db.
    "-inf" means silence.
    """
    return call("get_mixer", tracks=tracks)


@tool(idempotent=True)
def set_mixer(track: int | str, volume_db: float | str | None = None, volume: float | None = None,
              pan: float | str | None = None, sends: dict[str, float | str] | None = None,
              mute: bool | None = None, solo: bool | None = None, active: bool | None = None,
              crossfade: str | None = None, pan_mode: str | None = None, left_pan: float | str | None = None,
              right_pan: float | str | None = None, crossfader: float | str | None = None,
              cue_volume_db: float | str | None = None) -> dict:
    """Set a track's mixer in one call and get the resulting mixer state back.

    volume_db: up to +6, or "-inf" (or volume: raw 0..1). pan: -1..1 or "25L"/"C"/"50R". sends:
    {return letter, index or name: dB up to 0, or "-inf"}. mute/solo (solo is not exclusive), active
    (track activator), crossfade "A"/"none"/"B", pan_mode "stereo"/"split" with left_pan/right_pan.
    Master only: crossfader (-1 = A .. 1 = B) and cue_volume_db.
    Example: set_mixer("Bass", volume_db=-6, pan=-0.2, sends={"A": -18}).
    """
    return call("set_mixer", track=track, volume_db=volume_db, volume=volume, pan=pan, sends=sends, mute=mute,
                solo=solo, active=active, crossfade=crossfade, pan_mode=pan_mode, left_pan=left_pan,
                right_pan=right_pan, crossfader=crossfader, cue_volume_db=cue_volume_db)


@tool(read_only=True)
def get_meters(tracks: list[int | str] | None = None) -> dict:
    """Momentary peak levels of every track, return and master (or only `tracks`), read from Live's meters.

    Output levels are post-fader dBFS: peak_db (max of left/right, held 1 s), left_db, right_db, plus Live's
    raw 0..1 values (dBFS = 76 * raw - 70, so "-inf" means below -70 dBFS and 6.0 the meter top).
    over_0db flags a peak at or above 0 dBFS. Audio tracks add input levels; MIDI tracks show MIDI activity
    (0..1). Meters only move while the transport plays.
    """
    return call("get_meters", tracks=tracks)
