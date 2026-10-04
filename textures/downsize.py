import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="Downsize texture images to the caps in a texture_budget spec, renormalizing normal maps.")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True, help="folder of exported images")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def cap_for(name, spec):
    for rule in spec["max_size_rules"]:
        if rule["contains"] in name:
            return rule["max_size"]
    return spec["default_max_size"]


def kind_for(name, spec):
    return next((kind for kind, suffix in spec["suffixes"].items() if name.endswith(suffix)), "color")


def renormalize(image):
    pixels = np.asarray(image.convert("RGB"), dtype=np.float32) / 127.5 - 1.0
    length = np.linalg.norm(pixels, axis=2, keepdims=True)
    pixels = pixels / np.maximum(length, 1e-6)
    return Image.fromarray(np.clip((pixels + 1.0) * 127.5 + 0.5, 0, 255).astype(np.uint8), "RGB")


def main():
    args = parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    for path in sorted(args.source.glob("*.png")):
        name = path.stem
        cap = cap_for(name, spec)
        kind = kind_for(name, spec)
        with Image.open(path) as image:
            width, height = image.size
            scale = min(1.0, cap / max(width, height))
            size = (max(1, round(width * scale)), max(1, round(height * scale)))
            result = image.resize(size, Image.LANCZOS) if scale < 1.0 else image.copy()
            if kind == "normal" and scale < 1.0:
                result = renormalize(result)
            result.save(args.out / path.name)
        print(f"{name}: {width}x{height} -> {size[0]}x{size[1]} {kind}")


if __name__ == "__main__":
    main()
