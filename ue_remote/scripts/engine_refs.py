import unreal

library = unreal.EditorAssetLibrary
registry = unreal.AssetRegistryHelpers.get_asset_registry()
options = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=True,
    include_hard_package_references=True,
    include_searchable_names=False,
    include_soft_management_references=False,
    include_hard_management_references=False,
)
roots = ARGS.get("path", ["/Game"])

engine_users = {}
for root in roots:
    for package in sorted({p.split(".")[0] for p in library.list_assets(root, recursive=True)}):
        for dependency in registry.get_dependencies(package, options) or []:
            name = str(dependency)
            if name.startswith("/Engine/"):
                engine_users.setdefault(name, []).append(package)

for name in sorted(engine_users):
    users = engine_users[name]
    print(f"{name}  <- {len(users)}: {', '.join(users[:3])}{' ...' if len(users) > 3 else ''}")
print(f"{len(engine_users)} /Engine packages referenced directly from {', '.join(roots)}")
