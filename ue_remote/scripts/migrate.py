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
destination = ARGS["destination"][0]
dry_run = ARGS.get("dry_run", ["1"])[0] == "1"

roots = []
for path in ARGS.get("path", []):
    roots += sorted({p.split(".")[0] for p in library.list_assets(path, recursive=True)})
roots += [p.split(".")[0] for p in ARGS.get("asset", [])]

closure, pending = set(), list(roots)
while pending:
    package = pending.pop()
    if package in closure or not package.startswith("/Game/"):
        continue
    closure.add(package)
    pending += [str(d) for d in registry.get_dependencies(package, options) or []]

for package in sorted(closure):
    print(package)
print(f"{len(roots)} requested, {len(closure)} packages including dependencies -> {destination}")

if dry_run:
    print("dry run; pass --arg dry_run=0 to copy")
else:
    migration = unreal.MigrationOptions()
    migration.set_editor_property("prompt", False)
    migration.set_editor_property("ignore_dependencies", False)
    migration.set_editor_property("asset_conflict", unreal.AssetMigrationConflict.SKIP)
    unreal.AssetToolsHelpers.get_asset_tools().migrate_packages(roots, destination, migration)
    print("migrate_packages returned; existing files at the destination were skipped, never overwritten")
