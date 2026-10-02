import json
import urllib.request
from pathlib import Path

from shapely.geometry import Point

from citygen import osm

PLAZA_NAME = "Plaza San Ignacio"
CENTRO_CORNER_ANCHORS = ("CESFAM San Ignacio", "Gimnasio Municipal de San Ignacio")
SHARED_EDGE_MIN_M = 20.0

TAG_KEYS = (
    "amenity",
    "leisure",
    "shop",
    "tourism",
    "historic",
    "man_made",
    "sport",
    "office",
    "healthcare",
)


def _query(bbox):
    south, west, north, east = bbox
    selector = "|".join(TAG_KEYS)
    return (
        "[out:json][timeout:90];\n"
        f'(node[~"^({selector})$"~"."]({south},{west},{north},{east});\n'
        f' way[~"^({selector})$"~"."]({south},{west},{north},{east}););\n'
        "out center tags;\n"
    )


def fetch(bbox=osm.SAN_IGNACIO_BBOX, cache_path=None, refresh=False):
    cache = Path(cache_path) if cache_path else None
    if cache and cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    request = urllib.request.Request(
        osm.OVERPASS_URL,
        data=_query(bbox).encode("utf-8"),
        headers={"User-Agent": "san-ignacio-citygen/0.1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _kind(tags):
    for key in TAG_KEYS + ("landuse",):
        if key in tags:
            return f"{key}={tags[key]}"
    return None


def load(payload, plane, chunks):
    found = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        anchor = element.get("center") or element
        if "lon" not in anchor or "lat" not in anchor:
            continue
        kind = _kind(tags)
        if kind is None:
            continue
        x, y = plane.forward(anchor["lon"], anchor["lat"])
        point = Point(x, y)
        host = next((cid for cid, polygon in chunks if polygon.contains(point)), None)
        found.append(
            {
                "name": tags.get("name"),
                "kind": kind,
                "chunk": host,
                "local": [round(x, 1), round(y, 1)],
                "osm": f"{element['type']}/{element['id']}",
            }
        )
    return found


def plaza_chunk(found):
    for item in found:
        if item["name"] == PLAZA_NAME:
            return item["chunk"], item["local"]
    return None, None


def edge_neighbours(chunks, chunk_id):
    lookup = dict(chunks)
    target = lookup[chunk_id]
    touching = []
    for other_id, polygon in chunks:
        if other_id == chunk_id:
            continue
        shared = target.boundary.intersection(polygon.boundary)
        if not shared.is_empty and shared.length >= SHARED_EDGE_MIN_M:
            touching.append(other_id)
    return sorted(touching)


def centro(chunks, found):
    anchor, _ = plaza_chunk(found)
    if anchor is None:
        return []
    selected = [anchor] + edge_neighbours(chunks, anchor)
    for name in CENTRO_CORNER_ANCHORS:
        host = next((i["chunk"] for i in found if i["name"] == name and i["chunk"]), None)
        if host and host not in selected:
            selected.append(host)
    return sorted(selected)
