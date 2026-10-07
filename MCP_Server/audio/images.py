"""PNG pictures of a file for an agent that cannot listen: a spectrogram and a waveform (ffmpeg filters)."""
from .ffmpeg import AudioError, probe, run, timeout_for

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _render(info, graph):
    """Run a filter graph whose output pad [img] is one picture; returns PNG bytes."""
    completed = run("ffmpeg", ["-v", "error", "-i", info["path"], "-filter_complex", graph, "-map", "[img]",
                               "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"], timeout=timeout_for(info["duration"], 0.5))
    if not completed.stdout.startswith(PNG_SIGNATURE):
        raise AudioError("ffmpeg produced no PNG for {0}".format(info["path"]))
    return completed.stdout


def spectrogram_png(path, width=1024, height=512, info=None):
    """Log-frequency spectrogram (20 Hz to Nyquist) with time and dBFS legends."""
    info = info or probe(path)
    return _render(info, "[0:a:0]showspectrumpic=s={0}x{1}:mode=combined:color=intensity:scale=log:fscale=log:legend=1[img]".format(
        int(width), int(height)))


def waveform_png(path, width=1024, height=256, info=None):
    """Peak waveform, one lane per channel, on a white background."""
    info = info or probe(path)
    return _render(info, ("color=c=white:s={0}x{1}[bg];[0:a:0]showwavespic=s={0}x{1}:split_channels=1:colors=#1f77b4|#2ca02c:"
                          "filter=peak[wave];[bg][wave]overlay=format=auto[img]").format(int(width), int(height)))
