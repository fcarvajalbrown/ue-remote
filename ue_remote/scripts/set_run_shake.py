import unreal

library = unreal.EditorAssetLibrary
shake_path = "/Game/SanIgna/Characters/Protagonist/CS_Run"
protagonist = "/Game/SanIgna/Characters/Protagonist/BP_Protagonist"

shake_class = library.load_blueprint_class(shake_path)
pattern = unreal.get_default_object(shake_class).get_editor_property("root_shake_pattern")
print("shake pattern after restart", pattern.get_class().get_name() if pattern else None)
if pattern:
    print("pitch amplitude", pattern.get_editor_property("pitch").get_editor_property("amplitude"))

character = unreal.get_default_object(library.load_blueprint_class(protagonist))
character.set_editor_property("run_camera_shake", shake_class)
unreal.BlueprintEditorLibrary.compile_blueprint(library.load_asset(protagonist))
print(f"{protagonist}: saved={library.save_asset(protagonist, only_if_is_dirty=False)}")

check = unreal.get_default_object(library.load_blueprint_class(protagonist))
print("check shake", check.get_editor_property("run_camera_shake").get_name())
print("check min speed", check.get_editor_property("run_shake_min_speed"), "scale", check.get_editor_property("run_shake_scale"))
