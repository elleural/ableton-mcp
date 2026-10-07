"""Audio processing for AbletonMCP (WS-E), pure Python with ffmpeg and numpy; nothing here talks to Live.

- ffmpeg:   locate and run ffmpeg / ffprobe, probe and decode files
- analysis: EBU R128 loudness, levels, stereo image, spectral balance, sections, dropouts
- images:   spectrogram and waveform PNGs
- render:   deliver a recorded bounce (sample-exact trim, bounce.json)
- release:  normalise, dither, encode, tag, artwork, release.json
"""
from .ffmpeg import AudioError, available  # noqa: F401
