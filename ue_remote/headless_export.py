import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT_SCRIPT = os.path.join(HERE, "scripts", "export_assets.py")
PROJECT_NAME = "HeadlessExport"


class MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def free_gb():
    st = MemoryStatus()
    st.dwLength = ctypes.sizeof(st)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullAvailPhys / 2**30


def ensure_project(work, engine_version):
    project_dir = os.path.join(work, PROJECT_NAME)
    os.makedirs(os.path.join(project_dir, "Content"), exist_ok=True)
    uproject = os.path.join(project_dir, PROJECT_NAME + ".uproject")
    spec = {
        "FileVersion": 3,
        "EngineAssociation": engine_version,
        "Plugins": [
            {"Name": "PythonScriptPlugin", "Enabled": True},
            {"Name": "EditorScriptingUtilities", "Enabled": True},
        ],
    }
    with open(uproject, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=1)
    return project_dir, uproject


def content_roots(pack):
    roots = []
    for dirpath, dirnames, _ in os.walk(pack):
        if os.path.basename(dirpath) == "Content":
            roots.append(dirpath)
            dirnames.clear()
    return roots or [root_from_package_paths(pack)]


def root_from_package_paths(pack):
    for dirpath, _, names in os.walk(pack):
        for name in names:
            if not name.lower().endswith(".uasset"):
                continue
            stem = os.path.splitext(name)[0]
            with open(os.path.join(dirpath, name), "rb") as fh:
                data = fh.read()
            found = re.search(rb"/Game/((?:[A-Za-z0-9_]+/)*)" + re.escape(stem.encode()) + rb"(?![A-Za-z0-9_])", data)
            if not found:
                continue
            depth = found.group(1).decode().count("/")
            root = dirpath
            for _ in range(depth):
                root = os.path.dirname(root)
            return root
    return pack


def manifest_path(content):
    return os.path.join(os.path.dirname(content), "moved.json")


def restore(content):
    path = manifest_path(content)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        moves = json.load(fh)
    for inside, original in moves:
        if os.path.exists(inside) and not os.path.exists(original):
            os.rename(inside, original)
    os.remove(path)


def move_in(pack, content):
    moves = []
    for root in content_roots(pack):
        for entry in os.scandir(root):
            if not entry.is_dir():
                continue
            target = os.path.join(content, entry.name)
            if os.path.exists(target):
                continue
            moves.append([target, entry.path])
    with open(manifest_path(content), "w", encoding="utf-8") as fh:
        json.dump(moves, fh)
    for inside, original in moves:
        os.rename(original, inside)
    return [os.path.basename(m[0]) for m in moves]


def run_commandlet(editor_cmd, uproject, script, script_args, log_path):
    env = dict(os.environ)
    env["UE_SCRIPT_ARGS"] = json.dumps(script_args)
    cmd = [
        editor_cmd, uproject,
        "-run=pythonscript", f"-script={script}",
        "-unattended", "-nosplash", "-AllowCommandletRendering", "-nopause", "-stdout", "-FullStdOutLogOutput",
    ]
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
    return proc.returncode


def summary(log_path):
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        for line in reversed(fh.readlines()):
            if "export_assets: done" in line or "blueprints matched" in line:
                return line.strip().split("Display: ", 1)[-1]
    return "no summary line, see log"


def main():
    ap = argparse.ArgumentParser(description="Export every static and skeletal mesh of an extracted Unreal pack to FBX with a headless editor commandlet. No window opens and no running editor is touched.")
    ap.add_argument("packs", nargs="+", help="extracted pack folders that contain a Content folder")
    ap.add_argument("--out", required=True, help="output root; each pack gets a subfolder")
    ap.add_argument("--work", required=True, help="folder for the throwaway project, on a drive with space")
    ap.add_argument("--engine", default=os.environ.get("UE_ROOT", r"D:\EpicGames\UE_5.5"))
    ap.add_argument("--engine-version", default="5.5")
    ap.add_argument("--min-free-gb", type=float, default=4.0)
    ap.add_argument("--script", default=EXPORT_SCRIPT, help="editor script to run; defaults to the mesh FBX export")
    ap.add_argument("--arg", action="append", default=[], help="extra key=value for the script, repeatable")
    args = ap.parse_args()

    editor_cmd = os.path.join(args.engine, "Engine", "Binaries", "Win64", "UnrealEditor-Cmd.exe")
    if not os.path.exists(editor_cmd):
        print(f"not found: {editor_cmd}")
        return 2
    project_dir, uproject = ensure_project(args.work, args.engine_version)
    content = os.path.join(project_dir, "Content")
    restore(content)

    for pack in args.packs:
        name = os.path.basename(os.path.normpath(pack))
        while free_gb() < args.min_free_gb:
            print(f"{name}: waiting, free RAM {free_gb():.1f} GB")
            time.sleep(30)
        restore(content)
        linked = move_in(pack, content)
        if not linked:
            print(f"{name}: no Content folder")
            continue
        destination = os.path.join(args.out, name)
        os.makedirs(destination, exist_ok=True)
        log_path = os.path.join(destination, "_headless.log")
        script_args = {"root": ["/Game"], "destination": [destination.replace("\\", "/")]}
        for item in args.arg:
            key, _, value = item.partition("=")
            script_args.setdefault(key, []).append(value)
        try:
            code = run_commandlet(editor_cmd, uproject, args.script, script_args, log_path)
        finally:
            restore(content)
        print(f"{name}: exit={code} {summary(log_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
