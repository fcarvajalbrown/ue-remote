import math

import unreal

bones = ARGS.get("bone", ["pelvis", "spine_03", "neck_01", "head", "clavicle_l", "clavicle_r"])
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise SystemExit("no Play session running")

controller = unreal.GameplayStatics.get_player_controller(world, 0)
pawn = controller.get_controlled_pawn() if controller else None
if not pawn:
    raise SystemExit("no controlled pawn")


def fmt(v):
    return f"({v.x:7.1f}, {v.y:7.1f}, {v.z:7.1f})"


actor_location = pawn.get_actor_location()
actor_rotation = pawn.get_actor_rotation()


def to_actor_space(world_location):
    delta = world_location - actor_location
    yaw = math.radians(actor_rotation.yaw)
    return unreal.Vector(
        delta.x * math.cos(yaw) + delta.y * math.sin(yaw),
        -delta.x * math.sin(yaw) + delta.y * math.cos(yaw),
        delta.z,
    )


print(f"pawn       {pawn.get_class().get_name()} at {fmt(actor_location)} yaw {actor_rotation.yaw:.1f}")
print(f"control    pitch {controller.get_control_rotation().pitch:.1f} yaw {controller.get_control_rotation().yaw:.1f}")

for component in pawn.get_components_by_class(unreal.CameraComponent):
    location = component.get_world_location()
    local = to_actor_space(location)
    print(f"camera     {component.get_name()} world {fmt(location)} actor-space {fmt(local)} fov {component.field_of_view:.0f}")
    print(f"           attached to {component.get_attach_parent().get_name() if component.get_attach_parent() else None} socket {component.get_attach_socket_name()}")

for prop in ("camera_offset_from_head", "head_bone_name"):
    try:
        print(f"{prop:10} {pawn.get_editor_property(prop)}")
    except Exception as error:
        print(f"{prop:10} unreadable: {error}")

mesh = pawn.get_components_by_class(unreal.SkeletalMeshComponent)[0]
print(f"mesh       {mesh.get_skeletal_mesh_asset().get_name() if mesh.get_skeletal_mesh_asset() else None} anim mode {mesh.get_animation_mode()}")
for bone in bones:
    location = mesh.get_socket_location(bone)
    local = to_actor_space(location)
    hidden = mesh.is_bone_hidden_by_name(bone)
    print(f"bone       {bone:12} actor-space {fmt(local)} hidden {hidden}")
print(f"near clip  {unreal.SystemLibrary.get_console_variable_float_value('r.SetNearClipPlane')}")
