import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_openings

PLAN_TO_GLTF = check_openings.GLTF_TO_PLAN.T


def wall_with_door(door_x):
    wall = trimesh.creation.box([6.0, 0.2, 3.0])
    wall.apply_translation([0.0, 0.0, 1.5])
    door = trimesh.creation.box([1.1, 1.0, 2.2])
    door.apply_translation([door_x, 0.0, 1.1 - 0.01])
    return wall.difference(door)


class CheckOpeningsTest(unittest.TestCase):
    def run_check(self, mesh, openings, y_up):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            if y_up:
                mesh = trimesh.Trimesh(vertices=np.asarray(mesh.vertices) @ PLAN_TO_GLTF.T, faces=mesh.faces, process=False)
            scene = trimesh.Scene()
            scene.add_geometry(mesh, geom_name="SM_Test_Walls")
            scene.export(folder / "walls.glb")
            (folder / "openings.json").write_text(json.dumps(openings), encoding="utf-8")
            sys.argv = ["check_openings.py", str(folder / "walls.glb"), str(folder / "openings.json")] + (["--y-up"] if y_up else [])
            return check_openings.main()

    def openings(self, x):
        return {"doors": [{"plan_xy": [x, 0.0], "width_m": 1.1, "height_m": 2.2, "yaw_degrees": 0.0, "wall_top_m": 3.0}], "windows": []}

    def test_door_with_its_own_wall_top_passes_in_a_y_up_file(self):
        self.assertEqual(self.run_check(wall_with_door(0.0), self.openings(0.0), True), 0)

    def test_door_listed_in_solid_wall_fails(self):
        self.assertEqual(self.run_check(wall_with_door(0.0), self.openings(2.0), True), 1)


if __name__ == "__main__":
    unittest.main()
