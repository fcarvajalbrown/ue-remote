import os

import unreal

source = ARGS["source"][0]
folder = ARGS["folder"][0].rstrip("/")
apply = ARGS.get("apply", ["0"])[0] == "1"

library = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
files = sorted(f for f in os.listdir(source) if f.lower().endswith(".png"))
missing = [f for f in files if not library.does_asset_exist(f"{folder}/{os.path.splitext(f)[0]}")]
if missing:
    raise SystemExit(f"no existing texture for {missing}; nothing imported")

for name in files:
    asset_name = os.path.splitext(name)[0]
    if apply:
        task = unreal.AssetImportTask()
        task.filename = os.path.join(source, name)
        task.destination_path = folder
        task.destination_name = asset_name
        task.replace_existing = True
        task.replace_existing_settings = False
        task.automated = True
        task.save = True
        tools.import_asset_tasks([task])
    texture = library.load_asset(f"{folder}/{asset_name}")
    print(f"{folder}/{asset_name}: source {texture.blueprint_get_size_x()}x{texture.blueprint_get_size_y()} applied {apply}")
print(f"{len(files)} textures {'reimported' if apply else 'would be reimported'}")
