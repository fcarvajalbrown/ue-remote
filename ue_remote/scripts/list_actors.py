import unreal

class_filter = [c.lower() for c in ARGS.get("class", [])]
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()

print(f"level: {world.get_path_name() if world else None}")
shown = 0
for actor in sorted(actors, key=lambda a: a.get_actor_label()):
    class_name = actor.get_class().get_name()
    if class_filter and class_name.lower() not in class_filter:
        continue
    location = actor.get_actor_location()
    print(f"{actor.get_actor_label():40} {class_name:32} ({location.x:.0f}, {location.y:.0f}, {location.z:.0f})")
    shown += 1
print(f"{shown} of {len(actors)} actors")
