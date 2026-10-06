import argparse
from pathlib import Path

import trimesh


def main():
    parser = argparse.ArgumentParser(description="Combine a part set of GLBs into one GLB for a model check render (F3D), keeping each part as its own node; parts whose name contains any --skip word are left out.")
    parser.add_argument("parts", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--skip", nargs="*", default=[])
    args = parser.parse_args()
    scene = trimesh.Scene()
    for path in sorted(args.parts):
        if any(word in path.stem for word in args.skip):
            continue
        for name, geometry in trimesh.load(path, force="scene").geometry.items():
            scene.add_geometry(geometry, geom_name=f"{path.stem}_{name}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    scene.export(args.out)
    print(args.out, len(scene.geometry))


if __name__ == "__main__":
    main()
