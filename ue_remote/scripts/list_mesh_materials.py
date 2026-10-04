import unreal

library = unreal.EditorAssetLibrary

for entry in ARGS["path"]:
    for path in library.list_assets(entry, recursive=True, include_folder=False):
        asset = library.load_asset(path.split(".")[0])
        if not isinstance(asset, unreal.StaticMesh):
            print(f"{path}: {type(asset).__name__}")
            continue
        for index, slot in enumerate(asset.static_materials):
            material = slot.material_interface
            print(f"{path} slot {index} {slot.material_slot_name} -> {material.get_path_name() if material else None}")
