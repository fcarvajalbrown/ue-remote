import argparse
import json
from pathlib import Path

import numpy as np

import layout
import meshkit as mk
import parts
import terrain
import trees as treekit


def load(spec_dir, name):
    return json.loads((spec_dir / f"{name}.json").read_text(encoding="utf-8"))


def piece_mesh(name, pieces_spec, tree_pieces, tree_specs, lod):
    merged = mk.Mesh()
    if name in tree_pieces:
        for group in treekit.build_tree(tree_specs[tree_pieces[name]], lod).values():
            merged.include(group)
        return merged
    for group in parts.build_piece(pieces_spec[name]).values():
        merged.include(group)
    return merged


def main():
    parser = argparse.ArgumentParser(description="Merged preview GLB of selected placements, to open in any viewer.")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--folder", action="append", default=[], help="row folder suffix, for example House")
    parser.add_argument("--skip", default="", help="comma separated piece names to leave out")
    parser.add_argument("--tree", help="preview one tree stage on its own")
    parser.add_argument("--lod", type=int, default=0)
    parser.add_argument("--radius", type=float, help="only rows within this distance of the origin")
    parser.add_argument("--ground", action="store_true", help="include the terrain and paths")
    args = parser.parse_args()

    pieces_spec = load(args.spec, "pieces")
    buildings = load(args.spec, "buildings")
    tree_specs = load(args.spec, "trees")
    world = load(args.spec, "world")
    pieces_spec.update(layout.wall_pieces(buildings))
    prefix = world["forest"].get("piece_prefix", "tree")
    tree_pieces = {f"{prefix}_{stage}": stage for stage in tree_specs}
    scene = mk.Mesh()

    if args.tree:
        scene.include(piece_mesh(f"{prefix}_{args.tree}", pieces_spec, tree_pieces, tree_specs, args.lod))
    else:
        ground = terrain.Ground(world)
        rows = layout.building_rows(world, ground, buildings) + layout.prop_rows(world, ground) + layout.fence_rows(world, ground) + layout.tree_rows(world, ground)
        cache, skipped = {}, set(args.skip.split(","))
        for row in rows:
            if args.folder and not any(row["folder"].endswith(f) for f in args.folder):
                continue
            if row["piece"] in skipped:
                continue
            if args.radius and np.hypot(row["x"], row["y"]) > args.radius:
                continue
            if row["piece"] not in cache:
                cache[row["piece"]] = piece_mesh(row["piece"], pieces_spec, tree_pieces, tree_specs, args.lod)
            stretched = np.diag([row["scale_x"] * row["scale"], row["scale"], row["scale"]])
            scene.include(cache[row["piece"]], mk.rotation_z(np.radians(row["yaw"])) @ stretched, (row["x"], row["y"], row["z"]))
        if args.ground:
            scene.include(terrain.terrain_mesh(ground))
            scene.include(terrain.paths_mesh(ground, world))

    mk.write_glb(scene, args.out)
    print(f"{scene.triangle_count()} tris -> {args.out}")


if __name__ == "__main__":
    main()
