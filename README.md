<p align="center"><img src="logo.svg" width="96" alt="unreal-engine-python-tools logo"></p>

# unreal-engine-python-tools

Python tools for Unreal Engine 5: run scripts inside a running editor from the command line, plus
the side tools a small game project ends up needing. OpenStreetMap to DXF for city blockouts,
dither textures, Markdown to PDF and art-reference albums.

Built while making a third-person game in UE 5.5 set in a real Chilean town, and tested on that
project's content.

## What's inside

| Folder | What it does |
|---|---|
| `ue_remote/` | CLI that runs Python in an open Unreal Editor through Epic's Remote Execution, plus 26 editor scripts |
| `citygen/` | OpenStreetMap streets and building footprints to a layered R12 DXF for SketchUp, with Microsoft building footprints to fill the gaps |
| `textures/` | Ordered-dither (Bayer) threshold texture as a PNG, for 1-bit and retro post-process materials |
| `docs_tools/` | Markdown to PDF through headless Edge, tables kept whole across pages |
| `moodboard/` | Art-reference albums from itch.io or Steam screenshots, as HTML and PDF |
| `meshkit/` | Small procedural mesh kit: primitives, walls with openings, shingle and corrugated roofs, GLB writer |

No pip packages for anything except `citygen/`, which needs `shapely` and `numpy`, and `meshkit/`, which needs `numpy`.

## ue_remote

Talks to the editor with Epic's own `remote_execution.py` from the Python Script Plugin, so nothing
gets installed into your project.

1. In the editor: Project Settings → Plugins → Python → enable **Remote Execution**, and set the
   multicast bind address to `127.0.0.1`.
2. Point the CLI at your engine with `--engine` or the `UE_ROOT` environment variable.

```
python ue_remote/ue_remote.py list
python ue_remote/ue_remote.py exec MyProject -c "import unreal; print(unreal.SystemLibrary.get_engine_version())"
python ue_remote/ue_remote.py exec MyProject -f ue_remote/scripts/list_assets.py --arg path=/Game/Characters
```

`--arg key=value` can repeat; the script reads it as `ARGS["key"]`, always a list. In Git Bash, set
`MSYS_NO_PATHCONV=1` or `/Game/...` arguments get rewritten into Windows paths.

Some of the scripts:

| Script | Job |
|---|---|
| `list_assets.py`, `list_actors.py` | Inventory a folder or the open level |
| `report_unused.py`, `validate_assets.py`, `engine_refs.py` | Find unused assets, broken ones, and anything that pulls engine content into a shipping build |
| `mesh_budget.py`, `texture_audit.py` | Triangle and texture-size budgets |
| `move_assets.py`, `move_folder.py`, `fix_redirectors.py` | Move assets and folders, then fix up the redirectors a move leaves |
| `delete_assets.py` | Delete with a preview first; refuses when something outside still references the asset |
| `retarget_batch.py`, `strip_notifies.py`, `migrate.py` | Animation retargeting and clean migration between projects |
| `make_look_materials.py` | Builds two post-process materials: a soft 1-bit dither in the style of Return of the Obra Dinn, and a PS2-era look |
| `material_stats.py` | Pixel-shader instruction count, a quick check that a material compiled |
| `screenshot.py`, `console.py` | High-res screenshot, read or run console variables |
| `set_camera.py`, `shots.py` | Move the editor camera and save one screenshot per view, from a list or an orbit |
| `import_manifest.py` | Import the GLB files listed in a JSON manifest as static meshes with LODs, collision and tinted material instances |
| `make_light_functions.py` | Build light-function materials (drifting noise, flicker) and instances from a JSON spec |
| `setup_ui.py` | Sets up CommonUI in one run: click and back input actions with their mapping context, the input data asset, controller data for keyboard and mouse, an Xbox-style gamepad and the Steam Deck (glyphs from Kenney's CC0 input prompts), and Blueprint children of a C++ root widget, pause screen and HUD. The paths and class names come from the game it was written for; change them for yours |

## citygen

```
cd citygen
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python citygen/run.py
.venv/Scripts/python citygen/ms_buildings.py
.venv/Scripts/python citygen/draw_streets.py
```

The bounding box is `SAN_IGNACIO_BBOX` in `citygen/osm.py`; change it for your town. Output lands in
`citygen/out/`: block faces, property lines inset from the street centreline, kerbs, and building
footprints on two layers (`EDIFICIO_OSM`, `EDIFICIO_MS`) as closed polylines you can push/pull in
SketchUp. Microsoft footprints that overlap an OSM one by 20% or more are dropped. Neither source gave
building heights for the town it was built for, so heights are left to you.

`preview_dxf.py` renders any layer of the DXF to PNG, so you can check the geometry before trusting
it. `flat_svg.py` writes a flat SVG map of streets and footprints.

## meshkit

A few hundred lines of numpy that turn a JSON description into low-poly meshes. `parts.build_piece` takes a list of primitives (`box`, `cyl`, `extrude` for any outline including concave ones, `tube`, `wall` with door and window openings, `roof_slope` in shingle or corrugated style, `repeat`) and returns one mesh per group. `write_glb` writes a GLB with flat normals, box-projected UVs and one named material per colour.

```
import sys
sys.path.insert(0, "meshkit")
import meshkit, parts

piece = parts.build_piece({"parts": [{"t": "box", "m": "wood", "size": [1, 1, 1], "at": [0, 0, 0.5]}]})
meshkit.write_glb(piece["main"], "box.glb")
```

Units are metres and Z is up; the GLB is written Y-up. Unreal mirrors Y when it imports a glTF, so convert placement tables before using them in the editor.

## Importing, light functions and screenshots

`import_manifest.py` reads a manifest with `meshes` (each with an asset name, a folder, a list of GLB files where the first is LOD 0 and the rest are further LODs, a collision mode and its material names), a `content` block for prefixes and folders, and `world.lods.screen_sizes`. Meshes without extra LOD files get automatic reduction when they have 150 triangles or more. Nanite is switched off on import. Material instances are created from the parents named in a second JSON file.

```
python ue_remote/ue_remote.py exec MyProject -f ue_remote/scripts/import_manifest.py --arg manifest=out/manifest.json --arg materials=spec/materials.json --arg root=/Game/MyProject
```

`make_light_functions.py` builds two light-function materials, a drifting 3D noise and a two-sine flicker, plus one instance per entry in a JSON list. Put the drift instance on a directional light and volumetric fog shows moving patches of light; put the flicker on a point light and the glow around it pulses. In UE 5.5 the materials compile and every node is wired to the output. Nobody has confirmed the motion by eye yet.

```
python ue_remote/ue_remote.py exec MyProject -f ue_remote/scripts/make_light_functions.py --arg spec=world.json --arg key=light_functions --arg root=/Game/MyProject/Atmosphere
```

`shots.py` moves the editor camera and copies one PNG per view into a folder. Coordinates are Unreal centimetres. The editor window has to stay in the foreground or the viewport does not render.

```
python ue_remote/shots.py --project MyProject --out shots --view "house:0,5400,300>-1000,2600,250"
python ue_remote/shots.py --project MyProject --out shots --orbit 0,0,300 --radius 4000 --height 800 --count 6
```

Two things that cost time: remote execution in file mode fails with "Could not load Python file" if the script text contains `.py` followed by a space, and an asset cannot be recreated right after deleting it unless garbage is collected first.

## The rest

```
python textures/make_bayer.py --size 8 --out T_Bayer8.png
python docs_tools/md_to_pdf.py notes.md notes.pdf
python moodboard/itch_tags.py tag-abstract/tag-horror --out games.json --covers covers/
python moodboard/itch_album.py album.json out/ --pdf album.pdf
```

`md_to_pdf.py` and the album PDFs need Microsoft Edge on Windows. itch.io starts refusing requests
after a dozen or so in a row; wait and run again.

## License

MIT
