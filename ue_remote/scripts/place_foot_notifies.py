import unreal

bones = ARGS["bone"]
notify_class = unreal.load_class(None, ARGS["notify_class"][0])
track = ARGS.get("track", ["Footsteps"])[0]
contact_cm = float(ARGS.get("contact_cm", ["3"])[0])
lift_cm = float(ARGS.get("lift_cm", ["6"])[0])
samples_per_second = int(ARGS.get("rate", ["120"])[0])
apply = ARGS.get("apply", ["0"])[0] == "1"
method = ARGS.get("method", ["height"])[0]
reference = ARGS.get("reference", ["Hips"])[0]
forward = ARGS.get("forward", ["y"])[0]
reach_fraction = float(ARGS.get("reach_fraction", ["0.7"])[0])

library = unreal.AnimationLibrary
poses = unreal.AnimPoseExtensions


def heights(animation, bone, times):
    options = unreal.AnimPoseEvaluationOptions()
    values = []
    for time in times:
        pose = poses.get_anim_pose_at_time(animation, time, options)
        values.append(poses.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD).translation.z)
    return values


def sample(animation, bone, times):
    options = unreal.AnimPoseEvaluationOptions()
    axis = forward.lstrip("-")
    sign = -1.0 if forward.startswith("-") else 1.0
    values = []
    for time in times:
        pose = poses.get_anim_pose_at_time(animation, time, options)
        foot = poses.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD).translation
        root = poses.get_bone_pose(pose, reference, unreal.AnimPoseSpaces.WORLD).translation
        values.append(sign * (getattr(foot, axis) - getattr(root, axis)))
    return values


def heel_strikes(values, times):
    low, high = min(values), max(values)
    found = []
    for index in range(1, len(values) - 1):
        if values[index] >= values[index - 1] and values[index] > values[index + 1] and values[index] > low + reach_fraction * (high - low):
            found.append(times[index])
    return found, high - low


def contacts(values, times):
    floor = min(values)
    found = []
    lifted = values[0] > floor + lift_cm
    for value, time in zip(values, times):
        if value > floor + lift_cm:
            lifted = True
        elif lifted and value <= floor + contact_cm:
            found.append(time)
            lifted = False
    return found, floor


for path in ARGS["asset"]:
    animation = unreal.EditorAssetLibrary.load_asset(path)
    length = library.get_sequence_length(animation)
    count = max(2, int(length * samples_per_second))
    times = [length * index / count for index in range(count)]
    if apply:
        library.remove_animation_notify_events_by_track(animation, track)
        if track not in library.get_animation_notify_track_names(animation):
            library.add_animation_notify_track(animation, track)
    for bone in bones:
        if method == "reach":
            found, reach = heel_strikes(sample(animation, bone, times), times)
            print(f"{path} {bone}: forward reach {reach:.1f} cm from {reference}, heel strikes {[round(t, 3) for t in found]}")
        else:
            values = heights(animation, bone, times)
            found, floor = contacts(values, times)
            print(f"{path} {bone}: floor {floor:.1f} cm, range {max(values) - floor:.1f} cm, contacts {[round(t, 3) for t in found]}")
        if apply:
            for time in found:
                notify = library.add_animation_notify_event(animation, track, time, notify_class)
                notify.set_editor_property("foot_bone", bone)
    if apply:
        print(f"saved {unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)}")
