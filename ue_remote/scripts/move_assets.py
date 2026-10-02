import unreal

library = unreal.EditorAssetLibrary
destination = ARGS["destination"][0].rstrip("/")
strip_suffix = ARGS.get("strip_suffix", [""])[0]

renames = []
for path in ARGS["asset"]:
    package = path.split(".")[0]
    asset = library.load_asset(package)
    if not asset:
        raise SystemExit(f"asset not found: {package}")
    name = package.rsplit("/", 1)[1]
    if strip_suffix and name.endswith(strip_suffix):
        name = name[: -len(strip_suffix)]
    if library.does_asset_exist(f"{destination}/{name}"):
        raise SystemExit(f"{destination}/{name} already exists; nothing moved")
    renames.append(unreal.AssetRenameData(asset, destination, name))

if not unreal.AssetToolsHelpers.get_asset_tools().rename_assets(renames):
    raise SystemExit("rename_assets reported failure")

for data in renames:
    moved = f"{destination}/{data.get_editor_property('new_name')}"
    print(f"{moved}: saved={library.save_asset(moved, only_if_is_dirty=False)}")
