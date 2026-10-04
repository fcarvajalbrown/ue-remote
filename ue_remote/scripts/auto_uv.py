import unreal

if not hasattr(unreal, "GeometryScript_MeshUVFunctions"):
    raise SystemExit("enable the Geometry Scripting plugin in this project and restart the editor; nothing changed")

library = unreal.EditorAssetLibrary
assets = unreal.GeometryScript_AssetFunctions
uvs = unreal.GeometryScript_MeshUVFunctions

def find(owner, *parts):
    names = [name for name in dir(owner) if all(part in name for part in parts)]
    if len(names) != 1:
        raise SystemExit(f"expected one function matching {parts} on {owner.__name__}, found {names}")
    return getattr(owner, names[0])


auto_xatlas = find(uvs, "auto_generate", "atlas")
auto_patch = find(uvs, "auto_generate", "patch")
repack = find(uvs, "repack")

method = ARGS.get("method", ["xatlas"])[0]
channel = int(ARGS.get("channel", ["0"])[0])
dry_run = ARGS.get("dry_run", ["1"])[0] != "0"

paths = []
for entry in ARGS.get("path", []) + ARGS.get("asset", []):
    if library.does_directory_exist(entry):
        paths += library.list_assets(entry, recursive=True, include_folder=False)
    else:
        paths.append(entry)

meshes = [library.load_asset(path.split(".")[0]) for path in paths]
meshes = [mesh for mesh in meshes if isinstance(mesh, unreal.StaticMesh)]
print(f"{len(meshes)} static meshes, method {method}, UV channel {channel}, dry_run={dry_run}")

read_options = unreal.GeometryScriptCopyMeshFromAssetOptions()
write_options = unreal.GeometryScriptCopyMeshToAssetOptions()
write_options.set_editor_property("replace_materials", False)
lod = unreal.GeometryScriptMeshReadLOD()
write_lod = unreal.GeometryScriptMeshWriteLOD()

for mesh in meshes:
    path = mesh.get_path_name().split(".")[0]
    if dry_run:
        print(f"would auto-UV {path}")
        continue

    dynamic = unreal.DynamicMesh()
    dynamic, outcome = assets.copy_mesh_from_static_mesh(mesh, dynamic, read_options, lod)
    if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
        print(f"skip {path}: could not read mesh")
        continue

    if method == "patch":
        dynamic = auto_patch(dynamic, channel, unreal.GeometryScriptPatchBuilderOptions())
    else:
        dynamic = auto_xatlas(dynamic, channel, unreal.GeometryScriptXAtlasOptions())
    dynamic = repack(dynamic, channel, unreal.GeometryScriptRepackUVsOptions())

    dynamic, outcome = assets.copy_mesh_to_static_mesh(dynamic, mesh, write_options, write_lod)
    if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
        print(f"failed {path}: could not write mesh")
        continue
    print(f"{path}: auto-UV done, saved={library.save_asset(path, only_if_is_dirty=False)}")
