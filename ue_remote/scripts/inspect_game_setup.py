import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
settings = world.get_world_settings()
override = settings.get_editor_property("default_game_mode")
print("map", world.get_path_name())
print("world settings game mode override", override)

for path in unreal.EditorAssetLibrary.list_assets("/Game/SanIgna", recursive=True):
    asset_data = unreal.EditorAssetLibrary.find_asset_data(path)
    if str(asset_data.asset_class_path.asset_name) != "Blueprint":
        continue
    blueprint = unreal.EditorAssetLibrary.load_asset(path)
    generated = unreal.EditorAssetLibrary.load_blueprint_class(path.split(".")[0])
    if not generated:
        continue
    default = unreal.get_default_object(generated)
    print("blueprint", path.split(".")[0], "class", type(default).__name__)
    if isinstance(default, unreal.GameModeBase):
        print("  default pawn", default.get_editor_property("default_pawn_class"))
    if isinstance(default, unreal.Character):
        mesh = default.get_editor_property("mesh")
        print("  mesh asset", mesh.get_editor_property("skeletal_mesh_asset") if mesh else None)
        print("  anim mode", mesh.get_editor_property("animation_mode") if mesh else None)
