"""MCP tool modules, grouped by workflow area (docs/PRD.md section 7). Importing registers them."""
from . import (  # noqa: F401
    status,       # WS-A: status, overview, undo/redo, dialogs
    project,      # WS-A: save/new/open set (UI automation)
    song,         # WS-A: song settings, transport, scenes, locators, grooves, selection
    tracks,       # WS-B: tracks, mixer, routing, meters, buses
    clips,        # WS-C: clips, notes, drum patterns, automation
    arrangement,  # WS-C: arrangement timeline
    theory,       # WS-C: music theory helpers
    devices,      # WS-D: devices, parameters, racks
    browser,      # WS-D: browser search and loading
    export,       # WS-E: bounce, analysis, release
    lom,          # lead: generic object-model access
)
