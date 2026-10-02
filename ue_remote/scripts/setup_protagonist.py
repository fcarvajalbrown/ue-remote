import unreal

library = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()

old_protagonist = "/Game/SanIgna/Player/BP_Protagonist"
protagonist_folder = "/Game/SanIgna/Characters/Protagonist"
protagonist = f"{protagonist_folder}/BP_Protagonist"
game_mode_folder = "/Game/SanIgna/Core"
game_mode = f"{game_mode_folder}/BP_SanIgnaGameMode"
mesh_path = "/Game/SanIgna/Characters/Protagonist/Mannequin/Meshes/SK_Mannequin"
blend_space_path = "/Game/SanIgna/Characters/Protagonist/Animations/BS_MM_WalkRun"

if library.does_asset_exist(old_protagonist) and not library.does_asset_exist(protagonist):
    asset = library.load_asset(old_protagonist)
    if not tools.rename_assets([unreal.AssetRenameData(asset, protagonist_folder, "BP_Protagonist")]):
        raise SystemExit("could not move BP_Protagonist")
    print(f"moved {old_protagonist} -> {protagonist}")

protagonist_bp = library.load_asset(protagonist)
protagonist_class = library.load_blueprint_class(protagonist)
character = unreal.get_default_object(protagonist_class)
body = character.get_editor_property("mesh")
body.set_editor_property("skeletal_mesh_asset", library.load_asset(mesh_path))
character.set_editor_property("locomotion_blend_space", library.load_asset(blend_space_path))
unreal.BlueprintEditorLibrary.compile_blueprint(protagonist_bp)
print(f"{protagonist}: saved={library.save_asset(protagonist, only_if_is_dirty=False)}")

if not library.does_asset_exist(game_mode):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.load_class(None, "/Script/SanIgna.SanIgnaGameMode"))
    tools.create_asset("BP_SanIgnaGameMode", game_mode_folder, unreal.Blueprint, factory)
game_mode_bp = library.load_asset(game_mode)
game_mode_class = library.load_blueprint_class(game_mode)
unreal.get_default_object(game_mode_class).set_editor_property("default_pawn_class", protagonist_class)
unreal.BlueprintEditorLibrary.compile_blueprint(game_mode_bp)
print(f"{game_mode}: saved={library.save_asset(game_mode, only_if_is_dirty=False)}")

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
world.get_world_settings().set_editor_property("default_game_mode", game_mode_class)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
print(f"{world.get_path_name()}: game mode override -> {game_mode}, saved={level.save_current_level()}")

check = unreal.get_default_object(library.load_blueprint_class(protagonist))
print("check mesh", check.get_editor_property("mesh").get_editor_property("skeletal_mesh_asset").get_path_name())
print("check blend space", check.get_editor_property("locomotion_blend_space").get_path_name())
print("check pawn", unreal.get_default_object(library.load_blueprint_class(game_mode)).get_editor_property("default_pawn_class").get_name())
