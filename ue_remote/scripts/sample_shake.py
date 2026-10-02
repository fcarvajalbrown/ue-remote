import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise SystemExit("no Play session running")
controller = unreal.GameplayStatics.get_player_controller(world, 0)
manager = controller.get_editor_property("player_camera_manager")
pawn = controller.get_controlled_pawn()
camera = pawn.get_editor_property("follow_camera")
state = {"last": -1, "rows": []}


def sample(delta):
    frame = unreal.SystemLibrary.get_frame_count()
    if frame == state["last"]:
        return
    state["last"] = frame
    view = manager.get_camera_rotation()
    base = camera.get_world_rotation()
    location = manager.get_camera_location() - camera.get_world_location()
    state["rows"].append((frame, round(view.pitch - base.pitch, 3), round(view.roll - base.roll, 3), round(location.z, 2)))
    if len(state["rows"]) >= 120:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        for row in state["rows"][::12]:
            print("shake sample frame pitch roll z", row)


state["handle"] = unreal.register_slate_post_tick_callback(sample)
