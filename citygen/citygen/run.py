import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shapely.geometry import Point

from citygen import blocks, landmarks, osm, projection

FRONTAGE_WIDTH_M = 10.0
OUT = Path(__file__).resolve().parent.parent / "out"


def main(refresh=False):
    OUT.mkdir(parents=True, exist_ok=True)
    plane = projection.centred_on(osm.SAN_IGNACIO_BBOX)

    payload = osm.fetch(cache_path=OUT / "osm_raw.json", refresh=refresh)
    streets, skipped = osm.streets(payload)
    water = osm.waterways(payload)

    print(f"streets kept: {len(streets)}")
    print(f"waterways: {len(water)}")
    if skipped:
        print("highway types excluded: " + ", ".join(f"{k}={v}" for k, v in sorted(skipped.items())))

    faces, dropped = blocks.faces(streets, plane)
    print(f"block faces: {len(faces)}  (dropped {len(dropped)} slivers under {blocks.MIN_BLOCK_AREA} m2)")

    records = [
        blocks.describe(polygon, i, streets, plane, FRONTAGE_WIDTH_M)
        for i, polygon in enumerate(faces)
    ]

    chunks = [(f"c_{i:03d}", polygon) for i, polygon in enumerate(faces)]
    pois = landmarks.load(landmarks.fetch(cache_path=OUT / "osm_pois.json"), plane, chunks)
    anchor_chunk, anchor_xy = landmarks.plaza_chunk(pois)
    centro_ids = landmarks.centro(chunks, pois)
    if anchor_xy is None:
        raise SystemExit(f"{landmarks.PLAZA_NAME} not found in OSM - cannot anchor Centro")
    print(f"plaza: {landmarks.PLAZA_NAME} in {anchor_chunk} at {anchor_xy}")
    print("centro: " + ", ".join(centro_ids))

    by_chunk = {}
    for poi in pois:
        if poi["chunk"] and poi["name"]:
            by_chunk.setdefault(poi["chunk"], []).append(poi["name"])

    for record, (_, polygon) in zip(records, chunks):
        record["distance_from_plaza_m"] = round(polygon.distance(Point(*anchor_xy)), 1)
        record["zone"] = "centro" if record["id"] in centro_ids else None
        record["landmarks"] = by_chunk.get(record["id"], [])

    ranked = sorted(records, key=lambda r: r["distance_from_plaza_m"])
    for rank, record in enumerate(ranked):
        record["centrality_rank"] = rank

    manifest = {
        "town": "San Ignacio, Nuble, Chile",
        "bbox": osm.SAN_IGNACIO_BBOX,
        "projection": {
            "kind": "local_equirectangular",
            "lat0": plane.lat0,
            "lon0": plane.lon0,
        },
        "assumptions": {"lot_frontage_m": FRONTAGE_WIDTH_M},
        "counts": {
            "streets": len(streets),
            "blocks": len(faces),
            "estimated_lots": sum(r["estimated_lots"] for r in records),
        },
        "chunks": records,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    features = [
        blocks.to_geojson_feature(polygon, record, plane)
        for polygon, record in zip(faces, records)
    ]
    features += [
        blocks.line_to_geojson_feature(
            street["coords"],
            {"kind": "street", "name": street["name"], "highway": street["highway"]},
        )
        for street in streets
    ]
    features += [
        blocks.line_to_geojson_feature(
            way["coords"], {"kind": "water", "name": way["name"], "waterway": way["waterway"]}
        )
        for way in water
    ]
    (OUT / "blocks.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nestimated lots at {FRONTAGE_WIDTH_M:.0f} m frontage: {manifest['counts']['estimated_lots']}")
    print("\nten most central blocks:")
    for record in ranked[:10]:
        names = ", ".join(list(record["frontage_m"])[:3]) or "unnamed"
        print(
            f"  {record['id']}  {record['area_m2']:>9.0f} m2  "
            f"{record['estimated_lots']:>3} lots  {record['corners']} corners  {names}"
        )

    named = {}
    for street in streets:
        if street["name"]:
            named[street["name"]] = named.get(street["name"], 0) + 1
    print(f"\nnamed streets: {len(named)}")
    for name in sorted(named):
        print(f"  {name}")

    print(f"\nwrote {OUT / 'manifest.json'}")
    print(f"wrote {OUT / 'blocks.geojson'}")


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
