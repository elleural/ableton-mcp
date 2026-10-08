"""Synthetic listening snapshots for the notes ear: a clean set, and the same set with one planted defect.

`clean_snapshot(spec, "neon")` builds, from the spec alone, a snapshot in the format of
docs/listening-loop-plan.md section 5 that passes every fail- and warn-level check of `ears.notes`:

    kick   2-bar clips, one per tempo band: LOW half-time (beats 1 and 3), MID four-on-the-floor,
           HIGH four-on-the-floor plus a pickup on the last sixteenth
    perc   4-bar clips, one per band
    pad    16 bars, shared by both variations: two notes per bar chosen so that neither is a semitone from a
           chord tone of any progression in that bar (bar 4 of the real progressions leaves only D and B)
    bass   8 bars, the chord root on beats 1 and 3, following the variation's progression
    arp    8 bars, sixteenth-note chord tones
    lead   8 bars, chord tones with about 40% rests
    fill   a one-bar fill in the fill scene, when the spec has one (a track the ear never looks at)

Like the real set, only the drums have a clip in every band's scene; the other stems live in the default
scene (NEON-MID). Every melodic note is a tone of its bar's chord, so the stems cannot clash.

`plant(snapshot, defect)` returns a deep copy with one of the PRD's note defects (the set is the first whose
tracks the snapshot has, so it works for MAINFRAME's snapshot as well):

    bass_semitone   the bass a semitone off for one bar              in_key, chord_tones (and clash: it
                                                                       sits a semitone from the chord)
    d_major         an F# where Dm belongs                           in_key, chord_tones
    clash           two stems a semitone apart for a beat            clash
    kick_late       the MID kick late by a thirty-second note        grid
    lead_no_rests   the lead holds every note until the next         lead_rests
    pad_a_over_e    the shared pad holding A in bar 4, which          shared_stem (and clash with the
                    meets the G# of E in progression B                 variation B stems that play the G#)

The small builders (`note`, `clip`, `track`, `device`, `snapshot`) are public so tests can hand-build other
layouts, such as one track with clips named A and B.
"""
import copy
from collections import OrderedDict
from itertools import count

from .. import theory
from ..spec import load as load_spec

KICK, CLAP, HAT = 36, 39, 42   # drum-rack pitches
PAD_LOW, BASS_LOW, ARP_LOW, LEAD_LOW = 57, 36, 60, 72   # lowest pitch each stem's voicing starts from
LEAD_TEMPLATES = (
    # (start step, length in steps, index into the chord's tones ascending, then up an octave)
    ((0, 3, 2), (4, 2, 1), (8, 4, 0), (13, 1, 1)),   # 10 of 16 steps sound: 6 rests
    ((0, 2, 3), (3, 3, 2), (8, 2, 1), (12, 2, 0)),   # 9 of 16 steps sound: 7 rests
)
ARP_PATTERN = (0, 1, 2, 1)   # root, third, fifth, third, over sixteenth notes


# -- builders -----------------------------------------------------------------------------------------


def note(pitch, start, duration, velocity=100, mute=False, probability=1.0):
    """A note in the snapshot's format (times in beats)."""
    return {"id": 0, "pitch": int(pitch), "start": float(start), "duration": float(duration),
            "velocity": float(velocity), "mute": bool(mute), "probability": float(probability),
            "velocity_deviation": 0.0}


def clip(name, notes, length, slot=0, scene="", is_midi=True, looping=True, warping=False):
    """A clip in the snapshot's format; `notes=None` leaves the notes out (an audio clip)."""
    out = {"slot": slot, "scene": scene, "name": name, "is_midi": is_midi, "length": float(length),
           "looping": looping, "loop_start": 0.0, "loop_end": float(length), "start_marker": 0.0,
           "end_marker": float(length), "warping": warping, "muted": False}
    if notes is not None:
        out["notes"] = list(notes)
    return out


def device(name, kind="instrument", class_name="InstrumentVector", path="0", active=True):
    return {"path": path, "name": name, "class_name": class_name, "type": kind, "active": active}


def track(name, clips, index=0, kind="midi", devices=None):
    return {"index": index, "name": name, "kind": kind, "mute": False, "solo": False, "arm": False,
            "mixer": {"volume_db": -6.0, "pan": 0.0, "sends": {"A": None, "B": None}},
            "devices": list(devices or []), "clips": list(clips)}


def snapshot(tracks, scenes, tempo=140.0, set_name="NOVA"):
    """A snapshot from tracks and scene names (scene i gets index i)."""
    return {
        "song": {"tempo": float(tempo), "time_signature": "4/4", "set_name": set_name, "set_path": "",
                 "live_version": "12.4.6"},
        "scenes": [{"index": index, "name": name} for index, name in enumerate(scenes)],
        "tracks": list(tracks),
        "returns": [],
        "master": {"mixer": {"volume_db": 0.0, "pan": 0.0, "sends": {}}, "devices": []},
    }


def renumber(snap):
    """Give every note a unique id, in track and clip order."""
    ids = count(1)
    for one in snap.get("tracks", []):
        for each in one.get("clips", []):
            for entry in each.get("notes") or []:
                entry["id"] = next(ids)
    return snap


# -- the clean set ---------------------------------------------------------------------------------------


def stack(pitch_classes, low):
    """Ascending MIDI pitches for pitch classes: the first at or above `low`, each next one above the last."""
    pitches, current = [], low - 1
    for pc in pitch_classes:
        pitch = current + 1
        while pitch % 12 != pc:
            pitch += 1
        pitches.append(pitch)
        current = pitch
    return pitches


def _chord_at(progression, bar):
    return progression[bar % len(progression)]


def _kick_notes(expectation, bars, size):
    out = []
    for bar in range(bars):
        beats = (0, 2) if expectation == "half-time" else range(int(size))
        out.extend(note(KICK, bar * size + beat, 0.25, 110) for beat in beats)
    if expectation not in ("half-time", "four-on-the-floor"):   # no pattern named: add a pickup
        out.append(note(KICK, bars * size - 0.25, 0.25, 90))
    return out


def _perc_notes(expectation, bars, size):
    out = []
    for bar in range(bars):
        base = bar * size
        if expectation == "half-time":
            out.append(note(CLAP, base + 2, 0.25, 100))
            out.extend(note(HAT, base + beat + 0.5, 0.25, 70) for beat in (1, 3))
        else:
            out.extend(note(CLAP, base + beat, 0.25, 100) for beat in (1, 3))
            if expectation == "four-on-the-floor":   # off-beat eighths
                positions = [beat + 0.5 for beat in range(int(size))]
            else:                                    # a busy band: every sixteenth
                positions = [step * 0.25 for step in range(int(size * 4))]
            out.extend(note(HAT, base + position, 0.25, 70) for position in positions)
    return out


def _safe_pitch_classes(spec, chords):
    """Up to two pitch classes that are in key and not a semitone from any tone of the chords played together.

    Chosen by how many of the chords they belong to, then root, fifth, third of the first chord.
    """
    tones = set()
    for chord in chords:
        tones |= theory.chord_tones(chord)
    forbidden = theory.semitone_neighbours(tones)
    first = theory.parse_chord(chords[0]).tones
    order = [first[0]] + list(first[2:]) + list(first[1:2])

    def rank(pc):
        belongs = sum(1 for chord in chords if pc in theory.chord_tones(chord))
        return (-belongs, order.index(pc) if pc in order else 99, pc)

    candidates = [pc for pc in range(12) if pc not in forbidden and (pc in spec.scale or pc in tones)]
    return sorted(candidates, key=rank)[:2]


def _pad_notes(spec, part, size):
    out = []
    progressions = [spec.progressions[name] for name in part.progressions]
    for bar in range(int(part.bars)):
        chords = [_chord_at(progression, bar) for progression in progressions]
        out.extend(note(pitch, bar * size, size, 70) for pitch in stack(_safe_pitch_classes(spec, chords), PAD_LOW))
    return out


def _bass_notes(spec, set_name, part, size):
    progression = spec.progression(set_name, part.variation)
    beats = [int(beat) - 1 for beat in spec.tolerance("chord_tone_beats", [1, 3])]
    out = []
    for bar in range(int(part.bars)):
        pitch = stack([theory.chord_root(_chord_at(progression, bar))], BASS_LOW)[0]
        out.extend(note(pitch, bar * size + beat, 1.5, 100) for beat in beats)
    return out


def _arp_notes(spec, set_name, part, size):
    progression = spec.progression(set_name, part.variation)
    steps = int(round(size / (4.0 / spec.grid)))
    out = []
    for bar in range(int(part.bars)):
        pitches = stack(theory.parse_chord(_chord_at(progression, bar)).tones[:3], ARP_LOW)
        for step in range(steps):
            out.append(note(pitches[ARP_PATTERN[step % len(ARP_PATTERN)]], bar * size + step * 0.25, 0.25, 90))
    return out


def _lead_notes(spec, set_name, part, size):
    progression = spec.progression(set_name, part.variation)
    out = []
    for bar in range(int(part.bars)):
        pitches = stack(theory.parse_chord(_chord_at(progression, bar)).tones[:3], LEAD_LOW)
        pitches += [pitch + 12 for pitch in pitches]
        for start, length, index in LEAD_TEMPLATES[bar % len(LEAD_TEMPLATES)]:
            out.append(note(pitches[index], bar * size + start * 0.25, length * 0.25, 95))
    return out


def _part_notes(spec, set_name, part, band, size):
    if part.role == "kick":
        return _kick_notes(band.get("kick") if band else None, int(part.bars), size)
    if part.role == "perc":
        return _perc_notes(band.get("kick") if band else None, int(part.bars), size)
    if part.role == "pad":
        return _pad_notes(spec, part, size)
    if part.role == "bass":
        return _bass_notes(spec, set_name, part, size)
    if part.role == "arp":
        return _arp_notes(spec, set_name, part, size)
    if part.role == "lead":
        return _lead_notes(spec, set_name, part, size)
    raise ValueError("The fixture has no notes for role {0!r} (part {1})".format(part.role, part.id))


def clean_snapshot(spec, set_name="neon"):
    """A snapshot of the set that passes every fail- and warn-level check of the notes ear."""
    spec = load_spec(spec)
    set_name = spec.set_name(set_name)
    if spec.layout(set_name) != "track":
        raise ValueError("clean_snapshot builds the layout with one track per variation; build a one-track layout "
                         "with clips named A and B by hand from track() and clip()")
    size = spec.beats_per_bar
    entry = spec.set_spec(set_name)
    bands = spec.bands(set_name)
    default_scene = entry.get("default_scene") or (bands[0]["scene"] if bands else "")
    scenes = []
    wanted = [band.get("scene") for band in bands] + [default_scene] + [fill.get("scene") for fill in spec.fills(set_name).values()]
    for name in wanted:
        if name and name not in scenes:
            scenes.append(name)
    tracks = []
    for part in spec.parts(set_name):
        clips = []
        if not part.pitched and bands:   # the drums have a clip in every band's scene
            for band in bands:
                clips.append(clip("{0} {1}".format(part.stem, band["name"]), _part_notes(spec, set_name, part, band, size),
                                  part.bars * size, slot=scenes.index(band["scene"]), scene=band["scene"]))
        else:
            clips.append(clip(part.variation or part.stem, _part_notes(spec, set_name, part, None, size),
                              part.bars * size, slot=scenes.index(default_scene) if default_scene else 0, scene=default_scene))
        instrument = device("Drum Rack", class_name="DrumGroupDevice") if not part.pitched else device("Wavetable")
        tracks.append(track(part.track, clips, index=len(tracks), devices=[instrument]))
    for name, fill in spec.fills(set_name).items():   # a fill track the notes ear never reads
        if fill.get("track") and fill.get("scene"):
            length = int(fill.get("bars", 1)) * size
            hits = [note(CLAP, length - 1 + k * 0.25, 0.25, 100) for k in range(4)]
            tracks.append(track(fill["track"], [clip(name, hits, length, slot=scenes.index(fill["scene"]), scene=fill["scene"])],
                                index=len(tracks), devices=[device("Drum Rack", class_name="DrumGroupDevice")]))
    snap = snapshot(tracks, scenes)
    snap["returns"] = [dict(track("A-Reverb", [], index=0, kind="return"), letter="A"),
                       dict(track("B-Delay", [], index=1, kind="return"), letter="B")]
    return renumber(snap)


# -- planted defects -------------------------------------------------------------------------------------


def _find(snap, spec, set_name, part_id, band="MID"):
    """(part, clip) of a part in the clip the given band would play."""
    part = spec.part(set_name, part_id)
    band_dict = spec.band(set_name, name=band) if spec.bands(set_name) else None
    one = next((each for each in snap["tracks"] if each["name"] == part.track), None)
    if one is None:
        raise LookupError("The snapshot has no track {0!r}".format(part.track))
    for scene in spec.scenes_for(set_name, band_dict) or [None]:
        for each in one["clips"]:
            if scene is None or each["scene"] == scene:
                return part, each
    raise LookupError("No clip for {0} in {1}".format(part_id, spec.scenes_for(set_name, band_dict)))


def _in_bar(entries, bar, size):
    return [entry for entry in entries if bar * size - 1e-9 <= entry["start"] < (bar + 1) * size - 1e-9]


def _bass_semitone(snap, spec, set_name):
    """The bass plays a semitone above the chord root for the whole of bar 3 (D# where Dm belongs)."""
    _, target = _find(snap, spec, set_name, "bassA")
    for entry in _in_bar(target["notes"], 2, spec.beats_per_bar):
        entry["pitch"] += 1


def _d_major(snap, spec, set_name):
    """Every F of arp A and lead A over Dm becomes F#: D major where D minor belongs."""
    size = spec.beats_per_bar
    progression = spec.progression(set_name, "A")
    for part_id in ("arpA", "leadA"):
        part, target = _find(snap, spec, set_name, part_id)
        for bar in range(int(part.bars)):
            if _chord_at(progression, bar) != "Dm":
                continue
            for entry in _in_bar(target["notes"], bar, size):
                if entry["pitch"] % 12 == theory.parse_pitch_class("F"):
                    entry["pitch"] += 1


def _clash(snap, spec, set_name):
    """Lead A holds B3 for beat 2 of bar 5 while arp A plays C4 under it: two stems a semitone apart."""
    size = spec.beats_per_bar
    _, target = _find(snap, spec, set_name, "leadA")
    start = 4 * size + 1
    target["notes"] = [entry for entry in target["notes"] if not start - 1e-9 <= entry["start"] < start + 1 - 1e-9]
    target["notes"].append(note(theory.parse_note("B3"), start, 1.0, 95))
    target["notes"].sort(key=lambda entry: (entry["start"], entry["pitch"]))


def _kick_late(snap, spec, set_name):
    """Every MID kick hit lands a thirty-second note (an eighth of a beat) late: 54 ms at 140 BPM."""
    _, target = _find(snap, spec, set_name, "kick", band="MID")
    for entry in target["notes"]:
        entry["start"] += 0.125


def _lead_no_rests(snap, spec, set_name):
    """Lead A holds each note until the next one starts (or the bar ends): no rests."""
    size = spec.beats_per_bar
    part, target = _find(snap, spec, set_name, "leadA")
    for bar in range(int(part.bars)):
        entries = sorted(_in_bar(target["notes"], bar, size), key=lambda entry: entry["start"])
        for index, entry in enumerate(entries):
            end = entries[index + 1]["start"] if index + 1 < len(entries) else (bar + 1) * size
            entry["duration"] = end - entry["start"]


def _pad_a_over_e(snap, spec, set_name):
    """The pad holds A instead of B in bar 4: right for Dm in progression A, a semitone from the G# of E in B."""
    size = spec.beats_per_bar
    _, target = _find(snap, spec, set_name, "pad")
    for entry in _in_bar(target["notes"], 3, size):
        if entry["pitch"] % 12 == theory.parse_pitch_class("B"):
            entry["pitch"] -= 2


DEFECTS = OrderedDict([
    ("bass_semitone", _bass_semitone),
    ("d_major", _d_major),
    ("clash", _clash),
    ("kick_late", _kick_late),
    ("lead_no_rests", _lead_no_rests),
    ("pad_a_over_e", _pad_a_over_e),
])


def _set_of(snap, spec):
    """The first set of the spec whose stem tracks are all in the snapshot (else the spec's first set)."""
    names = set(each.get("name") for each in snap.get("tracks", []))
    for candidate in spec.set_names():
        if all(part.track in names for part in spec.parts(candidate)):
            return candidate
    return spec.default_set()


def plant(snapshot, defect, spec=None, set_name=None):
    """A deep copy of the snapshot with one defect from `DEFECTS` planted.

    The spec defaults to the bundled nova spec and the set to the first one whose tracks the snapshot has
    (neon for `clean_snapshot(spec)`, mainframe for `clean_snapshot(spec, "mainframe")`).
    """
    if defect not in DEFECTS:
        raise ValueError("Unknown defect {0!r}; defects: {1}".format(defect, ", ".join(DEFECTS)))
    spec = load_spec(spec or "nova")
    set_name = spec.set_name(set_name) if set_name else _set_of(snapshot, spec)
    out = copy.deepcopy(snapshot)
    DEFECTS[defect](out, spec, set_name)
    return renumber(out)
