import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import trimesh

GRID_METRES = 0.01
GRID_TOLERANCE = 1e-4
SLIVER_DEGREES = 1.0
SHORT_EDGE_METRES = 0.01


def triangle_angles(corners):
    angles = []
    for i in range(3):
        a = corners[:, (i + 1) % 3] - corners[:, i]
        b = corners[:, (i + 2) % 3] - corners[:, i]
        cosine = np.einsum("ij,ij->i", a, b) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-12)
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
    return np.min(np.stack(angles, axis=1), axis=1)


def body_count(faces, vertex_count):
    parent = np.arange(vertex_count)

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for a, b, c in faces:
        ra, rb, rc = root(a), root(b), root(c)
        parent[rb] = ra
        parent[rc] = ra
    return len({root(index) for index in np.unique(faces)})


def check(path):
    scene = trimesh.load(path, force="scene")
    meshes = [geometry for geometry in scene.dump() if isinstance(geometry, trimesh.Trimesh)]
    merged = trimesh.util.concatenate(meshes)
    merged = trimesh.Trimesh(vertices=np.round(merged.vertices, 4), faces=merged.faces, process=False)
    merged.merge_vertices(merge_tex=True, merge_norm=True, digits_vertex=4)
    corners = merged.vertices[merged.faces]
    areas = np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1) / 2.0
    edge_use = Counter(map(tuple, merged.edges_sorted))
    lengths = np.linalg.norm(merged.vertices[merged.edges_unique[:, 0]] - merged.vertices[merged.edges_unique[:, 1]], axis=1)
    off_grid = np.abs(merged.vertices / GRID_METRES - np.round(merged.vertices / GRID_METRES)) > GRID_TOLERANCE
    report = {
        "triangles": int(len(merged.faces)),
        "materials": len(meshes),
        "watertight": bool(merged.is_watertight),
        "winding_consistent": bool(merged.is_winding_consistent),
        "open_edges": sum(1 for count in edge_use.values() if count == 1),
        "non_manifold_edges": sum(1 for count in edge_use.values() if count > 2),
        "degenerate_triangles": int(np.sum(areas < 1e-8)),
        "sliver_triangles": int(np.sum(triangle_angles(corners[areas >= 1e-8]) < SLIVER_DEGREES)),
        "edges_shorter_than_1cm": int(np.sum((lengths > 1e-6) & (lengths < SHORT_EDGE_METRES - GRID_TOLERANCE))),
        "vertices_off_1cm_grid": int(np.any(off_grid, axis=1).sum()),
        "volume_m3": round(float(merged.volume), 3) if merged.is_watertight else None,
        "bodies": body_count(merged.faces, len(merged.vertices)),
    }
    report["clean"] = report["watertight"] and report["winding_consistent"] and not any(report[key] for key in ("open_edges", "non_manifold_edges", "degenerate_triangles", "vertices_off_1cm_grid")) and (report["volume_m3"] or 0) > 0
    return report


def main():
    parser = argparse.ArgumentParser(description="Check the topology of blockout GLBs: watertight, consistent winding, no open or non-manifold edges, no degenerate or sliver triangles, every vertex on the 1 cm grid, positive volume.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    failed = 0
    for path in args.paths:
        report = check(path)
        failed += not report["clean"]
        print(json.dumps({"file": path.name, **report}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
