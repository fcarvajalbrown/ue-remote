<p align="center"><img src="logo.svg" width="96" alt="ue-remote logo"></p>

# ue-remote

Python tools for Unreal Engine 5: run scripts inside a running editor from the command line, plus
the side tools a small game project ends up needing. OpenStreetMap to DXF for city blockouts,
dither textures, Markdown to PDF and art-reference albums.

Built while making a third-person game in UE 5.5 set in a real Chilean town, and tested on that
project's content.

## What's inside

| Folder | What it does |
|---|---|
| `ue_remote/` | CLI that runs Python in an open Unreal Editor through Epic's Remote Execution, plus a library of editor scripts |
| `citygen/` | OpenStreetMap streets and building footprints to a layered R12 DXF for SketchUp, with Microsoft building footprints to fill the gaps, and size statistics of isolated buildings around any point |
| `textures/` | Ordered-dither (Bayer) threshold texture as a PNG, for 1-bit and retro post-process materials; `hdri_match.py` ranks Poly Haven HDRIs (CC0) by how close their sky is to the sky in a reference image (brightness, cloud contrast, saturation, cool tint); `downsize.py` shrinks exported images to the caps of a `texture_budget` spec with Lanczos filtering, keeps alpha, and renormalizes normal maps |
| `docs_tools/` | Markdown to PDF through headless Edge, tables kept whole across pages |
| `moodboard/` | Art-reference albums from itch.io or Steam screenshots, as HTML and PDF; `commons_fetch.py` searches Wikimedia Commons and downloads images with a `sources.json` record of author, licence, source page, date and SHA-256 |
| `audio/` | `listen.py` describes how an audio file sounds in text, for checking sounds without hearing them: BS.1770 loudness and true peak, a timeline of loudness, steadiness, brightness and band shares in words, transients with the band they hit, hums and whistles, a voice-rhythm heuristic, stereo correlation and mono fold-down loss, clipping, and loop seams with a search for the best loop points; `--png` adds a spectrogram sheet. Needs numpy, scipy, soundfile, and matplotlib for the sheet. `slice_bursts.py` cuts continuous takes (cloth, breathing) into one-shot bursts from a JSON spec, rejects bursts with a pitched voice (autocorrelation voicing), and levels each to a momentary LUFS target under a true-peak ceiling with Keel's BS.1770-4 meters (`--keel`, run with Keel's venv). `archive_catalog.py` lists the files of archive.org items whose names match a pattern, with licence and length; `fetch_archive_org.py` downloads an item's files, optionally filtered by name, keeps each only when its SHA-1 matches archive.org's, and writes a manifest with SHA-256 for the licence record |
| `midi/` | Writes a Type 1 MIDI file from a JSON spec: notes by name, tempo changes, markers, controller and pitch-bend moves, and controller curves from a sine, triangle, square or random LFO. Standard library only, with tests |
| `bpdump/` | Reads Blueprint `.uasset` files offline into JSON and readable summaries, and scans whole folders of projects to identify every asset by class, parent, skeleton and source file, no editor needed. `run --blueprints-only` keeps every asset whose header names a parent class, whatever its file name. `batch_zips.py` extracts a folder of pack zips and exports their Blueprints, several packs at once, starting exports only while enough RAM is free |
| `cue4export/` | `extract_wav.py` cuts the PCM WAV files embedded in `.uasset` sound waves, no editor and no decoder, standard library only. Meshes go through `ue_remote/headless_export.py`: CUE4Parse and UE Viewer read cooked game files, and editor content keeps its meshes as source models they cannot convert ("Mesh has no LOD data") |
| `meshkit/` | Spec-driven blockout kit: primitives, walls with openings, roofs, parametric whorled-branch trees, terrain, scatter, layout tables, GLB and manifest output |
| `render/` | `relief_board.py` renders a carved, painted wooden board (a title card, a name board, a sign) headless with Mitsuba 3: a greyscale mask becomes a real carved mesh, PBR wood textures plus groove darkening and worn paint are baked into maps, area lights and a thin-lens camera come from a JSON spec, and the result is tonemapped to a PNG. Runs in its own hash-pinned venv |
| `blockout/` | Architectural blockouts from real plans: fetches a plan (DWG converted with LibreDWG 0.14, GPL-3.0, downloaded from its GitHub release on first use and checked against a pinned SHA-256, never shipped here), extracts wall solids from DXF line layers and extrudes them with door and window openings cut by manifold booleans (standard door width, double doors of two leaves, stepped windows with an outer width and the plan's splay behind), and writes GLB and OBJ with every vertex on the 1 cm grid. `lines` reads the horizontal or vertical drawn lines of an elevation image in metres from a ground line; `gridsnap` snaps any manifold3d solid to the grid without opening it, keeps one material per source solid and flips diagonals inside flat faces to remove fan slivers, and with `feature_step` splits long axis-aligned creases on a shared metre lattice so thin faces such as wall tops and fascias end with no sliver triangle; `check_openings.py` verifies doors, windows and lintels in a wall mesh (OBJ or glTF Y-up with `--y-up`, per-opening `sill_m` and `wall_top_m` for lower walls under a lean-to); `combine_parts.py` joins a part set of GLBs into one file for a model check render; `check_mesh.py` checks GLB topology (watertight, winding, open and non-manifold edges, degenerate and sliver triangles, the 1 cm grid). Needs ezdxf, shapely, numpy, trimesh, opencv, manifold3d, scipy and 7-Zip; tests run with `python -m unittest discover -s tests` |

No pip packages for anything except `citygen/`, which needs `shapely` and `numpy`, and `meshkit/`, which needs `numpy`, and `render/`, which needs `mitsuba` and `numpy` from its own `requirements.txt`.

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
| `texture_budget.py` | Caps texture sizes for downloaded or 4K assets without touching the source: max size per name rule, texture group, compression and sRGB by suffix (colour, normal, packed masks), all from a JSON spec (`texture_budget.example.json`). Preview by default, `apply=1` writes and saves. Switching a texture to `TC_MASKS` breaks every material whose sampler for it is still Color or Linear Color (the material falls back to the default grey); keep `TC_DEFAULT` with sRGB off unless the samplers are set to Masks |
| `nanite_audit.py` | Lists static meshes with Nanite enabled; `apply=1` switches it off and saves |
| `list_mesh_materials.py`, `list_material_parameters.py` | Which material sits in each mesh slot, and every scalar, vector and texture parameter of a material instance with its parent |
| `export_assets.py` | Exports to FBX: listed assets (`asset=`), or every static mesh, skeletal mesh and animation sequence under a folder (`root=`, narrowed with `class=`) with its folder structure kept |
| `export_textures.py` | Export textures to PNG |
| `import_texture.py` | Import one image file as a texture (`file`, `folder`, `name`), replacing an asset of the same name, saving it, and printing the imported path and size; stops with an error if nothing was imported |
| `reimport_textures.py` | Reimports a folder of images over the existing textures of the same name, keeping their settings; refuses if any image has no matching asset. Preview by default, `apply=1` imports. With `export_textures.py` and `textures/downsize.py` it shrinks stored 4K sources: export, downsize, reimport |
| `auto_uv.py` | Auto-generate UVs on static meshes through Geometry Scripting, xatlas or patch method, then repack. Dry run by default, `dry_run=0` writes. Needs the Geometry Scripting plugin |
| `import_fonts.py` | Import a folder of `Family-Style.ttf` files as font faces and group each family into a composite font. Needs an editor helper exposed as `unreal.BMFontBuilderLibrary.create_composite_font` from a C++ editor module; without it the script stops before importing |
| `build_editor.bat` | Command line build of a project's editor target, `build_editor.bat path\to\Project.uproject`, with `UE_ROOT` pointing at the engine |
| `move_assets.py`, `move_folder.py` | Move assets and folders |
| `fix_redirectors.py` | Resave whatever still points at a redirector, then delete the redirectors nothing references; preview first |
| `relink_media.py` | After a folder move, points `FileMediaSource` assets at the new location of their video files (`old` and `new` path prefixes); `move_folder.py` does not carry raw `.mp4` files, move those on disk first. Preview by default, `apply=1` writes |
| `import_audio.py` | Imports every WAV under a folder (`source`) as sound waves into `folder`, mirroring subfolders and prefixing names (`prefix`, default `A_`), replacing assets of the same name; prints the count and any file that failed |
| `place_foot_notifies.py` | Places an anim notify class on the footfalls of walk and run clips for the given foot bones. `method=reach` (recommended) puts each one at heel strike, the foot's furthest forward point relative to a reference bone (`reference`, default `Hips`; `forward`, default `y`); the default `height` method uses foot-height contacts, which fired about 95 ms early on a retargeted walk. Sets the notify's `foot_bone`. Preview by default, `apply=1` replaces the track and saves |
| `build_wave_metasound.py` | Builds a one-shot MetaSound Source with the builder API: a Wave Player fed by a WaveAsset input (`wave_input`) and a pitch-shift input in semitones (`pitch_input`), for code that picks the wave and passes it as a parameter at play time. Mono by default, `format=stereo` for stereo waves such as UI sounds |
| `build_layer_loop_metasound.py` | Builds a looping stereo MetaSound Source that plays several stems together through an Audio Mixer: one WaveAsset input and one `<layer>Gain` float input per `layer` argument, so code can fade layers by game state (`asset=/Game/.../MS_Theme --arg layer=Core --arg layer=Synth`) |
| `resave_blueprints.py` | Lists Blueprints, Widget and Anim Blueprints under a path with their parent class from the asset registry, optionally filtered by `match`; `apply=1` resaves them, which bakes class redirects into the files after a C++ class moves or is renamed |
| `delete_assets.py` | Delete folders or assets after a read-only preview. It resaves anything still pointing at a redirector, removes redirectors that would be left dangling, refuses when a live asset depends on the target, and clears the empty folders. `fix_maps=1` also resaves the maps that reference a redirector |
| `retarget_batch.py`, `strip_notifies.py`, `migrate.py` | Animation retargeting and clean migration between projects |
| `make_look_materials.py` | Builds two post-process materials: a soft 1-bit dither in the style of Return of the Obra Dinn, and a PS2-era look |
| `set_sound_waves.py` | Sets compression type (`bink_audio`, `adpcm`, `pcm`, `opus`, `rad_audio`), compression quality, loading behaviour (`load_on_demand` streams) and looping on every SoundWave under a path, printing each wave's current values, duration, rate and channels. Preview by default, `apply=1` writes and saves |
| `material_stats.py` | Pixel-shader instruction count, a quick check that a material compiled |
| `screenshot.py`, `console.py` | High-res screenshot, read or run console variables |
| `set_ini_cvars.py` | Command line tool, not an editor script: writes console variables from a JSON spec into a project's `[SystemSettings]` and refuses while that project's editor is open. In Git Bash set `MSYS_NO_PATHCONV=1` when the section starts with `/Script/` |
| `set_camera.py`, `shots.py` | Move the editor camera and save one screenshot per view, from a list or an orbit |
| `import_manifest.py` | Import the GLB files listed in a JSON manifest as static meshes with LODs, collision and tinted material instances |
| `make_light_functions.py` | Build light-function materials (drifting noise, flicker) and instances from a JSON spec |
| `place_layout.py` | Put a layout table into a level: unique pieces as static actors, repeated ones as instanced meshes through a small Blueprint |
| `build_atmosphere.py` | Add sky, moon and sky light, exposure, fog, lanterns and a player start to the open level from the sections present in a JSON spec. The `sky_light`, `height_fog`, `sky_atmosphere` and `post_process` sections take raw engine property names (colours, vectors and enum names converted, post-process override flags set) for copying a look from a reference; a sky light whose cubemap is missing falls back to a scene capture with a warning |
| `setup_ui.py` | Sets up CommonUI in one run: click and back input actions with their mapping context, the input data asset, controller data for keyboard and mouse, an Xbox-style gamepad and the Steam Deck (glyphs from Kenney's CC0 input prompts), and Blueprint children of a C++ root widget, pause screen and HUD. The paths and class names come from the game it was written for; change them for yours |

### Headless export, no editor window

`headless_export.py` runs an editor script through `UnrealEditor-Cmd -run=pythonscript` on extracted packs, with no window and without touching an editor that is already open. It writes a throwaway project into `--work`, moves each pack's content into that project's `Content` (a rename on the same drive, undone afterwards, also after a crash on the next run), runs the script, and waits while free RAM is under `--min-free-gb`. The default script is `export_assets.py` with `root=/Game`, so every static and skeletal mesh lands as FBX in `--out/<pack>/`; `--script` and `--arg key=value` run any other script, for example `resave_blueprints.py --arg apply=1`.

```
python ue_remote/headless_export.py "E:/packs/Creatures Insects Pack" --out E:/meshes --work E:/ue-work
```

Found while building it: Unreal does not follow directory junctions in `Content`, folder names with spaces are not valid package paths (for a pack without a `Content` folder the root comes from the `/Game/` path stored in its own assets), a commandlet sees no assets until it scans the registry synchronously, and the skeletal mesh FBX exporter asserts under `-nullrhi`, so the tool uses `-AllowCommandletRendering`. A 5.5 engine cannot open packs saved in 5.6.

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

`citygen/footprint_stats.py` answers a different question: how big are the isolated houses and sheds around a point? Give it one or more `name:lat,lon` centres and it prints the area quartiles and the long and short side medians for small and large isolated buildings, using the same Overpass data.

```
python citygen/citygen/footprint_stats.py --centre town:-39.36,-71.59 --radius 5000
```

`preview_dxf.py` renders any layer of the DXF to PNG, so you can check the geometry before trusting
it. `flat_svg.py` writes a flat SVG map of streets and footprints.

## meshkit

A few hundred lines of numpy that turn a folder of JSON specs into low-poly meshes, a placement table and a manifest. `parts.build_piece` takes a list of primitives (`box`, `cyl`, `extrude` for any outline including concave ones, `tube`, `wall` with door and window openings, `roof_slope` in shingle or corrugated style, `repeat`) and returns one mesh per group. `write_glb` writes a GLB with flat normals, box-projected UVs and one named material per colour.

`trees.py` builds a tree from numbers: height, trunk radius, where the crown starts, how many whorls and how many branches per whorl, branch length and thickness from the bottom whorl to the top, how steeply branches rise and how far they curl up at the tip, and a list of LOD levels. It returns the trunk and the crown as two meshes, so the trunk can carry collision and the crown can stay without. `examples/minimal/trees.json` holds three growth stages of a monkey puzzle tree (Araucaria araucana), which is the shape it was tuned on. Nothing in the code is specific to that species.

`terrain.py` makes one static terrain mesh with flat pads under buildings and a coarser grid far away, and drapes dirt paths over the exact triangles of that mesh so they never clip. `layout.py` turns building floor plans, props, a fence run and a scattered forest into placement rows. `build_world.py` ties them together:

```
python meshkit/build_world.py --spec meshkit/examples/minimal --out out
python meshkit/preview.py --spec meshkit/examples/minimal --out out/preview.glb --ground
```

The spec folder holds `pieces.json`, `buildings.json`, `trees.json`, `world.json`, `content.json` and `materials.json`; the example is a small hut, a fence and a forest. Output is `out/meshes/*.glb`, `out/layout.csv` (centimetres, Z up, already mirrored for Unreal) and `out/manifest.json`. The same seed gives byte-identical files.

For a single piece:

```
import sys
sys.path.insert(0, "meshkit")
import meshkit, parts

piece = parts.build_piece({"parts": [{"t": "box", "m": "wood", "size": [1, 1, 1], "at": [0, 0, 0.5]}]})
meshkit.write_glb(piece["main"], "box.glb")
```

Units are metres and Z is up; the GLB is written Y-up. Unreal mirrors Y when it imports a glTF, which is why `layout.csv` is already converted.

## Importing, light functions and screenshots

`import_manifest.py` reads a manifest with `meshes` (each with an asset name, a folder, a list of GLB files where the first is LOD 0 and the rest are further LODs, a collision mode and its material names), a `content` block for prefixes and folders, and `world.lods.screen_sizes`. Meshes without extra LOD files get automatic reduction when they have 150 triangles or more. Nanite is switched off on import. Material instances are created from the parents named in a second JSON file.

```
python ue_remote/ue_remote.py exec MyProject -f ue_remote/scripts/import_manifest.py --arg manifest=out/manifest.json --arg materials=spec/materials.json --arg root=/Game/MyProject
```

`place_layout.py` reads `out/layout.csv` and the manifest, optionally creates and saves a level (`map=`), and places everything. `build_atmosphere.py` then adds whichever of `sky`, `night`, `fog`, `lanterns` and `player_start` the manifest's `world` section contains, so a project without a sky asset just skips that part. If the Screen Space Fog Scattering plugin is not loaded it leaves its settings alone and says so.

```
python ue_remote/ue_remote.py exec MyProject -f ue_remote/scripts/place_layout.py --arg manifest=out/manifest.json --arg layout=out/layout.csv --arg root=/Game/MyProject --arg map=/Game/MyProject/Maps/L_Main
python ue_remote/ue_remote.py exec MyProject -f ue_remote/scripts/build_atmosphere.py --arg manifest=out/manifest.json --arg root=/Game/MyProject --arg map=/Game/MyProject/Maps/L_Main
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

## bpdump

Reads Blueprint `.uasset` files without opening the editor, which makes Blueprints easy to review, search and diff. It drives UAssetGUI (MIT) as a separate process, downloaded once from the pinned release and checked against its SHA-256 before use.

```
python bpdump/bpdump.py fetch
python bpdump/bpdump.py run --source MyProject/Content/Blueprints --out dump
```

`fetch` saves the binary under `bpdump/.cache`, or under the folder in `UASSETGUI_DIR` if you set it. `run` writes `dump/json/` with the full export and `dump/summary/` with one Markdown file per Blueprint listing its parent class and variables. `export` and `summarize` do the two halves separately. `--engine` defaults to `VER_UE5_5`; Blueprints last saved in an older engine need its version, for example `--engine VER_UE4_24`, or UAssetGUI fails on them (72 of 74 failed on a 4.24 project without it). In 4.x output, local variable names show as `?` while calls and flow stay readable. `--include` takes a glob on the relative path and can repeat. Tested on one Blueprint here, a sky actor, and the summary listed its variables correctly.

`scan` is the fast pass for whole drives of old projects. Standard library only, no UAssetGUI, no editor, every asset type. It walks a Content folder, a project or a folder of many projects, skips `DerivedDataCache`, `Intermediate`, `Saved` and `Binaries`, and writes one JSON line per `.uasset` or `.umap`:

```
python bpdump/bpdump.py scan --source "D:/Old Projects" --out old_projects.jsonl --refs --names
```

Each line holds the project name and its `EngineAssociation`, the asset's class read from the package's export and import tables, the parent and native parent class of a Blueprint, the skeleton it uses, whether it has Mixamo bones, the engine version it was saved with, the source file path its import data recorded, and its size. `--refs` adds the `/Game` packages it references; `--names` adds the spaced names inside it, which for a Blueprint are its variables, settings and categories. Assets already in the output file are skipped, so an interrupted run picks up where it stopped. `class_from` says whether the class came from the export table or, for a package the parser cannot read, from a string search of its asset registry data. Run on 16,869 assets across eleven projects saved between UE 4.13 and 5.5: every class came from the export table, in about six minutes from a cold disk.

```
python bpdump/tests/test_scan.py
```

## The rest

```
python textures/make_bayer.py --size 8 --out T_Bayer8.png
python docs_tools/md_to_pdf.py notes.md notes.pdf
python midi/midi_export.py song.json --out song.mid
python moodboard/itch_tags.py tag-abstract/tag-horror --out games.json --covers covers/
python moodboard/itch_album.py album.json out/ --pdf album.pdf
python moodboard/commons_fetch.py search "Faro Punta Delgada"
python moodboard/commons_fetch.py fetch photos.json out/ --width 1600
python audio/archive_catalog.py Red_Library_Foley_Props_2 --match "cloth|fabric"
python audio/fetch_archive_org.py Red_Library_Foley_Props_2 --dest out/ --match "Clothing"
.venv/Scripts/python audio/slice_bursts.py --spec layers.json --out cuts/ --keel C:/Projects/Keel
```

`md_to_pdf.py` and the album PDFs need Microsoft Edge on Windows. itch.io starts refusing requests
after a dozen or so in a row; wait and run again.

## License

MIT

## render

```
uv venv render/.venv --python 3.14
uv pip install --python render/.venv/Scripts/python.exe --require-hashes -r render/requirements.txt
render/.venv/Scripts/python render/relief_board.py --spec board.json --mask mask.png --out card.png --root <project> --scale 0.3 --spp 16
```

The mask is white where the board is cut; the spec sets the board size, mesh and bake resolution, carve depth and blur, wood textures and tint, groove darkening, paint colour and wear, camera, area lights and render settings. `--scale` and `--spp` make quick previews. A light is a `rect` area light or a `spot`; a spot with `look_at_to` sweeps its aim from `look_at` to `look_at_to` over `render.frames` (a lighthouse beam crossing the board), and with more than one frame `--out` is a folder of `frame_NNNN.png`; `--frame-range 0:72:18` renders every 18th frame for a check. For a single still, `--frames 1 --at 0.55` freezes every moving light that far along its sweep. Opt-in spec keys: `carve.profile: "v"` cuts true V-grooves from a distance field; `regions` flood-fill parts of the mask from a seed point and give them their own floor depth, albedo, roughness and emission (a lit window in a letter); `backdrop` adds a planked wood wall behind the board; `wood.clearcoat` a varnish layer; `render.post` bloom and vignette. A spec without them renders as before. `ffmpeg -framerate 24 -i out/frame_%04d.png -c:v libtheora -q:v 9 card.ogv` turns the frames into Ogg Theora, which Godot plays natively. Use the CPU variant `llvm_ad_rgb` when the GPU is small or busy: on a 4 GB RTX 2050 shared with an open Unreal Editor the CUDA variant ran out of memory and crawled (about 5 minutes for a 1152x648 preview), while the CPU rendered the same preview in 2.5 s.
