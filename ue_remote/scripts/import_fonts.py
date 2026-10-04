import os
import re

import unreal

if not hasattr(unreal, "BMFontBuilderLibrary"):
    raise SystemExit("this script needs the editor helper unreal.BMFontBuilderLibrary.create_composite_font from a C++ editor module; nothing imported")

source_directory = ARGS["source"][0]
destination = ARGS["destination"][0].rstrip("/")

tasks = []
families = {}

for file_name in sorted(os.listdir(source_directory)):
    stem, extension = os.path.splitext(file_name)
    if extension.lower() != ".ttf":
        continue
    family, style = stem.split("-")
    asset_name = "FF_" + family + re.sub(r"[^A-Za-z0-9]", "", style)
    task = unreal.AssetImportTask()
    task.filename = os.path.join(source_directory, file_name)
    task.destination_path = destination
    task.destination_name = asset_name
    task.automated = True
    task.replace_existing = True
    task.save = True
    tasks.append(task)
    families.setdefault(family, []).append((style, asset_name))

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
for task in tasks:
    print("face", [str(path) for path in task.imported_object_paths])

for family, faces in families.items():
    loaded = [unreal.EditorAssetLibrary.load_asset(f"{destination}/{asset_name}") for _, asset_name in faces]
    font = unreal.BMFontBuilderLibrary.create_composite_font(destination, f"F_{family}", [style for style, _ in faces], loaded)
    unreal.EditorAssetLibrary.save_loaded_asset(font)
    print("font", font.get_path_name(), [style for style, _ in faces])
