import os

import unreal

destination = ARGS["destination"][0]
os.makedirs(destination, exist_ok=True)

for path in ARGS["asset"]:
    texture = unreal.EditorAssetLibrary.load_asset(path)
    task = unreal.AssetExportTask()
    task.object = texture
    task.filename = os.path.join(destination, path.rsplit("/", 1)[-1] + ".png").replace("\\", "/")
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    print(f"{path} -> {task.filename}: {unreal.Exporter.run_asset_export_task(task)}")
