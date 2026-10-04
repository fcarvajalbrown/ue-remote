import math
import random

import meshkit as mk


def lerp(pair, t):
    return pair[0] + (pair[1] - pair[0]) * t


def trunk_radius_at(spec, z):
    return lerp(spec["trunk_radius"], min(z / spec["height"], 1.0))


def branch_path(spec, lod, start_radius, z, length, radius, elevation, yaw):
    points = lod["points"]
    segment = length / (points - 1)
    x, height = start_radius, z
    path, radii = [(x, 0.0, height)], [radius]
    for k in range(1, points):
        s = k / (points - 1)
        angle = math.radians(elevation + spec["curl_deg"] * s * s)
        x += segment * math.cos(angle)
        height += segment * math.sin(angle)
        path.append((x, 0.0, height))
        radii.append(radius * (1.0 - 0.55 * s))
    rotation = mk.rotation_z(math.radians(yaw))
    return [tuple(rotation @ point) for point in path], radii


def build_tree(spec, lod_index):
    lod = spec["lods"][lod_index]
    rng = random.Random(spec["seed"])
    height = spec["height"]
    r_base, r_top = spec["trunk_radius"]
    crown_start = spec["crown_start"] * height
    trunk, crown = mk.Mesh(), mk.Mesh()

    heights = [0.0, height * 0.04, height * 0.5, height - spec["leader"]]
    radii = [r_base * 1.3, r_base, lerp((r_base, r_top), 0.5), r_top]
    trunk.tube("bark", [(0.0, 0.0, z) for z in heights], radii, lod["trunk_sections"])

    if lod_index <= 1:
        scars = spec["scar_whorls"]
        for w in range(scars):
            z = crown_start * (0.35 + 0.6 * w / max(scars, 1))
            base = rng.random() * 360
            for j in range(4):
                path, stub = branch_path({"curl_deg": 0}, {"points": 2}, trunk_radius_at(spec, z), z, 0.55, 0.05, -4, base + j * 90)
                trunk.tube("bark", path, stub, 4, True, False)

    whorls = spec["whorls"]
    top_z = height - spec["leader"]
    for i in range(0, whorls, lod["whorl_step"]):
        t = i / (whorls - 1)
        z = crown_start + (top_z - crown_start) * t
        length = lerp(spec["branch_length"], t)
        radius = lerp(spec["branch_radius"], t)
        elevation = lerp(spec["elevation_deg"], t)
        count = spec["branches_per_whorl"]
        offset = rng.random() * 360
        for j in range(count):
            yaw = offset + j * 360 / count + rng.uniform(-12, 12)
            path, widths = branch_path(spec, lod, trunk_radius_at(spec, z) * 0.8, z, length * rng.uniform(0.9, 1.1), radius, elevation, yaw)
            crown.tube("foliage", path, widths, lod["sections"], True, False)

    crown.frustum("foliage", spec["branch_radius"][1] * 1.4, 0.04, spec["leader"] + 0.6, top_z - 0.6, max(lod["sections"], 4))
    return {"trunk": trunk, "crown": crown}
