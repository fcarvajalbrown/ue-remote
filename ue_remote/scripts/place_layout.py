import csv
import json

import unreal

manifest = json.load(open(ARGS["manifest"][0], encoding="utf-8"))
layout_path = ARGS["layout"][0]
root = ARGS["root"][0].rstrip("/")
map_path = ARGS.get("map", [None])[0]
ground_names = [name for name in ARGS.get("ground", ["terrain,paths"])[0].split(",") if name]
ground_folder = f"{manifest['world'].get('folder_root', 'World')}/Ground"

library = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
actors_library = unreal.EditorLevelLibrary
content = manifest["content"]
core_folder = f"{root}/{content['core_folder']}"
instance_blueprint = f"{core_folder}/BP_InstancedMesh"
cull = manifest["world"].get("lods", {})


def ensure_instance_blueprint():
    if library.does_asset_exist(instance_blueprint):
        return library.load_asset(instance_blueprint)
    library.make_directory(core_folder)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    blueprint = tools.create_asset("BP_InstancedMesh", core_folder, unreal.Blueprint, factory)
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = subsystem.k2_gather_subobject_data_for_blueprint(blueprint)
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.HierarchicalInstancedStaticMeshComponent, blueprint_context=blueprint)
    handle, _ = subsystem.add_new_subobject(params)
    subsystem.rename_subobject(handle, "Instances")
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    library.save_loaded_asset(blueprint)
    return blueprint


def mesh_asset(name):
    entry = manifest["meshes"][name]
    return library.load_asset(f"{root}/{entry['folder']}/{entry['asset']}")


def transform_of(row):
    scale = float(row["scale"])
    return unreal.Transform(
        unreal.Vector(float(row["x_cm"]), float(row["y_cm"]), float(row["z_cm"])),
        unreal.Rotator(0.0, 0.0, float(row["yaw_deg"])),
        unreal.Vector(scale * float(row["scale_x"]), scale, scale),
    )


def spawn_static(mesh_name, transform, label, folder):
    actor = actors_library.spawn_actor_from_class(unreal.StaticMeshActor, transform.translation, transform.rotation.rotator())
    actor.set_actor_scale3d(transform.scale3d)
    component = actor.static_mesh_component
    component.set_static_mesh(mesh_asset(mesh_name))
    component.set_mobility(unreal.ComponentMobility.STATIC)
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    return actor


def place_ground():
    for name in ground_names:
        if name in manifest["meshes"]:
            spawn_static(name, unreal.Transform(), name, ground_folder)


def place_layout():
    rows = list(csv.DictReader(open(layout_path, newline="", encoding="utf-8")))
    blueprint = ensure_instance_blueprint()
    instances = {}
    singles = 0
    for row in rows:
        transform = transform_of(row)
        for mesh_name in manifest["pieces"][row["piece"]]:
            if row["instance"] == "1":
                instances.setdefault((mesh_name, row["folder"]), []).append(transform)
            else:
                spawn_static(mesh_name, transform, mesh_name, row["folder"])
                singles += 1
    for (mesh_name, folder), transforms in instances.items():
        actor = actors_library.spawn_actor_from_object(blueprint, unreal.Vector(0, 0, 0))
        component = actor.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
        component.set_static_mesh(mesh_asset(mesh_name))
        component.set_mobility(unreal.ComponentMobility.STATIC)
        component.add_instances(transforms, False, True)
        if "cull_start" in cull and "cull_end" in cull:
            component.set_cull_distances(cull["cull_start"], cull["cull_end"])
        if manifest["meshes"][mesh_name]["collision"] == "none":
            component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        actor.set_actor_label(f"{mesh_name}_instances")
        actor.set_folder_path(folder)
        print(f"{mesh_name} [{folder}]: {len(transforms)} instances")
    print(f"{singles} single actors, {len(instances)} instanced actors")


if map_path:
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
place_ground()
place_layout()
if map_path:
    library.make_directory(map_path.rsplit("/", 1)[0])
    print("saved map", unreal.EditorLoadingAndSavingUtils.save_map(actors_library.get_editor_world(), map_path))
print("actors", len(actors_library.get_all_level_actors()))
