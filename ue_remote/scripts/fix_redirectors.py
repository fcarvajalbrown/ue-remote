import unreal

library = unreal.EditorAssetLibrary
registry = unreal.AssetRegistryHelpers.get_asset_registry()
options = unreal.AssetRegistryDependencyOptions()
options.set_editor_property("include_hard_package_references", True)
options.set_editor_property("include_soft_package_references", True)

confirm = ARGS.get("confirm", ["0"])[0] == "1"
fix_maps = ARGS.get("fix_maps", ["0"])[0] == "1"
roots = [path.rstrip("/") for path in ARGS.get("path", ["/Game"])]


def class_of(package):
    data = library.find_asset_data(package)
    return str(data.asset_class_path.asset_name) if data and data.is_valid() else ""


def referencers(package):
    return {str(name) for name in registry.get_referencers(package, options) or [] if not str(name).startswith("/Script")}


def resave_map(package):
    utilities = unreal.EditorLoadingAndSavingUtils
    if utilities.get_dirty_map_packages():
        return "refused: unsaved maps are open"
    original = unreal.EditorLevelLibrary.get_editor_world().get_outermost().get_name()
    if original.startswith("/Temp/"):
        return "refused: the open level is untitled"
    utilities.load_map(package)
    saved = utilities.save_map(unreal.EditorLevelLibrary.get_editor_world(), package)
    utilities.load_map(original)
    return "saved" if saved else "not saved"


registry.scan_paths_synchronous(roots, True)
registry.wait_for_completion()
redirectors = set()
for root in roots:
    for path in library.list_assets(root, recursive=True, include_folder=False):
        package = path.split(".")[0]
        if class_of(package) == "ObjectRedirector":
            redirectors.add(package)
redirectors = sorted(redirectors)
print(f"{len(redirectors)} redirectors under {roots}")

maps = {}
removable, held = [], {}
for redirector in redirectors:
    users = {user for user in referencers(redirector) if class_of(user) != "ObjectRedirector"}
    for user in sorted(users):
        if class_of(user) == "World":
            if confirm and fix_maps:
                print(f"{redirector} <- {user}: {resave_map(user)}")
            else:
                maps.setdefault(user, []).append(redirector)
            continue
        if confirm:
            asset = library.load_asset(user)
            outcome = "saved" if asset is not None and library.save_loaded_asset(asset) else "failed"
        else:
            outcome = "would resave"
        print(f"{redirector} <- {user}: {outcome}")
    remaining = {user for user in referencers(redirector) if class_of(user) != "ObjectRedirector"} if confirm else users
    if remaining:
        held[redirector] = sorted(remaining)
    else:
        removable.append(redirector)

for user, through in sorted(maps.items()):
    print(f"MAP {user} references {len(through)} redirectors; add --arg fix_maps=1 --arg confirm=1 to resave it, or open it and save it")
for redirector, users in sorted(held.items()):
    print(f"KEPT {redirector}: still referenced by {users}")

if not confirm:
    print(f"preview only: {len(removable)} redirectors are unreferenced now, the rest need their referencers resaved. Rerun with --arg confirm=1")
else:
    deleted = [package for package in removable if library.delete_asset(package)]
    print(f"deleted {len(deleted)} redirectors, {len(held)} kept")
