import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()
options = unreal.AssetRegistryDependencyOptions()

for root in ARGS["path"]:
    packages = sorted({p.split(".")[0] for p in unreal.EditorAssetLibrary.list_assets(root, recursive=True)})
    for package in packages:
        outside = lambda names: sorted(str(n) for n in names or [] if not str(n).startswith(root) and str(n).startswith("/Game"))
        print(package)
        print("    referenced by:", outside(registry.get_referencers(package, options)))
        print("    depends on:   ", outside(registry.get_dependencies(package, options)))
