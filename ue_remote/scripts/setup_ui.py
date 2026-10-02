import os

import unreal

library = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()

source_root = ARGS["source"][0]
ui_folder = "/Game/SanIgna/UI"
glyph_folder = f"{ui_folder}/Glyphs"
input_folder = f"{ui_folder}/Input"
game_mode = "/Game/SanIgna/Core/BP_SanIgnaGameMode"

GAMEPAD_KEYS = [
    "Gamepad_FaceButton_Bottom", "Gamepad_FaceButton_Right", "Gamepad_FaceButton_Left", "Gamepad_FaceButton_Top",
    "Gamepad_LeftShoulder", "Gamepad_RightShoulder", "Gamepad_LeftTrigger", "Gamepad_RightTrigger",
    "Gamepad_LeftThumbstick", "Gamepad_RightThumbstick", "Gamepad_Special_Right", "Gamepad_Special_Left",
    "Gamepad_DPad_Up", "Gamepad_DPad_Down", "Gamepad_DPad_Left", "Gamepad_DPad_Right",
    "Gamepad_Left2D", "Gamepad_Right2D",
]

GLYPH_SETS = {
    "Xbox": ("Xbox Series/Default", [
        "xbox_button_a", "xbox_button_b", "xbox_button_x", "xbox_button_y",
        "xbox_lb", "xbox_rb", "xbox_lt", "xbox_rt",
        "xbox_stick_l_press", "xbox_stick_r_press", "xbox_button_menu", "xbox_button_view",
        "xbox_dpad_up", "xbox_dpad_down", "xbox_dpad_left", "xbox_dpad_right",
        "xbox_stick_l", "xbox_stick_r",
    ]),
    "SteamDeck": ("Steam Deck/Default", [
        "steamdeck_button_a", "steamdeck_button_b", "steamdeck_button_x", "steamdeck_button_y",
        "steamdeck_button_l1", "steamdeck_button_r1", "steamdeck_button_l2", "steamdeck_button_r2",
        "steamdeck_stick_l_press", "steamdeck_stick_r_press", "steamdeck_button_options", "steamdeck_button_view",
        "steamdeck_dpad_up", "steamdeck_dpad_down", "steamdeck_dpad_left", "steamdeck_dpad_right",
        "steamdeck_stick_l", "steamdeck_stick_r",
    ]),
}

KEYBOARD_GLYPHS = [
    ("Escape", "keyboard_escape"), ("Enter", "keyboard_enter"), ("SpaceBar", "keyboard_space"),
    ("E", "keyboard_e"), ("LeftShift", "keyboard_shift"), ("W", "keyboard_w"), ("A", "keyboard_a"),
    ("S", "keyboard_s"), ("D", "keyboard_d"), ("LeftMouseButton", "mouse_left"), ("Mouse2D", "mouse_move"),
]

CONTROLLERS = [
    ("CD_KeyboardMouse", "MouseAndKeyboard", "", "Keyboard & Mouse/Default", KEYBOARD_GLYPHS),
    ("CD_Gamepad", "Gamepad", "Generic", GLYPH_SETS["Xbox"][0], list(zip(GAMEPAD_KEYS, GLYPH_SETS["Xbox"][1]))),
    ("CD_SteamDeck", "Gamepad", "SteamDeck", GLYPH_SETS["SteamDeck"][0], list(zip(GAMEPAD_KEYS, GLYPH_SETS["SteamDeck"][1]))),
]


def asset_path(folder, name):
    return f"{folder}/{name}"


def import_glyph(subfolder, name):
    destination = f"{glyph_folder}/{subfolder.split('/')[0].replace(' & ', '').replace(' ', '')}"
    path = asset_path(destination, f"T_{name}")
    if library.does_asset_exist(path):
        return library.load_asset(path)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(source_root, subfolder, f"{name}.png"))
    task.set_editor_property("destination_path", destination)
    task.set_editor_property("destination_name", f"T_{name}")
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    tools.import_asset_tasks([task])
    texture = library.load_asset(path)
    texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    texture.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI)
    texture.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    texture.set_editor_property("never_stream", True)
    library.save_asset(path, only_if_is_dirty=False)
    return texture


def make_asset(name, folder, asset_class, factory):
    path = asset_path(folder, name)
    if not library.does_asset_exist(path):
        tools.create_asset(name, folder, asset_class, factory)
    return library.load_asset(path)


def make_blueprint(name, folder, parent, widget=False):
    factory = unreal.WidgetBlueprintFactory() if widget else unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    asset_class = unreal.WidgetBlueprint if widget else unreal.Blueprint
    blueprint = make_asset(name, folder, asset_class, factory)
    return blueprint, unreal.get_default_object(library.load_blueprint_class(asset_path(folder, name)))


def finish(blueprint, path):
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    print(f"{path}: saved={library.save_asset(path, only_if_is_dirty=False)}")


def make_action(name):
    action = make_asset(name, input_folder, unreal.InputAction, unreal.InputAction_Factory())
    action.set_editor_property("value_type", unreal.InputActionValueType.BOOLEAN)
    library.save_asset(asset_path(input_folder, name), only_if_is_dirty=False)
    return action


def key(name):
    value = unreal.Key()
    value.import_text(name)
    return value


click = make_action("IA_UI_Click")
back = make_action("IA_UI_Back")
context = make_asset("IMC_UI", input_folder, unreal.InputMappingContext, unreal.InputMappingContext_Factory())
context.unmap_all()
for action, keys in ((click, ["Gamepad_FaceButton_Bottom", "Enter", "SpaceBar"]), (back, ["Gamepad_FaceButton_Right", "Escape"])):
    for name in keys:
        context.map_key(action, key(name))
library.save_asset(asset_path(input_folder, "IMC_UI"), only_if_is_dirty=False)

input_data_bp, input_data = make_blueprint("BP_UIInputData", input_folder, unreal.CommonUIInputData)
input_data.set_editor_property("enhanced_input_click_action", click)
input_data.set_editor_property("enhanced_input_back_action", back)
finish(input_data_bp, asset_path(input_folder, "BP_UIInputData"))

for name, input_type, gamepad, subfolder, glyphs in CONTROLLERS:
    blueprint, data = make_blueprint(name, input_folder, unreal.CommonInputBaseControllerData)
    data.set_editor_property("input_type", getattr(unreal.CommonInputType, {"MouseAndKeyboard": "MOUSE_AND_KEYBOARD", "Gamepad": "GAMEPAD"}[input_type]))
    if gamepad:
        data.set_editor_property("gamepad_name", gamepad)
    entries = []
    for key_name, glyph in glyphs:
        texture = import_glyph(subfolder, glyph)
        entry = unreal.CommonInputKeyBrushConfiguration()
        entry.import_text(f'(Key={key_name},KeyBrush=(ImageSize=(X=64.000000,Y=64.000000),ResourceObject="{texture.get_path_name()}"))')
        entries.append(entry)
    data.set_editor_property("input_brush_data_map", entries)
    finish(blueprint, asset_path(input_folder, name))

root_bp, _ = make_blueprint("WBP_Root", ui_folder, unreal.SanIgnaRootWidget, widget=True)
finish(root_bp, asset_path(ui_folder, "WBP_Root"))

pause_bp, pause = make_blueprint("WBP_Pause", ui_folder, unreal.PauseScreen, widget=True)
pause.set_editor_property("input_mapping", context)
finish(pause_bp, asset_path(ui_folder, "WBP_Pause"))

hud_bp, hud = make_blueprint("BP_SanIgnaHUD", ui_folder, unreal.SanIgnaHUD)
hud.set_editor_property("root_class", library.load_blueprint_class(asset_path(ui_folder, "WBP_Root")))
hud.set_editor_property("pause_screen_class", library.load_blueprint_class(asset_path(ui_folder, "WBP_Pause")))
finish(hud_bp, asset_path(ui_folder, "BP_SanIgnaHUD"))

game_mode_bp = library.load_asset(game_mode)
unreal.get_default_object(library.load_blueprint_class(game_mode)).set_editor_property("hud_class", library.load_blueprint_class(asset_path(ui_folder, "BP_SanIgnaHUD")))
finish(game_mode_bp, game_mode)

print("controller data:")
for name, *_ in CONTROLLERS:
    data = unreal.get_default_object(library.load_blueprint_class(asset_path(input_folder, name)))
    brushes = data.get_editor_property("input_brush_data_map")
    print(f"  {name}: {data.get_editor_property('input_type')} {data.get_editor_property('gamepad_name')} glyphs={len(brushes)} first={brushes[0].export_text()[:120] if brushes else None}")
print("check pause mapping", unreal.get_default_object(library.load_blueprint_class(asset_path(ui_folder, "WBP_Pause"))).get_editor_property("input_mapping"))
print("check hud", unreal.get_default_object(library.load_blueprint_class(game_mode)).get_editor_property("hud_class"))
