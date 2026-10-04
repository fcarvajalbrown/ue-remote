import math
import random


def folder_root(world):
    return world.get("folder_root", "World")


def distance_to_segment(px, py, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    t = 0.0 if length_squared == 0 else max(0.0, min(1.0, ((px - start[0]) * dx + (py - start[1]) * dy) / length_squared))
    return math.hypot(px - (start[0] + t * dx), py - (start[1] + t * dy))


def near_path(world, x, y, margin):
    for path in world["paths"]:
        reach = path["width"] / 2 + margin
        for start, end in zip(path["points"][:-1], path["points"][1:]):
            if distance_to_segment(x, y, start, end) < reach:
                return True
    return False


def rotate_xy(x, y, degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return x * c - y * s, x * s + y * c


def building_rows(world, ground, buildings):
    rows = []
    for placement in world["buildings"]:
        spec = buildings[placement["building"]]
        bx, by = placement["at"]
        yaw = placement.get("yaw", 0)
        base_z = ground.pad_height(bx, by) + spec["elevation"]
        folder = f"{folder_root(world)}/{placement['folder']}"

        def add(piece, lx, ly, lz, local_yaw):
            wx, wy = rotate_xy(lx, ly, yaw)
            rows.append({"piece": piece, "x": bx + wx, "y": by + wy, "z": base_z + lz, "yaw": yaw + local_yaw, "scale": 1.0, "scale_x": 1.0, "folder": folder})

        for wall in spec["walls"]:
            (x0, y0), (x1, y1) = wall["from"], wall["to"]
            add(f"{placement['building']}_wall_{wall['id']}", x0, y0, 0.0, math.degrees(math.atan2(y1 - y0, x1 - x0)))
        for part in spec["parts"]:
            ax, ay, az = part["at"]
            add(part["piece"], ax, ay, az, part.get("yaw", 0))
    return rows


def wall_pieces(buildings):
    pieces = {}
    for name, spec in buildings.items():
        for wall in spec["walls"]:
            (x0, y0), (x1, y1) = wall["from"], wall["to"]
            pieces[f"{name}_wall_{wall['id']}"] = {
                "parts": [{
                    "t": "wall", "m": "wood", "length": math.hypot(x1 - x0, y1 - y0), "height": wall["height"],
                    "thickness": wall.get("thickness", spec["thickness"]), "openings": wall["openings"],
                    "siding": wall["siding"], "extend": wall.get("extend", False),
                }]
            }
    return pieces


def prop_rows(world, ground):
    return [
        {"piece": p["piece"], "x": p["at"][0], "y": p["at"][1], "z": ground.pad_height(*p["at"]), "yaw": p.get("yaw", 0), "scale": 1.0, "scale_x": 1.0, "folder": f"{folder_root(world)}/Props"}
        for p in world["props"]
    ]


def fence_rows(world, ground):
    half_x, half_y = world["plot"]["half"]
    gate_x, gate_half = world["gate"]["x"], world["gate"]["half_width"]
    corners = [(-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)]
    runs = [
        (corners[0], (gate_x - gate_half, -half_y)),
        ((gate_x + gate_half, -half_y), corners[1]),
        (corners[1], corners[2]),
        (corners[2], corners[3]),
        (corners[3], corners[0]),
    ]
    rows = []
    for start, end in runs:
        length = math.dist(start, end)
        count = max(int(round(length / 3.0)), 1)
        heading = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
        for i in range(count):
            x = start[0] + (end[0] - start[0]) * i / count
            y = start[1] + (end[1] - start[1]) * i / count
            rows.append({"piece": "fence_section", "x": x, "y": y, "z": ground.mesh_height(x, y), "yaw": heading, "scale": 1.0, "scale_x": length / count / 3.0, "folder": f"{folder_root(world)}/Fence"})
    for x, y in ((gate_x + gate_half, -half_y), (-half_x, -half_y)):
        rows.append({"piece": "fence_post", "x": x, "y": y, "z": ground.mesh_height(x, y), "yaw": 0.0, "scale": 1.0, "scale_x": 1.0, "folder": f"{folder_root(world)}/Fence"})
    gx = gate_x - gate_half
    rows.append({"piece": "gate", "x": gx, "y": -half_y, "z": ground.mesh_height(gx, -half_y), "yaw": 0.0, "scale": 1.0, "scale_x": 1.0, "folder": f"{folder_root(world)}/Fence"})
    return rows


def tree_rows(world, ground):
    spec = world["forest"]
    prefix = spec.get("piece_prefix", "tree")
    rng = random.Random(spec["seed"])
    half_x, half_y = world["plot"]["half"]
    margin = spec["clearing_margin"]
    spacing = spec["spacing"]
    cell = spacing / math.sqrt(2)
    grid, accepted = {}, []
    keepouts = [(b["at"][0], b["at"][1], b["pad"] + 6) for b in world["buildings"]]
    path_margin = spec.get("path_margin", 3.0)

    def free(x, y):
        gx, gy = int(x // cell), int(y // cell)
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                other = grid.get((gx + dx, gy + dy))
                if other and math.hypot(other[0] - x, other[1] - y) < spacing:
                    return False
        return True

    attempts = int(math.pi * spec["radius"] ** 2 / spacing ** 2 * 14)
    for _ in range(attempts):
        radius = spec["radius"] * math.sqrt(rng.random())
        angle = rng.random() * 2 * math.pi
        x, y = radius * math.cos(angle), radius * math.sin(angle)
        if abs(x) < half_x + margin and abs(y) < half_y + margin:
            continue
        if near_path(world, x, y, path_margin) or any(math.hypot(x - kx, y - ky) < kr for kx, ky, kr in keepouts):
            continue
        if free(x, y):
            grid[(int(x // cell), int(y // cell))] = (x, y)
            accepted.append((x, y))

    stages, weights = list(spec["mix"].keys()), list(spec["mix"].values())
    rows = []
    for x, y in accepted:
        stage = rng.choices(stages, weights)[0]
        rows.append({"piece": f"{prefix}_{stage}", "x": x, "y": y, "z": ground.mesh_height(x, y), "yaw": rng.random() * 360, "scale": rng.uniform(*spec["scale"]), "scale_x": 1.0, "folder": f"{folder_root(world)}/Forest"})
    for tree in spec["yard_trees"]:
        x, y = tree["at"]
        rows.append({"piece": f"{prefix}_{tree['stage']}", "x": x, "y": y, "z": ground.mesh_height(x, y), "yaw": rng.random() * 360, "scale": 1.0, "scale_x": 1.0, "folder": f"{folder_root(world)}/Yard"})
    return rows
