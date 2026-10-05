import argparse
import datetime
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
AGENT = "ue-remote-commons-fetch/1.0 (https://github.com/fcarvajalbrown/ue-remote)"
FIELDS = "LicenseShortName|LicenseUrl|Artist|Credit|ImageDescription|DateTimeOriginal|AttributionRequired|UsageTerms"


def get(url, attempts=4):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (ConnectionError, TimeoutError, urllib.error.URLError):
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))


def query(params):
    params = {"action": "query", "format": "json", "prop": "imageinfo",
              "iiprop": "url|size|extmetadata", "iiextmetadatafilter": FIELDS, **params}
    data = json.loads(get(API + "?" + urllib.parse.urlencode(params)))
    return list(data.get("query", {}).get("pages", {}).values())


def plain(meta, key):
    value = meta.get(key, {}).get("value", "")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(value))).strip()
    half = len(text) // 2
    return text[:half] if len(text) % 2 == 0 and text[:half] == text[half:] else text


def describe(page):
    info = page["imageinfo"][0]
    meta = info["extmetadata"]
    return {
        "title": page["title"],
        "page_url": info["descriptionurl"],
        "width": info["width"],
        "height": info["height"],
        "author": plain(meta, "Artist"),
        "credit": plain(meta, "Credit"),
        "licence": plain(meta, "LicenseShortName"),
        "licence_url": plain(meta, "LicenseUrl"),
        "attribution_required": plain(meta, "AttributionRequired"),
        "description": plain(meta, "ImageDescription"),
        "taken": plain(meta, "DateTimeOriginal"),
    }


def search(args):
    pages = query({"generator": "search", "gsrnamespace": 6, "gsrsearch": args.query, "gsrlimit": args.limit})
    for page in pages:
        item = describe(page)
        print(f"{item['title']} | {item['width']}x{item['height']} | {item['licence']} | "
              f"{item['author'][:50]} | {item['description'][:100]}")


def fetch(args):
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    images = args.out_dir / "images"
    images.mkdir(parents=True, exist_ok=True)
    records = []
    for entry in spec["files"]:
        page = query({"titles": entry["title"], "iiurlwidth": args.width})[0]
        if "imageinfo" not in page:
            print(f"skip {entry['title']}: not found")
            continue
        item = describe(page)
        info = page["imageinfo"][0]
        source = info.get("thumburl") or info["url"]
        target = images / entry["name"]
        if target.exists() and not args.refresh:
            payload = target.read_bytes()
        else:
            payload = get(source)
            target.write_bytes(payload)
        item.update({
            "file": f"images/{entry['name']}",
            "download_url": source,
            "downloaded": datetime.date.today().isoformat(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
        records.append(item)
        print(f"ok {entry['name']} {item['licence']} {item['author'][:40]}")
        time.sleep(1)
    manifest = args.out_dir / "images" / "sources.json"
    manifest.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {manifest}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Search and download Wikimedia Commons images with licence records.")
    commands = parser.add_subparsers(dest="command", required=True)
    finder = commands.add_parser("search")
    finder.add_argument("query")
    finder.add_argument("--limit", type=int, default=40)
    finder.set_defaults(run=search)
    getter = commands.add_parser("fetch")
    getter.add_argument("spec", type=Path, help="JSON: {files: [{title, name}]}")
    getter.add_argument("out_dir", type=Path)
    getter.add_argument("--width", type=int, default=1600)
    getter.add_argument("--refresh", action="store_true", help="Download again even when the file exists")
    getter.set_defaults(run=fetch)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
