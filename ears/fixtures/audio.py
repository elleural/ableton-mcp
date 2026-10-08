"""Synthetic NOVA-like stems with planted defects (PRD section 13.2, fixture form).

`render_parts(spec, set_name, tempo)` synthesises every part of a set in A minor following the spec's
progressions: a pitch-dropping kick, noise hats and claps, a pad on tones that are safe over every
progression (with a hall reverb), a mono-compatible bass with a sub, a 16th-note arp and a sparse
square lead. Each part is rendered for two cycles of its own loop plus a bar, reverb included, and
the second cycle plus the tail is kept, exactly like a capture: the tails are folded.

`write_take(home, ...)` writes a take folder the measurement ear can analyse; `plant()` returns the
parts with one defect: arp_3k, sub_out_of_phase, master_reverb, seam_click, unfolded, short_5ms,
stem_louder (use with several tempos).
"""
import json

import numpy as np
from scipy import signal as sps

from .. import audio as audio_io
from .. import loudness, report, theory
from ..take import next_id, takes_dir

RATE = 48000
DEFECTS = ("arp_3k", "sub_out_of_phase", "master_reverb", "seam_click", "unfolded", "short_5ms", "stem_louder")
# Part levels (dB) chosen so the T5 sum lands near -14 LUFS with true peak below -1 dBTP.
LEVELS = {"kick": -18.0, "perc": -22.0, "pad": -14.0, "bass": -18.0, "arp": -16.0, "lead": -18.0}


def _freq(midi, a4=440.0):
    return a4 * 2.0 ** ((midi - 69) / 12.0)


def _env(frames, rate, attack, decay, sustain=1.0, release=None):
    t = np.arange(frames) / rate
    env = np.minimum(1.0, t / max(attack, 1e-4))
    if release is None:
        env = env * np.exp(-np.maximum(0.0, t - attack) / max(decay, 1e-4)) * (1 - sustain) + env * sustain if sustain < 1 else env
    return env


def _tone(freq, frames, rate, harmonics=6, phase=0.0):
    t = np.arange(frames) / rate
    out = np.zeros(frames)
    for n in range(1, harmonics + 1):
        if freq * n < rate / 2.2:
            out += np.sin(2 * np.pi * freq * n * t + phase * n) / n
    return out


def _add(buffer, start, samples, gains):
    end = min(buffer.shape[0], start + samples.shape[0])
    if end > start:
        buffer[start:end, 0] += samples[:end - start] * gains[0]
        buffer[start:end, 1] += samples[:end - start] * gains[1]


def _reverb(samples, rate, seconds=1.2, wet=0.35, seed=7):
    rng = np.random.default_rng(seed)
    n = int(seconds * rate)
    decay = np.exp(-6.91 * np.arange(n) / n)
    out = samples * (1 - wet)
    for channel in range(2):
        ir = rng.standard_normal(n) * decay
        ir /= np.sqrt(np.sum(ir ** 2))
        out[:, channel] += wet * sps.fftconvolve(samples[:, channel], ir)[:samples.shape[0]]
    return out


def _chord_pcs(name):
    """Chord tones in order (root, third, fifth...)."""
    return list(theory.parse_chord(name).tones)


def safe_tones(spec, set_name, bar):
    """Pitch classes no semitone away from any chord tone any of the set's progressions plays in `bar`."""
    chords = set()
    for variation in spec.variations(set_name):
        progression = spec.progression(set_name, variation)
        chords.add(progression[bar % len(progression)])
    tones = set()
    for chord in chords:
        tones |= set(_chord_pcs(chord))
    safe = []
    for pc in range(12):
        if all(min((pc - tone) % 12, (tone - pc) % 12) != 1 for tone in tones) and pc in spec.scale | tones:
            safe.append(pc)
    chord_tones = [pc for pc in safe if pc in tones]
    return chord_tones or safe


def _render(kind, spec, set_name, variation, tempo, bars, rate):
    beat = 60.0 / tempo
    bar_s = spec.beats_per_bar * beat
    total = int(round((bars + 1) * bar_s * rate))
    out = np.zeros((total, 2))
    progression = spec.progression(set_name, variation or spec.variations(set_name)[0])
    rng = np.random.default_rng(11)
    sixteenth = beat / 4.0
    for bar in range(bars + 1):
        chord = progression[bar % len(progression)]
        tones = _chord_pcs(chord)
        root = theory.chord_root(chord)
        at = lambda b: int(round((bar * bar_s + b * beat) * rate))
        if kind == "kick":
            for b in range(4):
                n = int(0.35 * rate)
                t = np.arange(n) / rate
                f = 50 + 110 * np.exp(-t / 0.03)
                body = np.sin(2 * np.pi * np.cumsum(f) / rate) * np.exp(-t / 0.12)
                _add(out, at(b), body, (1.0, 1.0))
        elif kind == "perc":
            for step in range(8):
                if step % 2 == 1:
                    n = int(0.03 * rate)
                    noise = rng.standard_normal(n) * np.exp(-np.arange(n) / (0.008 * rate))
                    noise = sps.sosfilt(sps.butter(4, 6000, "highpass", fs=rate, output="sos"), noise)
                    _add(out, at(step * 0.5), noise, (0.8, 1.0))
            for b in (1, 3):
                n = int(0.08 * rate)
                noise = rng.standard_normal(n) * np.exp(-np.arange(n) / (0.02 * rate))
                noise = sps.sosfilt(sps.butter(2, [1000, 3000], "bandpass", fs=rate, output="sos"), noise)
                _add(out, at(b), noise * 0.8, (1.0, 0.9))
        elif kind == "pad":
            n = int((bar_s + 0.4) * rate)
            env = np.minimum(1.0, np.arange(n) / (0.3 * rate)) * np.clip((n - np.arange(n)) / (0.4 * rate), 0, 1)
            for pc in safe_tones(spec, set_name, bar):
                midi = 57 + ((pc - 9) % 12)
                _add(out, at(0), _tone(_freq(midi), n, rate, 6) * env * 0.25, (1.0, 0.9))
        elif kind == "bass":
            # Root on beat 1, the chord's third (minor chords) or fifth on beat 3: chord tones that also
            # say "A minor" when the bass is heard alone.
            third = tones[1] if len(tones) > 1 else root
            second = third if (third - root) % 12 == 3 else (tones[2] if len(tones) > 2 else root)
            for b, pc in ((0, root), (2, second)):
                midi = 33 + ((pc - 9) % 12)
                n = int(1.6 * beat * rate)
                t = np.arange(n) / rate
                env = np.minimum(1.0, t / 0.004) * np.exp(-t / 0.35)
                body = _tone(_freq(midi), n, rate, 4) * 0.6 + np.sin(2 * np.pi * _freq(midi - 12) * t) * 0.8
                _add(out, at(b), body * env, (1.0, 1.0))
        elif kind == "arp":
            cycle = sorted(tones)
            for step in range(16):
                pc = cycle[step % len(cycle)]
                midi = 69 + ((pc - 9) % 12) + (12 if step % 8 >= 4 else 0)
                n = int(sixteenth * 0.9 * rate)
                t = np.arange(n) / rate
                body = _tone(_freq(midi), n, rate, 5) * np.minimum(1.0, t / 0.002) * np.exp(-t / 0.08)
                pan = (1.0, 0.7) if step % 2 == 0 else (0.7, 1.0)
                _add(out, int(round((bar * bar_s + step * sixteenth) * rate)), body, pan)
        elif kind == "lead":
            pattern = "x-x---x-xx--x---"
            for step, mark in enumerate(pattern):
                if mark != "x":
                    continue
                pc = tones[(step // 2) % len(tones)]
                midi = 81 + ((pc - 9) % 12)
                n = int(sixteenth * 1.5 * rate)
                t = np.arange(n) / rate
                body = np.sign(np.sin(2 * np.pi * _freq(midi) * t)) * np.minimum(1.0, t / 0.003) * np.exp(-t / 0.2)
                body = sps.sosfilt(sps.butter(2, 5000, "lowpass", fs=rate, output="sos"), body)
                _add(out, int(round((bar * bar_s + step * sixteenth) * rate)), body * 0.5, (1.0, 0.8) if step % 4 else (0.8, 1.0))
    if kind in ("pad", "arp", "lead"):
        out = _reverb(out, rate, 1.6 if kind == "pad" else 0.9, 0.35 if kind == "pad" else 0.25)
    return out


def render_part(spec, set_name, part, tempo, rate=RATE, folded=True):
    """Audio of one part: its second cycle plus the tail (folded) or the first cycle (unfolded)."""
    stem_kind = part.role if part.role in LEVELS else part.stem
    cycles = 2
    samples = _render(stem_kind, spec, set_name, part.variation, tempo, cycles * part.bars, rate)
    bar_s = spec.bar_seconds(tempo)
    length = int(round((part.bars * bar_s + spec.tail_seconds()) * rate))
    start = int(round(part.bars * bar_s * rate)) if folded else 0
    gain = 10 ** (LEVELS.get(stem_kind, -20.0) / 20.0) / max(1e-9, float(np.max(np.abs(samples))))
    return audio_io.Audio(samples[start:start + length] * gain, rate)


def render_parts(spec, set_name, tempo, rate=RATE, variations=None):
    return dict((part.id, render_part(spec, set_name, part, tempo, rate)) for part in spec.parts(set_name, variations=variations))


def mix_of(parts, spec, set_name, tempo):
    """The main mix of a one-pass capture: every part tiled to the longest loop, summed."""
    from ..tiers import tile
    bar_s = spec.bar_seconds(tempo)
    bars = dict((part.id, part.bars) for part in spec.parts(set_name))
    longest = max(bars[part_id] for part_id in parts)
    tiled = [tile(audio, bars[part_id] * bar_s, longest * bar_s).samples for part_id, audio in parts.items()]
    frames = min(item.shape[0] for item in tiled)
    return audio_io.Audio(np.sum([item[:frames] for item in tiled], axis=0), next(iter(parts.values())).rate)


def peaking(samples, rate, freq, gain_db, q=1.0):
    """RBJ peaking EQ."""
    a = 10 ** (gain_db / 40.0)
    w = 2 * np.pi * freq / rate
    alpha = np.sin(w) / (2 * q)
    b = [1 + alpha * a, -2 * np.cos(w), 1 - alpha * a]
    den = [1 + alpha / a, -2 * np.cos(w), 1 - alpha / a]
    return sps.lfilter(np.array(b) / den[0], np.array(den) / den[0], samples, axis=0)


def plant(parts, defect, spec, set_name, tempo):
    """A copy of the parts with one audio defect planted (see DEFECTS); returns (parts, mix or None)."""
    parts = dict((key, audio_io.Audio(value.samples.copy(), value.rate)) for key, value in parts.items())
    rate = next(iter(parts.values())).rate
    mix = None
    if defect == "arp_3k":
        for key in parts:
            if key.startswith("arp"):
                parts[key] = audio_io.Audio(peaking(parts[key].samples, rate, 3000.0, 6.0), rate)
    elif defect == "sub_out_of_phase":
        for key in parts:
            if key.startswith("bass"):
                samples = parts[key].samples.copy()
                low = sps.sosfiltfilt(sps.butter(4, 120.0, "lowpass", fs=rate, output="sos"), samples[:, 1])
                samples[:, 1] = samples[:, 1] - 2 * low
                parts[key] = audio_io.Audio(samples, rate)
    elif defect == "master_reverb":
        clean = mix_of(parts, spec, set_name, tempo)
        mix = audio_io.Audio(_reverb(clean.samples, rate, 1.5, 0.3, seed=3), rate)
    elif defect == "seam_click":
        key = "pad"
        samples = parts[key].samples.copy()
        start = int(0.004 * rate)
        burst = np.random.default_rng(5).standard_normal((int(0.0005 * rate), 2)) * 0.5
        samples[start:start + burst.shape[0]] += burst
        parts[key] = audio_io.Audio(samples, rate)
    elif defect == "unfolded":
        part = spec.part(set_name, "pad")
        parts["pad"] = render_part(spec, set_name, part, tempo, rate, folded=False)
    elif defect == "short_5ms":
        key = next(key for key in parts if key.startswith("bass"))
        parts[key] = audio_io.Audio(parts[key].samples[:-int(0.005 * rate)], rate)
    elif defect == "stem_louder":
        key = next(key for key in parts if key.startswith("arp"))
        parts[key] = audio_io.Audio(parts[key].samples * 10 ** (3.0 / 20.0), rate)
    else:
        raise ValueError("Unknown defect {0!r}; defects: {1}".format(defect, ", ".join(DEFECTS)))
    return parts, mix


def write_take(home, spec, set_name, tempo, parts, mix=None, variations=None, bit_depth=32, mode="tap", note=None):
    """A take folder of synthetic parts (and their mix) the measurement ear can analyse."""
    variations = variations or spec.variations(set_name)
    take_id = next_id(home, set_name, tempo, "".join(variations))
    folder = takes_dir(home) / take_id
    meta = {"id": take_id, "created": report.now(), "set": set_name, "tempo": float(tempo), "variation": "".join(variations),
            "variations": list(variations), "mode": mode, "spec": spec.name, "note": note or "synthetic fixture",
            "parts": {}, "returns": {}, "mixes": [], "passes": [], "warnings": [], "offsets": {}, "formats": {}}
    for part_id, item in parts.items():
        relative = "stems/{0}.wav".format(part_id)
        audio_io.write_wav(folder / relative, item.samples, item.rate, bit_depth)
        meta["parts"][part_id] = {"file": relative, "pass": "p1", "frames": item.frames}
    if mode == "tap":
        mix = mix if mix is not None else mix_of(parts, spec, set_name, tempo)
        audio_io.write_wav(folder / "mix.wav", mix.samples, mix.rate, 32)   # float: a planted defect may push the sum past 0 dBFS
        meta["mixes"].append({"file": "mix.wav", "pass": "p1", "variations": list(variations), "frames": mix.frames})
    (folder / "take.json").write_text(json.dumps(report.clean(meta), indent=1) + "\n")
    return take_id


def normalise(parts, spec, set_name, tempo, variation=None, target=-14.0):
    """Scale every part by one gain so the top tier of `variation` measures `target` LUFS."""
    from ..tiers import tier_sums
    variation = variation or spec.variations(set_name)[0]
    sums, _ = tier_sums(parts, spec, set_name, variation, tempo)
    top = sums[list(sums)[-1]]
    gain = 10 ** ((target - loudness.integrated(top.samples, top.rate)) / 20.0)
    return dict((key, audio_io.Audio(value.samples * gain, value.rate)) for key, value in parts.items())
