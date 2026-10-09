# Genre deep dive: Nine Inch Nails, Boys Noize, industrial techno and EBM - and how to get there in Live 12

Researched 2026-10-08 for agents that compose in Ableton Live 12.4.6 Suite through AbletonMCP and cannot hear. Deeper treatments: pads and width `03-sound-design-recipes.md`; kick and bass `04-drums-and-low-end.md`; mixing `06-mixing.md`; voicing and arrangement `08-arrangement-and-composition.md`; game stems `10-game-audio-adaptive-music.md`; measuring without ears `11-listening-without-ears.md`; device parameters `12-live-devices-reference.md`. The synthesis is `00-agent-playbook.md`.

**Evidence tags.** [D] documented by the artist, engineer, credits or an official page. [R] reconstructed by a third party from released stems (not the artists' statement). [W] weak: fan wiki, forum, crowd-submitted data, school or blog post, aggregator numbers. [I] my inference or engineering practice: a starting point to test, not a fact. Untagged numbers come from the tutorial cited beside them.

**Research limits.** The session's web-search quota ran out partway, and several outlets could not be opened (Rolling Stone, Variety, Hollywood Reporter, IndieWire, MusicRadar, Reverb, Gearspace, Pitchfork). Nothing below comes from a page I could not read, except the one untraced tempo claim flagged in section 3.3. I found no first-hand production interviews for Ancient Methods, Rebekah or I Hate Models, nothing on the Nine Inch Noize remix tempos, drum machines or synths, and nothing on the gear behind the TRON: Ares score.

## If you remember five things

1. **"Big, heavy and clean" is built, not found.** The documented facts (analogue-style monosynth layers, interval stacking, dry mixes, distortion on sources and drums followed by clean-up EQ) suggest a recipe [I]: harmonically rich saw voices shaped by a filter, octaves and fifths in the low register, width only above about 200 Hz, distortion on simple elements (kick, single-note bass, percussion) and never on sustained chords. The earlier agent measured the references' background synth as one low root at 41-49 Hz, a saw-like stack to about 2 kHz, width above 200 Hz, almost no noise.
2. **Nine Inch Noize is documented at the level of credits, process and source-song tempos, not sounds.** Boys Noize rebuilt the Challengers score from stems (new drums, new synths, remade sounds); the Noize versions are semi-live remixes; one review calls the album spacious and clean. Remix tempos, drum machines, synths and DAW are not public in anything I could read. Measure the four references (`ref`, `compare`) instead of assuming.
3. **Industrial techno** is straight 4/4 at about 126-138 BPM (hard techno 145-160): a tuned 909-type kick plus a separate reverb-and-distortion "rumble" layer low-passed around 150-250 Hz and ducked by the kick, and crushed or saturated percussion built one element at a time. In the tutorials that give numbers, heavy compression sits on the whole beat; limiters on single elements are creative transient tools or safety nets, never loudness tools.
4. **EBM** is a repeating sequenced mono bass (often 16ths), plain programmed drums and shouted vocals. The sources I could read give no tempo range. In an instrumental the sequence must be the hook. Flood links EBM and NIN: he produced Nitzer Ebb's *Belief* and co-produced "Closer".
5. **Steer by construction and by the producer's ear, not by distance to a mix.** Never match a full-mix spectrum with one instrument, never rank presets by it, never saturate whole chords, never limit stems to hit a loudness number. One change at a time, loudness-matched, labelled. Ask the questions in section 8.3.

---

## 1. What the producer's words mean in this genre

| Word | Usually built from [I] | First check (measure) |
| --- | --- | --- |
| big | a low root (41-49 Hz in the references), a dark reverb tail of several seconds, width above 200 Hz, octave layers | side/mid about 0.75-0.95 above 200 Hz; small mono-sum loss on the pad stem; root visible in the 40-63 Hz third-octave bands |
| heavy | weight in the lows plus a dense harmonic stack (saw-like, to about 2 kHz) and restrained dynamics; not noise or boosted lows | band balance from 100 Hz to 2 kHz falls smoothly; no hump at 55-65 Hz from chord thirds; crest factor not collapsed |
| clean | little noise, stable tuning, no intermodulation hash, mono bass, filter-shaped | `analyze_notes` clean; no rough beating below 150 Hz; no limiter on the stem |

The reference facts come from an earlier agent's measurements of the intro synths of "As Alive As You Need Me To Be" and "Vessel" (audio not kept; `docs/handoff/2026-10-08-nova-v2-paused.md`). They describe one sustained layer, not the whole mixes, and they are not a spectral target for any other instrument.

---

## 2. Nine Inch Nails, Reznor and Ross

### 2.1 Instruments and tools

| Tool | What is known | Tag |
| --- | --- | --- |
| Moog (Prodigy first, Minimoog Voyager, IIIc and Model 15 reissues) | Reznor says Moog is the one constant since *Pretty Hate Machine*; he calls the Voyager the archetype of a synth ([Fact](https://factmag.com/2015/09/30/trent-reznor-moog-synthesizers-haxan-cloak), [Spill](https://spillmagazine.com/3180), [SynthHistory](https://www.synthhistory.com/post/interview-with-trent-reznor)) | D |
| Prophet 6, ARP Odyssey, Dreadbox Nymphes, Oberheim Four Voice | his 2022 list of studio staples; he likes the Odyssey's "bite-y, kind of ugly, great sound" ([SynthHistory](https://www.synthhistory.com/post/interview-with-trent-reznor)) | D |
| E-mu Emax, Kurzweil K2000, Waldorf Microwave | Emax for *Pretty Hate Machine* drums and crunchy pitched-down samples; K2000 on *Downward Spiral*; Microwave textures on *The Fragile* ([MusicTech](https://musictech.com/guides/buyers-guide/five-synths-that-define-nine-inch-nails-sound/), [Gearnews](https://www.gearnews.com/how-to-sound-like-nine-inch-nails-pretty-hate-machine/)) | D |
| Prophet VS, Oberheim Xpander / OB-Mx, Nord Lead | Xpander FM grit and raw Prophet VS tones on PHM (Gearnews); "Closer" bass is sampled layers with Prophet VS licks ([SOS](https://www.soundonsound.com/techniques/classic-tracks-nine-inch-nails-closer)), or a prototype OB-Mx per the fan wiki; Nord Lead for *Fragile* pads per a forum quoting Keyboard 2000 ([thread](https://forum.vintagesynth.com/viewtopic.php?t=53954)) | D/W |
| ARP Odyssey/Oddity, Korg MS-20, Analogue Solutions Vostok, SidStation, TR-909 | stem names of the released *Social Network* multitrack "In Motion" ([Reverb Machine](https://reverbmachine.com/blog/trent-reznor-atticus-ross-in-motion/)) | R |
| Buchla (Cortini), Doepfer modular (Reznor), a studio "like a museum of synthesizers" | Cortini builds drone patches and sequences that trigger melodies ([Synthtopia](https://www.synthtopia.com/content/2010/08/10/alessandro-cortini-interview/), [Suite Studios](https://blog.suitestudios.io/article/inside-the-studio-tommy-simpson-macro-micro-feature-interview)); Reznor finds modular easy to get lost in when time is tight | D |
| Ableton Live, Maschine | Reznor now writes in Live because he likes how it makes him think (and dislikes Pro Tools) ([SynthHistory](https://www.synthhistory.com/post/interview-with-trent-reznor)); *Hesitation Marks* was built in Maschine ([MusicTech](https://musictech.com/guides/buyers-guide/five-synths-that-define-nine-inch-nails-sound/)) | D |
| iZotope Trash, RX, Ozone | Ross's favourite distortion is Trash, often used with its distortion off; RX removes looper clicks ([iZotope Learn](https://www.izotope.com/en/learn/atticus-ross.html)) | D |
| Soundtoys Decapitator, EchoBoy; Reaktor as a distortion box | crowd gear pages only ([Equipboard](https://equipboard.com/pros/trent-reznor)) | W |

### 2.2 Texture, distortion and layering

- **Sampling as distortion.** Samples pitched down an octave or two for crunch; a distorted woodblock, resampled and pitched down, became a screeching lead [D, MusicTech, Gearnews].
- **Console and room distortion.** "Closer": preamps pushed, SSL channel distortion, LA-2A/LA-3 chains, a Zoom 9030 ring modulator on the snare [D, SOS]. *The Fragile*: PZM boundary mics driven into preamp distortion, U87s about 15 feet away at the edge of breakup, 1176s with every button in [D, [SOS 2000](https://www.soundonsound.com/people/alan-moulder-recording-nine-inch-nails-smashing-pumpkins)]; guitar fuzz and pedal chains strung together on purpose [D, [Mix 2000](https://www.mixonline.com/?p=101283)].
- **Layers with a job.** Moulder put a low sample under the recorded kick, a dbx subharmonic synth below that, and an ambient snare sample where others add reverb [D, Mix 2000]. *The Fragile* was assembled from a database of parts indexed by key and tempo [D, SOS 2000].
- **Imperfection and noise as material.** They avoid over-quantising and over-tuning [D, SynthHistory, iZotope Learn]; Reznor says noise is written in from the start, not added later [D, [WNYC](https://www.wnyc.org/story/trent-reznor-and-atticus-ross-gone-girl/)].
- **Improvised long takes.** *Ghosts I-IV*: ten weeks, no agenda, each piece started from an imagined place [D, [Wikipedia](https://en.wikipedia.org/wiki/Ghosts_I%E2%80%93IV)].
- **Distortion is paired with clean-up.** An independent recreation of the *Social Network* guitars used a fuzz pedal and a saturator, then heavy EQ to remove noise [R, [Reverb Machine](https://reverbmachine.com/blog/trent-reznor-social-network-synth-sounds/); the plug-ins are the author's choice].

### 2.3 Drums and mix: aggressive but clear

- "Closer": the kick is a cleaned but gritty sample of Iggy Pop's "Nightclubbing"; the snare is a sample through SSL distortion and ring modulation (the fan wiki names a Roland R-70 as its source); Flood programmed the hats [D, SOS; [NIN wiki](https://www.nin.wiki/Closer) W]. Moulder triggered kick and snare samples behind the recorded drums with a Forat F16 [D, Mix 2000]. Reznor and Ross prefer a sample or machine to a live drummer for what they need [D, SynthHistory]. "In Motion" has no snare: a 909 kick, an off-beat 909 hat and modular hats over one 4-bar loop [R].
- Moulder mixes quietly on an Auratone, uses filters "probably more than EQ", and compresses the bus only slightly [D, Mix 2000]. "In Motion" is a very dry mix with a little short reverb [R]. On TRON: Ares, Reznor and Ross mixed the instrumentals, Serban Ghenea the vocals; mastering Randy Merrill, Idania Valencia and Mike Marsh [D, [Wikipedia](https://en.wikipedia.org/wiki/Tron:_Ares_%28soundtrack%29)].
- Released loudness is high (section 7); Reznor's note on the Noize album is "Listen LOUD" [D, [Consequence](https://consequence.net/2026/04/nine-inch-noize-album-details/)].

### 2.4 The scores

| Score | Documented | Take-away |
| --- | --- | --- |
| *The Social Network* (2010) | Fincher: no orchestra, keep it somewhat synthetic, Tangerine Dream and Vangelis as touchstones; two weeks of tonal sketches first ([Drowned in Sound](https://www.drownedinsound.org/archive-interview-trent-reznor-discusses-the-social-network-soundtrack-4141283/)) [D]. "In Motion": one 4-bar loop, two saws 19 semitones apart in a 3-voice unison, a square sequence with the filter near 2 kHz [R] | few elements; intervals carry harmony |
| *Gone Girl* (2014) | "spa music" that unravels; an improvised modular solo gliding through waveforms; cheap plastic keyboard tones ([WNYC](https://www.wnyc.org/story/trent-reznor-and-atticus-ross-gone-girl/)) [D] | a clean surface over slow instability |
| *Soul* (2020) | every place needed its own identity ([Disney](https://thewaltdisneycompany.com/news/how-original-music-adds-soul-to-pixars-new-movie/)) [D] | one palette per game zone |
| *Bones and All* (2022) | an hour of live improvisation through loopers and modular, edited into sections ([Spitfire](https://composer.spitfireaudio.com/en/articles/trent-reznor-and-atticus-ross-on-emotively-scoring-bones-and-all)) [D] | perform long takes, cut loops |
| *Challengers* (2024) | Guadagnino's "driving techno" brief; it should feel like a needle drop but is score ([Consequence](https://consequence.net/cover-stories/trent-reznor-atticus-ross-movies-interviews/)) [D] | techno is already in their writing |
| *TRON: Ares* (2025) | no orchestra at all; the sound is "precise and unpleasant at times" (Empire, via [Wikipedia](https://en.wikipedia.org/wiki/Tron:_Ares_%28soundtrack%29)); critics hear 80s electro synths and huge synth-bass ([Wikipedia](https://en.wikipedia.org/wiki/As_Alive_as_You_Need_Me_to_Be)). **Gear undocumented.** | synth-forward, exact, hard-edged |

### 2.5 Why their background synths read as big, heavy and clean [I]

1. Harmonically rich oscillators from analogue-style synths, so the filter does the shaping. A reconstruction of the "Swarmatron" lead of "A Painted Sun in Abstract" is five unison saw voices, slight detune, filter around 800-1400 Hz [R, [Reverb Machine](https://reverbmachine.com/blog/how-reznor-ross-created-painted-sun/)].
2. A fixed, moderate cutoff (1-2 kHz) and little resonance: a smooth top, not a sweep.
3. Octaves and fifths low, thirds high. Critical bands are about 100 Hz wide below 500 Hz ([Bark scale](https://en.wikipedia.org/wiki/Bark_scale)), so close low notes beat and roughen unless their harmonics line up (octaves, fifths).
4. Width from unison, detune and ensemble above about 200 Hz; the low end stays centred.
5. Dry or dark reverb; EQ clean-up on any noisy layer.
6. No distortion on stacked notes: nonlinear processing of two or more notes adds sum and difference tones ([intermodulation](https://en.wikipedia.org/wiki/Intermodulation)), which the ear hears as wrong notes.

> **For an agent (Reznor/Ross).** Use these facts to pick a *construction* (saw stack + filter + open voicing + dark reverb), never to claim "this is what NIN used". Read a preset's structure with `get_device` (which oscillators are above 0, noise, sub, cutoff) before auditioning it: "Dark Throne" is a sub oscillator plus noise, hollow by design. Verify with `analyze_notes` and, on the pad stem alone, `analyze_audio` (third-octave bands, side/mid above 200 Hz, mono-sum loss). Measurements diagnose; the producer decides.

---

## 3. Boys Noize and Nine Inch Noize

### 3.1 Boys Noize's toolkit and habits [D unless noted]

- **Software.** Logic Pro, starting from a plain one-track session; the EXS24 sampler since his Timbaland-sample days ([Output](https://output.com/blog/talkback-with-boys-noize)).
- **Hardware.** Jupiter-6, TR-808 and a custom TR-707 (by Diabolical) with filter, bit-crush and pitch per voice, synced to a TB-303; Eurorack since about 2016, with roughly 500 raw modular recordings (each under ten minutes) kept to revisit; in 2020 he co-designed Triptych, a Eurorack distortion module ([Roland](https://articles.roland.com/1010-by-boys-noize/), Output).
- **Mixing.** No standard chain; Neve EQ for colour, SSL for clean and bright, Pro-Q 3 for clinical. Pre-masters go out with an empty master bus, and he says loudness costs the low end (Output). Raw material stays raw (his "Strictly Raw" series); his project filter is whether it is cool ([podcast notes](https://www.buzzsprout.com/1448794/episodes/18697802-boys-noize-on-nine-inch-nails-collaboration-tron-and-his-new-label-oaz-vinyl-crate-digging)). Wikipedia files him under electro house, techno and acid with heavy noise ([Wikipedia](https://en.wikipedia.org/wiki/Boys_Noize)).
- **On the Challengers score** he began cautiously, was told to go harder, then remade most sounds, replaced drums, added synths and rearranged to bridge scores at different tempos; he drew on 90s happy hardcore and gabber, and the closing track alternates his version with theirs ([TheWrap](https://www.thewrap.com/challengers-mixed-album-boys-noize-explained/), [Paper](https://www.papermag.com/boys-noize-challengers-soundtrack), [NIN Hotline](https://www.theninhotline.com/archives/articles/display/6199)).

### 3.2 Timeline [D]

| Date | Event |
| --- | --- |
| 2024-04-12 | *Challengers [MIXED]*: 28 minutes, nine reworked score tracks, a continuous DJ-friendly mix built from stems (Paper, [Wikipedia](https://en.wikipedia.org/wiki/Challengers_%28soundtrack%29)) |
| 2025-06-15 to 2026-03-16 | Peel It Back Tour; Boys Noize opens every show and joins a B-stage remix set ([Wikipedia](https://en.wikipedia.org/wiki/Peel_It_Back_Tour), [NIN wiki](https://www.nin.wiki/Boys_Noize)) |
| 2025-07-17 / 09-19 | TRON: Ares single and album; Boys Noize co-produces "As Alive As You Need Me To Be" and adds production and programming elsewhere ([Wikipedia](https://en.wikipedia.org/wiki/Tron:_Ares_%28soundtrack%29)) |
| 2026-02-27 | *Tron Ares: Divergence* remix album; three Boys Noize remixes ([Wikipedia](https://en.wikipedia.org/wiki/Tron_Ares:_Divergence)) |
| 2026-04-11 | Nine Inch Noize debut at Coachella ([Wikipedia](https://en.wikipedia.org/wiki/Nine_Inch_Noize)) |
| 2026-04-17 | *Nine Inch Noize*, 12 tracks, 46:41, partly recorded live; mixed by Boys Noize, Reznor and Ross; mastered by Marsh, Merrill and Tucci ([Wikipedia](https://en.wikipedia.org/wiki/Nine_Inch_Noize_%28album%29), [NIN wiki](https://www.nin.wiki/Nine_Inch_Noize), [Spin](https://www.spinmagazine.com/2026/04/nine-inch-nails-boys-noize-new-album/)) |

### 3.3 Known and unknown about the remixes

| Known | Tag | Unknown (do not assert) |
| --- | --- | --- |
| Source-song tempos: Vessel about 92, Closer 90, She's Gone Away 80, Heresy 115, Came Back Haunted 130, Memorabilia (NIN's Soft Cell cover) 134 BPM ([NIN wiki](https://www.nin.wiki/Vessel) and sibling pages) | W | tempos of the Noize versions, except the two stored measurements below |
| Each is a semi-live remix: audience noise at both ends, studio-quality middle; vocoder-led techno/EDM touches on "Vessel" and "Closer" ([NIN wiki](https://www.nin.wiki/Closer)) | W | drum machines, kick design, synths, DAW |
| "She's Gone Away" is built on Boys Noize's own "Girl Crush"; "Parasite" uses elements of "Xpress Yourself"; guitars removed ([Wikipedia](https://en.wikipedia.org/wiki/Nine_Inch_Noize_%28album%29), [Ghost Cult](https://ghostcultmag.com/album-review-nine-inch-noize-nine-inch-noize-the-null-corporation/)) | D/W | what the "As Alive" intro pad is |
| Critics: "spacious and clean" (Metal Hammer, via Wikipedia), grime and nihilism stripped back, thrumming bass on "She's Gone Away", gritty bass on "Came Back Haunted", "Closer" closest to its original ([Louder](https://www.loudersound.com/music/albums/nine-inch-noize-album-review), Ghost Cult) | D (critics) | loudness in LUFS |
| Dynamic range 4 (min 3, max 7), one lossless submission ([DR database](https://dr.loudness-war.info/?album=nine+inch+noize)) | W | which master Spotify serves |

The repo's two stored reference measurements (`ref(action="list")`, taken through a lossy stream and the loopback, so estimates) read the Noize "Vessel" at 92.1 BPM and "She's Gone Away" at 93.1 BPM, each with the doubled value as runner-up (project measurement); if right, the Noize "She's Gone Away" is not at the source song's 80 BPM. Likely palette from his habits [I]: saturated electro drums, an acid-style resonant sequence, buzzing mono basses, raw modular texture. None of it is confirmed for the album. A search-result summary quoted about 127 BPM ("Closer") and 134 ("Came Back Haunted") for the Noize versions and a blog review says "95-125 BPM"; I could not trace either to a page.

> **For an agent (Boys Noize/Nine Inch Noize).** Take reference tempos from `ref`/`measure.tempo_estimate`, and remember loop-built music often reads at half tempo with the true tempo as runner-up (`docs/handoff/2026-10-08-listening-loop-references.md`). Treat "Boys Noize style" as a direction (hard electro drums, acid-ish motion, remade sounds, DJ-friendly sections, long outros) and ask Fred which part he means. The remixes rebuilt songs from stems, replacing drums and adding synths while keeping the melodic identity: for the game, keep the producer's chosen sounds and add or swap one stem at a time.

---

## 4. Industrial techno

### 4.1 Tempo and groove

| Style / source | Tempo | Notes |
| --- | --- | --- |
| Techno overall ([Wikipedia](https://en.wikipedia.org/wiki/Techno)) | 120-150 BPM | four-on-the-floor; 808/909/303 |
| Attack, [Industrial Techno](https://www.attackmagazine.com/technique/beat-dissected/industrial-techno/) | 126-130, swing 50-60% | 909 kick, crushed hats, distorted toms |
| Attack, [Paula Temple-style](https://www.attackmagazine.com/technique/beat-dissected/dark-cinematic-hypnotic-techno/) | 131, swing 50% | Live 12 |
| Attack, [Silent Servant-style](https://www.attackmagazine.com/technique/beat-dissected/create-raw-hypnotic-techno-like-silent-servant/) (EBM-driven), [Phase Fatale-style](https://www.attackmagazine.com/technique/beat-dissected/hypnotic-techno-inspired-by-phase-fatales-love-is-destructive/) | 138, swing 50% | |
| Hard techno ([Future Proof](https://futureproofmusicschool.com/blog/making-hard-techno-a-path-to-unique-sound-design)) [W] | 145-160, peak time 150-155 | school blog |
| Hardcore/gabber ([Wikipedia](https://en.wikipedia.org/wiki/Hard_techno)) | 160-200+ | distorted saw kicks |

At 126 / 130 / 138 / 140 BPM a beat is 476 / 462 / 435 / 429 ms and a 16th is 119 / 115 / 109 / 107 ms. A half-time feel at 140 BPM (the producer's accepted choice) pulses at 70 BPM, closer to the 80-92 BPM source songs [I].

### 4.2 Kick and rumble

A short, punchy, distorted main kick plus a long sub tail ("rumble") that gives physical weight [W, Future Proof; D, Attack].

- **Main kick.** Layer a high, mid and low kick, EQ each, glue at about -5 dB, cut near 120 Hz and 800 Hz, lift a low shelf near 80 Hz, add overdrive and a limiter ([Attack](https://www.attackmagazine.com/technique/tutorials/adding-reverb-techno-kick/)). Or a 909 kick transposed up, 333 ms decay, then Attack's "Drum Pumper" preset (its parameters are Drum Buss's) set to `Boom Amt` 57 %, `Boom Freq` 49 Hz, `Damping Freq` 6.8 kHz, `Crunch` 0 (Silent Servant-style). A pitch drop to the fundamental within 10-20 ms gives the click [W].
- **Rumble.** A parallel path: long reverb (3-5 s, fully wet), heavy distortion, high-pass near 30 Hz, low-pass or shelf at 150-250 Hz, sidechain from the dry kick, mono [W, Future Proof]. [Bonedo](https://www.bonedo.de/?p=932209): delay, then reverb, then a 250 Hz low-pass; the rumble can also be its own 16th-note MIDI part, with send level moved 1-2 dB across 8 bars. Attack's Paula Temple-style layer: a second kick through unsynced delay (L 2 ms, R 3 ms, 50% feedback), then Reverb 3.79 s at 68% wet, then Saturator Medium Curve at 5.7 dB.
- **Berghain-style.** Sub from two layered kicks, top from a 909 pitched down 8 semitones; different distortion per band (gentle low, overdrive or fuzz mid, tight high); reverb on a send; a steep high cut isolates the rumble; a tempo-synced filter adds movement ([Attack](https://www.attackmagazine.com/technique/tutorials/processing-berghain-kicks-with-multiband-distortion/)).
- **Kick vs bass.** Rolling bass: sub below 80 Hz (12 dB/oct low-pass), bass line 65-350 Hz, kick cut 4.5 dB at 98 Hz for a G bass (the tutorial's G2 is scientific notation; Live G1, MIDI 43), first 16th of each beat left empty, sidechain needed ([Attack](https://www.attackmagazine.com/technique/tutorials/warehouse-rolling-techno-bass/)); see `04-drums-and-low-end.md`.

### 4.3 Distortion chains

- Parallel beats serial for drums; EQ before the distortion decides what it sees; Attack suggests Live's Saturator at about 7 dB Drive with Output down about 5 dB, and a limiter on each driven track as a safety net ([Attack](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/)). A safety limiter whose ceiling sits above the peaks does almost nothing [I]; it is not the 12 dB loudness limiting that failed on 2026-10-08.
- Hardware habits: Perc runs hardware through a Pro Co RAT and says the Jomox M.Brane's metallic hits are clean until distorted ([Attack, My Studio](https://www.attackmagazine.com/features/my-studio/perc/)). Surgeon records hardware improvisation as 6-9 stereo tracks, then layers and treats them in Live with UAD 1176 and LA-2A, EQ Eight, Amp, Delay and The Glue ([SOS](https://www.soundonsound.com/people/generations-part2-surgeon), [XLR8R](https://xlr8r.com/?p=57316)). Blawan likes a dirty modular distortion module for gluing patches, a wave folder and low pass gates ([Fabric](https://fabriclondon.com/posts/studio-guide-blawan-london-modular-alliance-discuss-favourite-modular-units)), and jams on modular, picks grooves out of the jam and groups kick and groove with processing ([Sonic State](https://sonicstate.com/news/2025/12/01/blawana-kick-groove-technique)).

### 4.4 Percussion and metallic hits

- **Attack's industrial beat** (126-130 BPM): 909 kick with overdrive, a 250-300 Hz cut and a bitcrusher; closed hat resampled through a 12-bit sampler, off-beats, short plate reverb; 909 tom bitcrushed, with *lower velocity where it overlaps kick or hat* instead of sidechain; a woodblock crushed to 6-bit / 22 kHz; a shaker on every second off-beat through a 24 dB high-pass; a synthesised noise snare on 2 and 4 with overdrive and a softened attack.
- **Phase Fatale-style:** layered kicks with a Limiter at -12 dB ceiling and 6 ms lookahead as a transient tool, Redux on claps, hats at 34L and 7R, a Drum Noise Glitcher with automated Distort, a metallic reverb on a conga. **Silent Servant-style:** 909 hats shortened for the Tresor click, snare through a distortion rack.
- **Metal sources:** Perc's Jomox M.Brane plus distortion and spring reverb; Live equivalents in 6.5.

### 4.5 Atmospheres, drones and arrangement

- Drones from drums: an 808 kick pitched down 24 semitones, stretched, doubled an octave up, tape-saturated, lows cut, 300 Hz lifted, a pitched-down cymbal underneath ([Attack](https://www.attackmagazine.com/technique/tutorials/drones-from-drums/)).
- Interval logic: D2, D3, D4 with a G3 between (octave numbers as the tutorial writes them; it does not state its convention, and its notch frequencies match Live's D2 to D5 at 147, 294, 587 and 1175 Hz), EQ notches at 150, 300, 600 and 1200 Hz removing the D so the G stands out, sidechained to the kick ([Attack](https://www.attackmagazine.com/technique/synth-secrets/making-lcd-soundsystem-style-drones/)). A fifth or fourth dyad is enough.
- Techno stays hypnotic through slow filter and send movement over 8-bar loops (Bonedo, Attack) [D]; in adaptive stems give each stem a small, slow movement. Tutorial master chains belong on a whole beat, not on stems.

> **For an agent (industrial techno).** Pick tempo from the producer's pace, not this table (earlier passes were "way too fast"). Build kick and rumble as separate layers and judge each alone (`bounce` + `analyze_audio`). Put crush and metal on percussion one element at a time with a labelled A/B. Do not import club loudness (about -6 to -5 LUFS for hard techno [W]) into game stems; the top tier is -14 LUFS / -1 dBTP (`07-mastering-and-loudness.md`, `10-game-audio-adaptive-music.md`).

---

## 5. EBM

**What it is [D].** Electronic body music joins industrial and synth-punk with dance music: sequenced repetitive basslines, programmed disco or rock beats, mostly undistorted shouted vocals, hammer and machine samples; defining synths include the Korg MS-20, Roland SH-101, ARP Odyssey and Emulator II ([Wikipedia](https://en.wikipedia.org/wiki/Electronic_body_music)). Front 242 used the term on *No Comment* (1984) and had a club hit with "Headhunter" in 1988 ([Wikipedia](https://en.wikipedia.org/wiki/Front_242)). DAF ran an MS-20 and Odyssey from a Korg SQ-10 sequencer; one sequenced line was bass and melody at once, sometimes deliberately detuned; Conny Plank produced them ([Wikipedia](https://en.wikipedia.org/wiki/Deutsch_Amerikanische_Freundschaft)). Hardcore techno also drew on EBM ([Wikipedia](https://en.wikipedia.org/wiki/Hard_techno)).

**The NIN link [D].** Flood produced Nitzer Ebb's *Belief* ([Wikipedia](https://en.wikipedia.org/wiki/Nitzer_Ebb)) and co-produced "Closer", where he programmed the hats ([SOS](https://www.soundonsound.com/techniques/classic-tracks-nine-inch-nails-closer)).

**Not documented in the sources I could read:** a tempo range, kit sounds, bass patterns. The rest of this section is [I]:

- **Sequenced bass.** One mono voice, a repeated 16-step pattern, mostly the chord root with one or two octave or fifth moves per bar, short gates (50-70% of a 16th, about 55-80 ms at 126-138 BPM), accents on the beat.
- **Drums.** Steady four-on-the-floor or half-time, a short hard snare or clap on 2 and 4, little reverb; metallic hits as punctuation.
- **Instrumental version.** The sequence carries the hook: keep it simple, mostly root, one memorable interval. Replace the chant with a short stab or metallic hit every 2 or 4 bars (call and response). Build by adding and removing layers in 8-bar blocks, which matches the game's tier stems.

> **For an agent (EBM).** If the producer says "EBM", ask which: DAF-style minimal sequencer, Front 242 / Nitzer Ebb drive, or modern EBM-techno (Silent Servant-like, 138 BPM). Do not guess a tempo. Pass 1 ("acid/EBM") was judged horrible, way too fast, "like a circus": slow it down (half-time), lower the register and filter the sequence before adding distortion.

---

## 6. Recipes in Live 12

### 6.0 Rules for every recipe

- All numbers are starting points [I]. Confirm names and ranges with `get_device(track, device)` before `set_device_parameters`, and compare the echoed `display` with what you asked for (out-of-range display values are clamped silently, and "1/8" is read as 1).
- Iterate on the producer's sound: `duplicate_track`, mute the twin, change one thing, `capture`, `compare("latest","best")`, then ask for a labelled, loudness-matched A/B before keeping it (`.claude/skills/listening-loop/SKILL.md`).
- Live's note names: C3 = 60. MIDI 28 / 29 / 31 / 33 = E0 / F0 / G0 / A0 = 41.2 / 43.7 / 49.0 / 55.0 Hz; MIDI 45 = A1 = 110 Hz; 57 = A2 = 220 Hz.
- No limiter or loudness dynamics on stems; gain only (`05-gain-staging-and-metering.md`).

### 6.1 Big clean drone pad

**Goal.** One low root, a saw-like stack to about 2 kHz, wide above 200 Hz, almost no noise. Start from the producer's `base pad` (his edited copy of Dark Throne in Poli: `Saw` 80 %, `Sub` 35 % at `Sub Octave` -1, `Noise` 0, `LPF` 1.4 kHz, Hybrid Reverb Dark Hall 5 s at 30 %, Utility `Bass Mono` On at `Bass Freq` 120 Hz; the preset's own defaults are Saw 0 %, Pulse 0 %, Sub 39.4 % at -2 octaves, Noise 18.9 %, LPF 372 Hz, Res 2 %, Chorus C) and make it bigger without making it dirtier: body, sub, air.

| Layer | Starting values [I] | Why |
| --- | --- | --- |
| Body | Wavetable, Drift, Analog or Poli, saw (optionally a second saw an octave up, not a fifth, so chords stay chords). Unison: Wavetable `unison_mode` classic with `unison_voice_count` 4-6 (device properties, set with `set_device`) and a low `Unison Amount`, Drift unison, or Analog `Unison On/Off` with low `Unison Detune`. Total detune spread about 3-8 cents (0.35-0.9 Hz of beating at 200 Hz: slow shimmer; much more reads as out of tune). Low-pass 24 dB (Drift Type II), cutoff 1.2-2 kHz, resonance 0-10%, key tracking 0-30%. Amp attack 0.5-3 s, release 3-6 s. Noise 0. | the saw stack is the "heavy"; the filter sets the smooth top |
| Sub | Either the synth's own sub oscillator at -1 octave only (never -2: that put chord thirds at 55-65 Hz; even -1 copies every third one octave down, so the Am, F and E thirds in the table below would land at 104-131 Hz, under E2: use it only with thirds at E3 or higher), or, the safer choice, a separate root-only clip on its own track playing the "Sub root" column below; 6-12 dB under the body. `set_chain` `in_note`/`out_note` work on Drum Rack chains only, so an Instrument Rack cannot be key-split with it. | weight without low thirds |
| Air | The body patch an octave up, EQ Eight high-pass about 200 Hz, then Chorus-Ensemble with `Mode` Ensemble (`Rate` 0.3-0.5 Hz, moderate `Amount`, `Width` 100-150 %, its own high-pass: `HP On` at `HP Freq` 150-250 Hz), then Utility `Stereo Width` 120-160 %; 3-6 dB under the body. | width only above 200 Hz; no chorus on noise (the "flangy" complaint) |
| Bus | EQ Eight high-pass 25-30 Hz, optional gentle high shelf cut above 6 kHz; Utility `Bass Mono` On at `Bass Freq` 120-150 Hz; Hybrid Reverb `Algo Type` Dark Hall, `Decay` 4-6 s, `Predelay` 20-40 ms, `Dry/Wet` 20-30 %, lows below about 200 Hz removed from the wet signal (the reverb's own EQ section: `EQ Lo Type` Cut with `EQ Lo Freq`; or an EQ Eight after it). | clean lows, dark space |
| Avoid | Saturator or Roar on the whole chord; any limiter; noise; chorus on noise | intermodulation; "hollow, airy, raspy, flangy" |

**Voicings (Live names; MIDI in brackets).** Only roots, fifths and octaves under about 130 Hz (Live C2); major thirds from about 165 Hz (Live E2), minor thirds higher still ([08-arrangement-and-composition.md](08-arrangement-and-composition.md) section 2.5). The thirds below all sit at 208 Hz or higher.

| Chord | Sub root | Body notes |
| --- | --- | --- |
| Am | A0 (33) | A1 (45), E2 (52), A2 (57), C3 (60, 262 Hz), E3 (64) |
| Dm | D1 (38) | D2 (50), A2 (57), D3 (62), F3 (65, 349 Hz), A3 (69) |
| F | F0 (29) | F1 (41), C2 (48), F2 (53), A2 (57, 220 Hz), C3 (60) |
| E | E0 (28) | E1 (40), B1 (47), E2 (52), G#2 (56, 208 Hz), B2 (59) |

**Measure.** Pad stem alone: third-octave bands show the root and a smooth fall from about 2 kHz; side/mid about 0.75-0.95 above 200 Hz; mono-sub loss about 1 dB or less (`audio.mono_sub`, `mono_sub_loss_db`, as in `06-mixing.md`) and whole-pad mono-sum loss about 3 dB or less (my guideline; a larger loss in 200-2000 Hz suggests chorus comb filtering); `analyze_notes` shows no clash. Compare with the references qualitatively (root pitch, harmonic span, roll-off knee, width) on sections where the synth is exposed, never against their full-mix band levels.

> **For an agent (pad).** A/B `base pad` against the new version, same loudness (within 0.2 LU, 0.3 LU at most), labelled, alone and in the mix. "Wrong notes": check voicing, saturation and detune first. "Hollow": add saw before sub. "Too distorted": remove saturation and any limiter first.

### 6.2 Distorted rumble kick

| Stage | Starting values [I unless noted] | Source |
| --- | --- | --- |
| Main kick | 909 Core Kit or Drum Essentials kick; fundamental near the chord root (A = 55 Hz); decay 250-350 ms; EQ Eight cut 250-300 Hz; Drum Buss `Boom Amt` 40-60 % with `Boom Freq` at the fundamental (49 Hz in Attack's example), `Crunch` 0-20 %, `Damping Freq` 6-7 kHz; Saturator Medium Curve or Analog Clip, Drive 4-6 dB; Glue about -3 to -5 dB | Attack, Future Proof |
| Rumble | Parallel path (own track plus `set_sidechain`, or a rack chain): optional unsynced Delay (`L Sync`, `R Sync` and `Link` Off; `L Time` 2 ms, `R Time` 3 ms, `Feedback` 50 %); Reverb or Hybrid Reverb 3-4 s, `Dry/Wet` 100 %; Saturator Medium Curve 5-8 dB or Roar; EQ Eight high-pass 30 Hz, low-pass 150-250 Hz; Utility `Stereo Width` 0 % (or `Mono` On); level about 8-15 dB under the main kick | Attack, Bonedo, Future Proof |
| Ducking | `set_sidechain(rumble_track, kick_track, threshold_db=-30, ratio=6, release_ms=150)`; if the rumble must share the kick's track, duck it with a clip envelope on a Utility `Output` (gain, `write_automation`) | `docs/TOOLS.md` |
| Roar option | Multiband routing (a device property, not a parameter: see `get_device` and [12-live-devices-reference.md](12-live-devices-reference.md) section 1.5): mild shaper on the sub band, harder on mids, tight on highs (the Berghain idea in one device; Roar has three saturation stages and a feedback generator) | [Ableton](https://www.ableton.com/en/live/all-new-features/) |

**Measure.** Kick stem: 40-80 Hz present, 160-315 Hz slightly cut, mono-sum loss near 0 dB, crest factor not collapsed, tail ends before the next kick or loops cleanly (`file.seam`). At a 70 BPM half-time feel a 3-4 s tail spans several beats: duck or shorten it.

> **For an agent (kick).** The producer approves the rumble amount by ear on a system with sub output: offer three labelled levels (-15, -11, -8 dB) at equal integrated loudness (within 0.2 LU). Do not decide by the 40-80 Hz band level alone.

### 6.3 EBM bass sequence

| Item | Starting values [I] |
| --- | --- |
| Synth | Drift (mono voice mode, saw plus rectangle, Type II 24 dB low-pass) or Analog (saw plus sub, 24 dB low-pass) |
| Filter | cutoff 500-900 Hz, envelope amount +30-50%, envelope decay 150-250 ms, resonance 15-25% |
| Amp | attack 0-2 ms, decay 120-200 ms, sustain 60-80%, release 40-80 ms; note length 50-70% of a 16th |
| Distortion | Saturator Analog Clip 3-6 dB after the filter; one note at a time, so no intermodulation |
| EQ / stereo | EQ Eight high-pass 35-40 Hz; Utility `Mono` On; no chorus |
| Pattern A (drive) | all 16 steps on the chord root, octave on steps 4, 8, 12, 15; accents (velocity 110 vs 80) on 1, 5, 9, 13 |
| Pattern B (leaves the kick free) | root on steps 3, 7, 11, 15 plus 16; accents on 3 and 11 |
| Rolling variant | first 16th of every beat empty, sidechained to the kick (Attack's rolling bass) |

Register A0-A1 (55-110 Hz). Write with `write_notes`, then `analyze_notes` for key and chord tones (`music_theory` gives each bar's root).

> **For an agent (EBM bass).** Check rhythm, not spectrum: `analyze_notes` reports density and kick pattern; the `audio.onsets` check in `analyze_audio(take=...)` (share of onsets on the 16th grid) should be high. Ask Fred whether the sequence is the bass stem or the arp stem.

### 6.4 Industrial percussion loop

Build in a Drum Rack, one voice at a time, judging each alone.

| Voice | Source and processing (Live equivalents) | `write_drum_pattern` string |
| --- | --- | --- |
| Kick | section 6.2 | `x---x---x---x---` (or `X---x---X---x---`) |
| Closed hat | 909 hat, Redux (about 12-bit) plus Saturator, short reverb on a send (0.3-0.6 s, 100% wet) | `--x---x---x---x-` |
| Shaker | Auto Filter high-pass 24 dB, mild resonance, short reverb | `------x-------x-` |
| Noise snare | Analog or Drift noise through a low-pass, medium-long decay, Saturator, EQ Eight to soften the attack | `----x-------x---` |
| Tom | 909 low tom, Redux plus Saturator; lower velocity where it overlaps kick or hat | `---o--x----o--x-` |
| Crushed wood | woodblock, Redux about 6-bit and a low sample rate | `o--x--o---x--o--` |
| Bus | Drum Buss (`Drive Type` Medium, `Crunch` low), Glue 1-4 dB, parallel crush | |

Light swing (50-60% in MPC terms is swing 0 to 0.4 in this repo's tools, where percent = 50 + 25 x swing, see [08](08-arrangement-and-composition.md) section 4): `write_drum_pattern(swing=0.1)` (52.5 %) or `transform_notes(operation="quantize", swing=...)`, then check with `get_notes`. **Measure:** onset rate matches the grid; perc crest factor stays high; no energy below 100 Hz (the kick owns it); hats and shakers panned off-centre (Attack's Phase Fatale-style uses 7L-34L).

### 6.5 Metallic hits

Pick one method and audition it alone.

1. **Corpus** on a short noise or click burst (Suite): `Resonance Type` Plate, Beam or Pipe, `Decay` 0.2-0.8 s, `Brightness` 50-70 %, `Inharmonics` 20-60 %, `Tune` 300-900 Hz, `Dry Wet` 100 % (no slash on Corpus); then Saturator Hard Curve 4-6 dB and a 0.3-0.5 s Reverb as a stand-in for Perc's spring reverb.
2. **Collision:** mallet or noise exciter into Plate or Membrane resonators, short decay.
3. **Operator FM:** two or three operators, non-integer modulator ratios (about 1.4 or 3.5; use Fine or fixed-frequency mode), decay 150-400 ms, a little modulator feedback, EQ Eight high-pass near 300 Hz.
4. **Samples:** Mood Reel (rattling metals), Glitch and Wash (static-drenched clicks, bit-crushed kicks); pitch, clip, then a short Echo.

Check: energy mostly above 1 kHz (above the pad's roll-off), decay ends before the next kick, no sub energy.

### 6.6 Noise risers and impacts

| Stage | Starting values [I] |
| --- | --- |
| Source | Analog noise (`Noise On/Off`, `Noise Color`, `Noise Level`) or Drift noise (`Noise On`, `Noise Gain`), or a Build and Drop riser sample |
| Filter | Auto Filter (`Filter Type` High-pass, `Filter Slope` 24dB) swept from 300 Hz to 8-10 kHz over 4 or 8 bars, `Resonance` 15-30 %: `write_automation(track, "Frequency", device="Auto Filter", slot=n, shape={"type":"ramp","from":"300 Hz","to":"9 kHz"})` |
| Level / width | volume ramp about -30 to -6 dB, cut the last 1/16; Utility `Stereo Width` 60 % to 150 % |
| Space | Hybrid Reverb 3-5 s, 40-60% wet, lows removed |
| Pitch layer | optional sine or saw gliding up 12-24 semitones to the key's tonic |

Keep everything above about 200 Hz so the rise never muddies kick or pad.

### 6.7 Pack map and third-party equivalents

| Role | Where to look (installed) | Caution |
| --- | --- | --- |
| Pad / drone | Synth Essentials (Wavetable, Operator, Analog presets), Creative Extensions *Poli* and *Bass*, Granulator III Cloud mode, Mood Reel layers | *Dark Throne* is sub + noise. **Drone Lab** has instruments in alternative tunings (Pythagorean, Pelog, Solfeggio) and a just-intonation synth ([Ableton](https://www.ableton.com/en/packs/drone-lab/)); they can sound out of tune against 12-tone bass. Avoid unless asked. |
| Kick, drums | Drum Essentials (100+ Drum Racks), Core 909 kits, Build and Drop (15 Drum Racks), Glitch and Wash (bit-crushed kicks, clicks) | |
| Metal, noise, texture | Mood Reel, Glitch and Wash, PitchLoop89 (Publison-style pitch-shifting delay, with Robert Henke), Granulator III | |
| Risers, impacts | Build and Drop (rises, rushing effects, 8 Effect Racks) | |
| Orchestral Strings | none | the TRON: Ares score used no orchestra at all; avoid unless asked |

| Pro tool in the sources | Live 12 equivalent |
| --- | --- |
| Soundtoys Decapitator | Saturator (Analog Clip or Medium Curve) or one Roar stage |
| iZotope Trash, FabFilter Saturn, Waves MultiMod | Roar in Multiband routing, or an Audio Effect Rack with band-split chains |
| D16 Decimort, SP-1200 | Redux + Saturator + EQ Eight low-pass |
| Eventide H3000, EchoBoy | Echo, Delay, Chorus-Ensemble, PitchLoop89 |
| Zoom 9030 ring mod | Shifter with `Mode` Ring |
| SSL bus compressor / 1176 | Glue Compressor / Compressor (approximation) |
| Valhalla VintageVerb, EMT 250 | Hybrid Reverb (Dark Hall) or Reverb |

---

## 7. Typical numbers

| Quantity | Value | Tag / source |
| --- | --- | --- |
| Tempo | techno 120-150; industrial techno beats 126-131 and 138; hard techno 145-160; hardcore 160-200+ | D/W |
| Source NIN songs | 80-134 BPM; Noize versions unknown | W |
| Kick | fundamental about 45-60 Hz; decay 250-350 ms; pitch drop within 10-20 ms | D/W |
| Kick-bass spacing | cuts at 250-300 Hz, or 120 and 800 Hz, or 98 Hz (-4.5 dB) for a G bass (Live G1) | D |
| Rumble | reverb 3-5 s; high-pass about 30 Hz; low-pass 150-250 Hz; mono | D/W |
| Mono below | about 120-150 Hz | D/W |
| Bass bands | sub below 80 Hz; bass line 65-350 Hz | D |
| Pad (references) | root 41-49 Hz; saw-like harmonics to about 2 kHz; side/mid 0.75-0.95 above 200 Hz | project measurement |
| Clean unison detune | about 3-8 cents | I |
| Critical band | about 100 Hz wide below 500 Hz (Bark; the narrower ERB model gives 31-48 Hz at 55-220 Hz, see [11](11-listening-without-ears.md) section 4.2) | D |
| Spectral tilt | a raw saw falls 6 dB/oct; FabFilter's analyser applies a 4.5 dB/oct display tilt by default to look natural ([FabFilter](https://www.fabfilter.com/help/pro-q/using/analyzer)), implying average music falls roughly that fast [I] | D/I |
| Release dynamic range (DR, lower = more compressed) | *Pretty Hate Machine* 13, *Downward Spiral* 8, *The Fragile* 6, *Hesitation Marks* 6, TRON: Ares OST 6, Nine Inch Noize 4; Boys Noize 2007-2013 albums 5-8, lossy ([DR database](https://dr.loudness-war.info/?artist=nine+inch+nails), [Boys Noize](https://dr.loudness-war.info/?artist=boys+noize)) | W |
| Club loudness | about -6 to -5 LUFS for hard techno | W |
| Game stem sum | -14 LUFS / -1 dBTP at the top tier | project |

---

## 8. Steering with this digest

### 8.1 Complaint to cause

| Fred's word (2026-10-08) | Likely cause [I] | First single change | Check |
| --- | --- | --- | --- |
| hollow | sub + noise preset, little energy 100 Hz-2 kHz | raise the saw, noise to 0 | 160 Hz-1.6 kHz bands rise relative to 40-80 Hz |
| airy, raspy | noise oscillator, high noise | noise 0, lower the low-pass | high bands fall |
| flangy | chorus on noise, or short-delay chorus comb | no chorus on noisy layers; slow Ensemble or plain detune | mono-sum loss down |
| wrong notes, out of tune | thirds below E2 (about 165 Hz), saturated chords, big detune, alternative-tuning pack | open voicing; saturate only a mono root; detune 3-8 cents | `analyze_notes`; sub band |
| circus | bright pulses, high register, fast arps | lower register, low-pass, slower pace | bands above 3 kHz fall |
| too distorted, squashed | Saturator plus limiter on the stem | remove the limiter, lower Drive | crest factor back up |
| sounds like garbage | many global changes at once | restore the last liked take (`takes(action="restore", take=...)`) | `compare("latest","best")` |

### 8.2 Do and do not

- **Do** start from the producer's chosen sound with a muted twin, change one thing, loudness-match, label A/B; use measurements to diagnose and the human to decide; keep distortion on mono, simple elements or on a parallel, band-limited path.
- **Do not** match a full-mix reference spectrum with one instrument (it contains drums, bass and vocals); rank presets by distance to a mix; put True Peak limiters on stems or copy tutorial master chains onto them; put thirds under E2 (about 165 Hz) or saturate whole chords; use Drone Lab tunings against 12-tone bass unasked; treat unverified tempos, DR figures or aggregator data as targets.

### 8.3 What to ask the human

1. Which moment of which reference is the sound you mean? (He once pointed at the first sound after he stopped Spotify.)
2. Is the weight you want felt in the sub (40-60 Hz) or in the body (100-500 Hz)?
3. Pace: half-time at 140 (about 70 BPM feel), or straight at 126-135?
4. How dirty may kick and percussion be: clean, crunchy, crushed?
5. Is EBM here the sequenced bass, the arp, or only a flavour?
6. A or B? (loudness-matched, labelled, one change apart.)

---

## Sources

**NIN, Reznor, Ross, Moulder**
- [SOS: Alan Moulder (2000)](https://www.soundonsound.com/people/alan-moulder-recording-nine-inch-nails-smashing-pumpkins) and [Mix: Moulder, From Trident to Nine Inch Nails (2000)](https://www.mixonline.com/?p=101283) - *Fragile* drums, kick layering, pedals, filters over EQ. D.
- [SOS Classic Tracks: Closer](https://www.soundonsound.com/techniques/classic-tracks-nine-inch-nails-closer) - sources and console distortion. D.
- [iZotope Learn: Atticus Ross](https://www.izotope.com/en/learn/atticus-ross.html); [SynthHistory: Reznor (2022)](https://www.synthhistory.com/post/interview-with-trent-reznor); [MusicTech](https://musictech.com/guides/buyers-guide/five-synths-that-define-nine-inch-nails-sound/); [Gearnews](https://www.gearnews.com/how-to-sound-like-nine-inch-nails-pretty-hate-machine/); [Fact](https://factmag.com/2015/09/30/trent-reznor-moog-synthesizers-haxan-cloak); [Spill](https://spillmagazine.com/3180). D.
- Reverb Machine: [In Motion](https://reverbmachine.com/blog/trent-reznor-atticus-ross-in-motion/), [mixing notes](https://reverbmachine.com/blog/trent-reznor-social-network-synth-sounds/), [Painted Sun](https://reverbmachine.com/blog/how-reznor-ross-created-painted-sun/) - stem names are documented; patch values are the author's reconstruction. R.
- Scores and studio: [Drowned in Sound](https://www.drownedinsound.org/archive-interview-trent-reznor-discusses-the-social-network-soundtrack-4141283/), [WNYC](https://www.wnyc.org/story/trent-reznor-and-atticus-ross-gone-girl/), [Disney (Soul)](https://thewaltdisneycompany.com/news/how-original-music-adds-soul-to-pixars-new-movie/), [Spitfire (Bones and All)](https://composer.spitfireaudio.com/en/articles/trent-reznor-and-atticus-ross-on-emotively-scoring-bones-and-all), [Consequence cover story](https://consequence.net/cover-stories/trent-reznor-atticus-ross-movies-interviews/), [Suite Studios](https://blog.suitestudios.io/article/inside-the-studio-tommy-simpson-macro-micro-feature-interview), [Synthtopia (Cortini)](https://www.synthtopia.com/content/2010/08/10/alessandro-cortini-interview/). D.
- W: [Equipboard](https://equipboard.com/pros/trent-reznor); [forum quoting Keyboard (2000)](https://forum.vintagesynth.com/viewtopic.php?t=53954).
- Wikipedia: [TRON: Ares soundtrack](https://en.wikipedia.org/wiki/Tron:_Ares_%28soundtrack%29), [As Alive As You Need Me To Be](https://en.wikipedia.org/wiki/As_Alive_as_You_Need_Me_to_Be), [Challengers soundtrack](https://en.wikipedia.org/wiki/Challengers_%28soundtrack%29), [Ghosts I-IV](https://en.wikipedia.org/wiki/Ghosts_I%E2%80%93IV).

**Boys Noize and Nine Inch Noize**
- [Output](https://output.com/blog/talkback-with-boys-noize), [Roland](https://articles.roland.com/1010-by-boys-noize/), [podcast notes](https://www.buzzsprout.com/1448794/episodes/18697802-boys-noize-on-nine-inch-nails-collaboration-tron-and-his-new-label-oaz-vinyl-crate-digging) - tools and habits. D.
- [TheWrap](https://www.thewrap.com/challengers-mixed-album-boys-noize-explained/), [Paper](https://www.papermag.com/boys-noize-challengers-soundtrack), [NIN Hotline](https://www.theninhotline.com/archives/articles/display/6199) - Challengers [MIXED]. D.
- Wikipedia: [Nine Inch Noize (album)](https://en.wikipedia.org/wiki/Nine_Inch_Noize_%28album%29), [Nine Inch Noize](https://en.wikipedia.org/wiki/Nine_Inch_Noize), [Peel It Back Tour](https://en.wikipedia.org/wiki/Peel_It_Back_Tour), [Tron Ares: Divergence](https://en.wikipedia.org/wiki/Tron_Ares:_Divergence), [Boys Noize](https://en.wikipedia.org/wiki/Boys_Noize).
- NIN wiki (fan wiki, W): [Boys Noize](https://www.nin.wiki/Boys_Noize), [Nine Inch Noize](https://www.nin.wiki/Nine_Inch_Noize), [Closer](https://www.nin.wiki/Closer), [Vessel](https://www.nin.wiki/Vessel), [She's Gone Away](https://www.nin.wiki/She%27s_Gone_Away), [Came Back Haunted](https://www.nin.wiki/Came_Back_Haunted_%28song%29), [Heresy](https://www.nin.wiki/Heresy), [Memorabilia](https://www.nin.wiki/Memorabilia).
- Reviews: [Louder](https://www.loudersound.com/music/albums/nine-inch-noize-album-review), [Ghost Cult](https://ghostcultmag.com/album-review-nine-inch-noize-nine-inch-noize-the-null-corporation/), [Consequence](https://consequence.net/2026/04/nine-inch-noize-album-details/), [Spin](https://www.spinmagazine.com/2026/04/nine-inch-nails-boys-noize-new-album/); weak: [Midnight Rebels](https://midnightrebels.com/nine-inch-noize-remix-album-review/).
- Crowd data (W): [DR database, Nine Inch Nails](https://dr.loudness-war.info/?artist=nine+inch+nails), [Nine Inch Noize](https://dr.loudness-war.info/?album=nine+inch+noize), [Boys Noize](https://dr.loudness-war.info/?artist=boys+noize).

**Industrial techno and EBM**
- Attack Magazine: [Industrial Techno](https://www.attackmagazine.com/technique/beat-dissected/industrial-techno/), [Silent Servant](https://www.attackmagazine.com/technique/beat-dissected/create-raw-hypnotic-techno-like-silent-servant/), [Dark Cinematic](https://www.attackmagazine.com/technique/beat-dissected/dark-cinematic-hypnotic-techno/), [Phase Fatale](https://www.attackmagazine.com/technique/beat-dissected/hypnotic-techno-inspired-by-phase-fatales-love-is-destructive/), [Warehouse bass](https://www.attackmagazine.com/technique/tutorials/warehouse-rolling-techno-bass/), [Berghain kicks](https://www.attackmagazine.com/technique/tutorials/processing-berghain-kicks-with-multiband-distortion/), [Reverb on a kick](https://www.attackmagazine.com/technique/tutorials/adding-reverb-techno-kick/), [Distortion as a mix tool](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/), [Drones from drums](https://www.attackmagazine.com/technique/tutorials/drones-from-drums/), [LCD-style drones](https://www.attackmagazine.com/technique/synth-secrets/making-lcd-soundsystem-style-drones/), [My Studio: Perc](https://www.attackmagazine.com/features/my-studio/perc/). D.
- [Bonedo](https://www.bonedo.de/?p=932209) D; [Future Proof Music School](https://futureproofmusicschool.com/blog/making-hard-techno-a-path-to-unique-sound-design) W.
- Surgeon: [SOS](https://www.soundonsound.com/people/generations-part2-surgeon), [XLR8R](https://xlr8r.com/?p=57316). Blawan: [Fabric](https://fabriclondon.com/posts/studio-guide-blawan-london-modular-alliance-discuss-favourite-modular-units), [Sonic State](https://sonicstate.com/news/2025/12/01/blawana-kick-groove-technique). D.
- Wikipedia: [EBM](https://en.wikipedia.org/wiki/Electronic_body_music), [DAF](https://en.wikipedia.org/wiki/Deutsch_Amerikanische_Freundschaft), [Front 242](https://en.wikipedia.org/wiki/Front_242), [Nitzer Ebb](https://en.wikipedia.org/wiki/Nitzer_Ebb), [Techno](https://en.wikipedia.org/wiki/Techno), [Hardcore](https://en.wikipedia.org/wiki/Hard_techno), [Bark scale](https://en.wikipedia.org/wiki/Bark_scale), [Intermodulation](https://en.wikipedia.org/wiki/Intermodulation).

**Live and project**
- Ableton: [Live 12 features](https://www.ableton.com/en/live/all-new-features/); [audio effects](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/) and [instruments](https://www.ableton.com/en/live-manual/12/live-instrument-reference/) manual pages (my fetch truncated after Corpus and Collision); packs: [Drone Lab](https://www.ableton.com/en/packs/drone-lab/), [Build and Drop](https://www.ableton.com/en/packs/build-and-drop/), [Creative Extensions](https://www.ableton.com/en/packs/creative-extensions/), [Mood Reel](https://www.ableton.com/en/packs/mood-reel/), [Synth Essentials](https://www.ableton.com/en/packs/synth-essentials/), [Drum Essentials](https://www.ableton.com/en/packs/drum-essentials/), [Glitch and Wash](https://www.ableton.com/en/packs/glitch-and-wash/), [Granulator III](https://www.ableton.com/en/packs/granulator-iii/), [PitchLoop89](https://www.ableton.com/en/packs/pitchloop89/).
- [FabFilter Pro-Q help](https://www.fabfilter.com/help/pro-q/using/analyzer).
- Repo: `docs/handoff/2026-10-08-nova-v2-paused.md`, `docs/handoff/2026-10-08-listening-loop-references.md`, `docs/TOOLS.md`, `docs/reference/live_api_12.4.6.md`, `.claude/skills/listening-loop/SKILL.md`.

---

## Open questions / where sources disagree

1. **Noize-version tempos are mostly unknown.** The fan wiki gives the source songs at 80-134 BPM [W]; the repo's two stored measurements estimate the Noize "Vessel" and "She's Gone Away" at about 92 and 93 BPM. An untraced search-result summary gave about 127 and 134 BPM for the Noize "Closer" and "Came Back Haunted", which sits oddly with a critic saying "Closer" changes least; a blog says 95-125 BPM without method. Measure the other two with `ref` and check the half/double estimate.
2. **How long Boys Noize had.** The Consequence cover story points to about 48 hours for a first pass; the fan wiki and Paper say weeks. Probably a fast first mix then weeks of refinement; unconfirmed.
3. **"Closer" sources.** SOS: bass from an Akai sample layered with Prophet VS licks, snare through SSL distortion and ring modulation. Fan wiki: bass from a prototype OB-Mx, snare from a Roland R-70. Both may be true (source, then processing).
4. **Reznor's DAW.** Live for writing (2022), Maschine for *Hesitation Marks* (2013), Pro Tools for tracking *The Fragile* (2000). Do not state a DAW for the Noize remixes.
5. **Limiters on single tracks.** Attack recommends one per driven track as a safety net and uses one at a -12 dB ceiling as a kick transient tool, while the 2026-10-08 failure used 12 dB of limiting to chase loudness. The difference is purpose and gain reduction [I].
6. **Rumble band limits.** Bonedo low-passes at about 250 Hz, Future Proof (a school blog) says cut above 150-200 Hz, Attack's reverb-kick chain cuts 120 Hz and 800 Hz. Different recipes; test by ear.
7. **DR figures** are user submissions with unknown masters; the Noize album's DR 4 may not match what Spotify serves.
8. **Not found:** TRON: Ares synths; Noize-album hardware and plug-ins; Ancient Methods, Rebekah, I Hate Models and Paula Temple in their own words (the Paula Temple page is an Attack tutorial modelled on her track); a canonical EBM tempo range; LUFS for any of the references.
