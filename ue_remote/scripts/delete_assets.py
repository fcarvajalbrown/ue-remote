import unreal

library = unreal.EditorAssetLibrary
registry = unreal.AssetRegistryHelpers.get_asset_registry()
options = unreal.AssetRegistryDependencyOptions()
confirm = ARGS.get("confirm", ["0"])[0] == "1"

targets = set()
for path in ARGS.get("path", []):
    targets |= {p.split(".")[0] for p in library.list_assets(path, recursive=True)}
targets |= {p.split(".")[0] for p in ARGS.get("asset", [])}
targets = sorted(targets)

blocked = {}
for package in targets:
    outside = [str(r) for r in registry.get_referencers(package, options) or [] if str(r) not in targets]
    if outside:
        blocked[package] = outside

for package in targets:
    print(package)
print(f"{len(targets)} assets targeted")

if blocked:
    for package, referencers in blocked.items():
        print(f"BLOCKED {package} is referenced by {referencers}")
    raise SystemExit("nothing deleted: assets outside the target set still reference these")

if not confirm:
    print("preview only; nothing deleted. Rerun with --arg confirm=1 to delete")
else:
    for package in targets:
        print(f"{package}: deleted={library.delete_asset(package)}")
    for path in ARGS.get("path", []):
        if not library.list_assets(path, recursive=True, include_folder=False):
            print(f"{path}: folder removed={library.delete_directory(path)}")
