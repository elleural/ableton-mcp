"""WS-D: browser search and loading (docs/PRD.md section 7.4). Owned by workstream D."""
from ..app import call, tool


@tool(read_only=True)
def search_browser(query: str, category: str = "all", limit: int = 25, refresh: bool = False) -> dict:
    """Search Live's browser by name: devices, presets, drum kits, samples, clips, plug-ins, Max for Live
    devices and packs. Every word must appear in the name (or the path). Ranked results give name, path,
    uri, category, kind (device, preset, rack_preset, sample, clip, max_device, plugin, folder),
    is_loadable and is_device.

    category: "all" or instruments, audio_effects, midi_effects, sounds, drums, samples, clips, plugins,
    max_for_live, packs, user_library, current_project, user_folders. The index builds in the background
    ("truncated" until complete) and follows newly installed packs; refresh=True forces a rescan.
    Load a result with load_from_browser(track, uri=...).
    """
    return call("search_browser", timeout=25, query=query, category=category, limit=limit, refresh=refresh)


@tool(read_only=True)
def browse(path: str = "", limit: int = 100, offset: int = 0) -> dict:
    """List a browser folder. path "" lists the categories; "drums/Drum Hits/Kick" lists that folder (names
    match case-insensitively, file extensions optional). Items give name, path, uri, kind, is_loadable and
    is_device; page large folders with limit and offset.
    """
    return call("browse", timeout=25, path=path, limit=limit, offset=offset)


@tool(destructive=True)
def load_from_browser(track: int | str, uri: str | None = None, path: str | None = None, query: str | None = None,
                      position: int | None = None, drum_pad: int | str | None = None, slot: int | None = None) -> dict:
    """Load a browser item onto a track, chosen by exactly one of uri or path (from search_browser or
    browse) or query (the best loadable match).

    Targets: by default devices and presets go on the track (an instrument, instrument preset or drum kit
    replaces the track's instrument; a sample on a MIDI track becomes a Simpler). position: device index
    to insert at. drum_pad: a note ("C1", 36) or pad name on the track's Drum Rack. slot: Session scene
    index for a sample on an audio track (default: the first empty slot). Clips (.alc) load as a new track.
    Returns the new or replaced devices, the pad or slot, and any created tracks.
    """
    return call("load_from_browser", timeout=40, track=track, uri=uri, path=path, query=query, position=position,
                drum_pad=drum_pad, slot=slot)
