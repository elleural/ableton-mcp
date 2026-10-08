"""Unit tests for ears/audio.py: the numpy WAV reader and writer, WAVE_FORMAT_EXTENSIBLE headers (Live writes them),
channel helpers, mixing and ffmpeg discovery. Everything but the FLAC test runs without ffmpeg."""
import os
import struct
import subprocess

import numpy as np
import pytest

from ears import audio
from ears.audio import Audio, AudioFileError

LSB16, LSB24 = 1.0 / 32768.0, 1.0 / (1 << 23)


def make_signal(frames=2000, channels=2, seed=1):
    """A sine plus noise below full scale, with exact values at the ends: 0, +0.5 and -1.0 land on grid points."""
    rng = np.random.default_rng(seed)
    t = np.arange(frames) / 48000.0
    base = 0.6 * np.sin(2 * np.pi * 997.0 * t) + 0.2 * rng.standard_normal(frames) * 0.5
    out = np.stack([base, 0.8 * base[::-1]][:channels], axis=1)
    out[0], out[1], out[2] = 0.0, 0.5, -1.0
    return np.clip(out, -1.0, 0.999)


def pcm24_bytes(ints):
    return b"".join(struct.pack("<i", int(value))[:3] for value in np.asarray(ints).reshape(-1))


def riff(chunks, tag=b"RIFF"):
    body = b"WAVE" + b"".join(chunks)
    return tag + struct.pack("<I", len(body)) + body


def chunk(tag, payload):
    return tag + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) & 1 else b"")


def extensible_fmt(channels, rate, container_bits, valid_bits, subformat, mask=3):
    block = channels * container_bits // 8
    guid = struct.pack("<H", subformat) + b"\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
    payload = struct.pack("<HHIIHH", 0xFFFE, channels, rate, rate * block, block, container_bits)
    payload += struct.pack("<HHI", 22, valid_bits, mask) + guid
    return chunk(b"fmt ", payload)


# ---------------------------------------------------------------------------
# Round trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bit_depth, tolerance, kind", [(16, LSB16, "pcm"), (24, LSB24, "pcm"), (32, 1e-7, "float")])
@pytest.mark.parametrize("channels", [1, 2])
def test_write_then_read_round_trips_within_one_lsb(tmp_path, bit_depth, tolerance, kind, channels):
    samples = make_signal(channels=channels)
    path = audio.write_wav(tmp_path / "x.wav", samples, 48000, bit_depth)
    assert path == tmp_path / "x.wav"
    decoded = audio.read_wav(path)
    assert decoded.rate == 48000 and decoded.channels == channels and decoded.frames == samples.shape[0]
    assert decoded.bit_depth == bit_depth and decoded.format == kind and decoded.path == str(path)
    assert np.max(np.abs(decoded.samples - samples)) <= tolerance
    if bit_depth == 24:
        assert decoded.samples[2, 0] == -1.0 and decoded.samples[1, 0] == 0.5 and decoded.samples[0, 0] == 0.0   # exact on grid points


def test_float_round_trip_keeps_values_beyond_full_scale(tmp_path):
    samples = np.array([[2.5, -3.0], [1e-9, 0.0]])
    decoded = audio.read_wav(audio.write_wav(tmp_path / "big.wav", samples, 44100, 32))
    assert decoded.samples[0, 0] == 2.5 and decoded.samples[0, 1] == -3.0 and decoded.samples[1, 0] == pytest.approx(1e-9, rel=1e-6)


@pytest.mark.parametrize("bit_depth, top", [(16, 32767 / 32768.0), (24, ((1 << 23) - 1) / float(1 << 23))])
def test_pcm_writes_clip_instead_of_wrapping(tmp_path, bit_depth, top):
    decoded = audio.read_wav(audio.write_wav(tmp_path / "hot.wav", np.array([2.0, -2.0, 1.0, -1.0, 0.0]), 48000, bit_depth))
    assert decoded.samples[:, 0].tolist() == [top, -1.0, top, -1.0, 0.0]


def test_odd_sized_payload_is_padded_and_reads_back(tmp_path):
    samples = np.array([0.1, -0.2, 0.3])                       # 3 frames x 3 bytes = 9 bytes: odd
    path = audio.write_wav(tmp_path / "odd.wav", samples, 48000, 24)
    assert path.stat().st_size % 2 == 0 and path.stat().st_size == 44 + 9 + 1
    assert np.max(np.abs(audio.read_wav(path).samples[:, 0] - samples)) <= LSB24


def test_write_creates_folders_and_leaves_no_temp_file(tmp_path):
    path = audio.write_wav(tmp_path / "a" / "b" / "c.wav", np.zeros((10, 2)), 48000, 16)
    assert path.is_file() and [p.name for p in path.parent.iterdir()] == ["c.wav"]
    audio.write_wav(path, np.ones((10, 2)) * 0.5, 48000, 16)           # overwrite in place
    assert audio.read_wav(path).samples[0, 0] == 0.5 and [p.name for p in path.parent.iterdir()] == ["c.wav"]


def test_write_header_fields(tmp_path):
    path = audio.write_wav(tmp_path / "h.wav", np.zeros((100, 2)), 44100, 24)
    raw = path.read_bytes()
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE" and raw[12:16] == b"fmt "
    code, channels, rate, byte_rate, block, bits = struct.unpack("<HHIIHH", raw[20:36])
    assert (code, channels, rate, bits) == (1, 2, 44100, 24) and block == 6 and byte_rate == 44100 * 6
    assert struct.unpack("<I", raw[4:8])[0] == len(raw) - 8
    assert raw[36:40] == b"data" and struct.unpack("<I", raw[40:44])[0] == 600
    code32 = struct.unpack("<H", audio.write_wav(tmp_path / "f.wav", np.zeros((4, 1)), 48000, 32).read_bytes()[20:22])[0]
    assert code32 == 3                                                   # IEEE float


def test_write_rejects_other_bit_depths(tmp_path):
    for depth in (8, 12, 64, 0):
        with pytest.raises(AudioFileError, match="bit_depth must be 16, 24 or 32"):
            audio.write_wav(tmp_path / "x.wav", np.zeros(4), 48000, depth)
    assert not (tmp_path / "x.wav").exists()


def test_write_accepts_a_one_dimensional_array_and_audio_objects(tmp_path):
    audio.write_wav(tmp_path / "mono.wav", np.array([0.25, -0.25]), 8000, 16)
    mono = audio.read_wav(tmp_path / "mono.wav")
    assert mono.channels == 1 and mono.rate == 8000 and mono.samples[:, 0].tolist() == [0.25, -0.25]
    audio.write(tmp_path / "copy.wav", mono, 24)
    again = audio.read(tmp_path / "copy.wav")
    assert again.bit_depth == 24 and again.samples[:, 0].tolist() == [0.25, -0.25]


# ---------------------------------------------------------------------------
# WAVE_FORMAT_EXTENSIBLE and other hand-built headers
# ---------------------------------------------------------------------------


def test_extensible_float32_stereo(tmp_path):
    data = np.array([[0.5, -0.25], [0.125, 1.0], [-1.0, 0.0]], dtype="<f4")
    path = tmp_path / "ext_f32.wav"
    path.write_bytes(riff([extensible_fmt(2, 48000, 32, 32, 3), chunk(b"fact", struct.pack("<I", 3)), chunk(b"data", data.tobytes())]))
    decoded = audio.read_wav(path)
    assert (decoded.rate, decoded.channels, decoded.frames, decoded.bit_depth, decoded.format) == (48000, 2, 3, 32, "float")
    assert decoded.samples.tolist() == data.astype(np.float64).tolist()


def test_extensible_pcm24_at_96k_reads_the_subformat_not_the_tag(tmp_path):
    ints = np.array([[1 << 22, -(1 << 22)], [1, -1], [(1 << 23) - 1, -(1 << 23)]])
    path = tmp_path / "ext_pcm24.wav"
    path.write_bytes(riff([extensible_fmt(2, 96000, 24, 24, 1), chunk(b"data", pcm24_bytes(ints))]))
    decoded = audio.read_wav(path)
    assert (decoded.rate, decoded.bit_depth, decoded.format) == (96000, 24, "pcm")
    assert decoded.samples.tolist() == (ints / float(1 << 23)).tolist()


def test_extensible_pcm16_mono_and_float64(tmp_path):
    path = tmp_path / "ext16.wav"
    path.write_bytes(riff([extensible_fmt(1, 44100, 16, 16, 1), chunk(b"data", np.array([16384, -16384, 32767, -32768], dtype="<i2").tobytes())]))
    decoded = audio.read_wav(path)
    assert decoded.channels == 1 and decoded.rate == 44100 and decoded.samples[:, 0].tolist() == [0.5, -0.5, 32767 / 32768.0, -1.0]
    path = tmp_path / "ext64.wav"
    path.write_bytes(riff([extensible_fmt(2, 48000, 64, 64, 3), chunk(b"data", np.array([0.5, -0.5, 0.25, 0.125], dtype="<f8").tobytes())]))
    decoded = audio.read_wav(path)
    assert decoded.format == "float" and decoded.bit_depth == 64 and decoded.samples.tolist() == [[0.5, -0.5], [0.25, 0.125]]


def test_extensible_header_too_short_for_a_subformat_is_unsupported(tmp_path):
    fmt = chunk(b"fmt ", struct.pack("<HHIIHH", 0xFFFE, 2, 48000, 192000, 4, 16) + struct.pack("<H", 0))     # 18 bytes: no GUID
    path = tmp_path / "short_ext.wav"
    path.write_bytes(riff([fmt, chunk(b"data", b"\0" * 8)]))
    with pytest.raises(AudioFileError, match="Unsupported WAV encoding"):
        audio.read_wav(path)


def test_plain_pcm32_and_pcm8(tmp_path):
    path = tmp_path / "p32.wav"
    fmt = chunk(b"fmt ", struct.pack("<HHIIHH", 1, 2, 48000, 384000, 8, 32))
    path.write_bytes(riff([fmt, chunk(b"data", np.array([1 << 30, -(1 << 30)], dtype="<i4").tobytes())]))
    assert audio.read_wav(path).samples.tolist() == [[0.5, -0.5]]
    fmt = chunk(b"fmt ", struct.pack("<HHIIHH", 1, 1, 8000, 8000, 1, 8))
    path.write_bytes(riff([fmt, chunk(b"data", bytes([128, 255, 0, 64]))]))
    assert audio.read_wav(path).samples[:, 0].tolist() == [0.0, 127 / 128.0, -1.0, -0.5]


def test_unsupported_encodings_are_reported(tmp_path):
    path = tmp_path / "adpcm.wav"
    fmt = chunk(b"fmt ", struct.pack("<HHIIHH", 2, 1, 8000, 4000, 1, 4))
    path.write_bytes(riff([fmt, chunk(b"data", b"\0" * 8)]))
    with pytest.raises(AudioFileError, match=r"Unsupported WAV encoding \(format 2, 4 bits\)"):
        audio.read_wav(path)


def test_extra_chunks_before_data_are_skipped_including_odd_sized_ones(tmp_path):
    path = audio.write_wav(tmp_path / "plain.wav", np.array([[0.5, 0.5], [0.25, 0.25]]), 48000, 16)
    raw = path.read_bytes()
    odd = chunk(b"LIST", b"abcde")                                     # 5 bytes of payload plus a pad byte
    patched = raw[:36] + odd + raw[36:]
    patched = patched[:4] + struct.pack("<I", len(patched) - 8) + patched[8:]
    path.write_bytes(patched)
    assert audio.read_wav(path).samples.tolist() == [[0.5, 0.5], [0.25, 0.25]]


def test_a_truncated_data_chunk_keeps_the_whole_frames(tmp_path):
    path = audio.write_wav(tmp_path / "cut.wav", np.zeros((100, 2)), 48000, 16)
    path.write_bytes(path.read_bytes()[:-7])                            # the header still promises 400 bytes; 393 are there
    assert audio.read_wav(path).frames == 98


def test_rf64_style_header_with_unset_sizes_reads_to_the_end(tmp_path):
    ds64 = chunk(b"ds64", struct.pack("<QQQI", 0, 0, 0, 0))
    fmt = chunk(b"fmt ", struct.pack("<HHIIHH", 1, 1, 48000, 96000, 2, 16))
    payload = np.array([100, -100, 200], dtype="<i2").tobytes()
    data = b"data" + struct.pack("<I", 0xFFFFFFFF) + payload
    body = b"WAVE" + ds64 + fmt + data
    path = tmp_path / "big.wav"
    path.write_bytes(b"RF64" + struct.pack("<I", 0xFFFFFFFF) + body)
    assert audio.read_wav(path).samples[:, 0].tolist() == [100 / 32768.0, -100 / 32768.0, 200 / 32768.0]


def test_wav_without_a_data_chunk_is_an_error(tmp_path):
    path = tmp_path / "nodata.wav"
    path.write_bytes(riff([chunk(b"fmt ", struct.pack("<HHIIHH", 1, 2, 48000, 192000, 4, 16))]))
    with pytest.raises(AudioFileError, match="no fmt or data chunk"):
        audio.read_wav(path)
    path.write_bytes(riff([chunk(b"data", b"\0\0\0\0")]))             # data before fmt is not decodable
    with pytest.raises(AudioFileError, match="no fmt or data chunk"):
        audio.read_wav(path)


# ---------------------------------------------------------------------------
# Not a WAV file
# ---------------------------------------------------------------------------


def test_read_wav_rejects_files_that_are_not_wav(tmp_path):
    for name, content in (("text.wav", b"this is not audio at all, definitely"), ("empty.wav", b""), ("short.wav", b"RIFF"),
                          ("aiff.wav", b"FORM\x00\x00\x00\x04AIFF" + b"\0" * 20), ("riff_but_avi.wav", b"RIFF\x04\x00\x00\x00AVI ")):
        path = tmp_path / name
        path.write_bytes(content)
        with pytest.raises(AudioFileError, match="is not a WAV file"):
            audio.read_wav(path)


@pytest.mark.parametrize("name, chunks", [
    ("truncated_fmt", [b"fmt " + struct.pack("<I", 16) + b"\x01\x00\x02\x00"]),
    ("zero_block_align", [chunk(b"fmt ", struct.pack("<HHIIHH", 1, 2, 48000, 192000, 0, 16)), chunk(b"data", b"\0" * 8)]),
    ("zero_channels", [chunk(b"fmt ", struct.pack("<HHIIHH", 1, 0, 48000, 0, 4, 16)), chunk(b"data", b"\0" * 8)]),
    ("zero_sample_rate", [chunk(b"fmt ", struct.pack("<HHIIHH", 1, 2, 0, 0, 4, 16)), chunk(b"data", b"\0" * 8)]),
])
def test_a_wav_with_a_malformed_header_is_an_audio_error(tmp_path, name, chunks):
    path = tmp_path / (name + ".wav")
    path.write_bytes(riff(chunks))
    with pytest.raises(AudioFileError):
        audio.read_wav(path)


def test_read_wav_missing_file_is_an_audio_error(tmp_path):
    with pytest.raises(AudioFileError, match="Cannot read"):
        audio.read_wav(tmp_path / "nowhere.wav")


def test_read_of_garbage_is_an_audio_error_with_or_without_ffmpeg(tmp_path):
    path = tmp_path / "garbage.wav"
    path.write_bytes(b"not a wav file " * 10)
    with pytest.raises(AudioFileError):
        audio.read(path)
    other = tmp_path / "garbage.mp3"
    other.write_bytes(b"\xff\xfb" + b"\0" * 20)
    with pytest.raises(AudioFileError):
        audio.read(other)
    with pytest.raises(AudioFileError, match="No such audio file"):
        audio.read(tmp_path / "missing.wav")


def test_read_dispatches_on_wav_suffixes_without_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "find_ffmpeg", lambda name="ffmpeg": None)
    for name in ("a.wav", "b.WAV", "c.wave"):
        audio.write_wav(tmp_path / name, np.array([0.5, -0.5]), 48000, 16)
        assert audio.read(tmp_path / name).samples[:, 0].tolist() == [0.5, -0.5]
    (tmp_path / "bad.wav").write_bytes(b"x" * 100)
    with pytest.raises(AudioFileError, match="is not a WAV file"):          # no ffmpeg to fall back on: the original error
        audio.read(tmp_path / "bad.wav")
    (tmp_path / "song.flac").write_bytes(b"fLaC")
    with pytest.raises(AudioFileError, match="needs ffmpeg"):
        audio.read(tmp_path / "song.flac")


def test_read_expands_the_user_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    audio.write_wav(tmp_path / "home.wav", np.array([0.5]), 8000, 16)
    assert audio.read("~/home.wav").frames == 1


@pytest.mark.skipif(audio.find_ffmpeg() is None or audio.find_ffmpeg("ffprobe") is None, reason="ffmpeg and ffprobe are not installed")
def test_read_decodes_flac_through_ffmpeg(tmp_path):
    samples = make_signal(frames=4800)
    wav = audio.write_wav(tmp_path / "source.wav", samples, 48000, 24)
    flac = tmp_path / "source.flac"
    subprocess.run([audio.find_ffmpeg(), "-v", "error", "-i", str(wav), "-c:a", "flac", "-sample_fmt", "s32", str(flac)], check=True)
    decoded = audio.read(flac)
    assert decoded.format == "decoded" and decoded.rate == 48000 and decoded.channels == 2 and decoded.frames == 4800
    assert np.max(np.abs(decoded.samples - samples)) <= 2 * LSB24


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------


def test_audio_properties_and_info():
    sig = Audio(np.array([0.5, 0.25, -0.5]), 48000, path="/x/y.wav", bit_depth=24, format="pcm")
    assert sig.samples.shape == (3, 1) and sig.channels == 1 and sig.frames == 3 and sig.rate == 48000
    assert sig.duration == pytest.approx(3 / 48000.0)
    assert sig.info() == {"path": "/x/y.wav", "rate": 48000, "channels": 1, "frames": 3, "duration": 6.3e-05, "bit_depth": 24, "format": "pcm"}
    assert "3 frames, 1 ch, 48000 Hz, y.wav" in repr(sig)
    assert Audio(np.zeros((0, 2)), 48000).duration == 0.0 and "y.wav" not in repr(Audio(np.zeros((4, 2)), 48000))


def test_mono_is_the_channel_average():
    stereo = Audio(np.array([[1.0, 0.0], [0.5, -0.5]]), 48000)
    assert stereo.mono().tolist() == [0.5, 0.0]
    assert Audio(np.array([0.25, 0.5]), 48000).mono().tolist() == [0.25, 0.5]


def test_stereo_duplicates_mono_and_keeps_the_first_two_channels():
    mono = Audio(np.array([0.25, 0.5]), 48000)
    assert mono.stereo().shape == (2, 2) and mono.stereo()[:, 0].tolist() == [0.25, 0.5] and mono.stereo()[:, 1].tolist() == [0.25, 0.5]
    stereo = Audio(np.array([[1.0, 2.0], [3.0, 4.0]]), 48000)
    assert stereo.stereo() is stereo.samples
    surround = Audio(np.arange(12, dtype=float).reshape(4, 3), 48000)
    assert surround.stereo().tolist() == [[0.0, 1.0], [3.0, 4.0], [6.0, 7.0], [9.0, 10.0]]


def test_slice_by_seconds():
    sig = Audio(np.arange(100, dtype=float), 100, path="p")
    assert sig.slice(0.25, 0.5).samples[:, 0].tolist() == list(range(25, 50))
    assert sig.slice(0.5).frames == 50 and sig.slice().frames == 100
    assert sig.slice(-1.0, 0.1).frames == 10 and sig.slice(0.9, 5.0).frames == 10 and sig.slice(2.0, 3.0).frames == 0
    assert sig.slice(0.25, 0.5).path == "p"


def test_mix_pads_to_the_longest_and_returns_stereo():
    short_mono = Audio(np.ones((4, 1)), 10)
    long_stereo = Audio(np.stack([np.full(6, 0.5), np.full(6, -0.25)], axis=1), 10)
    mixed = audio.mix([short_mono, long_stereo])
    assert mixed.rate == 10 and mixed.channels == 2 and mixed.frames == 6
    assert mixed.samples[:, 0].tolist() == [1.5, 1.5, 1.5, 1.5, 0.5, 0.5]
    assert mixed.samples[:, 1].tolist() == [0.75, 0.75, 0.75, 0.75, -0.25, -0.25]
    assert audio.mix([long_stereo]).samples.tolist() == long_stereo.samples.tolist()


def test_mix_of_different_lengths_and_the_inputs_stay_untouched():
    a, b, c = (Audio(np.full((n, 2), value), 48000) for n, value in ((3, 0.1), (7, 0.2), (5, 0.4)))
    mixed = audio.mix([a, b, c])
    assert mixed.frames == 7 and mixed.samples[:, 0].tolist() == pytest.approx([0.7] * 3 + [0.6] * 2 + [0.2] * 2)
    assert a.frames == 3 and b.frames == 7 and a.samples[0, 0] == 0.1


def test_mix_rejects_nothing_and_mixed_rates():
    with pytest.raises(AudioFileError, match="Nothing to mix"):
        audio.mix([])
    with pytest.raises(AudioFileError, match=r"different sample rates: \[10, 20\]"):
        audio.mix([Audio(np.ones((4, 1)), 10), Audio(np.ones((4, 1)), 20)])


def test_match_length_zero_pads():
    out = audio.match_length([np.ones((2, 2)), np.ones((5, 2)), np.ones((3, 2))])
    assert [item.shape[0] for item in out] == [5, 5, 5] and out[0][2:].sum() == 0 and out[1].sum() == 10


def test_level_helpers():
    assert audio.db(1.0) == 0.0 and audio.db(0.5) == pytest.approx(-6.0206, abs=1e-4) and audio.db(10.0) == pytest.approx(20.0)
    assert audio.db(0.0) == -200.0 and audio.db(1e-12) == -200.0 and audio.db(-1.0) == -200.0       # floored, never -inf
    assert audio.power_db(1.0) == 0.0 and audio.power_db(0.5) == pytest.approx(-3.0103, abs=1e-4) and audio.power_db(0.0) == -200.0
    assert audio.rms([1.0, -1.0, 1.0, -1.0]) == 1.0 and audio.rms([]) == 0.0 and audio.rms(np.zeros((3, 2))) == 0.0
    assert audio.peak([0.1, -0.7]) == 0.7 and audio.peak([]) == 0.0


def test_db_floor_argument():
    assert audio.db(1e-9, floor=-100.0) == -100.0                         # below the floor's amplitude
    assert audio.db(1e-4, floor=-60.0) == -60.0
    assert audio.db(1e-2, floor=-60.0) == pytest.approx(-40.0)
    assert audio.power_db(1e-12, floor=-100.0) == -100.0 and audio.power_db(1e-3, floor=-100.0) == pytest.approx(-30.0)


# ---------------------------------------------------------------------------
# find_ffmpeg
# ---------------------------------------------------------------------------


def make_tool(folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return str(path)


def test_find_ffmpeg_prefers_the_environment_override(tmp_path, monkeypatch):
    fake = make_tool(tmp_path / "bin", "my-ffmpeg")
    monkeypatch.setenv("EARS_FFMPEG", fake)
    assert audio.find_ffmpeg() == fake
    monkeypatch.delenv("EARS_FFMPEG")
    monkeypatch.setenv("ABLETON_MCP_FFMPEG", fake)
    assert audio.find_ffmpeg() == fake
    monkeypatch.setenv("EARS_FFPROBE", fake)
    assert audio.find_ffmpeg("ffprobe") == fake                           # the variable name follows the tool name


def test_find_ffmpeg_ignores_an_override_that_is_not_a_file(tmp_path, monkeypatch):
    monkeypatch.setenv("EARS_FFMPEG", str(tmp_path / "absent"))
    monkeypatch.setattr(audio.shutil, "which", lambda name: "/found/on/path/" + name)
    assert audio.find_ffmpeg() == "/found/on/path/ffmpeg"


def test_find_ffmpeg_falls_back_to_the_usual_folders_then_none(tmp_path, monkeypatch):
    for variable in ("EARS_FFMPEG", "ABLETON_MCP_FFMPEG"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    monkeypatch.setattr(audio, "FFMPEG_DIRS", (str(tmp_path / "missing"), str(tmp_path / "usr")))
    assert audio.find_ffmpeg() is None
    fake = make_tool(tmp_path / "usr", "ffmpeg")
    assert audio.find_ffmpeg() == fake
    (tmp_path / "usr" / "ffprobe").write_text("not executable")
    assert audio.find_ffmpeg("ffprobe") is None                           # present but not executable
