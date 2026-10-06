import json
import os

import unreal

ARGS = globals().get("ARGS") or json.loads(os.environ.get("UE_SCRIPT_ARGS", "{}"))

root = ARGS.get("path", ["/Game"])[0]
match = ARGS.get("match", [""])[0]
apply = ARGS.get("apply", ["0"])[0] == "1"

library = unreal.EditorAssetLibrary
registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous([root], True)
blueprint_classes = {"Blueprint", "WidgetBlueprint", "AnimBlueprint"}

found = 0
for data in registry.get_assets_by_path(root, recursive=True):
    if str(data.asset_class_path.asset_name) not in blueprint_classes:
        continue
    parent_path = str(data.get_tag_value("ParentClass") or "None")
    if match and match not in parent_path:
        continue
    blueprint = data.get_asset()
    found += 1
    saved = library.save_loaded_asset(blueprint, only_if_is_dirty=False) if apply else False
    print(f"{data.package_name} parent {parent_path} saved {saved}")
print(f"blueprints matched {found} apply {apply}")
