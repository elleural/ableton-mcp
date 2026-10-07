"""Release packaging: loudness normalisation, dither, encoding, tags, artwork and release.json.

Normalisation is two-pass. Pass one measures the source (EBU R128). When the true peak allows, the
gain is linear and exact. Otherwise the gain feeds a true-peak limiter (4x oversampled ffmpeg
alimiter), re-measured and corrected until loudness is within 0.2 LU and the true peak under the
ceiling. Encodes come from that float premaster: 16-bit gets triangular dither; lossy files whose
true peak rises above the ceiling are re-encoded slightly quieter.
"""
import hashlib
import json
import math
import os
import shutil
import tempfile
import time

from .analysis import measure_loudness, parse_ebur128, rounded
from .ffmpeg import AudioError, check_file, has_encoder, probe, run, timeout_for
from .render import default_dir, manifest_for, safe_filename

FORMATS = {
    "wav24": {"ext": ".wav", "suffix": " (24-bit)", "label": "WAV 24-bit", "muxer": "wav"},
    "wav16": {"ext": ".wav", "suffix": " (16-bit)", "label": "WAV 16-bit, triangular dither", "muxer": "wav"},
    "flac": {"ext": ".flac", "suffix": "", "label": "FLAC 24-bit", "muxer": "flac"},
    "mp3": {"ext": ".mp3", "suffix": "", "label": "MP3 320 kbps CBR", "muxer": "mp3"},
    "aac": {"ext": ".m4a", "suffix": "", "label": "AAC 256 kbps (M4A)", "muxer": "ipod"},
}
DEFAULT_FORMATS = ("wav24", "wav16", "flac", "mp3", "aac")
ARTWORK_FORMATS = ("flac", "mp3", "aac")
LOSSY = ("mp3", "aac")
OVERSAMPLE = 4
LIMITER_MARGIN = 0.3      # dB under the ceiling for the limiter at first
LOUDNESS_TOLERANCE = 0.2  # LU
TP_SAFETY = 0.05          # dB: ffmpeg prints true peak to 0.1 dB, so a printed -1.0 may really be -0.96
MAX_PASSES = 6
LOSSY_RETRIES = 2
DITHER_16 = "aresample=osf=s16:dither_method=triangular"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_formats(formats):
    """Validated list of format keys (defaults to every format)."""
    if formats is None:
        return list(DEFAULT_FORMATS)
    if isinstance(formats, str):
        formats = [formats]
    chosen = []
    for item in formats:
        key = str(item).strip().lower().replace("-", "").replace(" ", "")
        key = {"wav": "wav24", "m4a": "aac"}.get(key, key)
        if key not in FORMATS:
            raise AudioError("Unknown format {0!r}. Formats: {1}".format(item, ", ".join(FORMATS)))
        if key not in chosen:
            chosen.append(key)
    if not chosen:
        raise AudioError("formats is empty. Formats: " + ", ".join(FORMATS))
    return chosen


def _float_chain(*filters):
    return ",".join(("aformat=sample_fmts=flt",) + tuple(item for item in filters if item))


def render_measured(source_info, destination, chain):
    """Render source through an audio filter chain to a float WAV and measure it (EBU R128) in one pass."""
    meter = "ebur128=peak=true" + (":dualmono=true" if source_info["channels"] == 1 else "")
    graph = "[0:a:0]{0},asplit=2[out][meter];[meter]{1}[metered]".format(chain, meter)
    completed = run("ffmpeg", ["-nostats", "-y", "-i", source_info["path"], "-filter_complex", graph,
                               "-map", "[out]", "-c:a", "pcm_f32le", destination, "-map", "[metered]", "-f", "null", "-"],
                    timeout=timeout_for(source_info["duration"], 2.0))
    return parse_ebur128(completed.stderr.decode("utf-8", "replace"))


def limiter_chain(gain_db, ceiling_dbtp, sample_rate):
    """Gain into a 4x-oversampled lookahead limiter (latency compensated), back at the source rate."""
    return _float_chain(
        "volume={0:.4f}dB".format(gain_db),
        "aresample={0}".format(sample_rate * OVERSAMPLE),
        "alimiter=limit={0:.6f}:attack=5:release=50:level=0:latency=1".format(max(0.0625, 10.0 ** (ceiling_dbtp / 20.0))),
        "aresample={0}".format(sample_rate),
    )


def normalize(source_info, measured, target_lufs, true_peak, workdir, name="premaster.wav"):
    """Write a float premaster at target_lufs with its true peak at or under true_peak (dBTP).

    Returns (premaster path, its measurement, a report of what was done).
    """
    integrated, peak = measured["integrated"], measured["true_peak"]
    if not math.isfinite(integrated):
        raise AudioError("The source is silent or too short to measure loudness (it needs at least 0.4 s of sound)")
    premaster = os.path.join(workdir, name)
    gain = target_lufs - integrated
    report = {"source_lufs": rounded(integrated, 1), "source_true_peak_dbtp": rounded(peak, 1), "target_lufs": target_lufs,
              "true_peak_ceiling_dbtp": true_peak}
    if math.isfinite(peak) and peak + gain <= true_peak - 0.1:
        after = render_measured(source_info, premaster, _float_chain("volume={0:.4f}dB".format(gain)))
        report.update(method="linear", gain_db=round(gain, 2))
        return premaster, after, report
    margin, passes = LIMITER_MARGIN, 0
    while True:
        passes += 1
        used_gain, used_ceiling = gain, true_peak - margin
        after = render_measured(source_info, premaster, limiter_chain(used_gain, used_ceiling, source_info["sample_rate"]))
        miss, over = target_lufs - after["integrated"], after["true_peak"] - (true_peak - TP_SAFETY)
        if (abs(miss) <= LOUDNESS_TOLERANCE and over <= 0) or passes >= MAX_PASSES:
            break
        if over > 0:
            margin += over + 0.1
        gain += miss
    report.update(method="limited", gain_db=round(used_gain, 2), limiter_ceiling_dbtp=round(used_ceiling, 2), passes=passes,
                  gain_reduction_db=rounded(max(0.0, peak + used_gain - used_ceiling), 1) if math.isfinite(peak) else None)
    return premaster, after, report


def prepare_artwork(path, workdir):
    """(file to embed, info) for an artwork image; non-JPEG/PNG images are converted to PNG."""
    full = check_file(path, "Artwork")
    try:
        info = probe_image(full)
    except AudioError:
        raise AudioError("Artwork {0} is not a readable image".format(full))
    if info["codec"] in ("mjpeg", "png"):
        return full, info
    converted = os.path.join(workdir, "cover.png")
    run("ffmpeg", ["-v", "error", "-y", "-i", full, "-frames:v", "1", converted], timeout=60)
    return converted, probe_image(converted)


def probe_image(path):
    raw = run("ffprobe", ["-v", "error", "-print_format", "json", "-show_streams", path], timeout=30).stdout
    streams = [item for item in json.loads(raw.decode("utf-8", "replace")).get("streams") or [] if item.get("codec_type") == "video"]
    if not streams:
        raise AudioError("{0} is not an image".format(path))
    return {"codec": streams[0].get("codec_name"), "width": streams[0].get("width"), "height": streams[0].get("height")}


def encode(premaster, fmt, destination, tags, artwork=None, duration=None):
    """Encode the premaster into one format, tagged, with artwork where the container supports it."""
    spec = FORMATS[fmt]
    arguments = ["-v", "error", "-y", "-i", premaster]
    embed = artwork is not None and fmt in ARTWORK_FORMATS
    if embed:
        arguments += ["-i", artwork]
    arguments += ["-map", "0:a:0"]
    if embed:
        arguments += ["-map", "1:v:0", "-c:v", "copy", "-disposition:v:0", "attached_pic"]
    filters = []
    if fmt == "wav24":
        codec = ["-c:a", "pcm_s24le", "-write_id3v2", "1"]
    elif fmt == "wav16":
        filters.append(DITHER_16)
        codec = ["-c:a", "pcm_s16le", "-write_id3v2", "1"]
    elif fmt == "flac":
        codec = ["-c:a", "flac", "-sample_fmt", "s32", "-compression_level", "8"]
        if embed:
            codec += ["-metadata:s:v", "comment=Cover (front)"]
    elif fmt == "mp3":
        codec = ["-c:a", "libmp3lame", "-b:a", "320k", "-id3v2_version", "3", "-write_xing", "1"]
        if embed:
            codec += ["-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)"]
    else:  # aac
        if has_encoder("aac_at"):
            filters.append(DITHER_16)  # AudioToolbox takes 16-bit input
            codec = ["-c:a", "aac_at", "-b:a", "256k", "-aac_at_mode", "cvbr"]
        else:
            codec = ["-c:a", "aac", "-b:a", "256k"]
        codec += ["-movflags", "+faststart"]
    if filters:
        arguments += ["-af", ",".join(filters)]
    arguments += codec
    for key, value in tags.items():
        if value not in (None, ""):
            arguments += ["-metadata", "{0}={1}".format(key, value)]
    folder = os.path.dirname(destination)
    partial = os.path.join(folder, ".{0}.part{1}".format(os.path.basename(destination), spec["ext"]))
    try:
        run("ffmpeg", arguments + ["-f", spec["muxer"], partial], timeout=timeout_for(duration, 1.0))
        os.replace(partial, destination)
    finally:
        if os.path.exists(partial):
            os.remove(partial)
    return destination


def describe_file(path, fmt):
    info = probe(path)
    loudness = measure_loudness(path, info)
    return {
        "format": fmt,
        "file": os.path.basename(path),
        "path": path,
        "codec": info["codec"],
        "sample_rate": info["sample_rate"],
        "channels": info["channels"],
        "bit_depth": info["bit_depth"] if fmt not in LOSSY else None,
        "bitrate_kbps": round(info["bit_rate"] / 1000.0) if fmt in LOSSY and info["bit_rate"] else None,
        "duration_seconds": round(info["duration"], 3),
        "integrated_lufs": rounded(loudness["integrated"], 1),
        "true_peak_dbtp": rounded(loudness["true_peak"], 1),
        "loudness_range_lu": rounded(loudness["range"], 1),
        "artwork": info["artwork"],
        "tags": dict((key, info["tags"].get(key)) for key in ("title", "artist", "album", "date", "genre", "track") if info["tags"].get(key)),
        "bytes": os.path.getsize(path),
        "sha256": sha256(path),
    }


def resolve_stems(stems, source):
    """Stem paths: a list of files, or "auto" for the other files of the source's bounce (bounce.json)."""
    if stems is None:
        return []
    if isinstance(stems, str) and stems.strip().lower() == "auto":
        manifest, entry = manifest_for(source)
        if manifest is None:
            raise AudioError("stems='auto' needs a bounced source with bounce.json beside it; pass stem file paths instead")
        folder = os.path.dirname(os.path.abspath(source))
        return [os.path.join(folder, item["path"]) for item in manifest["files"] if item.get("role") != "master"]
    if isinstance(stems, str):
        stems = [stems]
    return [check_file(path, "Stem file") for path in stems]


def create_release(source, title, artist, album=None, year=None, genre=None, track_number=None, artwork=None,
                   target_lufs=-14.0, true_peak=-1.0, formats=None, output_dir=None, stems=None, live_info=None):
    """Master, encode, tag and package a release folder with release.json. Returns the manifest."""
    if not title or not artist:
        raise AudioError("title and artist are required")
    if not -40.0 <= float(target_lufs) <= -5.0:
        raise AudioError("target_lufs must be between -40 and -5 LUFS (streaming: -14)")
    if not -9.0 <= float(true_peak) <= 0.0:
        raise AudioError("true_peak must be between -9 and 0 dBTP (streaming: -1)")
    chosen = parse_formats(formats)
    source_info = probe(check_file(source, "Source"))
    stem_paths = resolve_stems(stems, source_info["path"])
    base = safe_filename("{0} - {1}".format(artist, title))
    folder = os.path.abspath(os.path.expanduser(output_dir or default_dir("Releases", base)))
    os.makedirs(folder, exist_ok=True)
    tags = {"title": title, "artist": artist, "album_artist": artist, "album": album or title,
            "date": str(year) if year else None, "genre": genre, "track": str(track_number) if track_number else None}
    warnings = []
    workdir = tempfile.mkdtemp(prefix="abletonmcp-release-")
    try:
        measured = measure_loudness(source_info["path"], source_info)
        premaster, after, mastering = normalize(source_info, measured, float(target_lufs), float(true_peak), workdir)
        mastering["premaster_lufs"] = rounded(after["integrated"], 2)
        mastering["premaster_true_peak_dbtp"] = rounded(after["true_peak"], 2)
        if mastering.get("gain_reduction_db") and mastering["gain_reduction_db"] > 6:
            warnings.append("Heavy limiting (~{0} dB): raise the mix level or choose a quieter target".format(mastering["gain_reduction_db"]))
        art_path, art_info = (prepare_artwork(artwork, workdir) if artwork else (None, None))
        files = []
        lossy_master, lossy_ceiling = premaster, float(true_peak)
        for fmt in chosen:
            destination = os.path.join(folder, base + FORMATS[fmt]["suffix"] + FORMATS[fmt]["ext"])
            attempts = 0
            while True:
                encode(lossy_master if fmt in LOSSY else premaster, fmt, destination, tags, art_path, source_info["duration"])
                record = describe_file(destination, fmt)
                over = (record["true_peak_dbtp"] if record["true_peak_dbtp"] is not None else -99.0) - (float(true_peak) - TP_SAFETY)
                if fmt not in LOSSY or over <= 0.0 or attempts >= LOSSY_RETRIES:
                    break
                # Lossy encoding overshoots the true peak: limit a copy harder at the same loudness and re-encode.
                attempts += 1
                lossy_ceiling -= over + 0.2
                lossy_master, _, lossy_report = normalize(source_info, measured, float(target_lufs), lossy_ceiling, workdir, "premaster-lossy.wav")
                mastering["lossy_true_peak_ceiling_dbtp"] = round(lossy_ceiling, 2)
                mastering["lossy_method"] = lossy_report["method"]
            if fmt in LOSSY and lossy_master != premaster:
                record["limited_for_encoding"] = True
            if fmt in LOSSY and over > 0.0:
                warnings.append("{0}: true peak {1} dBTP is above the ceiling after encoding".format(fmt, record["true_peak_dbtp"]))
            record["label"] = FORMATS[fmt]["label"]
            files.append(record)
        if lossy_master != premaster:
            warnings.append("Lossy encodes overshot the true-peak ceiling, so they come from a premaster limited to {0:.1f} dBTP "
                            "at the same loudness".format(lossy_ceiling))
        cover = None
        if art_path:
            cover_path = os.path.join(folder, "cover" + os.path.splitext(art_path)[1].lower().replace(".jpeg", ".jpg"))
            shutil.copyfile(art_path, cover_path)
            cover = {"file": os.path.basename(cover_path), "width": art_info["width"], "height": art_info["height"], "sha256": sha256(cover_path)}
            if any(fmt in ("wav24", "wav16") for fmt in chosen):
                warnings.append("WAV files carry tags but no embedded artwork (the format has no standard picture field); cover is beside them")
        stem_records = copy_stems(stem_paths, folder, base)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    manifest = {
        "title": title, "artist": artist, "album": tags["album"], "year": year, "genre": genre, "track_number": track_number,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "generator": "AbletonMCP",
        "live": live_info,
        "source": {"path": source_info["path"], "sha256": sha256(source_info["path"]), "duration_seconds": round(source_info["duration"], 3),
                   "sample_rate": source_info["sample_rate"], "bit_depth": source_info["bit_depth"]},
        "mastering": mastering,
        "duration_seconds": round(source_info["duration"], 3),
        "files": [dict((key, value) for key, value in record.items() if key != "path") for record in files],
        "artwork": cover,
        "stems": stem_records,
        "warnings": warnings,
    }
    path = os.path.join(folder, "release.json")
    with open(path, "w") as handle:
        json.dump(manifest, handle, indent=2)
    return dict(manifest, folder=folder, manifest=path, file_paths=[record["path"] for record in files])



def copy_stems(paths, folder, base):
    """Copy stems unprocessed (pre-master levels) into <folder>/Stems with checksums."""
    if not paths:
        return []
    target = os.path.join(folder, "Stems")
    os.makedirs(target, exist_ok=True)
    records = []
    for path in paths:
        info = probe(path)
        name = os.path.splitext(os.path.basename(path))[0]
        label = name.split(" - ", 1)[1] if " - " in name else name
        destination = os.path.join(target, "{0} - {1}.wav".format(base, safe_filename(label)))
        if info["container"] == "wav":
            shutil.copyfile(path, destination)
        else:
            run("ffmpeg", ["-v", "error", "-y", "-i", path, "-map", "0:a:0", "-c:a", "pcm_s24le", destination], timeout=timeout_for(info["duration"]))
        records.append({"file": os.path.join("Stems", os.path.basename(destination)), "source": path, "duration_seconds": round(info["duration"], 3),
                        "bytes": os.path.getsize(destination), "sha256": sha256(destination)})
    return records
