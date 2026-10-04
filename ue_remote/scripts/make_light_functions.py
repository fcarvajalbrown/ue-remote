import json

import unreal

library = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
assets = unreal.EditorAssetLibrary

root = ARGS["root"][0].rstrip("/")
definitions = json.load(open(ARGS["spec"][0], encoding="utf-8"))
if "key" in ARGS:
    for key in ARGS["key"][0].split("."):
        definitions = definitions[key]
rebuild = ARGS.get("rebuild", ["0"])[0] == "1"

DRIFT_PARAMETERS = {"scale": "Scale", "speed": "Speed", "contrast": "Contrast", "bias": "Bias", "floor": "Floor"}
FLICKER_PARAMETERS = {"freq1": "Freq1", "freq2": "Freq2", "min": "Min"}
DRIFT_DEFAULTS = {"Scale": 0.0007, "Speed": 80.0, "Contrast": 2.4, "Bias": -0.3, "Floor": 0.2}
FLICKER_DEFAULTS = {"Freq1": 1.1, "Freq2": 2.9, "Min": 0.72}


def pascal(text):
    return "".join(part.capitalize() for part in text.split("_"))


def node(material, expression_class, x, y, **properties):
    expression = library.create_material_expression(material, expression_class, x, y)
    for name, value in properties.items():
        expression.set_editor_property(name, value)
    return expression


def scalar(material, name, default, x, y):
    return node(material, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=default)


def constant(material, value, x, y):
    return node(material, unreal.MaterialExpressionConstant, x, y, r=value)


def link(source, target, pin):
    library.connect_material_expressions(source, "", target, pin)


def math_node(material, expression_class, x, y, a, b):
    expression = node(material, expression_class, x, y)
    link(a, expression, "A")
    link(b, expression, "B")
    return expression


def fresh_material(name):
    path = f"{root}/{name}"
    if assets.does_asset_exist(path):
        if not rebuild:
            return None
        assets.delete_asset(path)
        unreal.SystemLibrary.collect_garbage()
    material = tools.create_asset(name, root, unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_LIGHT_FUNCTION)
    return material


def finish(material, output):
    library.connect_material_property(output, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    library.recompile_material(material)
    assets.save_loaded_asset(material)
    print(f"built {material.get_name()}")


def build_drift():
    material = fresh_material("M_LF_Drift")
    if material is None:
        return
    position = node(material, unreal.MaterialExpressionWorldPosition, -1400, 0)
    time = node(material, unreal.MaterialExpressionTime, -1400, 200)
    wind = node(material, unreal.MaterialExpressionVectorParameter, -1400, 380, parameter_name="Wind", default_value=unreal.LinearColor(1.0, 0.35, 0.0, 1.0))
    travelled = math_node(material, unreal.MaterialExpressionMultiply, -1150, 260, time, scalar(material, "Speed", DRIFT_DEFAULTS["Speed"], -1400, 560))
    offset = math_node(material, unreal.MaterialExpressionMultiply, -950, 300, wind, travelled)
    moved = math_node(material, unreal.MaterialExpressionAdd, -750, 100, position, offset)
    scaled = math_node(material, unreal.MaterialExpressionMultiply, -550, 100, moved, scalar(material, "Scale", DRIFT_DEFAULTS["Scale"], -750, 260))
    noise = node(material, unreal.MaterialExpressionNoise, -350, 100, scale=1.0, quality=1, noise_function=unreal.NoiseFunction.NOISEFUNCTION_GRADIENT_ALU, levels=3, level_scale=2.0, output_min=0.0, output_max=1.0)
    link(scaled, noise, "")
    biased = math_node(material, unreal.MaterialExpressionAdd, -150, 100, noise, scalar(material, "Bias", DRIFT_DEFAULTS["Bias"], -350, 300))
    stretched = math_node(material, unreal.MaterialExpressionMultiply, 50, 100, biased, scalar(material, "Contrast", DRIFT_DEFAULTS["Contrast"], -150, 300))
    clamped = node(material, unreal.MaterialExpressionSaturate, 250, 100)
    link(stretched, clamped, "")
    mixed = node(material, unreal.MaterialExpressionLinearInterpolate, 450, 100)
    link(scalar(material, "Floor", DRIFT_DEFAULTS["Floor"], 250, 300), mixed, "A")
    link(constant(material, 1.0, 250, 420), mixed, "B")
    link(clamped, mixed, "Alpha")
    finish(material, mixed)


def build_flicker():
    material = fresh_material("M_LF_Flicker")
    if material is None:
        return
    time = node(material, unreal.MaterialExpressionTime, -1200, 0)
    first = node(material, unreal.MaterialExpressionSine, -700, -100, period=1.0)
    link(math_node(material, unreal.MaterialExpressionMultiply, -950, -100, time, scalar(material, "Freq1", FLICKER_DEFAULTS["Freq1"], -1200, 160)), first, "")
    shifted = math_node(material, unreal.MaterialExpressionAdd, -700, 200, math_node(material, unreal.MaterialExpressionMultiply, -950, 200, time, scalar(material, "Freq2", FLICKER_DEFAULTS["Freq2"], -1200, 320)), constant(material, 1.7, -950, 360))
    second = node(material, unreal.MaterialExpressionSine, -500, 200, period=1.0)
    link(shifted, second, "")
    both = math_node(material, unreal.MaterialExpressionAdd, -300, 50, first, second)
    half = math_node(material, unreal.MaterialExpressionMultiply, -100, 50, both, constant(material, 0.25, -300, 220))
    centred = math_node(material, unreal.MaterialExpressionAdd, 100, 50, half, constant(material, 0.5, -100, 220))
    clamped = node(material, unreal.MaterialExpressionSaturate, 300, 50)
    link(centred, clamped, "")
    mixed = node(material, unreal.MaterialExpressionLinearInterpolate, 500, 50)
    link(scalar(material, "Min", FLICKER_DEFAULTS["Min"], 300, 250), mixed, "A")
    link(constant(material, 1.0, 300, 370), mixed, "B")
    link(clamped, mixed, "Alpha")
    finish(material, mixed)


def build_instance(definition):
    kind = definition["kind"]
    parent = assets.load_asset(f"{root}/M_LF_{'Drift' if kind == 'drift' else 'Flicker'}")
    name = f"MI_LF_{pascal(definition['id'])}"
    path = f"{root}/{name}"
    if assets.does_asset_exist(path):
        assets.delete_asset(path)
        unreal.SystemLibrary.collect_garbage()
    instance = tools.create_asset(name, root, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    instance.set_editor_property("parent", parent)
    mapping = DRIFT_PARAMETERS if kind == "drift" else FLICKER_PARAMETERS
    for key, parameter in mapping.items():
        if key in definition:
            library.set_material_instance_scalar_parameter_value(instance, parameter, float(definition[key]))
    if kind == "drift" and "wind" in definition:
        wind = definition["wind"]
        library.set_material_instance_vector_parameter_value(instance, "Wind", unreal.LinearColor(wind[0], wind[1], wind[2], 1.0))
    library.update_material_instance(instance)
    assets.save_loaded_asset(instance)
    print(f"instance {name}")


assets.make_directory(root)
kinds = {definition["kind"] for definition in definitions}
if "drift" in kinds:
    build_drift()
if "flicker" in kinds:
    build_flicker()
for definition in definitions:
    build_instance(definition)
