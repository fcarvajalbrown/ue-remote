import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import manifold3d
import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

PROBE_MARGIN_METRES = 0.05
CLOSE_GAP_METRES = 1.6
MIN_GAP_AREA_M2 = 0.02
MIN_WALL_THICKNESS_METRES = 0.08
MIN_FIN_AREA_M2 = 0.002
FIN_HEIGHTS_METRES = (1.0, 2.0, 3.0)


def explode(geometry):
    return [part for part in getattr(geometry, "geoms", [geometry]) if isinstance(part, Polygon) and not part.is_empty]


GLTF_TO_PLAN = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])


def load_walls(path, name, y_up=False):
    scene = trimesh.load(path, force="scene")
    mesh = scene.geometry[name] if name in scene.geometry or len(scene.geometry) != 1 else next(iter(scene.geometry.values()))
    if y_up:
        mesh = trimesh.Trimesh(vertices=np.asarray(mesh.vertices) @ GLTF_TO_PLAN.T, faces=mesh.faces, process=False)
    mesh.merge_vertices()
    solid = manifold3d.Manifold(manifold3d.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32), tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))
    return mesh, solid


def section(solid, height):
    rings = solid.slice(height).to_polygons()
    shapes = [Polygon(ring) for ring in rings if len(ring) >= 3]
    outer = unary_union([shape for shape in shapes if shape.exterior.is_ccw])
    holes = unary_union([shape for shape in shapes if not shape.exterior.is_ccw])
    return outer.difference(holes)


def probe(solid, xy, heights):
    point = Point(*xy)
    return {round(height, 2): section(solid, height).contains(point) for height in heights}


def main():
    parser = argparse.ArgumentParser(description="Check a blockout wall mesh against its door list: no wall thinner than 8 cm, watertight, every door open from the floor to its head and walled above, every window walled below the sill, open to the head and walled above, and no full-height gap anywhere above the highest head. An opening may carry its own sill_m and wall_top_m, which override --sill and --wall-height.")
    parser.add_argument("obj", type=Path)
    parser.add_argument("doors", type=Path)
    parser.add_argument("--object", default="walls")
    parser.add_argument("--y-up", action="store_true", help="the file is glTF Y-up (x, up, -north); turn it to plan x, north, up")
    parser.add_argument("--wall-height", type=float)
    parser.add_argument("--sill", type=float)
    args = parser.parse_args()

    mesh, solid = load_walls(args.obj, args.object, args.y_up)
    placements = json.loads(args.doors.read_text(encoding="utf-8"))
    failures = []
    edge_use = Counter(map(tuple, mesh.edges_sorted))
    open_edges = sum(1 for count in edge_use.values() if count == 1)
    shared_edges = sum(1 for count in edge_use.values() if count > 2)
    if open_edges:
        failures.append(f"{open_edges} open edges: the wall surface has holes")
    if solid.status() != manifold3d.Error.NoError:
        failures.append(f"manifold status {solid.status()}")

    heads = []
    for kind in ("doors", "windows"):
        for opening in placements[kind]:
            xy = opening["plan_xy"]
            top = opening.get("wall_top_m", args.wall_height) - PROBE_MARGIN_METRES
            bottom = 0.0 if kind == "doors" else opening.get("sill_m", args.sill)
            head = bottom + opening["height_m"]
            heads.append(head)
            expected = {PROBE_MARGIN_METRES: kind == "windows", bottom + PROBE_MARGIN_METRES: False, head - PROBE_MARGIN_METRES: False, head + PROBE_MARGIN_METRES: True, top: True}
            found = probe(solid, xy, expected)
            wrong = {height: found[round(height, 2)] for height, wall in expected.items() if found[round(height, 2)] != wall}
            if wrong:
                failures.append(f"{kind[:-1]} at {xy}: wall present by height {wrong}, expected {expected}")

    above = max(heads) + PROBE_MARGIN_METRES
    band = section(solid, above)
    closed = band.buffer(CLOSE_GAP_METRES / 2, join_style=2).buffer(-CLOSE_GAP_METRES / 2, join_style=2)
    spaces = explode(box(*closed.buffer(CLOSE_GAP_METRES).bounds).difference(closed))
    gaps = [part for part in explode(closed.difference(band)) if part.area > MIN_GAP_AREA_M2 and sum(1 for space in spaces if part.buffer(PROBE_MARGIN_METRES).intersects(space)) >= 2]
    for gap in gaps:
        failures.append(f"gap at {above:.2f} m above every head: plan ({gap.centroid.x:.2f}, {gap.centroid.y:.2f}), {gap.area:.2f} m2")

    half = MIN_WALL_THICKNESS_METRES / 2
    for height in FIN_HEIGHTS_METRES:
        cut = section(solid, height)
        fins = cut.difference(cut.buffer(-half).buffer(half + 1e-6))
        for fin in explode(fins):
            if fin.area > MIN_FIN_AREA_M2:
                failures.append(f"wall thinner than {MIN_WALL_THICKNESS_METRES} m at {height} m: plan ({fin.centroid.x:.2f}, {fin.centroid.y:.2f}), {fin.area:.4f} m2")

    print(json.dumps({"open_edges": open_edges, "edges_shared_by_more_than_two_faces": shared_edges, "doors": len(placements["doors"]), "windows": len(placements["windows"]), "checked_above_heads_m": round(above, 2), "failures": failures}, indent=1))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
