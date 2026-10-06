import os
import sys

import unreal


def read_arguments():
    injected = globals().get("ARGS")
    if injected:
        return injected
    from_env = os.environ.get("UE_SCRIPT_ARGS")
    if from_env:
        import json
        return json.loads(from_env)
    values = {}
    for item in sys.argv[1:]:
        key, _, value = item.partition("=")
        values.setdefault(key, []).append(value)
    return values


def assets_under(root, class_names):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_paths_synchronous([root], True)
    found = []
    for class_name in class_names:
        flt = unreal.ARFilter(
            package_paths=[root],
            class_paths=[unreal.TopLevelAssetPath("/Script/Engine", class_name)],
            recursive_paths=True,
        )
        found += [str(a.package_name) for a in registry.get_assets(flt)]
    return sorted(set(found))


arguments = read_arguments()
destination = arguments["destination"][0]
os.makedirs(destination, exist_ok=True)

options = unreal.FbxExportOption()
options.set_editor_property("vertex_color", True)
options.set_editor_property("level_of_detail", False)
options.set_editor_property("collision", False)
options.set_editor_property("export_morph_targets", False)
options.set_editor_property("export_preview_mesh", True)

paths = list(arguments.get("asset", []))
roots = arguments.get("root", [])
classes = arguments.get("class", ["StaticMesh", "SkeletalMesh", "AnimSequence"])
for root in roots:
    paths += assets_under(root, classes)

exported = 0
failed = 0
for path in paths:
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        print(f"export_assets: cannot load {path}")
        failed += 1
        continue
    relative = path.rsplit("/", 1)[0]
    for root in roots:
        if path.startswith(root):
            relative = path[len(root):].rsplit("/", 1)[0]
            break
    folder = os.path.join(destination, relative.strip("/")) if roots else destination
    os.makedirs(folder, exist_ok=True)
    task = unreal.AssetExportTask()
    task.object = asset
    task.filename = os.path.join(folder, path.rsplit("/", 1)[-1] + ".fbx").replace("\\", "/")
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    task.options = options
    ok = unreal.Exporter.run_asset_export_task(task)
    exported += 1 if ok else 0
    failed += 0 if ok else 1
    print(f"export_assets: {path} -> {task.filename}: {ok}")

print(f"export_assets: done exported={exported} failed={failed}")
