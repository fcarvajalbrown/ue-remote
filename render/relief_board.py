import argparse
import json
import time
from collections import deque
from pathlib import Path

import numpy as np
import mitsuba as mi


def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def box_blur(image, radius):
    if radius < 1:
        return image
    size = 2 * radius + 1
    for axis in (0, 1):
        padded = np.pad(image, [(radius + 1, radius) if a == axis else (0, 0) for a in (0, 1)], mode="edge")
        summed = np.cumsum(padded, axis=axis)
        upper = np.take(summed, np.arange(size, summed.shape[axis]), axis=axis)
        lower = np.take(summed, np.arange(0, summed.shape[axis] - size), axis=axis)
        image = (upper - lower) / size
    return image


def soft_blur(image, radius):
    step = max(int(round(radius / 1.7)), 1)
    for _ in range(3):
        image = box_blur(image, step)
    return image


def sample(image, u, v):
    height, width = image.shape[:2]
    x = u * width - 0.5
    y = v * height - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = x - x0
    fy = y - y0
    x0 %= width
    y0 %= height
    x1 = (x0 + 1) % width
    y1 = (y0 + 1) % height
    if image.ndim == 3:
        fx = fx[..., None]
        fy = fy[..., None]
    top = image[y0, x0] * (1 - fx) + image[y0, x1] * fx
    bottom = image[y1, x0] * (1 - fx) + image[y1, x1] * fx
    return top * (1 - fy) + bottom * fy


def clamp_sample(image, u, v):
    height, width = image.shape[:2]
    return sample(image, np.clip(u, 0.5 / width, 1 - 0.5 / width), np.clip(v, 0.5 / height, 1 - 0.5 / height))


def grid(width, height):
    u = (np.arange(width) + 0.5) / width
    v = (np.arange(height) + 0.5) / height
    return np.meshgrid(u, v)


def load_image(path):
    return np.array(mi.Bitmap(str(path)), dtype=np.float32) / 255.0


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def filmic(x):
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0)


def carve_fields(mask, carve):
    soft = soft_blur(mask, float(carve["blur_px"]))
    return smoothstep(0.0, 1.0, soft)


def inside_distance(coverage, max_px):
    cut = coverage > 0.5
    height, width = cut.shape
    cap = np.float32(max_px + 1)
    column = np.empty((height, width), np.float32)
    run = np.zeros(width, np.float32)
    for y in range(height):
        run = np.where(cut[y], np.minimum(run + 1, cap), 0).astype(np.float32)
        column[y] = run
    run = np.zeros(width, np.float32)
    for y in range(height - 1, -1, -1):
        run = np.where(cut[y], np.minimum(run + 1, column[y]), 0).astype(np.float32)
        column[y] = run
    squared = column * column
    best = squared.copy()
    for k in range(1, int(max_px) + 2):
        kk = np.float32(k * k)
        np.minimum(best[:, k:], squared[:, :-k] + kk, out=best[:, k:])
        np.minimum(best[:, :-k], squared[:, k:] + kk, out=best[:, :-k])
    x = np.arange(width, dtype=np.float32)
    best = np.minimum(best, np.minimum((x + 1) ** 2, (width - x) ** 2)[None, :])
    distance = np.sqrt(best) - 1.0 + np.clip(coverage, 0.0, 1.0)
    return np.where(cut, np.maximum(distance, 0.0), 0.0).astype(np.float32)


def flood(binary, seed):
    height, width = binary.shape
    sx = min(max(int(seed[0] * width), 0), width - 1)
    sy = min(max(int(seed[1] * height), 0), height - 1)
    target = binary[sy, sx]
    flat = binary.ravel()
    region = np.zeros(height * width, bool)
    start = sy * width + sx
    region[start] = True
    queue = deque([start])
    last_row = (height - 1) * width
    while queue:
        i = queue.popleft()
        x = i % width
        for j, ok in ((i - 1, x > 0), (i + 1, x < width - 1), (i - width, i >= width), (i + width, i < last_row)):
            if ok and not region[j] and flat[j] == target:
                region[j] = True
                queue.append(j)
    return region.reshape(height, width)


def profile_depth(coverage, depth_m, carve, pixel_m):
    if carve.get("profile", "soft") != "v":
        return smoothstep(0.0, 1.0, soft_blur(coverage, float(carve["blur_px"]))) * depth_m, None
    slope = float(carve.get("slope", 1.0))
    max_px = int(np.ceil(depth_m / (slope * pixel_m))) + 2
    distance = inside_distance(coverage, max_px)
    depth = np.minimum(distance * pixel_m * slope, depth_m)
    smooth = float(carve.get("smooth_px", 0.0))
    if smooth > 0:
        depth = soft_blur(depth, smooth)
    return depth.astype(np.float32), distance


def relief_fields(mask, spec):
    carve, board = spec["carve"], spec["board"]
    depth_m = float(carve["depth_m"])
    profile = carve.get("profile", "soft")
    if profile != "v" and not spec.get("regions"):
        groove = carve_fields(mask, carve)
        return {"depth": None, "groove": groove, "letters": mask, "distance": None, "regions": []}
    pixel_m = float(board["width_m"]) / mask.shape[1]
    cut = mask > 0.5
    found = [(entry, flood(cut, entry["seed_uv"])) for entry in spec.get("regions", [])]
    letters = mask.copy()
    for entry, region in found:
        if float(entry.get("depth_m", 0.0)) <= 0:
            letters[region] = 0.0
    depth, distance = profile_depth(letters, depth_m, carve, pixel_m)
    if profile == "v":
        groove = smoothstep(0.0, 1.0, soft_blur(letters, float(carve.get("groove_blur_px", 2.0))))
    else:
        groove = depth / depth_m
    regions = []
    for entry, region in found:
        floor_depth = float(entry.get("depth_m", 0.0))
        if floor_depth <= 0:
            continue
        own, _ = profile_depth(region.astype(np.float32), floor_depth, dict(carve, slope=entry.get("slope", carve.get("slope", 1.0))), pixel_m)
        depth = np.maximum(depth, own)
        floor = smoothstep(0.85, 0.98, own / floor_depth)
        groove = np.maximum(groove, smoothstep(0.02, 0.2, own / floor_depth) * (1 - floor))
        ys, xs = np.nonzero(region)
        centre = ((xs.min() + xs.max()) / 2 / mask.shape[1], (ys.min() + ys.max()) / 2 / mask.shape[0])
        extent = ((xs.max() - xs.min()) / 2 / mask.shape[1], (ys.max() - ys.min()) / 2 / mask.shape[0])
        regions.append({"entry": entry, "floor": floor.astype(np.float32), "centre": centre, "extent": extent})
    return {"depth": depth.astype(np.float32), "groove": groove.astype(np.float32), "letters": letters, "distance": distance, "regions": regions}


def edge_drop(board, x, y, drop):
    radius = float(board["edge_round_m"])
    width, height = float(board["width_m"]), float(board["height_m"])
    edge = np.minimum(np.minimum(x + width / 2, width / 2 - x), np.minimum(y + height / 2, height / 2 - y))
    t = np.clip(1.0 - edge / radius, 0.0, 1.0)
    return drop * (1.0 - np.sqrt(1.0 - t * t))


def build_face(board, carve, groove, depth_field=None):
    nx, ny = (int(n) for n in board["mesh_px"])
    u, v = grid(nx, ny)
    if depth_field is None:
        depth = clamp_sample(groove, u, v) * float(carve["depth_m"])
    else:
        depth = clamp_sample(depth_field, u, v)
    width, height = float(board["width_m"]), float(board["height_m"])
    x = (u - 0.5) * width
    y = (0.5 - v) * height
    z = -depth
    if float(board.get("edge_round_m", 0.0)) > 0:
        drop = float(board.get("edge_drop_m", float(depth.max()) + 0.003))
        z = np.minimum(z, -edge_drop(board, x, y, drop))
    dzdx = np.gradient(z, x[0], axis=1)
    dzdy = np.gradient(z, y[:, 0], axis=0)
    normals = np.stack([-dzdx, -dzdy, np.ones_like(z)], axis=-1)
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    positions = np.stack([x, y, z], axis=-1).reshape(-1, 3)
    uvs = np.stack([u, v], axis=-1).reshape(-1, 2)
    index = np.arange(nx * ny).reshape(ny, nx)
    a = index[:-1, :-1].ravel()
    b = index[:-1, 1:].ravel()
    c = index[1:, :-1].ravel()
    d = index[1:, 1:].ravel()
    faces = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])
    mesh = mi.Mesh("face", vertex_count=nx * ny, face_count=len(faces), has_vertex_normals=True, has_vertex_texcoords=True)
    params = mi.traverse(mesh)
    params["vertex_positions"] = mi.Float(positions.astype(np.float32).ravel())
    params["vertex_normals"] = mi.Float(normals.reshape(-1, 3).astype(np.float32).ravel())
    params["vertex_texcoords"] = mi.Float(uvs.astype(np.float32).ravel())
    params["faces"] = mi.UInt32(faces.astype(np.uint32).ravel())
    params.update()
    return mesh, float(-z.min())


def chip_noise(rough, wu, wv, paint):
    octaves = paint.get("chip_octaves")
    if not octaves:
        tiling = float(paint["chip_tiling"])
        return sample(rough, wu * tiling, wv * tiling)
    total = 0.0
    for tiling, angle, offset in octaves:
        a = np.radians(float(angle))
        ru = (wu * np.cos(a) - wv * np.sin(a)) * float(tiling) + float(offset)
        rv = (wu * np.sin(a) + wv * np.cos(a)) * float(tiling) + float(offset) * 0.61
        total = total + sample(rough, ru, rv)
    noise = total / len(octaves)
    return (noise - noise.mean()) / max(float(noise.std()), 1e-6) * float(paint.get("chip_spread", 0.12)) + float(paint.get("chip_mean", 0.62))


def bake_maps(spec, root, mask, groove, fields=None):
    board, wood, carve, paint = spec["board"], spec["wood"], spec["groove"], spec["paint"]
    bw, bh = (int(n) for n in spec["bake_px"])
    u, v = grid(bw, bh)
    per = float(wood["metres_per_texture"])
    wu = u * float(board["width_m"]) / per
    wv = v * float(board["height_m"]) / per
    colour = srgb_to_linear(load_image(root / wood["color"])[..., :3])
    normal = load_image(root / wood["normal"])[..., :3]
    rough = load_image(root / wood["roughness"])
    rough = rough[..., 0] if rough.ndim == 3 else rough
    albedo = sample(colour, wu, wv) * np.array(wood["tint"], dtype=np.float32)
    grey = albedo @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    albedo = grey[..., None] + (albedo - grey[..., None]) * float(wood.get("saturation", 1.0))
    wood_rough = sample(rough, wu, wv) * float(wood["burnish_roughness"])
    here = clamp_sample(groove, u, v)
    sharp = clamp_sample(mask if fields is None else fields["letters"], u, v)
    in_groove = smoothstep(float(carve["from"]), float(carve["to"]), here)
    chips = chip_noise(rough, wu, wv, paint)
    wear = float(paint["wear"])
    if fields is not None and fields["distance"] is not None and float(paint.get("edge_wear", 0.0)) > 0:
        near = 1.0 - smoothstep(0.0, float(paint.get("edge_wear_px", 6.0)), clamp_sample(fields["distance"], u, v))
        wear = wear + float(paint["edge_wear"]) * near
    soft = float(paint["wear_softness"])
    coat = smoothstep(float(paint["floor_from"]), float(paint["floor_to"]), sharp) * smoothstep(-soft, soft, chips - wear)
    wood_albedo = albedo * (1.0 - (1.0 - float(carve["darkening"])) * in_groove)[..., None]
    if "cut_tint" in carve:
        wood_albedo = wood_albedo * (1.0 + (np.array(carve["cut_tint"], dtype=np.float32) - 1.0) * in_groove[..., None])
    paint_colour = np.array(paint["colour"], dtype=np.float32) * (0.85 + 0.15 * smoothstep(0.57, 0.68, chips))[..., None]
    final_albedo = wood_albedo * (1 - coat[..., None]) + paint_colour * coat[..., None]
    wood_r = wood_rough * (1 - in_groove) + float(carve["roughness"]) * in_groove
    final_rough = wood_r * (1 - coat) + float(paint["roughness"]) * coat
    n = sample(normal, wu, wv) * 2.0 - 1.0
    strength = float(wood["normal_strength"]) * (1 - coat * (1 - float(paint.get("normal_through", 0.0))))
    extras = {}
    if fields is not None and fields["regions"]:
        emission = np.zeros(final_albedo.shape, np.float32)
        for region in fields["regions"]:
            entry = region["entry"]
            floor = clamp_sample(region["floor"], u, v)
            if "albedo" in entry:
                final_albedo = final_albedo * (1 - floor[..., None]) + np.array(entry["albedo"], dtype=np.float32) * floor[..., None]
            if "roughness" in entry:
                final_rough = final_rough * (1 - floor) + float(entry["roughness"]) * floor
            strength = strength * (1 - floor * float(entry.get("flatten_normal", 1.0)))
            if "emission" in entry:
                du = (u - region["centre"][0]) / max(region["extent"][0], 1e-6)
                dv = (v - region["centre"][1] - float(entry.get("emission_centre_shift", 0.0)) * region["extent"][1]) / max(region["extent"][1], 1e-6)
                glow = np.clip(1.0 - float(entry.get("emission_falloff", 0.0)) * (du * du + dv * dv), 0.0, 1.0)
                emission += np.array(entry["emission"], dtype=np.float32) * (floor * glow)[..., None]
        extras["emission"] = emission
    if "clearcoat" in wood:
        clear = float(wood["clearcoat"]) * (1 - coat) * (1 - in_groove)
        if fields is not None:
            for region in fields["regions"]:
                clear = clear * (1 - clamp_sample(region["floor"], u, v))
        extras["clearcoat"] = clear.astype(np.float32)
    n[..., 0] *= strength
    n[..., 1] *= strength
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    maps = (final_albedo.astype(np.float32), final_rough.astype(np.float32), (n * 0.5 + 0.5).astype(np.float32))
    return maps if fields is None else maps + (extras,)


def bake_backdrop(spec, root):
    backdrop, wood = spec["backdrop"], spec["wood"]
    bw, bh = (int(n) for n in backdrop["bake_px"])
    u, v = grid(bw, bh)
    width, height = (float(n) for n in backdrop["size_m"])
    per = float(backdrop.get("metres_per_texture", wood["metres_per_texture"]))
    ym = v * height
    plank = float(backdrop.get("plank_m", 0.0))
    index = np.floor(ym / plank) if plank > 0 else np.zeros_like(ym)
    wu = u * width / per + index * 0.618
    wv = ym / per + index * 0.29
    colour = srgb_to_linear(load_image(root / wood["color"])[..., :3])
    rough = load_image(root / wood["roughness"])
    rough = rough[..., 0] if rough.ndim == 3 else rough
    albedo = sample(colour, wu, wv) * np.array(backdrop["tint"], dtype=np.float32)
    grey = albedo @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    albedo = grey[..., None] + (albedo - grey[..., None]) * float(backdrop.get("saturation", 1.0))
    variation = float(backdrop.get("plank_variation", 0.0))
    albedo = albedo * (1.0 + variation * 0.5 * np.sin(index * 12.9898))[..., None]
    if plank > 0:
        gap = float(backdrop.get("seam_m", 0.004))
        within = ym - index * plank
        seam = 1.0 - smoothstep(0.0, gap, np.minimum(within, plank - within))
        albedo = albedo * (1.0 - float(backdrop.get("seam_darkening", 0.8)) * seam)[..., None]
    roughness = np.clip(sample(rough, wu, wv) * float(backdrop.get("roughness_scale", 1.0)), 0.05, 1.0)
    return {"albedo": albedo.astype(np.float32), "roughness": roughness.astype(np.float32)}


def bitmap(array):
    return {"type": "bitmap", "bitmap": mi.Bitmap(np.ascontiguousarray(array)), "raw": True, "filter_type": "bilinear"}


def look_at(entry):
    return mi.ScalarTransform4f().look_at(origin=entry["position"], target=entry["look_at"], up=entry.get("up", [0, 1, 0]))


def face_bsdf(spec, albedo, roughness, normal, extras=None):
    inner = {"type": "principled", "base_color": bitmap(albedo), "roughness": bitmap(roughness[..., None]), "specular": float(spec["wood"].get("specular", 0.5))}
    if extras and "clearcoat" in extras:
        inner["clearcoat"] = bitmap(extras["clearcoat"][..., None])
        inner["clearcoat_gloss"] = float(spec["wood"].get("clearcoat_gloss", 0.8))
    return {"type": "normalmap", "normalmap": bitmap(normal), "bsdf": inner}


def light_at(light, t):
    entry = dict(light)
    if "look_at_to" in light:
        eased = t if light.get("easing", "linear") == "linear" else t * t * (3 - 2 * t)
        entry["look_at"] = [a + (b - a) * eased for a, b in zip(light["look_at"], light["look_at_to"])]
    return entry


def light_dict(light, t):
    entry = light_at(light, t)
    if light.get("type", "rect") == "spot":
        return {
            "type": "spot",
            "to_world": look_at(entry),
            "intensity": {"type": "rgb", "value": light["intensity"]},
            "cutoff_angle": float(light["cutoff_angle"]),
            "beam_width": float(light["beam_width"]),
        }
    half = [light["size"][0] / 2, light["size"][1] / 2, 1]
    return {
        "type": "rectangle",
        "to_world": look_at(entry) @ mi.ScalarTransform4f().scale(half),
        "emitter": {"type": "area", "radiance": {"type": "rgb", "value": light["radiance"]}},
    }


def post_process(image, post):
    height, width = image.shape[:2]
    bloom = post.get("bloom")
    if bloom:
        bright = np.maximum(image - float(bloom["threshold"]), 0.0)
        glow = np.zeros_like(image)
        for radius, weight in bloom["layers"]:
            r = max(float(radius) * width / 3840.0, 1.0)
            glow += float(weight) * np.stack([soft_blur(bright[..., c], r) for c in range(3)], axis=-1)
        image = image + float(bloom.get("strength", 1.0)) * glow
    vignette = float(post.get("vignette", 0.0))
    if vignette > 0:
        u, v = grid(width, height)
        r2 = ((u - 0.5) * 2) ** 2 * 0.6 + ((v - 0.5) * 2) ** 2 * 0.4
        image = image * np.clip(1.0 - vignette * r2, 0.0, 1.0)[..., None]
    return np.maximum(image, 0.0)


def tonemap(image, exposure, post=None):
    image = image * exposure
    if post:
        image = post_process(image, post)
    return (linear_to_srgb(filmic(image)) * 255.0 + 0.5).astype(np.uint8)


def build_scene(spec, face_path, face_material, width, height, spp, at=0.0, face_bottom=None, emission=None, backdrop=None):
    board, cam = spec["board"], spec["camera"]
    depth = float(spec["carve"]["depth_m"]) if face_bottom is None else max(float(spec["carve"]["depth_m"]), face_bottom)
    thickness = float(board["thickness_m"])
    body_tint = np.array(spec["wood"]["tint"], dtype=np.float32) * float(spec["wood"].get("body_shade", 0.25))
    sensor = {
        "type": "thinlens" if float(cam.get("aperture_radius", 0)) > 0 else "perspective",
        "fov": float(cam["fov"]),
        "fov_axis": "y",
        "to_world": look_at(cam),
        "film": {"type": "hdrfilm", "width": width, "height": height, "rfilter": {"type": "gaussian"}},
        "sampler": {"type": "independent", "sample_count": spp},
    }
    if sensor["type"] == "thinlens":
        sensor["aperture_radius"] = float(cam["aperture_radius"])
        sensor["focus_distance"] = float(cam["focus_distance"])
    scene = {
        "type": "scene",
        "integrator": {"type": "path", "max_depth": int(spec["render"].get("max_depth", 8))},
        "sensor": sensor,
        "face": {"type": "ply", "filename": str(face_path), "face_normals": False, "bsdf": face_material},
        "body": {
            "type": "cube",
            "to_world": mi.ScalarTransform4f().translate([0, 0, -depth - 0.002 - thickness / 2]).scale([float(board["width_m"]) / 2, float(board["height_m"]) / 2, thickness / 2]),
            "bsdf": {"type": "principled", "base_color": {"type": "rgb", "value": body_tint.tolist()}, "roughness": 0.6},
        },
        "ambient": {"type": "constant", "radiance": {"type": "rgb", "value": spec["ambient"]}},
    }
    if emission is not None and float(emission.max()) > 0:
        scene["face"]["emitter"] = {"type": "area", "radiance": bitmap(emission)}
    if backdrop is not None:
        entry = spec["backdrop"]
        w, h = (float(n) for n in entry["size_m"])
        z = -depth - 0.002 - thickness - float(entry.get("gap_m", 0.0))
        centre = entry.get("centre_m", [0.0, 0.0])
        scene["backdrop"] = {
            "type": "rectangle",
            "to_world": mi.ScalarTransform4f().translate([float(centre[0]), float(centre[1]), z]).scale([w / 2, h / 2, 1]),
            "bsdf": {"type": "principled", "base_color": bitmap(backdrop["albedo"]), "roughness": bitmap(backdrop["roughness"][..., None]), "specular": float(entry.get("specular", 0.4))},
        }
    for i, light in enumerate(spec["lights"]):
        scene[f"light_{i}"] = light_dict(light, at)
    return scene


def main():
    parser = argparse.ArgumentParser(description="Render a carved, painted relief board headless with Mitsuba 3.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--mask", required=True, help="greyscale PNG, white where the board is cut")
    parser.add_argument("--out", required=True)
    parser.add_argument("--root", default=".", help="folder the spec's texture paths are relative to")
    parser.add_argument("--scale", type=float, default=1.0, help="multiply the output size, e.g. 0.25 for a preview")
    parser.add_argument("--spp", type=int, default=0)
    parser.add_argument("--variant", default="")
    parser.add_argument("--frames", type=int, default=0, help="override the spec's frame count; above 1, --out is a folder of frame_NNNN.png")
    parser.add_argument("--at", type=float, default=0.0, help="for a single frame, how far along its sweep each moving light is, 0 to 1")
    parser.add_argument("--frame-range", default="", help="python slice of frames to render, e.g. 0:72:12 for a preview")
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    render = spec["render"]
    mi.set_variant(args.variant or render.get("variant", "cuda_ad_rgb"))
    started = time.time()
    mask = load_image(args.mask)
    mask = mask[..., 0] if mask.ndim == 3 else mask
    fields = relief_fields(mask, spec)
    groove = fields["groove"]
    face, face_bottom = build_face(spec["board"], spec["carve"], groove, fields["depth"])
    albedo, roughness, normal, extras = bake_maps(spec, Path(args.root), mask, groove, fields)
    backdrop = bake_backdrop(spec, Path(args.root)) if "backdrop" in spec else None
    face_path = Path(args.out).with_suffix(".face.ply")
    face_path.parent.mkdir(parents=True, exist_ok=True)
    face.write_ply(str(face_path))
    width = int(round(int(render["width"]) * args.scale))
    height = int(round(int(render["height"]) * args.scale))
    material = face_bsdf(spec, albedo, roughness, normal, extras)
    scene_dict = build_scene(spec, face_path, material, width, height, args.spp or int(render["spp"]), args.at, face_bottom, extras.get("emission"), backdrop)
    built = time.time()
    scene = mi.load_dict(scene_dict)
    face_path.unlink()
    exposure = float(render.get("exposure", 1.0))
    post = render.get("post")
    frames = int(args.frames or render.get("frames", 1))
    if frames == 1:
        image = np.array(mi.render(scene), dtype=np.float32)[..., :3]
        mi.Bitmap(tonemap(image, exposure, post), pixel_format=mi.Bitmap.PixelFormat.RGB).write(args.out)
        print(f"{args.out} {width}x{height} build {built - started:.1f}s render {time.time() - built:.1f}s")
        return
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    params = mi.traverse(scene)
    moving = [i for i, light in enumerate(spec["lights"]) if light.get("type") == "spot" and "look_at_to" in light]
    chosen = range(frames)[slice(*[int(x) if x else None for x in args.frame_range.split(":")])] if args.frame_range else range(frames)
    for frame in chosen:
        t = frame / (frames - 1)
        for i in moving:
            params[f"light_{i}.to_world"] = look_at(light_at(spec["lights"][i], t))
        params.update()
        image = np.array(mi.render(scene, params, seed=0), dtype=np.float32)[..., :3]
        mi.Bitmap(tonemap(image, exposure, post), pixel_format=mi.Bitmap.PixelFormat.RGB).write(str(folder / f"frame_{frame:04d}.png"))
    print(f"{folder} {len(chosen)} frames {width}x{height} build {built - started:.1f}s render {time.time() - built:.1f}s")


if __name__ == "__main__":
    main()
