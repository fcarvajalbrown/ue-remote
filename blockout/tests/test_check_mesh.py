import sys
import tempfile
import unittest
from pathlib import Path

import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_mesh


class CheckMeshTest(unittest.TestCase):
    def report(self, mesh):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "part.glb"
            mesh.export(path)
            return check_mesh.check(path)

    def test_closed_box_on_the_grid_is_clean(self):
        report = self.report(trimesh.creation.box([1.0, 2.0, 0.5]))
        self.assertTrue(report["clean"])
        self.assertEqual(report["open_edges"], 0)
        self.assertEqual(report["bodies"], 1)

    def test_open_or_off_grid_mesh_fails(self):
        box = trimesh.creation.box([1.0, 2.0, 0.5])
        open_box = trimesh.Trimesh(box.vertices, box.faces[:-1], process=False)
        self.assertGreater(self.report(open_box)["open_edges"], 0)
        shifted = box.copy()
        shifted.apply_translation([0.003, 0.0, 0.0])
        self.assertFalse(self.report(shifted)["clean"])

    def test_far_from_the_origin_float32_storage_is_on_the_grid(self):
        box = trimesh.creation.box([1.0, 2.0, 0.5])
        box.apply_translation([1234.57, -987.65, 12.34])
        self.assertTrue(self.report(box)["clean"])


if __name__ == "__main__":
    unittest.main()
