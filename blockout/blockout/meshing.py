import numpy as np
import trimesh
from shapely.affinity import translate
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from blockout import gridsnap

DEFAULT_WALL_HEIGHT_METRES = 3.0
DEFAULT_SLAB_THICKNESS_METRES = 0.15
DEFAULT_CLOSE_GAP_METRES = 1.5
DEFAULT_DOOR_HEIGHT_METRES = 2.1
DEFAULT_SILL_HEIGHT_METRES = 0.9
DEFAULT_WINDOW_HEAD_METRES = 2.1
DEFAULT_OPENING_WIDTH_METRES = 2.5
SIMPLIFY_TOLERANCE_METRES = 0.05
AXES_CAD = "cad"
AXES_GLTF = "gltf"


def explode(geometry):
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    return [part for part in getattr(geometry, "geoms", []) if isinstance(part, Polygon)]


def extrude_all(polygons, height, origin):
    meshes = []
    for polygon in polygons:
        for part in explode(polygon):
            if part.area <= 0:
                continue
            moved = Polygon(
                [(x - origin[0], y - origin[1]) for x, y in part.exterior.coords],
                [[(x - origin[0], y - origin[1]) for x, y in ring.coords] for ring in part.interiors],
            )
            meshes.append(trimesh.creation.extrude_polygon(moved, height))
    return trimesh.util.concatenate(meshes) if meshes else None


def footprint(polygons, close_gap):
    joined = unary_union(polygons).buffer(close_gap / 2).buffer(-close_gap / 2)
    return unary_union([Polygon(part.exterior).simplify(SIMPLIFY_TOLERANCE_METRES) for part in explode(joined)])


def slab(shape, origin, bottom, thickness):
    meshes = []
    for part in explode(translate(shape, -origin[0], -origin[1])):
        solid = trimesh.creation.extrude_polygon(part, thickness)
        solid.apply_translation([0, 0, bottom])
        meshes.append(solid)
    return trimesh.util.concatenate(meshes)


def gable(shape, origin, base, pitch_degrees, overhang):
    low_x, low_y, high_x, high_y = translate(shape, -origin[0], -origin[1]).bounds
    low_x, low_y, high_x, high_y = low_x - overhang, low_y - overhang, high_x + overhang, high_y + overhang
    along_x = (high_x - low_x) >= (high_y - low_y)
    span = (high_y - low_y) if along_x else (high_x - low_x)
    rise = span / 2 * np.tan(np.radians(pitch_degrees))
    if along_x:
        mid = (low_y + high_y) / 2
        vertices = [[low_x, low_y, base], [high_x, low_y, base], [high_x, high_y, base], [low_x, high_y, base], [low_x, mid, base + rise], [high_x, mid, base + rise]]
        faces = [[0, 1, 5], [0, 5, 4], [3, 4, 5], [3, 5, 2], [0, 4, 3], [1, 2, 5], [0, 3, 2], [0, 2, 1]]
    else:
        mid = (low_x + high_x) / 2
        vertices = [[low_x, low_y, base], [high_x, low_y, base], [high_x, high_y, base], [low_x, high_y, base], [mid, low_y, base + rise], [mid, high_y, base + rise]]
        faces = [[0, 1, 4], [3, 5, 2], [0, 4, 5], [0, 5, 3], [1, 2, 5], [1, 5, 4], [0, 3, 2], [0, 2, 1]]
    roof = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    if roof.volume < 0:
        roof.invert()
    return roof


def to_axes(mesh, axes):
    result = mesh.copy()
    if axes == AXES_GLTF:
        rotation = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)
        result.apply_transform(rotation)
    return result


def named_scene(parts, axes):
    scene = trimesh.Scene()
    for name, mesh in parts.items():
        moved = to_axes(mesh, axes)
        moved.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(name=name))
        scene.add_geometry(moved, geom_name=name, node_name=name)
    return scene


def snap_to_cm(mesh):
    return gridsnap.to_trimesh(gridsnap.on_grid(gridsnap.from_trimesh(mesh)))


def write_mesh(mesh, base_path, axes):
    mesh = {name: snap_to_cm(part) for name, part in mesh.items()} if isinstance(mesh, dict) else snap_to_cm(mesh)
    parts = mesh if isinstance(mesh, dict) else {"mesh": mesh}
    outputs = []
    if axes == AXES_GLTF:
        target = f"{base_path}.glb"
        named_scene(parts, AXES_GLTF).export(target)
        outputs.append(target)
    target = f"{base_path}.obj"
    named_scene(parts, AXES_CAD).export(target)
    outputs.append(target)
    return outputs


def mesh_report(mesh):
    low, high = mesh.bounds
    size = high - low
    return (
        f"vertices {len(mesh.vertices)}, triangles {len(mesh.faces)}, "
        f"size {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} m, volume {mesh.volume:.1f} m3"
    )


def prism(shape, origin, bottom, top):
    return slab(shape, origin, bottom, top - bottom)


def walls_with_openings(solid, cutters, height, origin):
    walls = extrude_all([solid], height, origin)
    boxes = [prism(shape, origin, bottom, top) for shape, bottom, top in cutters]
    if not boxes:
        return walls
    return trimesh.boolean.difference([walls] + boxes, engine="manifold")


