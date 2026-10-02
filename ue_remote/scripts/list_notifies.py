import unreal

library = unreal.AnimationLibrary

for path in ARGS["asset"]:
    animation = unreal.EditorAssetLibrary.load_asset(path)
    print(path)
    for track in library.get_animation_notify_track_names(animation):
        for event in library.get_animation_notify_events_for_track(animation, track):
            notify = event.get_editor_property("notify")
            state = event.get_editor_property("notify_state_class")
            source = notify or state
            print(
                f"    track {track}"
                f"  t={library.get_anim_notify_event_trigger_time(event):.3f}"
                f"  name {event.get_editor_property('notify_name')}"
                f"  class {source.get_class().get_path_name() if source else None}"
            )
