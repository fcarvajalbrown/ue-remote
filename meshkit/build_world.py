import argparse
import csv
import fnmatch
import json
from pathlib import Path

import layout
import meshkit as mk
import parts
import terrain
import trees as treekit

CM = 100.0
CROWN_GROUPS = {"crown"}
TREE_GROUPS = ("trunk", "crown")


def load(spec_dir, name):
    return json.loads((spec_dir / f"{name}.json").read_text(encoding="utf-8"))


def pascal(text):
    return "".join(part.capitalize() for part in text.split("_"))


def folder_for(piece, content):
    for rule in content["folders"]:
        if fnmatch.fnmatch(piece, rule["match"]):
            return rule["folder"]
    return content.get("default_folder", "Props")


def mesh_entry(content, name, files, mesh, collision, instance, piece):
    return {
        "name": name, "asset": f"{content['mesh_prefix']}{pascal(name)}", "folder": folder_for(piece, content), "files": files,
        "collision": collision, "instance": instance, "piece": piece, "materials": sorted(mesh.merged().keys()), "triangles": mesh.triangle_count(),
    }


def write_mesh(out, content, entries, name, mesh, piece, collision, instance):
    mk.write_glb(mesh, out / "meshes" / f"{name}.glb")
    entries[name] = mesh_entry(content, name, [f"meshes/{name}.glb"], mesh, collision, instance, piece)


def build_pieces(out, content, pieces_spec, meshes, piece_meshes):
    for piece, spec in pieces_spec.items():
        piece_meshes[piece] = []
        for group, mesh in parts.build_piece(spec).items():
            name = piece if group == "main" else f"{piece}_{group}"
            write_mesh(out, content, meshes, name, mesh, piece, spec.get("collision", "complex"), spec.get("instance", False))
            piece_meshes[piece].append(name)


def build_trees(out, content, tree_specs, prefix, meshes, piece_meshes):
    for stage, spec in tree_specs.items():
        piece = f"{prefix}_{stage}"
        lod_meshes = [treekit.build_tree(spec, index) for index in range(len(spec["lods"]))]
        piece_meshes[piece] = []
        for group in TREE_GROUPS:
            name = f"{piece}_{group}"
            files = []
            for index, lod in enumerate(lod_meshes):
                lod_name = f"{name}_lod{index}"
                mk.write_glb(lod[group], out / "meshes" / f"{lod_name}.glb")
                files.append(f"meshes/{lod_name}.glb")
            entry = mesh_entry(content, name, files, lod_meshes[0][group], "none" if group in CROWN_GROUPS else "complex", True, piece)
            entry["lod_triangles"] = [lod[group].triangle_count() for lod in lod_meshes]
            meshes[name] = entry
            piece_meshes[piece].append(name)


def build_all(spec_dir, out, seed_override=None):
    (out / "meshes").mkdir(parents=True, exist_ok=True)
    content = load(spec_dir, "content")
    pieces_spec = load(spec_dir, "pieces")
    buildings = load(spec_dir, "buildings")
    tree_specs = load(spec_dir, "trees")
    world = load(spec_dir, "world")
    if seed_override is not None:
        world["forest"]["seed"] = seed_override
    pieces_spec.update(layout.wall_pieces(buildings))

    meshes, piece_meshes = {}, {}
    build_pieces(out, content, pieces_spec, meshes, piece_meshes)
    build_trees(out, content, tree_specs, world["forest"].get("piece_prefix", "tree"), meshes, piece_meshes)

    ground = terrain.Ground(world)
    write_mesh(out, content, meshes, "terrain", terrain.terrain_mesh(ground), "terrain", "complex", False)
    write_mesh(out, content, meshes, "paths", terrain.paths_mesh(ground, world), "paths", "none", False)
    piece_meshes["terrain"] = ["terrain"]
    piece_meshes["paths"] = ["paths"]

    rows = layout.building_rows(world, ground, buildings) + layout.prop_rows(world, ground) + layout.fence_rows(world, ground) + layout.tree_rows(world, ground)
    for row in rows:
        row["instance"] = meshes[piece_meshes[row["piece"]][0]]["instance"]
    return {"meshes": meshes, "pieces": piece_meshes, "rows": rows, "world": world, "content": content}


def write_layout(out, rows):
    columns = ("piece", "x_cm", "y_cm", "z_cm", "yaw_deg", "scale", "scale_x", "folder", "instance")
    with (out / "layout.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([
                row["piece"], round(row["x"] * CM, 1), round(-row["y"] * CM, 1), round(row["z"] * CM, 1),
                round(-row["yaw"] + 0.0, 2) + 0.0, round(row["scale"], 4), round(row["scale_x"], 4), row["folder"], int(row["instance"]),
            ])


def main():
    parser = argparse.ArgumentParser(description="Build GLB meshes, a placement table and a manifest from a folder of JSON specs.")
    parser.add_argument("--spec", required=True, type=Path, help="folder with pieces, buildings, trees, world and content JSON")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    built = build_all(args.spec, args.out, args.seed)
    write_layout(args.out, built["rows"])
    manifest = {"meshes": built["meshes"], "pieces": built["pieces"], "world": built["world"], "content": built["content"]}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    for name, entry in sorted(built["meshes"].items(), key=lambda item: -item[1]["triangles"]):
        extra = f" lods {entry['lod_triangles']}" if "lod_triangles" in entry else ""
        print(f"{name:34s} {entry['triangles']:7d} tris  {entry['collision']:8s}{extra}")
    counts = {}
    for row in built["rows"]:
        counts[row["piece"]] = counts.get(row["piece"], 0) + 1
    print(f"{len(built['rows'])} placements: {counts}")


if __name__ == "__main__":
    main()
