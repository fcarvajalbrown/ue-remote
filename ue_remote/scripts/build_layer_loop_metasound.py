import unreal

asset_path = ARGS["asset"][0]
layers = ARGS["layer"]
folder, name = asset_path.rsplit("/", 1)

builders = unreal.get_engine_subsystem(unreal.MetaSoundBuilderSubsystem)
editor = unreal.get_editor_subsystem(unreal.MetaSoundEditorSubsystem)
succeeded = unreal.MetaSoundBuilderResult.SUCCEEDED


def check(result, step):
    if result != succeeded:
        raise SystemExit(f"{step} failed: {result}")


def literal(value):
    return value[0] if isinstance(value, tuple) else value


def pin(handle_and_result, step):
    handle, result = handle_and_result
    check(result, step)
    return handle


builder, on_play, on_finished, audio_outs, result = builders.create_source_builder(name, unreal.MetaSoundOutputAudioFormat.STEREO, False)
check(result, "create source builder")
mixer, result = builder.add_node_by_class_name(unreal.MetasoundFrontendClassName("AudioMixer", f"Audio Mixer (Stereo, {len(layers)})", ""), 1)
check(result, "add mixer")
for index, layer in enumerate(layers):
    player, result = builder.add_node_by_class_name(unreal.MetasoundFrontendClassName("UE", "Wave Player", "Stereo"), 1)
    check(result, f"add player {layer}")
    wave_out = pin(builder.add_graph_input_node(layer, "WaveAsset", literal(builders.create_object_meta_sound_literal(None))), f"input {layer}")
    gain_out = pin(builder.add_graph_input_node(f"{layer}Gain", "Float", literal(builders.create_float_meta_sound_literal(1.0))), f"input {layer}Gain")
    check(builder.connect_nodes(on_play, pin(builder.find_node_input_by_name(player, "Play"), "play pin")), f"connect play {layer}")
    check(builder.connect_nodes(wave_out, pin(builder.find_node_input_by_name(player, "Wave Asset"), "wave pin")), f"connect wave {layer}")
    builder.set_node_input_default(pin(builder.find_node_input_by_name(player, "Loop"), "loop pin"), literal(builders.create_bool_meta_sound_literal(True)))
    check(builder.connect_nodes(pin(builder.find_node_output_by_name(player, "Out Left"), "left"), pin(builder.find_node_input_by_name(mixer, f"In {index} L"), "mix left")), f"connect left {layer}")
    check(builder.connect_nodes(pin(builder.find_node_output_by_name(player, "Out Right"), "right"), pin(builder.find_node_input_by_name(mixer, f"In {index} R"), "mix right")), f"connect right {layer}")
    check(builder.connect_nodes(gain_out, pin(builder.find_node_input_by_name(mixer, f"Gain {index}"), "mix gain")), f"connect gain {layer}")
check(builder.connect_nodes(pin(builder.find_node_output_by_name(mixer, "Out L"), "out l"), audio_outs[0]), "connect out left")
check(builder.connect_nodes(pin(builder.find_node_output_by_name(mixer, "Out R"), "out r"), audio_outs[1]), "connect out right")

if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
    unreal.EditorAssetLibrary.delete_asset(asset_path)
asset, result = editor.build_to_asset(builder, "Brown Marco Studios", name, folder)
check(result, "build to asset")
unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
print(f"{asset_path}: looping stereo layers {layers}, each with a <layer>Gain input")
