import unreal

library = unreal.EditorAssetLibrary
folder = ARGS["path"][0]
redirectors = []
for path in library.list_assets(folder, recursive=True, include_folder=False):
    data = library.find_asset_data(path)
    if str(data.asset_class_path.asset_name) == "ObjectRedirector":
        redirectors.append(library.load_asset(path))
        print("redirector", path)
if redirectors:
    unreal.AssetToolsHelpers.get_asset_tools().fix_up_referencers(redirectors)
print("remaining", library.list_assets(folder, recursive=True, include_folder=False))
