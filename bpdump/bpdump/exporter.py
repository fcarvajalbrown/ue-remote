import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path, PurePosixPath

RELEASE_API = "https://api.github.com/repos/atenfyr/UAssetGUI/releases/tags/{tag}"
PINNED_TAG = "v1.1.0"
EXECUTABLE_NAME = "UAssetGUI.exe"
VENDOR_DIR = Path(os.environ.get("UASSETGUI_DIR") or Path(__file__).resolve().parents[1] / ".cache" / "UAssetGUI")
PINNED_SHA256 = "b7d75c0893f1a60e565853ae638bc21f2416cd12c2d9d854e297abb87ceb3263"
EXPORT_TIMEOUT_SECONDS = 300


def executable_path():
    return VENDOR_DIR / EXECUTABLE_NAME


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    if not executable_path().is_file():
        sys.exit(f"{executable_path()} missing, run: bpdump fetch")
    if sha256_of(executable_path()) != PINNED_SHA256:
        sys.exit(f"{executable_path()} does not match PINNED_SHA256 in bpdump/exporter.py")


def fetch(tag=PINNED_TAG):
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(RELEASE_API.format(tag=tag), headers={"User-Agent": "bpdump"})
    with urllib.request.urlopen(request) as response:
        release = json.load(response)
    asset = next(item for item in release["assets"] if item["name"] == EXECUTABLE_NAME)
    urllib.request.urlretrieve(asset["browser_download_url"], executable_path())
    verify()
    print(f"saved {executable_path()} ({tag}), hash verified")


def export_one(source, destination, engine):
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(executable_path()), "tojson", str(source), str(destination), engine],
        capture_output=True,
        text=True,
        timeout=EXPORT_TIMEOUT_SECONDS,
    )
    return result.returncode == 0 and destination.is_file()


def is_blueprint(asset):
    from bpdump.scan import is_blueprint as header_says_blueprint
    try:
        return header_says_blueprint(asset)
    except OSError:
        return False


def is_included(relative, patterns):
    if not patterns:
        return True
    return any(PurePosixPath(relative.as_posix()).match(pattern) for pattern in patterns)


def export_folder(source_root, out_root, engine, force, include=(), blueprints_only=False):
    verify()
    exported = 0
    failed = []
    for asset in sorted(Path(source_root).rglob("*.uasset")):
        relative = asset.relative_to(source_root).with_suffix(".json")
        if not is_included(relative, include):
            continue
        if blueprints_only and not is_blueprint(asset):
            continue
        destination = Path(out_root) / "json" / relative
        if destination.is_file() and not force:
            continue
        if export_one(asset, destination, engine):
            exported += 1
        else:
            failed.append(str(relative))
    print(f"exported {exported}, failed {len(failed)}")
    for name in failed:
        print(f"  failed: {name}", file=sys.stderr)
    return not failed
