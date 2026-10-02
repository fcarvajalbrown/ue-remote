import os

import unreal

library = unreal.EditorAssetLibrary
editing = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()

scripts = ARGS["scripts"][0]
bayer_png = ARGS["bayer"][0]
one_bit_folder = "/Game/SanIgna/Core/Look/OneBit"
ps2_folder = "/Game/SanIgna/Core/Look/PS2"


def read(name):
    with open(os.path.join(scripts, "look", name), encoding="utf-8") as handle:
        return handle.read()


def after_tonemapping():
    names = [name for name in dir(unreal.BlendableLocation) if "TONEMAPPING" in name and "AFTER" in name]
    if not names:
        raise SystemExit(f"no after-tonemapping blendable location in {dir(unreal.BlendableLocation)}")
    return getattr(unreal.BlendableLocation, names[0])


def import_bayer():
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", bayer_png)
    task.set_editor_property("destination_path", one_bit_folder)
    task.set_editor_property("destination_name", "T_Bayer8")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    tools.import_asset_tasks([task])
    texture = library.load_asset(f"{one_bit_folder}/T_Bayer8")
    texture.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
    texture.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    texture.set_editor_property("srgb", False)
    texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    library.save_asset(f"{one_bit_folder}/T_Bayer8", only_if_is_dirty=False)
    return texture


def material(folder, name):
    path = f"{folder}/{name}"
    if library.does_asset_exist(path):
        built = library.load_asset(path)
        editing.delete_all_material_expressions(built)
    else:
        built = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    built.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    built.set_editor_property("blendable_location", after_tonemapping())
    return built


def custom_node(built, code, description, parameters):
    scene = editing.create_material_expression(built, unreal.MaterialExpressionSceneTexture, -900, -300)
    scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)

    node = editing.create_material_expression(built, unreal.MaterialExpressionCustom, -300, 0)
    node.set_editor_property("code", code)
    node.set_editor_property("description", description)
    node.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs = []
    for name in ["SceneTexture"] + [entry[0] for entry in parameters]:
        entry = unreal.CustomInput()
        entry.set_editor_property("input_name", name)
        inputs.append(entry)
    node.set_editor_property("inputs", inputs)
    if not editing.connect_material_expressions(scene, "Color", node, "SceneTexture"):
        raise SystemExit("could not connect the scene texture")

    for index, (name, kind, value) in enumerate(parameters):
        y = index * 110 - 500
        if kind == "scalar":
            parameter = editing.create_material_expression(built, unreal.MaterialExpressionScalarParameter, -700, y)
            parameter.set_editor_property("default_value", value)
        elif kind == "vector":
            parameter = editing.create_material_expression(built, unreal.MaterialExpressionVectorParameter, -700, y)
            parameter.set_editor_property("default_value", unreal.LinearColor(*value, 1.0))
        else:
            parameter = editing.create_material_expression(built, unreal.MaterialExpressionTextureObjectParameter, -700, y)
            parameter.set_editor_property("texture", value)
        parameter.set_editor_property("parameter_name", name)
        if not editing.connect_material_expressions(parameter, "", node, name):
            raise SystemExit(f"could not connect {name}")

    if not editing.connect_material_property(node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise SystemExit("could not connect emissive")
    editing.recompile_material(built)


def instance(parent, folder, name):
    path = f"{folder}/{name}"
    if library.does_asset_exist(path):
        built = library.load_asset(path)
    else:
        built = tools.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    editing.set_material_instance_parent(built, parent)
    library.save_asset(path, only_if_is_dirty=False)


bayer = import_bayer()

one_bit = material(one_bit_folder, "M_PP_SoftOneBit")
custom_node(one_bit, read("soft_one_bit.hlsl"), "SoftOneBit", [
    ("Bayer", "texture", bayer),
    ("Contrast", "scalar", 1.1),
    ("Tones", "scalar", 4.0),
    ("DitherAmount", "scalar", 0.75),
    ("PixelScale", "scalar", 1.0),
    ("DepthThreshold", "scalar", 0.02),
    ("NormalThreshold", "scalar", 0.5),
    ("OutlineStrength", "scalar", 1.0),
    ("Ink", "vector", (0.10, 0.09, 0.08)),
    ("Paper", "vector", (0.86, 0.82, 0.72)),
])
library.save_asset(f"{one_bit_folder}/M_PP_SoftOneBit", only_if_is_dirty=False)
instance(one_bit, one_bit_folder, "MI_PP_SoftOneBit")

ps2 = material(ps2_folder, "M_PP_PS2")
custom_node(ps2, read("ps2.hlsl"), "PS2", [
    ("Softness", "scalar", 1.0),
    ("Saturation", "scalar", 0.85),
    ("Tint", "vector", (1.0, 1.0, 1.0)),
])
library.save_asset(f"{ps2_folder}/M_PP_PS2", only_if_is_dirty=False)
instance(ps2, ps2_folder, "MI_PP_PS2")

for folder in (one_bit_folder, ps2_folder):
    for path in library.list_assets(folder, recursive=False):
        print(path)
