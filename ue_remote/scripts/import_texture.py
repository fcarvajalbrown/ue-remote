import unreal

source = ARGS["file"][0]
folder = ARGS["folder"][0].rstrip("/")
name = ARGS["name"][0]

task = unreal.AssetImportTask()
task.filename = source
task.destination_path = folder
task.destination_name = name
task.replace_existing = True
task.automated = True
task.save = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
for path in task.imported_object_paths:
    asset = unreal.EditorAssetLibrary.load_asset(path)
    print(f"{path}: {type(asset).__name__} {asset.blueprint_get_size_x()}x{asset.blueprint_get_size_y()}" if hasattr(asset, "blueprint_get_size_x") else f"{path}: {type(asset).__name__}")
if not task.imported_object_paths:
    raise SystemExit(f"nothing imported from {source}")
