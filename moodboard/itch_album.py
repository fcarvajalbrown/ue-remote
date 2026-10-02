import argparse
import html
import json
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
SHOT = re.compile(r'<a[^>]+href="(https://img\.itch\.zone/[^"]+)"[^>]*data-image_lightbox')
SHOT_FALLBACK = re.compile(r'class="screenshot_list".*?</div>', re.S)
HREF = re.compile(r'href="(https://img\.itch\.zone/[^"]+)"')
TITLE = re.compile(r'<title>([^<]+?)(?: by [^<]*)?</title>')
AUTHOR = re.compile(r'<meta name="twitter:creator" content="@?([^"]+)"')

STYLE = """
body { font-family: Segoe UI, Arial, sans-serif; color: #151515; margin: 0; }
h1 { font-size: 22pt; margin: 0 0 4px; }
p.lead { margin: 0 0 18px; color: #444; }
section { break-inside: avoid; margin: 0 0 22px; }
h2 { font-size: 14pt; margin: 0 0 2px; }
p.meta { margin: 0 0 6px; color: #555; font-size: 9.5pt; }
p.take { margin: 0 0 8px; font-size: 10.5pt; }
.shots { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.shots img { width: 100%; height: 190px; object-fit: cover; display: block; }
@page { size: A4 landscape; margin: 12mm; }
"""


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def screenshots(page):
    found = SHOT.findall(page)
    if not found:
        block = SHOT_FALLBACK.search(page)
        found = HREF.findall(block.group(0)) if block else []
    return list(dict.fromkeys(found))


def collect(url, images, limit):
    page = fetch(url).decode("utf-8", errors="ignore")
    title = TITLE.search(page)
    author = url.split("//")[1].split(".itch.io")[0]
    files = []
    for index, shot in enumerate(screenshots(page)[:limit]):
        slug = url.rstrip("/").split("/")[-1]
        target = images / f"{author}_{slug}_{index}{Path(shot).suffix or '.png'}"
        if not target.exists():
            target.write_bytes(fetch(shot))
        files.append(target)
    return (html.unescape(title.group(1)) if title else url), author, files


def main():
    parser = argparse.ArgumentParser(description="Build a reference album from itch.io game pages.")
    parser.add_argument("spec", type=Path, help="JSON: {title, lead, shots, games: [{url, take}]}")
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    images = args.out_dir / "images"
    images.mkdir(parents=True, exist_ok=True)

    sections = []
    for game in spec["games"]:
        title, author, files = collect(game["url"], images, spec.get("shots", 3))
        tiles = "".join(f'<img src="images/{f.name}">' for f in files)
        take = f"<p class='take'>{html.escape(game['take'])}</p>" if game.get("take") else ""
        sections.append(
            f"<section><h2>{html.escape(title)}</h2>"
            f"<p class='meta'>{html.escape(author)} &middot; {html.escape(game['url'])}</p>"
            f"{take}<div class='shots'>{tiles}</div></section>"
        )
        print(f"ok {title}: {len(files)} shots")
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
