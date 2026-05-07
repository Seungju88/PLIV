# PLIV

This repository contains a first-pass PyMOL 3.1 Open Source plugin skeleton for
PLIV, the Protein-Ligand Interaction Visualizer.

The immediate goal is not full Maestro parity yet. The goal of this PLIV
skeleton is to give us:

- a reusable plugin package layout
- a requirements draft we can iterate on
- a stable split between GUI, engine, renderer, and config
- a place to plug in the existing prototype logic from the reference scripts

Reference files reviewed during setup:

- `/Users/iseungju/scripts/sjlee/pymol_script/maestro_pro_engine.py`
- `/Users/iseungju/scripts/sjlee/pymol_script/maestro_pro_gui.py`
- `/Users/iseungju/scripts/sjlee/pymol_script/interaction_config.json`

## Current Layout

See [docs/project-structure.md](/Users/iseungju/Documents/PLIV/docs/project-structure.md)
for the directory tree and file responsibilities.

See [docs/usage-draft.md](/Users/iseungju/Documents/PLIV/docs/usage-draft.md)
for a working draft of the main PLIV usage guide.

## Next Recommended Step

Port the existing prototype logic into these files in this order:

1. `maestro_pro_plugin/engine.py`
2. `maestro_pro_plugin/renderer.py`
3. `maestro_pro_plugin/gui.py`

## Plugin Packaging Note

PyMOL plugins can be installed from a directory or a zip archive whose root
contains an `__init__.py` plugin entrypoint. In this repo, that installable root
is the `maestro_pro_plugin/` directory.
