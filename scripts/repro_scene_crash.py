"""Try to reproduce the Live 12.4.6 crash of 2026-10-07 (FatalError std::out_of_range in
LSong::OnSceneTransactionCounterChanged), on scratch objects only.

The crash came at the end of tests/live/test_e2e_release.py, when its cleanup deleted three tracks, a return
track and two scenes in ONE batch (one main-thread tick). This script rebuilds that state with "[repro]" objects
and runs the same deletions, in one of several shapes, so a crash can be narrowed down to one of them:

    all-in-one      the original: tracks, return, scenes in one batch (default)
    scenes-batch    tracks and the return one call each, then both scenes in one batch
    tracks-batch    the tracks and the return in one batch, then the scenes one call each
    separate        every deletion its own call (what the live tests do now)

It refuses to run unless the open set is saved (a crash must not cost unsaved work) and asks for --go.
Watch `ableton-mcp journal` (or `ableton-mcp journal --crash` after a crash): the last "item" line without an
"end" names the deletion that killed Live.

    uv run python scripts/repro_scene_crash.py --go [--shape all-in-one] [--rounds 3]
"""
import argparse
import sys
import time

from MCP_Server.connection import AbletonConnection, AbletonError

PREFIX = "[repro]"


def lom(live, kind, **params):
    return live.send_command("lom_" + kind, params)


def names(live, collection):
    """Every name in the collection, in Live's order: one lom_get shows a window of names, so page through them."""
    found = []
    while True:
        summary = lom(live, "get", path="live_set", properties=[collection], offset=len(found), limit=1000)["values"][collection]
        page = summary.get("items", [])
        found += page
        if not page or len(found) >= summary.get("count", 0):
            return found


def build(live):
    """Three MIDI tracks with an instrument and clips in two new scenes, a reverb return the tracks send to with
    automation, then a scene played for two seconds and stopped (what the e2e test did before its cleanup)."""
    tracks = []
    for label, device in (("Drums", "Drum Rack"), ("Bass", "Operator"), ("Chords", "Drift")):
        made = lom(live, "call", path="live_set", method="create_midi_track", args=[-1])["result"]["path"]
        lom(live, "set", path=made, property="name", value="{0} {1}".format(PREFIX, label))
        tracks.append("{0} {1}".format(PREFIX, label))
        try:
            live.send_command("add_device", {"track": tracks[-1], "name": device})
        except AbletonError:
            pass
    made = lom(live, "call", path="live_set", method="create_return_track", args=[])["result"]["path"]
    lom(live, "set", path=made, property="name", value="{0} Verb".format(PREFIX))
    letter = chr(ord("A") + len(names(live, "return_tracks")) - 1)
    try:
        live.send_command("add_device", {"track": "return:" + letter, "name": "Reverb"})
    except AbletonError:
        pass
    scenes = []
    for label in ("Verse", "Drop"):
        made = lom(live, "call", path="live_set", method="create_scene", args=[-1])["result"]["path"]
        lom(live, "set", path=made, property="name", value="{0} {1}".format(PREFIX, label))
        scenes.append(names(live, "scenes").index("{0} {1}".format(PREFIX, label)))
    notes = [{"pitch": 48 + 7 * (i % 3), "start": float(i), "duration": 0.5, "velocity": 100} for i in range(8)]
    for track in tracks:
        for slot in scenes:
            live.send_command("create_clip", {"track": track, "slot": slot, "length": 8.0})
            live.send_command("write_notes", {"track": track, "slot": slot, "notes": notes})
        live.send_command("set_mixer", {"track": track, "sends": {letter: -12.0}})
        try:
            live.send_command("write_automation", {"track": track, "slot": scenes[1], "parameter": "send:" + letter,
                                                   "points": [{"time": 0.0, "value": -30.0}, {"time": 4.0, "value": -6.0}]})
        except AbletonError:
            pass
    live.send_command("fire_scene", {"scene": scenes[0]})
    time.sleep(2.0)
    lom(live, "call", path="live_set", method="stop_playing", args=[])
    time.sleep(0.5)


def deletions(live):
    """The cleanup's deletions in its order: tracks (last first), returns, scenes (last first)."""
    out = []
    for collection, method in (("tracks", "delete_track"), ("return_tracks", "delete_return_track"), ("scenes", "delete_scene")):
        items = names(live, collection)
        for index in reversed(range(len(items))):
            if items[index].split("-", 1)[-1].startswith(PREFIX) or items[index].startswith(PREFIX):
                out.append((method, index))
    return out


def run_batch(live, steps):
    commands = [{"type": "lom_call", "params": {"path": "live_set", "method": method, "args": [index]}} for method, index in steps]
    return live.send_command("batch", {"commands": commands, "stop_on_error": False})


def clean(live, shape):
    steps = deletions(live)
    tracks = [step for step in steps if step[0] != "delete_scene"]
    scenes = [step for step in steps if step[0] == "delete_scene"]
    if shape == "all-in-one":
        run_batch(live, steps)
    elif shape == "scenes-batch":
        for method, index in tracks:
            lom(live, "call", path="live_set", method=method, args=[index])
        run_batch(live, scenes)
    elif shape == "tracks-batch":
        run_batch(live, tracks)
        for method, index in scenes:
            lom(live, "call", path="live_set", method=method, args=[index])
    else:
        for method, index in steps:
            lom(live, "call", path="live_set", method=method, args=[index])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--go", action="store_true", help="really run (it may crash Live)")
    parser.add_argument("--shape", choices=("all-in-one", "scenes-batch", "tracks-batch", "separate"), default="all-in-one")
    parser.add_argument("--rounds", type=int, default=1)
    args = parser.parse_args(argv)
    live = AbletonConnection()
    status = live.send_command("get_status")
    song = status.get("set") or {}
    if not song.get("path") or not song.get("saved"):
        print("Refusing: the open set is not saved ({0}). Save it (or open a new empty saved set) first.".format(song.get("path") or "untitled"))
        return 2
    if not args.go:
        print("Dry run: would build [repro] objects in {0} and delete them as {1}, {2} round(s). Add --go.".format(song["path"], args.shape, args.rounds))
        return 0
    for round_number in range(1, args.rounds + 1):
        build(live)
        print("round {0}: built; deleting as {1}".format(round_number, args.shape), flush=True)
        clean(live, args.shape)
        print("round {0}: Live survived".format(round_number), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
