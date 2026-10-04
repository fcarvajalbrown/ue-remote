import unreal


def triple(text):
    return [float(v) for v in text.split(",")]


location = unreal.Vector(*triple(ARGS["loc"][0]))
if "look_at" in ARGS:
    rotation = unreal.MathLibrary.find_look_at_rotation(location, unreal.Vector(*triple(ARGS["look_at"][0])))
else:
    pitch, yaw, roll = triple(ARGS.get("rot", ["0,0,0"])[0])
    rotation = unreal.Rotator(roll, pitch, yaw)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(location, rotation)
unreal.EditorLevelLibrary.editor_set_game_view(ARGS.get("game_view", ["1"])[0] == "1")
print(f"camera at {location} rotation {rotation}")
