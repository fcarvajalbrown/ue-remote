import os

import unreal

source = ARGS["source"][0]
folder = ARGS["folder"][0].rstrip("/")
prefix = ARGS.get("prefix", ["A_"])[0]
extensions = (".wav",)

tasks = []
for directory, _, files in os.walk(source):
    relative = os.path.relpath(directory, source)
    destination = folder if relative == "." else f"{folder}/{relative.replace(os.sep, '/')}"
    for file_name in sorted(files):
        if not file_name.lower().endswith(extensions):
            continue
        task = unreal.AssetImportTask()
        task.filename = os.path.join(directory, file_name)
        task.destination_path = destination
        task.destination_name = prefix + os.path.splitext(file_name)[0]
        task.replace_existing = True
        task.automated = True
        task.save = True
        tasks.append(task)

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
imported = sum(len(task.imported_object_paths) for task in tasks)
failed = [task.filename for task in tasks if not task.imported_object_paths]
print(f"{imported} of {len(tasks)} sounds imported into {folder}")
for path in failed:
    print(f"FAILED {path}")
