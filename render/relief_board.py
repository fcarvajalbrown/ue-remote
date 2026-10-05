import argparse
import json
import time
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


def build_face(board, carve, groove):
    nx, ny = (int(n) for n in board["mesh_px"])
    u, v = grid(nx, ny)
    depth = clamp_sample(groove, u, v) * float(carve["depth_m"])
    width, height = float(board["width_m"]), float(board["height_m"])
    x = (u - 0.5) * width
    y = (0.5 - v) * height
    z = -depth
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
    return mesh


def bake_maps(spec, root, mask, groove):
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
    sharp = clamp_sample(mask, u, v)
    in_groove = smoothstep(float(carve["from"]), float(carve["to"]), here)
    tiling = float(paint["chip_tiling"])
    chips = sample(rough, wu * tiling, wv * tiling)
    wear = float(paint["wear"])
    soft = float(paint["wear_softness"])
    coat = smoothstep(float(paint["floor_from"]), float(paint["floor_to"]), sharp) * smoothstep(wear - soft, wear + soft, chips)
    wood_albedo = albedo * (1.0 - (1.0 - float(carve["darkening"])) * in_groove)[..., None]
    paint_colour = np.array(paint["colour"], dtype=np.float32) * (0.85 + 0.15 * smoothstep(0.57, 0.68, chips))[..., None]
    final_albedo = wood_albedo * (1 - coat[..., None]) + paint_colour * coat[..., None]
    wood_r = wood_rough * (1 - in_groove) + float(carve["roughness"]) * in_groove
    final_rough = wood_r * (1 - coat) + float(paint["roughness"]) * coat
    n = sample(normal, wu, wv) * 2.0 - 1.0
    strength = float(wood["normal_strength"]) * (1 - coat)
    n[..., 0] *= strength
    n[..., 1] *= strength
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return final_albedo.astype(np.float32), final_rough.astype(np.float32), (n * 0.5 + 0.5).astype(np.float32)


def bitmap(array):
    return {"type": "bitmap", "bitmap": mi.Bitmap(np.ascontiguousarray(array)), "raw": True, "filter_type": "bilinear"}


def look_at(entry):
    return mi.ScalarTransform4f().look_at(origin=entry["position"], target=entry["look_at"], up=entry.get("up", [0, 1, 0]))


def face_bsdf(spec, albedo, roughness, normal):
    return {
        "type": "normalmap",
        "normalmap": bitmap(normal),
        "bsdf": {"type": "principled", "base_color": bitmap(albedo), "roughness": bitmap(roughness[..., None]), "specular": float(spec["wood"].get("specular", 0.5))},
    }


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


def tonemap(image, exposure):
    return (linear_to_srgb(filmic(image * exposure)) * 255.0 + 0.5).astype(np.uint8)


def build_scene(spec, face_path, face_material, width, height, spp):
    board, cam = spec["board"], spec["camera"]
    depth = float(spec["carve"]["depth_m"])
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
    for i, light in enumerate(spec["lights"]):
        scene[f"light_{i}"] = light_dict(light, 0.0)
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
    parser.add_argument("--frame-range", default="", help="python slice of frames to render, e.g. 0:72:12 for a preview")
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    render = spec["render"]
    mi.set_variant(args.variant or render.get("variant", "cuda_ad_rgb"))
    started = time.time()
    mask = load_image(args.mask)
    mask = mask[..., 0] if mask.ndim == 3 else mask
    groove = carve_fields(mask, spec["carve"])
    face = build_face(spec["board"], spec["carve"], groove)
    albedo, roughness, normal = bake_maps(spec, Path(args.root), mask, groove)
    face_path = Path(args.out).with_suffix(".face.ply")
    face_path.parent.mkdir(parents=True, exist_ok=True)
    face.write_ply(str(face_path))
    width = int(round(int(render["width"]) * args.scale))
    height = int(round(int(render["height"]) * args.scale))
    scene_dict = build_scene(spec, face_path, face_bsdf(spec, albedo, roughness, normal), width, height, args.spp or int(render["spp"]))
    built = time.time()
    scene = mi.load_dict(scene_dict)
    face_path.unlink()
    exposure = float(render.get("exposure", 1.0))
    frames = int(args.frames or render.get("frames", 1))
    if frames == 1:
        image = np.array(mi.render(scene), dtype=np.float32)[..., :3]
        mi.Bitmap(tonemap(image, exposure), pixel_format=mi.Bitmap.PixelFormat.RGB).write(args.out)
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
        mi.Bitmap(tonemap(image, exposure), pixel_format=mi.Bitmap.PixelFormat.RGB).write(str(folder / f"frame_{frame:04d}.png"))
    print(f"{folder} {len(chosen)} frames {width}x{height} build {built - started:.1f}s render {time.time() - built:.1f}s")


if __name__ == "__main__":
    main()
