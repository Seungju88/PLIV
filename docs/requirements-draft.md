# PLIV Requirements Draft

## 1. Product Goal

Build PLIV, a PyMOL 3.1 Open Source GUI plugin that visualizes protein-ligand
interactions using criteria and presentation rules that are as close as practical
to Schrodinger Maestro.

## 2. Target Environment

- Host application: PyMOL 3.1 Open Source
- Plugin style: PyMOL plugin with Qt GUI
- Primary Python API: `pymol.cmd`
- Preferred Qt import path: `pymol.Qt`
- Packaging target: installable PyMOL plugin directory or zip

## 3. Problem Statement

PyMOL can display distances and contacts, but it does not provide a built-in
Maestro-like interaction panel with consistent interaction typing, per-ligand
selection flow, and publication-oriented presets. The plugin should close that
gap with a workflow tailored to protein-ligand inspection.

## 4. Scope For V1

### In scope

- GUI-based complex and ligand selection
- Per-ligand interaction analysis entrypoint
- Config-driven interaction thresholds
- Rendering presets for working mode and publication mode
- Export-ready internal data model for future CSV and JSON output
- Interaction families:
  - hydrogen bond
  - halogen bond
  - salt bridge
  - pi-pi stacking
  - pi-cation
  - hydrophobic contact

### Out of scope for V1

- water bridge
- metal coordination
- aromatic hydrogen bond parity
- batch processing of many complexes
- full 2D interaction diagrams
- exact one-to-one Maestro UI duplication

## 5. User Workflow

1. User opens the plugin from the PyMOL Plugin menu.
2. User selects one complex object.
3. User selects one ligand instance by chain, residue number, and residue name.
4. User enables or disables interaction families.
5. User runs analysis.
6. Plugin creates pocket selections and interaction display objects.
7. User optionally switches to publication view.

## 6. Functional Requirements

### FR-1 Object discovery

- The plugin must list user-relevant PyMOL objects.
- Helper objects created by the plugin must be filtered out of the object list.

### FR-2 Ligand discovery

- The plugin must list ligand instances from the selected complex.
- Ligands should be identified at least by `chain:resi:resn`.
- Water and common solvent residues must be excluded by default.

### FR-3 Config loading

- The plugin must load thresholds and rendering options from a JSON file bundled
  with the plugin.
- The plugin must provide a fallback if the config file cannot be loaded.

### FR-4 Request normalization

- The plugin must convert GUI selections into a normalized analysis request.
- The request should contain stable selections for:
  - complex
  - protein
  - ligand
  - pocket
  - analysis token or namespace

### FR-5 Interaction detection engine

- The engine must be independent from the GUI layer.
- The engine should expose one entrypoint per analysis run.
- The engine must be able to return structured interaction records later, even if
  the first implementation renders only a subset.

### FR-6 Rendering

- The renderer must clear or reuse plugin-owned objects safely.
- The renderer must support:
  - working view
  - publication view
- Rendered objects must be grouped under a ligand-specific group name.

### FR-7 Publication preset

- The plugin must provide a one-click publication preset that adjusts
  background, cartoon, ligand style, and plugin-owned interaction objects.

### FR-8 Logging and user feedback

- The GUI must show success, warning, and error messages for key actions.

## 7. Non-Functional Requirements

### NFR-1 Maintainability

- GUI, engine, renderer, and config must live in separate modules.

### NFR-2 Testability

- Selection parsing and config loading should be testable without a live PyMOL
  GUI where possible.

### NFR-3 Compatibility

- Use `pymol.Qt` instead of importing `PyQt5` directly when possible.

### NFR-4 Safety

- Plugin cleanup must remove only plugin-owned objects and selections.

## 8. Architecture Requirements

### GUI layer

- Owns widgets, user actions, and status messages
- Does not implement geometric interaction logic directly

### Engine layer

- Owns selection creation, request normalization, and interaction computation
- Consumes config values

### Renderer layer

- Owns PyMOL visualization objects and display presets

### Config layer

- Owns config file path resolution and defaults

### Model layer

- Owns dataclasses for ligand identity, analysis request, and result summary

## 9. Acceptance Criteria For Skeleton Milestone

- Repository contains a requirements draft
- Repository contains a documented project structure
- Repository contains a PyMOL-installable plugin package
- Plugin entrypoint is wired through `__init_plugin__(app=None)`
- GUI can open and list candidate objects
- GUI can list ligand instances for a selected object
- Analysis action creates a normalized request and a pocket selection
- Publication action runs without depending on unfinished interaction logic

## 10. Acceptance Criteria For V1

- The plugin reproduces the selected V1 interaction families with benchmarked
  thresholds
- The plugin produces stable output on a curated validation set
- The plugin keeps plugin-owned objects grouped and removable
- The plugin supports at least one export format for analysis results

## 11. Integration Notes From The Reviewed Prototype Files

The reviewed prototype files already contain useful starting points:

- hierarchical complex to ligand selection
- interaction config JSON
- pocket selection creation
- ring centroid and normal estimation
- simple publication view styling

The main missing step is to refactor those ideas into a cleaner module boundary
so that Maestro parity work can proceed without the GUI becoming the engine.
