import argparse
import json
import sys

import cv2
import trimesh
from pathlib import Path
from shapely import set_precision
from shapely.geometry import Point
from shapely.ops import unary_union

from blockout import elevation, silhouette, sources
from blockout.calibrate import calibration_report
from blockout.inspect_dxf import extents_report, summary
from blockout.meshing import (
    AXES_CAD,
    AXES_GLTF,
    DEFAULT_CLOSE_GAP_METRES,
    DEFAULT_DOOR_HEIGHT_METRES,
    DEFAULT_OPENING_WIDTH_METRES,
    DEFAULT_SILL_HEIGHT_METRES,
    DEFAULT_WINDOW_HEAD_METRES,
    DEFAULT_SLAB_THICKNESS_METRES,
    DEFAULT_WALL_HEIGHT_METRES,
    explode,
    walls_with_openings,
    footprint,
    gable,
    mesh_report,
    slab,
    write_mesh,
)
from blockout.preview import PIXELS_PER_UNIT, render
from blockout.walls import (
    absorb_fins,
    CENTIMETRE,
    DOOR_CUT_EXTRA_METRES,
    SLOT_CUT_EXTRA_METRES,
    INTERIOR_PROBE_METRES,
    MIN_PASSABLE_CLEAR_METRES,
    PIXELS_PER_METRE,
    door_placements,
    opening_axes,
    door_swing_centres,
    extract_walls,
    find_openings,
    PASSAGE_MIN_AREA_M2,
    find_passages,
    interior_as_doors,
    merge_openings,
    split_openings,
    standard_door,
    stepped_window,
    to_cm,
)


def window_argument(text):
    values = [float(part) for part in text.split(",")]
    if len(values) != 4:
        raise argparse.ArgumentTypeError("window is x0,y0,x1,y1")
    return tuple(values)


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="blockout", description="Plan to blockout mesh, with short outputs.")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="download a URL into .cache, unpack archives, list files")
    fetch.add_argument("url")
    fetch.add_argument("--name")
    convert = sub.add_parser("convert", help="DWG to DXF with the vendored LibreDWG")
    convert.add_argument("dwg")
    convert.add_argument("dxf")
    for name in ("summary", "extents", "calibrate"):
        step = sub.add_parser(name)
        step.add_argument("dxf")
    preview = sub.add_parser("preview", help="render layers to a PNG for one look")
    preview.add_argument("dxf")
    preview.add_argument("--layers", required=True, help="comma separated layer names")
    preview.add_argument("--window", required=True, type=window_argument)
    preview.add_argument("--out", required=True)
    preview.add_argument("--ppu", type=float, default=PIXELS_PER_UNIT)
    walls = sub.add_parser("walls", help="extract wall solids from line layers and extrude them")
    walls.add_argument("dxf")
    walls.add_argument("--layers", required=True)
    walls.add_argument("--window", required=True, type=window_argument)
    walls.add_argument("--height", type=float, default=DEFAULT_WALL_HEIGHT_METRES, help="metres; an ESTIMATE unless taken from a section")
    walls.add_argument("--out", required=True, help="output path without extension")
    walls.add_argument("--axes", choices=[AXES_CAD, AXES_GLTF], default=AXES_GLTF)
    walls.add_argument("--ppm", type=float, default=PIXELS_PER_METRE)
    walls.add_argument("--carve-circle", default=None, help="x,y,radius in drawing units: a round hole cut out of the wall solids, for a larger tower or column standing in the plan")
    walls.add_argument("--hatch-layer", default=None, help="layer whose hatches mark solid masonry; their areas are added to the walls (thick masses the outline pass rejects as rooms)")
    walls.add_argument("--openings", action="store_true", help="close door and window gaps above and below their frames")
    walls.add_argument("--door-layer", default="segmento", help="layer whose arcs mark door swings; gaps near one are doors, the rest windows")
    walls.add_argument("--door-height", type=float, default=DEFAULT_DOOR_HEIGHT_METRES, help="metres; an ESTIMATE unless sourced")
    walls.add_argument("--sill", type=float, default=DEFAULT_SILL_HEIGHT_METRES, help="window sill height, metres; an ESTIMATE")
    walls.add_argument("--window-head", type=float, default=DEFAULT_WINDOW_HEAD_METRES, help="window head height, metres; an ESTIMATE")
    walls.add_argument("--max-opening", type=float, default=DEFAULT_OPENING_WIDTH_METRES, help="widest gap, metres, treated as a door or window")
    walls.add_argument("--max-opening-depth", type=float, default=0.5, help="thickest wall, metres, whose gaps count as openings")
    walls.add_argument("--interior-doors", action="store_true", help="treat openings with the footprint on both sides as doors, so only outer walls carry windows")
    walls.add_argument("--slot-windows", action="store_true", help="gaps too narrow to walk through become windows cut from the sill to the head with their own outline, instead of solid wall")
    walls.add_argument("--door-width", type=float, default=None, help="cut every door to this one clear width, metres, centred on the plan's opening, so one door asset fits all")
    walls.add_argument("--max-double-opening", type=float, default=None, help="gaps wider than --max-opening and up to this width, metres, become double doors of two --door-width leaves")
    walls.add_argument("--window-outer-width", type=float, default=None, help="clear width of every window through the outer part of the wall, metres; the plan's full gap stays behind it as the inner splay")
    walls.add_argument("--window-outer-depth", type=float, default=None, help="depth from the outer face that --window-outer-width applies to, metres")
    walls.add_argument("--door-list", default=None, help="write door and window placements (plan position relative to the window corner, yaw, size) to this JSON file")
    walls.add_argument("--floor", action="store_true", help="add a floor slab under the footprint")
    walls.add_argument("--roof", action="store_true", help="add a roof over the footprint; flat unless --roof-pitch is given")
    walls.add_argument("--roof-pitch", type=float, default=0.0, help="degrees; a gable along the long side; an ESTIMATE unless sourced")
    walls.add_argument("--overhang", type=float, default=0.0, help="metres of roof beyond the footprint")
    walls.add_argument("--slab", type=float, default=DEFAULT_SLAB_THICKNESS_METRES, help="slab thickness, metres")
    walls.add_argument("--close-gap", type=float, default=DEFAULT_CLOSE_GAP_METRES, help="openings up to this width, metres, are closed to find the footprint")
    crop = sub.add_parser("crop", help="save an enlarged crop of an image region to read small labels")
    crop.add_argument("image")
    crop.add_argument("--box", required=True, type=window_argument, help="x0,y0,x1,y1 in image pixels")
    crop.add_argument("--zoom", type=float, default=2.0)
    crop.add_argument("--out", required=True)
    lines = sub.add_parser("lines", help="list the long horizontal or vertical drawn lines in a region of an elevation image, in metres from a ground line")
    lines.add_argument("image")
    lines.add_argument("--box", required=True, type=window_argument, help="x0,y0,x1,y1 in image pixels")
    lines.add_argument("--axis", choices=[elevation.HORIZONTAL, elevation.VERTICAL], required=True)
    lines.add_argument("--min-length", type=float, required=True, help="shortest line to report, metres")
    lines.add_argument("--ppm", type=float, required=True, help="image pixels per metre, measured from a dimension on the sheet")
    lines.add_argument("--ground-y", type=float, required=True, help="image y of the ground line")
    lines.add_argument("--origin-x", type=float, default=0.0, help="image x that reads as 0 m")
    hull = sub.add_parser("hull", help="blockout from two orthogonal elevation images by silhouette intersection")
    hull.add_argument("image")
    hull.add_argument("--front-box", required=True, type=window_argument, help="x0,y0,x1,y1 in image pixels")
    hull.add_argument("--side-box", required=True, type=window_argument)
    hull.add_argument("--front-width", type=float, help="real width of the front view, metres")
    hull.add_argument("--side-width", type=float, help="real width of the side view, metres")
    hull.add_argument("--scale", type=float, help="pixels per metre measured from a dimension on the image; replaces the two widths")
    hull.add_argument("--out", required=True)
    hull.add_argument("--axes", choices=[AXES_CAD, AXES_GLTF], default=AXES_GLTF)
    return parser.parse_args(argv)


def run_hull(args):
    front_box = tuple(int(v) for v in args.front_box)
    side_box = tuple(int(v) for v in args.side_box)
    front = silhouette.silhouette_polygon(silhouette.filled_mask(silhouette.load_crop(args.image, front_box)))
    side = silhouette.silhouette_polygon(silhouette.filled_mask(silhouette.load_crop(args.image, side_box)))
    front_width, side_width = args.front_width, args.side_width
    if args.scale:
        front_width = (front.bounds[2] - front.bounds[0]) / args.scale
        side_width = (side.bounds[2] - side.bounds[0]) / args.scale
        print(f"scale {args.scale} px/m gives widths {front_width:.2f} m (front) and {side_width:.2f} m (side)")
    if not front_width or not side_width:
        print("give --scale or both --front-width and --side-width")
        return 1
    solid, front_height, side_height, height = silhouette.hull_mesh(front, side, front_width, side_width)
    print(f"front view implies height {front_height:.2f} m, side view {side_height:.2f} m (should agree)")
    print(mesh_report(solid))
    for output in write_mesh(solid, args.out, args.axes):
        print(f"wrote {output}")
    return 0


def run(args):
    if args.command == "hull":
        return run_hull(args)
    if args.command == "lines":
        for row in elevation.measure_lines(args.image, args.box, args.axis, args.min_length, args.ppm, args.ground_y, args.origin_x):
            print(json.dumps(row))
        return 0
    if args.command == "crop":
        box = tuple(int(v) for v in args.box)
        region = silhouette.load_crop(args.image, box)
        enlarged = cv2.resize(region, None, fx=args.zoom, fy=args.zoom, interpolation=cv2.INTER_CUBIC)
        cv2.imwrite(args.out, enlarged)
        print(f"wrote {args.out} {enlarged.shape[1]}x{enlarged.shape[0]}")
        return 0
    if args.command == "fetch":
        for path in sources.fetch(args.url, args.name):
            print(f"{path.stat().st_size:>10}  {path}")
    elif args.command == "convert":
        print("ok" if sources.dwg_to_dxf(args.dwg, args.dxf) else "failed")
    elif args.command == "summary":
        print(summary(args.dxf))
    elif args.command == "extents":
        print(extents_report(args.dxf))
    elif args.command == "calibrate":
        print(calibration_report(args.dxf))
    elif args.command == "preview":
        drawn, size = render(args.dxf, args.layers.split(","), args.window, args.out, args.ppu)
        print(f"drew {drawn} paths into {args.out} {size[0]}x{size[1]}")
    elif args.command == "walls":
        polygons, wall_mask = extract_walls(args.dxf, set(args.layers.split(",")), args.window, args.ppm, args.hatch_layer)
        origin = (args.window[0], args.window[1])
        if args.carve_circle:
            x, y, radius = (float(v) for v in args.carve_circle.split(","))
            hole = Point(x, y).buffer(radius, 64)
            polygons = [part for polygon in polygons for part in explode(polygon.difference(hole)) if part.area > 0]
        doors, windows, gaps, unpassable, doubles = [], [], [], [], []
        if args.openings:
            found = find_openings(wall_mask, args.window, args.ppm, args.max_opening, args.max_opening_depth)
            doors, windows = split_openings(found, door_swing_centres(args.dxf, args.door_layer, args.window))
            arcs = len(doors)
            if args.interior_doors:
                outline = footprint(polygons, args.close_gap)
                doors, windows = interior_as_doors(doors, windows, outline, INTERIOR_PROBE_METRES)
                passages, unpassable = find_passages(polygons, outline, args.max_opening, PASSAGE_MIN_AREA_M2, MIN_PASSABLE_CLEAR_METRES)
                doors = merge_openings(doors, windows, passages)
            doubles = []
            if args.max_double_opening:
                wide = find_openings(wall_mask, args.window, args.ppm, args.max_double_opening, args.max_opening_depth)
                doubles = [gap for gap in wide if not any(gap.intersects(single) for single in found)]
            gaps = doors + windows + unpassable + doubles
            print(f"openings {len(found)}: {len(doors)} doors ({arcs} by swing arc), {len(windows)} windows, {len(unpassable)} unpassable gaps {"cut as slot windows" if args.slot_windows else "filled"}, {len(doubles)} double doors")
        wall_union = unary_union(polygons)
        solid = unary_union(polygons + gaps)
        if args.carve_circle:
            solid = solid.difference(hole)
        solid = set_precision(solid, CENTIMETRE)
        door_cuts = [standard_door(door, args.door_width, DOOR_CUT_EXTRA_METRES, wall_union) if args.door_width else standard_door(door, opening_axes(door, wall_union)[2], DOOR_CUT_EXTRA_METRES, wall_union) for door in doors]
        door_cuts += [standard_door(door, 2 * args.door_width, DOOR_CUT_EXTRA_METRES, wall_union) for door in doubles]
        window_cuts = [standard_door(window, opening_axes(window, wall_union)[2], DOOR_CUT_EXTRA_METRES, wall_union) for window in windows]
        window_outward = [None] * len(window_cuts)
        if args.window_outer_width and window_cuts:
            house = footprint(polygons, args.close_gap)
            stepped = [stepped_window(cut, window, args.window_outer_width, args.window_outer_depth, wall_union, house) for cut, window in zip(window_cuts, windows)]
            window_cuts, window_outward = [shape for shape, _ in stepped], [direction for _, direction in stepped]
        cutters = [(set_precision(absorb_fins(solid, set_precision(cut, CENTIMETRE)), CENTIMETRE), -DOOR_CUT_EXTRA_METRES, args.door_height) for cut in door_cuts]
        cutters += [(set_precision(cut, CENTIMETRE), args.sill, args.window_head) for cut in window_cuts]
        slot_cuts = [set_precision(gap.buffer(SLOT_CUT_EXTRA_METRES, join_style=2), CENTIMETRE) for gap in unpassable] if args.slot_windows else []
        cutters += [(cut, args.sill, args.window_head) for cut in slot_cuts]
        mesh = walls_with_openings(solid, cutters, args.height, origin)
        if mesh is None or mesh.is_empty:
            print("no wall shapes found")
            return 1
        polygons = list(explode(solid))
        if args.openings and args.door_list:
            placements = {"origin_drawing_xy": list(origin), "doors": door_placements(door_cuts, origin, args.door_height, wall_union), "windows": [dict(placement, **({"outward_xy": list(direction), "outer_width_m": args.window_outer_width} if direction else {})) for placement, direction in zip(door_placements(window_cuts, origin, args.window_head - args.sill, wall_union), window_outward)], "slots": [[[to_cm(x - origin[0]), to_cm(y - origin[1])] for x, y in cut.exterior.coords] for cut in slot_cuts]}
            Path(args.door_list).write_text(json.dumps(placements, indent=1) + chr(10), encoding="utf-8", newline=chr(10))
            print(f"wrote {args.door_list}")
        if args.floor or args.roof:
            outline = footprint(polygons, args.close_gap)
            parts = {"walls": mesh}
            if args.floor:
                parts["floor"] = slab(outline, origin, -args.slab, args.slab)
            if args.roof and args.roof_pitch > 0:
                parts["roof"] = gable(outline, origin, args.height, args.roof_pitch, args.overhang)
            elif args.roof:
                parts["roof"] = slab(outline.buffer(args.overhang), origin, args.height, args.slab)
            mesh = parts
        report = trimesh.util.concatenate(list(mesh.values())) if isinstance(mesh, dict) else mesh
        print(f"wall shapes {len(polygons)}, area {sum(p.area for p in polygons):.1f} m2, height {args.height} m")
        print(mesh_report(report))
        for output in write_mesh(mesh, args.out, args.axes):
            print(f"wrote {output}")
    return 0


def main(argv=None):
    return run(parse_args(argv if argv is not None else sys.argv[1:]))
