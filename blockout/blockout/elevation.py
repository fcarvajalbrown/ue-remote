import cv2
import numpy as np

from blockout.silhouette import DARK_THRESHOLD, load_crop

HORIZONTAL = "h"
VERTICAL = "v"


def dark_mask(gray):
    return (gray < DARK_THRESHOLD).astype(np.uint8)


def long_runs(mask, axis, min_length_px):
    if axis == HORIZONTAL:
        kernel = np.ones((1, min_length_px), dtype=np.uint8)
    else:
        kernel = np.ones((min_length_px, 1), dtype=np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)


def edge_lines(gray, axis, min_length_px):
    runs = long_runs(dark_mask(gray), axis, min_length_px)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(runs, connectivity=8)
    lines = []
    for label in range(1, count):
        x, y, width, height, _ = stats[label]
        if axis == HORIZONTAL:
            lines.append({"at": y + (height - 1) / 2.0, "from": x, "to": x + width - 1, "thickness": height})
        else:
            lines.append({"at": x + (width - 1) / 2.0, "from": y, "to": y + height - 1, "thickness": width})
    return sorted(lines, key=lambda line: line["at"])


def measure_lines(image, box, axis, min_length_m, ppm, ground_y, origin_x):
    x0, y0 = int(box[0]), int(box[1])
    gray = load_crop(image, tuple(int(v) for v in box))
    found = edge_lines(gray, axis, max(2, int(round(min_length_m * ppm))))
    rows = []
    for line in found:
        if axis == HORIZONTAL:
            rows.append({"height_m": round((ground_y - (line["at"] + y0)) / ppm, 3), "from_m": round((line["from"] + x0 - origin_x) / ppm, 3), "to_m": round((line["to"] + x0 - origin_x) / ppm, 3), "length_m": round((line["to"] - line["from"] + 1) / ppm, 3), "image_y": round(line["at"] + y0, 1), "thickness_px": int(line["thickness"])})
        else:
            rows.append({"x_m": round((line["at"] + x0 - origin_x) / ppm, 3), "bottom_m": round((ground_y - (line["to"] + y0)) / ppm, 3), "top_m": round((ground_y - (line["from"] + y0)) / ppm, 3), "length_m": round((line["to"] - line["from"] + 1) / ppm, 3), "image_x": round(line["at"] + x0, 1), "thickness_px": int(line["thickness"])})
    return rows
