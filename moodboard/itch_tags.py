import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
CELL = re.compile(r'<div data-game_id="(\d+)".*?(?=<div data-game_id="|\Z)', re.S)
TITLE = re.compile(r'class="title game_link"[^>]*href="([^"]+)"[^>]*>([^<]+)<')
COVER = re.compile(r'data-lazy_src="([^"]+)"')
AUTHOR = re.compile(r'<div class="game_author"><a[^>]*>([^<]+)<')
TEXT = re.compile(r'<div class="game_text" title="([^"]*)"')


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse(page):
    for cell in CELL.finditer(page):
        block = cell.group(0)
        title = TITLE.search(block)
        if not title:
            continue
        cover = COVER.search(block)
        author = AUTHOR.search(block)
        text = TEXT.search(block)
        yield {
            "id": cell.group(1),
            "url": title.group(1),
            "title": html.unescape(title.group(2)).strip(),
            "author": html.unescape(author.group(1)) if author else "",
            "text": html.unescape(text.group(1)) if text else "",
            "cover": cover.group(1) if cover else "",
        }


def main():
    parser = argparse.ArgumentParser(description="List itch.io games for tag combinations, with cover images.")
    parser.add_argument("tags", nargs="+", help="tag paths such as tag-abstract/tag-horror")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--covers", type=Path)
    args = parser.parse_args()

    games = {}
    for tag in args.tags:
        try:
            page = fetch(f"https://itch.io/games/{tag}")
        except urllib.error.HTTPError as error:
            print(f"skip {tag}: HTTP {error.code}")
            continue
        for game in parse(page):
            game.setdefault("tags", [])
            games.setdefault(game["id"], game)["tags"].append(tag)
        time.sleep(1)

    if args.covers:
        args.covers.mkdir(parents=True, exist_ok=True)
        for game in games.values():
            if game["cover"]:
                target = args.covers / f"{game['id']}{Path(game['cover']).suffix or '.png'}"
                if not target.exists():
                    request = urllib.request.Request(game["cover"], headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(request, timeout=30) as response:
                        target.write_bytes(response.read())
                game["cover_file"] = str(target)

    args.out.write_text(json.dumps(list(games.values()), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(games)} games -> {args.out}")


if __name__ == "__main__":
    main()
