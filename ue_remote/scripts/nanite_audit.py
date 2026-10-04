import unreal

root = ARGS.get("path", ["/Game"])[0]
apply = ARGS.get("apply", ["0"])[0] == "1"
registry = unreal.AssetRegistryHelpers.get_asset_registry()
flagged = 0
total = 0
for data in registry.get_assets_by_path(root, recursive=True):
    if str(data.asset_class_path.asset_name) != "StaticMesh":
        continue
    total += 1
    mesh = unreal.EditorAssetLibrary.load_asset(str(data.get_asset().get_path_name()))
    settings = mesh.get_editor_property("nanite_settings")
    enabled = settings.get_editor_property("enabled")
    if enabled and apply:
        settings.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", settings)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        enabled = mesh.get_editor_property("nanite_settings").get_editor_property("enabled")
    if enabled:
        flagged += 1
    print(("NANITE " if enabled else "off    ") + str(data.get_asset().get_path_name()))
print(f"{flagged} of {total} static meshes have Nanite enabled under {root}")
