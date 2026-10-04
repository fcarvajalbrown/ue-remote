import unreal

root = ARGS.get("path", ["/Game"])[0]
old = ARGS["old"][0]
new = ARGS["new"][0]
apply = ARGS.get("apply", ["0"])[0] == "1"

registry = unreal.AssetRegistryHelpers.get_asset_registry()
for data in registry.get_assets_by_path(root, recursive=True):
    if str(data.asset_class_path.asset_name) != "FileMediaSource":
        continue
    source = data.get_asset()
    current = source.get_editor_property("file_path")
    if not current.startswith(old):
        print(f"{data.package_name} kept {current}")
        continue
    target = new + current[len(old):]
    if apply:
        source.set_file_path(target)
        unreal.EditorAssetLibrary.save_loaded_asset(source, only_if_is_dirty=False)
    print(f"{data.package_name} {current} -> {target} applied {apply}")
