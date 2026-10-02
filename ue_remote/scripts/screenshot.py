import unreal

name = ARGS.get("name", ["ue_remote"])[0]
width, height = (int(v) for v in ARGS.get("size", ["1280x800"])[0].lower().split("x"))

unreal.AutomationLibrary.take_high_res_screenshot(width, height, f"{name}.png")
folder = unreal.Paths.convert_relative_path_to_full(unreal.Paths.screen_shot_dir())
print(f"{folder}{name}.png ({width}x{height}) is written on the next frame the viewport renders; a backgrounded editor may not render")
