"""`ears`: the listening loop's analysis from the command line (no Live needed).

    ears analyze <take id | take folder>      measurement ear on a take (--strict adds file checks)
    ears check <folder> --set neon --tempo 140    delivery files named after their parts (bassA.wav ...)
    ears acceptance <masters root>            soundtrack PRD 7.5: every <set>/<bpm>/ folder, strict
    ears notes <snapshot.json>                notes ear on a snapshot (from a take or listening_snapshot)
    ears compare <a> <b> [--blind]            deltas between takes ("best" works for b)
    ears ledger | ears keep <take>            history and the best pointer
    ears calibrate                            planted-defect run (PRD 13.2), Markdown table
    ears spec                                 what the spec defines: parts, tracks, bands, tiers

Exit status: 0 when nothing failed, 1 when a check failed, 2 on usage or input errors.
`--home` (or EARS_HOME) is where takes live; `--spec` a path or bundled name (default: nova).
"""
import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__, analyze, calibration, compare, ledger, notes, report, spec as specs, take as takes


def _print(data, as_json):
    if as_json:
        print(json.dumps(report.clean(data), indent=1))
    else:
        print(json.dumps(report.clean(data), indent=1))


def _home(args):
    return Path(args.home or os.environ.get("EARS_HOME") or ".").expanduser()


def _load_spec(args, home=None):
    return specs.load(args.spec or os.environ.get("EARS_SPEC") or "nova", home)


def _take(home, ref):
    path = Path(ref).expanduser()
    if (path / "take.json").is_file():
        return takes.Take(path)
    return takes.load(home, ref)


def cmd_analyze(args):
    home = _home(args)
    spec = _load_spec(args, home)
    item = _take(home, args.take)
    result = analyze.analyze_take(item, spec, strict_mode=args.strict, images_dir=(item.path / "images") if args.images else None)
    full = report.write(result, item.path / ("report-strict.json" if args.strict else "report.json"))
    _print(report.compact(result, full), args.json)
    return 1 if result["counts"]["fail"] else 0


def _part_files(folder, spec, set_name):
    known = set(part.id for part in spec.parts(set_name)) | set(spec.fills(set_name))
    return dict((path.stem, str(path)) for path in sorted(Path(folder).glob("*.wav")) if path.stem in known)


def cmd_check(args):
    spec = _load_spec(args)
    files = _part_files(args.folder, spec, args.set)
    if not files:
        print("No part files (e.g. bassA.wav) in {0}".format(args.folder), file=sys.stderr)
        return 2
    result = analyze.analyze_files(spec, args.set, args.tempo, files, strict_mode=not args.no_strict)
    result["subject"] = str(args.folder)
    _print(report.compact(result), args.json)
    return 1 if result["counts"]["fail"] else 0


def cmd_acceptance(args):
    """Soundtrack PRD 7.5 over <root>/<set>/<bpm>/: strict checks per tempo folder, tempo consistency per set."""
    import tempfile
    from .audio import AudioFileError
    spec = _load_spec(args)
    root = Path(args.root).expanduser()
    rows, failed = [], 0
    with tempfile.TemporaryDirectory() as home:
        for set_name in spec.set_names():
            loaded = {}
            for tempo in spec.tempos(set_name):
                folder = root / set_name / takes.format_bpm(tempo)
                files = _part_files(folder, spec, set_name) if folder.is_dir() else {}
                if not files:
                    rows.append({"set": set_name, "tempo": tempo, "verdict": "fail: no part files in {0}".format(folder)})
                    failed += 1
                    continue
                try:
                    take_id = takes.from_files(home, set_name, tempo, files, spec, copy=False)
                    loaded[tempo] = takes.load(home, take_id)
                    loaded[tempo].parts()
                except (AudioFileError, OSError, ValueError) as error:
                    rows.append({"set": set_name, "tempo": tempo, "verdict": "fail: unreadable file ({0})".format(error)})
                    failed += 1
                    loaded.pop(tempo, None)
            for tempo, item in loaded.items():
                others = [other for key, other in loaded.items() if key != tempo]
                result = analyze.analyze_take(item, spec, strict_mode=True, others=others)
                fails = [entry for entry in result["checks"] if entry["status"] == "fail"]
                failed += bool(fails)
                rows.append({"set": set_name, "tempo": tempo, "verdict": result["verdict"],
                             "fails": ["{0} {1}: {2}".format(entry["check"], entry.get("subject"), entry["summary"]) for entry in fails][:8]})
    rows.sort(key=lambda row: (spec.set_names().index(row["set"]), row["tempo"]))
    if args.json:
        _print({"rows": rows, "failed": failed}, True)
    else:
        for row in rows:
            print("{0:<10} {1:>5g}  {2}".format(row["set"], row["tempo"], row["verdict"]))
            for line in row.get("fails") or []:
                print("    " + line)
        print("{0} of {1} tempo folders failed".format(failed, len(rows)))
    return 1 if failed else 0


def cmd_notes(args):
    spec = _load_spec(args)
    snapshot = json.loads(Path(args.snapshot).read_text())
    result = notes.analyze_notes(snapshot, spec, args.set, band=args.band)
    _print(report.compact(result), args.json)
    return 1 if result["counts"]["fail"] else 0


def cmd_compare(args):
    home = _home(args)
    spec = _load_spec(args, home)
    a = _take(home, args.a)
    if args.b == "best":
        best = ledger.best(home, a.set, a.tempo, a.meta.get("variation"))
        if not best:
            print("No best take for {0}".format(ledger.best_key(a.set, a.tempo, a.meta.get("variation"))), file=sys.stderr)
            return 2
        b = takes.load(home, best)
    elif args.b == "spec":
        _print(compare.compare_spec(a, spec), args.json)
        return 0
    else:
        b = _take(home, args.b)
    result = compare.compare_takes(a, b, spec, home=home)
    if args.blind:
        import time as _time
        packet = compare.blind_packet(result, a.id, b.id)
        key_file = home / "blind" / "{0}.json".format(_time.strftime("%Y%m%d-%H%M%S"))
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(json.dumps(packet["key"]))
        result = dict(packet["packet"], key_file=str(key_file))
    else:
        result.update({"a": a.id, "b": b.id})
    _print(result, args.json)
    return 0


def cmd_ledger(args):
    home = _home(args)
    _print(ledger.query(home, set_name=args.set, limit=args.limit), args.json)
    return 0


def cmd_keep(args):
    home = _home(args)
    item = takes.load(home, args.take)
    _print({"kept": item.id, "key": ledger.keep(home, item.meta)}, args.json)
    return 0


def cmd_calibrate(args):
    spec = _load_spec(args)
    rows = calibration.planted_defects(spec, args.set, args.tempo)
    if args.json:
        _print(rows, True)
    else:
        print(calibration.markdown_table(rows))
    return 0 if all(row["ok"] for row in rows) else 1


def cmd_spec(args):
    spec = _load_spec(args)
    out = {"name": spec.name, "path": spec.path, "key": "{0} {1}".format(spec.key_name, spec.mode), "sets": {}}
    for set_name in spec.set_names():
        out["sets"][set_name] = {
            "tempos": spec.tempos(set_name), "layout": spec.layout(set_name),
            "variations": dict((v, spec.progression(set_name, v)) for v in spec.variations(set_name)),
            "parts": dict((part.id, {"track": part.track, "bars": part.bars}) for part in spec.parts(set_name)),
            "bands": spec.bands(set_name), "tiers": dict((v, spec.tier_parts(set_name, v)) for v in spec.variations(set_name)),
        }
    _print(out, True)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="ears", description="Listening-loop analysis: notes, audio, compare, ledger.")
    parser.add_argument("--version", action="version", version="ears " + __version__)
    parser.add_argument("--home", help="ears home (takes, refs, calibration, ledger); default $EARS_HOME or .")
    parser.add_argument("--spec", help="spec file or bundled name (default nova)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("analyze", help="measurement ear on a take")
    item.add_argument("take")
    item.add_argument("--strict", action="store_true")
    item.add_argument("--images", action="store_true")
    item.set_defaults(func=cmd_analyze)
    item = sub.add_parser("check", help="delivery files of one set and tempo")
    item.add_argument("folder")
    item.add_argument("--set", required=True)
    item.add_argument("--tempo", type=float, required=True)
    item.add_argument("--no-strict", action="store_true")
    item.set_defaults(func=cmd_check)
    item = sub.add_parser("acceptance", help="soundtrack acceptance over <root>/<set>/<bpm>/")
    item.add_argument("root")
    item.set_defaults(func=cmd_acceptance)
    item = sub.add_parser("notes", help="notes ear on a snapshot JSON")
    item.add_argument("snapshot")
    item.add_argument("--set")
    item.add_argument("--band")
    item.set_defaults(func=cmd_notes)
    item = sub.add_parser("compare", help="deltas between two takes")
    item.add_argument("a")
    item.add_argument("b")
    item.add_argument("--blind", action="store_true")
    item.set_defaults(func=cmd_compare)
    item = sub.add_parser("ledger", help="take history")
    item.add_argument("--set")
    item.add_argument("--limit", type=int, default=20)
    item.set_defaults(func=cmd_ledger)
    item = sub.add_parser("keep", help="mark a take as the best of its set, tempo and variation")
    item.add_argument("take")
    item.set_defaults(func=cmd_keep)
    item = sub.add_parser("calibrate", help="planted-defect run (PRD 13.2)")
    item.add_argument("--set", default="neon")
    item.add_argument("--tempo", type=float, default=140.0)
    item.set_defaults(func=cmd_calibrate)
    item = sub.add_parser("spec", help="print what the spec defines")
    item.set_defaults(func=cmd_spec)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (specs.SpecError, takes.TakeError, ValueError, OSError) as error:
        print("ears: {0}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
