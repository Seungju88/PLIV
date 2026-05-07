# PLIV Project Structure

```text
.
|-- README.md
|-- docs
|   |-- project-structure.md
|   `-- requirements-draft.md
`-- maestro_pro_plugin
    |-- __init__.py
    |-- config.py
    |-- engine.py
    |-- gui.py
    |-- models.py
    |-- renderer.py
    `-- resources
        `-- interaction_config.json
```

## Directory Roles

### `docs/`

- `requirements-draft.md`
  - product scope, environment assumptions, functional requirements
- `project-structure.md`
  - installable layout and file ownership

### `maestro_pro_plugin/`

- `__init__.py`
  - PyMOL plugin entrypoint
  - menu registration
  - command registration

- `config.py`
  - bundled JSON config loading
  - light config access helpers

- `models.py`
  - dataclasses shared across GUI, engine, and renderer

- `engine.py`
  - selection normalization
  - ligand discovery
  - analysis request construction
  - future interaction typing logic

- `renderer.py`
  - plugin-owned object cleanup
  - working view and publication view rendering
  - future interaction object rendering

- `gui.py`
  - Qt dialog
  - user interaction flow
  - orchestration of engine and renderer

- `resources/interaction_config.json`
  - default thresholds
  - plugin naming
  - display and selection defaults

## Installable Root

For PyMOL Plugin Manager packaging, the installable root is the
`maestro_pro_plugin/` directory.

Zip target example:

```text
maestro_pro_plugin.zip
`-- maestro_pro_plugin/
    |-- __init__.py
    |-- gui.py
    `-- ...
```
