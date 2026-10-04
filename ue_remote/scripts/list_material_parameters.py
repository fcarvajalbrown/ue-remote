import unreal

library = unreal.MaterialEditingLibrary

for path in ARGS["asset"]:
    instance = unreal.EditorAssetLibrary.load_asset(path)
    print(f"{path}: {type(instance).__name__}, parent {instance.get_editor_property('parent').get_path_name()}")
    for name in library.get_scalar_parameter_names(instance):
        print(f"  scalar {name} = {library.get_material_instance_scalar_parameter_value(instance, name)}")
    for name in library.get_vector_parameter_names(instance):
        print(f"  vector {name} = {library.get_material_instance_vector_parameter_value(instance, name)}")
    for name in library.get_texture_parameter_names(instance):
        texture = library.get_material_instance_texture_parameter_value(instance, name)
        print(f"  texture {name} = {texture.get_path_name() if texture else None}")
