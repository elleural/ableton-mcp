"""Listening loop live tests: the Session capture engine against the running Live (audible, about 30 s).

A scratch audio track holds a generated calibration clip (impulses at known beats, a -18 dBFS tone).
Captures record it by its Post Mixer tap and by Resampling (with the scratch track soloed, so the rest
of the set is silent) and must land sample-exact at unity gain (PRD C3, C4), leave the set as found
(C2) and remove their tracks.
"""
import time

import numpy as np
import pytest

from ears import audio

RATE = 44100
IMPULSE_BEATS = (0.5, 1.5, 2.5, 3.5)
TONE_BEATS = (4.0, 6.0)
STATE = ["tempo", "clip_trigger_quantization", "loop", "metronome", "record_mode", "session_record", "back_to_arranger",
         "start_time", "is_playing"]


def write_calibration(path, tempo):
    beat = 60.0 / tempo
    frames = int(round(8 * beat * RATE))
    signal = np.zeros((frames, 2))
    for position in IMPULSE_BEATS:
        signal[int(round(position * beat * RATE)), :] = 0.5
    start, end = (int(round(b * beat * RATE)) for b in TONE_BEATS)
    signal[start:end, :] = (10 ** (-18 / 20.0) * np.sin(2 * np.pi * 1000 * np.arange(end - start) / RATE))[:, None]
    audio.write_wav(path, signal, RATE, 24)


def wait_for(live, phases, timeout=60.0):
    deadline = time.time() + timeout
    while True:
        job = live.send_command("capture_status", {})
        if job["phase"] in phases or time.time() > deadline:
            return job
        time.sleep(0.2)


def song(live):
    values = live.send_command("lom_get", {"path": "live_set", "properties": STATE})["values"]
    return dict((key, entry.get("value")) for key, entry in values.items())


def mixer_flags(live):
    overview = live.send_command("get_song_overview", {})
    return dict((track["name"], (track["mute"], track["solo"], track["arm"])) for track in overview["tracks"])


@pytest.fixture
def calibration(live, scratch, song_state, tmp_path):
    tempo = 140.0
    name = scratch.track("src", kind="audio")
    path = tmp_path / "calibration.wav"
    write_calibration(path, tempo)
    live.send_command("create_clip", {"track": name, "slot": 0, "file_path": str(path)})
    live.send_command("set_clip", {"track": name, "slot": 0, "warping": False, "looping": False})
    yield {"track": name, "tempo": tempo}
    live.send_command("capture_cancel", {})


def test_capture_is_sample_exact_and_leaves_no_trace(live, calibration):
    before_song, before_flags = song(live), mixer_flags(live)
    track, tempo = calibration["track"], calibration["tempo"]
    passes = [{"label": "cal", "tempo": tempo, "fire": [{"track": track, "slot": 0}], "solo": [track],
               "record": [{"key": "tap", "source": track}, {"key": "mix", "source": "resampling"}], "beats": 8}]
    job = live.send_command("capture_start", {"passes": passes, "name": "test"})
    assert job["phase"] == "route" and job["tracks"] == ["cap:tap", "cap:mix"]
    with pytest.raises(Exception) as busy:
        live.send_command("capture_start", {"passes": passes})
    assert "busy" in str(busy.value).lower() or "still" in str(busy.value)
    job = wait_for(live, ("recorded", "failed"))
    assert job["phase"] == "recorded", job.get("error")
    assert job["restored"], job["warnings"]
    result = job["results"][0]
    assert result["tempo_steady"] and abs(result["tempo"] - tempo) < 1e-9
    beat = 60.0 / tempo
    for item in result["files"]:
        recorded = audio.read(item["file_path"])
        assert recorded.rate == int(item["sample_rate"])
        x = recorded.samples[:, 0]
        base = item["offset_samples"]
        for position in IMPULSE_BEATS:
            expect = base + position * beat * recorded.rate
            window = x[int(expect - 0.05 * recorded.rate):int(expect + 0.05 * recorded.rate)]
            found = int(expect - 0.05 * recorded.rate) + int(np.argmax(np.abs(window)))
            assert abs(found - expect) <= 1, (item["key"], position, found - expect)            # C3: sample-exact
        start, end = (int(base + b * beat * recorded.rate) for b in (TONE_BEATS[0] + 0.25, TONE_BEATS[1] - 0.25))
        level = 20 * np.log10(np.sqrt(np.mean(x[start:end] ** 2)))
        assert abs(level - (-18.0 - 3.0103)) < 0.1, (item["key"], level)                           # C4: unity gain
    done = live.send_command("capture_cleanup", {"job_id": job["id"]})
    assert done["phase"] == "done" and sorted(done["removed_tracks"]) == ["cap:mix", "cap:tap"]
    time.sleep(0.3)
    after_song, after_flags = song(live), mixer_flags(live)
    for key in STATE:
        assert after_song[key] == before_song[key], key                                             # C2: no trace
    assert after_flags == before_flags


def test_capture_errors_and_cancel(live, calibration):
    track = calibration["track"]
    with pytest.raises(Exception) as missing:
        live.send_command("capture_start", {"passes": [{"fire": [{"track": track, "slot": 3}], "record": [{"key": "x", "source": track}], "beats": 4}]})
    assert "no clip" in str(missing.value)
    with pytest.raises(Exception):
        live.send_command("capture_start", {"passes": [{"fire": [{"track": "no such track", "slot": 0}], "record": [{"key": "x", "source": track}], "beats": 4}]})
    with pytest.raises(Exception):
        live.send_command("capture_start", {"passes": [{"fire": [{"track": track, "slot": 0}], "record": [{"key": "x", "source": track, "tap": "Post Pan"}], "beats": 4}]})
    passes = [{"fire": [{"track": track, "slot": 0}], "solo": [track], "record": [{"key": "tap", "source": track}], "beats": 64}]
    live.send_command("capture_start", {"passes": passes})
    wait_for(live, ("recording",), timeout=20)
    job = live.send_command("capture_cancel", {})
    job = wait_for(live, ("cancelled", "failed"))
    assert job["phase"] == "cancelled" and job["removed_tracks"] == ["cap:tap"]
    names = [t["name"] for t in live.send_command("get_song_overview", {})["tracks"]]
    assert not [name for name in names if name.startswith("cap:")]
    assert not song(live)["is_playing"]


def test_later_pass_unmutes_what_an_earlier_pass_muted(live, scratch, song_state, tmp_path):
    """Pass 1 mutes the track it does not fire; pass 2 fires that track, which must not record silence."""
    tempo = 140.0
    first, second = scratch.track("one", kind="audio"), scratch.track("two", kind="audio")
    for name in (first, second):
        path = tmp_path / (name.replace(" ", "_").replace(":", "_") + ".wav")
        write_calibration(path, tempo)
        live.send_command("create_clip", {"track": name, "slot": 0, "file_path": str(path)})
        live.send_command("set_clip", {"track": name, "slot": 0, "warping": False, "looping": False})
    before = mixer_flags(live)
    passes = [{"label": "one", "tempo": tempo, "fire": [{"track": first, "slot": 0}], "record": [{"key": "one", "source": first}], "beats": 8},
              {"label": "two", "tempo": tempo, "fire": [{"track": second, "slot": 0}], "record": [{"key": "two", "source": second}], "beats": 8}]
    live.send_command("capture_start", {"passes": passes})
    try:
        job = wait_for(live, ("recorded", "failed"), timeout=60)
        assert job["phase"] == "recorded", job.get("error")
        for result in job["results"]:
            recorded = audio.read(result["files"][0]["file_path"])
            level = 20 * np.log10(np.max(np.abs(recorded.samples)) + 1e-12)
            assert level > -10.0, (result["label"], level)   # the impulses (-6 dBFS) are there, not silence
        live.send_command("capture_cleanup", {"job_id": job["id"]})
    finally:
        live.send_command("capture_cancel", {})
    time.sleep(0.3)
    assert mixer_flags(live) == before
