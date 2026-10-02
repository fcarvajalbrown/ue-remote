import unreal

roots = ARGS.get("path", ["/Game"])
asset_data = []
for root in roots:
    for path in unreal.EditorAssetLibrary.list_assets(root, recursive=True):
        asset_data.append(unreal.EditorAssetLibrary.find_asset_data(path))

validator = unreal.get_editor_subsystem(unreal.EditorValidatorSubsystem)
settings = unreal.ValidateAssetsSettings()
settings.set_editor_property("show_if_no_failures", False)
settings.set_editor_property("skip_excluded_directories", True)
failures, results = validator.validate_assets_with_settings(asset_data, settings)
for field in ("num_requested", "num_checked", "num_valid", "num_invalid", "num_skipped", "num_warnings", "num_unable_to_validate"):
    print(f"{field}: {results.get_editor_property(field)}")
print(f"failures: {failures}. Details are in the editor's Message Log under Asset Check.")
