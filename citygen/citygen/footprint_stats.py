import argparse
import json
import math
import statistics
import urllib.parse
import urllib.request
from pathlib import Path

from shapely.geometry import Polygon

ENDPOINTS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
METRES_PER_DEGREE_LAT = 110540.0
METRES_PER_DEGREE_LON = 111320.0
MIN_AREA_SQUARE_METRES = 15


def fetch(name, lat, lon, radius, cache):
    target = cache / f"osm_{name}.json"
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    query = f'[out:json][timeout:90];way["building"](around:{radius},{lat},{lon});out geom;'
    body = urllib.parse.urlencode({"data": query}).encode()
    for endpoint in ENDPOINTS:
        request = urllib.request.Request(endpoint, data=body, headers={"User-Agent": "footprint-stats/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
        except Exception as error:
            print(f"  {endpoint}: {error}")
            continue
        cache.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return json.loads(raw)
    raise SystemExit(f"all Overpass endpoints failed for {name}")


def metric_polygon(geometry, lat0):
    scale_x = METRES_PER_DEGREE_LON * math.cos(math.radians(lat0))
    return Polygon([(point["lon"] * scale_x, point["lat"] * METRES_PER_DEGREE_LAT) for point in geometry])


def sides(polygon):
    xs, ys = polygon.minimum_rotated_rectangle.exterior.coords.xy
    edges = [math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(2)]
    return max(edges), min(edges)


def buildings(data, lat0):
    result = []
    for element in data.get("elements", []):
        geometry = element.get("geometry")
        if not geometry or len(geometry) < 4:
            continue
        polygon = metric_polygon(geometry, lat0)
        if polygon.is_valid and polygon.area >= MIN_AREA_SQUARE_METRES:
            result.append(polygon)
    return result


def isolated(polygons, radius, maximum):
    centres = [polygon.centroid for polygon in polygons]
    keep = []
    for index, centre in enumerate(centres):
        neighbours = sum(1 for other, point in enumerate(centres) if other != index and centre.distance(point) < radius)
        if neighbours <= maximum:
            keep.append(polygons[index])
    return keep


def describe(label, polygons):
    if not polygons:
        print(f"  {label:12s} none")
        return
    areas = [polygon.area for polygon in polygons]
    pairs = [sides(polygon) for polygon in polygons]
    quartiles = statistics.quantiles(areas, n=4) if len(areas) >= 4 else [min(areas), statistics.median(areas), max(areas)]
    print(
        f"  {label:12s} n={len(polygons):4d} area p25/median/p75={quartiles[0]:.0f}/{quartiles[1]:.0f}/{quartiles[2]:.0f} m2  "
        f"long median={statistics.median(p[0] for p in pairs):.1f} short median={statistics.median(p[1] for p in pairs):.1f} m  "
        f"aspect median={statistics.median(p[0] / p[1] for p in pairs):.2f}"
    )


def parse_centre(text):
    name, _, position = text.partition(":")
    lat, _, lon = position.partition(",")
    return name, float(lat), float(lon)


def main():
    parser = argparse.ArgumentParser(description="Size statistics of isolated buildings around one or more points, from OpenStreetMap.")
    parser.add_argument("--centre", action="append", required=True, type=parse_centre, help="name:lat,lon, repeatable")
    parser.add_argument("--radius", type=int, default=5000, help="search radius in metres")
    parser.add_argument("--cache", type=Path, default=Path("out"), help="folder for the raw Overpass answers")
    parser.add_argument("--neighbour-radius", type=float, default=150.0)
    parser.add_argument("--max-neighbours", type=int, default=5, help="a building is isolated when it has at most this many neighbours inside the radius")
    parser.add_argument("--small-max", type=float, default=200.0, help="largest area counted as small, in square metres")
    parser.add_argument("--large-min", type=float, default=150.0, help="smallest area counted as large, in square metres")
    args = parser.parse_args()

    for name, lat, lon in args.centre:
        polygons = buildings(fetch(name, lat, lon, args.radius, args.cache), lat)
        alone = isolated(polygons, args.neighbour_radius, args.max_neighbours)
        print(f"== {name}: {len(polygons)} buildings, {len(alone)} isolated")
        describe("small", [p for p in alone if p.area <= args.small_max])
        describe("large", [p for p in alone if p.area >= args.large_min])


if __name__ == "__main__":
    main()
