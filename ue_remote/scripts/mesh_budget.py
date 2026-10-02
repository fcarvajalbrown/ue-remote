import unreal

roots = ARGS.get("path", ["/Game"])
mesh_subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)

rows = []
for root in roots:
    for path in unreal.EditorAssetLibrary.list_assets(root, recursive=True):
        data = unreal.EditorAssetLibrary.find_asset_data(path)
        if data.asset_class_path.asset_name != "StaticMesh":
            continue
        mesh = data.get_asset()
        lods = mesh_subsystem.get_lod_count(mesh)
        triangles = [mesh.get_num_triangles(lod) for lod in range(lods)]
        nanite = mesh.get_editor_property("nanite_settings").get_editor_property("enabled")
        rows.append((triangles[0] if triangles else 0, path.split(".")[0], lods, triangles, nanite))

for lod0, path, lods, triangles, nanite in sorted(rows, reverse=True):
    print(f"{lod0:>9,} tris  {lods} LODs {triangles}  nanite={nanite}  {path}")
print(f"{len(rows)} static meshes, {sum(r[0] for r in rows):,} LOD0 triangles total")
