# Handoff: NOVA v2 resumed (2026-10-09): new pad, instrument scans, v2 stems and IRIS one-shots delivered

Continues `2026-10-08-nova-v2-paused.md`. Composition resumed with the production knowledge base
(`docs/production/`, PR elleural/ableton-mcp#6) and the same references (TRON: Ares / Nine Inch Noize).

## What Fred said, in order

1. "Resume the composition with your new skill and the same inspiration tracks."
2. "Feel free to replace the base pad altogether." Then: "maybe do another scan of all pad candidates with improved
   judging skill", "take note of the top 10 best candidates, just so I can ask for a review later", "you should do
   for all the instruments we need on this track".
3. Another agent builds the game IRIS (NOVA · IRIS, tetris-nova): "work with that agent and provide the music he wants",
   "use the same inspiration (TRON soundtrack) for the style". The IRIS agent later relayed that Fred "pre approved"
   the v2 render and the IRIS additions.
4. After the pad audition (A base pad, 1 Analog Slow Sweep Pad, 2 Strings Basis Pad with its noise oscillator off,
   3 Pad D built from scratch; matched within 0.05 LU): "you pick for now, continue". I picked **Pad D**.

## The pad

- 282 pad presets scanned with gates calibrated on the base pad (approved) and Dark Throne (rejected): 20 passed;
  noise/air (121) and distortion devices inside presets (76) were the main failures. Method and traps:
  `docs/production/13-preset-scanning.md`.
- **Pad D** (track `pad`): Wavetable, Basic Shapes saw at 66 %, the same saw +12 st at -6 dB, a sine sub -1 octave at
  -10 dB, Classic unison 4 voices at 12 %, 24 dB clean low-pass 1.8 kHz, 60 Hz high-pass, attack 150 ms, release
  2.5 s, 16 voices; then the base pad's Hybrid Reverb (Dark Hall 5 s, 30 %) and Utility (Bass Mono 120 Hz).
  Measured: noise -77 dB, chord off-series -72 dB, width 0.93 (references 0.75-0.95), body +4 dB, in tune within 3 c.
- Placed at the pass-6 pad stem loudness (-22 LUFS; fader -8.9 dB). Capture `neon-140-AB-0009` against pass 6
  (`neon-140-AB-0006`): tier loudness unchanged, mono-sub fail gone, the pad no longer masks the arp at 6-10 kHz.
  **Not yet confirmed by Fred's ear in the mix; not marked best.**

## Live set state (`NOVA v1.als`, unsaved changes: press Cmd+S)

- `pad` = Pad D (renamed from `pad D designed`); its TITLE slot (4) holds the old pad's title clip.
- Muted references and leftovers: `pad old #2` (the previous `pad`, #2 gritty Dark Throne), `base pad` (Fred's base,
  fader -6 dB; alone it peaks near 0 dBFS, 14 dB over the mix's pad level), `pad 1 Analog Slow Sweep Pad` and
  `pad 2 Strings Basis Pad` (finalists, trims on their Utility +16.1 / +12.8 dB), `pad W wider`, `pad L longer`,
  `pad H heavier` (one-change twins, never auditioned), `pad tuned`. Delete them once Fred has decided.
- `iris ...` tracks (muted): the IRIS one-shot instruments (`iris_build.py`).
- Arrangement bars 1-35 hold the last render's layout (NEON-HIGH kick/perc at 180 BPM); tempo is back at 120.

## Delivered

- `/Users/fred/Music/AbletonMCP/Deliveries/nova-v2-music` (manifest version 1, `acceptance.py --strict` passes,
  18.0 MB): NEON v2 at 100-180 BPM from the current mix (pass-6 sounds + Pad D), rendered through v1's pipeline
  (`render_v2.py`: 34-bar arrangement so loop tails continue past bar 33, band kick/perc, fill at bar 33, bounce,
  `cut_stems.py`); 100 BPM needed +0.45 dB over the automatic trim (a LOW-band kick peak). MAINFRAME, title and v1
  one-shots unchanged. Plus the IRIS one-shots of tetris-nova `docs/iris-music-spec.md`: seal per chord, octave
  riser, perfect shell, dash_charged and zone_riser_body (seamless Shepard loops), shatter, deflect, blasts, breach,
  danger, iris_open, fit chime, level_up, tick, click, zone_bank_1..5, zone_riser_peak, and 25 plate plucks A2-A5
  (scientific names, equal RMS). The IRIS agent verified them and ships the folder in its milestone N4.

## Shortlists for Fred's later review

`~/Music/Ableton/NOVA v1 Project/v2-work/top10.md` (and `top10_<role>.json`): pad, bass, arp, lead; kick and perc
after the kit scan. Notes in the file: the gates are stricter than Fred's taste for arp and lead (his pass-6 sounds
fail them); acoustic emulations are counted off-palette; the current bassA is almost pure sub (51 Hz centroid,
inaudible on a phone speaker in the capture's phone check).

## Next

1. Fred judges Pad D in the mix (labelled, loudness-matched A/B against the base pad if he wants it; `ab_pad.py`).
2. Bass on phones: offer a bass with more 200 Hz-1 kHz harmonics (Face Bass, Wub Bass) or a mid-bass layer, A/B.
3. Gentle mix pass: the 100 BPM LOW-band kick peak; no per-stem limiters.
4. MAINFRAME v2 and a title re-render with the new pad; then refresh the delivery folder (keep the layout).
5. Clean up the audition tracks after Fred decides; save the set.
6. The scanners and the A/B player live in the work folder; turning them into repo tools is a separate task.
