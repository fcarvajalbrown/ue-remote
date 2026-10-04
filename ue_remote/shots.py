import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REMOTE = HERE / "ue_remote.py"
SCREENSHOT_SCRIPT = HERE / "scripts" / "screenshot.py"
CAMERA_SCRIPT = HERE / "scripts" / "set_camera.py"
SETTLE_SECONDS = 2.5
WAIT_SECONDS = 40


def remote(args):
    environment = dict(os.environ, MSYS_NO_PATHCONV="1")
    result = subprocess.run([sys.executable, str(REMOTE)] + args, capture_output=True, text=True, env=environment)
    if result.returncode != 0:
        raise SystemExit(f"ue_remote failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def project_root(project):
    nodes = json.loads(remote(["list"]))
    for node in nodes:
        if node["project_name"].lower() == project.lower():
            return Path(node["project_root"])
    raise SystemExit(f"no open editor for {project}")


def parse_view(text):
    name, _, rest = text.partition(":")
    position, _, target = rest.partition(">")
    return {"name": name, "loc": [float(v) for v in position.split(",")], "look_at": [float(v) for v in target.split(",")]}


def orbit_views(centre, radius, height, count, start_degrees):
    views = []
    for index in range(count):
        angle = math.radians(start_degrees + 360.0 * index / count)
        loc = [centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle), centre[2] + height]
        views.append({"name": f"orbit_{index:02d}", "loc": loc, "look_at": list(centre)})
    return views


def fmt(values):
    return ",".join(f"{v:.1f}" for v in values)


def shoot(project, root, view, size, prefix, out_dir, game_view):
    name = f"{prefix}_{view['name']}"
    remote(["exec", project, "-f", str(CAMERA_SCRIPT), "--arg", f"loc={fmt(view['loc'])}", "--arg", f"look_at={fmt(view['look_at'])}", "--arg", f"game_view={int(game_view)}"])
    time.sleep(SETTLE_SECONDS)
    shots = list((root / "Saved" / "Screenshots").rglob(f"{name}.png"))
    for stale in shots:
        stale.unlink()
    remote(["exec", project, "-f", str(SCREENSHOT_SCRIPT), "--arg", f"name={name}", "--arg", f"size={size}"])
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        found = list((root / "Saved" / "Screenshots").rglob(f"{name}.png"))
        if found:
            time.sleep(0.5)
            target = out_dir / f"{name}.png"
            shutil.copyfile(found[0], target)
            return target
        time.sleep(0.5)
    raise SystemExit(f"screenshot {name} did not appear; keep the editor window in the foreground")


def main():
    parser = argparse.ArgumentParser(description="Move the editor viewport camera and save one screenshot per view.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--prefix", default="shot")
    parser.add_argument("--size", default="1280x720")
    parser.add_argument("--view", action="append", default=[], help="name:x,y,z>tx,ty,tz in Unreal centimetres")
    parser.add_argument("--views", type=Path, help="JSON list of {name, loc, look_at}")
    parser.add_argument("--orbit", help="cx,cy,cz centre in Unreal centimetres")
    parser.add_argument("--radius", type=float, default=3000)
    parser.add_argument("--height", type=float, default=600)
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--editor-ui", action="store_true", help="keep gizmos and editor overlays")
    args = parser.parse_args()

    views = [parse_view(v) for v in args.view]
    if args.views:
        views += json.loads(args.views.read_text(encoding="utf-8"))
    if args.orbit:
        views += orbit_views([float(v) for v in args.orbit.split(",")], args.radius, args.height, args.count, args.start)
    if not views:
        raise SystemExit("give --view, --views or --orbit")

    args.out.mkdir(parents=True, exist_ok=True)
    root = project_root(args.project)
    for view in views:
        print(shoot(args.project, root, view, args.size, args.prefix, args.out, not args.editor_ui))
    remote(["exec", args.project, "-c", "import unreal; unreal.EditorLevelLibrary.editor_set_game_view(False)"])


if __name__ == "__main__":
    main()
