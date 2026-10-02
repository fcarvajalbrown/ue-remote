import unreal

library = unreal.EditorAssetLibrary
registry = unreal.AssetRegistryHelpers.get_asset_registry()
source = ARGS["source"][0].rstrip("/")
destination = ARGS["destination"][0].rstrip("/")
dry_run = ARGS.get("dry_run", ["1"])[0] == "1"

packages = sorted({p.split(".")[0] for p in library.list_assets(source, recursive=True)})
plan = []
for package in packages:
    relative = package[len(source):]
    folder, name = (destination + relative).rsplit("/", 1)
    if library.does_asset_exist(f"{folder}/{name}"):
        raise SystemExit(f"{folder}/{name} already exists; nothing moved")
    plan.append((package, folder, name))

outside = set()
for package, _, _ in plan:
    for referencer in registry.get_referencers(package, unreal.AssetRegistryDependencyOptions()) or []:
        if not str(referencer).startswith(source + "/"):
            outside.add(str(referencer))

for package, folder, name in plan:
    print(f"{package} -> {folder}/{name}")
print(f"{len(plan)} assets; referencers outside {source} that will be resaved: {sorted(outside)}")

if dry_run:
    print("dry run; pass --arg dry_run=0 to move")
else:
    renames = [unreal.AssetRenameData(library.load_asset(p), f, n) for p, f, n in plan]
    if not unreal.AssetToolsHelpers.get_asset_tools().rename_assets(renames):
        raise SystemExit("rename_assets reported failure")
    for _, folder, name in plan:
        library.save_asset(f"{folder}/{name}", only_if_is_dirty=False)
    for referencer in sorted(outside):
        library.save_asset(referencer, only_if_is_dirty=True)
    left = library.list_assets(source, recursive=True)
    print(f"moved; {len(left)} entries left under {source}: {left}")
