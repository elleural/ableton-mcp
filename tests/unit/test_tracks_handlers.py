"""Unit tests for WS-B's Remote Script handlers against small fakes of Live's Song, Track and mixer."""
import pytest

from AbletonMCP_Remote_Script import refs
from AbletonMCP_Remote_Script.errors import CommandError
from AbletonMCP_Remote_Script.handlers import tracks

ZERO_DB = 70 / 76.0  # fake dB parameters use the meter scale: dB = 76 * value - 70


class Param(object):
    """DeviceParameter fake. kind: 'db' (volume/send), 'pan', 'crossfader' or 'switch'."""

    def __init__(self, name, value=0.0, minimum=0.0, maximum=1.0, kind="db", state=0):
        self.name = self.original_name = name
        self.value, self.min, self.max, self.kind, self.state = value, minimum, maximum, kind, state
        self.is_quantized = kind == "switch"
        self.is_enabled = True

    def _display(self, value):
        return {"db": 76.0 * value - 70.0, "pan": value * 50.0, "crossfader": value * 50.0}.get(self.kind, value)

    @property
    def display_value(self):
        return self._display(self.value)

    @display_value.setter
    def display_value(self, number):
        raw = {"db": (number + 70.0) / 76.0, "pan": number / 50.0, "crossfader": number / 50.0}.get(self.kind, number)
        self.value = min(max(raw, self.min), self.max)

    def str_for_value(self, value):
        if self.kind == "db":
            return "-inf dB" if value <= self.min else "{0:.1f} dB".format(self._display(value))
        if self.kind in ("pan", "crossfader"):
            if abs(value) < 1e-9:
                return "C" if self.kind == "pan" else "0"
            sides = ("L", "R") if self.kind == "pan" else ("A", "B")
            return "{0}{1}".format(int(round(abs(value) * 50)), sides[0] if value < 0 else sides[1])
        return str(value)


class Mixer(object):
    def __init__(self, sends=2, master=False, send_state=0):
        self.volume = Param("Track Volume", ZERO_DB)
        self.panning = Param("Track Panning", 0.0, -1.0, 1.0, "pan")
        self.track_activator = Param("Speaker On", 1.0, kind="switch")
        self.left_split_stereo = Param("Left Split Stereo", -1.0, -1.0, 1.0, "pan")
        self.right_split_stereo = Param("Right Split Stereo", 1.0, -1.0, 1.0, "pan")
        self.sends = [] if master else [Param("Send", 0.0, state=send_state) for _ in range(sends)]
        self.panning_mode = 0
        self._crossfade = 1
        self._master = master
        if master:
            self.crossfader = Param("Crossfade", 0.0, -1.0, 1.0, "crossfader")
            self.cue_volume = Param("Preview Volume", 64 / 76.0)

    @property
    def crossfade_assign(self):
        if self._master:
            raise RuntimeError("Main track has no crossfader assignment!")
        return self._crossfade

    @crossfade_assign.setter
    def crossfade_assign(self, value):
        self._crossfade = value


class Routing(object):
    def __init__(self, display_name, attached_object=None):
        self.display_name = display_name
        self.attached_object = attached_object


class View(object):
    is_collapsed = False


class Device(object):
    def __init__(self, name, class_name=None):
        self.name = self.class_display_name = name
        self.class_name = class_name or name
        self.parameters = [Param("Device On", 1.0, kind="switch")]
        self.is_active = True
        self.type = 1
        self.can_have_chains = False


class Track(object):
    def __init__(self, name, kind="audio", sends=2):
        self.name = name
        self.has_midi_input = kind == "midi"
        self.has_audio_input = kind != "midi"
        self.has_audio_output = kind not in ("midi",)
        self.has_midi_output = kind == "midi"
        self.is_foldable = kind == "group"
        self.can_be_armed = kind in ("midi", "audio")
        self.mute = self.solo = self.arm = self.implicit_arm = False
        self.current_monitoring_state = 1
        self.fold_state = 0
        self.is_grouped, self.group_track, self.is_frozen = False, None, False
        self.devices, self.clip_slots, self.arrangement_clips, self.take_lanes = [], [], [], []
        self.view = View()
        self.mixer_device = Mixer(sends)
        self.color_index, self.color = 3, 0xFF8800
        self.can_show_chains = self.is_showing_chains = False
        self.output_meter_left = self.output_meter_right = self.output_meter_level = 0.0
        self.input_meter_left = self.input_meter_right = self.input_meter_level = 0.0
        self.available_input_routing_types = [Routing("Ext. In"), Routing("No Input")]
        self.available_output_routing_types = [Routing("Main"), Routing("Sends Only")]
        self.channels = {"Ext. In": ["1/2", "1", "2"], "No Input": [""], "Main": [""], "Sends Only": [""]}
        self.input_routing_type = self.available_input_routing_types[0]
        self.output_routing_type = self.available_output_routing_types[0]
        self.input_routing_channel = Routing("1/2")
        self.output_routing_channel = Routing("")
        self.fail_channel = False

    @property
    def available_input_routing_channels(self):
        return [Routing(name) for name in self.channels.get(self.input_routing_type.display_name, [""])]

    @property
    def available_output_routing_channels(self):
        return [Routing(name) for name in self.channels.get(self.output_routing_type.display_name, [""])]

    def __setattr__(self, name, value):
        if name in ("input_routing_channel", "output_routing_channel") and getattr(self, "fail_channel", False):
            raise RuntimeError("channel rejected")
        object.__setattr__(self, name, value)

    def insert_device(self, name):
        if name == "Broken":
            raise RuntimeError("Can not insert device")
        device = Device(name)
        self.devices.append(device)
        if self.has_midi_input:
            self.has_audio_output = True
        return device


class ReturnTrack(Track):
    def __init__(self, song, bare_name, sends=2, send_state=1):
        self.song = song
        Track.__init__(self, bare_name, "return", sends)
        self.mixer_device = Mixer(sends, send_state=send_state)

    def __setattr__(self, name, value):
        if name == "name" and "song" in self.__dict__:
            position = len(self.song.return_tracks) if self not in self.song.return_tracks else self.song.return_tracks.index(self)
            value = "{0}-{1}".format(refs.return_letter(position), value)
        Track.__setattr__(self, name, value)


class MasterTrack(Track):
    def __init__(self):
        Track.__init__(self, "Main", "master", 0)
        self.mixer_device = Mixer(0, master=True)
        self.can_be_armed = False
        self.clip_slots = []

    def __getattribute__(self, name):
        if name in ("mute", "solo", "arm", "current_monitoring_state"):
            raise RuntimeError("Main track has no '{0}' property!".format(name))
        return object.__getattribute__(self, name)


class Song(object):
    def __init__(self):
        self.signature_numerator = self.signature_denominator = 4
        self.is_playing = False
        self.tracks = [Track("1-MIDI", "midi"), Track("Bass", "audio"), Track("Keys", "audio")]
        self.return_tracks = []
        for bare in ("Reverb", "Delay"):
            track = ReturnTrack(self, bare)
            self.return_tracks.append(track)
        self.master_track = MasterTrack()
        for track in self.tracks:
            track.available_output_routing_types.insert(1, Routing("Keys", self.tracks[2]))

    def _new(self, track, index):
        self.tracks.insert(len(self.tracks) if index == -1 else index, track)
        return track

    def create_midi_track(self, index):
        return self._new(Track("{0}-MIDI".format(len(self.tracks) + 1), "midi"), index)

    def create_audio_track(self, index):
        return self._new(Track("{0}-Audio".format(len(self.tracks) + 1), "audio"), index)

    def create_return_track(self):
        track = ReturnTrack(self, "Return")
        self.return_tracks.append(track)
        return track

    def delete_track(self, index):
        del self.tracks[index]

    def delete_return_track(self, index):
        del self.return_tracks[index]

    def duplicate_track(self, index):
        source = self.tracks[index]
        copy = Track(source.name, "midi" if source.has_midi_input else "audio")
        self.tracks.insert(index + 1, copy)


class Ctx(object):
    def __init__(self, song):
        self.song = song
        self.app = object()


@pytest.fixture
def song():
    return Song()


@pytest.fixture
def ctx(song):
    return Ctx(song)


@pytest.fixture(autouse=True)
def native_devices(monkeypatch):
    names = {"instruments": ["Operator", "Wavetable"], "audio_effects": ["Reverb", "EQ Eight", "Broken"], "midi_effects": ["Arpeggiator"]}
    monkeypatch.setattr(refs, "native_device_names", lambda app: names)
    return names


def error_of(function, *args, **kwargs):
    with pytest.raises(CommandError) as caught:
        function(*args, **kwargs)
    return caught.value


# --- mixer ----------------------------------------------------------------------------------------


def test_mixer_state_regular_track(song):
    bass = song.tracks[1]
    bass.mixer_device.sends[1].value = 58 / 76.0  # -12 dB
    state = tracks.mixer_state(song, bass)
    assert state["track"] == 1 and state["kind"] == "audio"
    assert state["volume_db"] == 0.0 and state["pan"] == 0.0 and state["pan_display"] == "C"
    assert state["sends"] == {"A": "-inf", "B": -12.0}
    assert state["crossfade"] == "none" and state["pan_mode"] == "stereo" and state["active"] is True
    assert state["arm"] is False and "crossfader" not in state


def test_mixer_state_return_lists_inactive_sends(song):
    state = tracks.mixer_state(song, song.return_tracks[0])
    assert state["track"] == "return:A" and state["name"] == "A-Reverb"
    assert state["sends"] == {} and state["inactive_sends"] == ["A", "B"]
    assert "arm" not in state


def test_mixer_state_master(song):
    state = tracks.mixer_state(song, song.master_track)
    assert state["kind"] == "master" and state["cue_volume_db"] == -6.0
    assert state["crossfader"] == 0.0 and state["crossfader_display"] == "0"
    for absent in ("sends", "mute", "solo", "crossfade", "arm"):
        assert absent not in state


def test_set_mixer_volume_and_sends_keep_their_own_values(ctx, song):
    state = tracks.set_mixer(ctx, "Bass", volume_db=-6, sends={"A": -12, "Delay": "-inf"})
    assert state["volume_db"] == -6.0
    assert state["sends"] == {"A": -12.0, "B": "-inf"}


def test_set_mixer_switches_pan_and_modes(ctx, song):
    state = tracks.set_mixer(ctx, 1, pan="25L", mute=True, solo=True, active=False, crossfade="B",
                             pan_mode="split", left_pan=-0.5, right_pan="50R")
    assert state["pan"] == -0.5 and state["pan_display"] == "25L"
    assert state["mute"] and state["solo"] and state["active"] is False
    assert state["crossfade"] == "B" and state["pan_mode"] == "split"
    assert state["left_pan"] == -0.5 and state["right_pan"] == 1.0


def test_set_mixer_raw_volume_and_silence(ctx, song):
    assert tracks.set_mixer(ctx, "Bass", volume=ZERO_DB)["volume_db"] == 0.0
    assert tracks.set_mixer(ctx, "Bass", volume_db="-inf")["volume_db"] == "-inf"
    assert tracks.set_mixer(ctx, "Bass", volume_db=-90)["volume_db"] == "-inf"


def test_set_mixer_validates_everything_before_changing_anything(ctx, song):
    error = error_of(tracks.set_mixer, ctx, "Bass", volume_db=-6, sends={"A": 3})
    assert error.code == "invalid_argument" and "above the maximum" in error.message
    assert tracks.mixer_state(song, song.tracks[1])["volume_db"] == 0.0


@pytest.mark.parametrize("kwargs, code", [
    ({}, "invalid_argument"),
    ({"volume_db": 7}, "invalid_argument"),
    ({"volume_db": -6, "volume": 0.5}, "invalid_argument"),
    ({"volume": 1.5}, "invalid_argument"),
    ({"crossfader": 0.5}, "invalid_argument"),
    ({"cue_volume_db": -6}, "invalid_argument"),
    ({"sends": {"Z": -6}}, "not_found"),
    ({"sends": []}, "invalid_argument"),
    ({"crossfade": "middle"}, "invalid_argument"),
    ({"mute": "yes"}, "invalid_argument"),
])
def test_set_mixer_errors(ctx, kwargs, code):
    assert error_of(tracks.set_mixer, ctx, "Bass", **kwargs).code == code


def test_set_mixer_master_only_parameters(ctx, song):
    state = tracks.set_mixer(ctx, "master", crossfader="25B", cue_volume_db=-12, volume_db=-1.5)
    assert state["crossfader"] == 0.5 and state["cue_volume_db"] == -12.0 and state["volume_db"] == -1.5
    assert error_of(tracks.set_mixer, ctx, "master", mute=True).code == "unsupported"
    assert error_of(tracks.set_mixer, ctx, "master", crossfade="A").code == "unsupported"
    assert error_of(tracks.set_mixer, ctx, "master", sends={"A": -6}).code == "unsupported"


def test_set_mixer_refuses_inactive_return_sends(ctx):
    assert error_of(tracks.set_mixer, ctx, "return:A", sends={"B": -6}).code == "unsupported"


def test_get_mixer_covers_every_track(ctx, song):
    names = [item["name"] for item in tracks.get_mixer(ctx)["tracks"]]
    assert names == ["1-MIDI", "Bass", "Keys", "A-Reverb", "B-Delay", "Main"]
    assert [item["name"] for item in tracks.get_mixer(ctx, tracks=["Keys", "master"])["tracks"]] == ["Keys", "Main"]


# --- meters ---------------------------------------------------------------------------------------


def test_meters_state_audio_track(song):
    bass = song.tracks[1]
    bass.output_meter_left, bass.output_meter_right, bass.output_meter_level = 0.5, 64 / 76.0, ZERO_DB
    bass.input_meter_left = ZERO_DB
    state = tracks.meters_state(song, bass)
    assert state["output"]["left_db"] == -32.0 and state["output"]["right_db"] == -6.0
    assert state["output"]["peak_db"] == 0.0 and state["output"]["over_0db"] is True
    assert state["input"]["left_db"] == 0.0 and state["input"]["right_db"] == "-inf"


def test_meters_state_midi_track_without_instrument(song):
    midi = song.tracks[0]
    midi.output_meter_level = 0.25
    state = tracks.meters_state(song, midi)
    assert state["output"] == {"midi": 0.25} and "input" in state


def test_get_meters_notes_a_stopped_transport(ctx, song):
    result = tracks.get_meters(ctx, tracks=["master"])
    assert result["playing"] is False and "note" in result
    assert result["tracks"][0]["output"]["peak_db"] == "-inf" and "input" not in result["tracks"][0]


# --- tracks ---------------------------------------------------------------------------------------


class Slot(object):
    def __init__(self, clip=None):
        self.clip = clip
        self.has_clip = clip is not None
        self.is_recording = self.is_triggered = False


class Clip(object):
    def __init__(self, name, start=0.0, length=4.0):
        self.name, self.start_time, self.end_time, self.length = name, start, start + length, length
        self.is_playing = False


def test_track_state_bounds_slots_and_reports_arrangement(song):
    keys = song.tracks[2]
    keys.clip_slots = [Slot(Clip("c{0}".format(i))) for i in range(tracks.MAX_SLOTS + 5)] + [Slot()]
    keys.arrangement_clips = [Clip("late", 32.0, 8.0), Clip("early", 4.0, 4.0)]
    keys.devices = [Device("EQ Eight", "Eq8")]
    state = tracks.track_state(song, keys)
    assert len(state["slots"]) == tracks.MAX_SLOTS and state["slots_truncated"] == 5
    assert state["slot_count"] == tracks.MAX_SLOTS + 6
    assert state["arrangement"] == {"clip_count": 2, "start": {"beats": 4.0, "bar": "2.1.1"}, "end": {"beats": 40.0, "bar": "11.1.1"}}
    assert state["devices"] == [{"index": 0, "name": "EQ Eight", "class": "EQ Eight", "on": True}]
    assert state["input"] == {"type": "Ext. In", "channel": "1/2"} and state["output"] == {"type": "Main", "channel": None}
    detail = tracks.track_state(song, keys, detail=True)
    assert len(detail["slots"]) == tracks.MAX_SLOTS + 5 and "slots_truncated" not in detail
    assert [clip["name"] for clip in detail["arrangement"]["clips"]] == ["early", "late"]
    assert detail["devices"][0]["class_name"] == "Eq8" and "meters" in detail and "state" in detail


def test_track_state_master_and_return(song):
    master = tracks.track_state(song, song.master_track)
    assert master["kind"] == "master" and "input" not in master and "mute" not in master and "arrangement" not in master
    ret = tracks.track_state(song, song.return_tracks[1])
    assert ret["track"] == "return:B" and "input" not in ret and "monitoring" not in ret


def test_create_track_with_device(ctx, song):
    out = tracks.create_track(ctx, "midi", name="Lead", color="#FF0000", device="operator")
    assert out["name"] == "Lead" and out["kind"] == "midi" and out["track"] == 3
    assert out["device"]["name"] == "Operator" and out["arm"] is False and out["monitoring"] == "auto"
    assert song.tracks[3].color == 0xFF0000


def test_create_track_omits_routing_live_has_not_resolved(ctx, song, monkeypatch):
    original = song.create_audio_track

    def unresolved(index):
        track = original(index)
        track.output_routing_type = Routing("")
        return track

    monkeypatch.setattr(song, "create_audio_track", unresolved)
    out = tracks.create_track(ctx, "audio", name="Fresh")
    assert "output" not in out and out["input"]["type"] == "Ext. In" and "next call" in out["note"]


def test_create_return_track_strips_its_own_letter(ctx, song):
    out = tracks.create_track(ctx, "return", name="C-Verb 2")
    assert out["name"] == "C-Verb 2" and out["track"] == "return:C"


@pytest.mark.parametrize("kwargs, code", [
    ({"kind": "group"}, "invalid_argument"),
    ({"kind": "audio", "device": "Operator"}, "invalid_argument"),
    ({"kind": "return", "device": "Arpeggiator"}, "invalid_argument"),
    ({"kind": "audio", "device": "Granulator III"}, "not_found"),
    ({"kind": "midi", "index": 99}, "invalid_argument"),
    ({"kind": "return", "index": 0}, "invalid_argument"),
    ({"kind": "midi", "color": 120}, "invalid_argument"),
    ({"kind": "midi", "name": "  "}, "invalid_argument"),
])
def test_create_track_validates_before_creating(ctx, song, kwargs, code):
    count = len(song.tracks), len(song.return_tracks)
    assert error_of(tracks.create_track, ctx, **kwargs).code == code
    assert (len(song.tracks), len(song.return_tracks)) == count


def test_create_track_removes_the_track_when_the_device_fails(ctx, song):
    count = len(song.tracks)
    error = error_of(tracks.create_track, ctx, "audio", name="FX", device="Broken")
    assert error.code == "live_error" and "not created" in error.message and "load_from_browser" in error.hint
    assert len(song.tracks) == count


def test_set_track_switches_and_routing(ctx, song):
    out = tracks.set_track(ctx, "Bass", name="Bass 2", arm=True, monitoring="in", collapsed=True,
                           input="ext. in", input_channel=2, output="sends only")
    assert out["name"] == "Bass 2" and out["arm"] is True and out["monitoring"] == "in" and out["collapsed"] is True
    assert out["input"] == {"type": "Ext. In", "channel": "2"} and out["output"]["type"] == "Sends Only"


def test_set_track_routes_to_a_track_by_index(ctx, song):
    out = tracks.set_track(ctx, "Bass", output=2)
    assert out["output"]["type"] == "Keys"


def test_set_track_unknown_routing_lists_options_and_changes_nothing(ctx, song):
    error = error_of(tracks.set_track, ctx, "Bass", name="Renamed", output="Nowhere")
    assert error.code == "not_found" and "Available: Main, Keys, Sends Only" in error.message
    assert song.tracks[1].name == "Bass"


def test_set_track_routing_not_ready_is_busy(ctx, song):
    song.tracks[1].available_output_routing_types = [Routing("")]
    assert error_of(tracks.set_track, ctx, "Bass", output="Main").code == "busy"


def test_set_track_restores_the_type_when_the_channel_fails(ctx, song):
    bass = song.tracks[1]
    bass.input_routing_type = bass.available_input_routing_types[1]  # No Input
    bass.channels["No Input"] = [""]
    bass.fail_channel = True
    with pytest.raises(Exception):
        tracks.set_track(ctx, "Bass", input="Ext. In", input_channel="1")
    assert bass.input_routing_type.display_name == "No Input"


@pytest.mark.parametrize("track, kwargs, code", [
    ("Bass", {}, "invalid_argument"),
    ("Bass", {"fold": True}, "unsupported"),
    ("Bass", {"show_chains": True}, "unsupported"),
    ("Bass", {"monitoring": "loud"}, "invalid_argument"),
    ("return:A", {"monitoring": "in"}, "unsupported"),
    ("return:A", {"arm": True}, "unsupported"),
    ("return:A", {"input": "Ext. In"}, "unsupported"),
    ("master", {"input_channel": "1/2"}, "unsupported"),
    ("Nope", {"name": "x"}, "not_found"),
])
def test_set_track_errors(ctx, track, kwargs, code):
    assert error_of(tracks.set_track, ctx, track, **kwargs).code == code


def test_set_track_renames_return_without_doubling_the_letter(ctx, song):
    assert tracks.set_track(ctx, "Reverb", name="A-Hall")["name"] == "A-Hall"


def test_delete_track(ctx, song):
    assert error_of(tracks.delete_track, ctx, "master").code == "invalid_argument"
    out = tracks.delete_track(ctx, "Keys")
    assert out == {"deleted": {"track": 2, "name": "Keys", "kind": "audio"}, "tracks_removed": 1}
    out = tracks.delete_track(ctx, "return:B")
    assert out["deleted"]["name"] == "B-Delay" and "note" in out and len(song.return_tracks) == 1


def test_duplicate_track(ctx, song):
    out = tracks.duplicate_track(ctx, "Bass", name="Bass copy")
    assert out["track"] == 2 and out["name"] == "Bass copy" and out["source"]["track"] == 1
    assert error_of(tracks.duplicate_track, ctx, "return:A").code == "unsupported"
    assert error_of(tracks.duplicate_track, ctx, "master").code == "unsupported"


def test_get_routing_options(ctx, song):
    out = tracks.get_routing_options(ctx, "Bass")
    assert out["input"] == {"type": "Ext. In", "channel": "1/2", "types": ["Ext. In", "No Input"], "channels": ["1/2", "1", "2"]}
    assert out["output"]["types"] == ["Main", "Keys", "Sends Only"] and out["output"]["channels"] == []
    assert "input" not in tracks.get_routing_options(ctx, "master")


# --- buses ----------------------------------------------------------------------------------------


def test_create_bus_validates_then_creates(ctx, song):
    assert error_of(tracks.create_bus, ctx, "Bass", ["Keys"]).code == "invalid_argument"  # name taken
    assert error_of(tracks.create_bus, ctx, "Bus", ["1-MIDI"]).code == "invalid_argument"  # no audio output
    assert error_of(tracks.create_bus, ctx, "Bus", ["Bass", "bass"]).code == "invalid_argument"  # listed twice
    assert error_of(tracks.create_bus, ctx, "Bus", ["master"]).code == "invalid_argument"
    assert error_of(tracks.create_bus, ctx, "Bus", []).code == "invalid_argument"
    assert error_of(tracks.create_bus, ctx, "Bus", ["Nope"]).code == "not_found"
    assert len(song.tracks) == 3
    out = tracks.create_bus(ctx, "Bus", ["Bass", 2], color=5)
    assert out["bus"]["name"] == "Bus" and out["bus"]["monitoring"] == "in" and song.tracks[3].color_index == 5
    assert [source["ref"] for source in out["sources"]] == ["Bass", "Keys"]


def test_route_to_bus_is_busy_until_live_offers_the_bus(ctx, song):
    tracks.create_bus(ctx, "Bus", ["Bass"])
    error = error_of(tracks.tracks_route_to_bus, ctx, "Bus", ["Bass"])
    assert error.code == "busy" and error.hint == "not ready yet"
    bus = song.tracks[3]
    song.tracks[1].available_output_routing_types.insert(2, Routing("Bus", bus))  # Live's next tick
    out = tracks.tracks_route_to_bus(ctx, "Bus", ["Bass"])
    assert out["sources"][0]["output"]["type"] == "Bus"
    assert out["bus"]["input"]["type"] == "No Input" and out["bus"]["monitoring"] == "in"


def test_route_to_bus_rejects_bad_targets(ctx, song):
    assert error_of(tracks.tracks_route_to_bus, ctx, "1-MIDI", ["Bass"]).code == "invalid_argument"
    assert error_of(tracks.tracks_route_to_bus, ctx, "Keys", ["Keys"]).code == "invalid_argument"
