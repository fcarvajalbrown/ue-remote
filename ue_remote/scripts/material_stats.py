import unreal

for path in ARGS["asset"]:
    material = unreal.EditorAssetLibrary.load_asset(path)
    stats = unreal.MaterialEditingLibrary.get_statistics(material)
    print(path, "pixel_instructions", stats.num_pixel_shader_instructions, "samplers", stats.num_samplers)
