import hashlib
import subprocess
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
SEVEN_ZIP = Path("C:/Program Files/7-Zip/7z.exe")
LIBREDWG_ARCHIVE = ROOT.parent / "vendor" / "LibreDWG" / "libredwg-0.14-win64.zip"
LIBREDWG_DIR = CACHE / "libredwg"
LIBREDWG_URL = "https://github.com/LibreDWG/libredwg/releases/download/0.14/libredwg-0.14-win64.zip"
LIBREDWG_SHA256 = "1ad7e15344d20b3426c3435b078d82fb84b35062815946b2cca9c5fc9810fea8"
ARCHIVE_SUFFIXES = {".rar", ".zip", ".7z"}
USER_AGENT = "Mozilla/5.0"


def download(url, name=None):
    CACHE.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request) as response:
        final = urlparse(response.geturl()).path
        target = CACHE / (name or Path(final).name or "download.bin")
        target.write_bytes(response.read())
    return target


def unpack(archive):
    destination = CACHE / archive.stem
    subprocess.run([str(SEVEN_ZIP), "x", "-y", f"-o{destination}", str(archive)], capture_output=True, check=True)
    return destination


def fetch(url, name=None):
    target = download(url, name)
    if target.suffix.lower() in ARCHIVE_SUFFIXES:
        folder = unpack(target)
        return sorted(path for path in folder.rglob("*") if path.is_file())
    return [target]


def libredwg_archive():
    if LIBREDWG_ARCHIVE.is_file():
        return LIBREDWG_ARCHIVE
    archive = CACHE / Path(urlparse(LIBREDWG_URL).path).name
    if not archive.is_file():
        download(LIBREDWG_URL, archive.name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != LIBREDWG_SHA256:
        archive.unlink()
        raise RuntimeError(f"LibreDWG download hash {digest} is not the pinned {LIBREDWG_SHA256}")
    return archive


def libredwg_tool(tool="dwg2dxf.exe"):
    if not (LIBREDWG_DIR / tool).is_file():
        subprocess.run([str(SEVEN_ZIP), "x", "-y", f"-o{LIBREDWG_DIR}", str(libredwg_archive())], capture_output=True, check=True)
    return LIBREDWG_DIR / tool


def dwg_to_dxf(dwg_path, dxf_path):
    subprocess.run([str(libredwg_tool()), "-y", "-o", str(dxf_path), str(dwg_path)], capture_output=True)
    return Path(dxf_path).is_file()
