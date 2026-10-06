import cv2
import ezdxf
import numpy as np
import shapely
from ezdxf import path as ezpath
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid

from blockout.preview import entity_paths

PIXELS_PER_METRE = 40.0
LINE_THICKNESS_PIXELS = 2
GAP_CLOSE_PIXELS = 3
MAX_WALL_HALF_THICKNESS_METRES = 0.35
MIN_WALL_AREA_SQUARE_METRES = 0.05
SIMPLIFY_METRES = 0.02
BORDER_PIXELS = 4
MAX_OPENING_DEPTH_METRES = 0.5
MIN_OPENING_DEPTH_METRES = 0.15
MIN_OPENING_WIDTH_METRES = 0.4
INTERIOR_PROBE_METRES = 0.4
DOOR_CUT_EXTRA_METRES = 0.02
SLOT_CUT_EXTRA_METRES = 0.02
PASSAGE_MIN_AREA_M2 = 0.05
PASSAGE_MAX_DEPTH_METRES = 1.2
MIN_PASSABLE_CLEAR_METRES = 0.6
CENTIMETRE = 0.01
MAX_CUT_HALF_DEPTH_METRES = 0.75
MIN_WALL_THICKNESS_METRES = 0.08
CLEARANCE_STEP_METRES = 0.01
DOOR_ARC_REACH_METRES = 0.8
HATCH_FLATTEN_METRES = 0.02


def rasterize(path, layers, window, pixels_per_metre):
    document = ezdxf.readfile(path)
    x0, y0, x1, y1 = window
    width = int((x1 - x0) * pixels_per_metre) + 2 * BORDER_PIXELS
    height = int((y1 - y0) * pixels_per_metre) + 2 * BORDER_PIXELS
    mask = np.zeros((height, width), dtype=np.uint8)

    def to_pixel(point):
        px = int((point[0] - x0) * pixels_per_metre) + BORDER_PIXELS
        py = height - (int((point[1] - y0) * pixels_per_metre) + BORDER_PIXELS)
        return px, py

    for entity in document.modelspace():
        if entity.dxf.layer not in layers:
            continue
        for polyline in entity_paths(entity):
            pixels = np.array([to_pixel(p) for p in polyline], dtype=np.int32)
            cv2.polylines(mask, [pixels], False, 255, LINE_THICKNESS_PIXELS)
    return mask


def wall_regions(line_mask, pixels_per_metre):
    kernel = np.ones((GAP_CLOSE_PIXELS, GAP_CLOSE_PIXELS), dtype=np.uint8)
    sealed = cv2.morphologyEx(line_mask, cv2.MORPH_CLOSE, kernel)
    free = cv2.bitwise_not(sealed)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
    distance = cv2.distanceTransform(free, cv2.DIST_L2, 3)
    limit = MAX_WALL_HALF_THICKNESS_METRES * pixels_per_metre
    minimum_area = MIN_WALL_AREA_SQUARE_METRES * pixels_per_metre ** 2
    height, width = free.shape
    keep = np.zeros_like(free)
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        touches_border = x == 0 or y == 0 or x + w == width or y + h == height
        if touches_border or area < minimum_area:
            continue
        region = labels == label
        if distance[region].max() <= limit:
            keep[region] = 255
    return cv2.dilate(keep, kernel, iterations=1)


def polygons_from_mask(mask, window, pixels_per_metre):
    x0, y0, _, _ = window
    height = mask.shape[0]
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)

    def to_world(contour):
        points = contour.reshape(-1, 2).astype(float)
        xs = (points[:, 0] - BORDER_PIXELS) / pixels_per_metre + x0
        ys = (height - points[:, 1] - BORDER_PIXELS) / pixels_per_metre + y0
        return list(zip(xs, ys))

    polygons = []
    if hierarchy is None:
        return polygons
    for index, contour in enumerate(contours):
        if hierarchy[0][index][3] != -1 or len(contour) < 4:
            continue
        holes = []
        child = hierarchy[0][index][2]
        while child != -1:
            if len(contours[child]) >= 4:
                holes.append(to_world(contours[child]))
            child = hierarchy[0][child][0]
        polygon = Polygon(to_world(contour), holes)
        if not polygon.is_valid:
            polygon = make_valid(polygon)
        simplified = polygon.simplify(SIMPLIFY_METRES)
        if not simplified.is_empty and simplified.area > 0:
            polygons.append(simplified)
    return polygons


def hatch_geometry(path, layer, window):
    document = ezdxf.readfile(path)
    x0, y0, x1, y1 = window
    clip = box(x0, y0, x1, y1)
    shapes = []
    for entity in document.modelspace():
        if entity.dxftype() != "HATCH" or entity.dxf.layer != layer:
            continue
        solid = None
        for sub in ezpath.make_path(entity).sub_paths():
            points = [(vertex.x, vertex.y) for vertex in sub.flattening(HATCH_FLATTEN_METRES)]
            if len(points) < 3:
                continue
            ring = Polygon(points)
            if not ring.is_valid:
                ring = make_valid(ring)
            solid = ring if solid is None else solid.symmetric_difference(ring)
        if solid is not None and not solid.is_empty:
            clipped = solid.intersection(clip)
            if not clipped.is_empty:
                shapes.append(clipped)
    return shapes


def paint_hatch(mask, shapes, window, pixels_per_metre):
    x0, y0, _, _ = window
    height = mask.shape[0]

    def to_pixel(point):
        return int((point[0] - x0) * pixels_per_metre) + BORDER_PIXELS, height - (int((point[1] - y0) * pixels_per_metre) + BORDER_PIXELS)

    for shape in shapes:
        for part in getattr(shape, "geoms", [shape]):
            if part.geom_type != "Polygon":
                continue
            cv2.fillPoly(mask, [np.array([to_pixel(p) for p in part.exterior.coords], dtype=np.int32)], 255)
            for hole in part.interiors:
                cv2.fillPoly(mask, [np.array([to_pixel(p) for p in hole.coords], dtype=np.int32)], 0)


def extract_walls(path, layers, window, pixels_per_metre=PIXELS_PER_METRE, hatch_layer=None):
    line_mask = rasterize(path, layers, window, pixels_per_metre)
    wall_mask = wall_regions(line_mask, pixels_per_metre)
    solid_mask = wall_mask.copy()
    if hatch_layer:
        paint_hatch(solid_mask, hatch_geometry(path, hatch_layer, window), window, pixels_per_metre)
    return polygons_from_mask(solid_mask, window, pixels_per_metre), wall_mask


def find_openings(wall_mask, window, pixels_per_metre, max_width, max_depth=MAX_OPENING_DEPTH_METRES):
    x0, y0, _, _ = window
    height = wall_mask.shape[0]
    length = int(max_width * pixels_per_metre)
    across_x = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, np.ones((1, length), dtype=np.uint8))
    across_y = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, np.ones((length, 1), dtype=np.uint8))
    deepest = max_depth * pixels_per_metre
    narrowest = MIN_OPENING_WIDTH_METRES * pixels_per_metre
    shallowest = MIN_OPENING_DEPTH_METRES * pixels_per_metre
    free = cv2.bitwise_not(wall_mask)
    openings = []
    for closed in (across_x, across_y):
        count, _, stats, _ = cv2.connectedComponentsWithStats(cv2.bitwise_and(closed, free), connectivity=4)
        for label in range(1, count):
            x, y, w, h, _ = stats[label]
            if not shallowest <= min(w, h) <= deepest or max(w, h) < narrowest:
                continue
            left = (x - BORDER_PIXELS) / pixels_per_metre + x0
            right = (x + w - BORDER_PIXELS) / pixels_per_metre + x0
            top = (height - y - BORDER_PIXELS) / pixels_per_metre + y0
            bottom = (height - (y + h) - BORDER_PIXELS) / pixels_per_metre + y0
            openings.append(box(left, bottom, right, top))
    return openings


def door_swing_centres(path, layer, window):
    document = ezdxf.readfile(path)
    x0, y0, x1, y1 = window
    centres = []
    for entity in document.modelspace():
        if entity.dxf.layer != layer or entity.dxftype() != "ARC":
            continue
        centre = entity.dxf.center
        if x0 <= centre.x <= x1 and y0 <= centre.y <= y1:
            centres.append(Point(centre.x, centre.y))
    return centres


def split_openings(openings, swing_centres):
    doors, windows = [], []
    for opening in openings:
        near = any(opening.distance(centre) <= DOOR_ARC_REACH_METRES for centre in swing_centres)
        (doors if near else windows).append(opening)
    return doors, windows


def opening_axes(opening, walls=None):
    x0, y0, x1, y1 = opening.bounds
    along_x = (x1 - x0) >= (y1 - y0)
    if walls is not None:
        edge = 0.03
        inset_y = (y1 - y0) * 0.25
        inset_x = (x1 - x0) * 0.25
        x_sides = walls.intersects(box(x0 - edge, y0 + inset_y, x0 + edge, y1 - inset_y)) and walls.intersects(box(x1 - edge, y0 + inset_y, x1 + edge, y1 - inset_y))
        y_sides = walls.intersects(box(x0 + inset_x, y0 - edge, x1 - inset_x, y0 + edge)) and walls.intersects(box(x0 + inset_x, y1 - edge, x1 - inset_x, y1 + edge))
        if x_sides != y_sides:
            along_x = x_sides
    centre = ((x0 + x1) / 2, (y0 + y1) / 2)
    width, depth = (x1 - x0, y1 - y0) if along_x else (y1 - y0, x1 - x0)
    return centre, along_x, width, depth


def interior_as_doors(doors, windows, outline, reach):
    kept = []
    for window in windows:
        centre, along_x, _, depth = opening_axes(window)
        offset = depth / 2 + reach
        sides = [(centre[0], centre[1] - offset), (centre[0], centre[1] + offset)] if along_x else [(centre[0] - offset, centre[1]), (centre[0] + offset, centre[1])]
        (doors if all(outline.contains(Point(*side)) for side in sides) else kept).append(window)
    return doors, kept


def wall_clearance(gap, walls, step):
    x0, y0, x1, y1 = gap.bounds
    xs, ys = np.meshgrid(np.arange(x0, x1, step), np.arange(y0, y1, step))
    points = shapely.points(xs.ravel(), ys.ravel())
    inside = points[shapely.contains(gap, points)]
    return float(shapely.distance(inside, walls).max()) if len(inside) else 0.0


def oriented_box(centre, along_x, half_w, half_d):
    if along_x:
        return box(centre[0] - half_w, centre[1] - half_d, centre[0] + half_w, centre[1] + half_d)
    return box(centre[0] - half_d, centre[1] - half_w, centre[0] + half_d, centre[1] + half_w)


def faces_clear(centre, along_x, half_w, half_d, walls):
    inner = half_w - CENTIMETRE
    for side in (-1, 1):
        offset = side * half_d
        face_centre = (centre[0], centre[1] + offset) if along_x else (centre[0] + offset, centre[1])
        if walls.intersects(oriented_box(face_centre, along_x, inner, CENTIMETRE / 2)):
            return False
    return True


def absorb_fins(solid, cut):
    half = MIN_WALL_THICKNESS_METRES / 2
    solid, cut = shapely.set_precision(solid, 0.0), shapely.set_precision(cut, 0.0)
    rest = solid.difference(cut)
    fins = rest.difference(rest.buffer(-half).buffer(half + CENTIMETRE / 10))
    touching = [fin for fin in explode_polygons(fins) if fin.distance(cut) < 2 * CENTIMETRE]
    return unary_union([cut] + [fin.buffer(CENTIMETRE / 10) for fin in touching]) if touching else cut


def standard_door(opening, width, extra_depth, walls=None):
    centre, along_x, _, depth = opening_axes(opening, walls)
    half_w, half_d = width / 2, depth / 2 + extra_depth
    if walls is not None:
        while not faces_clear(centre, along_x, half_w, half_d, walls) and half_d < MAX_CUT_HALF_DEPTH_METRES:
            half_d = round(half_d + CENTIMETRE, 2)
    return oriented_box(centre, along_x, half_w, half_d)


def door_placements(doors, origin, height, walls=None):
    placements = []
    for door in doors:
        centre, along_x, width, _ = opening_axes(door, walls)
        placements.append({"plan_xy": [to_cm(centre[0] - origin[0]), to_cm(centre[1] - origin[1])], "yaw_degrees": 0.0 if along_x else 90.0, "width_m": to_cm(width), "height_m": to_cm(height)})
    return placements


def find_passages(polygons, outline, max_width, min_area, min_clear):
    walls = unary_union(polygons)
    half = max_width / 2
    closed = walls.buffer(half, join_style=2).buffer(-half, join_style=2)
    regions = [part for part in explode_polygons(outline.buffer(-0.01).difference(closed)) if part.area > min_area]
    outside = outline.buffer(max_width * 4).difference(outline)
    passages, unpassable = [], []
    for gap in explode_polygons(closed.difference(walls)):
        if gap.area < min_area:
            continue
        grown = gap.buffer(0.05)
        touching = sum(1 for region in regions if grown.intersects(region)) + (1 if grown.intersects(outside) else 0)
        x0, y0, x1, y1 = gap.bounds
        if touching < 2 or min(x1 - x0, y1 - y0) > PASSAGE_MAX_DEPTH_METRES:
            continue
        if 2 * wall_clearance(gap, walls, CLEARANCE_STEP_METRES) < min_clear:
            unpassable.append(gap)
        else:
            passages.append(gap.minimum_rotated_rectangle)
    return passages, unpassable


def merge_openings(doors, windows, passages):
    merged_doors = list(doors)
    for passage in passages:
        if any(passage.intersects(opening) for opening in doors + windows):
            continue
        merged_doors.append(box(*passage.bounds))
    return merged_doors


def explode_polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [polygon for part in getattr(geometry, "geoms", []) for polygon in explode_polygons(part)]


def to_cm(value):
    return float(np.floor(value * 100.0 + 0.5 + 1e-6) / 100.0)


def outward_sign(centre, along_x, half_depth, outline, reach=0.3):
    offset = half_depth + reach
    probe = Point(centre[0], centre[1] + offset) if along_x else Point(centre[0] + offset, centre[1])
    return -1.0 if outline.contains(probe) else 1.0


def depth_band(centre, along_x, half_width, near, far):
    low, high = sorted((near, far))
    if along_x:
        return box(centre[0] - half_width, centre[1] + low, centre[0] + half_width, centre[1] + high)
    return box(centre[0] + low, centre[1] - half_width, centre[0] + high, centre[1] + half_width)


def stepped_window(cut, opening, outer_width, outer_depth, walls, outline):
    centre, along_x, _, depth = opening_axes(opening, walls)
    x0, y0, x1, y1 = cut.bounds
    half_cut_depth = (y1 - y0) / 2 if along_x else (x1 - x0) / 2
    half_cut_width = (x1 - x0) / 2 if along_x else (y1 - y0) / 2
    sign = outward_sign(centre, along_x, depth / 2, outline)
    step = sign * (depth / 2 - outer_depth)
    outer = depth_band(centre, along_x, outer_width / 2, sign * half_cut_depth, step)
    inner = depth_band(centre, along_x, half_cut_width, step, -sign * half_cut_depth)
    return unary_union([outer, inner]), (0.0, sign) if along_x else (sign, 0.0)
