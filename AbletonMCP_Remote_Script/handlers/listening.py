"""Listening loop: snapshot and restore of clips, notes, mixer and device parameters.

Owned by the listening loop's agent R (docs/listening-loop-plan.md section 4). The snapshot is the plan's shared
format (section 5): a take stores it as snapshot.json, the notes ear reads it, and a restore writes it back
(docs/listening-loop-prd.md section 9, "Snapshot and restore").

listening_snapshot(tracks=None, scenes=None, notes=True, parameters=False, arrangement=False), read-only, returns

    {song: {tempo, time_signature, set_name, set_path, live_version, root_note, scale_name},
     scenes: [{index, name}],
     tracks: [{index, name, kind, mute, solo, arm, mixer, devices, clips, arrangement_clips?}],
     returns: [{... as tracks, plus letter}],
     master: {mixer, devices} or null}

    tracks   None reads every regular track, every return and the master; a list reads just those refs (names,
             indices, "return:A", "master"). scenes limits the Session slots read; `scenes` lists the ones read.
    mixer    {volume_db, pan, sends: {letter: dB}}. dB is null for -inf, pan is -1..1. Inactive sends
             (return-to-return sends Live has not enabled) are left out, as in get_mixer.
    devices  Flat and depth first, through rack chains (drum pad chains included) and rack return chains:
             {path, name, class_name, type, active, parameters?: [{index, name, value, min, max, quantized, display}]}.
             path is the index path of refs.device_path ("1/0/1"); a rack's return chain N is the segment "return:N".
    clips    Session clips: {slot, scene, name, is_midi, length, looping, loop_start, loop_end, start_marker,
             end_marker, warping (audio only, else null), muted, notes?: [{id, pitch, start, duration, velocity,
             mute, probability, velocity_deviation, release_velocity}]}. Notes come from get_notes_extended over every
             pitch and a window far wider than any clip, so notes outside the loop or before beat 0 are included.
             arrangement=True adds arrangement_clips: the same fields plus index, start and end (song beats)
             instead of slot and scene.
    Times are beats (seconds for unwarped audio clips, as Live reports them). Values are not rounded, except dB
    (4 decimals) and pan (6), so a restore writes back exactly what was read.

listening_restore(snapshot, notes=True, parameters=True, mixer=True, dry_run=False) writes a snapshot back in one
undo step. It plans (and validates) every write before making any; dry_run=True returns the plan alone.

    tracks      regular tracks by exact name, returns by name without their letter, the master as itself.
    notes       clips match by their scene's name when exactly one scene has it (so inserted or reordered scenes do
                not matter), else by slot, and the clip name must agree; arrangement clips match by start and
                name. Notes pair by id, then by pitch and start: unpaired notes are removed or added, paired ones
                that differ are modified in place, so unchanged notes keep their ids and per-note expression.
    parameters  devices match by path, name and class_name, each chain aligned so that devices whose neighbours
                were added, removed or moved still match. Parameters match by index; one whose name differs, or
                that is disabled (macro-mapped), automated or out of range now, is skipped.
    mixer       volume_db, pan and sends; a send letter is followed through the snapshot's return names.
    Not undone: added and removed devices (listed), clip loops, markers and mute (reported as skipped), plug-in
    state that is not a parameter. A snapshot holding only some tracks restores only those.
    Returns {dry_run, tracks, clips, notes, parameters, mixer} counts of what changed (or would), plus skipped,
    added_devices, removed_devices, moved_devices and changes (each at most LIST_LIMIT long, with a *_total count
    when longer).

Cost on Live's main thread (Live 12.4.6, the 28-track NOVA set: 220 devices, 12,130 parameters, 1,463 notes):
a snapshot takes about 20 ms, 55 ms with parameters; restoring 1,421 changed parameters and 192 notes of three
tracks took 7 ms to plan and 81 ms to apply. A whole-set restore therefore fits one call. The JSON itself costs
more than Live: a full snapshot with parameters is about 1.6 MB.

Live behaviour relied on (docs/spikes.md): MidiNoteSpecification takes keyword arguments; apply_note_modifications
accepts only the MidiNoteVector Live returned (get_notes_by_id) and applies chained moves (60->67->74) at once;
a note added at an existing pitch and start replaces it; volume and send display_value floors at -70 at the
minimum, where Live shows -inf; send state 1 marks an inactive return-to-return send; return track names carry
their letter ("A-Reverb"). Parameter writes reach the undo history only when Live syncs them, after the command's
undo step has closed, so a restore calls Song.sync_parameter_changes before returning (one undo step, not two).
"""
import math
import traceback

from .. import refs, values
from ..core import command
from ..errors import CommandError

DB_FLOOR = -70.0         # volume and send display_value at the minimum, which Live shows as -inf
DB_MAX = {"volume_db": 6.0, "send": 0.0}
DB_TOLERANCE = 0.002     # dB below which a mixer level counts as unchanged (snapshots round dB to 4 decimals)
PAN_TOLERANCE = 1e-5
TIME_TOLERANCE = 1e-6    # beats: note times and arrangement clip starts
NOTE_TOLERANCE = 1e-6    # note velocity, probability, velocity deviation and release velocity
VALUE_TOLERANCE = 1e-7   # device parameters, relative to the parameter's range (values are stored exactly)
NOTE_FROM_TIME = -1e7    # get_notes_extended window covering every note of a clip, whatever its markers
NOTE_TIME_SPAN = 2e7
LIST_LIMIT = 50          # entries kept in each list of a restore result
NAMES_LIMIT = 12         # parameter or mixer names listed per change
REGION_FIELDS = ("looping", "loop_start", "loop_end", "start_marker", "end_marker", "muted")


# ---------------------------------------------------------------------------
# Small helpers (pure, unit-tested offline)
# ---------------------------------------------------------------------------


def num(value):
    """A number for JSON: integral values as ints, -0.0 as 0, non-finite as None, everything else unrounded."""
    value = float(value)
    if value.is_integer():
        return int(value)
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def flag(value, name):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise CommandError("invalid_argument", "{0} must be true or false, got {1!r}".format(name, value))


def as_list(value):
    return list(value) if isinstance(value, (list, tuple)) else [value]


def is_finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and not math.isnan(value) and not math.isinf(value)


def finite(value, what):
    """A finite float from a snapshot value, or invalid_argument naming where it came from (what: text or a callable)."""
    if not is_finite(value):
        raise CommandError("invalid_argument", "{0} must be a finite number, got {1!r}".format(what() if callable(what) else what, value))
    return float(value)


def letter_index(letter):
    """Send index of a return letter ('A' -> 0), or None."""
    text = str(letter).strip().upper()
    if len(text) == 1 and "A" <= text <= "Z":
        return ord(text) - ord("A")
    return None


def container_of(path):
    """('1/0', '1') for device path '1/0/1': the chain container and the device's index in it ('' = the track)."""
    container, _, leaf = str(path).rpartition("/")
    return container, leaf


def _leaf_order(leaf):
    try:
        return int(leaf)
    except ValueError:
        return 1 << 30


def align(first, second):
    """Index pairs of a longest common subsequence of two key lists (leftmost on ties).

    Aligning the (name, class_name) sequence of a chain pairs every device that survived an insertion,
    deletion or move of its neighbours, and pairs position for position when nothing moved.
    """
    rows, cols = len(first), len(second)
    table = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(cols - 1, -1, -1):
            if first[i] == second[j]:
                table[i][j] = table[i + 1][j + 1] + 1
            else:
                table[i][j] = max(table[i + 1][j], table[i][j + 1])
    pairs, i, j = [], 0, 0
    while i < rows and j < cols:
        if first[i] == second[j]:
            pairs.append((i, j))
            i += 1
            j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def _groups(entries):
    """{container path: [entry positions ordered by device index]} for a flat device list."""
    groups = {}
    for position, entry in enumerate(entries):
        container, leaf = container_of(entry["path"])
        groups.setdefault(container, []).append((_leaf_order(leaf), position))
    return dict((key, [position for _, position in sorted(items)]) for key, items in groups.items())


def match_devices(wanted, current):
    """Pair snapshot devices with the track's current ones.

    Both are flat depth-first lists of {path, name, class_name}. The top-level chain, and then every rack chain
    of a paired rack (same chain index), is aligned by (name, class_name): a device whose path, name and class
    are unchanged pairs with itself; a device whose neighbours were added, removed or moved still pairs, at its
    new path. Returns (pairs [(wanted_i, current_j)], removed [wanted_i], added [current_j]).
    """
    wanted_groups, current_groups = _groups(wanted), _groups(current)
    chains = {}
    for key in wanted_groups:
        if key:
            rack, _, segment = key.rpartition("/")
            chains.setdefault(rack, []).append(segment)
    pairs = []

    def key(entry):
        return (entry.get("name"), entry.get("class_name"))

    def visit(wanted_key, current_key):
        wanted_items, current_items = wanted_groups.get(wanted_key, []), current_groups.get(current_key, [])
        aligned = align([key(wanted[i]) for i in wanted_items], [key(current[j]) for j in current_items])
        for i, j in aligned:
            wanted_index, current_index = wanted_items[i], current_items[j]
            pairs.append((wanted_index, current_index))
            wanted_path, current_path = wanted[wanted_index]["path"], current[current_index]["path"]
            for segment in chains.get(wanted_path, []):
                visit(wanted_path + "/" + segment, current_path + "/" + segment)

    visit("", "")
    paired_wanted = set(i for i, _ in pairs)
    paired_current = set(j for _, j in pairs)
    removed = [i for i in range(len(wanted)) if i not in paired_wanted]
    added = [j for j in range(len(current)) if j not in paired_current]
    return pairs, removed, added


def note_key(note):
    return (int(note["pitch"]), round(float(note["start"]), 6))


def same_note(first, second):
    if int(first["pitch"]) != int(second["pitch"]) or bool(first["mute"]) != bool(second["mute"]):
        return False
    for field in ("start", "duration"):
        if abs(float(first[field]) - float(second[field])) > TIME_TOLERANCE:
            return False
    for field in ("velocity", "probability", "velocity_deviation", "release_velocity"):
        if abs(float(first[field]) - float(second[field])) > NOTE_TOLERANCE:
            return False
    return True


def diff_notes(current, wanted):
    """What turns a clip's current notes into the snapshot's.

    Notes pair by id first, then by pitch and start (Live keeps one note per pitch and start, so ids that changed
    through a delete-and-rewrite still pair). Returns (remove_ids, modify {current id: wanted note}, add [notes]):
    unpaired current notes go, paired notes that differ are modified in place (keeping their id and per-note
    expression), and unpaired snapshot notes are added.
    """
    current_by_id = dict((int(note["id"]), note) for note in current)
    pairs, wanted_left, by_id = [], [], set()
    for note in wanted:
        note_id = note.get("id")
        if note_id is not None and int(note_id) in current_by_id and int(note_id) not in by_id:
            by_id.add(int(note_id))
            pairs.append((int(note_id), note))
        else:
            wanted_left.append(note)
    current_left = dict((note_key(note), note) for note in current if int(note["id"]) not in by_id)
    add = []
    for note in wanted_left:
        partner = current_left.pop(note_key(note), None)
        if partner is None:
            add.append(note)
        else:
            pairs.append((int(partner["id"]), note))
    paired = set(note_id for note_id, _ in pairs)
    remove_ids = sorted(note_id for note_id in current_by_id if note_id not in paired)
    modify = dict((note_id, note) for note_id, note in pairs if not same_note(current_by_id[note_id], note))
    return remove_ids, modify, add


_NOTE_RANGES = (("velocity", 100.0, 1e-9, 127.0), ("probability", 1.0, 0.0, 1.0),
                ("velocity_deviation", 0.0, -127.0, 127.0), ("release_velocity", 64.0, 0.0, 127.0))


def check_note(raw, where):
    """A snapshot note validated into the fields Live needs, id kept when it is an int.

    where() names the note in the error; it is only called when the note is invalid.
    """
    def fail(problem):
        raise CommandError("invalid_argument", "{0}: {1}".format(where(), problem))

    if not isinstance(raw, dict):
        fail("a note must be an object, got {0!r}".format(raw))
    pitch, start, duration = raw.get("pitch"), raw.get("start"), raw.get("duration")
    if not is_finite(pitch) or float(pitch) != int(pitch) or not 0 <= pitch <= 127:
        fail("pitch must be a MIDI number 0..127, got {0!r}".format(pitch))
    if not is_finite(start):
        fail("start must be a number of beats, got {0!r}".format(start))
    if not is_finite(duration) or duration <= 0:
        fail("duration must be a positive number of beats, got {0!r}".format(duration))
    note_id = raw.get("id")
    note = {"id": note_id if isinstance(note_id, int) and not isinstance(note_id, bool) else None, "pitch": int(pitch),
            "start": float(start), "duration": float(duration), "mute": bool(raw.get("mute", False))}
    for field, default, low, high in _NOTE_RANGES:
        value = raw.get(field)
        if value is None:
            value = default
        elif not is_finite(value) or not low <= value <= high:
            fail("{0} {1!r} is outside Live's range {2:g}..{3:g}".format(field, value, max(low, 0.0), high))
        note[field] = float(value)
    return note


def check_db(value, what, maximum):
    """A snapshot dB value: None (-inf) or a number up to maximum."""
    if value is None:
        return None
    number = finite(value, what)
    if number > maximum + 1e-6:
        raise CommandError("invalid_argument", "{0} {1:g} dB is above the maximum of {2:+g} dB".format(what, number, maximum))
    return None if number <= DB_FLOOR else number


def same_db(first, second):
    if first is None or second is None:
        return first is None and second is None
    return abs(first - second) <= DB_TOLERANCE


def region_changes(now, then):
    """Fields of REGION_FIELDS that differ between a clip's current state and its snapshot entry ([] when the
    snapshot lacks them): a restore writes notes only, so these are reported, not reverted."""
    changed = []
    for field in REGION_FIELDS:
        if field not in then:
            return []
        if field in ("looping", "muted"):
            if bool(now[field]) != bool(then[field]):
                changed.append(field)
        elif not is_finite(then[field]) or abs(float(now[field]) - float(then[field])) > TIME_TOLERANCE:
            changed.append(field)
    return changed


def region_text(entry):
    """'loop 0..16, markers 0..16' (plus 'loop off', 'muted') for skip reasons."""
    def text(value):
        return "{0:g}".format(float(value)) if is_finite(value) else "?"

    return "loop {0}{1}..{2}, markers {3}..{4}{5}".format(
        "" if entry["looping"] else "off ", text(entry["loop_start"]), text(entry["loop_end"]),
        text(entry["start_marker"]), text(entry["end_marker"]), ", muted" if entry["muted"] else "")


# ---------------------------------------------------------------------------
# Reading Live objects
# ---------------------------------------------------------------------------


def db_out(param):
    """dB of a volume or send parameter, None for -inf (its minimum, where display_value floors at -70)."""
    if float(param.value) <= float(param.min) + 1e-9:
        return None
    shown = values.display_number(param)
    if shown is None or math.isnan(shown) or math.isinf(shown) or shown <= DB_FLOOR:
        return None
    return num(round(shown, 4))


def send_active(send):
    """False for sends Live marks inactive (state 1: a return-to-return send that is not enabled)."""
    try:
        return int(send.state) == 0
    except Exception:
        return True


def mixer_out(track, master=False):
    mixer = track.mixer_device
    sends = {}
    if not master:
        for position, send in enumerate(mixer.sends):
            if send_active(send):
                sends[refs.return_letter(position)] = db_out(send)
    return {"volume_db": db_out(mixer.volume), "pan": num(round(float(mixer.panning.value), 6)), "sends": sends}


def device_type(device):
    try:
        return values.DEVICE_TYPE.name(device.type)
    except Exception:
        return "undefined"


def parameters_out(device):
    out = []
    for position, param in enumerate(device.parameters):
        value = param.value
        try:
            display = param.str_for_value(value)
        except Exception:
            display = None
        out.append({"index": position, "name": param.name, "value": num(value), "min": num(param.min), "max": num(param.max),
                    "quantized": bool(param.is_quantized), "display": display})
    return out


def walk_devices(devices, visit, prefix=""):
    """Call visit(path, device) for every device, depth first through rack chains and return chains."""
    for position, device in enumerate(devices):
        path = prefix + str(position)
        visit(path, device)
        if device.can_have_chains:
            for index, chain in enumerate(device.chains):
                walk_devices(chain.devices, visit, "{0}/{1}/".format(path, index))
            for index, chain in enumerate(device.return_chains):
                walk_devices(chain.devices, visit, "{0}/return:{1}/".format(path, index))


def devices_out(track, parameters):
    out = []

    def visit(path, device):
        entry = {"path": path, "name": device.name, "class_name": device.class_name, "type": device_type(device),
                 "active": bool(device.is_active)}
        if parameters:
            entry["parameters"] = parameters_out(device)
        out.append(entry)

    walk_devices(track.devices, visit)
    return out


def read_notes(clip):
    """Every note of a MIDI clip: get_notes_extended over all pitches and a window wider than any clip."""
    return clip.get_notes_extended(0, 128, NOTE_FROM_TIME, NOTE_TIME_SPAN)


def note_out(note):
    return {"id": int(note.note_id), "pitch": int(note.pitch), "start": num(note.start_time), "duration": num(note.duration),
            "velocity": num(note.velocity), "mute": bool(note.mute), "probability": num(note.probability),
            "velocity_deviation": num(note.velocity_deviation), "release_velocity": num(note.release_velocity)}


def notes_out(clip):
    notes = [note_out(note) for note in read_notes(clip)]
    notes.sort(key=lambda note: (note["start"], note["pitch"]))
    return notes


def clip_out(clip, notes):
    midi = bool(clip.is_midi_clip)
    entry = {"name": clip.name, "is_midi": midi, "length": num(clip.length), "looping": bool(clip.looping),
             "loop_start": num(clip.loop_start), "loop_end": num(clip.loop_end), "start_marker": num(clip.start_marker),
             "end_marker": num(clip.end_marker), "warping": None if midi else bool(clip.warping), "muted": bool(clip.muted)}
    if notes and midi:
        entry["notes"] = notes_out(clip)
    return entry


def session_clips_out(track, slots, scene_names, notes):
    out = []
    clip_slots = list(track.clip_slots)
    for slot in slots:
        if slot >= len(clip_slots):
            continue
        holder = clip_slots[slot]
        if holder.has_clip:
            entry = {"slot": slot, "scene": scene_names[slot]}
            entry.update(clip_out(holder.clip, notes))
            out.append(entry)
    return out


def arrangement_clips_out(track, notes):
    out = []
    for index, clip in enumerate(refs.arrangement_clips(track)):
        entry = {"index": index, "start": num(clip.start_time), "end": num(clip.end_time)}
        entry.update(clip_out(clip, notes))
        out.append(entry)
    return out


def regular_kind(track):
    if getattr(track, "is_foldable", False):
        return "group"
    return "midi" if track.has_midi_input else "audio"


def track_out(track, index, kind, options):
    """Snapshot entry of a regular or return track. options: slots, scene_names, notes, parameters, arrangement."""
    entry = {"index": index, "name": track.name, "kind": kind, "mute": bool(track.mute), "solo": bool(track.solo),
             "arm": bool(track.arm) if track.can_be_armed else None, "mixer": mixer_out(track),
             "devices": devices_out(track, options["parameters"]), "clips": []}
    if kind in ("midi", "audio", "group"):
        entry["clips"] = session_clips_out(track, options["slots"], options["scene_names"], options["notes"])
        if options["arrangement"]:
            entry["arrangement_clips"] = arrangement_clips_out(track, options["notes"]) if kind != "group" else []
    return entry


def song_out(song, app):
    try:
        version = app.get_version_string()
    except Exception:
        version = None
    return {
        "tempo": num(round(float(song.tempo), 6)),
        "time_signature": "{0}/{1}".format(int(song.signature_numerator), int(song.signature_denominator)),
        "set_name": str(song.name or "") or None,
        "set_path": str(song.file_path or "") or None,
        "live_version": version,
        "root_note": int(song.root_note),
        "scale_name": str(song.scale_name),
    }


def _selection(song, tracks):
    """(regular [(index, track)], returns [(index, track)], master?) for a tracks argument (None = everything)."""
    regular, returns = list(song.tracks), list(song.return_tracks)
    if tracks is None:
        return list(enumerate(regular)), list(enumerate(returns)), True
    chosen_regular, chosen_returns, master = {}, {}, False
    for ref in as_list(tracks):
        found = refs.track(song, ref)
        position = refs.index_of(regular, found)
        if position is not None:
            chosen_regular[position] = found
            continue
        position = refs.index_of(returns, found)
        if position is not None:
            chosen_returns[position] = found
        else:
            master = True
    return sorted(chosen_regular.items()), sorted(chosen_returns.items()), master


def _slots(song, scenes, count):
    if scenes is None:
        return list(range(count))
    chosen = set()
    all_scenes = list(song.scenes)
    for ref in as_list(scenes):
        chosen.add(refs.index_of(all_scenes, refs.scene(song, ref)))
    return sorted(chosen)


@command("listening_snapshot", readonly=True, timeout=30.0)
def listening_snapshot(ctx, tracks=None, scenes=None, notes=True, parameters=False, arrangement=False):
    """Notes, clips, mixer and devices (optionally every parameter) of the set, in the listening loop's snapshot format."""
    song = ctx.song
    options = {"notes": flag(notes, "notes"), "parameters": flag(parameters, "parameters"),
               "arrangement": flag(arrangement, "arrangement")}
    scene_names = [scene.name for scene in song.scenes]
    options["slots"] = _slots(song, scenes, len(scene_names))
    options["scene_names"] = scene_names
    regular, returns, master = _selection(song, tracks)
    out = {
        "song": song_out(song, ctx.app),
        "scenes": [{"index": slot, "name": scene_names[slot]} for slot in options["slots"]],
        "tracks": [track_out(track, index, regular_kind(track), options) for index, track in regular],
        "returns": [],
        "master": None,
    }
    for index, track in returns:
        entry = track_out(track, index, "return", options)
        entry["letter"] = refs.return_letter(index)
        out["returns"].append(entry)
    if master:
        track = song.master_track
        out["master"] = {"mixer": mixer_out(track, master=True), "devices": devices_out(track, options["parameters"])}
    return out


# ---------------------------------------------------------------------------
# Restore: plan every write first (validating the snapshot), then apply the plan
# ---------------------------------------------------------------------------


class Plan(object):
    """Every write a restore makes, what it skips, and the device changes it found."""

    def __init__(self):
        self.actions = []   # dicts: track, kind ("notes" | "parameter" | "mixer"), group, label, run, count, detail
        self.skipped = []
        self.added_devices, self.removed_devices, self.moved_devices = [], [], []
        self.recheck = []   # (param, wanted value, tolerance, skip entry): disabled parameters a restored macro may set

    def skip(self, reason, **where):
        entry = dict(where)
        entry["reason"] = reason
        self.skipped.append(entry)
        return entry

    def add(self, track, kind, group, label, run, count=1, detail=None):
        self.actions.append({"track": track, "kind": kind, "group": group, "label": label, "run": run, "count": count,
                             "detail": detail})

    def execute(self, dry_run, log, sync=None):
        """Run the actions (unless dry_run) and return those that took effect. A write Live refuses is skipped
        with its error, so one bad parameter never leaves the rest of a restore undone.

        sync() runs after the writes: Live queues parameter changes and commits them to the document later, after
        the command's undo step has closed, which splits a restore of notes and parameters into two undo steps
        (docs/spikes.md). Song.sync_parameter_changes commits them inside the step.
        """
        done = []
        for action in self.actions:
            if not dry_run:
                try:
                    action["run"]()
                except Exception as error:
                    log("listening_restore: {0}\n{1}".format(error, traceback.format_exc()))
                    where = dict(action["group"][1])
                    if action["kind"] == "parameter":
                        where["parameter"] = action["label"]
                    elif action["kind"] == "mixer":
                        where["mixer"] = action["label"]
                    self.skip("Live refused the change: {0}".format(error), **where)
                    continue
            done.append(action)
        if not dry_run and sync is not None and any(action["kind"] != "notes" for action in done):
            try:
                sync()
            except Exception as error:
                log("listening_restore: sync_parameter_changes failed: {0}".format(error))
        if not dry_run and self.recheck:
            settled = set()
            for param, wanted, tolerance, entry in self.recheck:
                try:
                    if abs(float(param.value) - wanted) <= tolerance:
                        settled.add(id(entry))  # its macro, restored above, brought it back
                except Exception:
                    pass
            self.skipped = [entry for entry in self.skipped if id(entry) not in settled]
        return done


def _report(plan, done, dry_run):
    tracks, totals, changes, grouped = set(), {"clips": 0, "notes": 0, "parameters": 0, "mixer": 0}, [], {}
    for action in done:
        tracks.add(action["track"])
        kind = action["kind"]
        if kind == "notes":
            totals["clips"] += 1
            totals["notes"] += action["count"]
            changes.append(dict(action["group"][1], notes=action["detail"]))
            continue
        field = "parameters" if kind == "parameter" else "mixer"
        totals[field] += 1
        key = action["group"][0]
        if key not in grouped:
            grouped[key] = dict(action["group"][1])
            grouped[key][field] = []
            changes.append(grouped[key])
        if len(grouped[key][field]) < NAMES_LIMIT:
            grouped[key][field].append(action["label"])
    out = {"dry_run": dry_run, "tracks": len(tracks), "clips": totals["clips"], "notes": totals["notes"],
           "parameters": totals["parameters"], "mixer": totals["mixer"]}
    for name, items in (("skipped", plan.skipped), ("added_devices", plan.added_devices),
                        ("removed_devices", plan.removed_devices), ("moved_devices", plan.moved_devices), ("changes", changes)):
        out[name] = items[:LIST_LIMIT]
        if len(items) > LIST_LIMIT:
            out[name + "_total"] = len(items)
    return out


def _check_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise CommandError("invalid_argument", "snapshot must be the object listening_snapshot returned")
    for key in ("tracks", "returns"):
        items = snapshot.get(key)
        if items is not None and (not isinstance(items, list) or not all(isinstance(item, dict) for item in items)):
            raise CommandError("invalid_argument", "snapshot.{0} must be a list of track objects".format(key))
    master = snapshot.get("master")
    if master is not None and not isinstance(master, dict):
        raise CommandError("invalid_argument", "snapshot.master must be an object or null")
    if not (snapshot.get("tracks") or snapshot.get("returns") or master):
        raise CommandError("invalid_argument", "The snapshot holds no tracks, returns or master to restore")


def _index(items, key):
    found = {}
    for item in items:
        found.setdefault(key(item), []).append(item)
    return found


def _send_targets(song, snapshot):
    """{snapshot send letter: (current send index or None, return name)}, through the return names the snapshot lists,
    so a send still reaches its return after returns were deleted or reordered."""
    by_name = _index(list(enumerate(song.return_tracks)), lambda item: refs.return_bare_name(item[1].name))
    targets = {}
    for entry in snapshot.get("returns") or []:
        letter, name = entry.get("letter"), entry.get("name")
        if letter is None or name is None:
            continue
        matches = by_name.get(refs.return_bare_name(name), [])
        targets[str(letter)] = (matches[0][0] if len(matches) == 1 else None, refs.return_bare_name(name))
    return targets


def _unwritable(param):
    """Why a parameter must not be written (disabled, unchangeable or automated), or None."""
    try:
        if not param.is_enabled:
            return "disabled (macro-mapped or controlled by Max)"
        if int(param.state) == 2:
            return "Live does not allow changing it now"
        if int(param.automation_state) != 0:
            return "automated: its value follows the automation"
    except Exception:
        return None
    return None


def _setter(param, value):
    def run():
        param.value = value
    return run


def apply_notes(clip, remove_ids, modify, add):
    """Apply a diff_notes result: remove, then modify in place by id, then add, so no step collides with a note
    that is about to go."""
    if remove_ids:
        clip.remove_notes_by_id(list(remove_ids))
    if modify:
        vector = clip.get_notes_by_id(list(modify))  # apply_note_modifications needs Live's own MidiNoteVector
        for live_note in vector:
            note = modify[int(live_note.note_id)]
            live_note.pitch = int(note["pitch"])
            live_note.start_time = float(note["start"])
            live_note.duration = float(note["duration"])
            live_note.velocity = float(note["velocity"])
            live_note.mute = bool(note["mute"])
            live_note.probability = float(note["probability"])
            live_note.velocity_deviation = float(note["velocity_deviation"])
            live_note.release_velocity = float(note["release_velocity"])
        clip.apply_note_modifications(vector)
    if add:
        import Live
        clip.add_new_notes(tuple(
            Live.Clip.MidiNoteSpecification(
                pitch=int(note["pitch"]), start_time=float(note["start"]), duration=float(note["duration"]),
                velocity=float(note["velocity"]), mute=bool(note["mute"]), probability=float(note["probability"]),
                velocity_deviation=float(note["velocity_deviation"]), release_velocity=float(note["release_velocity"]))
            for note in add))


class Restorer(object):
    """Plans a restore: matches tracks, clips and devices, validates the snapshot, and queues every write that
    differs from the set's current state. Nothing is written until Plan.execute."""

    def __init__(self, song, snapshot, notes, parameters, mixer):
        self.song, self.snapshot = song, snapshot
        self.notes, self.parameters, self.mixer = notes, parameters, mixer
        self.plan = Plan()
        self.send_targets = _send_targets(song, snapshot)
        self.scenes = _index(list(enumerate(song.scenes)), lambda item: item[1].name)

    # -- tracks ---------------------------------------------------------------

    def run(self):
        regular = _index(list(self.song.tracks), lambda track: track.name)
        for entry in self.snapshot.get("tracks") or []:
            name = entry.get("name")
            matches = regular.get(name, [])
            if len(matches) != 1:
                self.plan.skip("track not found" if not matches else "{0} tracks share this name".format(len(matches)), track=name)
                continue
            self.track(matches[0], entry, str(name), regular_kind(matches[0]))
        returns = _index(list(self.song.return_tracks), lambda track: refs.return_bare_name(track.name))
        for entry in self.snapshot.get("returns") or []:
            name = entry.get("name")
            matches = returns.get(refs.return_bare_name(name), []) if name is not None else []
            if len(matches) != 1:
                self.plan.skip("return track not found" if not matches else "{0} return tracks share this name".format(len(matches)),
                               track=name)
                continue
            self.track(matches[0], entry, matches[0].name, "return")
        if self.snapshot.get("master"):
            self.track(self.song.master_track, self.snapshot["master"], "master", "master")
        return self.plan

    def track(self, track, entry, label, kind):
        if self.mixer and isinstance(entry.get("mixer"), dict):
            self.mixer_values(track, entry["mixer"], label, kind)
        if isinstance(entry.get("devices"), list):
            self.devices(track, entry["devices"], label)
        if self.notes and kind in ("midi", "audio", "group"):
            for clip_entry in entry.get("clips") or []:
                if isinstance(clip_entry, dict):
                    self.session_clip(track, clip_entry, label)
            for clip_entry in entry.get("arrangement_clips") or []:
                if isinstance(clip_entry, dict):
                    self.arrangement_clip(track, clip_entry, label)

    # -- mixer ----------------------------------------------------------------

    def mixer_values(self, track, wanted, label, kind):
        mixer = track.mixer_device
        group = (("mixer", label), {"track": label})
        if "volume_db" in wanted:
            db = check_db(wanted["volume_db"], "{0} volume_db".format(label), DB_MAX["volume_db"])
            self.level(mixer.volume, db, label, "volume_db", group)
        if wanted.get("pan") is not None:
            pan = finite(wanted["pan"], "{0} pan".format(label))
            if not -1.0 - 1e-6 <= pan <= 1.0 + 1e-6:
                raise CommandError("invalid_argument", "{0} pan must be within -1..1, got {1!r}".format(label, pan))
            param = mixer.panning
            if abs(float(param.value) - pan) > PAN_TOLERANCE and self.writable(param, label, "pan"):
                self.plan.add(label, "mixer", group, "pan", _setter(param, min(max(pan, -1.0), 1.0)))
        sends = wanted.get("sends")
        if not sends or kind == "master":
            return
        if not isinstance(sends, dict):
            raise CommandError("invalid_argument", "{0} mixer.sends must be an object like {{\"A\": -12}}".format(label))
        current = list(mixer.sends)
        for letter, db in sends.items():
            db = check_db(db, "{0} send {1}".format(label, letter), DB_MAX["send"])
            target, return_name = self.send_targets.get(str(letter), (letter_index(letter), None))
            field = "send {0}".format(letter)
            if target is None or target >= len(current):
                if db is not None:  # a silent send to a return that is gone needs nothing
                    self.plan.skip("return track {0!r} not found".format(return_name or letter), track=label, mixer=field)
                continue
            if target != letter_index(letter):
                field = "send {0} (was {1})".format(refs.return_letter(target), letter)
            if not send_active(current[target]):
                if db is not None:
                    self.plan.skip("the send is inactive (Live keeps return-to-return sends off until enabled)", track=label,
                                   mixer=field)
                continue
            self.level(current[target], db, label, field, group)

    def level(self, param, db, label, field, group):
        if same_db(db_out(param), db) or not self.writable(param, label, field):
            return
        self.plan.add(label, "mixer", group, field, lambda: values.set_volume_db(param, "-inf" if db is None else db))

    def writable(self, param, label, field):
        reason = _unwritable(param)
        if reason:
            self.plan.skip(reason, track=label, mixer=field)
            return False
        return True

    # -- devices --------------------------------------------------------------

    def devices(self, track, wanted, label):
        current, objects = [], []

        def visit(path, device):
            current.append({"path": path, "name": device.name, "class_name": device.class_name})
            objects.append(device)

        walk_devices(track.devices, visit)
        entries = []
        for position, entry in enumerate(wanted):
            if not isinstance(entry, dict) or entry.get("path") is None:
                raise CommandError("invalid_argument", "{0} devices[{1}] must be an object with path, name and class_name".format(
                    label, position))
            entries.append({"path": str(entry["path"]), "name": entry.get("name"), "class_name": entry.get("class_name")})
        pairs, removed, added = match_devices(entries, current)
        for i in removed:
            self.plan.removed_devices.append(dict(entries[i], track=label))
        for j in added:
            self.plan.added_devices.append(dict(current[j], track=label))
        for i, j in pairs:
            if entries[i]["path"] != current[j]["path"]:
                self.plan.moved_devices.append({"track": label, "name": current[j]["name"], "from": entries[i]["path"],
                                                "to": current[j]["path"]})
            if self.parameters and isinstance(wanted[i].get("parameters"), list):
                self.device_parameters(objects[j], wanted[i]["parameters"], label, current[j]["path"])

    def device_parameters(self, device, wanted, label, path):
        params = list(device.parameters)
        count = len(params)
        group = (("device", label, path), {"track": label, "device": path, "name": device.name})
        for position, raw in enumerate(wanted):
            index = raw.get("index") if isinstance(raw, dict) else None
            value = raw.get("value") if isinstance(raw, dict) else None
            if isinstance(index, bool) or not isinstance(index, int) or index < 0 or not is_finite(value):
                raise CommandError("invalid_argument", "{0} device {1} parameters[{2}] needs an index and a finite value, got {3!r}".format(
                    label, path, position, raw))
            name = raw.get("name")
            if index >= count:
                self.plan.skip("the device has no parameter {0} now ({1} parameters)".format(index, count), track=label,
                               device=path, parameter=name)
                continue
            param = params[index]
            low, high = raw.get("min"), raw.get("max")
            tolerance = VALUE_TOLERANCE * max(1.0, abs(high - low)) if is_finite(low) and is_finite(high) else VALUE_TOLERANCE
            if abs(float(param.value) - value) <= tolerance:
                continue
            if param.name != name:
                self.plan.skip("parameter {0} is named {1!r} now".format(index, param.name), track=label, device=path,
                               parameter=name)
                continue
            reason = _unwritable(param)
            if reason:
                entry = self.plan.skip(reason, track=label, device=path, parameter=name)
                self.plan.recheck.append((param, value, tolerance, entry))
                continue
            low, high = float(param.min), float(param.max)
            if not low - tolerance <= value <= high + tolerance:
                self.plan.skip("value {0:g} is outside the parameter's range {1:g}..{2:g} now".format(value, low, high),
                               track=label, device=path, parameter=name)
                continue
            self.plan.add(label, "parameter", group, name, _setter(param, min(max(value, low), high)))

    # -- clips ----------------------------------------------------------------

    def session_clip(self, track, entry, label):
        """Match by the clip's scene name when exactly one scene has it (so clips survive inserted or reordered
        scenes), else by slot; the clip name must agree either way."""
        name, slot, scene = entry.get("name"), entry.get("slot"), entry.get("scene")
        where = {"track": label, "slot": slot, "clip": name}
        matches = self.scenes.get(scene, []) if scene is not None else []
        if len(matches) == 1:
            position = matches[0][0]
        elif isinstance(slot, int) and not isinstance(slot, bool):
            position = slot
        else:
            position = None
        holders = list(track.clip_slots)
        if position is None or not 0 <= position < len(holders):
            self.plan.skip("no such slot", **where)
            return
        where["slot"] = position
        holder = holders[position]
        if not holder.has_clip:
            self.plan.skip("the slot is empty", **where)
            return
        clip = holder.clip
        if clip.name != name:
            self.plan.skip("the clip in this slot is named {0!r}".format(clip.name), **where)
            return
        self.clip(clip, entry, label, where)

    def arrangement_clip(self, track, entry, label):
        name, start = entry.get("name"), entry.get("start")
        where = {"track": label, "arrangement_clip": entry.get("index"), "clip": name}
        found = []
        if is_finite(start):
            found = [(index, clip) for index, clip in enumerate(refs.arrangement_clips(track))
                     if abs(float(clip.start_time) - start) <= TIME_TOLERANCE and clip.name == name]
        if len(found) != 1:
            self.plan.skip("no arrangement clip of this name starts at beat {0}".format(start), **where)
            return
        where["arrangement_clip"] = found[0][0]
        self.clip(found[0][1], entry, label, where)

    def clip(self, clip, entry, label, where):
        wanted = entry.get("notes")
        if wanted is None:
            return
        if not isinstance(wanted, list):
            raise CommandError("invalid_argument", "{0} clip {1!r}: notes must be a list".format(label, entry.get("name")))
        if not clip.is_midi_clip:
            self.plan.skip("the clip is an audio clip now", **where)
            return
        checked = []
        for index, raw in enumerate(wanted):
            checked.append(check_note(raw, lambda: "{0} clip {1!r} notes[{2}]".format(label, entry.get("name"), index)))
        now = {"looping": bool(clip.looping), "loop_start": float(clip.loop_start), "loop_end": float(clip.loop_end),
               "start_marker": float(clip.start_marker), "end_marker": float(clip.end_marker), "muted": bool(clip.muted)}
        changed = region_changes(now, entry)
        if changed:
            self.plan.skip("clip {0} changed since the snapshot (now {1}; snapshot {2}); a restore writes notes only".format(
                ", ".join(changed), region_text(now), region_text(entry)), **where)
        remove_ids, modify, add = diff_notes(notes_out(clip), checked)
        count = len(remove_ids) + len(modify) + len(add)
        if count:
            detail = {"added": len(add), "removed": len(remove_ids), "modified": len(modify)}
            self.plan.add(label, "notes", (None, dict(where)), None, lambda: apply_notes(clip, remove_ids, modify, add), count,
                          detail)


@command("listening_restore", timeout=30.0)
def listening_restore(ctx, snapshot, notes=True, parameters=True, mixer=True, dry_run=False):
    """Write a listening_snapshot back (notes, device parameter values, mixer levels) in one undo step."""
    _check_snapshot(snapshot)
    dry_run = flag(dry_run, "dry_run")
    song = ctx.song
    plan = Restorer(song, snapshot, flag(notes, "notes"), flag(parameters, "parameters"), flag(mixer, "mixer")).run()
    done = plan.execute(dry_run, ctx.log, sync=song.sync_parameter_changes)
    return _report(plan, done, dry_run)
