"""Command handler modules, imported in this order by core.load_handlers().

Each module registers its commands with @core.command. A module that fails to import is reported
by ping and reload_remote_script and skipped, so one broken module never takes the others down.
"""

MODULES = [
    "system",       # lead: ping, get_commands, dump_live_api
    "lom",          # lead: generic object-model access (lom_get/lom_set/lom_call/lom_describe)
    "status",       # WS-A: status, overview, undo/redo, dialogs
    "song",         # WS-A: song settings, transport, scenes, locators, grooves, selection
    "tracks",       # WS-B: tracks, mixer, routing, meters, buses
    "clips",        # WS-C: clips, notes, drum patterns, clip actions
    "automation",   # WS-F: clip automation envelopes
    "arrangement",  # WS-F: arrangement timeline, arrange_from_scenes
    "devices",      # WS-D: devices, parameters, racks, chains, device actions
    "browser",      # WS-D: browser search, browse, load
    "bounce",       # WS-E: real-time bounce engine
]
