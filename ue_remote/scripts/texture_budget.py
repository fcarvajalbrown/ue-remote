import json

import unreal

with open(ARGS["spec"][0], encoding="utf-8") as handle:
    spec = json.load(handle)
apply = ARGS.get("apply", ["0"])[0] == "1"

library = unreal.EditorAssetLibrary
changed = 0
for path in library.list_assets(spec["path"], recursive=True):
    data = library.find_asset_data(path)
    if str(data.asset_class_path.asset_name) != "Texture2D":
        continue
    name = str(data.asset_name)
    texture = data.get_asset()
    max_size = spec["default_max_size"]
    for rule in spec["max_size_rules"]:
        if rule["contains"] in name:
            max_size = rule["max_size"]
            break
    kind = next((k for k, suffix in spec["suffixes"].items() if name.endswith(suffix)), "color")
    settings = spec["kinds"][kind]
    target = {
        "max_texture_size": max_size,
        "lod_group": getattr(unreal.TextureGroup, settings["lod_group"]),
        "compression_settings": getattr(unreal.TextureCompressionSettings, settings["compression"]),
        "srgb": settings["srgb"],
    }
    before = {key: texture.get_editor_property(key) for key in target}
    if before != target:
        changed += 1
        if apply:
            for key, value in target.items():
                texture.set_editor_property(key, value)
            library.save_loaded_asset(texture, only_if_is_dirty=False)
    after = {key: texture.get_editor_property(key) for key in target}
    print(f"{name}: max {after['max_texture_size']} {after['lod_group'].name} {after['compression_settings'].name} srgb={after['srgb']}")
print(f"{changed} textures {'changed' if apply else 'would change'}")
