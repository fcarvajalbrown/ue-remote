from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union

MIN_BLOCK_AREA = 300.0
BOUNDARY_TOLERANCE = 2.0
MIN_SHARED_FRONTAGE = 8.0


def _noded(street_lines):
    return unary_union([LineString(line) for line in street_lines])


def faces(streets, plane, min_area=MIN_BLOCK_AREA):
    projected = [plane.forward_ring(street["coords"]) for street in streets]
    network = _noded([line for line in projected if len(line) >= 2])

    kept, dropped = [], []
    for polygon in polygonize(network):
        if polygon.area >= min_area:
            kept.append(polygon)
        else:
            dropped.append(polygon.area)

    kept.sort(key=lambda p: (-round(p.centroid.y), round(p.centroid.x)))
    return kept, dropped


def frontages(polygon, streets, plane):
    edge = polygon.exterior.buffer(BOUNDARY_TOLERANCE)
    found = {}
    for street in streets:
        line = LineString(plane.forward_ring(street["coords"]))
        shared = line.intersection(edge)
        if shared.is_empty or shared.length < MIN_SHARED_FRONTAGE:
            continue
        label = street["name"] or f"({street['highway']} sin nombre)"
        found[label] = found.get(label, 0.0) + shared.length
    return dict(sorted(found.items(), key=lambda item: -item[1]))


def describe(polygon, index, streets, plane, frontage_width):
    bounds = polygon.bounds
    return {
        "id": f"c_{index:03d}",
        "area_m2": round(polygon.area, 1),
        "perimeter_m": round(polygon.exterior.length, 1),
        "extent_m": [
            round(bounds[2] - bounds[0], 1),
            round(bounds[3] - bounds[1], 1),
        ],
        "centroid_local": [round(polygon.centroid.x, 1), round(polygon.centroid.y, 1)],
        "corners": len(polygon.exterior.coords) - 1,
        "estimated_lots": max(1, round(polygon.exterior.length / frontage_width)),
        "frontage_m": {
            name: round(length, 1)
            for name, length in frontages(polygon, streets, plane).items()
        },
    }


def to_geojson_feature(polygon, record, plane):
    ring = plane.inverse_ring(list(polygon.exterior.coords))
    return {
        "type": "Feature",
        "properties": record,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[round(lon, 7), round(lat, 7)] for lon, lat in ring]],
        },
    }


def line_to_geojson_feature(coords, properties):
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "LineString",
            "coordinates": [[round(lon, 7), round(lat, 7)] for lon, lat in coords],
        },
    }
