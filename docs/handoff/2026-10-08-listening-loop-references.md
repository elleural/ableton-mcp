# Handoff: listening loop phase 4, references and the meter (2026-10-08)

Builds on [2026-10-07-listening-loop.md](2026-10-07-listening-loop.md). Plan and decisions:
[listening-loop-plan.md](../listening-loop-plan.md) §8; hardware findings: [spikes.md](../spikes.md) "Meter and
references"; calibration: [listening-loop-calibration.md](../listening-loop-calibration.md) §7.

## What exists

- `ref` tool (and `uv run ears ref ...`): `measure` plays Spotify tracks in the desktop app and meters them through
  the Scarlett's Loopback (inputs 3-4), whole track, once; sections "track", "full", "sparse" (or named spans);
  `add` for owned files; `list`, `play`/`pause`, `setup` (M6), `status`/`cancel`, `delete`. Long-polls like
  `capture`.
- `meter` tool (and `ears meter`): what the Mac plays now, `source="live"` (Live's output, absolute figures) or
  `"external"` (shape only).
- `compare(take, "refs")` / `"refs:sparse"` / `"ref:<name>[:<section>]"`; `analyze_audio(take=...)` runs
  `audio.balance` against the stored references' full-section envelope.
- `ears.profile` (the level-independent measurement set), `ears.meter`, `ears.player`, `ears.refs`,
  `measure.tempo_estimate`.
- References live in one shared store: `~/Music/AbletonMCP/Ears/refs/` (`EARS_REFS` overrides).

## Frederic's references

*Nine Inch Noize* (Nine Inch Nails × Boys Noize), album `spotify:album:7lcpCG4RBy3njzxHXlhOnp`. The four he
pointed at (album tracks 2, 3, 8, 12):

| Track | Spotify id | Length |
| --- | --- | --- |
| Vessel | 66wNW3FvUSyNmeZ7NSejha | 4:17 |
| She's Gone Away | 2brRKInIh1aJ2r0dcZtNzm | 3:33 |
| Closer | 32ZmFcP0qeEIuXtO6TDZ1K | 5:44 |
| As Alive As You Need Me To Be | 3cCpBRsf5vF9W8vUfcoTkf | 4:15 |

## State

- Verified on this Mac: Loopback is bit-exact; a second process reads it while Live runs; the calibration tone
  from Live and M3 pass (`uv run pytest tests/live/test_meter.py`); M1, M2, M4, M5 pass offline.
- **Not yet verified: Spotify by AppleScript.** macOS's "allow claude to control Spotify" prompt was pending; every
  call timed out. Once allowed (System Settings > Privacy & Security > Automation > claude > Spotify):
  `ref(action="measure", uri=[the four ids above])`, about 18 minutes of playback with Live stopped.
- **M6 is Frederic's:** Spotify > Settings > Playback: Normalize volume off, Crossfade songs off; volume 100; System
  Settings > Sound > "Play sound effects through" not the Scarlett; then `ref(action="setup", confirm=True)`.
- The NOVA set was crash-recovered and still unsaved: it carries the e2e test's leftovers (three
  `[test:e2e_release]` tracks, return C, two scenes) and 21 tracks re-armed by the recovery. Clean them up only
  after Frederic saves, deleting one object per call.

## Next

1. Measure the four references, then `compare` the latest NOVA takes against them and hand the gaps to the
   composer (band balance, dynamics, width, density; tempo and key are information).
2. Phase 3 (listeners) still waits for PRD §15 q3-q4 (Gemini key and permission; embeddings policy).
3. Tempo estimates of loop-built mixes often come out at half tempo (NOVA's NEON 120-180); the runner-up is the
   true tempo. A better pulse detector would help if tempo ever gates anything (it does not now).
