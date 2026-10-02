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
| `ue_remote/` | CLI that runs Python in an open Unreal Editor through Epic's Remote Execution, plus 25 editor scripts |
| `citygen/` | OpenStreetMap streets and building footprints to a layered R12 DXF for SketchUp, with Microsoft building footprints to fill the gaps |
| `textures/` | Ordered-dither (Bayer) threshold texture as a PNG, for 1-bit and retro post-process materials |
| `docs_tools/` | Markdown to PDF through headless Edge, tables kept whole across pages |
| `moodboard/` | Art-reference albums from itch.io or Steam screenshots, as HTML and PDF |

No pip packages for anything except `citygen/`, which needs `shapely` and `numpy`.

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
