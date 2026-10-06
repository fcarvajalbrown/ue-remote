import manifold3d
import numpy as np
import trimesh

Manifold = manifold3d.Manifold
GRID_METRES = 0.01
GRID_NUDGE = 1e-6


def snap_point(point):
    return [float(np.floor(value / GRID_METRES + 0.5 + GRID_NUDGE) * GRID_METRES) for value in point]


def on_grid(solid):
    snapped = solid.warp(snap_point).simplify(0.0)
    if snapped.status() != manifold3d.Error.NoError:
        raise ValueError(f"grid snap failed: {snapped.status()}")
    return snapped


def from_triangles(triangles):
    merged = trimesh.Trimesh(vertices=np.asarray(triangles, dtype=float).reshape(-1, 3), faces=np.arange(len(triangles) * 3).reshape(-1, 3), process=False)
    merged.merge_vertices(digits_vertex=6)
    return from_trimesh(merged)


def from_trimesh(mesh):
    solid = Manifold(manifold3d.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32), tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))
    if solid.status() != manifold3d.Error.NoError:
        raise ValueError(f"not a closed solid: {solid.status()}")
    return solid


def triangles(solid):
    mesh = solid.to_mesh()
    return np.asarray(mesh.vert_properties)[:, :3].astype(float)[np.asarray(mesh.tri_verts)]


def to_trimesh(solid):
    mesh = solid.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3].astype(float), faces=np.asarray(mesh.tri_verts, dtype=np.int64), process=False)


def labelled_union(pieces):
    labels, solids = {}, []
    for material, solid in pieces:
        if solid.is_empty():
            continue
        tagged = solid.as_original()
        labels[tagged.original_id()] = material
        solids.append(tagged)
    return Manifold.batch_boolean(solids, manifold3d.OpType.Add), labels


def split_by_label(solid, labels):
    mesh = solid.to_mesh()
    corners = np.asarray(mesh.vert_properties)[:, :3].astype(float)[np.asarray(mesh.tri_verts)]
    starts = np.asarray(mesh.run_index) // 3
    owners = np.asarray(mesh.run_original_id)
    parts = {}
    for run, original in enumerate(owners):
        material = labels.get(int(original))
        if material is None:
            raise ValueError(f"triangles from an unlabelled source {original}")
        parts.setdefault(material, []).append(corners[starts[run]:starts[run + 1]])
    return {material: np.concatenate(chunks) for material, chunks in parts.items()}


def minimum_angle(points):
    a, b, c = points
    angles = []
    for p, q, r in ((a, b, c), (b, c, a), (c, a, b)):
        u, v = q - p, r - p
        denominator = np.linalg.norm(u) * np.linalg.norm(v)
        if denominator < 1e-15:
            return 0.0
        angles.append(np.arccos(np.clip(np.dot(u, v) / denominator, -1.0, 1.0)))
    return min(angles)


def unit_normal(points):
    normal = np.cross(points[1] - points[0], points[2] - points[0])
    length = np.linalg.norm(normal)
    return normal / length if length > 1e-15 else None


def flip_to_fatter(vertices, faces, labels, max_passes=50, gain=1e-6, coplanar=1e-9):
    faces = [list(face) for face in faces]
    for _ in range(max_passes):
        edges = {}
        for index, (a, b, c) in enumerate(faces):
            for u, v in ((a, b), (b, c), (c, a)):
                edges.setdefault((min(u, v), max(u, v)), []).append(index)
        flipped = False
        touched = set()
        for (low, high), owners in edges.items():
            if len(owners) != 2:
                continue
            first, second = owners
            if first in touched or second in touched or labels[first] != labels[second]:
                continue
            t1, t2 = faces[first], faces[second]
            i = next(k for k in range(3) if {t1[k], t1[(k + 1) % 3]} == {low, high})
            a, b, c = t1[i], t1[(i + 1) % 3], t1[(i + 2) % 3]
            if not ({b, a} <= set(t2)):
                continue
            d = next(vertex for vertex in t2 if vertex not in (a, b))
            if d == c:
                continue
            n1, n2 = unit_normal(vertices[[a, b, c]]), unit_normal(vertices[[b, a, d]])
            if n1 is None or n2 is None or np.dot(n1, n2) < 1.0 - coplanar:
                continue
            new1, new2 = [a, d, c], [d, b, c]
            m1, m2 = unit_normal(vertices[new1]), unit_normal(vertices[new2])
            if m1 is None or m2 is None or np.dot(m1, n1) < 1.0 - coplanar or np.dot(m2, n1) < 1.0 - coplanar:
                continue
            before = min(minimum_angle(vertices[[a, b, c]]), minimum_angle(vertices[[b, a, d]]))
            after = min(minimum_angle(vertices[new1]), minimum_angle(vertices[new2]))
            if after > before + gain:
                faces[first], faces[second] = new1, new2
                touched.update((first, second))
                flipped = True
        if not flipped:
            break
    return np.array(faces, dtype=np.int64)


def finished_parts(solid, labels=None):
    snapped = on_grid(solid)
    mesh = snapped.to_mesh()
    vertices = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64)
    faces = np.asarray(mesh.tri_verts, dtype=np.int64)
    owner = np.empty(len(faces), dtype=object)
    starts = np.asarray(mesh.run_index) // 3
    for run, original in enumerate(np.asarray(mesh.run_original_id)):
        owner[starts[run]:starts[run + 1]] = labels.get(int(original)) if labels else None
    if labels and any(value is None for value in owner):
        raise ValueError("triangles from an unlabelled source")
    faces = flip_to_fatter(vertices, faces, list(owner))
    parts = {}
    for material in dict.fromkeys(owner):
        parts[material] = vertices[faces[owner == material]]
    return parts
