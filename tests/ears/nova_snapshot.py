"""A fake Live Set snapshot modelled on the real NOVA set (docs/listening-loop-plan.md section 5), for the planner and
the take-ingestion tests. Not a test module: helpers only.

The real set: one track per stem and variation (kick, perc, pad, bassA, bassB, arpA, arpB, leadA, leadB), Session
scenes per tempo band (NEON-MID is scene 0, NEON-LOW scene 1, NEON-HIGH scene 2), clips for kick and perc in all three
scenes and for every other stem in the MID scene only, and two returns (A-Reverb, B-Delay).
"""
import copy

SCENES = ("NEON-MID", "NEON-LOW", "NEON-HIGH")
MAINFRAME_SCENES = ("MF-MID", "MF-LOW")
TRACKS = ("kick", "perc", "pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB")
RETURNS = ("A-Reverb", "B-Delay")
PER_BAND = ("kick", "perc")          # the only stems that have a clip in every scene


def clip(slot, scene, name="clip", notes=None, loop_start=0.0, length=32.0):
    entry = {"slot": slot, "scene": scene, "name": name, "is_midi": True, "length": length, "looping": True,
             "loop_start": loop_start, "loop_end": loop_start + length, "start_marker": loop_start,
             "end_marker": loop_start + length, "warping": None, "muted": False}
    if notes is not None:
        entry["notes"] = notes
    return entry


def track_entry(index, name, clips, mute=False, sends=None, devices=None, kind="midi"):
    return {"index": index, "name": name, "kind": kind, "mute": mute, "solo": False, "arm": False,
            "mixer": {"volume_db": 0.0, "pan": 0.0, "sends": dict(sends) if sends is not None else {"A": None, "B": None}},
            "devices": list(devices or []), "clips": list(clips)}


def return_entries(returns):
    return [{"index": index, "letter": name[0], "name": name, "kind": "return", "mute": False, "solo": False,
             "mixer": {"volume_db": 0.0, "pan": 0.0, "sends": {}}, "devices": [], "clips": []}
            for index, name in enumerate(returns)]


def nova_snapshot(without=(), muted=(), sends=None, slots=None, devices=None, notes=None, returns=RETURNS,
                  duplicate=(), scenes=SCENES, tempo=140.0, prefix=""):
    """The fake snapshot.

    without    track names (without the prefix) left out of the set
    muted      track names whose mute is on
    sends      {track name: {"A": dB or None, "B": ...}} send levels (the default is both returns at minimum)
    slots      {track name: [slot, ...]} where a track has clips (default: kick and perc 0, 1 and 2; the rest 0)
    devices    {track name: [device dict, ...]}
    notes      {track name: [note dict, ...]} notes of the track's clips (every clip of the track gets them)
    duplicate  track names that appear twice (a name clash)
    prefix     "mf_" for MAINFRAME's tracks (pass scenes=MAINFRAME_SCENES too)
    """
    slots = slots or {}
    sends = sends or {}
    devices = devices or {}
    notes = notes or {}
    tracks = []
    for name in TRACKS:
        if name in without:
            continue
        default = [0, 1, 2][:len(scenes)] if name in PER_BAND else [0]
        wanted = slots.get(name, default)
        clips = [clip(slot, scenes[slot], name=name, notes=notes.get(name)) for slot in wanted]
        entry = track_entry(len(tracks), prefix + name, clips, mute=name in muted, sends=sends.get(name), devices=devices.get(name))
        tracks.append(entry)
        if name in duplicate:
            twin = copy.deepcopy(entry)
            twin["index"] = len(tracks)
            tracks.append(twin)
    return {
        "song": {"tempo": tempo, "time_signature": "4/4", "set_name": "NOVA", "set_path": None, "live_version": "12.4.6"},
        "scenes": [{"index": index, "name": name} for index, name in enumerate(scenes)],
        "tracks": tracks,
        "returns": return_entries(returns),
        "master": {"mixer": {"volume_db": 0.0, "pan": 0.0}, "devices": []},
    }


def clip_layout_data():
    """A spec where the variations share one track and are told apart by clip names A and B (PRD 7.1)."""
    return {
        "name": "clipset", "key": "A minor",
        "progressions": {"A": ["Am", "Dm"], "B": ["Am", "F"]},
        "stems": {"kick": {"bars": 2, "pitched": False}, "bass": {"bars": 4, "variations": ["A", "B"]}},
        "tiers": {"T1": ["bass"], "T2": ["kick"]},
        "sets": {"demo": {
            "tempos": [110, 135], "variations": {"A": "A", "B": "B"}, "default_scene": "S-LOW",
            "bands": [{"name": "LOW", "tempos": [100, 120], "scene": "S-LOW"}, {"name": "HIGH", "tempos": [130, 140], "scene": "S-HIGH"}],
        }},
        "targets": {"tail_ms": 50},
    }


def clip_layout_snapshot():
    """Track "bass" holds clip A in the LOW and HIGH scenes and clip B in an extra scene; "kick" has one clip per band scene."""
    scenes = ("S-LOW", "S-HIGH", "S-ALT")
    bass = [clip(0, "S-LOW", name="A"), clip(1, "S-HIGH", name="A"), clip(2, "S-ALT", name="B")]
    return {
        "song": {"tempo": 120.0},
        "scenes": [{"index": index, "name": name} for index, name in enumerate(scenes)],
        "tracks": [track_entry(0, "kick", [clip(0, "S-LOW", name="kick"), clip(1, "S-HIGH", name="kick")]),
                   track_entry(1, "bass", bass)],
        "returns": return_entries(("A-Reverb",)),
    }
