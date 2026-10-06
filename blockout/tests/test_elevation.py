import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blockout import elevation


class ElevationLinesTest(unittest.TestCase):
    def test_lines_are_read_in_metres_from_the_ground(self):
        image = np.full((400, 600), 255, dtype=np.uint8)
        image[300:302, 50:550] = 0
        image[100, 100:500] = 0
        image[50:300, 200] = 0
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "sheet.png")
            cv2.imwrite(path, image)
            horizontal = elevation.measure_lines(path, (0, 0, 600, 400), elevation.HORIZONTAL, 2.0, 50.0, 300.5, 50.0)
            vertical = elevation.measure_lines(path, (0, 0, 600, 400), elevation.VERTICAL, 2.0, 50.0, 300.5, 50.0)
        self.assertEqual([round(row["height_m"], 2) for row in horizontal], [4.01, 0.0])
        self.assertEqual(horizontal[0]["length_m"], 8.0)
        self.assertEqual(len(vertical), 1)
        self.assertEqual(vertical[0]["x_m"], 3.0)


if __name__ == "__main__":
    unittest.main()
