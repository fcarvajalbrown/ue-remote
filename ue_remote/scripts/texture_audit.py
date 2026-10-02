import unreal

roots = ARGS.get("path", ["/Game"])

rows = []
for root in roots:
    for path in unreal.EditorAssetLibrary.list_assets(root, recursive=True):
        data = unreal.EditorAssetLibrary.find_asset_data(path)
        if data.asset_class_path.asset_name != "Texture2D":
            continue
        texture = data.get_asset()
        width = texture.blueprint_get_size_x()
        height = texture.blueprint_get_size_y()
        compression = texture.get_editor_property("compression_settings")
        srgb = texture.get_editor_property("srgb")
        max_size = texture.get_editor_property("max_texture_size")
        lod_group = texture.get_editor_property("lod_group")
        rows.append((width * height, path.split(".")[0], width, height, compression, srgb, max_size, lod_group))

for _, path, width, height, compression, srgb, max_size, lod_group in sorted(rows, reverse=True):
    print(f"{width:>5}x{height:<5} {compression.name:24} srgb={srgb!s:5} max={max_size:<5} {lod_group.name:30} {path}")
print(f"{len(rows)} textures")
