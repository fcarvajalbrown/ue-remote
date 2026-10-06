import argparse
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
BPDUMP = os.path.join(HERE, "bpdump.py")
INCLUDES = ["BP_*", "ABP_*", "WBP_*", "*/Blueprints/*"]
ENGINES = ["VER_UE5_5", "VER_UE4_27"]
PER_EXPORT_GB = 1.5


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


def stem(name):
    base = os.path.splitext(name)[0]
    return "".join(c if c.isalnum() or c in "-_ ." else "_" for c in base).strip()


def wanted(rec):
    return rec.get("status") == "ok" and (rec.get("uasset", 0) > 0 or rec.get("umap", 0) > 0)


def finished(log_path):
    done = set()
    if not os.path.exists(log_path):
        return done
    pat = re.compile(r"^(.*): (ok|no blueprints exported)$")
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            m = pat.match(line.rstrip("\n"))
            if m:
                done.add(m.group(1))
    return done


def extract(zip_path, dest):
    if os.path.isdir(dest) and any(os.scandir(dest)):
        return "already"
    partial = dest + ".partial"
    if os.path.isdir(partial):
        shutil.rmtree(partial)
    os.makedirs(partial)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            z.extract(info, partial)
    os.rename(partial, dest)
    return "extracted"


def find_content_roots(dest):
    roots = []
    for dirpath, dirnames, _ in os.walk(dest):
        if os.path.basename(dirpath) == "Content":
            roots.append(dirpath)
    return roots or [dest]


def export(source, out, engine):
    cmd = [sys.executable, BPDUMP, "run", "--source", source, "--out", out, "--engine", engine]
    for pat in INCLUDES:
        cmd += ["--include", pat]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-2:]
    return proc.returncode, " | ".join(tail)


def succeeded(summary):
    m = re.search(r"exported (\d+), failed (\d+) \| summarised (\d+)", summary)
    return bool(m) and int(m.group(2)) == 0 and int(m.group(3)) > 0


class ExportGate:
    def __init__(self, slots, min_free_gb):
        self.slots = slots
        self.min_free_gb = min_free_gb
        self.running = 0
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                need = self.min_free_gb + PER_EXPORT_GB * self.running
                if self.running < self.slots and free_gb() >= need:
                    self.running += 1
                    return
            time.sleep(10)

    def release(self):
        with self.lock:
            self.running -= 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--zip-dir", required=True)
    ap.add_argument("--extract-root", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--exports", type=int, default=2)
    ap.add_argument("--min-free-gb", type=float, default=2.5)
    args = ap.parse_args()

    recs = [json.loads(l) for l in open(args.inventory, encoding="utf-8")]
    skip = finished(args.log)
    todo = [
        r for r in recs
        if wanted(r)
        and (not args.only or r["file"] in args.only)
        and stem(r["file"]) not in skip
    ]

    gate = ExportGate(args.exports, args.min_free_gb)
    log_lock = threading.Lock()

    def write(line):
        with log_lock:
            with open(args.log, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def run_pack(r):
        zip_path = os.path.join(args.zip_dir, r["file"])
        name = stem(r["file"])
        dest = os.path.join(args.extract_root, name)
        out = os.path.join(args.out_root, name)
        state = extract(zip_path, dest)
        write(f"{name}: {state}")
        done = False
        for engine in ENGINES:
            for source in find_content_roots(dest):
                gate.acquire()
                try:
                    code, tail = export(source, out, engine)
                finally:
                    gate.release()
                write(f"{name} [{engine}] {os.path.relpath(source, dest)}: {tail}")
                if code == 0 and succeeded(tail):
                    done = True
            if done:
                break
        write(f"{name}: {'ok' if done else 'no blueprints exported'}")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_pack, r) for r in todo]
        for f in futures:
            f.result()


if __name__ == "__main__":
    main()
