import unreal

library = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()

folder = "/Game/SanIgna/Characters/Protagonist"
path = f"{folder}/CS_Run"

if not library.does_asset_exist(path):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.CameraShakeBase)
    tools.create_asset("CS_Run", folder, unreal.Blueprint, factory)

blueprint = library.load_asset(path)
shake = unreal.get_default_object(library.load_blueprint_class(path))
shake.set_editor_property("single_instance", True)

pattern = unreal.new_object(unreal.PerlinNoiseCameraShakePattern, outer=shake, name="RunNoise")
pattern.set_editor_property("duration", 0.0)
pattern.set_editor_property("blend_in_time", 0.3)
pattern.set_editor_property("blend_out_time", 0.4)
for multiplier in ["location_amplitude_multiplier", "location_frequency_multiplier", "rotation_amplitude_multiplier", "rotation_frequency_multiplier"]:
    pattern.set_editor_property(multiplier, 1.0)


def shaker(amplitude, frequency):
    value = unreal.PerlinNoiseShaker()
    value.set_editor_property("amplitude", amplitude)
    value.set_editor_property("frequency", frequency)
    return value


pattern.set_editor_property("pitch", shaker(0.35, 6.0))
pattern.set_editor_property("yaw", shaker(0.25, 4.0))
pattern.set_editor_property("roll", shaker(0.2, 3.0))
pattern.set_editor_property("z", shaker(0.8, 5.0))
shake.set_editor_property("root_shake_pattern", pattern)

unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
print(f"{path}: saved={library.save_asset(path, only_if_is_dirty=False)}")

check = unreal.get_default_object(library.load_blueprint_class(path)).get_editor_property("root_shake_pattern")
print("check pattern", check.get_class().get_name() if check else None)
if check:
    print("check pitch", check.get_editor_property("pitch").get_editor_property("amplitude"))
    print("check multipliers", check.get_editor_property("rotation_amplitude_multiplier"), check.get_editor_property("location_amplitude_multiplier"), check.get_editor_property("rotation_frequency_multiplier"), check.get_editor_property("location_frequency_multiplier"))
