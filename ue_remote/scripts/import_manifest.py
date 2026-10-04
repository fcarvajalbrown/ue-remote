import json
import os

import unreal

manifest = json.load(open(ARGS["manifest"][0], encoding="utf-8"))
materials_spec = json.load(open(ARGS["materials"][0], encoding="utf-8"))
root = ARGS["root"][0].rstrip("/")
temp = ARGS.get("temp", ["/Game/Developers/Import"])[0].rstrip("/")
third_party = ARGS.get("third_party", ["/Game/ThirdParty"])[0].rstrip("/")
content = manifest["content"]
source_dir = os.path.dirname(ARGS["manifest"][0])
lods_spec = manifest["world"]["lods"]
core_folder = f"{root}/{content['core_folder']}"

library = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
mesh_tools = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)

REDUCE_MIN_TRIANGLES = 150
REDUCTION_STEPS = ((0.5, 0.3), (0.2, 0.1))


def pascal(text):
    return "".join(part.capitalize() for part in text.split("_"))


def linear(rgb):
    return unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0)


def base_material():
    path = f"{core_folder}/M_Base"
    if library.does_asset_exist(path):
        return library.load_asset(path)
    material = tools.create_asset("M_Base", core_folder, unreal.Material, unreal.MaterialFactoryNew())
    colour = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -300, 0)
    colour.set_editor_property("parameter_name", "Main Color")
    colour.set_editor_property("default_value", unreal.LinearColor(0.5, 0.5, 0.5, 1.0))
    unreal.MaterialEditingLibrary.connect_material_property(colour, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(material)
    library.save_loaded_asset(material)
    return material


def ensure_materials(names):
    library.make_directory(core_folder)
    for name in names:
        asset_name = f"{content['material_prefix']}{pascal(name)}"
        if library.does_asset_exist(f"{core_folder}/{asset_name}"):
            continue
        parent_name = materials_spec["parents"].get(name, materials_spec["parents"]["default"])
        parent = library.load_asset(f"{third_party}/ProtoGrid/Materials/Instances/{parent_name}")
        if parent is None:
            print(f"parent {parent_name} not found under {third_party}; using the project base material")
            parent = base_material()
        asset = tools.create_asset(asset_name, core_folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        asset.set_editor_property("parent", parent)
        tint = materials_spec["tints"].get(name, [0.5, 0.5, 0.5])
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(asset, "Main Color", linear(tint))
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(asset, "Second Color", linear([c * 0.8 for c in tint]))
        library.save_loaded_asset(asset)


def import_lod0(entry):
    folder = f"{root}/{entry['folder']}"
    final = f"{folder}/{entry['asset']}"
    if library.does_asset_exist(final):
        library.delete_asset(final)
    task = unreal.AssetImportTask()
    task.filename = os.path.join(source_dir, entry["files"][0]).replace("\\", "/")
    task.destination_path = f"{temp}/{entry['piece']}"
    task.destination_name = entry["asset"]
    task.automated = True
    task.replace_existing = True
    task.save = False
    tools.import_asset_tasks([task])
    meshes = [library.load_asset(str(p)) for p in task.imported_object_paths]
    mesh = [m for m in meshes if isinstance(m, unreal.StaticMesh)][0]
    library.make_directory(folder)
    library.rename_asset(mesh.get_path_name().split(".")[0], final)
    return library.load_asset(final)


def apply_lods(mesh, entry):
    if len(entry["files"]) > 1:
        for index, relative in enumerate(entry["files"][1:], start=1):
            mesh_tools.import_lod(mesh, index, os.path.join(source_dir, relative).replace("\\", "/"))
        sizes = lods_spec["screen_sizes"][: mesh_tools.get_lod_count(mesh)]
        mesh_tools.set_lod_screen_sizes(mesh, sizes)
    elif entry["triangles"] >= REDUCE_MIN_TRIANGLES:
        options = unreal.EditorScriptingMeshReductionOptions()
        options.auto_compute_lod_screen_size = False
        options.reduction_settings = [
            unreal.EditorScriptingMeshReductionSettings(percent_triangles, screen_size) for percent_triangles, screen_size in REDUCTION_STEPS
        ]
        unreal.EditorStaticMeshLibrary.set_lods(mesh, options)


def apply_materials(mesh):
    for index, slot in enumerate(mesh.static_materials):
        name = str(slot.material_slot_name)
        target = library.load_asset(f"{core_folder}/{content['material_prefix']}{pascal(name)}")
        if target is None:
            print(f"no material for slot {name} on {mesh.get_name()}")
            continue
        mesh.set_material(index, target)


def apply_collision(mesh, entry):
    if entry["collision"] == "complex":
        setup = mesh.get_editor_property("body_setup")
        setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        mesh.set_editor_property("body_setup", setup)
    else:
        unreal.EditorStaticMeshLibrary.remove_collisions(mesh)


def finish(mesh, entry):
    nanite = mesh.get_editor_property("nanite_settings")
    nanite.set_editor_property("enabled", False)
    mesh.set_editor_property("nanite_settings", nanite)
    apply_collision(mesh, entry)
    apply_materials(mesh)
    library.save_loaded_asset(mesh)


used = sorted({m for entry in manifest["meshes"].values() for m in entry["materials"]})
ensure_materials(used)

imported = 0
for name, entry in sorted(manifest["meshes"].items()):
    mesh = import_lod0(entry)
    apply_lods(mesh, entry)
    finish(mesh, entry)
    counts = [mesh.get_num_triangles(i) for i in range(mesh_tools.get_lod_count(mesh))]
    print(f"{entry['folder']}/{entry['asset']}: lods {counts}")
    imported += 1
print(f"imported {imported} meshes")
