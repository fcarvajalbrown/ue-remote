import json
import urllib.request
from pathlib import Path

from shapely.geometry import Polygon
from shapely.strtree import STRtree

from citygen.osm import OVERPASS_URL, SAN_IGNACIO_BBOX

OVERLAP_SHARE = 0.2
MIN_AREA_M2 = 6.0


def fetch_osm(cache_path, bbox=SAN_IGNACIO_BBOX, refresh=False):
    cache = Path(cache_path)
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    south, west, north, east = bbox
    query = f'[out:json][timeout:90];\nway["building"]({south},{west},{north},{east});\nout body geom;\n'
    request = urllib.request.Request(OVERPASS_URL, data=query.encode("utf-8"), headers={"User-Agent": "san-ignacio-citygen/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    cache.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _polygon(points, plane):
    polygon = Polygon(plane.forward_ring(points))
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.geom_type != "Polygon" or polygon.area < MIN_AREA_M2:
        return None
    return polygon


def osm_polygons(payload, plane):
    found = []
    for element in payload.get("elements", []):
        if element.get("type") != "way" or "geometry" not in element or not element.get("tags", {}).get("building"):
            continue
        polygon = _polygon([(node["lon"], node["lat"]) for node in element["geometry"]], plane)
        if polygon is not None:
            found.append(polygon)
    return found


def ms_polygons(path, plane):
    found = []
    if not Path(path).exists():
        return found
    for feature in json.loads(Path(path).read_text(encoding="utf-8"))["features"]:
        polygon = _polygon([tuple(point[:2]) for point in feature["geometry"]["coordinates"][0]], plane)
        if polygon is not None:
            found.append(polygon)
    return found


def without_duplicates(candidates, reference):
    tree = STRtree(reference)
    kept = []
    for candidate in candidates:
        overlap = sum(reference[index].intersection(candidate).area for index in tree.query(candidate))
        if overlap < OVERLAP_SHARE * candidate.area:
            kept.append(candidate)
    return kept
