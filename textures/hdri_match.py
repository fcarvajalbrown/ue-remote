import argparse
import io
import json
import urllib.request

import numpy as np
from PIL import Image

API = "https://api.polyhaven.com/assets?t=hdris&c={category}"
THUMB = "https://cdn.polyhaven.com/asset_img/primary/{asset}.png?height=256"
AGENT = {"User-Agent": "ue-remote-hdri-match"}


def parse_args():
    parser = argparse.ArgumentParser(description="Rank Poly Haven HDRIs by how close their sky is to the sky in a reference image.")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--sky-fraction", type=float, default=0.4, help="top share of the reference image that is sky")
    parser.add_argument("--category", default="overcast")
    parser.add_argument("--require", default="pure skies", help="category every candidate must also have; empty for none")
    parser.add_argument("--top", type=int, default=10)
    return parser.parse_args()


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=30) as response:
        return response.read()


def stats(image):
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    saturation = rgb.max(axis=2) - rgb.min(axis=2)
    return np.array([luma.mean(), luma.std(), saturation.mean(), (rgb[..., 2] - rgb[..., 0]).mean()])


def main():
    args = parse_args()
    reference = Image.open(args.reference)
    width, height = reference.size
    target = stats(reference.crop((0, 0, width, int(height * args.sky_fraction))))
    assets = json.loads(fetch(API.format(category=args.category)))
    rows = []
    for asset, info in assets.items():
        if args.require and args.require not in info.get("categories", []):
            continue
        thumb = Image.open(io.BytesIO(fetch(THUMB.format(asset=asset))))
        tw, th = thumb.size
        sky = stats(thumb.crop((0, 0, tw, th // 2)))
        rows.append((float(np.abs(sky - target).sum()), asset, info["name"], sky))
    print(f"reference sky: mean luma {target[0]:.3f} contrast {target[1]:.3f} saturation {target[2]:.3f} blue-red {target[3]:+.3f}")
    for distance, asset, name, sky in sorted(rows)[: args.top]:
        print(f"{distance:.3f} {asset} | {name} | luma {sky[0]:.3f} contrast {sky[1]:.3f} saturation {sky[2]:.3f} blue-red {sky[3]:+.3f}")


if __name__ == "__main__":
    main()
