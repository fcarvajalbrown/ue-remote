import argparse
import sys
from pathlib import Path

from bpdump import exporter, scan
from bpdump.summary import summarize

DEFAULT_ENGINE = "VER_UE5_5"


def summarize_folder(out_root):
    json_root = Path(out_root) / "json"
    count = 0
    for json_path in sorted(json_root.rglob("*.json")):
        relative = json_path.relative_to(json_root).with_suffix(".md")
        destination = Path(out_root) / "summary" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(summarize(json_path), encoding="utf-8")
        count += 1
    print(f"summarised {count}")


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="bpdump", description="Read Blueprint .uasset files offline into JSON and readable summaries.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download the pinned UAssetGUI release into .cache next to the tool, or into UASSETGUI_DIR when set")
    for name in ("export", "run"):
        step = sub.add_parser(name)
        step.add_argument("--source", required=True, help="Content folder holding .uasset files, read only")
        step.add_argument("--out", required=True, help="output folder, json/ and summary/ are created inside")
        step.add_argument("--engine", default=DEFAULT_ENGINE)
        step.add_argument("--force", action="store_true", help="re-export files that already exist")
        step.add_argument("--include", action="append", default=[], help="glob on the relative path, repeatable, for example 'SaveGame/**/*.json'")
        step.add_argument("--blueprints-only", action="store_true", help="keep only assets whose header names a parent class, whatever their file name")
    summary = sub.add_parser("summarize")
    summary.add_argument("--out", required=True)
    sweep = sub.add_parser("scan", help="identify every .uasset and .umap under a folder without UAssetGUI or the editor, one JSON line per asset")
    sweep.add_argument("--source", required=True, help="a Content folder, a project, or a folder of many projects, read only")
    sweep.add_argument("--out", required=True, help="JSONL file; assets already in it are skipped, so an interrupted run resumes")
    sweep.add_argument("--include", action="append", default=[], help="glob on the path relative to --source, repeatable")
    sweep.add_argument("--refs", action="store_true", help="list the /Game packages each asset references")
    sweep.add_argument("--names", action="store_true", help="list the spaced names inside each asset, which for a Blueprint are its variables, settings and categories")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.command == "fetch":
        exporter.fetch()
        return 0
    if args.command == "scan":
        return 0 if scan.scan(args.source, args.out, args.include, args.refs, args.names) else 1
    if args.command in ("export", "run"):
        ok = exporter.export_folder(args.source, args.out, args.engine, args.force, args.include, args.blueprints_only)
        if args.command == "run":
            summarize_folder(args.out)
        return 0 if ok else 1
    summarize_folder(args.out)
    return 0
