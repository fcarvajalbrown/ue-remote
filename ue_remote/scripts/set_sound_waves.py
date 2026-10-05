import unreal

path = ARGS["path"][0].rstrip("/")
compression = ARGS.get("compression", [None])[0]
quality = ARGS.get("quality", [None])[0]
loading = ARGS.get("loading", [None])[0]
looping = ARGS.get("looping", [None])[0]
apply = ARGS.get("apply", ["0"])[0] == "1"

changes = {}
if compression:
    changes["sound_asset_compression_type"] = getattr(unreal.SoundAssetCompressionType, compression.upper())
if quality:
    changes["compression_quality"] = int(quality)
if loading:
    changes["loading_behavior"] = getattr(unreal.SoundWaveLoadingBehavior, loading.upper())
if looping:
    changes["looping"] = looping == "1"

registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = [data for data in registry.get_assets_by_path(path, recursive=True)
          if str(data.asset_class_path.asset_name) == "SoundWave"]
for data in sorted(assets, key=lambda item: str(item.package_name)):
    wave = data.get_asset()
    before = {name: wave.get_editor_property(name) for name in changes}
    print(f"{data.package_name}: {before} -> {changes if changes else 'no change requested'}"
          f" ({wave.get_editor_property('duration'):.2f} s, {wave.get_editor_property('sample_rate')} Hz,"
          f" {wave.get_editor_property('num_channels')} ch)")
    if apply and changes:
        for name, value in changes.items():
            wave.set_editor_property(name, value)
        unreal.EditorAssetLibrary.save_loaded_asset(wave, only_if_is_dirty=False)
print(f"{len(assets)} sound waves under {path}, {'applied' if apply else 'preview only, apply=1 writes'}")
