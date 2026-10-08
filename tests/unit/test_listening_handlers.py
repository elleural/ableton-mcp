"""Unit tests for the listening loop's snapshot and restore commands (handlers/listening.py) against small fakes of
Live's song, tracks, mixer, devices, clips and notes."""
import copy
import json
import sys

import pytest

from AbletonMCP_Remote_Script import core
from AbletonMCP_Remote_Script.errors import CommandError

core.load_handlers()
from AbletonMCP_Remote_Script.handlers import listening  # noqa: E402

ZERO_DB = 70 / 76.0  # fake dB parameters use the meter scale: dB = 76 * raw - 70


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class Param(object):
    """DeviceParameter fake. kind 'db' maps raw 0..1 to dB as 76 * raw - 70, kind 'pan' shows -50..50."""

    def __init__(self, name, value=0.0, minimum=0.0, maximum=1.0, quantized=False, kind=None, state=0, enabled=True,
                 automation=0):
        self.name = self.original_name = name
        self._value = float(value)
        self.min, self.max = minimum, maximum
        self.is_quantized, self.kind = quantized, kind
        self.state, self.is_enabled, self.automation_state = state, enabled, automation
        self.writes, self.fail, self.followers = 0, False, []

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, number):
        if self.fail:
            raise RuntimeError("Parameter refused the value")
        if not self.min <= number <= self.max:
            raise ValueError("Invalid value")
        self._value = float(number)
        self.writes += 1
        for follower, mapping in self.followers:  # a rack macro mapped to another parameter
            follower._value = mapping(number)

    @property
    def display_value(self):
        if self.kind == "db":
            return 76.0 * self._value - 70.0
        if self.kind == "pan":
            return self._value * 50.0
        return self._value

    @display_value.setter
    def display_value(self, number):
        raw = (number + 70.0) / 76.0 if self.kind == "db" else number / 50.0 if self.kind == "pan" else number
        self.value = min(max(raw, self.min), self.max)

    def str_for_value(self, value):
        if self.kind == "db":
            return "-inf dB" if value <= self.min else "{0:.1f} dB".format(76.0 * value - 70.0)
        if self.is_quantized:
            return ["Off", "On"][int(value)]
        return "{0:.2f}".format(value)


def device_on(value=1.0):
    return Param("Device On", value, 0.0, 1.0, quantized=True)


class Device(object):
    def __init__(self, name, class_name=None, kind=2, parameters=None, chains=None, return_chains=None, active=True):
        self.name = name
        self.class_name = class_name or name.replace(" ", "")
        self.type = kind
        self.is_active = active
        self.parameters = parameters if parameters is not None else [device_on(), Param("Amount", 0.5)]
        self.can_have_chains = chains is not None
        self.chains = chains or []
        self.return_chains = return_chains or []


class Chain(object):
    def __init__(self, *devices):
        self.devices = list(devices)


class Note(object):
    def __init__(self, note_id, pitch, start, duration=1.0, velocity=100.0, mute=False, probability=1.0,
                 velocity_deviation=0.0, release_velocity=64.0):
        self.note_id, self.pitch, self.start_time, self.duration = note_id, pitch, start, duration
        self.velocity, self.mute, self.probability = velocity, mute, probability
        self.velocity_deviation, self.release_velocity = velocity_deviation, release_velocity


class Spec(object):
    """Stand-in for Live.Clip.MidiNoteSpecification (keyword arguments)."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


class Clip(object):
    def __init__(self, name, notes=(), midi=True, length=4.0, start_time=0.0):
        self.name = name
        self.is_midi_clip, self.is_audio_clip = midi, not midi
        self.length, self.looping, self.loop_start, self.loop_end = length, True, 0.0, length
        self.start_marker, self.end_marker, self.warping, self.muted = 0.0, length, True, False
        self.start_time, self.end_time = start_time, start_time + length
        self.notes = list(notes)
        self.next_id = max([note.note_id for note in self.notes] + [0]) + 1
        self.windows = []

    def get_notes_extended(self, from_pitch, pitch_span, from_time, time_span):
        self.windows.append((from_pitch, pitch_span, from_time, time_span))
        return [copy.copy(note) for note in self.notes
                if from_pitch <= note.pitch < from_pitch + pitch_span and from_time <= note.start_time < from_time + time_span]

    def remove_notes_by_id(self, ids):
        ids = set(ids)
        self.notes = [note for note in self.notes if note.note_id not in ids]

    def get_notes_by_id(self, ids):
        ids = set(ids)
        return [copy.copy(note) for note in self.notes if note.note_id in ids]

    def apply_note_modifications(self, vector):
        by_id = dict((note.note_id, note) for note in vector)
        if not set(by_id) <= set(note.note_id for note in self.notes):
            raise RuntimeError("All given IDs must be present in clip")
        self.notes = [copy.copy(by_id[note.note_id]) if note.note_id in by_id else note for note in self.notes]

    def add_new_notes(self, specs):
        ids = []
        for spec in specs:
            # Live keeps one note per pitch and start: an added note replaces the one there.
            self.notes = [note for note in self.notes if not (note.pitch == spec.pitch and note.start_time == spec.start_time)]
            self.notes.append(Note(self.next_id, spec.pitch, spec.start_time, spec.duration, spec.velocity, spec.mute,
                                   spec.probability, spec.velocity_deviation, spec.release_velocity))
            ids.append(self.next_id)
            self.next_id += 1
        return ids


class Slot(object):
    def __init__(self, clip=None):
        self.clip = clip

    @property
    def has_clip(self):
        return self.clip is not None


class Mixer(object):
    def __init__(self, sends=2, send_states=None):
        states = send_states or [0] * sends
        self.volume = Param("Track Volume", ZERO_DB, kind="db")
        self.panning = Param("Track Panning", 0.0, -1.0, 1.0, kind="pan")
        self.sends = [Param("Send", 0.0, kind="db", state=states[position]) for position in range(sends)]


class Track(object):
    def __init__(self, name, kind="midi", devices=None, slots=3, sends=2, send_states=None):
        self.name = name
        self.has_midi_input = kind == "midi"
        self.is_foldable = kind == "group"
        self.can_be_armed = kind in ("midi", "audio")
        self.mute = self.solo = self.arm = False
        self.mixer_device = Mixer(sends, send_states)
        self.devices = list(devices or [])
        self.clip_slots = [Slot() for _ in range(slots if kind in ("midi", "audio", "group") else 0)]
        self.arrangement_clips = []


class MasterTrack(Track):
    def __init__(self, devices=None):
        Track.__init__(self, "Main", "master", devices, sends=0)

    def __getattribute__(self, name):
        if name in ("mute", "solo", "arm"):
            raise RuntimeError("Main track has no '{0}' property!".format(name))
        return object.__getattribute__(self, name)


class Scene(object):
    def __init__(self, name):
        self.name = name


class Song(object):
    def __init__(self):
        self.tempo, self.signature_numerator, self.signature_denominator = 140.0, 4, 4
        self.name, self.file_path, self.root_note, self.scale_name = "nova", "/sets/nova.als", 9, "Minor"
        self.scenes = [Scene("NEON-MID"), Scene("NEON-LOW"), Scene("FILL")]
        self.operator = Device("Operator", kind=1, parameters=[device_on(), Param("Amount", 0.25), Param("Transpose", 0, -48, 48),
                                                               Param("Algorithm", 0, 0, 10, quantized=True)])
        self.saturator = Device("Saturator", parameters=[device_on(), Param("Drive", 0.3)])
        self.rack = Device("Instrument Rack", "InstrumentGroupDevice", kind=1,
                           parameters=[device_on(), Param("Macro 1", 0.0)],
                           chains=[Chain(self.operator), Chain(Device("Analog", "UltraAnalog", kind=1), self.saturator)])
        self.filter = Device("Auto Filter", "AutoFilter2")
        bass = Track("bass", "midi", [self.rack, self.filter])
        self.clip = Clip("A", [Note(1, 45, 0.0, 1.0, 100), Note(2, 52, 1.0, 0.5, 90, probability=0.5),
                               Note(3, 57, 2.0, 1.0, 80, velocity_deviation=20, release_velocity=30), Note(4, 48, 6.0, mute=True)],
                         length=8.0)
        bass.clip_slots[0].clip = self.clip
        bass.clip_slots[2].clip = Clip("B", [Note(1, 45, 0.0)], length=4.0)
        drum_rack = Device("Drum Rack", "DrumGroupDevice", kind=1, parameters=[device_on()],
                           chains=[Chain(Device("Kick", "OriginalSimpler", kind=1)), Chain(Device("Snare", "OriginalSimpler", kind=1))],
                           return_chains=[Chain(Device("Reverb"))])
        drums = Track("drums", "midi", [drum_rack])
        vox = Track("vox", "audio", [Device("EQ Eight", "Eq8")])
        take = Clip("take", midi=False, length=12.5)
        take.warping = False
        vox.clip_slots[1].clip = take
        vox.arrangement_clips = [Clip("late", midi=False, length=4.0, start_time=16.0), Clip("early", midi=False, start_time=0.0)]
        self.tracks = [bass, drums, vox]
        self.return_tracks = [Track("A-Reverb", "return", [Device("Reverb")], send_states=[1, 1]),
                              Track("B-Delay", "return", [Device("Delay")], send_states=[1, 1])]
        self.master_track = MasterTrack([Device("Limiter")])
        self.syncs = 0

    def sync_parameter_changes(self):
        self.syncs += 1


class App(object):
    def get_version_string(self):
        return "12.4.6"


class Ctx(object):
    def __init__(self, song):
        self.song, self.app, self.messages = song, App(), []

    def log(self, message):
        self.messages.append(message)


@pytest.fixture(autouse=True)
def note_spec(monkeypatch):
    monkeypatch.setattr(sys.modules["Live"].Clip, "MidiNoteSpecification", Spec, raising=False)


@pytest.fixture
def song():
    return Song()


@pytest.fixture
def ctx(song):
    return Ctx(song)


def error_of(function, *args, **kwargs):
    with pytest.raises(CommandError) as caught:
        function(*args, **kwargs)
    return caught.value


def snapshot(ctx, **params):
    """A snapshot as the MCP side receives it (through JSON)."""
    return json.loads(json.dumps(listening.listening_snapshot(ctx, **params)))


def without_ids(data):
    out = copy.deepcopy(data)
    for track in out["tracks"]:
        for clip in track["clips"]:
            for note in clip.get("notes", []):
                note.pop("id")
    return out


TRACK_KEYS = {"index", "name", "kind", "mute", "solo", "arm", "mixer", "devices", "clips"}
CLIP_KEYS = {"slot", "scene", "name", "is_midi", "length", "looping", "loop_start", "loop_end", "start_marker", "end_marker",
             "warping", "muted"}
NOTE_KEYS = {"id", "pitch", "start", "duration", "velocity", "mute", "probability", "velocity_deviation", "release_velocity"}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value, expected", [(4.0, 4), (-0.0, 0), (0.25, 0.25), (1 / 3.0, 1 / 3.0), (float("inf"), None),
                                             (float("nan"), None), (7, 7)])
def test_num(value, expected):
    result = listening.num(value)
    assert result == expected or (expected is None and result is None)
    if isinstance(expected, int):
        assert isinstance(result, int)


def test_align_is_a_leftmost_longest_common_subsequence():
    assert listening.align(list("abc"), list("abc")) == [(0, 0), (1, 1), (2, 2)]
    assert listening.align(list("abc"), list("xabc")) == [(0, 1), (1, 2), (2, 3)]
    assert listening.align(list("abc"), list("ac")) == [(0, 0), (2, 1)]
    assert listening.align(list("aa"), list("a")) == [(0, 0)]
    assert listening.align([], list("a")) == []


def devices(*specs):
    return [{"path": path, "name": name, "class_name": name} for path, name in specs]


def test_match_devices_pairs_by_path_name_and_class():
    wanted = devices(("0", "Rack"), ("0/0/0", "Operator"), ("0/1/0", "Analog"), ("1", "EQ"))
    pairs, removed, added = listening.match_devices(wanted, copy.deepcopy(wanted))
    assert pairs == [(0, 0), (1, 1), (2, 2), (3, 3)] and removed == [] and added == []


def test_match_devices_follows_devices_moved_by_an_insertion():
    wanted = devices(("0", "Rack"), ("0/0/0", "Operator"), ("1", "EQ"))
    current = devices(("0", "Utility"), ("1", "Rack"), ("1/0/0", "Operator"), ("2", "EQ"))
    pairs, removed, added = listening.match_devices(wanted, current)
    assert pairs == [(0, 1), (1, 2), (2, 3)] and removed == [] and added == [0]


def test_match_devices_lists_removed_and_replaced_devices():
    wanted = devices(("0", "Rack"), ("0/0/0", "Operator"), ("0/0/1", "Saturator"), ("1", "EQ"), ("2", "Limiter"))
    current = devices(("0", "Rack"), ("0/0/0", "Saturator"), ("1", "Compressor"), ("2", "Limiter"))
    pairs, removed, added = listening.match_devices(wanted, current)
    assert pairs == [(0, 0), (2, 1), (4, 3)]
    assert removed == [1, 3] and added == [2]


def test_match_devices_keeps_chains_by_index_and_ignores_unpaired_racks():
    wanted = devices(("0", "Rack"), ("0/0/0", "A"), ("0/1/0", "B"), ("0/return:0/0", "Reverb"))
    current = devices(("0", "Other Rack"), ("0/0/0", "A"), ("0/1/0", "B"))
    pairs, removed, added = listening.match_devices(wanted, current)
    assert pairs == [] and removed == [0, 1, 2, 3] and added == [0, 1, 2]
    current = devices(("0", "Rack"), ("0/0/0", "B"), ("0/1/0", "A"), ("0/return:0/0", "Reverb"))
    pairs, removed, added = listening.match_devices(wanted, current)
    assert pairs == [(0, 0), (3, 3)] and removed == [1, 2] and added == [1, 2]


def note(note_id, pitch, start, **fields):
    out = {"id": note_id, "pitch": pitch, "start": start, "duration": 1.0, "velocity": 100.0, "mute": False, "probability": 1.0,
           "velocity_deviation": 0.0, "release_velocity": 64.0}
    out.update(fields)
    return out


def test_diff_notes_unchanged_is_empty():
    notes = [note(1, 60, 0.0), note(2, 64, 1.0, probability=0.5)]
    assert listening.diff_notes(notes, copy.deepcopy(notes)) == ([], {}, [])


def test_diff_notes_modifies_removes_and_adds():
    current = [note(1, 61, 0.0), note(3, 70, 2.0), note(5, 72, 3.0, velocity=10.0)]
    wanted = [note(1, 60, 0.0), note(2, 64, 1.0), note(5, 72, 3.0)]
    remove_ids, modify, add = listening.diff_notes(current, wanted)
    assert remove_ids == [3]
    assert sorted(modify) == [1, 5] and modify[1]["pitch"] == 60 and modify[5]["velocity"] == 100.0
    assert [item["pitch"] for item in add] == [64]


def test_diff_notes_pairs_rewritten_notes_by_pitch_and_start():
    current = [note(7, 60, 0.0), note(8, 64, 1.0, velocity=50.0)]  # same notes, new ids after a rewrite
    wanted = [note(1, 60, 0.0), note(2, 64, 1.0)]
    remove_ids, modify, add = listening.diff_notes(current, wanted)
    assert remove_ids == [] and add == [] and list(modify) == [8] and modify[8]["velocity"] == 100.0


def test_diff_notes_chained_transposition_modifies_in_place():
    current = [note(1, 67, 0.0), note(2, 74, 0.0), note(3, 81, 0.0)]
    wanted = [note(1, 60, 0.0), note(2, 67, 0.0), note(3, 74, 0.0)]
    remove_ids, modify, add = listening.diff_notes(current, wanted)
    assert remove_ids == [] and add == [] and sorted(modify) == [1, 2, 3]


def test_check_note_validates_and_defaults():
    checked = listening.check_note({"pitch": 60, "start": 0, "duration": 0.5}, lambda: "n")
    assert checked == {"id": None, "pitch": 60, "start": 0.0, "duration": 0.5, "mute": False, "velocity": 100.0,
                       "probability": 1.0, "velocity_deviation": 0.0, "release_velocity": 64.0}
    for bad in ({"pitch": 128, "start": 0, "duration": 1}, {"pitch": 60, "start": None, "duration": 1},
                {"pitch": 60, "start": 0, "duration": 0}, {"pitch": 60, "start": 0, "duration": 1, "velocity": 0},
                {"pitch": 60, "start": 0, "duration": 1, "probability": 1.5}, {"pitch": True, "start": 0, "duration": 1}, "x"):
        error = error_of(listening.check_note, bad, lambda: "clip 'A' notes[3]")
        assert error.code == "invalid_argument" and "clip 'A' notes[3]" in error.message


def test_region_changes():
    now = {"looping": True, "loop_start": 0.0, "loop_end": 8.0, "start_marker": 0.0, "end_marker": 8.0, "muted": False}
    assert listening.region_changes(now, dict(now)) == []
    assert listening.region_changes(now, dict(now, loop_end=16, muted=True)) == ["loop_end", "muted"]
    assert listening.region_changes(now, {"name": "A"}) == []  # snapshot without the fields: nothing to compare


# ---------------------------------------------------------------------------
# listening_snapshot
# ---------------------------------------------------------------------------


def test_snapshot_shape(ctx):
    out = snapshot(ctx)
    assert set(out) == {"song", "scenes", "tracks", "returns", "master"}
    assert out["song"] == {"tempo": 140, "time_signature": "4/4", "set_name": "nova", "set_path": "/sets/nova.als",
                           "live_version": "12.4.6", "root_note": 9, "scale_name": "Minor"}
    assert out["scenes"] == [{"index": 0, "name": "NEON-MID"}, {"index": 1, "name": "NEON-LOW"}, {"index": 2, "name": "FILL"}]
    bass, drums, vox = out["tracks"]
    for track in out["tracks"]:
        assert set(track) == TRACK_KEYS
    assert (bass["index"], bass["name"], bass["kind"], bass["arm"], vox["kind"]) == (0, "bass", "midi", False, "audio")
    assert bass["mixer"] == {"volume_db": 0, "pan": 0, "sends": {"A": None, "B": None}}
    assert set(bass["devices"][0]) == {"path", "name", "class_name", "type", "active"}
    assert bass["devices"][0] == {"path": "0", "name": "Instrument Rack", "class_name": "InstrumentGroupDevice",
                                  "type": "instrument", "active": True}
    clip = bass["clips"][0]
    assert set(clip) == CLIP_KEYS | {"notes"}
    assert dict((key, clip[key]) for key in CLIP_KEYS) == {
        "slot": 0, "scene": "NEON-MID", "name": "A", "is_midi": True, "length": 8, "looping": True, "loop_start": 0, "loop_end": 8,
        "start_marker": 0, "end_marker": 8, "warping": None, "muted": False}
    assert [item["slot"] for item in bass["clips"]] == [0, 2]
    assert [set(item) for item in clip["notes"]] == [NOTE_KEYS] * 4
    assert clip["notes"][1] == {"id": 2, "pitch": 52, "start": 1, "duration": 0.5, "velocity": 90, "mute": False,
                                "probability": 0.5, "velocity_deviation": 0, "release_velocity": 64}
    assert clip["notes"][3]["mute"] is True and clip["notes"][2]["velocity_deviation"] == 20
    audio = vox["clips"][0]
    assert (audio["slot"], audio["scene"], audio["is_midi"], audio["warping"], audio["length"]) == (1, "NEON-LOW", False, False, 12.5)
    assert "notes" not in audio
    assert [item["letter"] for item in out["returns"]] == ["A", "B"]
    for entry in out["returns"]:
        assert set(entry) == TRACK_KEYS | {"letter"}
        assert entry["kind"] == "return" and entry["arm"] is None and entry["clips"] == []
        assert entry["mixer"]["sends"] == {}  # return-to-return sends are inactive
    assert out["master"] == {"mixer": {"volume_db": 0, "pan": 0, "sends": {}},
                             "devices": [{"path": "0", "name": "Limiter", "class_name": "Limiter", "type": "audio_effect",
                                          "active": True}]}


def test_snapshot_reads_notes_over_the_whole_clip(ctx, song):
    song.clip.notes.append(Note(9, 40, -0.5))  # Live accepts notes before beat 0; they are part of the clip
    song.clip.loop_end = 4.0  # and the note at beat 6 lies past the loop
    notes = snapshot(ctx, tracks=["bass"])["tracks"][0]["clips"][0]["notes"]
    assert [(item["pitch"], item["start"]) for item in notes] == [(40, -0.5), (45, 0), (52, 1), (57, 2), (48, 6)]
    from_pitch, pitch_span, from_time, time_span = song.clip.windows[-1]
    assert (from_pitch, pitch_span) == (0, 128) and from_time <= -1e6 and from_time + time_span >= 1e6


def test_snapshot_minus_inf_volume_and_sends_are_null(ctx, song):
    mixer = song.tracks[0].mixer_device
    mixer.volume._value = 0.0
    mixer.sends[0]._value = 58 / 76.0  # -12 dB
    mixer.panning._value = -0.25
    out = snapshot(ctx, tracks=["bass"])["tracks"][0]["mixer"]
    assert out == {"volume_db": None, "pan": -0.25, "sends": {"A": -12, "B": None}}
    mixer.volume._value = 0.4 / 76.0  # display -69.6 dB: still audible
    assert snapshot(ctx, tracks=["bass"])["tracks"][0]["mixer"]["volume_db"] == pytest.approx(-69.6)


def test_snapshot_device_paths_recurse_into_rack_drum_and_return_chains(ctx):
    out = snapshot(ctx)
    paths = [(item["path"], item["name"]) for item in out["tracks"][0]["devices"]]
    assert paths == [("0", "Instrument Rack"), ("0/0/0", "Operator"), ("0/1/0", "Analog"), ("0/1/1", "Saturator"),
                     ("1", "Auto Filter")]
    drums = [(item["path"], item["name"], item["type"]) for item in out["tracks"][1]["devices"]]
    assert drums == [("0", "Drum Rack", "instrument"), ("0/0/0", "Kick", "instrument"), ("0/1/0", "Snare", "instrument"),
                     ("0/return:0/0", "Reverb", "audio_effect")]


def test_snapshot_parameters_only_on_request(ctx, song):
    assert all("parameters" not in item for item in snapshot(ctx)["tracks"][0]["devices"])
    out = snapshot(ctx, parameters=True)
    operator = out["tracks"][0]["devices"][1]
    assert operator["parameters"] == [
        {"index": 0, "name": "Device On", "value": 1, "min": 0, "max": 1, "quantized": True, "display": "On"},
        {"index": 1, "name": "Amount", "value": 0.25, "min": 0, "max": 1, "quantized": False, "display": "0.25"},
        {"index": 2, "name": "Transpose", "value": 0, "min": -48, "max": 48, "quantized": False, "display": "0.00"},
        {"index": 3, "name": "Algorithm", "value": 0, "min": 0, "max": 10, "quantized": True, "display": "Off"},
    ]
    assert all("parameters" in item for item in out["master"]["devices"])


def test_snapshot_filters_tracks_scenes_and_notes(ctx, song):
    out = snapshot(ctx, tracks=["vox", "bass", "bass"])
    assert [item["name"] for item in out["tracks"]] == ["bass", "vox"]
    assert out["returns"] == [] and out["master"] is None
    out = snapshot(ctx, tracks=["return:B", "master"])
    assert out["tracks"] == [] and [item["name"] for item in out["returns"]] == ["B-Delay"] and out["returns"][0]["letter"] == "B"
    assert out["master"]["devices"][0]["name"] == "Limiter"
    out = snapshot(ctx, tracks=["bass"], scenes=["FILL"])
    assert out["scenes"] == [{"index": 2, "name": "FILL"}]
    assert [item["name"] for item in out["tracks"][0]["clips"]] == ["B"]
    assert "notes" not in snapshot(ctx, tracks=["bass"], notes=False)["tracks"][0]["clips"][0]
    assert error_of(listening.listening_snapshot, ctx, tracks=["nope"]).code == "not_found"
    assert error_of(listening.listening_snapshot, ctx, scenes=["nope"]).code == "not_found"
    assert error_of(listening.listening_snapshot, ctx, parameters="yes").code == "invalid_argument"


def test_snapshot_group_track(ctx, song):
    group = Track("strings", "group", [Device("Glue Compressor", "GlueCompressor")])
    song.tracks.insert(0, group)
    out = snapshot(ctx, tracks=["strings"], arrangement=True)["tracks"][0]
    assert (out["index"], out["kind"], out["arm"], out["clips"], out["arrangement_clips"]) == (0, "group", None, [], [])
    assert out["devices"][0]["class_name"] == "GlueCompressor"


def test_snapshot_arrangement_clips(ctx):
    out = snapshot(ctx, tracks=["vox", "bass"], arrangement=True)
    vox = out["tracks"][1]
    assert [(item["index"], item["name"], item["start"], item["end"]) for item in vox["arrangement_clips"]] == [
        (0, "early", 0, 4), (1, "late", 16, 20)]
    assert set(vox["arrangement_clips"][0]) == (CLIP_KEYS - {"slot", "scene"}) | {"index", "start", "end"}
    assert out["tracks"][0]["arrangement_clips"] == []
    assert "arrangement_clips" not in snapshot(ctx)["tracks"][0]


# ---------------------------------------------------------------------------
# listening_restore
# ---------------------------------------------------------------------------


def change_everything(song):
    """Edits since the snapshot: notes, parameters (one nested) and mixer of 'bass'."""
    clip = song.clip
    clip.notes[0].pitch = 46                  # modified
    clip.notes[1].probability = 1.0           # modified (probability back to 1)
    del clip.notes[2]                         # removed: comes back with a new id
    clip.notes.append(Note(20, 70, 3.0))      # added: goes
    song.operator.parameters[1].value = 0.9
    song.saturator.parameters[0].value = 0.0  # Device On, inside a rack chain
    mixer = song.tracks[0].mixer_device
    mixer.volume.display_value = -12.0
    mixer.panning.value = 0.5
    mixer.sends[0].display_value = -6.0


def test_restore_round_trip(ctx, song):
    before = snapshot(ctx, parameters=True)
    change_everything(song)
    out = listening.listening_restore(ctx, before)
    assert (out["dry_run"], out["tracks"], out["clips"], out["notes"], out["parameters"], out["mixer"]) == (False, 1, 1, 4, 2, 3)
    assert out["skipped"] == [] and out["added_devices"] == [] and out["removed_devices"] == [] and out["moved_devices"] == []
    assert {"track": "bass", "slot": 0, "clip": "A", "notes": {"added": 1, "removed": 1, "modified": 2}} in out["changes"]
    assert {"track": "bass", "device": "0/0/0", "name": "Operator", "parameters": ["Amount"]} in out["changes"]
    assert {"track": "bass", "mixer": ["volume_db", "pan", "send A"]} in out["changes"]
    after = snapshot(ctx, parameters=True)
    assert without_ids(after) == without_ids(before)
    ids = [item["id"] for item in after["tracks"][0]["clips"][0]["notes"]]
    assert ids[:2] == [1, 2] and 3 not in ids  # edited notes kept their ids; the removed one came back as a new note
    again = listening.listening_restore(ctx, before)
    assert (again["tracks"], again["notes"], again["parameters"], again["mixer"], again["changes"]) == (0, 0, 0, 0, [])


def test_restore_syncs_parameter_changes_inside_its_undo_step(ctx, song):
    """Live commits parameter writes to the undo history late: unsynced, notes and parameters become two steps."""
    before = snapshot(ctx, parameters=True)
    song.clip.notes[0].pitch = 46
    listening.listening_restore(ctx, before)
    assert song.syncs == 0  # notes only: nothing to sync
    change_everything(song)
    listening.listening_restore(ctx, before, dry_run=True)
    assert song.syncs == 0
    listening.listening_restore(ctx, before)
    assert song.syncs == 1


def test_restore_dry_run_changes_nothing(ctx, song):
    before = snapshot(ctx, parameters=True)
    change_everything(song)
    changed = snapshot(ctx, parameters=True)
    out = listening.listening_restore(ctx, before, dry_run=True)
    assert (out["dry_run"], out["tracks"], out["clips"], out["notes"], out["parameters"], out["mixer"]) == (True, 1, 1, 4, 2, 3)
    assert snapshot(ctx, parameters=True) == changed
    assert song.operator.parameters[1].writes == 1  # only the edit above


def test_restore_flags_limit_what_is_written(ctx, song):
    before = snapshot(ctx, parameters=True)
    change_everything(song)
    out = listening.listening_restore(ctx, before, notes=False, mixer=False)
    assert (out["notes"], out["parameters"], out["mixer"]) == (0, 2, 0)
    out = listening.listening_restore(ctx, before, parameters=False)
    assert (out["notes"], out["parameters"], out["mixer"]) == (4, 0, 3)
    assert without_ids(snapshot(ctx, parameters=True)) == without_ids(before)


def test_restore_parameters_need_a_parameter_snapshot(ctx, song):
    before = snapshot(ctx)  # parameters=False: devices without parameters
    song.operator.parameters[1].value = 0.9
    out = listening.listening_restore(ctx, before)
    assert out["parameters"] == 0 and song.operator.parameters[1].value == 0.9


def test_restore_matches_tracks_by_exact_name(ctx, song):
    before = snapshot(ctx, parameters=True)
    before["tracks"].append(dict(before["tracks"][0], name="Bass"))  # case differs: not the same track
    song.tracks.append(Track("vox", "audio"))  # two tracks named vox now
    out = listening.listening_restore(ctx, before)
    assert {"track": "Bass", "reason": "track not found"} in out["skipped"]
    assert {"track": "vox", "reason": "2 tracks share this name"} in out["skipped"]


def test_restore_lists_added_removed_and_moved_devices(ctx, song):
    before = snapshot(ctx, parameters=True)
    bass = song.tracks[0]
    bass.devices.insert(0, Device("Utility", "StereoGain"))  # everything moves one place right
    del song.rack.chains[1].devices[0]                        # Analog removed: Saturator moves to 1/1/0
    song.saturator.parameters[1].value = 0.8
    out = listening.listening_restore(ctx, before)
    assert out["added_devices"] == [{"track": "bass", "path": "0", "name": "Utility", "class_name": "StereoGain"}]
    assert out["removed_devices"] == [{"track": "bass", "path": "0/1/0", "name": "Analog", "class_name": "UltraAnalog"}]
    assert {"track": "bass", "name": "Saturator", "from": "0/1/1", "to": "1/1/0"} in out["moved_devices"]
    assert {"track": "bass", "name": "Auto Filter", "from": "1", "to": "2"} in out["moved_devices"]
    assert out["parameters"] == 1 and song.saturator.parameters[1].value == pytest.approx(0.3)
    assert len(bass.devices) == 3  # added devices are listed, not removed


def test_restore_skips_parameters_it_must_not_write(ctx, song):
    before = snapshot(ctx, parameters=True)
    amount, transpose, algorithm = song.operator.parameters[1:4]
    amount.value = 0.9
    amount.is_enabled = False             # macro-mapped since
    transpose.value = 12
    transpose.automation_state = 1        # automated since
    algorithm.value = 3
    algorithm.name = "Algo"               # another parameter at this index now
    song.filter.parameters.pop()          # Auto Filter lost its parameter 1
    out = listening.listening_restore(ctx, before)
    assert sorted((item["device"], item["parameter"], item["reason"]) for item in out["skipped"]) == [
        ("0/0/0", "Algorithm", "parameter 3 is named 'Algo' now"),
        ("0/0/0", "Amount", "disabled (macro-mapped or controlled by Max)"),
        ("0/0/0", "Transpose", "automated: its value follows the automation"),
        ("1", "Amount", "the device has no parameter 1 now (1 parameters)"),
    ]
    assert out["parameters"] == 0
    assert (amount.value, transpose.value, algorithm.value) == (0.9, 12, 3)


def test_restore_skips_values_outside_the_current_range(ctx, song):
    before = snapshot(ctx, parameters=True)
    transpose = song.operator.parameters[2]
    before["tracks"][0]["devices"][1]["parameters"][2]["value"] = 60  # outside -48..48
    out = listening.listening_restore(ctx, before)
    assert [item["reason"] for item in out["skipped"]] == ["value 60 is outside the parameter's range -48..48 now"]
    assert transpose.value == 0


def test_restore_drops_a_disabled_parameter_its_macro_brought_back(ctx, song):
    macro, amount = song.rack.parameters[1], song.operator.parameters[1]
    macro.followers.append((amount, lambda value: 0.25 + value))  # Macro 1 drives Operator's Amount
    before = snapshot(ctx, parameters=True)
    amount.is_enabled = False
    macro.value = 0.5  # Amount follows to 0.75
    out = listening.listening_restore(ctx, before)
    assert out["parameters"] == 1 and macro.value == 0.0 and amount.value == 0.25
    assert out["skipped"] == []  # Amount was disabled, but restoring the macro restored it
    plan = listening.listening_restore(ctx, dict(before, tracks=[before["tracks"][0]]), dry_run=True)
    assert plan["parameters"] == 0


def test_restore_reports_a_write_live_refuses_and_goes_on(ctx, song):
    before = snapshot(ctx, parameters=True)
    change_everything(song)
    song.operator.parameters[1].fail = True
    out = listening.listening_restore(ctx, before)
    assert out["parameters"] == 1 and out["mixer"] == 3 and out["notes"] == 4
    assert [(item["parameter"], item["reason"]) for item in out["skipped"]] == [
        ("Amount", "Live refused the change: Parameter refused the value")]
    assert any("Parameter refused the value" in message for message in ctx.messages)


def test_restore_matches_clips_by_scene_name_then_slot(ctx, song):
    before = snapshot(ctx)
    song.clip.notes[0].pitch = 30
    song.scenes.insert(0, Scene("NEW"))  # every slot moves one down
    for track in song.tracks:
        track.clip_slots.insert(0, Slot())
    out = listening.listening_restore(ctx, before)
    assert out["notes"] == 1 and out["changes"][0]["slot"] == 1 and song.clip.notes[0].pitch == 45
    song.clip.notes[0].pitch = 30
    song.scenes[1].name = "renamed"  # the scene is gone by name: fall back to the slot, which now holds another clip
    out = listening.listening_restore(ctx, before)
    assert out["notes"] == 0
    assert {"track": "bass", "slot": 0, "clip": "A", "reason": "the slot is empty"} in out["skipped"]


def test_restore_skips_missing_renamed_and_audio_clips(ctx, song):
    before = snapshot(ctx)
    bass = song.tracks[0]
    bass.clip_slots[2].clip.name = "B2"
    bass.clip_slots[0].clip = Clip("A", midi=False)
    out = listening.listening_restore(ctx, before)
    assert {"track": "bass", "slot": 2, "clip": "B", "reason": "the clip in this slot is named 'B2'"} in out["skipped"]
    assert {"track": "bass", "slot": 0, "clip": "A", "reason": "the clip is an audio clip now"} in out["skipped"]
    bass.clip_slots[0].clip = None
    out = listening.listening_restore(ctx, before)
    assert {"track": "bass", "slot": 0, "clip": "A", "reason": "the slot is empty"} in out["skipped"]


def test_restore_reports_clip_region_changes_but_writes_notes_only(ctx, song):
    before = snapshot(ctx)
    song.clip.loop_end = 16.0
    song.clip.muted = True
    out = listening.listening_restore(ctx, before)
    assert out["notes"] == 0 and song.clip.loop_end == 16.0
    assert out["skipped"][0]["reason"].startswith("clip loop_end, muted changed since the snapshot (now loop 0..16, markers 0..8, muted;")


def test_restore_arrangement_clip_notes(ctx, song):
    bass = song.tracks[0]
    bass.arrangement_clips = [Clip("A", [Note(1, 45, 0.0)], start_time=32.0)]
    before = snapshot(ctx, tracks=["bass"], arrangement=True)
    bass.arrangement_clips[0].notes[0].pitch = 47
    out = listening.listening_restore(ctx, before)
    assert out["notes"] == 1 and bass.arrangement_clips[0].notes[0].pitch == 45
    assert {"track": "bass", "arrangement_clip": 0, "clip": "A", "notes": {"added": 0, "removed": 0, "modified": 1}} in out["changes"]
    bass.arrangement_clips[0].start_time = 36.0
    out = listening.listening_restore(ctx, before)
    assert out["skipped"][0]["reason"] == "no arrangement clip of this name starts at beat 32"


def test_restore_mixer_levels_and_minus_inf(ctx, song):
    mixer = song.tracks[0].mixer_device
    mixer.sends[1].display_value = -20.0
    before = snapshot(ctx, tracks=["bass"])
    mixer.volume._value = 0.0       # -inf now
    mixer.sends[1]._value = 0.0
    mixer.sends[0].display_value = -3.0  # the snapshot holds -inf here
    out = listening.listening_restore(ctx, before)
    assert out["mixer"] == 3
    assert snapshot(ctx, tracks=["bass"])["tracks"][0]["mixer"] == {"volume_db": 0, "pan": 0, "sends": {"A": None, "B": -20}}
    assert mixer.sends[0].value == 0.0


def test_restore_sends_follow_their_return_by_name(ctx, song):
    mixer = song.tracks[0].mixer_device
    mixer.sends[0].display_value = -15.0  # bass -> A-Reverb
    mixer.sends[1].display_value = -9.0   # bass -> B-Delay
    before = snapshot(ctx)
    del song.return_tracks[0]             # Reverb deleted: Delay becomes return A, at send index 0
    song.return_tracks[0].name = "A-Delay"
    del mixer.sends[0]
    mixer.sends[0]._value = 0.0
    out = listening.listening_restore(ctx, before)
    assert {"track": "bass", "mixer": "send A", "reason": "return track 'Reverb' not found"} in out["skipped"]
    assert {"track": "A-Reverb", "reason": "return track not found"} in out["skipped"]
    assert len(out["skipped"]) == 2  # the other tracks' silent sends to Reverb need nothing
    assert {"track": "bass", "mixer": ["send A (was B)"]} in out["changes"]
    assert mixer.sends[0].display_value == pytest.approx(-9.0)
    # Without the snapshot's return names, letters are send indices: A lands on what is now the Delay send.
    mixer.sends[0]._value = 0.0
    out = listening.listening_restore(ctx, dict(before, returns=[]))
    assert mixer.sends[0].display_value == pytest.approx(-15.0)
    assert {"track": "bass", "mixer": "send B", "reason": "return track 'B' not found"} in out["skipped"]


def test_restore_skips_automated_or_inactive_mixer_values(ctx, song):
    before = snapshot(ctx, tracks=["bass"])
    mixer = song.tracks[0].mixer_device
    mixer.volume.display_value = -10.0
    mixer.volume.automation_state = 1
    mixer.sends[0].display_value = -10.0
    mixer.sends[0].state = 1
    before["tracks"][0]["mixer"]["sends"]["A"] = -5.0
    out = listening.listening_restore(ctx, before)
    assert out["mixer"] == 0
    reasons = dict((item["mixer"], item["reason"]) for item in out["skipped"])
    assert reasons["volume_db"].startswith("automated") and reasons["send A"].startswith("the send is inactive")


def test_restore_returns_and_master(ctx, song):
    before = snapshot(ctx, parameters=True)
    song.return_tracks[1].mixer_device.volume.display_value = -4.0
    song.return_tracks[1].devices[0].parameters[1].value = 0.1
    song.master_track.mixer_device.panning.value = 0.2
    song.return_tracks[1].name = "B-Delay"
    out = listening.listening_restore(ctx, before)
    assert (out["tracks"], out["parameters"], out["mixer"]) == (2, 1, 2)
    assert {"track": "B-Delay", "mixer": ["volume_db"]} in out["changes"] and {"track": "master", "mixer": ["pan"]} in out["changes"]
    renamed = copy.deepcopy(before)
    renamed["returns"][1]["name"] = "A-Delay"  # matched by bare name, whatever the letter
    song.return_tracks[1].mixer_device.volume.display_value = -4.0
    assert listening.listening_restore(ctx, renamed)["mixer"] == 1


def test_restore_validates_the_whole_snapshot_before_writing(ctx, song):
    before = snapshot(ctx, parameters=True)
    change_everything(song)
    changed = snapshot(ctx, parameters=True)
    broken = copy.deepcopy(before)
    broken["tracks"][2]["mixer"]["volume_db"] = 12  # vox comes after bass, whose changes are planned first
    error = error_of(listening.listening_restore, ctx, broken)
    assert error.code == "invalid_argument" and "above the maximum" in error.message
    broken = copy.deepcopy(before)
    broken["tracks"][0]["clips"][1]["notes"][0]["velocity"] = 0
    error = error_of(listening.listening_restore, ctx, broken)
    assert "bass clip 'B' notes[0]" in error.message and "velocity" in error.message
    assert snapshot(ctx, parameters=True) == changed


@pytest.mark.parametrize("bad", [None, [], {}, {"tracks": "bass"}, {"tracks": [1]}, {"master": 3}, {"tracks": []}])
def test_restore_rejects_malformed_snapshots(ctx, bad):
    assert error_of(listening.listening_restore, ctx, bad).code == "invalid_argument"


def test_restore_bounds_its_lists(ctx, song):
    before = snapshot(ctx)
    before["tracks"] = [{"name": "ghost {0}".format(position)} for position in range(60)]
    out = listening.listening_restore(ctx, before)
    assert len(out["skipped"]) == listening.LIST_LIMIT and out["skipped_total"] == 60


def test_commands_are_registered():
    snapshot_spec, restore_spec = core.COMMANDS["listening_snapshot"], core.COMMANDS["listening_restore"]
    assert snapshot_spec.readonly and snapshot_spec.params == ["tracks", "scenes", "notes", "parameters", "arrangement"]
    assert not restore_spec.readonly and restore_spec.undo
    assert restore_spec.params == ["snapshot", "notes", "parameters", "mixer", "dry_run"] and restore_spec.required == ["snapshot"]
