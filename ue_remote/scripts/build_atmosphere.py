import json

import unreal

manifest = json.load(open(ARGS["manifest"][0], encoding="utf-8"))
root = ARGS.get("root", ["/Game"])[0].rstrip("/")
map_path = ARGS.get("map", [None])[0]
ground_label = ARGS.get("ground_label", ["terrain"])[0]
world_spec = manifest["world"]
content = manifest.get("content", {})
folder = f"{world_spec.get('folder_root', 'World')}/Atmosphere"
function_folder = f"{root}/{content.get('atmosphere_folder', '')}"

library = unreal.EditorAssetLibrary
actors_library = unreal.EditorLevelLibrary


def pascal(text):
    return "".join(part.capitalize() for part in text.split("_"))


def plugin_loaded(module):
    return unreal.find_object(None, f"/Script/{module}") is not None


def vector(values):
    return unreal.Vector(values[0], values[1], values[2])


def color(values):
    return unreal.LinearColor(values[0], values[1], values[2], 1.0)


def srgb(values):
    return unreal.Color(r=int(values[0] * 255), g=int(values[1] * 255), b=int(values[2] * 255), a=255)


def set_properties(target, values):
    for name, value in values.items():
        try:
            target.set_editor_property(name, value)
        except Exception as error:
            print(f"property {name}: {error}")


def make_movable(actor, component_class):
    actor.get_component_by_class(component_class).set_mobility(unreal.ComponentMobility.MOVABLE)


def label(actor, name):
    actor.set_actor_label(name)
    actor.set_folder_path(folder)


def assign_light_function(component, apply_to):
    for entry in world_spec.get("light_functions", []):
        if entry["apply_to"] != apply_to:
            continue
        asset = library.load_asset(f"{function_folder}/MI_LF_{pascal(entry['id'])}")
        if asset is None:
            print(f"WARNING light function MI_LF_{pascal(entry['id'])} is missing, build the light function materials first")
            return
        component.set_editor_property("light_function_material", asset)
        print(f"light function {entry['id']} on {apply_to}")


def terrain_z(x, y):
    actors = actors_library.get_all_level_actors()
    ground = [a for a in actors if a.get_actor_label() == ground_label]
    if not ground:
        return 0.0
    ignored = [a for a in actors if a != ground[0]]
    start, end = unreal.Vector(x * 100, -y * 100, 20000), unreal.Vector(x * 100, -y * 100, -20000)
    hit = unreal.SystemLibrary.line_trace_single(actors_library.get_editor_world(), start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored, unreal.DrawDebugTrace.NONE, True)
    return hit.to_tuple()[4].z / 100.0 if hit and hit.to_tuple()[0] else 0.0


def place_sky():
    spec = world_spec["sky"]
    sky_class = library.load_blueprint_class(spec["blueprint"])
    if sky_class is None:
        print(f"WARNING sky blueprint {spec['blueprint']} is missing in this project: no sky placed")
        return None
    actor = actors_library.spawn_actor_from_class(sky_class, vector(spec["location"]))
    actor.set_actor_scale3d(unreal.Vector(spec["scale"], spec["scale"], spec["scale"]))
    label(actor, "Sky")
    for name, value in spec.items():
        if name in ("blueprint", "location", "scale"):
            continue
        try:
            current = actor.get_editor_property(name)
            if isinstance(value, str):
                value = getattr(type(current), value)
            actor.set_editor_property(name, value)
            print(f"sky {name} = {value}")
        except Exception as error:
            print(f"sky {name}: {error}")
    return actor


def moon_rotation(sky, night):
    name = night.get("moon_mesh_component")
    if sky is not None and name:
        for component in sky.get_components_by_class(unreal.StaticMeshComponent):
            if component.get_name() == name:
                return unreal.MathLibrary.find_look_at_rotation(component.get_world_location(), unreal.Vector(0, 0, 0))
    return unreal.Rotator(0.0, night["moon_pitch"], night["moon_yaw"])


def place_lighting(sky):
    night = world_spec["night"]
    moon = actors_library.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 5000), moon_rotation(sky, night))
    moon_component = moon.get_component_by_class(unreal.DirectionalLightComponent)
    set_properties(moon_component, {"intensity": night["moon_light_intensity"], "light_color": srgb(night["moon_light_color"])})
    make_movable(moon, unreal.DirectionalLightComponent)
    assign_light_function(moon_component, "moon")
    label(moon, "MoonLight")
    sky_light = actors_library.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 6000))
    sky_component = sky_light.get_component_by_class(unreal.SkyLightComponent)
    set_properties(sky_component, {"intensity": night["sky_light_intensity"], "real_time_capture": False})
    make_movable(sky_light, unreal.SkyLightComponent)
    sky_component.recapture_sky()
    label(sky_light, "SkyLight")
    volume = actors_library.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    volume.set_editor_property("unbound", True)
    settings = volume.get_editor_property("settings")
    set_properties(settings, {
        "override_auto_exposure_min_brightness": True, "auto_exposure_min_brightness": night["exposure_min"],
        "override_auto_exposure_max_brightness": True, "auto_exposure_max_brightness": night["exposure_max"],
    })
    volume.set_editor_property("settings", settings)
    label(volume, "Exposure")


def place_fog():
    spec = world_spec["fog"]
    fog = actors_library.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, spec["height"]))
    set_properties(fog.get_component_by_class(unreal.ExponentialHeightFogComponent), {
        "fog_density": spec["density"], "fog_height_falloff": spec["height_falloff"], "start_distance": spec["start_distance"],
        "fog_max_opacity": spec["max_opacity"], "fog_inscattering_luminance": color(spec["color"]),
        "enable_volumetric_fog": spec["volumetric"], "volumetric_fog_scattering_distribution": 0.2,
        "volumetric_fog_distance": spec["volumetric_distance"], "volumetric_fog_albedo": srgb(spec["albedo"]),
        "directional_inscattering_luminance": color(spec["directional_color"]), "directional_inscattering_exponent": spec["directional_exponent"],
    })
    label(fog, "Fog")
    cvars = spec.get("cvars", {})
    if cvars and not plugin_loaded("ScreenSpaceFogScattering"):
        print("WARNING ScreenSpaceFogScattering is not loaded: plain exponential height fog, r.SSFS settings skipped")
        return
    for variable, value in cvars.items():
        unreal.SystemLibrary.execute_console_command(None, f"{variable} {value}")
        print(f"cvar {variable} = {unreal.SystemLibrary.get_console_variable_float_value(variable)}")


def place_lanterns():
    for lantern in world_spec["lanterns"]:
        x, y, z = lantern["at"]
        actor = actors_library.spawn_actor_from_class(unreal.PointLight, unreal.Vector(x * 100, -y * 100, (terrain_z(x, y) + z) * 100))
        component = actor.get_component_by_class(unreal.PointLightComponent)
        set_properties(component, {
            "intensity": lantern["intensity"], "light_color": srgb(lantern["color"]), "attenuation_radius": lantern["radius"],
            "volumetric_scattering_intensity": lantern["scatter"], "cast_shadows": False,
        })
        make_movable(actor, unreal.PointLightComponent)
        assign_light_function(component, "lanterns")
        label(actor, f"Lantern_{lantern['id']}")


def place_player_start():
    spec = world_spec["player_start"]
    x, y, z = spec["at"]
    start = actors_library.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(x * 100, -y * 100, z * 100), unreal.Rotator(0.0, 0.0, spec["yaw"]))
    label(start, "PlayerStart")


def convert(current, value):
    if isinstance(current, unreal.Color):
        return unreal.Color(r=int(value[0]), g=int(value[1]), b=int(value[2]), a=int(value[3]) if len(value) > 3 else 255)
    if isinstance(current, unreal.LinearColor):
        return unreal.LinearColor(value[0], value[1], value[2], value[3] if len(value) > 3 else 1.0)
    if isinstance(current, unreal.Vector4):
        return unreal.Vector4(*value)
    if isinstance(current, unreal.EnumBase):
        return getattr(type(current), value)
    if isinstance(value, str) and not isinstance(current, str):
        asset = library.load_asset(value) if value.startswith("/") else None
        if asset is None:
            raise ValueError(f"asset {value} not found")
        return asset
    return value


def apply_raw(target, values, override_flags=False):
    failed = []
    for name, value in values.items():
        try:
            target.set_editor_property(name, convert(target.get_editor_property(name), value))
            if override_flags:
                try:
                    target.set_editor_property(f"override_{name}", True)
                except Exception:
                    pass
            print(f"  {name} = {target.get_editor_property(name)}")
        except Exception as error:
            failed.append(name)
            print(f"  SKIPPED {name}: {error}")
    return failed


def place_raw_sky_light(values):
    actor = actors_library.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 6000))
    component = actor.get_component_by_class(unreal.SkyLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    print("sky light")
    failed = apply_raw(component, values)
    if "cubemap" in failed:
        component.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_CAPTURED_SCENE)
        print("  WARNING cubemap missing: source type set to captured scene")
    component.recapture_sky()
    label(actor, "SkyLight")


def place_raw_height_fog(values):
    actor = actors_library.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0))
    print("height fog")
    apply_raw(actor.get_component_by_class(unreal.ExponentialHeightFogComponent), values)
    label(actor, "ExponentialHeightFog")


def place_raw_sky_atmosphere(values):
    actor = actors_library.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
    print("sky atmosphere")
    apply_raw(actor.get_component_by_class(unreal.SkyAtmosphereComponent), values)
    label(actor, "SkyAtmosphere")


def place_raw_post_process(spec):
    volume = actors_library.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    print("post process")
    for name in ("priority", "unbound", "blend_weight"):
        if name in spec:
            volume.set_editor_property(name, spec[name])
    settings = volume.get_editor_property("settings")
    apply_raw(settings, spec.get("settings", {}), override_flags=True)
    volume.set_editor_property("settings", settings)
    label(volume, "GlobalPostProcessVolume")


sky = place_sky() if "sky" in world_spec else None
if "sky_light" in world_spec:
    place_raw_sky_light(world_spec["sky_light"])
if "height_fog" in world_spec:
    place_raw_height_fog(world_spec["height_fog"])
if "sky_atmosphere" in world_spec:
    place_raw_sky_atmosphere(world_spec["sky_atmosphere"])
if "post_process" in world_spec:
    place_raw_post_process(world_spec["post_process"])
if "night" in world_spec:
    place_lighting(sky)
if "fog" in world_spec:
    place_fog()
if "lanterns" in world_spec:
    place_lanterns()
if "player_start" in world_spec:
    place_player_start()
if map_path:
    library.make_directory(map_path.rsplit("/", 1)[0])
    print("saved map", unreal.EditorLoadingAndSavingUtils.save_map(actors_library.get_editor_world(), map_path))
print("actors", len(actors_library.get_all_level_actors()))
