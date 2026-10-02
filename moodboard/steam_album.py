import argparse
import html
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
API = "https://store.steampowered.com/api/appdetails?appids={}&l=english"

STYLE = """
body { font-family: Segoe UI, Arial, sans-serif; color: #151515; margin: 0; }
h1 { font-size: 22pt; margin: 0 0 4px; }
p.lead { margin: 0 0 18px; color: #444; }
section { break-inside: avoid; margin: 0 0 22px; }
h2 { font-size: 14pt; margin: 0 0 2px; }
p.meta { margin: 0 0 6px; color: #555; font-size: 9.5pt; }
p.take { margin: 0 0 8px; font-size: 10.5pt; }
.shots { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.shots img { width: 100%; display: block; }
@page { size: A4 landscape; margin: 12mm; }
"""


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def download(url, target):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        target.write_bytes(response.read())


def main():
    parser = argparse.ArgumentParser(description="Build a reference album from Steam store screenshots.")
    parser.add_argument("spec", type=Path, help="JSON: {title, lead, shots, games: [{appid, take}]}")
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    images = args.out_dir / "images"
    images.mkdir(parents=True, exist_ok=True)

    sections = []
    for game in spec["games"]:
        data = fetch_json(API.format(game["appid"])).get(str(game["appid"]), {})
        if not data.get("success"):
            print(f"skip {game['appid']}: not found")
            continue
        info = data["data"]
        developers = ", ".join(info.get("developers", []))
        released = info.get("release_date", {}).get("date", "")
        tiles = []
        for index, shot in enumerate(info.get("screenshots", [])[: spec.get("shots", 3)]):
            name = f"{game['appid']}_{index}.jpg"
            target = images / name
            if not target.exists():
                download(shot["path_full"], target)
            tiles.append(f'<img src="images/{name}">')
        sections.append(
            f"<section><h2>{html.escape(info['name'])}</h2>"
            f"<p class='meta'>{html.escape(developers)} &middot; {html.escape(released)} &middot; "
            f"store.steampowered.com/app/{game['appid']}</p>"
            f"<p class='take'>{html.escape(game['take'])}</p>"
            f"<div class='shots'>{''.join(tiles)}</div></section>"
        )
        print(f"ok {info['name']}")
        time.sleep(1)

    page = (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(spec['title'])}</title>"
        f"<style>{STYLE}</style></head><body><h1>{html.escape(spec['title'])}</h1>"
        f"<p class='lead'>{html.escape(spec['lead'])}</p>{''.join(sections)}</body></html>"
    )
    page_path = args.out_dir / "album.html"
    page_path.write_text(page, encoding="utf-8")
    print(f"wrote {page_path}")

    if args.pdf:
        with tempfile.TemporaryDirectory() as scratch:
            subprocess.run(
                [str(EDGE), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                 f"--user-data-dir={scratch}", f"--print-to-pdf={args.pdf.resolve()}", page_path.resolve().as_uri()],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        print(f"wrote {args.pdf.resolve()}")


if __name__ == "__main__":
    main()
