import unreal

library = unreal.EditorAssetLibrary
suffix = ARGS.get("suffix", [""])[0]
prefix = ARGS.get("prefix", [""])[0]

assets = []
for path in ARGS["asset"]:
    data = library.find_asset_data(path)
    if not data.is_valid():
        raise SystemExit(f"asset not found: {path}")
    assets.append(data)

source_mesh = library.load_asset(ARGS["source_mesh"][0])
target_mesh = library.load_asset(ARGS["target_mesh"][0])
retargeter = library.load_asset(ARGS["retargeter"][0])
for label, value in (("source_mesh", source_mesh), ("target_mesh", target_mesh), ("retargeter", retargeter)):
    if not value:
        raise SystemExit(f"could not load {label}")

results = unreal.IKRetargetBatchOperation.duplicate_and_retarget(
    assets, source_mesh, target_mesh, retargeter, "", "", prefix, suffix, True
)
for data in results:
    print(f"{data.package_name}  ({data.asset_class_path.asset_name})")
print(f"{len(results)} assets created")
