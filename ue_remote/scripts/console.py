import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()

for name in ARGS.get("get", []):
    value = unreal.SystemLibrary.get_console_variable_string_value(name)
    print(f"{name} = {value!r}")

for command in ARGS.get("run", []):
    unreal.SystemLibrary.execute_console_command(world, command)
    print(f"ran: {command}")
