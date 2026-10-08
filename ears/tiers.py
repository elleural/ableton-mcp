"""Loop playback as the game does it, and tier sums (PRD section 8, soundtrack PRD sections 6 and 8).

The game never loops a file natively: it starts a new iteration of each stem on its own bar clock,
plays the whole file (loop body plus the 50 ms tail), and crossfades the previous iteration out over
10 ms with an equal-power curve starting at the seam; the old voice stops 60 ms after the seam.
`tile()` renders exactly that, so tier sums hear the seams the player hears.
"""
import numpy as np

from .audio import Audio


def crossfade_curves(frames):
    """Equal-power fade-out and fade-in over `frames` samples."""
    if frames <= 0:
        return np.zeros(0), np.ones(0)
    phase = (np.arange(frames) + 0.5) / frames * (np.pi / 2.0)
    return np.cos(phase), np.sin(phase)


def tile(audio, body_seconds, total_seconds, crossfade_ms=10.0, stop_ms=60.0):
    """Play `audio` as a loop of `body_seconds` for `total_seconds`, game style; returns Audio (stereo).

    Iteration k starts at k * body. Each iteration's file is played whole; from the next seam on, its
    remaining tail fades out over `crossfade_ms` and is cut `stop_ms` after the seam. The output has
    the length total + the file's tail, so the last iteration keeps its natural end.
    """
    samples = audio.stereo()
    rate = audio.rate
    body = body_seconds * rate
    length = int(round(total_seconds * rate)) + max(0, samples.shape[0] - int(round(body)))
    out = np.zeros((length, 2))
    fade = int(round(crossfade_ms / 1000.0 * rate))
    fade_out, fade_in = crossfade_curves(fade)
    iterations = int(np.ceil(total_seconds / body_seconds - 1e-9))
    for k in range(iterations):
        start = int(round(k * body))
        chunk = samples.copy()
        if k > 0 and fade:
            head = min(fade, chunk.shape[0])
            chunk[:head] *= fade_in[:head, None]
        if k < iterations - 1:
            seam = int(round((k + 1) * body)) - start
            if seam < chunk.shape[0]:
                end = min(chunk.shape[0], seam + fade)
                chunk[seam:end] *= fade_out[:end - seam, None]
                chunk[end:] = 0.0   # faded out; the voice stops `stop_ms` after the seam

        stop_at = min(length, start + chunk.shape[0])
        out[start:stop_at] += chunk[:stop_at - start]
    return Audio(out, rate)


def tier_sums(parts, spec, set_name, variation, bpm, total_bars=None, bars=None):
    """{tier: Audio} cumulative tier sums for one variation, each part tiled to the longest loop.

    parts: {part id: Audio} (cut files: bars x bar length + tail). bars: {part id: loop bars in the
    file} when a take was cut shorter than the spec's loops (a `bars` quick check). Missing parts are
    skipped and listed in "missing". Returns (sums, missing).
    """
    tiers = spec.tier_parts(set_name, variation)
    bar = spec.bar_seconds(bpm)
    crossfade = float(spec.target("crossfade_ms", 10.0))
    override = bars or {}
    bars = dict((part.id, float(override.get(part.id) or part.bars)) for part in spec.parts(set_name, variations=[variation]))
    longest = total_bars or max(bars.values())
    rendered, missing = {}, []
    for part_id in bars:
        if part_id not in parts:
            missing.append(part_id)
            continue
        rendered[part_id] = tile(parts[part_id], bars[part_id] * bar, longest * bar, crossfade)
    sums = {}
    rate = next(iter(parts.values())).rate if parts else 48000
    for tier, members in tiers.items():
        present = [rendered[part_id] for part_id in members if part_id in rendered]
        if not present:
            continue
        frames = max(item.frames for item in present)
        total = np.zeros((frames, 2))
        for item in present:
            total[:item.frames] += item.samples
        sums[tier] = Audio(total, rate)
    return sums, missing


def loop_body(audio, bars, bpm, beats_per_bar=4.0):
    """The loop body of a cut file (without its tail)."""
    seconds = bars * beats_per_bar * 60.0 / float(bpm)
    return audio.slice(0.0, seconds)
