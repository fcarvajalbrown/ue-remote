import cv2
import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Polygon

DARK_THRESHOLD = 160
CLOSE_KERNEL_PIXELS = 15
SIMPLIFY_PIXELS = 3.0
MIN_AREA_FRACTION = 0.02
SIDE_TO_WORLD = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=float)


def load_crop(path, box):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    x0, y0, x1, y1 = box
    return image[y0:y1, x0:x1]


def filled_mask(gray):
    dark = (gray < DARK_THRESHOLD).astype(np.uint8) * 255
    kernel = np.ones((CLOSE_KERNEL_PIXELS, CLOSE_KERNEL_PIXELS), dtype=np.uint8)
    closed = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros_like(closed)
    limit = MIN_AREA_FRACTION * closed.shape[0] * closed.shape[1]
    kept = [c for c in contours if cv2.contourArea(c) >= limit]
    cv2.drawContours(mask, kept, -1, 255, thickness=cv2.FILLED)
    return mask


def silhouette_polygon(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    outline = max(contours, key=cv2.contourArea).reshape(-1, 2).astype(float)
    cleaned = Polygon(outline).buffer(0).simplify(SIMPLIFY_PIXELS, preserve_topology=True).buffer(0)
    if isinstance(cleaned, MultiPolygon):
        cleaned = max(cleaned.geoms, key=lambda part: part.area)
    return Polygon(cleaned.exterior)


def measured(polygon, known_width_metres):
    x0, y0, x1, y1 = polygon.bounds
    scale = known_width_metres / (x1 - x0)
    return scale, (x1 - x0) * scale, (y1 - y0) * scale


def profile_polygon(polygon, scale):
    x0, _, _, y1 = polygon.bounds
    points = [((x - x0) * scale, (y1 - y) * scale) for x, y in polygon.exterior.coords]
    return Polygon(points)


def hull_mesh(front, side, front_width, side_width):
    front_scale, _, front_height = measured(front, front_width)
    side_scale, _, side_height = measured(side, side_width)
    front_profile = profile_polygon(front, front_scale)
    side_profile = profile_polygon(side, side_scale)
    depth = side_width
    width = front_width
    height = max(front_height, side_height)
    front_solid = trimesh.creation.extrude_polygon(front_profile, depth)
    front_solid.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    front_solid.apply_translation([0, depth, 0])
    side_solid = trimesh.creation.extrude_polygon(side_profile, width)
    side_solid.apply_transform(SIDE_TO_WORLD)
    solid = trimesh.boolean.intersection([front_solid, side_solid], engine="manifold")
    return solid, front_height, side_height, height
