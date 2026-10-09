# Mixing in Live 12 like a pro

Digest 06 of `docs/production/`. Researched 2026-10-08 for Live 12.4.6 Suite driven through AbletonMCP, for agents that
cannot hear and a producer who judges by ear. Levels, meters and loudness maths are in
[05-gain-staging-and-metering.md](05-gain-staging-and-metering.md); kick and bass design in
[04-drums-and-low-end.md](04-drums-and-low-end.md); sound design in [03-sound-design-recipes.md](03-sound-design-recipes.md);
mastering and delivery in [07-mastering-and-loudness.md](07-mastering-and-loudness.md); adaptive stems in
[10-game-audio-adaptive-music.md](10-game-audio-adaptive-music.md); measuring without ears in
[11-listening-without-ears.md](11-listening-without-ears.md); device parameters in
[12-live-devices-reference.md](12-live-devices-reference.md).

## If you remember five things

1. **Balance first with faders and pan, process second, and start from the producer's approved mix.** A mix that does
   not work on faders alone has an arrangement or sound-choice problem that EQ will not fix. Never rebuild what the
   producer already approved; improve it in small, labelled, reversible steps.
2. **Subtract before you add, and never judge a part on solo.** Cut to fix, boost to flavour; narrow cuts, wide small
   boosts; high-pass what has no business in the low end (but keep a deliberate low root, in mono). Make room by *role*
   (who owns 40-80 Hz, who owns 2-4 kHz), not by EQing every track.
3. **Dynamics in small doses, with a stated purpose.** About 1-3 dB on buses, 2-6 dB on a drum that needs it, nothing on a
   synth that is already steady. Sidechain is a mixing tool, not a style requirement. A limiter belongs at the end of
   one chain, never on every stem.
4. **Space on sends, width above the bass.** Returns at 100 % wet, EQ'd on both ends, short pre-delay, ducked; pads wide
   above ~200 Hz with a mono low end; check mono every time width changes.
5. **Over-processing is the main way an agent ruins a mix.** Change one thing, measure, A/B at matched loudness, keep a
   restore point, and stop when the remaining problems are taste. Numbers diagnose; the producer decides.

---

## 0. What the 2026-10-08 failure teaches

| What happened | Rule it breaks | Where covered |
| --- | --- | --- |
| Sounds chosen by spectral distance to full-mix references | A full-mix spectrum is not a target for one stem; measurements diagnose, ears choose | 03, 11; section 11 below |
| True Peak limiters on every stem (+12 dB into -14 dB ceilings), broad EQ cuts and new faders on every track at once | One change at a time; no per-stem limiters; one shared gain for loudness | sections 5.8, 12 |
| "Garbage" result; restoring the earlier mix fixed it | Always keep a restore point; the previous mix is the baseline | sections 2, 12.3 |
| Saturating whole chords sounded out of tune; chorus on noise sounded flangy | Intermodulation and comb filtering are real; treat polyphony and noise differently | sections 6, 8 |
| Auditions unlabelled; the producer's chosen sound replaced; no loudness-matched A/B | Label, level-match, and iterate on the producer's sound instead of swapping it | sections 2, 12.3; 05 section 7.2 |

---

## 1. The order of work

Professionals converge on the same sequence: organise, build a static balance, fix problems by subtraction, add dynamics
where there is a reason, add space, then movement and checks. Puremix calls the first musical milestone a *static
balance*: only faders and pan, no EQ, compression or effects, and if it is not compelling at that point the remaining
moves are refinement and persistent problems point to the arrangement
([Puremix](https://www.puremix.com/blog/where-to-start-when-you-open-a-mix-the-static-balance-method)). iZotope's
workflow runs from anchor (drums for rhythm-driven music) to balance and EQ, dynamics, reverb and delay with panning,
section-by-section evolution, and automation
([iZotope, how to mix](https://www.izotope.com/en/learn/how-to-mix-music.html)). SOS adds: check the tracks first, group
into subgroups, use processing sparingly, and take breaks
([SOS, Mixing Essentials](https://www.soundonsound.com/techniques/mixing-essentials)).

| # | Stage | Live tools | Gate before moving on |
| --- | --- | --- | --- |
| 0 | Restore point; list protected sounds | `capture(note="baseline")`, `takes(action="keep")` | A take exists to compare against and restore |
| 1 | Gain stage | Utility, instrument volume, `set_clip(gain_db)` | 05 section 2: peaks and RMS in range, no clipped samples |
| 2 | Static balance and pan | `set_mixer` | Main peaks -6 to -3 dBFS; still balanced in a mono check |
| 3 | Fix problems | polarity, EQ Eight (subtractive), Utility | Band shares moved by no more than ~1.5 dB; nothing new broke |
| 4 | Dynamics, only with a purpose | Compressor, Glue Compressor, `set_sidechain`, Drum Buss | Crest and loudness change within budget (section 12.2) |
| 5 | Space | return tracks, Reverb/Hybrid Reverb/Echo | Correlation not collapsing; low band not muddier; tails vs chord changes |
| 6 | Width | Utility Width and Bass Mono, EQ Eight in M/S | `mono_sub_loss_db` <= 1 dB; correlation >= 0 |
| 7 | Colour | Saturator, Drum Buss, Roar | Matched A/B; no new out-of-key energy; crest drop <= 1 dB per device |
| 8 | Bus glue | Glue Compressor on groups | Gain reduction <= 3 dB |
| 9 | Automation | `write_automation` | End values return to base; the producer told |
| 10 | References and translation | `compare("latest", "refs")`, the producer's listening | Gaps explained; producer approves |

The sequence is a default, not a law: Mike Senior-style mixing alternates between mono and stereo and revisits stages as
other moves change the balance.

---

## 2. Prepare: organisation, protected sounds, restore points

- **Organise.** Group by role (Drums, Bass, Music, FX) with `create_bus(name, sources)` (an audio track that receives the sources' output, not a Live Group Track), one colour per role, unique names
  (the MCP identifies tracks by name). Add returns with `create_track("return", "Short Room", device="Reverb")`.
- **Protect what the producer approved.** Write down the approved sounds and mixes. Mixing is a different job from sound
  design: if a sound is wrong, say so and ask; do not swap it. Iterate *on* the approved sound.
- **Restore points.** `capture(note="baseline")` then `takes(action="keep", take=<id>)`. To go back,
  `takes(action="restore", take=<id>, dry_run=True)` first, then without `dry_run`. Device additions and removals since the
  take are listed, not undone; plugin state outside Live's parameters is not covered. Also `undo` for the last step.
- **Keep the previous version on a muted twin track** (`duplicate_track`) while you try a change, named "A (approved)" and
  "B (what changed)", loudness-matched (05 section 7.2).
- **Check polarity and phase** between layered sounds before EQ: kick vs bass, doubled snare layers. Utility has a
  per-channel Phase invert; the check is whether a sum is louder or quieter in the low band after flipping.
- **Switch off, do not delete,** devices you are unsure about; the listening loop's snapshot lists devices added or
  removed since a take.

> **For an agent.** Before any change: `get_mixer()`, `get_devices(track)` for tracks you will touch, and
> `capture(note="baseline")`. Report to the producer which sounds you consider protected. If the next move needs more than
> two tracks changed at once, split it.

---

## 3. The static mix: levels and pan

**Procedure** (Puremix, iZotope, SOS): start from silence, bring in the anchor (in electronic music the kick, then the
bass), add parts in order of importance, balance each against what is already there, then pan, then listen to the whole
song. Set levels low enough to leave headroom; SOS suggests listening from outside the room or at low volume to judge
balance.

**Mono, then stereo, then mono.** SOS (Mike Senior): a balance in mono forces you to separate parts by level and tone, and
mixes that sound big in stereo often collapse in mono. Alternate: balance in mono, pan in stereo, re-check mono, finish in
stereo; do not adjust pans while listening in mono
([SOS, should I mix in mono?](https://www.soundonsound.com/sound-advice/q-should-be-mixing-mono)).

**Panning.**

- Keep kick, bass, snare or clap and the lead near the centre; they carry impact and survive mono
  ([Senior on panning](https://www.soundonsound.com/sound-advice/q-are-there-any-panning-rules-maintaining-mono-compatibility)).
- Live's pan law is constant power: 0 dB at the centre and **+3 dB** for a source panned fully to one side, so a hard-panned
  source jumps in level in that channel and falls about 3 dB in the mono sum
  ([Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/)). Re-balance after panning.
- Senior personally limits panned mono sources to about 85 % to avoid headphone dislocation (his preference, not a
  standard).

**Order of importance** (starting hypothesis, not a source): kick, bass, the hook or lead, drums and percussion, pads and
textures, effects. If the producer has an approved balance, it beats this list.

> **For an agent.** Balance is a taste decision. Use the tools to make small, labelled moves and to catch obvious faults:
> `get_mixer()` for the state; `set_mixer(track, volume_db=..., pan=...)`; after a pass, `bounce` and `analyze_audio` to
> confirm the Main still peaks at -6 to -3 dBFS and the stereo correlation is healthy. Numbers can say "this stem sits 15 dB
> below everything" or "two parts have the same band energy at the same time"; they cannot say the balance is right.
> Never move more than ~2 dB on a part the producer already balanced without asking. A stem-by-stem loudness normalise is
> wrong (05 section 2).

---

## 4. EQ

### 4.1 Principles

- **Cut to fix, boost to flavour.** Subtractive EQ solves masking and mud; boosting adds character and is easy to overdo
  ([Puremix on EQ](https://www.puremix.com/blog/how-to-eq-a-mix-when-to-cut-when-to-boost-and-where-to-start)).
- **Wide, gentle boosts; narrow cuts for problems.** SOS and Puremix agree: use narrow, deep cuts for a specific ring or
  harshness and wide, small boosts for tone ([SOS, Mixing Essentials](https://www.soundonsound.com/techniques/mixing-essentials)).
- **Do not perfect the solo.** A beginner's habit is to polish a part alone; it then clashes in the mix. Judge in context
  (Puremix).
- **High-pass the parts that are not bass.** Remove low-end build-up across tracks before chasing mud. For recorded audio
  this removes rumble; for virtual instruments it is about *masking*, not noise (one practitioner blog applies the
  high-pass habit to every track that is not a virtual instrument: [weak](https://www.musicguymixing.com/subtractive-eq/)).
  SOS's Mixing Essentials takes everything below 200 Hz off non-bass parts, which is too blunt for synths with a
  deliberate low root (see 13.3).
- **The ear is most sensitive between roughly 2.5 and 5 kHz** (iZotope, psychoacoustics): harshness there is the most
  audible, so cuts there are the most valuable and boosts the most dangerous.

### 4.2 Where to look (practitioner convention)

| Region | Approx. range | Common issue or character | Typical move |
| --- | --- | --- | --- |
| Sub | 20-60 Hz | weight; rumble below ~25-30 Hz | gentle high-pass at 25-30 Hz on parts with no content there; keep mono |
| Bass body | 60-200 Hz | thickness; kick vs bass fight; boom | complementary carve between kick and bass |
| Low mids | 200-500 Hz | mud, boxiness, cheap tone | narrow 2-4 dB cuts or a wide shelf cut on layers that accumulate here |
| Mids | 500 Hz-2 kHz | honk, nasal, core of leads | cuts to clear space for the hook |
| Upper mids | 2-5 kHz | presence, aggression, harshness | careful narrow cuts; small boosts only |
| Highs | 5-10 kHz | hiss, sibilance, brightness | low-pass noisy layers; tame resonances |
| Air | 10 kHz and up | openness | usually leave alone |

These bands are standard practitioner folklore: the pages I read mention the 300-500 Hz region, 1-2 kHz, 3-5 kHz presence and
10 kHz air in passing but give no single table. Treat them as where to *search*, never as where to cut.

### 4.3 Masking and complementary EQ

iZotope's definition: masking occurs when two similar sounds play together and the louder one partly hides the other;
common pairs are kick and bass in the sub, bass and guitars or snare and guitars in the mids, and any layers in the same
band ([iZotope, masking](https://www.izotope.com/en/learn/what-is-frequency-masking)). Fixes, in this order of
transparency: arrange so the parts alternate, change levels, **complementary EQ** (boost a band in one part, cut the same
band in the other), pan, sidechain or dynamic EQ.

### 4.4 Resonances and dynamic EQ

Use a narrow boost swept slowly to find a ringing frequency, then cut it. In EQ Eight, the **headphone Audition** button
solos an individual band so you hear what that filter is acting on. Live's EQ Eight is a static EQ in its documented feature set (eight
bands; low and high cuts at 12 or 48 dB per octave; stereo, left/right or mid/side processing; Adaptive Q; an optional
spectrum display) ([Live manual](https://www.ableton.com/en/manual/live-audio-effect-reference/)).

When a problem appears only on some notes or only while another part plays, a **dynamic EQ** is the pro tool: iZotope lists
taming resonances, reducing masking (for example a wide cut at 60-100 Hz on the bass triggered by the kick instead of audible
sidechain compression), controlling boosts, and emphasising transients
([iZotope, dynamic EQ](https://www.izotope.com/en/learn/when-to-use-dynamic-eq-in-a-mix)). Options in a Live set:

- Live's own approximations: **Multiband Dynamics** (band-wise thresholds above and below; it has a sidechain, whose toggle
  moved into the device header in 12.2) or a **Compressor with the sidechain EQ** shaping what triggers it. Routing a
  sidechain to anything other than Compressor may need the UI: `set_sidechain` routes Compressor only.
- Third-party, the usual pro choice: FabFilter Pro-Q, oeksound
  [soothe3](https://oeksound.com/plugins/soothe3) (a dynamic resonance suppressor), and the free
  [TDR Nova](https://www.tokyodawn.net/tdr-nova/) (four dynamic EQ bands plus filters, external sidechain; VST/AU).

> **For an agent: EQ protocol.**
> 1. Say *why* before touching: "kick and bass both heavy at 60-80 Hz", "pad piles up at 300 Hz".
> 2. `add_device(track, "EQ Eight")`, then `get_device(track, "EQ Eight")` to read the parameter names (12.4.6: for each band n = 1-8
>    `n Filter On A`, `n Filter Type A`, `n Frequency A`, `n Gain A`, `n Q A`, and the same with B for the second set used by L/R or mid/side,
>    plus `Output`, `Scale` and `Adaptive Q`; bands 1-4 start on, band 2 is a Bell at 200 Hz). Use
>    `set_device_parameters(track, "EQ Eight", {"2 Frequency A": "150 Hz", "2 Gain A": "-3 dB"})` with display strings.
> 3. **One track per step.** Budget: boosts <= +3 dB; broad cuts <= -4 dB; narrow notches up to -10 dB for a real
>    resonance; <= 3 active bands per track. These are digest guardrails, not industry rules. Larger moves are normal when
>    *designing* a kick's tone (Attack's kick chains swing 10+ dB), not when balancing.
> 4. Measure: bounce the passage before and after. `analyze_audio.spectrum` has only five broad bands, so a narrow 4 dB cut
>    barely moves one of them; for narrow moves use `compare` (third-octave, loudness-matched). Expect the intended region to
>    move by a fraction of the cut and everything else by under ~0.5 dB. Bad results: a broad cut that drops a whole band share,
>    several regions moving at once, the loudness changing by more than 0.5 LU because the EQ added or removed a lot.
> 5. Match loudness before offering an A/B (05 section 7.2). A broad boost always "sounds better" for a few seconds.
> 6. Ask the producer when the move changes the *character* of an approved sound, not only its balance.

---

## 5. Compression and dynamics

### 5.1 Why, and on what

Synthetic and sampled parts are already consistent, so the "level a performance" job is largely absent: Musician on a Mission's
cheat sheet notes that samples and virtual instruments do not need compression for dynamic control
([PDF](https://mastering.com/wp-content/uploads/2017/07/COMPRESSION-CHEAT-SHEET.pdf), weak). Compression in electronic music is for:

- **groove and pump** (sidechain),
- **punch**: shaping a drum's attack versus its body,
- **glue** on buses,
- **taming peaks** before a nonlinear stage,
- **density** via parallel processing.

If you cannot name which, do not insert a compressor.

### 5.2 Live's devices

- **Compressor.** Modes: *Peak* (reacts to short peaks; precise, aggressive), *RMS* (responds to sustained level; more musical),
  *Expand* (a ratio of 1:2 raises the output 2 dB for each dB above the threshold); the parameter is `Model`, and a Compressor added with `add_device` starts on RMS, so set Peak where this chapter says Peak. Controls: Threshold, Ratio, Attack, Release
  with **Auto Release**, **Knee** (0 dB is a hard knee; higher values start compressing gradually as the signal nears the
  threshold, which sounds smoother), **Lookahead** (0, 1, 10 ms), **Makeup** (automatic compensation when threshold or ratio change), **Dry/Wet**
  (built-in parallel), **Output**. Sidechain: any internal routing point as source, SC Gain, Mix, an EQ with several filter
  types, and a **Listen** (headphone) button to hear only the key signal. Display modes: collapsed, transfer curve, activity
  ([Live manual](https://www.ableton.com/en/manual/live-audio-effect-reference/)).
- **Glue Compressor.** The bus compressor. Stepped attack values in milliseconds and release values in seconds with **Auto**
  (a slow base plus fast reaction), stepped ratios (2, 4 and 10), **Range** (maximum reduction; very
  low values emulate the hardware, values between -40 and -15 dB act like a dry/wet; the API shows it as a positive 0-70 dB, 70.0 by default),
  **Soft Clip** (`Peak Clip In`: a waveshaper capping output near -0.5 dB, which distorts when active), a gain-reduction needle and
  Peak Clip LED; `Dry/Wet`; `Output` (makeup, 0 to +20 dB); sidechain with EQ
  ([Live 11 manual](https://www.ableton.com/en/live-manual/11/live-audio-effect-reference/)). `Attack`, `Ratio` and `Release` have no item list in the
  12.4.6 dump: they are raw steps (0-6, 0-2, 0-6), so read the display back after setting one.
- **Multiband Dynamics** for band-wise control; **Drum Buss** (a fixed drum compressor via Comp, Trim, three drive types, Crunch,
  Damp, Transients above 100 Hz, Boom) and **Limiter** (12.1: smoother release, Soft Clip and True Peak modes, Mid/Side routing,
  Maximize).

### 5.3 Starting points by intent

All numbers are starting points that disagree between sources (see Open questions). Attack and release are the controls
that matter; iZotope's rule is that you can usually afford only one of ratio, attack and release being extreme.

| Intent | Mode | Ratio | Attack | Release | Typical reduction | Basis |
| --- | --- | --- | --- | --- | --- | --- |
| Catch stray peaks | Peak | 4-6:1 | < 5 ms | 30-50 ms or Auto | 1-3 dB, on peaks only | iZotope |
| Even a sustained part | RMS | 2-3:1 | 15-50 ms | 100-300 ms | 2-4 dB | iZotope |
| Level a drum | Peak | about 3:1 | about 1 ms | about 100 ms | all but the softest hits | SOS drums |
| Punch: let the transient pass | Peak or RMS | 3-4:1 | 10-30 ms | 80 ms or more, tempo-based | 2-5 dB | SOS drums |
| Drum bus glue | Glue | 2:1 | 10-30 ms | 0.2-0.4 s or Auto | 2-4 dB (SOS); Attack Magazine uses 4-5 dB on dense dance mixes | SOS, Attack |
| Main glue | Glue | 1.5-2:1 (Glue's lowest step is 2:1) | 30-80 ms (Glue's longest step is 30 ms) | 100-250 ms | 1-2 dB (SOS: even 1 dB makes a difference) | SOS, iZotope |
| Parallel density | Peak | high | fast | medium | 7-8 dB (Attack's kick) up to 20+ dB (iZotope) on the compressed copy, blended about 20-35 % | SOS, iZotope, Attack |
| Sidechain duck | Peak | 4:1 or more | 0.1-5 ms | tempo-based, 50-200 ms | 3-8 dB for pads and bass; more for an obvious pump | Ableton, project defaults |

Gentle ratios stay transparent: iZotope notes that ratios under 1.5:1 can deliver 6-7 dB of reduction, and a very heavy
copy blended at around 35 % behaves like 3-4 dB of effective reduction
([iZotope, transparent compression](https://www.izotope.com/en/learn/tips-for-more-transparent-compression)).

### 5.4 Timing to the tempo

Release is the groove control: set it so the reduction falls back to about 0-1 dB before the next hit, so the compressor
breathes in time with the track ([Musician on a Mission](https://mastering.com/wp-content/uploads/2017/07/COMPRESSION-CHEAT-SHEET.pdf), weak; the same idea
appears in SOS's and iZotope's advice to match release to the groove). Milliseconds per note: `60000 / BPM` per beat, then divide.

| BPM | 1 beat | 1/8 | 1/16 |
| --- | --- | --- | --- |
| 100 | 600 ms | 300 | 150 |
| 120 | 500 ms | 250 | 125 |
| 128 | 469 ms | 234 | 117 |
| 140 | 429 ms | 214 | 107 |
| 180 | 333 ms | 167 | 83 |

SOS on drums: a longer attack lets the transient pass and reduces only the sustain; a very fast attack and release soften the
onset ([SOS, drum compression](https://www.soundonsound.com/techniques/compression-fashion-drum-sound-you-want)). On release,
a fast one makes the material sound louder but risks pumping and bass distortion, a slow one sounds quieter and duller
([SOS, limiter release](https://www.soundonsound.com/sound-advice/q-what-release-settings-should-use-limiter)).

### 5.5 Parallel and serial

- **Serial.** Two compressors each doing 2-3 dB are more transparent than one doing 5-6 dB; put a fast, higher-ratio unit
  first to catch peaks, then a slower, lower-ratio one. Ratios multiply (4:1 then 2:1 behaves like 8:1)
  ([iZotope](https://www.izotope.com/en/learn/tips-for-more-transparent-compression)).
- **Parallel.** Blend a heavily compressed copy under the dry signal. It lifts sustain and density while the dry copy keeps
  transients (SOS calls it "uplift" compression) ([SOS, parallel compression](https://www.soundonsound.com/techniques/parallel-compression)).
  In Live use a return track with a Compressor at 100 % wet, a Rack with two chains, or simply the Compressor's own Dry/Wet.
  Attack Magazine's microhouse mix sent the kick to a parallel return around -5 dB and used 7-8 dB of reduction
  ([Attack](https://www.attackmagazine.com/technique/tutorials/mixing-microhouse/)). A cheat sheet recommends parallel
  compression when compressing a whole drum bus, to avoid audible pumping on the cymbals
  ([Musician on a Mission](https://mastering.com/wp-content/uploads/2017/07/COMPRESSION-CHEAT-SHEET.pdf), weak).

### 5.6 Buses and the Main

- **Mix through the bus compressor from the start**, not after the mix is done, so you balance against it (SOS; iZotope).
  Settings: 1.5-2:1, medium attack (iZotope: 50-80 ms; SOS's mastering engineer: about 50 ms), release 100-250 ms matched to
  the groove, **1-3 dB of reduction**. iZotope warns that more than 3:1 on a mix bus is too much.
- **Sidechain filter on the bus compressor.** Filtering some lows out of the key signal stops a loud kick or bass from
  driving the pumping (SOS guide to mix compression).
- In dance music the kick drives the bus compressor; SOS's gentler guidance and Attack Magazine's 4-5 dB differ, see Open
  questions.
- **Project caveat.** In the adaptive soundtrack, stems must make sense in any subset, and the listening loop expects the
  stems plus returns to null against the Main. Glue *inside* each stem's group, not on the Main, and leave the Main chain
  empty (see 10). Likewise do not bake kick-keyed ducking into a pad, arp or bass stem: the kick is absent in tiers T1-T2
  (see 04, section 3.3).

### 5.7 Sidechain

Use it to give the kick room or to make a pad breathe. Ableton lists the kick-driven duck, accenting rhythm, keeping long
reverb tails from smothering drums, and frequency management, and says it also works through Gate, Multiband Dynamics and
Auto Filter ([Part 2](https://www.ableton.com/en/blog/sidechain-compression-part-2-common-and-uncommon-uses/),
[Part 1](https://www.ableton.com/en/blog/sidechain-compression-part-1/)). Attack Magazine reminds producers that classic
house and techno often had no surgical separation, and overlap can add cohesion
([Attack, rules to break](https://www.attackmagazine.com/technique/tutorials/5-mixing-rules-you-should-be-breaking/)).

> **For an agent: sidechain.**
> `set_sidechain(track="Pad", source="Kick", threshold_db=-30, ratio=4, attack_ms=1, release_ms=120)` creates or reuses a
> Compressor on the target (channel "Post FX" by default; it leaves `Model` as found, so a new one is on RMS: set Peak if you want the table's Peak). Choose the release from the table above so the gain returns
> before the next kick; choose threshold so the reduction is about 3-6 dB on the loudest kick for pads and 4-8 dB for bass;
> a deeper pump is a style decision to ask about. In the NOVA stems, tiers T1-T2 play without the kick: compose the gaps instead
> and keep any baked duck small (04, section 3.3). Verify by bouncing the ducked stem alone and measuring the duck depth with
> short `analyze_audio` sections: for example 80 ms just after a kick and 80 ms just before the next one (seconds =
> beats x 60 / BPM), then compare `rms_dbfs` in the two sections; the difference is the depth. (`loudness_curve` is too slow
> for this: its steps are a second or more.) If the ducked stem loses its body in mono, shorten the release or filter the key.

### 5.8 Limiting

A limiter is a compressor with a very high ratio and is for catching brief peaks (SOS: a few dB at most). It does not belong
on stems as a loudness tool. If you use one as a safety while pushing distortion, set its ceiling above the working level so
it normally does nothing; Attack Magazine describes the same safety use
([Attack, Organised Chaos](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/)).

> **For an agent: compression protocol.** State the purpose; add the device; set the values from 5.3; match output loudness;
> bounce before and after; read `levels.crest_factor_db`, `loudness.integrated_lufs` and the profile's `dynamics_spread` and
> `plr_db` (`compare`). A compressor that drops a sustained stem's crest by more than ~3 dB, or a drum's by more than ~6 dB,
> is working harder than the budget. The gain-reduction meters are visual only; infer the reduction from the before/after
> difference. **Ask the producer** when the intent is "make it punchier" or "more aggressive": those are taste calls.

---

## 6. Saturation and distortion

**Why.** Distortion adds harmonics that make a part feel louder, thicker and more forward without raising peaks, and it ties
layers together. **Live's devices:** Saturator (several curves; Live 12.1 added a Bass Shaper curve; Soft Clip), Drum Buss
(Soft, Medium, Hard drive; Crunch for mid-high distortion; Damp), Roar (up to three saturation stages in series, parallel,
mid/side or multiband), Pedal, Overdrive, Dynamic Tube (envelope-driven bias), Amp and Cabinet, Redux, Erosion, Vinyl Distortion
([Live 12 features](https://www.ableton.com/en/live/all-new-features/), [Live 12.1](https://www.ableton.com/en/blog/live-121-is-out-now/),
[manual](https://www.ableton.com/en/manual/live-audio-effect-reference/)).

### 6.1 Intermodulation: why chords and noise suffer

A nonlinear device acting on a single tone adds *harmonics* of that tone. Acting on several tones at once it also adds
*sum and difference frequencies* (f1 + f2, f1 - f2, 2f1 - f2, 2f2 - f1), which are not harmonically related to the notes and are
heard as dissonant ([Wikipedia, intermodulation](https://en.wikipedia.org/wiki/Intermodulation)). That is why guitarists play
power chords through heavy distortion: root and fifth keep the products musically related, while thirds and complex voicings
turn messy ([Wikipedia, power chord](https://en.wikipedia.org/wiki/Power_chord)). This is the likely cause of the
out-of-tune impression the producer had when a whole chord went through a Saturator.

**Rules for polyphonic and noisy material**

- Prefer **low drive and soft curves**; stop as soon as the part gets thicker, not when it gets dirty.
- **Saturate before the notes are summed when possible** (the instrument's own drive or filter stage), or saturate mono lines
  and drums rather than the pad.
- **Keep the distortion path out of the low register.** Intermodulation in the bass makes phantom low notes that sound like wrong
  notes. Attack Magazine cuts low frequencies on distorted channels to keep bass clear and uses a clean copy for the low end
  ([Attack, Organised Chaos](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/)).
  In Live use a Rack with parallel chains (a clean full-range chain and a high-passed distorted chain), or Roar in multiband mode.
- **Blend in parallel** (10-30 %) and **match loudness** before judging; harmonic saturation raises RMS.
- Below about 130 Hz (Live C2) only roots, fifths and octaves; major thirds from about 165 Hz (Live E2); minor thirds and seconds higher still (see the NOVA handoff, 04 section 3.2 and 08).
- **Chorus and ensemble on noise** comb-filter into a flanger sound. Keep Dry/Wet low, use the Chorus-Ensemble wet high-pass
  (`HP On`, `HP Freq`: 20 Hz to 2 kHz) so the effect stays out of the low end, and avoid it on noise layers
  ([Live manual](https://www.ableton.com/en/manual/live-audio-effect-reference/)).

> **For an agent.** Add one saturation device per step. Measure: loudness change (match it), `crest_factor_db` (a drop of up
> to ~1 dB per device is expected, more means heavy clipping), `spectrum` (new energy in `high_mid`/`high`), and, for pitched
> material, the capture's `audio.key` result (a stable key estimate after the change is mildly reassuring; a shift or a new
> semitone clash is a red flag). Bad results: harsh 2-5 kHz energy growth, correlation falling, new energy in the low band from
> a chordal part. **Always ask the producer before saturating a sound they chose.**

---

## 7. Reverb and delay

**Architecture.** Put reverb and delay on return tracks at **100 % wet**, send to them, and share them across tracks: it
gives a coherent space, one place to EQ and duck, and a clean dry signal
([SOS, Effects](https://www.soundonsound.com/techniques/effects-all-you-need-know-and-little-bit-more),
[Puremix](https://www.puremix.com/blog/how-to-use-reverb-without-washing-out-your-mix),
[iZotope](https://www.izotope.com/en/learn/essential-tips-for-mixing-reverb.html)). Do not add reverb to the kick or the
sub-bass (SOS).

**Recipe, in Live**

1. `create_track("return", "Room", device="Reverb")` (short, 0.8-1.5 s), another return for a long hall or Hybrid Reverb, and a
   tempo-synced Echo/Delay return. Three or four returns are enough.
2. **EQ both ends of the return, before the reverb.** The Abbey Road method puts a high-pass and low-pass before the reverb
   (iZotope). Typical settings: low cut at roughly 150 Hz or higher (SOS's vocal-production article rolls reverb lows off
   below about 150 Hz so the tail does not sound cloudy), high cut around 3-4 kHz for a natural, dark tail (SOS) and
   higher for brighter spaces. For dark industrial spaces go darker.
3. **Pre-delay.** Rule of thumb: short (about 10-20 ms) keeps percussion tight, longer (30-60 ms) keeps sustained parts
   forward; SOS cites 30-40 ms to well over 100 ms for a forward vocal, and Paul White up to about 120 ms. Syncing to the
   tempo makes it rhythmic: a 1/64 note is `60000 / BPM / 16` ms (31 ms at 120 BPM, 27 ms at 140).
4. **Decay vs chords.** The tail of the previous chord overlaps the next one. With one chord per bar (as in this project's
   NEON progressions), a decay beyond about one bar (2.4 s at 100 BPM, 2.0 s at 120, 1.7 s at 140, 1.3 s at 180) means two
   chords sound together; with Am to Dm that is an E against F semitone. If the producer wants a huge tail, duck it or accept
   it deliberately.
5. **Duck the return.** A Compressor after the reverb, sidechained from the dry source (`set_sidechain("return:A",
   source="Pad", ...)`): fast attack, release long enough to swell naturally, enough reduction that transients stay clean
   (Attack's burial-reverb walkthrough aims at about 5-6 dB of reduction; its other example sets the threshold near -13 dB)
   ([Attack, Burial reverb](https://www.attackmagazine.com/technique/tutorials/burying-the-mix-in-burial-style-reverb/),
   [Attack, compressing reverbs](https://www.attackmagazine.com/technique/tutorials/compressing-reverbs-for-clarity/)). Live's
   **Echo** has its own Ducking (reduces the wet signal while input is present) and Gate.
6. **Level.** Set the reverb where you like it and pull it back until you only just hear it (Puremix); SOS says about 3-4 dB
   below where it first seems right.
7. **Delays.** Time them from the tempo: a dotted 1/8 is 0.75 of a beat (352 ms at 128 BPM), a 1/4 is one beat. Filter the repeats
   (Echo has high-pass and low-pass sections; Delay has a band-pass filter) so they sit behind the dry sound, keep feedback modest
   (25-40 % is a rule of thumb, not a sourced figure), and duck them with Echo's Ducking or a sidechain Compressor so they fill the
   gaps instead of blurring the notes ([SOS](https://www.soundonsound.com/techniques/effects-all-you-need-know-and-little-bit-more),
   [Live manual](https://www.ableton.com/en/manual/live-audio-effect-reference/)).
8. **Automate sends** to open space in sparse sections and close it in dense ones (SOS vocal production; iZotope also
   retriggers reverb with bypass automation to stop tails accumulating).

**Mono.** Reverb decorrelates the channels; SOS notes that reverb that feels spacious in mono can sound too wet in stereo
and vice versa, and that narrowing the reverb width reduces the gap.

> **For an agent.** Send levels: `set_mixer(track, sends={"A": -18})`, not return faders, so the return's EQ and ducking
> still see sensible level. Measure after a send change: the `low` and `low_mid` shares in `analyze_audio.spectrum` (reverb
> mud shows up there) and `stereo.correlation`; ignore `loudness_range_lu` on short loops. A bad result: the full-mix
> `low_mid` share rising by more than ~1 dB, or correlation dropping toward zero on a part that should be solid. Ask the
> producer how big the space should be; it is style and genre taste.

---

## 8. Stereo image

- **Mono below ~120 Hz.** iZotope advises collapsing everything below about 100-150 Hz, because low frequencies are barely
  directional and out-of-phase bass cancels on mono systems. In Live use Utility's **Bass Mono** (crossover 50-500 Hz) on
  stereo parts, or EQ Eight in M/S mode with a high-pass on the Side channel
  ([iZotope](https://www.izotope.com/en/learn/mono-vs-stereo.html)).
- **Width.** Utility `Stereo Width`: 0 % is mono, above 100 % widens (the maximum is 200 %, raw 0..2). If Width scales the side signal, a source measuring 0.55 side/mid becomes about 0.83 at 150 % (arithmetic;
  verify by measuring `stereo.width`). Use it on pads and textures, not on the kick, bass or lead. Ableton also points to
  Utility's Width as the way to reduce the +3 dB pan-law boost on hard-panned sources.
- **Mid/side EQ.** EQ Eight's M/S mode lets you cut low mids or add air on the sides only.
- **Haas delays (5-35 ms)** widen but the part disappears or changes tone in mono through phase cancellation; SOS reserves
  them for non-critical parts and points to mid/side processing, double-tracking, reverb or chorus as more mono-friendly
  alternatives ([SOS](https://www.soundonsound.com/sound-advice/q-can-haas-delays-be-mono-compatible)).
- **Double-tracking and stereo reverb** collapse more gracefully than delay-based widening; phase inversion tricks cancel
  entirely in mono.
- **Mono check after every width move.** The correlation meter should hover between 0 and +1; sustained negative values mean
  out-of-phase content ([Anderton](https://craiganderton.org/all-about-audio-phase-and-correlation-meters/)).

**Keep the pad wide but out of the way** (the producer's target is a heavy, clean background synth that is very wide above
200 Hz, measured at side/mid about 0.75-0.95): keep the low root mono, widen above ~200 Hz, roll the top off above ~2 kHz,
duck 2-4 dB from the kick (in a NOVA pad stem only as composed gaps: the pad plays alone in tier T1, see 5.6), and leave the centre free for kick, bass and lead. Widen with decorrelated voices and a light
stereo reverb rather than with a Haas delay or heavy chorus on noise.

> **For an agent: width protocol.** `add_device(track, "Utility")`; `set_device_parameters(track, "Utility", {"Bass Mono": "On",
> "Bass Freq": "120 Hz", "Stereo Width": "140 %"})` (names from the 12.4.6 dump; Width 120-160 % for pads, crossover 120 Hz). Bounce and
> `analyze_audio`: `stereo.width`, `stereo.correlation`, and in the listening loop `mono_sub_loss_db` (<= 1 dB below 120 Hz is
> the repo's tolerance). Bad results: correlation near or below 0 for a pad, a sub that loses level in the mono sum
> (`mono_sub_loss_db` above 1 dB), width numbers far above those of the references. Do not leave a Mono switch engaged on
> the Main; ask the human to press it if they want to hear mono.

---

## 9. Automation for movement

Automation replaces heavy compression for transparent level control and creates contrast between sections
([SOS, Mixing Essentials](https://www.soundonsound.com/techniques/mixing-essentials); [iZotope](https://www.izotope.com/en/learn/how-to-mix-music.html)).
Useful moves:

- Volume rides of 1-3 dB for clarity (rule of thumb); larger moves for sections (drop versus break).
- Send throws for a dub-style tail; send reduction in busy sections.
- Filter cutoff sweeps across 4-16 bars; distortion or reverb amount across sections, because constant saturation fatigues the
  listener ([Attack, Organised Chaos](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/)).
- Width and Dry/Wet moves for transitions.

**In this repo**, `write_automation` writes a clip envelope in a Session clip (travelling into the arrangement) with points
or a shape (ramp, sine, triangle, square, saw, steps). Mixer targets are `"volume"`, `"pan"`, `"send:A"`; device targets
need `device=`. Read back with `get_automation`. A parameter under automation ignores the fader or knob until automation is
re-enabled in Live, so tell the producer when you automate a mixer or effect control.

> **For an agent.** After writing, `get_automation(track, slot, parameter, samples=16)` to confirm the shape, start and end
> values, and that the final value returns to the base. Avoid hard steps on levels (clicks); use ramps. Ask first before
> automating something the producer set by hand.

---

## 10. Bus processing and the Main

- **Groups.** Drums, Bass, Music/Synths, FX. Apply Glue Compressor at 2:1, attack 10-30 ms, release 0.2-0.4 s or Auto, 1-3 dB of
  reduction, on groups where the parts must feel like one instrument. Unify drums with Drum Buss (Trim before drive).
- **The Main.** Attack Magazine's rule for the mix handed over: leave the master no hotter than -3 dB so the mastering
  engineer keeps 3-6 dB of headroom. The Main should usually carry at most a gentle glue compressor and a subtle EQ; leave
  loudness to mastering (07). Do not add a limiter whose job is loudness.
- **Loudness comes from one shared gain.** If a sum needs to be quieter or louder, change one stage (the Main fader or a
  Utility on the sum). It never comes from touching every stem (05 section 4.1).
- **Level-match before judging a bus move.** iZotope's mix-bus article is blunt: louder often sounds better, and simply
  raising a fader can beat aggressive settings.

---

## 11. References and translation

**References.** Professionals match key and arrangement intensity to the reference, level-match, and compare tonal balance,
dynamics, width and balance; they use several; they avoid copying a reference's aesthetic
([iZotope, pros' reference tracks](https://www.izotope.com/community/blog/pro-reference-tracks)). Compare the same kind of
object: a *mix* against a *mix* (the Main or a tier sum), never one stem against a full-mix spectrum.

**Level-matching a reference.** Compare like with like: the same kind of section (a drop against a drop, an intro against an intro)
and the same loudness. Pros pick references with a similar arrangement intensity so that loudness comparisons are fair (iZotope).
A reference streamed through Spotify with normalisation on is played back near Spotify's -14 LUFS (integrated) reference
([Spotify](https://support.spotify.com/us/artists/article/loudness-normalization/)), so a mix whose integrated loudness is about
-14 LUFS plays at a roughly similar level; compare sections by ear on top of that. The listening loop instead turns
normalisation off and keeps only level-independent numbers.

> **For an agent.** `ref(action="list")` shows the stored references; `compare("latest", "refs")` places the tier sum's band
> balance, loudness range, peak-to-loudness, short-term spread, width and onset density inside, above or below the references'
> range. It is a direction, not a target: a game stem sum at -14 LUFS is meant to be less dense than a club master. The
> reference's absolute level is the player's, so do not claim a loudness match against a streamed reference; ask the producer
> how they level-match when they audition it.

**Translation checks** (mostly human): mono; laptop or phone speaker; earbuds; car; low volume and high volume (equal-loudness
shifts the perceived bass; see 05 section 5); another room. SOS advises checking headphones and several speaker systems,
comparing with commercial releases, and living with the mix for a few days before calling it finished. The listening loop
simulates a phone with a mono sum and a 4th-order high-pass at 200 Hz and reports the share of energy that survives; it is
information, not pass or fail.

---

## 12. The danger of over-processing

### 12.1 Why agents over-process

Every meter moves when you change something, and every change "looks" like progress; a processor that adds level
sounds better for a few seconds (Katz: the louder of two identical programmes often seems better in a short listen). A
smiley-face EQ and a pushed limiter both exploit that bias at a cost to dynamics and clarity
([iZotope, psychoacoustics](https://izotope.com/en/learn/psychoacoustics-how-perception-influences-music-production)).
The failure on 2026-10-08 was the mechanical version: a loudness number drove limiters, cuts and faders on every part at
once.

### 12.2 Guardrails (digest judgement, informed by the sources above)

| Item | Normal | Needs a stated reason | Stop and ask |
| --- | --- | --- | --- |
| EQ boost on one track | <= +3 dB | +3 to +6 dB | > +6 dB |
| EQ broad cut | <= -4 dB | -4 to -8 dB | > -8 dB |
| Active EQ bands per track | <= 3 | 4-5 | > 5 |
| Compression on one track | 0-4 dB | 4-8 dB | > 8 dB |
| Bus compression | 1-3 dB | 4-5 dB | > 5 dB |
| Limiter on any single stem | none | n/a | any |
| Limiter on the sum | 0-2 dB | 3 dB | > 3 dB |
| Fader move away from the approved mix | <= 2 dB | <= 4 dB | > 4 dB |
| Tracks changed in one step | 1 (or 2 in one role) | 3 | 4 or more |

SOS's rule of thumb that track compression "typically" needs only about 2-10 dB, iZotope's under-3-dB bus guidance and SOS's
limiter advice set the outer limits; these figures are tighter on purpose.

### 12.3 One change at a time, and how to prove it helped

1. Keep the previous take (`takes`) and a muted twin of the track.
2. Change **one** thing; label it.
3. Bounce or `capture` and `compare("latest", "best")`. Revert (`takes(action="restore")`) when anything regresses beyond noise:
   integrated loudness shifted unexpectedly by more than 0.5 LU, any third-octave band moved more than ~1.5 dB, crest down more
   than 1 dB, correlation or `mono_sub_loss_db` worse.
4. **Match loudness** (05 section 7.2) and offer the human A and B labelled and blind where possible (`compare(..., blind=True)`
   gives a packet for a fresh judge).
5. **Bypass test.** Switch the new device off at matched loudness. If you cannot name what got better, remove it. Live 12.3's
   device **Compare A/B** (exposed as `set_device(..., compare_b=...)`) holds the previous setting while you try a new one;
   it does not match loudness.
6. If it is not clearly better, it is not better.

### 12.4 When is a mix done

- It works on faders alone and survives a mono check (Puremix; SOS).
- References show no unexplained gaps at matched loudness (iZotope).
- Remaining changes are sideways moves: A/B differences come down to taste.
- Fresh ears the next day agree; SOS suggests living with the mix for 2-3 days and testing on several systems.
- The producer approves; at that point stop. Further "improvement" by numbers is how the 2026-10-08 mix was lost.

---

## 13. Electronic and industrial specifics

### 13.1 Kick and bass first

Build the anchor from kick and bass. Decide who owns each frequency at each moment: a common arrangement has the kick owning
the lowest fundamental on the hit and the bass owning the root between hits (see 04). Separate them by time (sidechain or tight
envelopes), by frequency (complementary carve), and in the stereo field (mono below ~120 Hz). iZotope notes kick and bass
fight in the sub; the kick-triggered dynamic cut is more transparent than obvious ducking. Attack Magazine notes bass
frequencies dominate bus-compressor activation, so the kick usually becomes the trigger; the microhouse example sidechains the
sub bass to the kick with a fast attack.

### 13.2 Managing many layers

Attack Magazine's layering advice for claps and snares generalises: choose layers with different tone and shape, shave the
low end off layers that should not own it, use complementary EQ so one is boosted where the other is cut, offset their attack
phase, and keep delay mixes under about 30 %
([Attack, layering](https://www.attackmagazine.com/technique/tutorials/layering-claps-snares-tutorial/)). In practice:

- Give each layer a **role and a band**: sub, body, mids, top. No more than two or three full-range layers at once (rule of
  thumb).
- Remove layers (arrangement) before you EQ them.
- High-pass progressively: one full-range layer, then layers starting at about 300 Hz, 800 Hz, 2 kHz (rule of thumb).
- Low layers mono; wide layers high.
- Group layers, glue the group lightly, send the group to a **shared** reverb.
- Check polarity between layers that share a frequency range.

### 13.3 Pads wide but out of the way

See section 8: mono low root, width from ~200 Hz, roll-off above ~2 kHz, ducking from kick (and from the lead if needed; not baked into NOVA stems, see 5.6), a
single shared reverb tail shorter than a chord, and a gentle mid-range dip (2-4 kHz) for the lead if they overlap.

### 13.4 Dirty but clear

The producer's wording for the background synth is "big, heavy and clean"; the *dirt* belongs to other elements. A workable
recipe:

- Distort drums and mids, not the sub; high-pass the distorted path or use multiband distortion (Roar).
- Parallel-crush the drum bus and **duck the crushed copy from the dry drums** so transients stay clean (Attack, Organised Chaos).
- Dark, ducked reverb (low-pass around 3-4 kHz) instead of bright tails.
- Automate the drive amount across sections to avoid fatigue.
- Keep some character: Attack Magazine argues a resonant peak can be the point of a sound; do not notch away every ring
  ([rules to break](https://www.attackmagazine.com/technique/tutorials/5-mixing-rules-you-should-be-breaking/)).
- Watch 2-5 kHz, where the ear is most sensitive and harshness is most audible.
- Keep noise textures low and ducked under the drums.

---

## 14. Mixing checklist for an agent

Tick in order; stop at any "ask".

1. [ ] `get_mixer()`; list approved sounds; `capture(note="baseline")`; `takes(action="keep")`.
2. [ ] Gain-stage (05 section 7.1): no clipped samples; nonlinear devices see sane levels.
3. [ ] Static balance: faders within about 2 dB of the approved mix unless the producer asked; pans per section 3.
4. [ ] Polarity and mono check of kick vs bass and any layered stems (`stereo.correlation`).
5. [ ] Subtractive EQ on **one track at a time** with a stated reason; measure; match loudness; A/B. Ask if a sound's character
   changes.
6. [ ] Dynamics only with a purpose; values from 5.3; crest and loudness within budget; no limiter on stems.
7. [ ] Sidechain from the kick where needed; release from the tempo table; check loss of bass body in mono.
8. [ ] Returns: 100 % wet, EQ'd both ends, pre-delay, ducked; decay shorter than a chord change; sends set with `set_mixer`.
9. [ ] Width: Bass Mono 120 Hz; pad widths 120-160 %; `mono_sub_loss_db` <= 1 dB; correlation >= 0.
10. [ ] Colour: one device at a time, parallel, matched; key estimate stable.
11. [ ] Bus glue on groups (1-3 dB); Main chain empty or one gentle device; peaks -6 to -3 dBFS.
12. [ ] Automation for contrast; verify with `get_automation`; tell the producer.
13. [ ] `compare("latest", "refs")` for direction; ask the producer for the real listening checks (mono, phone, car, low volume).
14. [ ] Revert (`takes(action="restore")`) anything that regressed; label and offer loudness-matched A/B for each audible change.
15. [ ] Write a short handoff: what changed, what was measured, what the producer must judge.

---

## Sources

**Primary and standards**

- Ableton Live 12 manual: [Mixing](https://www.ableton.com/en/manual/mixing/), [Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/),
  [Live Audio Effect Reference](https://www.ableton.com/en/manual/live-audio-effect-reference/) (Compressor, EQ Eight, Drum Buss, Echo, Channel EQ, Chorus-Ensemble, Delay),
  [Live 11 reference for Glue Compressor](https://www.ableton.com/en/live-manual/11/live-audio-effect-reference/).
- Ableton: [Live 12 features](https://www.ableton.com/en/live/all-new-features/), [Live 12.1](https://www.ableton.com/en/blog/live-121-is-out-now/),
  [release notes](https://www.ableton.com/en/release-notes/live-12/), sidechain compression
  [Part 1](https://www.ableton.com/en/blog/sidechain-compression-part-1/) and [Part 2](https://www.ableton.com/en/blog/sidechain-compression-part-2-common-and-uncommon-uses/).
- Bob Katz, [K-System](https://www.digido.com/portfolio-item/level-practices-part-2/).
- Repo: `docs/TOOLS.md`, `docs/handoff/2026-10-08-nova-v2-paused.md`, `docs/listening-loop-calibration.md`, `ears/profile.py`, `.claude/skills/listening-loop/SKILL.md`.

**Trade press and education**

- SOS: [Mixing Essentials](https://www.soundonsound.com/techniques/mixing-essentials), [Mixing in mono?](https://www.soundonsound.com/sound-advice/q-should-be-mixing-mono),
  [Panning and mono compatibility](https://www.soundonsound.com/sound-advice/q-are-there-any-panning-rules-maintaining-mono-compatibility),
  [Haas delays](https://www.soundonsound.com/sound-advice/q-can-haas-delays-be-mono-compatible),
  [Compression for drums](https://www.soundonsound.com/techniques/compression-fashion-drum-sound-you-want),
  [Guide to mix compression](https://www.soundonsound.com/techniques/sos-guide-mix-compression),
  [How & when to use mix compression](https://www.soundonsound.com/techniques/how-when-use-mix-compression),
  [Parallel compression](https://www.soundonsound.com/techniques/parallel-compression),
  [Limiter release](https://www.soundonsound.com/sound-advice/q-what-release-settings-should-use-limiter),
  [Effects](https://www.soundonsound.com/techniques/effects-all-you-need-know-and-little-bit-more),
  [Vocal Production](https://www.soundonsound.com/techniques/vocal-production).
- iZotope: [How to mix](https://www.izotope.com/en/learn/how-to-mix-music.html), [Masking](https://www.izotope.com/en/learn/what-is-frequency-masking),
  [Dynamic EQ](https://www.izotope.com/en/learn/when-to-use-dynamic-eq-in-a-mix), [Mix bus compression](https://www.izotope.com/en/learn/mix-bus-compression),
  [Transparent compression](https://www.izotope.com/en/learn/tips-for-more-transparent-compression),
  [Reverb tips](https://www.izotope.com/en/learn/essential-tips-for-mixing-reverb.html), [Mono vs stereo](https://www.izotope.com/en/learn/mono-vs-stereo.html),
  [Psychoacoustics](https://izotope.com/en/learn/psychoacoustics-how-perception-influences-music-production),
  [Pros' reference tracks](https://www.izotope.com/community/blog/pro-reference-tracks).
- Attack Magazine: [Mix bus compression](https://www.attackmagazine.com/technique/tutorials/mix-bus-compression/),
  [Organised Chaos](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/),
  [5 mixing rules to break](https://www.attackmagazine.com/technique/tutorials/5-mixing-rules-you-should-be-breaking/),
  [Mixing microhouse](https://www.attackmagazine.com/technique/tutorials/mixing-microhouse/),
  [Layering claps and snares](https://www.attackmagazine.com/technique/tutorials/layering-claps-snares-tutorial/),
  [Compressing reverbs](https://www.attackmagazine.com/technique/tutorials/compressing-reverbs-for-clarity/),
  [Burial-style reverb](https://www.attackmagazine.com/technique/tutorials/burying-the-mix-in-burial-style-reverb/),
  [Gain staging](https://www.attackmagazine.com/technique/tutorials/how-gain-staging-in-your-daw-can-help-keep-your-mix-clean-and-punchy/).
- Puremix: [static balance](https://www.puremix.com/blog/where-to-start-when-you-open-a-mix-the-static-balance-method),
  [EQ framework](https://www.puremix.com/blog/how-to-eq-a-mix-when-to-cut-when-to-boost-and-where-to-start),
  [reverb without washing out the mix](https://www.puremix.com/blog/how-to-use-reverb-without-washing-out-your-mix).
- Craig Anderton, [Phase and correlation meters](https://craiganderton.org/all-about-audio-phase-and-correlation-meters/).
- Wikipedia (definitions): [Intermodulation](https://en.wikipedia.org/wiki/Intermodulation), [Power chord](https://en.wikipedia.org/wiki/Power_chord).
- Vendors: [TDR Nova](https://www.tokyodawn.net/tdr-nova/), [soothe3](https://oeksound.com/plugins/soothe3).

**Weaker evidence (blogs and PDFs)**

- Music Guy Mixing [subtractive EQ](https://www.musicguymixing.com/subtractive-eq/) and [sidechain reverb](https://www.musicguymixing.com/sidechain-reverb/)
  (a sidechain reverb with maximum ratio and knee, instant attack and a release tuned until the tail swells);
  Musician on a Mission, [10 Top Compression Tips (PDF)](https://mastering.com/wp-content/uploads/2017/07/COMPRESSION-CHEAT-SHEET.pdf).

---

## Open questions and where sources disagree

- **How much bus compression.** SOS's guide says 1-3 dB and iZotope says under 2-3 dB; SOS's other article suggests 4-8 dB for the
  "gentle" style and Attack Magazine uses 4-5 dB for dance music with the kick driving the compressor; Attack's microhouse
  example reaches about 5 dB on the master. This digest defaults to 1-3 dB and allows more in dense electronic buses with a reason.
- **Compression numbers by instrument** vary by source (kick attack from about 1 ms to 30 ms; mix-bus attack from 30 to 80 ms). The table
  gives ranges; the right values depend on the sound and the producer's taste.
- **High-pass everything?** Puremix and SOS say yes for non-bass parts; for synths with a deliberate low root (the reference synth has one
  at 41-49 Hz) that would remove what the producer wants. The compromise: mono the low end, do not remove it.
- **Sidechain always?** Ableton and most dance tutorials use it; Attack Magazine argues overlap can give cohesion. Taste.
- **Not verified here:** whether `set_device(compare_b=...)` copies state or only toggles it; and any numeric target for a "healthy"
  PLR for industrial or EBM masters (none found). Settled since: the EQ Eight, Utility, Compressor and Glue Compressor parameter names
  are those of the 12.4.6 dump, Glue's stepped values agree with that dump's defaults and Ableton's presets, and `set_sidechain` routes
  only a Compressor, so Multiband Dynamics' sidechain source is a UI job.
