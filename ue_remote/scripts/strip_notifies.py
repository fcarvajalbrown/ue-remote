import unreal

library = unreal.AnimationLibrary
names = ARGS["name"]

for path in ARGS["asset"]:
    animation = unreal.EditorAssetLibrary.load_asset(path)
    before = len(library.get_animation_notify_events(animation))
    for name in names:
        library.remove_animation_notify_events_by_name(animation, name)
    for track in library.get_animation_notify_track_names(animation):
        if not library.get_animation_notify_events_for_track(animation, track):
            library.remove_animation_notify_track(animation, track)
    after = len(library.get_animation_notify_events(animation))
    saved = unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    print(f"{path}: {before} -> {after} notifies, saved={saved}")
