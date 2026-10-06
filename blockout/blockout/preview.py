import cv2
import ezdxf
import numpy as np

PIXELS_PER_UNIT = 8.0
MARGIN_PIXELS = 20
PALETTE = [
    (60, 60, 60), (200, 50, 50), (40, 140, 40), (200, 120, 0), (50, 50, 200),
    (160, 40, 160), (0, 150, 150), (120, 120, 0), (90, 90, 90),
]
ARC_STEP_DEGREES = 10.0


def entity_paths(entity):
    kind = entity.dxftype()
    if kind == "LINE":
        return [[(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]]
    if kind == "LWPOLYLINE":
        points = [(p[0], p[1]) for p in entity.get_points("xy")]
        return [points + points[:1]] if entity.closed else [points]
    if kind in ("ARC", "CIRCLE"):
        start = entity.dxf.start_angle if kind == "ARC" else 0.0
        end = entity.dxf.end_angle if kind == "ARC" else 360.0
        if end <= start:
            end += 360.0
        steps = max(4, int((end - start) / ARC_STEP_DEGREES))
        angles = np.radians(np.linspace(start, end, steps + 1))
        centre, radius = entity.dxf.center, entity.dxf.radius
        return [[(centre.x + radius * np.cos(a), centre.y + radius * np.sin(a)) for a in angles]]
    return []


def render(path, layers, window, output, pixels_per_unit=PIXELS_PER_UNIT):
    document = ezdxf.readfile(path)
    x0, y0, x1, y1 = window
    width = int((x1 - x0) * pixels_per_unit) + 2 * MARGIN_PIXELS
    height = int((y1 - y0) * pixels_per_unit) + 2 * MARGIN_PIXELS
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    colours = {name: PALETTE[index % len(PALETTE)] for index, name in enumerate(layers)}

    def to_pixel(point):
        px = int((point[0] - x0) * pixels_per_unit) + MARGIN_PIXELS
        py = height - (int((point[1] - y0) * pixels_per_unit) + MARGIN_PIXELS)
        return px, py

    drawn = 0
    for entity in document.modelspace():
        layer = entity.dxf.layer
        if layer not in colours:
            continue
        for polyline in entity_paths(entity):
            pixels = np.array([to_pixel(p) for p in polyline], dtype=np.int32)
            cv2.polylines(image, [pixels], False, colours[layer], 1, cv2.LINE_AA)
            drawn += 1
    cv2.imwrite(str(output), image)
    return drawn, (width, height)
