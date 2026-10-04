import os

import unreal

library = unreal.EditorAssetLibrary
registry = unreal.AssetRegistryHelpers.get_asset_registry()
options = unreal.AssetRegistryDependencyOptions()
options.set_editor_property("include_hard_package_references", True)
options.set_editor_property("include_soft_package_references", True)

confirm = ARGS.get("confirm", ["0"])[0] == "1"
fix_redirectors = ARGS.get("fix_redirectors", ["1"])[0] == "1"
fix_maps = ARGS.get("fix_maps", ["0"])[0] == "1"
allow_root = ARGS.get("allow_root", ["0"])[0] == "1"
roots = [path.rstrip("/") for path in ARGS.get("path", [])]
extra = [path.split(".")[0] for path in ARGS.get("asset", [])]
MAX_ROUNDS = 6


def class_of(package):
    data = library.find_asset_data(package)
    return str(data.asset_class_path.asset_name) if data and data.is_valid() else ""


def referencers(package):
    return {str(name) for name in registry.get_referencers(package, options) or [] if not str(name).startswith("/Script")}


def default_object(package):
    return f"{package}.{package.rsplit('/', 1)[1]}"


def objects_from_roots():
    found = set()
    for root in roots:
        found |= set(library.list_assets(root, recursive=True, include_folder=False))
    return found | {default_object(package) for package in extra}


def packages_of(objects):
    return {path.split(".")[0] for path in objects}


def check_roots():
    for root in roots:
        if len(root.strip("/").split("/")) < 2 and not allow_root:
            raise SystemExit(f"{root} is a project root; give a subfolder or add --arg allow_root=1")


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


def resave(package):
    if class_of(package) == "World":
        return resave_map(package)
    asset = library.load_asset(package)
    if asset is None:
        return "unloadable"
    return "saved" if library.save_loaded_asset(asset) else "not saved"


def resolve(targets):
    fixed, maps, dangling = {}, set(), set()
    for _ in range(MAX_ROUNDS):
        changed = False
        for package in sorted(targets):
            for referencer in sorted(referencers(package) - targets):
                if class_of(referencer) == "ObjectRedirector" and class_of(package) != "ObjectRedirector":
                    if not referencers(referencer) - targets:
                        dangling.add(referencer)
                        targets = targets | {referencer}
                        changed = True
                    continue
                if class_of(package) != "ObjectRedirector" or not fix_redirectors or referencer in fixed or referencer in maps:
                    continue
                if class_of(referencer) == "World" and not fix_maps:
                    maps.add(referencer)
                elif not confirm:
                    fixed[referencer] = "would resave"
                else:
                    outcome = resave(referencer)
                    if outcome.startswith("refused"):
                        maps.add(referencer)
                        print(f"map {referencer}: {outcome}")
                    else:
                        fixed[referencer] = outcome
                        changed = changed or outcome == "saved"
        if not changed:
            break
    pending = {referencer for referencer, outcome in fixed.items() if outcome == "would resave"}
    blocked = {}
    for package in targets:
        outside = referencers(package) - targets - pending
        if outside:
            blocked[package] = outside
    return targets, fixed, maps, blocked, dangling


def content_path_to_disk(folder):
    base = unreal.SystemLibrary.get_project_content_directory()
    return os.path.normpath(os.path.join(base, folder[len("/Game/"):]))


def remove_empty_folders(root):
    folders = [p for p in library.list_assets(root, recursive=True, include_folder=True) if "." not in p.rsplit("/", 1)[-1]]
    for folder in sorted(folders, key=len, reverse=True):
        if not library.list_assets(folder, recursive=True, include_folder=False):
            library.delete_directory(folder)
    if library.does_directory_exist(root) and not library.list_assets(root, recursive=True, include_folder=False):
        library.delete_directory(root)
    disk = content_path_to_disk(root)
    if os.path.isdir(disk):
        for current, _, _ in sorted(os.walk(disk), key=lambda item: len(item[0]), reverse=True):
            try:
                os.rmdir(current)
            except OSError:
                pass


check_roots()
registry.scan_paths_synchronous(roots + [path.rsplit("/", 1)[0] for path in extra], True)
registry.wait_for_completion()
objects = objects_from_roots()
targets = packages_of(objects)
if not targets:
    if confirm:
        for root in roots:
            remove_empty_folders(root)
        raise SystemExit(f"no assets under the given paths; removed empty folders, left: {[r for r in roots if library.does_directory_exist(r)]}")
    raise SystemExit("no assets under the given paths; rerun with --arg confirm=1 to remove the empty folders")

targets, fixed, maps, blocked, dangling = resolve(targets)
objects |= {default_object(package) for package in dangling}
redirectors = sorted(p for p in targets if class_of(p) == "ObjectRedirector")

for package in sorted(targets):
    print(f"{package} [{class_of(package)}]")
print(f"{len(targets)} assets targeted, {len(redirectors)} of them redirectors, {len(dangling)} outside redirectors added because they would dangle")
for referencer, outcome in sorted(fixed.items()):
    print(f"fixed reference in {referencer}: {outcome}")
for referencer in sorted(maps):
    print(f"MAP {referencer} references a redirector; add --arg fix_maps=1 to resave it, or open it and save it")

if blocked or maps:
    for package, outside in sorted(blocked.items()):
        print(f"BLOCKED {package} is referenced by {sorted(outside)}")
    raise SystemExit("nothing deleted: assets outside the target set still depend on these")

if not confirm:
    print("preview only; nothing deleted. Rerun with --arg confirm=1 to delete")
else:
    failed = []
    for path in sorted(objects, key=lambda p: class_of(p.split(".")[0]) != "ObjectRedirector"):
        if library.does_asset_exist(path) and not library.delete_asset(path):
            failed.append(path)
    for root in roots:
        remove_empty_folders(root)
    print(f"deleted {len(objects) - len(failed)} of {len(objects)} objects in {len(targets)} packages")
    for package in failed:
        print(f"FAILED {package}")
    print(f"folders left: {[root for root in roots if library.does_directory_exist(root)]}")
