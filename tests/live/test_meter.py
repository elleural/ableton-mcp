"""The meter on the Mac (docs/listening-loop-prd.md 11.2): the calibration tone and M3.

Live plays a file on a scratch audio track (soloed, unwarped, monitoring off) while ears.meter reads the
interface's loopback in memory; the readings must match what ears measures offline on the same file:
- calibration: a 1 kHz tone at a known level reads within +-0.1 dB;
- M3: a take's top tier measures the same through Live and the loopback as offline, so the agent's own
  takes and the streamed references share one chain.
Audible: a 3 s tone and about 20 s of a synthetic NOVA-like mix. Skipped without a loopback device.
"""
import threading
import time

import numpy as np
import pytest

from ears import meter as ears_meter
from ears import profile as profiles
from ears import spec as specs
from ears import tiers
from ears.audio import Audio, write_wav
from ears.fixtures import audio as fx
from MCP_Server.tools.clips import create_clip, fire_clip, set_clip
from MCP_Server.tools.song import transport
from MCP_Server.tools.tracks import get_mixer, set_mixer, set_track

TONE_DBFS = -24.0


@pytest.fixture(scope="module")
def loopback():
    try:
        return ears_meter.LoopbackInput()
    except ears_meter.MeterError as error:
        pytest.skip(str(error))


def _play_through_live(live, scratch, loopback, path, seconds):
    """Play `path` once from a soloed scratch track and record the loopback meanwhile (in memory)."""
    before = live.send_command("lom_get", {"path": "live_set", "properties": ["back_to_arranger"]})["values"]
    track = scratch.track("meter", kind="audio")
    slot = 0                      # the new track's own first slot: no scene is created (scene changes crashed Live once)
    set_track(track, monitoring="off")
    create_clip(track, slot=slot, file_path=str(path))
    set_clip(track, slot=slot, warping=False, looping=False)
    set_mixer(track, volume_db=0.0, pan=0.0, solo=True)
    result = {}
    reader = threading.Thread(target=lambda: result.update(recording=loopback.record(seconds)))
    reader.start()
    time.sleep(0.4)
    try:
        fire_clip(track, slot)
        reader.join(seconds + 10)
    finally:
        transport("stop")
        set_mixer(track, solo=False)
        if not before.get("back_to_arranger", {}).get("value", False):
            try:
                live.send_command("lom_set", {"path": "live_set", "property": "back_to_arranger", "value": False})
            except Exception:
                pass
    recording = result["recording"]
    start = ears_meter.signal_start(recording.samples)
    assert start is not None, "nothing reached the loopback: is Live's output the interface the meter reads?"
    return Audio(recording.samples[start:].astype(np.float64), recording.rate)


def _master_gain_db():
    master = get_mixer(["master"])
    item = master["master"] if "master" in master else master["tracks"][0]
    return float(item.get("volume_db") or 0.0)


def test_a_tone_from_live_reads_its_level(live, scratch, song_state, loopback, tmp_path):
    rate = loopback.rate
    t = np.arange(int(3.0 * rate)) / float(rate)
    tone = 10.0 ** (TONE_DBFS / 20.0) * np.sin(2 * np.pi * 1000.0 * t)
    path = tmp_path / "tone.wav"
    write_wav(path, np.column_stack([tone, tone]), rate, bit_depth=32)
    audio = _play_through_live(live, scratch, loopback, path, 5.0)
    body = audio.samples[int(0.5 * rate):int(2.5 * rate)]
    expected = TONE_DBFS + _master_gain_db()
    peak = 20.0 * np.log10(np.abs(body).max())
    rms = 20.0 * np.log10(np.sqrt(np.mean(body ** 2)))
    assert peak == pytest.approx(expected, abs=0.1)
    assert rms == pytest.approx(expected - 3.0103, abs=0.1)
    spectrum = np.abs(np.fft.rfft(body[:, 0] * np.hanning(len(body))))
    assert np.argmax(spectrum) * rate / float(len(body)) == pytest.approx(1000.0, abs=1.0)


def test_m3_a_take_measures_the_same_through_live_and_the_loopback(live, scratch, song_state, loopback, tmp_path):
    rate = loopback.rate
    spec = specs.load("nova")
    parts = fx.normalise(fx.render_parts(spec, "neon", 140.0, rate=rate, variations=["A"]), spec, "neon", 140.0, variation="A")
    bars = dict((part.id, part.bars) for part in spec.parts("neon", variations=["A"]))
    sums, _ = tiers.tier_sums(parts, spec, "neon", "A", 140.0, bars=bars)
    mix = np.tile(sums["T5"].samples, (2, 1))[:int(20.0 * rate)]
    path = tmp_path / "t5.wav"
    write_wav(path, mix, rate, bit_depth=32)
    offline = profiles.profile(Audio(mix, rate))
    audio = _play_through_live(live, scratch, loopback, path, 24.0)
    played = profiles.profile(Audio(audio.samples[:len(mix)], rate))
    gain = _master_gain_db()
    assert played["lufs_i"] == pytest.approx(offline["lufs_i"] + gain, abs=0.1)
    assert played["true_peak_dbtp"] == pytest.approx(offline["true_peak_dbtp"] + gain, abs=0.2)
    for band, value in offline["third_octave"].items():
        assert played["third_octave"][band] == pytest.approx(value, abs=0.2), band
    for key, tolerance in (("lra", 0.2), ("plr_db", 0.2), ("crest_db", 0.2), ("width", 0.01), ("correlation", 0.01),
                           ("mono_sub_loss_db", 0.1)):
        assert played[key] == pytest.approx(offline[key], abs=tolerance), key
    assert played["onset_rate"] == pytest.approx(offline["onset_rate"], rel=0.05)
    assert profiles.same_tempo(played["tempo"]["bpm"], offline["tempo"]["bpm"]) and played["key"]["key"] == offline["key"]["key"]
