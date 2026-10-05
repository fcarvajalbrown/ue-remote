import unreal

asset_path = ARGS["asset"][0]
wave_input = ARGS.get("wave_input", ["Wave"])[0]
pitch_input = ARGS.get("pitch_input", ["PitchShift"])[0]
folder, name = asset_path.rsplit("/", 1)

builders = unreal.get_engine_subsystem(unreal.MetaSoundBuilderSubsystem)
editor = unreal.get_editor_subsystem(unreal.MetaSoundEditorSubsystem)
succeeded = unreal.MetaSoundBuilderResult.SUCCEEDED


def check(result, step):
    if result != succeeded:
        raise SystemExit(f"{step} failed: {result}")


def literal(value):
    return value[0] if isinstance(value, tuple) else value


builder, on_play, on_finished, audio_outs, result = builders.create_source_builder(name, unreal.MetaSoundOutputAudioFormat.MONO, True)
check(result, "create source builder")
player, result = builder.add_node_by_class_name(unreal.MetasoundFrontendClassName("UE", "Wave Player", "Mono"), 1)
check(result, "add wave player")

wave_literal = literal(builders.create_object_meta_sound_literal(None))
wave_out, result = builder.add_graph_input_node(wave_input, "WaveAsset", wave_literal)
check(result, "add wave input")
pitch_literal = literal(builders.create_float_meta_sound_literal(0.0))
pitch_out, result = builder.add_graph_input_node(pitch_input, "Float", pitch_literal)
check(result, "add pitch input")


def player_input(pin):
    handle, result = builder.find_node_input_by_name(player, pin)
    check(result, f"find input {pin}")
    return handle


def player_output(pin):
    handle, result = builder.find_node_output_by_name(player, pin)
    check(result, f"find output {pin}")
    return handle


check(builder.connect_nodes(on_play, player_input("Play")), "connect play")
check(builder.connect_nodes(wave_out, player_input("Wave Asset")), "connect wave")
check(builder.connect_nodes(pitch_out, player_input("Pitch Shift")), "connect pitch")
check(builder.connect_nodes(player_output("Out Mono"), audio_outs[0]), "connect audio")
check(builder.connect_nodes(player_output("On Finished"), on_finished), "connect finished")

if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
    unreal.EditorAssetLibrary.delete_asset(asset_path)
asset, result = editor.build_to_asset(builder, "Brown Marco Studios", name, folder)
check(result, "build to asset")
unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
print(f"{asset_path}: inputs {wave_input} (WaveAsset), {pitch_input} (Float, semitones)")
