import argparse
import csv
import gzip
import io
import json
import math
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citygen.osm import SAN_IGNACIO_BBOX

LINKS = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"
USER_AGENT = "Mozilla/5.0"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def quadkey(lat, lon, zoom):
    x = (lon + 180.0) / 360.0
    sine = math.sin(math.radians(lat))
    y = 0.5 - math.log((1 + sine) / (1 - sine)) / (4 * math.pi)
    tile_x, tile_y = int(x * 2 ** zoom), int(y * 2 ** zoom)
    digits = []
    for level in range(zoom, 0, -1):
        mask = 1 << (level - 1)
        digits.append(str((1 if tile_x & mask else 0) + (2 if tile_y & mask else 0)))
    return "".join(digits)


def inside(ring, bbox):
    south, west, north, east = bbox
    lon = sum(point[0] for point in ring) / len(ring)
    lat = sum(point[1] for point in ring) / len(ring)
    return south <= lat <= north and west <= lon <= east


def main():
    parser = argparse.ArgumentParser(description="Microsoft GlobalMLBuildingFootprints clipped to the San Ignacio bbox.")
    parser.add_argument("--out", type=Path, default=ROOT / "out" / "ms_buildings.geojson")
    args = parser.parse_args()

    south, west, north, east = SAN_IGNACIO_BBOX
    keys = {quadkey(lat, lon, 9) for lat in (south, north) for lon in (west, east)}
    links = [row for row in csv.DictReader(io.StringIO(fetch(LINKS).decode("utf-8"))) if row["QuadKey"] in keys]
    print(f"tiles {sorted(keys)}: {len(links)} files")

    features, heights = [], 0
    for link in links:
        for line in gzip.decompress(fetch(link["Url"])).decode("utf-8").splitlines():
            feature = json.loads(line)
            ring = feature["geometry"]["coordinates"][0]
            if not inside(ring, SAN_IGNACIO_BBOX):
                continue
            height = feature.get("properties", {}).get("height", -1)
            if height is not None and height > 0:
                heights += 1
            features.append(feature)

    args.out.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    print(f"{len(features)} footprints in bbox, {heights} with a height estimate -> {args.out}")


if __name__ == "__main__":
    main()
