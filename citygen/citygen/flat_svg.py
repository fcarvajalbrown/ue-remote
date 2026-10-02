import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citygen.osm import SAN_IGNACIO_BBOX, streets
from citygen.projection import centred_on

CARRIAGEWAY_M = {"primary": 9.0, "secondary": 9.0, "tertiary": 9.0}
DEFAULT_CARRIAGEWAY_M = 7.0
COLOURS = {"ground": "#e9e6df", "street": "#ffffff", "street_edge": "#c9c4ba", "osm": "#5b5750", "extra": "#9a948a"}


def building_rings(payload):
    for element in payload.get("elements", []):
        if element.get("type") == "way" and "geometry" in element and element.get("tags", {}).get("building"):
            yield [(node["lon"], node["lat"]) for node in element["geometry"]]


def geojson_rings(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for feature in data.get("features", []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") == "Polygon":
            yield [tuple(point[:2]) for point in geometry["coordinates"][0]]
        elif geometry.get("type") == "MultiPolygon":
            for polygon in geometry["coordinates"]:
                yield [tuple(point[:2]) for point in polygon[0]]


def path_data(points, closed):
    head, *tail = points
    data = f"M{head[0]:.1f} {-head[1]:.1f}" + "".join(f"L{x:.1f} {-y:.1f}" for x, y in tail)
    return data + "Z" if closed else data


def main():
    parser = argparse.ArgumentParser(description="Flat SVG of San Ignacio streets and buildings in the manifest frame.")
    parser.add_argument("--streets", type=Path, default=ROOT / "out" / "osm_raw.json")
    parser.add_argument("--buildings", type=Path, default=ROOT / "out" / "osm_buildings.json")
    parser.add_argument("--extra-buildings", type=Path, help="GeoJSON footprints from another source, drawn lighter")
    parser.add_argument("--out", type=Path, default=ROOT / "out" / "flat_town.svg")
    args = parser.parse_args()

    plane = centred_on(SAN_IGNACIO_BBOX)
    south, west, north, east = SAN_IGNACIO_BBOX
    min_x, min_y = plane.forward(west, south)
    max_x, max_y = plane.forward(east, north)

    street_list, _ = streets(json.loads(args.streets.read_text(encoding="utf-8")))
    osm_buildings = list(building_rings(json.loads(args.buildings.read_text(encoding="utf-8"))))
    extra = list(geojson_rings(args.extra_buildings)) if args.extra_buildings else []

    layers = [f'<rect x="{min_x:.1f}" y="{-max_y:.1f}" width="{max_x - min_x:.1f}" height="{max_y - min_y:.1f}" fill="{COLOURS["ground"]}"/>']
    for edge, colour in ((2.0, COLOURS["street_edge"]), (0.0, COLOURS["street"])):
        group = []
        for street in street_list:
            width = CARRIAGEWAY_M.get(street["highway"], DEFAULT_CARRIAGEWAY_M) + edge
            group.append(f'<path d="{path_data(plane.forward_ring(street["coords"]), False)}" stroke-width="{width:.1f}"/>')
        layers.append(f'<g fill="none" stroke="{colour}" stroke-linecap="round" stroke-linejoin="round">{"".join(group)}</g>')
    for rings, colour, layer in ((extra, COLOURS["extra"], "extra"), (osm_buildings, COLOURS["osm"], "osm")):
        shapes = "".join(f'<path d="{path_data(plane.forward_ring(ring), True)}"/>' for ring in rings if len(ring) >= 3)
        layers.append(f'<g id="buildings_{layer}" fill="{colour}">{shapes}</g>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x:.1f} {-max_y:.1f} {max_x - min_x:.1f} {max_y - min_y:.1f}" '
        f'width="{(max_x - min_x) / 2:.0f}" height="{(max_y - min_y) / 2:.0f}">{"".join(layers)}</svg>'
    )
    args.out.write_text(svg, encoding="utf-8")
    print(f"{len(street_list)} streets, {len(osm_buildings)} OSM buildings, {len(extra)} extra buildings -> {args.out}")


if __name__ == "__main__":
    main()
