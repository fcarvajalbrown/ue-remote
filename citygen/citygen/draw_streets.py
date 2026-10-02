import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shapely.geometry import Polygon

from citygen import blocks, dxf, footprints, landmarks, osm, projection, streets

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
MARGIN_M = 40.0


def _cross(x, y, size=4.0):
    return [
        ("BLOCK_CENTRE", [(x - size, y), (x + size, y)], False),
        ("BLOCK_CENTRE", [(x, y - size), (x, y + size)], False),
    ]


def build(selection, streets_data, plane, label, resolved, buildings=()):
    entities = []
    xs, ys = [], []
    lines_out = {}

    for chunk_id, block in selection:
        edge_line, classes = streets.property_line(block, streets_data, plane, resolved)
        kerb = streets.kerb_line(block, streets_data, plane, resolved)
        if edge_line is None:
            print(f"  {chunk_id}: property line failed, skipped")
            continue
        lines_out[chunk_id] = (edge_line, classes)
        entities.append((f"LINEA_OFICIAL_{chunk_id.upper()}", list(edge_line.exterior.coords), True))
        if kerb is not None:
            entities.append(("SOLERA", list(kerb.exterior.coords), True))
        centre = edge_line.centroid
        entities += _cross(centre.x, centre.y)
        bounds = block.bounds
        xs += [bounds[0], bounds[2]]
        ys += [bounds[1], bounds[3]]

    lo = (min(xs) - MARGIN_M, min(ys) - MARGIN_M, max(xs) + MARGIN_M, max(ys) + MARGIN_M)
    window = Polygon(
        [(lo[0], lo[1]), (lo[2], lo[1]), (lo[2], lo[3]), (lo[0], lo[3])]
    )
    for street in streets_data:
        line = plane.forward_ring(street["coords"])
        kind = streets.kind_of(street, resolved)
        layer = "EJE_AVENIDA" if kind == "avenue" else "EJE_CALLE"
        from shapely.geometry import LineString

        clipped = LineString(line).intersection(window)
        if clipped.is_empty:
            continue
        parts = [clipped] if clipped.geom_type == "LineString" else list(clipped.geoms)
        for part in parts:
            if part.geom_type == "LineString" and part.length > 1.0:
                entities.append((layer, list(part.coords), False))

    for layer, polygons in buildings:
        drawn = 0
        for polygon in polygons:
            if window.contains(polygon):
                entities.append((layer, list(polygon.exterior.coords), True))
                drawn += 1
        print(f"  {layer}: {drawn} footprints")

    count = dxf.write(OUT / f"streets_{label}.dxf", entities, lo)
    print(f"  {label}: {len(entities)} entities, {count} layers -> out/streets_{label}.dxf")
    return lines_out


def main():
    plane = projection.centred_on(osm.SAN_IGNACIO_BBOX)
    payload = osm.fetch(cache_path=OUT / "osm_raw.json")
    streets_data, _ = osm.streets(payload)
    faces, _ = blocks.faces(streets_data, plane)

    everything = [(f"c_{i:03d}", polygon) for i, polygon in enumerate(faces)]
    resolved = streets.resolve_classes(streets_data, plane)
    pois = landmarks.load(landmarks.fetch(cache_path=OUT / "osm_pois.json"), plane, everything)
    centro_ids = landmarks.centro(everything, pois)
    if not centro_ids:
        raise SystemExit(f"{landmarks.PLAZA_NAME} not found - cannot anchor Centro")

    print("plaza anchor: " + landmarks.PLAZA_NAME + " -> centro " + ", ".join(centro_ids))
    print("avenues: " + ", ".join(sorted(n for n, k in resolved.items() if k == "avenue")))
    print("reserve widths:")
    for kind in ("residential", "avenue"):
        print(
            f"  {kind:12s} reserve {streets.RESERVE[kind]:.0f} m  "
            f"calzada {streets.CALZADA[kind]:.0f} m  vereda {streets.vereda(kind):.1f} m each side"
        )
    print()

    osm_buildings = footprints.osm_polygons(footprints.fetch_osm(OUT / "osm_buildings.json"), plane)
    ms_buildings = footprints.without_duplicates(footprints.ms_polygons(OUT / "ms_buildings.geojson", plane), osm_buildings)
    print(f"footprints: {len(osm_buildings)} OSM, {len(ms_buildings)} Microsoft not already in OSM")
    buildings = [("EDIFICIO_OSM", osm_buildings), ("EDIFICIO_MS", ms_buildings)]

    lines_out = build(everything, streets_data, plane, "town", resolved, buildings)

    report = {}
    for chunk_id, (edge_line, classes) in lines_out.items():
        original = dict(everything)[chunk_id]
        report[chunk_id] = {
            "block_area_m2": round(original.area, 1),
            "property_area_m2": round(edge_line.area, 1),
            "shrink_pct": round(100 * (1 - edge_line.area / original.area), 1),
            "zone": "centro" if chunk_id in centro_ids else None,
            "edges": [
                {"street": edge["street"], "kind": edge["kind"]} for edge in classes
            ],
        }
    (OUT / "streets.json").write_text(
        json.dumps(
            {
                "reserve_m": streets.RESERVE,
                "calzada_m": streets.CALZADA,
                "centro": centro_ids,
                "blocks": report,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("centro slice: " + ", ".join(centro_ids))
    print("chunk   block m2   property m2   shrink   bounding streets")
    for chunk_id in centro_ids:
        row = report[chunk_id]
        names = ", ".join(sorted({e["street"] for e in row["edges"] if e["street"]}))
        print(
            f"{chunk_id}  {row['block_area_m2']:>9.0f}  {row['property_area_m2']:>11.0f}  "
            f"{row['shrink_pct']:>5.1f}%   {names}"
        )
    print(f"\nwrote {OUT / 'streets.json'}")


if __name__ == "__main__":
    main()
