"""Unit tests for WS-A's Remote Script handlers (handlers/status.py, handlers/song.py) against fakes of Live.

The fake Song applies playhead and start-marker writes on the next tick(), as Live 12.4.6 does
(docs/spikes.md), so the two-phase locator and play-from-position protocols are exercised for real.
"""
import json

import pytest

from AbletonMCP_Remote_Script import core
from AbletonMCP_Remote_Script.errors import CommandError

core.load_handlers()  # the full registry, so this module never leaves a partial one for other tests
from AbletonMCP_Remote_Script.handlers import song as song_handlers  # noqa: E402
from AbletonMCP_Remote_Script.handlers import status as status_handlers  # noqa: E402

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class Obj(object):
    def __init__(self, **attributes):
        self.__dict__.update(attributes)


class Param(Obj):
    def __init__(self, value=0.85, display=0.0):
        Obj.__init__(self, value=value, min=0.0, max=1.0, display_value=display, name="Volume")

    def str_for_value(self, value):
        return "{0:.1f} dB".format(self.display_value)


class Clip(Obj):
    def __init__(self, name="Clip", length=4.0, start=0.0, end=4.0, audio=False):
        Obj.__init__(self, name=name, length=length, start_time=start, end_time=end, is_audio_clip=audio, is_midi_clip=not audio,
                     warping=True, is_playing=False, is_triggered=False, looping=True, muted=False, color=0xFF0000, color_index=1)


class Slot(Obj):
    def __init__(self, clip=None):
        Obj.__init__(self, clip=clip, has_clip=clip is not None)


class Device(Obj):
    def __init__(self, name):
        Obj.__init__(self, name=name, class_display_name=name, class_name=name, is_active=True)


class Track(Obj):
    def __init__(self, name, midi=True, slots=8, clips=0, arrangement=0, devices=("Operator",)):
        mixer = Obj(volume=Param(), panning=Obj(value=0.0), sends=[Param(), Param()])
        Obj.__init__(
            self, name=name, has_midi_input=midi, is_foldable=False, is_grouped=False, group_track=None, mute=False, solo=False,
            arm=False, can_be_armed=True, color=0x3DC300, color_index=12, is_frozen=False, mixer_device=mixer,
            devices=[Device(device) for device in devices],
            clip_slots=[Slot(Clip("Clip {0}".format(index), 16.0) if index < clips else None) for index in range(slots)],
            arrangement_clips=[Clip("Arr {0}".format(index), 16.0, 16.0 * index, 16.0 * (index + 1)) for index in range(arrangement)],
        )


class Scene(Obj):
    def __init__(self, name=""):
        Obj.__init__(self, name=name, is_empty=True, tempo=-1.0, tempo_enabled=False, time_signature_numerator=-1,
                     time_signature_denominator=-1, time_signature_enabled=False, color=0, color_index=0, is_triggered=False, fired=None)

    def fire(self, force_legato=False):
        self.fired = force_legato


class Cue(Obj):
    def __init__(self, time, name):
        Obj.__init__(self, time=time, name=name, jumped=False)

    def jump(self):
        self.jumped = True


class Groove(Obj):
    def __init__(self, name):
        Obj.__init__(self, name=name, base=3, quantization_amount=0.0, timing_amount=100.0, random_amount=0.0, velocity_amount=0.0)


class Song(object):
    """A Live Song whose current_song_time and start_time writes apply on the next tick()."""

    def __init__(self, tracks=None, scenes=4):
        self.tempo, self.signature_numerator, self.signature_denominator = 120.0, 4, 4
        self.root_note, self.scale_name, self.scale_mode = 0, "Major", True
        self.swing_amount, self.groove_amount = 0.0, 0.0
        self.metronome = self.loop = self.punch_in = self.punch_out = False
        self.loop_start, self.loop_length = 0.0, 16.0
        self.clip_trigger_quantization, self.midi_recording_quantization = 4, 0
        self.record_mode = self.session_record = self.arrangement_overdub = self.session_automation_record = False
        self.is_ableton_link_enabled = self.tempo_follower_enabled = False
        self.view = Obj(follow_song=True, selected_track=None, selected_scene=None, highlighted_clip_slot=None, detail_clip=None)
        self.tracks = tracks if tracks is not None else [Track("Drums"), Track("Bass")]
        self.return_tracks = [Track("A-Reverb", midi=False, slots=0, devices=("Reverb",))]
        for item in self.return_tracks:
            item.can_be_armed = False
            item.clip_slots = []
            item.arrangement_clips = []
        self.master_track = Track("Main", midi=False, slots=0, devices=())
        self.master_track.can_be_armed = False
        self.master_track.clip_slots = []
        self.master_track.arrangement_clips = []
        self.scenes = [Scene() for _ in range(scenes)]
        self.cue_points = []
        self.groove_pool = Obj(grooves=[Groove("Swing 16ths 66")])
        self.is_playing = False
        self.last_event_time, self.song_length = 64.0, 200.0
        self.can_jump_to_next_cue = self.can_jump_to_prev_cue = False
        self.can_capture_midi = False
        self.back_to_arranger = False
        self.history = []
        self.redo_stack = []
        self.calls = []
        self._time = 0.0
        self._start = 0.0
        self._pending = {}

    # deferred transport state, like Live
    @property
    def current_song_time(self):
        return self._time

    @current_song_time.setter
    def current_song_time(self, value):
        if value > self.song_length:
            raise RuntimeError("Cannot set the Songtime behind the Songlength")
        self._pending["_time"] = float(value)

    @property
    def start_time(self):
        return self._start

    @start_time.setter
    def start_time(self, value):
        self._pending["_start"] = float(value)

    def tick(self):
        for name, value in self._pending.items():
            setattr(self, name, value)
        self._pending = {}

    @property
    def can_undo(self):
        return bool(self.history)

    @property
    def can_redo(self):
        return bool(self.redo_stack)

    def undo(self):
        self.redo_stack.append(self.history.pop())
        return "Undo Custom Action"

    def redo(self):
        self.history.append(self.redo_stack.pop())
        return "Redo Custom Action"

    def _snapped(self):
        return round(self._time * 4) / 4.0

    def is_cue_point_selected(self):
        return any(abs(cue.time - self._snapped()) < 1e-9 for cue in self.cue_points)

    def set_or_delete_cue(self):
        existing = [cue for cue in self.cue_points if abs(cue.time - self._snapped()) < 1e-9]
        if existing:
            self.cue_points.remove(existing[0])
        else:
            self.cue_points.append(Cue(self._snapped(), str(len(self.cue_points) + 1)))

    def create_scene(self, index):
        scene = Scene()
        self.scenes.insert(len(self.scenes) if index == -1 else index, scene)
        return scene

    def delete_scene(self, index):
        del self.scenes[index]

    def duplicate_scene(self, index):
        copy = Scene(self.scenes[index].name)
        self.scenes.insert(index + 1, copy)

    def capture_and_insert_scene(self):
        self.scenes.append(Scene())

    def __getattr__(self, name):
        if name in ("start_playing", "stop_playing", "continue_playing", "play_selection", "stop_all_clips", "tap_tempo",
                    "capture_midi", "jump_to_next_cue", "jump_to_prev_cue"):
            return lambda *args: self.calls.append(name)
        raise AttributeError(name)


class App(object):
    def __init__(self, dialog=None, buttons=0):
        self.open_dialog_count = 1 if dialog else 0
        self.current_dialog_message = dialog or ""
        self.current_dialog_button_count = buttons
        self.average_process_usage = 0.25
        self.pressed = []
        self.view = Obj(focused_document_view="Session", focused=None)
        self.view.available_main_views = lambda: ["Browser", "Arranger", "Session", "Detail", "Detail/Clip", "Detail/DeviceChain"]
        self.view.is_view_visible = lambda name: name in ("Session", "Detail")
        self.view.focus_view = lambda name: setattr(self.view, "focused", name)

    def get_version_string(self):
        return "12.4.6"

    def press_current_dialog_button(self, index):
        self.pressed.append(index)


class Ctx(object):
    def __init__(self, song=None, app=None, state=None):
        self.song = song or Song()
        self.app = app or App()
        self.state = state if state is not None else {}
        self.messages = []
        self.cs = Obj(core_report={"failed": {}})

    def show_message(self, text):
        self.messages.append(text)


def run_until_done(handler, ctx, attempts=5, **params):
    """What MCP_Server.tools.song.until_done does, with a Live tick between calls."""
    result = handler(ctx, **params)
    for _ in range(attempts):
        if not (isinstance(result, dict) and result.get("pending")):
            return result
        if "restore" in result:
            params["restore"] = result["restore"]
        ctx.song.tick()
        result = handler(ctx, **params)
    raise AssertionError("still pending: {0}".format(result))


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [("3/4", (3, 4)), (" 7 / 8 ", (7, 8)), ([6, 8], (6, 8)), ("99/16", (99, 16)), ("1/1", (1, 1))])
def test_parse_signature(text, expected):
    assert song_handlers.parse_signature(text) == expected


@pytest.mark.parametrize("bad", ["3/5", "0/4", "100/4", "3:4", "four/four", 3, None, [3]])
def test_parse_signature_rejects(bad):
    with pytest.raises(CommandError):
        song_handlers.parse_signature(bad)


def test_split_key_and_flags():
    assert song_handlers.split_key("A minor") == ("A", "minor")
    assert song_handlers.split_key("F# Harmonic Minor") == ("F#", "Harmonic Minor")
    assert song_handlers.split_key("Bb") == ("Bb", None)
    assert song_handlers.split_key(9) == (9, None)
    assert song_handlers.parse_flag(1, "x") is True and song_handlers.parse_flag("off", "x") is False
    with pytest.raises(CommandError):
        song_handlers.parse_flag("maybe", "x")
    assert song_handlers.is_off("off") and song_handlers.is_off(False) and not song_handlers.is_off(120)


def test_resolve_scale_is_case_insensitive_and_lists_options():
    scales = ["Major", "Minor", "Dorian", "Harmonic Minor"]
    assert song_handlers.resolve_scale("harmonic minor", scales) == "Harmonic Minor"
    with pytest.raises(CommandError) as error:
        song_handlers.resolve_scale("Blues-ish", scales)
    assert error.value.code == "not_found" and "Dorian" in error.value.message


def test_loop_region():
    meter = song_handlers._Meter(3, 4)
    assert song_handlers.loop_region(meter, 0.0, 16.0, loop_start="2.1.1", loop_length="2 bars") == (3.0, 6.0)
    assert song_handlers.loop_region(meter, 4.0, 8.0, loop_end=10) == (4.0, 6.0)
    assert song_handlers.loop_region(meter, 4.0, 8.0, loop_start=12) == (12.0, 8.0)
    assert song_handlers.loop_region(meter, 4.0, 8.0) is None
    with pytest.raises(CommandError):
        song_handlers.loop_region(meter, 0.0, 4.0, loop_length=4, loop_end=8)
    with pytest.raises(CommandError):
        song_handlers.loop_region(meter, 8.0, 4.0, loop_end=8)


# ---------------------------------------------------------------------------
# set_song
# ---------------------------------------------------------------------------


@pytest.fixture
def scales(monkeypatch):
    monkeypatch.setattr(song_handlers, "scale_names", lambda: ["Major", "Minor", "Dorian"])


def test_set_song_applies_and_reports_every_setting(scales):
    ctx = Ctx()
    state = song_handlers.set_song(ctx, tempo=97.5, time_signature="3/4", key="D dorian", swing=0.2, groove_amount=1.3,
                                   loop=True, loop_start="2.1.1", loop_end="4.1.1", launch_quantization="1/4",
                                   record_quantization="1/16", follow=False, punch_in=True, link=True)
    song = ctx.song
    assert (song.tempo, song.signature_numerator, song.signature_denominator, song.root_note, song.scale_name) == (97.5, 3, 4, 2, "Dorian")
    assert (song.loop_start, song.loop_length) == (3.0, 6.0)  # bar notation in the new 3/4 meter
    assert song.clip_trigger_quantization == 7 and song.midi_recording_quantization == 5 and song.view.follow_song is False
    assert song.is_ableton_link_enabled is True
    assert state["key"] == "D" and state["scale"] == "Dorian" and state["time_signature"] == "3/4"
    assert state["launch_quantization"] == "1/4" and state["record_quantization"] == "1/16"
    assert state["loop_end"] == {"beats": 9.0, "bar": "4.1.1"} and state["punch_in"] is True


def test_set_song_without_arguments_reads(scales):
    ctx = Ctx()
    state = song_handlers.set_song(ctx)
    assert state["tempo"] == 120.0 and state["scale"] == "Major" and "warnings" not in state


@pytest.mark.parametrize("arguments", [
    {"tempo": 1000}, {"tempo": "fast"}, {"swing": 1.5}, {"groove_amount": 1.4}, {"scale": "Bogus"},
    {"key": "H"}, {"key": "A minor", "scale": "Dorian"}, {"launch_quantization": "1/3"}, {"metronome": "loud"},
    {"loop_length": 4, "loop_end": 8},
])
def test_set_song_validates_everything_before_changing_anything(scales, arguments):
    ctx = Ctx()
    with pytest.raises(CommandError):
        song_handlers.set_song(ctx, time_signature="7/8", **arguments)
    assert ctx.song.signature_numerator == 4  # the valid time signature was not applied either


# ---------------------------------------------------------------------------
# Status, overview, history, dialogs
# ---------------------------------------------------------------------------


def test_get_status_reports_set_transport_dialog_and_jobs():
    ctx = Ctx(app=App("Save changes to \"Untitled\" before closing?", 3), state={"jobs": {"b1": {"kind": "bounce", "status": "recording", "progress": 0.5}}})
    ctx.song.file_path = "/x/Song.als"
    ctx.song.name = "Song"
    out = status_handlers.get_status(ctx)
    assert out["set"] == {"name": "Song", "path": "/x/Song.als", "saved": True, "document": out["set"]["document"]}
    assert out["dialog"] == {"open": 1, "message": "Save changes to \"Untitled\" before closing?", "buttons": 3}
    assert out["transport"]["time_signature"] == "4/4" and out["transport"]["loop"]["end"]["beats"] == 16.0
    assert out["jobs"] == [{"id": "b1", "kind": "bounce", "status": "recording", "progress": 0.5}]
    json.dumps(out)


def test_active_jobs_conventions():
    state = {"jobs": {"a": {"status": "done"}, "b": {"status": "rendering"}}, "bounce": {"status": "recording", "id": "j7"}, "other": 3, "idle": {"status": "idle"}}
    ids = sorted(job["id"] for job in status_handlers.active_jobs(state))
    assert ids == ["b", "j7"]
    assert status_handlers.active_jobs(None) == []


def big_song(tracks=30, clips=8):
    song = Song(tracks=[Track("Track {0} with a long name".format(index), clips=clips, arrangement=4, devices=("Operator", "EQ Eight", "Compressor"))
                        for index in range(tracks)], scenes=8)
    song.cue_points = [Cue(16.0 * index, "Section {0}".format(index)) for index in range(6)]
    return song


def test_overview_shape_and_compactness():
    ctx = Ctx(song=big_song())
    out = status_handlers.get_song_overview(ctx)
    text = json.dumps(out, separators=(",", ":"))
    assert len(text) < 24000, len(text)  # 30 tracks x 8 clips: about 19 KB (~5k tokens)
    first = out["tracks"][0]
    assert first["track"] == 0 and first["kind"] == "midi" and first["devices"] == ["Operator", "EQ Eight", "Compressor"]
    assert first["clips"][0] == {"slot": 0, "name": "Clip 0", "length": 16.0}
    assert first["arrangement"]["clips"] == 4 and first["arrangement"]["end"] == {"beats": 64.0, "bar": "17.1.1"}
    assert out["returns"][0]["track"] == "return:A" and "clips" not in out["returns"][0] and "arm" not in out["returns"][0]
    assert out["master"]["kind"] == "master" and "mute" not in out["master"]
    assert out["scenes"][0] == {"scene": 0, "name": "", "empty": True}
    assert [cue["locator"] for cue in out["locators"]] == list(range(6))
    assert out["song"]["length"] == {"beats": 64.0, "bar": "17.1.1"} and "state" not in out["song"]


def test_overview_without_clips_is_small_and_detail_adds_mixer():
    ctx = Ctx(song=big_song(clips=0))
    compact = json.dumps(status_handlers.get_song_overview(ctx), separators=(",", ":"))
    assert len(compact) < 12000, len(compact)  # about 9 KB
    detail = status_handlers.get_song_overview(ctx, detail=True)
    track = detail["tracks"][0]
    assert track["volume_db"] == 0.0 and track["pan"] == 0.0 and track["sends_db"] == {"A": 0.0, "B": 0.0}
    assert track["devices"][0] == {"name": "Operator", "class": "Operator", "on": True}
    assert len(track["arrangement"]["items"]) == 4 and detail["song"]["state"]["launch_quantization"] == "1 bar"


def test_unwarped_audio_clip_reports_seconds():
    track = Track("Audio", midi=False)
    track.clip_slots[0] = Slot(Clip("Loop", 2.5, audio=True))
    track.clip_slots[0].clip.warping = False
    out = status_handlers.track_overview(Song(tracks=[track]), track)
    assert out["clips"] == [{"slot": 0, "name": "Loop", "length_seconds": 2.5}]


def test_undo_and_redo_count_steps():
    ctx = Ctx()
    ctx.song.history = ["a", "b", "c"]
    assert status_handlers.undo(ctx, steps=2) == {"undone": 2, "can_undo": True, "can_redo": True}
    assert status_handlers.undo(ctx, steps=5)["undone"] == 1
    with pytest.raises(CommandError):
        status_handlers.undo(ctx)
    assert status_handlers.redo(ctx, steps=3) == {"redone": 3, "can_undo": True, "can_redo": False}
    for bad in (0, 101, True, 1.5):
        with pytest.raises(CommandError):
            status_handlers.undo(Ctx(), steps=bad)


def test_dialog_button_names():
    prompt = 'Save changes to "Untitled" before closing?'
    index = status_handlers.dialog_button_index
    assert index(1, prompt, 3) == 1 and index("2", prompt, 3) == 2
    assert index("save", prompt, 3) == 0 and index("dont_save", prompt, 3) == 1 and index("Don't Save", prompt, 3) == 1
    assert index("cancel", prompt, 3) == 2 and index("OK", "Missing samples", 1) == 0
    for bad, message, count in ((3, prompt, 3), ("cancel", "Something else", 2), ("save", "Something else", 3), (True, prompt, 3)):
        with pytest.raises(CommandError):
            index(bad, message, count)


def test_respond_to_dialog():
    with pytest.raises(CommandError) as error:
        status_handlers.respond_to_dialog(Ctx(), button=0)
    assert error.value.code == "not_found"
    app = App('Save changes to "Untitled" before closing?', 3)
    out = status_handlers.respond_to_dialog(Ctx(app=app), button="dont_save")
    assert app.pressed == [1] and out["pressed"] == 1


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def test_transport_actions_and_aliases():
    assert song_handlers.transport_action("Jump To Next Locator") == "jump_to_next_locator"
    assert song_handlers.transport_action("prev_locator") == "jump_to_prev_locator"
    with pytest.raises(CommandError):
        song_handlers.transport_action("dance")
    ctx = Ctx()
    for action in ("continue", "stop", "play_selection", "stop_all_clips", "tap_tempo"):
        assert song_handlers.transport(ctx, action=action) == {"action": action}
    assert ctx.song.calls == ["continue_playing", "stop_playing", "play_selection", "stop_all_clips", "tap_tempo"]
    song_handlers.transport(ctx, action="back_to_arrangement")
    assert ctx.song.back_to_arranger is False


def test_play_from_position_moves_the_start_marker_then_plays():
    ctx = Ctx()
    out = run_until_done(song_handlers.transport, ctx, action="play", position="5.1.1")
    assert out == {"action": "play", "position": {"beats": 16.0, "bar": "5.1.1"}}
    assert ctx.song.start_time == 16.0 and ctx.song.calls == ["start_playing"]


def test_play_while_playing_jumps_and_jump_while_stopped_moves_the_marker():
    ctx = Ctx()
    ctx.song.is_playing = True
    song_handlers.transport(ctx, action="play", position=8)
    ctx.song.tick()
    assert ctx.song.current_song_time == 8.0 and ctx.song.calls == []
    ctx.song.is_playing = False
    song_handlers.transport(ctx, action="jump", position="3.1.1")
    ctx.song.tick()
    assert ctx.song.start_time == 8.0 and ctx.song.current_song_time == 8.0
    with pytest.raises(CommandError):
        song_handlers.transport(ctx, action="jump")


def test_jump_to_a_locator_by_name_while_playing():
    ctx = Ctx()
    cue = Cue(32.0, "Chorus")
    ctx.song.cue_points = [cue]
    ctx.song.is_playing = True
    out = song_handlers.transport(ctx, action="jump", position="chorus")
    assert out["locator"] == "Chorus" and cue.jumped


def test_next_locator_error_lists_locators():
    ctx = Ctx()
    ctx.song.cue_points = [Cue(8.0, "Verse")]
    with pytest.raises(CommandError) as error:
        song_handlers.transport(ctx, action="jump_to_next_locator")
    assert "Verse (3.1.1)" in error.value.message
    ctx.song.can_jump_to_next_cue = True
    song_handlers.transport(ctx, action="jump_to_next_locator")
    assert ctx.song.calls == ["jump_to_next_cue"]


def test_capture_midi_and_scene():
    ctx = Ctx()
    with pytest.raises(CommandError) as error:
        song_handlers.transport(ctx, action="capture_midi")
    assert error.value.code == "unsupported"
    out = song_handlers.transport(ctx, action="capture_scene")
    assert out["scene"]["scene"] == 4


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------


def test_scene_lifecycle():
    ctx = Ctx()
    created = song_handlers.create_scene(ctx, index=1, name="Chorus", color=5, tempo=128, time_signature="7/8")
    assert created["scene"] == 1 and created["tempo"] == 128.0 and created["time_signature"] == "7/8"
    scene = ctx.song.scenes[1]
    assert scene.tempo_enabled and scene.time_signature_enabled and scene.color_index == 5
    out = song_handlers.set_scene(ctx, scene="chorus", tempo="off", time_signature="off", color="#00FF00")
    assert "tempo" not in out and "time_signature" not in out and scene.color == 0x00FF00
    assert song_handlers.fire_scene(ctx, scene=1, force_legato=True)["fired"] and scene.fired is True
    duplicate = song_handlers.duplicate_scene(ctx, scene="Chorus")
    assert duplicate["scene"] == 2 and duplicate["source"] == 1
    deleted = song_handlers.delete_scene(ctx, scene=2)
    assert deleted == {"deleted": {"scene": 2, "name": "Chorus"}, "scenes": 5}


def test_scene_errors():
    ctx = Ctx(song=Song(scenes=1))
    with pytest.raises(CommandError):
        song_handlers.delete_scene(ctx, scene=0)
    for arguments in ({"index": 5}, {"index": True}, {"tempo": 5}, {"time_signature": "3/3"}):
        with pytest.raises(CommandError):
            song_handlers.create_scene(ctx, **arguments)
    assert len(ctx.song.scenes) == 1
    with pytest.raises(CommandError):
        song_handlers.set_scene(ctx, scene=0)
    with pytest.raises(CommandError) as error:
        song_handlers.fire_scene(ctx, scene="Nope")
    assert error.value.code == "not_found"


# ---------------------------------------------------------------------------
# Locators (two-phase)
# ---------------------------------------------------------------------------


def test_create_locator_two_phase_restores_the_playhead():
    ctx = Ctx()
    ctx.song._time = 2.0
    first = song_handlers.create_locator(ctx, time="5.1.1", name="Chorus")
    assert first == {"pending": "playhead", "restore": 2.0}
    out = run_until_done(song_handlers.create_locator, ctx, time="5.1.1", name="Chorus")
    assert out == {"locator": 0, "name": "Chorus", "time": {"beats": 16.0, "bar": "5.1.1"}}
    ctx.song.tick()
    assert ctx.song.current_song_time == 2.0


def test_create_locator_reports_grid_snapping():
    ctx = Ctx()
    out = run_until_done(song_handlers.create_locator, ctx, time=33.4)
    assert out["time"]["beats"] == 33.5 and out["requested"]["beats"] == 33.4


def test_create_locator_never_deletes_an_existing_cue():
    ctx = Ctx()
    ctx.song.cue_points = [Cue(16.0, "Chorus")]
    with pytest.raises(CommandError):
        run_until_done(song_handlers.create_locator, ctx, time=16)
    with pytest.raises(CommandError):
        run_until_done(song_handlers.create_locator, ctx, time=15.9)  # snaps onto the existing cue
    assert [cue.name for cue in ctx.song.cue_points] == ["Chorus"]


def test_locator_guards():
    ctx = Ctx()
    ctx.song.is_playing = True
    with pytest.raises(CommandError) as error:
        song_handlers.create_locator(ctx, time=4)
    assert error.value.code == "busy"
    ctx.song.is_playing = False
    with pytest.raises(CommandError):
        song_handlers.create_locator(ctx, time=500)  # beyond the song length
    with pytest.raises(CommandError):
        song_handlers.create_locator(ctx, time=-1)


def test_rename_and_delete_locator():
    ctx = Ctx()
    ctx.song.cue_points = [Cue(32.0, "B"), Cue(8.0, "A")]
    ctx.song._time = 1.0
    assert song_handlers.set_locator(ctx, locator=1, name="Bridge") == {"locator": 1, "name": "Bridge", "time": {"beats": 32.0, "bar": "9.1.1"}}
    out = run_until_done(song_handlers.delete_locator, ctx, locator="A")
    assert out == {"deleted": {"locator": 0, "name": "A", "time": {"beats": 8.0, "bar": "3.1.1"}}, "locators": 1}
    ctx.song.tick()
    assert [cue.name for cue in ctx.song.cue_points] == ["Bridge"] and ctx.song.current_song_time == 1.0


# ---------------------------------------------------------------------------
# Grooves, selection, messages
# ---------------------------------------------------------------------------


def test_grooves():
    ctx = Ctx()
    assert song_handlers.get_grooves(ctx)["grooves"][0] == {"groove": 0, "name": "Swing 16ths 66", "base": "1/16", "quantize": 0.0, "timing": 100.0, "random": 0.0, "velocity": 0.0}
    out = song_handlers.set_groove(ctx, groove="swing", base="1/8T", quantize=50, velocity=-20, name="Shuffle")
    assert out["base"] == "1/8T" and out["quantize"] == 50.0 and out["velocity"] == -20.0 and out["name"] == "Shuffle"
    for arguments in ({"timing": 101}, {"velocity": -101}, {"base": "1/5"}, {}):
        with pytest.raises(CommandError):
            song_handlers.set_groove(ctx, groove=0, **arguments)


def test_view_names():
    assert song_handlers.view_name("arrangement") == "Arranger"
    assert song_handlers.view_name("Devices") == "Detail/DeviceChain"
    assert song_handlers.view_name("detail/clip", ["Detail/Clip"]) == "Detail/Clip"
    with pytest.raises(CommandError):
        song_handlers.view_name("Mixer")


def test_select_and_read_back():
    ctx = Ctx()
    out = song_handlers.select(ctx, track="Bass", scene=2, view="arrangement")
    assert ctx.song.view.selected_track is ctx.song.tracks[1] and ctx.song.view.selected_scene is ctx.song.scenes[2]
    assert ctx.app.view.focused == "Arranger" and out["track"] == {"track": 1, "name": "Bass", "kind": "midi"}
    assert out["scene"] == {"scene": 2, "name": ""} and out["visible_views"] == ["Session", "Detail"]
    for arguments in ({"slot": 0}, {"device": 0}, {"track": 0, "slot": 0, "scene": 1}, {"view": "Mixer"}):
        with pytest.raises(CommandError):
            song_handlers.select(ctx, **arguments)


def test_show_message():
    ctx = Ctx()
    assert song_handlers.show_message(ctx, text="Hello") == {"shown": "Hello"} and ctx.messages == ["Hello"]


def test_registered_commands():
    mine = ["get_status", "get_song_overview", "undo", "redo", "respond_to_dialog", "set_song", "transport", "create_scene",
            "set_scene", "fire_scene", "delete_scene", "duplicate_scene", "create_locator", "set_locator", "delete_locator",
            "get_grooves", "set_groove", "select", "show_message"]
    for name in mine:
        assert name in core.COMMANDS, name
    assert not core.COMMANDS["undo"].undo and not core.COMMANDS["redo"].undo and not core.COMMANDS["select"].undo
    assert core.COMMANDS["get_song_overview"].readonly and core.COMMANDS["set_song"].undo
