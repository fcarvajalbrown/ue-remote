import os
import sys

import unreal


def read_arguments():
    injected = globals().get("ARGS")
    if injected:
        return injected
    values = {}
    for item in sys.argv[1:]:
        key, _, value = item.partition("=")
        values.setdefault(key, []).append(value)
    return values


arguments = read_arguments()
destination = arguments["destination"][0]
os.makedirs(destination, exist_ok=True)

options = unreal.FbxExportOption()
options.set_editor_property("vertex_color", True)
options.set_editor_property("level_of_detail", False)
options.set_editor_property("collision", False)
options.set_editor_property("export_morph_targets", False)
options.set_editor_property("export_preview_mesh", True)

for path in arguments["asset"]:
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        print(f"export_assets: cannot load {path}")
        continue
    task = unreal.AssetExportTask()
    task.object = asset
    task.filename = os.path.join(destination, path.rsplit("/", 1)[-1] + ".fbx").replace("\\", "/")
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    task.options = options
    print(f"export_assets: {path} -> {task.filename}: {unreal.Exporter.run_asset_export_task(task)}")
