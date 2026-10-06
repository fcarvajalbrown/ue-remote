import sys
import unittest
from collections import Counter
from pathlib import Path

import manifold3d
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blockout import gridsnap

Manifold = manifold3d.Manifold


def edge_counts(triangles):
    keys = {}
    faces = []
    for triangle in np.round(np.asarray(triangles) * 1000).astype(int):
        faces.append([keys.setdefault(tuple(point), len(keys)) for point in triangle])
    return Counter(tuple(sorted((a, b))) for face in faces for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])))


class GridSnapTest(unittest.TestCase):
    def cut_tube(self):
        tube = Manifold.cylinder(5.0, 0.98, 0.98, 64) - Manifold.cylinder(5.02, 0.88, 0.88, 64).translate([0.0, 0.0, -0.01])
        return tube - Manifold.cube([0.4, 1.1, 2.2], True).translate([0.93, 0.0, 1.1])

    def test_vertices_land_on_the_centimetre_grid_and_stay_closed(self):
        triangles = gridsnap.finished_parts(self.cut_tube())[None]
        cm = triangles.reshape(-1, 3) * 100.0
        self.assertTrue(np.allclose(cm, np.round(cm), atol=1e-3))
        self.assertTrue(all(count == 2 for count in edge_counts(triangles).values()))

    def test_materials_follow_their_source_solid(self):
        white = Manifold.cylinder(2.0, 0.98, 0.98, 64)
        red = Manifold.cylinder(1.0, 0.98, 0.98, 64).translate([0.0, 0.0, 2.0])
        whole, labels = gridsnap.labelled_union([("walls", white), ("band", red)])
        parts = gridsnap.finished_parts(whole, labels)
        self.assertEqual(set(parts), {"walls", "band"})
        band_heights = parts["band"].reshape(-1, 3)[:, 2]
        self.assertTrue(np.all(band_heights >= 2.0 - 1e-6))
        merged = np.concatenate(list(parts.values()))
        self.assertTrue(all(count == 2 for count in edge_counts(merged).values()))

    def test_flips_remove_fan_slivers_from_a_cut_wall(self):
        wall = Manifold.cube([20.0, 0.5, 4.0])
        for x in (3.0, 9.0):
            wall = wall - Manifold.cube([1.1, 2.0, 2.2]).translate([x, -0.5, -0.1])
        triangles = gridsnap.finished_parts(wall)[None]
        thinnest = min(gridsnap.minimum_angle(triangle) for triangle in triangles)
        self.assertGreater(np.degrees(thinnest), 1.0)

    def test_feature_step_removes_slivers_from_long_thin_faces(self):
        slab = Manifold.cube([38.06, 0.15, 0.2]).translate([-19.03, -4.73, -0.2])
        cut = slab - Manifold.cube([1.1, 1.0, 1.0]).translate([2.0, -5.0, -0.1])
        plain = gridsnap.finished_parts(cut)[None]
        self.assertLess(np.degrees(min(gridsnap.minimum_angle(triangle) for triangle in plain)), 1.0)
        triangles = gridsnap.finished_parts(cut, feature_step=1.0)[None]
        self.assertGreater(np.degrees(min(gridsnap.minimum_angle(triangle) for triangle in triangles)), 1.0)
        self.assertTrue(all(count == 2 for count in edge_counts(triangles).values()))
        cm = triangles.reshape(-1, 3) * 100.0
        self.assertTrue(np.allclose(cm, np.round(cm), atol=1e-6))

    def test_subdivision_points_sit_on_a_shared_lattice_away_from_the_ends(self):
        first = gridsnap.subdivision_points(np.array([9.28, 4.59, 3.0]), np.array([9.28, -4.62, 3.0]), 1.0)
        second = gridsnap.subdivision_points(np.array([9.38, -4.58, 3.0]), np.array([9.38, 4.63, 3.0]), 1.0)
        self.assertEqual(sorted(round(point[1], 2) for point in first), sorted(round(point[1], 2) for point in second))
        self.assertTrue(all(abs(point[1]) <= 4.0 for point in first))
        self.assertEqual(gridsnap.subdivision_points(np.array([0.0, 0.0, 0.0]), np.array([1.0, 1.0, 0.0]), 1.0), [])

    def test_feature_edges_skip_flat_diagonals_and_keep_creases(self):
        cube = gridsnap.on_grid(Manifold.cube([1.0, 1.0, 1.0]))
        mesh = cube.to_mesh()
        vertices = np.asarray(mesh.vert_properties)[:, :3].astype(float)
        faces = np.asarray(mesh.tri_verts, dtype=np.int64)
        edges = gridsnap.feature_edges(vertices, faces, [None] * len(faces), 1e-5)
        self.assertEqual(len(edges), 12)

    def test_open_mesh_is_refused(self):
        triangles = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], dtype=float)
        with self.assertRaises(ValueError):
            gridsnap.from_triangles(triangles)


if __name__ == "__main__":
    unittest.main()
