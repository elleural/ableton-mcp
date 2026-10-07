"""WS-E: the Remote Script bounce engine against a fake Live, tick by tick (offline).

The fake reproduces what the spikes found: routing lists are empty in the tick a track is created,
armed tracks record when the transport plays in record mode, and recorded clips start with a
pre-roll (their start_marker).
"""
import itertools

import pytest

from AbletonMCP_Remote_Script.errors import CommandError
from AbletonMCP_Remote_Script.handlers import bounce

_POINTERS = itertools.count(1000)
CHANNELS = {0: ["1/2", "1", "2"], 2: [""], 3: ["Pre FX", "Post FX", "Post Mixer"], 4: ["Pre FX", "Post FX", "Post Mixer"], 6: [""]}


class RoutingType(object):
    def __init__(self, display_name, category, attached_object=None):
        self.display_name, self.category, self.attached_object = display_name, category, attached_object


class Channel(object):
    def __init__(self, display_name):
        self.display_name = display_name


class Clip(object):
    def __init__(self, start, end, preroll, tempo, path, rate=44100.0, warping=True):
        self.start_time, self.end_time, self.start_marker = start, end, preroll
        self.warping, self.sample_rate, self.file_path, self.is_audio_clip = warping, rate, path, True
        self._tempo = tempo
        self.sample_length = int(round((end - start + preroll) * 60.0 / tempo * rate))

    def beat_to_sample_time(self, beat):
        return beat * 60.0 / self._tempo * self.sample_rate


class Track(object):
    def __init__(self, song, name, midi=False, audio_out=True, armable=True):
        self._song, self._live_ptr = song, next(_POINTERS)
        self.name, self.arm, self.can_be_armed = name, False, armable
        self.has_midi_input, self.has_audio_output, self.is_foldable = midi, audio_out, False
        self.mute = self.solo = False
        self.arrangement_clips = []
        self.current_monitoring_state = 1
        self._ready, self._input, self._channels = True, None, []
        self.input_routing_channel = None

    @property
    def available_input_routing_types(self):
        return self._song.routing_types(self) if self._ready else [RoutingType("", 7)]

    @property
    def input_routing_type(self):
        return self._input

    @input_routing_type.setter
    def input_routing_type(self, value):
        self._input = value
        self._channels = [Channel(name) for name in CHANNELS[value.category]]
        self.input_routing_channel = self._channels[0]

    @property
    def available_input_routing_channels(self):
        return list(self._channels)


class View(object):
    selected_track = None


class Cue(object):
    def __init__(self, name, time):
        self.name, self.time = name, time


class Song(object):
    def __init__(self, tempo=120.0):
        self._live_ptr = next(_POINTERS)
        self.tempo, self.signature_numerator, self.signature_denominator = tempo, 4, 4
        self.loop, self.metronome, self.record_mode, self.punch_in, self.punch_out = True, True, False, True, False
        self.arrangement_overdub = self.overdub = self.session_record = False
        self.session_automation_record = self.back_to_arranger = True
        self.start_time, self.current_song_time = 0.0, 11.5
        self.is_playing = self.is_counting_in = False
        self.count_in_duration, self.last_event_time, self.re_enable_automation_enabled = 0, 30.0, False
        self.root_note, self.scale_name, self.name, self.file_path = 9, "Minor", "Demo", ""
        self.cue_points = [Cue("Verse", 4.0), Cue("Chorus", 12.0)]
        self.view = View()
        self.master_track = Track(self, "Main", armable=False)
        self.tracks, self.return_tracks = [], []
        self.undo_depth, self.stopped_clips, self.preroll_beats = 0, 0, 0.4
        self._recording_from = None

    def routing_types(self, owner):
        types = [RoutingType("Ext. In", 0), RoutingType("Resampling", 2)]
        types += [RoutingType(track.name, 4, track) for track in self.tracks + self.return_tracks if track is not owner and track.has_audio_output]
        return types + [RoutingType("Main", 3, self.master_track), RoutingType("No Input", 6)]

    def create_audio_track(self, index):
        track = Track(self, "Audio")
        track._ready = False  # Live fills the routing lists on the next tick
        self.tracks.append(track) if index == -1 else self.tracks.insert(index, track)
        self.view.selected_track = track
        return track

    def delete_track(self, index):
        del self.tracks[index]

    def stop_all_clips(self, quantized=True):
        self.stopped_clips += 1

    def begin_undo_step(self):
        self.undo_depth += 1

    def end_undo_step(self):
        self.undo_depth -= 1

    def start_playing(self):
        self.is_playing, self.current_song_time = True, self.start_time
        self._recording_from = self.start_time if self.record_mode else None

    def stop_playing(self):
        if self.is_playing and self._recording_from is not None:
            for track in self.tracks:
                if track.arm and not track.has_midi_input:
                    path = "/Recorded/{0}.wav".format(track.name)
                    track.arrangement_clips.append(Clip(self._recording_from, self.current_song_time, self.preroll_beats, self.tempo, path))
        self.is_playing, self._recording_from = False, None

    def end_of_tick(self, seconds):
        for track in self.tracks:
            track._ready = True
        if self.is_playing:
            self.current_song_time += seconds * self.tempo / 60.0


class App(object):
    average_process_usage = 5.0


class Ctx(object):
    def __init__(self, song):
        self.song, self.app, self.state, self.logs = song, App(), {}, []

    def log(self, message):
        self.logs.append(message)

    def show_message(self, message):
        pass


class Clock(object):
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def live(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(bounce, "_now", clock)
    song = Song()
    drums = Track(song, "Drums")
    synth = Track(song, "Synth", midi=True)
    synth.arm = True  # Live auto-arms new MIDI tracks: it must be disarmed, then re-armed
    empty = Track(song, "Empty MIDI", midi=True, audio_out=False)
    song.tracks = [drums, synth, empty]
    song.return_tracks = [Track(song, "A-Reverb", armable=False)]
    song.view.selected_track = synth
    ctx = Ctx(song)

    def step(count=1, seconds=0.1):
        """One display tick: tasks already ran, then tickers, then Live advances."""
        for _ in range(count):
            bounce.bounce_tick(ctx)
            clock.now += seconds
            song.end_of_tick(seconds)

    def run_until(*phases, limit=400):
        for _ in range(limit):
            if ctx.state["bounce"]["phase"] in phases:
                return ctx.state["bounce"]
            step()
        raise AssertionError("never reached {0}; phase {1}".format(phases, ctx.state["bounce"]["phase"]))

    ctx.step, ctx.run_until = step, run_until
    return ctx


def names(song):
    return [track.name for track in song.tracks]


def assert_restored(song):
    assert (song.loop, song.metronome, song.punch_in, song.punch_out) == (True, True, True, False)
    assert song.session_automation_record and not song.record_mode
    assert not song.back_to_arranger  # returned to the arrangement; the API cannot re-light it
    assert song.current_song_time == pytest.approx(11.5) and song.start_time == pytest.approx(0.0)
    arms = dict((track.name, track.arm) for track in song.tracks)
    assert arms["Synth"] is True and arms["Drums"] is False and arms["Empty MIDI"] is False


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_round_up_to_bar():
    assert bounce.round_up_to_bar(0.0, 4.0) == 0.0
    assert bounce.round_up_to_bar(13.0, 4.0) == 16.0
    assert bounce.round_up_to_bar(16.0, 4.0) == 16.0
    assert bounce.round_up_to_bar(16.0000000001, 4.0) == 16.0
    assert bounce.round_up_to_bar(10.0, 3.0) == 12.0


def test_parse_tail_units():
    song = Song(tempo=120.0)
    assert bounce.parse_tail(song, None) == 0.0
    assert bounce.parse_tail(song, 0) == 0.0
    assert bounce.parse_tail(song, "0") == 0.0
    assert bounce.parse_tail(song, 2) == 2.0
    assert bounce.parse_tail(song, "1 bar") == 4.0
    assert bounce.parse_tail(song, "6 beats") == 6.0
    assert bounce.parse_tail(song, "2 s") == pytest.approx(4.0)
    assert bounce.parse_tail(song, "1.5 seconds") == pytest.approx(3.0)
    for bad in (-1, "soon", True):
        with pytest.raises(CommandError):
            bounce.parse_tail(song, bad)


def test_unique_labels_avoid_master_and_duplicates():
    assert bounce.unique_labels(["Synth", "Synth", "Master", "synth"]) == ["Synth", "Synth (2)", "Master (2)", "synth (3)"]


def test_sample_at_uses_the_clip_preroll():
    warped = Clip(8.0, 20.0, 0.4, 120.0, "/x.wav")
    assert bounce.sample_at(warped, 8.0, 120.0) == pytest.approx(8820.0)  # 0.4 beats of pre-roll
    assert bounce.sample_at(warped, 10.0, 120.0) == pytest.approx(8820.0 + 44100.0)
    unwarped = Clip(8.0, 20.0, 0.25, 120.0, "/x.wav", warping=False)  # markers in seconds
    assert bounce.sample_at(unwarped, 10.0, 120.0) == pytest.approx((0.25 + 1.0) * 44100.0)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def test_full_bounce_records_restores_and_cleans_up(live):
    song = live.song
    job = bounce.bounce_start(live, start="3.1.1", end="5.1.1", tail="1 s", stems=["Drums", "Synth"], name="Demo", output_dir="/out")
    assert job["phase"] == "route" and job["stems"] == ["Drums", "Synth"] and job["output_dir"] == "/out"
    assert names(song)[-3:] == ["[bounce] Master", "[bounce] Drums", "[bounce] Synth"]
    assert job["range"]["start"]["beats"] == 8.0 and job["range"]["stop_beats"] == 18.0 and job["duration_seconds"] == 5.0
    assert job["song"]["key"] == "A" and [cue["name"] for cue in job["song"]["locators"]] == ["Verse", "Chorus"]
    assert any("Back to Arrangement" in item for item in job["warnings"])
    assert "_internal" not in job and job["eta_seconds"] > 5

    live.step()  # same display tick as the command: the routing lists are still empty
    assert live.state["bounce"]["phase"] == "route"
    live.run_until("recording")
    master, drums_bounce = song.tracks[3], song.tracks[4]
    assert master.input_routing_type.display_name == "Resampling" and master.current_monitoring_state == 2
    assert drums_bounce.input_routing_type.attached_object is song.tracks[0]
    assert drums_bounce.input_routing_channel.display_name == "Post Mixer"
    assert [track.arm for track in song.tracks] == [False, False, False, True, True, True]
    assert not (song.loop or song.metronome or song.punch_in or song.session_automation_record or song.back_to_arranger)
    assert song.record_mode and song.is_playing and song.stopped_clips == 1

    done = live.run_until("recorded")
    assert done["progress"] == 1.0 and done.get("restored") is True and not done.get("error")
    assert_restored(song)
    assert not any(track.arm for track in song.tracks[3:])
    files = dict((item["stem"], item) for item in done["files"])
    assert set(files) == {"Master", "Drums", "Synth"}
    assert files["Master"]["file_path"] == "/Recorded/[bounce] Master.wav"
    assert files["Drums"]["offset_samples"] == pytest.approx(8820.0)  # the pre-roll
    assert files["Drums"]["length_samples"] == pytest.approx(5.0 * 44100.0) and files["Drums"]["duration_seconds"] == pytest.approx(5.0)
    assert files["Drums"]["recorded_seconds"] > 5.0  # pre-roll plus the stop margin
    assert files["Synth"]["source"] == "Synth" and files["Master"]["role"] == "master"
    assert song.undo_depth == 0

    with pytest.raises(CommandError) as error:
        bounce.bounce_cleanup(live, job_id="bounce-0")
    assert error.value.code == "not_found"
    cleaned = bounce.bounce_cleanup(live, job_id=job["id"], outputs={"folder": "/out"})
    assert cleaned["phase"] == "done" and cleaned["outputs"] == {"folder": "/out"}
    assert names(song) == ["Drums", "Synth", "Empty MIDI"] and song.view.selected_track is song.tracks[1]
    assert bounce.bounce_status(live)["phase"] == "done"


def test_default_end_is_the_last_event_rounded_up_to_a_bar(live):
    live.song.last_event_time = 29.0
    job = bounce.bounce_start(live)
    assert job["range"]["end"]["beats"] == 32.0 and job["range"]["start"]["beats"] == 0.0 and job["stems"] == []
    assert names(live.song)[-1] == "[bounce] Master"


def test_positions_accept_locator_names(live):
    job = bounce.bounce_start(live, start="Verse", end="Chorus")
    assert job["range"]["start"]["beats"] == 4.0 and job["range"]["end"]["beats"] == 12.0


def test_all_stems_skip_silent_tracks_and_include_returns(live):
    live.song.tracks[0].mute = True
    job = bounce.bounce_start(live, stems="all", include_returns=True)
    assert job["stems"] == ["Synth", "A-Reverb"]
    assert [item["name"] for item in job["skipped"]] == ["Drums", "Empty MIDI"]


@pytest.mark.parametrize("kwargs, code, text", [
    ({"start": 8, "end": 8}, "invalid_argument", "must be after"),
    ({"stems": ["Empty MIDI"]}, "invalid_argument", "no audio output"),
    ({"stems": ["master"]}, "invalid_argument", "always bounced"),
    ({"stems": ["Nope"]}, "not_found", "Nope"),
    ({"start": "Bridge"}, "invalid_argument", "Verse, Chorus"),
    ({"tail": -2}, "invalid_argument", "negative"),
    ({"start": 0, "end": 100000}, "invalid_argument", "limit"),
])
def test_bad_requests_are_refused_before_anything_changes(live, kwargs, code, text):
    with pytest.raises(CommandError) as error:
        bounce.bounce_start(live, **kwargs)
    assert error.value.code == code and text in error.value.message
    assert names(live.song) == ["Drums", "Synth", "Empty MIDI"] and "bounce" not in live.state


def test_refuses_while_busy_recording_or_with_leftovers(live):
    live.song.record_mode = True
    with pytest.raises(CommandError) as error:
        bounce.bounce_start(live)
    assert error.value.code == "busy"
    live.song.record_mode = False
    live.song.tracks.append(Track(live.song, "[bounce] Old"))
    with pytest.raises(CommandError) as error:
        bounce.bounce_start(live)
    assert "cancel_bounce" in error.value.hint
    assert bounce.bounce_cancel(live) == {"phase": "idle", "removed_tracks": ["[bounce] Old"]}
    bounce.bounce_start(live, end=8)
    with pytest.raises(CommandError) as error:
        bounce.bounce_start(live, end=8)
    assert error.value.code == "busy"


def test_external_stop_fails_the_job_and_restores_everything(live):
    bounce.bounce_start(live, start=0, end=8, stems=["Drums"])
    live.run_until("recording")
    live.step(5)
    live.song.stop_playing()  # someone pressed Stop
    failed = live.run_until("failed")
    assert "interrupted" in failed["error"] and failed["removed_tracks"]
    assert names(live.song) == ["Drums", "Synth", "Empty MIDI"]
    assert_restored(live.song)
    assert live.song.undo_depth == 0


def test_cancel_while_recording(live):
    bounce.bounce_start(live, start=0, end=8, stems=["Drums"])
    live.run_until("recording")
    job = bounce.bounce_cancel(live)
    assert job["phase"] == "aborting" and not live.song.is_playing and not live.song.record_mode
    cancelled = live.run_until("cancelled")
    assert cancelled.get("cancelled") and "error" not in cancelled
    assert names(live.song) == ["Drums", "Synth", "Empty MIDI"]
    assert_restored(live.song)
    with pytest.raises(CommandError):
        bounce.bounce_cleanup(live, job_id="nope")
    assert bounce.bounce_cleanup(live, job_id=cancelled["id"])["phase"] == "cancelled"


def test_cancel_before_transport_changes_leaves_the_transport_alone(live):
    bounce.bounce_start(live, start=0, end=8)
    live.song.current_song_time = 3.0  # nothing restores it: the bounce never moved it
    bounce.bounce_cancel(live)
    live.run_until("cancelled")
    assert live.song.current_song_time == 3.0 and live.song.loop and live.song.back_to_arranger
    assert names(live.song) == ["Drums", "Synth", "Empty MIDI"]


def test_cancel_after_recording_removes_tracks(live):
    bounce.bounce_start(live, start=0, end=4)
    live.run_until("recorded")
    job = bounce.bounce_cancel(live)
    assert job["phase"] == "cancelled" and names(live.song) == ["Drums", "Synth", "Empty MIDI"]


@pytest.mark.parametrize("disturb, text", [
    (lambda song: setattr(song, "current_song_time", song.current_song_time + 40), "jumped"),
    (lambda song: setattr(song, "current_song_time", 0.5), "jumped"),
    (lambda song: song.tracks.pop(), "deleted"),
    (lambda song: setattr(song.tracks[3], "arm", False), "disarmed"),
    (lambda song: setattr(song, "record_mode", False), "switched off"),
])
def test_interruptions_fail_the_job(live, disturb, text):
    bounce.bounce_start(live, start=0, end=16, stems=["Drums"])
    live.run_until("recording")
    live.step(3)
    disturb(live.song)
    failed = live.run_until("failed")
    assert text in failed["error"]
    assert not any(name.startswith("[bounce]") for name in names(live.song))
    assert_restored(live.song)


def test_a_new_set_abandons_the_job_without_touching_it(live):
    bounce.bounce_start(live, start=0, end=8)
    live.run_until("recording")
    other = Song()
    live.song = other
    live.step()
    job = live.state["bounce"]
    assert job["phase"] == "failed" and "Live Set changed" in job["error"]
    assert other.loop and other.current_song_time == 11.5


def test_transport_playing_at_start_is_stopped_and_settles(live):
    live.song.is_playing = True
    job = bounce.bounce_start(live, start=0, end=4)
    assert not live.song.is_playing and any("was playing" in item for item in job["warnings"])
    live.run_until("arm")
    live.step(5)  # 0.5 s: still settling
    assert live.state["bounce"]["phase"] == "arm"
    live.run_until("recording")


def test_count_in_is_reported_and_waited_for(live, monkeypatch):
    song = live.song
    song.count_in_duration = 1
    job = bounce.bounce_start(live, start=0, end=4)
    assert any("Count-in" in item for item in job["warnings"])
    original = song.start_playing

    def counting():
        song.is_counting_in = True

    monkeypatch.setattr(song, "start_playing", counting)
    live.run_until("starting")
    live.step(15)  # 1.5 s of count-in: no timeout, still starting
    assert live.state["bounce"]["phase"] == "starting"
    song.is_counting_in = False
    original()
    live.run_until("recorded")


def test_routing_that_never_appears_times_out(live, monkeypatch):
    bounce.bounce_start(live, start=0, end=4, stems=["Drums"])
    monkeypatch.setattr(Song, "routing_types", lambda self, owner: [RoutingType("Ext. In", 0), RoutingType("Resampling", 2)])
    failed = live.run_until("failed")
    assert "did not offer the inputs" in failed["error"] and "offered" in failed["error"]
    assert not any(name.startswith("[bounce]") for name in names(live.song))


def test_status_and_song_info(live):
    assert bounce.bounce_status(live) == {"phase": "idle"}
    info = bounce.bounce_song_info(live)
    assert info["tempo"] == 120.0 and info["time_signature"] == "4/4" and info["scale"] == "Minor"
    assert info["default_end"]["beats"] == 32.0 and info["locators"][1] == {"name": "Chorus", "beats": 12.0, "bar": "4.1.1"}
