import json
import urllib.request
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

SAN_IGNACIO_BBOX = (-36.8180, -72.0560, -36.7850, -72.0150)

STREET_TYPES = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "pedestrian",
    "road",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}


def _query(bbox):
    south, west, north, east = bbox
    return (
        "[out:json][timeout:90];\n"
        f'(way["highway"]({south},{west},{north},{east});\n'
        f' way["waterway"]({south},{west},{north},{east}););\n'
        "out body geom;\n"
    )


def fetch(bbox=SAN_IGNACIO_BBOX, cache_path=None, refresh=False):
    cache = Path(cache_path) if cache_path else None
    if cache and cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))

    request = urllib.request.Request(
        OVERPASS_URL,
        data=_query(bbox).encode("utf-8"),
        headers={"User-Agent": "san-ignacio-citygen/0.1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def streets(payload):
    kept, skipped = [], {}
    for element in payload.get("elements", []):
        if element.get("type") != "way" or "geometry" not in element:
            continue
        tags = element.get("tags", {})
        highway = tags.get("highway")
        if highway is None:
            continue
        if highway not in STREET_TYPES:
            skipped[highway] = skipped.get(highway, 0) + 1
            continue
        kept.append(
            {
                "osm_id": element["id"],
                "name": tags.get("name"),
                "highway": highway,
                "coords": [(node["lon"], node["lat"]) for node in element["geometry"]],
            }
        )
    return kept, skipped


def waterways(payload):
    found = []
    for element in payload.get("elements", []):
        if element.get("type") != "way" or "geometry" not in element:
            continue
        tags = element.get("tags", {})
        if "waterway" not in tags:
            continue
        found.append(
            {
                "osm_id": element["id"],
                "name": tags.get("name"),
                "waterway": tags["waterway"],
                "coords": [(node["lon"], node["lat"]) for node in element["geometry"]],
            }
        )
    return found
