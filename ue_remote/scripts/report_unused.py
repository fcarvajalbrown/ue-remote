import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()
options = unreal.AssetRegistryDependencyOptions()
roots = ARGS.get("path", ["/Game"])

unused = []
for root in roots:
    packages = sorted({p.split(".")[0] for p in unreal.EditorAssetLibrary.list_assets(root, recursive=True)})
    for package in packages:
        referencers = [str(r) for r in registry.get_referencers(package, options) or [] if str(r) != package]
        if not referencers:
            unused.append(package)

for package in unused:
    print(package)
print(f"{len(unused)} assets with no referencers under {', '.join(roots)}")
