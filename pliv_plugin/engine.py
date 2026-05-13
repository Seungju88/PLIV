"""Core orchestration and selection logic for the plugin skeleton."""

from __future__ import annotations

from collections import Counter
import re
import sys
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import numpy as np
    _NUMPY_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - depends on local Python runtime
    np = None
    _NUMPY_IMPORT_ERROR = exc

from .config import ConfigManager
from .models import AnalysisRequest, AnalysisSummary, InteractionRecord, LigandTarget


def _default_cmd_api():
    from pymol import cmd

    return cmd


class InteractionEngine:
    """Owns PyMOL selection building and future interaction computation."""

    _PROTEIN_RING_RESIDUES = ("PHE", "TYR", "TRP", "HIS")
    _IONIC_POSITIVE_RESIDUES = "ARG+LYS"
    _IONIC_NEGATIVE_RESIDUES = "ASP+GLU"
    _WATER_RESIDUES = ("HOH", "WAT", "TIP3")
    _STANDARD_AROMATIC_BONDS = {
        "PHE": (("CG", "CD1"), ("CD1", "CE1"), ("CE1", "CZ"), ("CZ", "CE2"), ("CE2", "CD2"), ("CD2", "CG")),
        "TYR": (("CG", "CD1"), ("CD1", "CE1"), ("CE1", "CZ"), ("CZ", "CE2"), ("CE2", "CD2"), ("CD2", "CG")),
        "TRP": (
            ("CG", "CD1"),
            ("CD1", "NE1"),
            ("NE1", "CE2"),
            ("CE2", "CD2"),
            ("CD2", "CG"),
            ("CE2", "CZ2"),
            ("CZ2", "CH2"),
            ("CH2", "CZ3"),
            ("CZ3", "CE3"),
            ("CE3", "CD2"),
        ),
        "HIS": (("CG", "ND1"), ("ND1", "CE1"), ("CE1", "NE2"), ("NE2", "CD2"), ("CD2", "CG")),
    }
    _STANDARD_AROMATIC_RING_ATOMS = {
        "PHE": ("CG", "CD1", "CE1", "CZ", "CE2", "CD2"),
        "TYR": ("CG", "CD1", "CE1", "CZ", "CE2", "CD2"),
        "TRP": ("CG", "CD1", "NE1", "CE2", "CD2", "CZ2", "CH2", "CZ3", "CE3"),
        "HIS": ("CG", "ND1", "CE1", "NE2", "CD2"),
    }

    def __init__(self, config: ConfigManager, cmd_api=None) -> None:
        self.config = config
        self.cmd = cmd_api or _default_cmd_api()

    def dependency_issue(self) -> Optional[str]:
        if _NUMPY_IMPORT_ERROR is None:
            return None
        return (
            "NumPy could not be imported in the Python environment used by PyMOL. "
            f"Interpreter: {sys.executable}. Original error: {_NUMPY_IMPORT_ERROR}"
        )

    def ensure_dependencies(self) -> None:
        issue = self.dependency_issue()
        if issue is None:
            return
        raise RuntimeError(
            issue
            + " PLIV requires a working NumPy installation for interaction geometry."
        )

    def list_complex_objects(self) -> List[str]:
        prefixes = self.config.get("render", "cleanup_prefixes", default=[])
        objects = self.cmd.get_names("objects")
        return [name for name in objects if not any(name.startswith(prefix) for prefix in prefixes)]

    def list_receptor_objects(self) -> List[str]:
        receptors: List[str] = []
        for name in self.list_complex_objects():
            if int(self.cmd.count_atoms(f"({name}) and polymer.protein")) > 0:
                receptors.append(name)
        return receptors

    def list_docking_ligand_objects(self, receptor_name: Optional[str] = None) -> List[LigandTarget]:
        ligands: List[LigandTarget] = []
        solvent = "+".join(self.config.get("selection", "solvent_resn", default=[]))
        ions = "+".join(self.config.get("selection", "ion_resn", default=[]))

        excluded = []
        if solvent:
            excluded.append(f"resn {solvent}")
        if ions:
            excluded.append(f"resn {ions}")
        exclusion_clause = ""
        if excluded:
            exclusion_clause = " and not (" + " or ".join(excluded) + ")"

        for name in self.list_complex_objects():
            if receptor_name and name == receptor_name:
                continue
            if int(self.cmd.count_atoms(f"({name}) and polymer.protein")) > 0:
                continue
            if int(self.cmd.count_atoms(f"({name}) and not polymer.protein{exclusion_clause}")) == 0:
                continue
            ligands.append(LigandTarget(object_name=name))
        return ligands

    def list_ligands(self, complex_name: str) -> List[LigandTarget]:
        solvent = "+".join(self.config.get("selection", "solvent_resn", default=[]))
        ions = "+".join(self.config.get("selection", "ion_resn", default=[]))

        excluded = []
        if solvent:
            excluded.append(f"resn {solvent}")
        if ions:
            excluded.append(f"resn {ions}")

        exclusion_clause = ""
        if excluded:
            exclusion_clause = " and not (" + " or ".join(excluded) + ")"

        selection = f"({complex_name} and not polymer.protein{exclusion_clause})"
        found = set()
        self.cmd.iterate(
            selection,
            "found.add((chain, resi, resn))",
            space={"found": found},
        )

        ligands = [LigandTarget(chain=chain, resi=resi, resn=resn) for chain, resi, resn in sorted(found)]
        return ligands

    def build_request(
        self,
        complex_name: str,
        ligand: LigandTarget,
        interaction_types: List[str],
        profile_name: str,
        input_mode: str = "complex",
    ) -> AnalysisRequest:
        token = self._build_target_token(ligand)
        ligand_selection = self._build_ligand_selection(complex_name, ligand, input_mode=input_mode)
        protein_selection = f"({complex_name} and polymer.protein)"
        pocket_selection = f"mp_pocket_{token}"
        water_selection = f"mp_water_{token}"
        ion_selection = f"mp_ion_{token}"
        group_name = f"mp_group_{token}"

        return AnalysisRequest(
            input_mode=input_mode,
            complex_name=complex_name,
            ligand=ligand,
            interaction_types=interaction_types,
            profile_name=profile_name,
            token=token,
            ligand_selection=ligand_selection,
            protein_selection=protein_selection,
            pocket_selection=pocket_selection,
            water_selection=water_selection,
            ion_selection=ion_selection,
            group_name=group_name,
        )

    def prepare_environment(self, request: AnalysisRequest) -> None:
        pocket_cutoff = float(self.config.get("selection", "pocket_cutoff", default=5.0))
        water_cutoff = float(self.config.get("selection", "water_cutoff", default=3.6))
        ion_cutoff = float(self.config.get("selection", "ion_cutoff", default=pocket_cutoff))
        ion_resn = "+".join(self.config.get("selection", "ion_resn", default=[]))
        self.cmd.select(
            request.pocket_selection,
            f"byres ({request.protein_selection} within {pocket_cutoff:.2f} of {request.ligand_selection})",
        )
        if bool(self.config.get("selection", "repair_protein_aromatics", default=True)):
            self._repair_standard_protein_aromatic_bonds(request.pocket_selection)
        self.cmd.select(
            request.water_selection,
            (
                f"({request.complex_name} and resn {'+'.join(self._WATER_RESIDUES)} "
                f"within {water_cutoff:.2f} of {request.ligand_selection})"
            ),
        )
        self.cmd.select(
            request.ion_selection,
            f"({request.complex_name} and resn {ion_resn} within {ion_cutoff:.2f} of {request.ligand_selection})",
        )

    def run_analysis(self, request: AnalysisRequest) -> AnalysisSummary:
        self.ensure_dependencies()
        self.prepare_environment(request)

        ligand_atom_count = int(self.cmd.count_atoms(request.ligand_selection))
        pocket_atom_count = int(self.cmd.count_atoms(request.pocket_selection))
        water_atom_count = int(self.cmd.count_atoms(request.water_selection))
        ion_atom_count = int(self.cmd.count_atoms(request.ion_selection))
        self._last_water_count = water_atom_count
        self._last_ion_count = ion_atom_count
        interactions = self._collect_interactions(request)
        counts = Counter(item["kind"] for item in interactions)
        unsupported = sorted(set(request.interaction_types) - self._implemented_interaction_types())

        summary = AnalysisSummary(
            ligand_atom_count=ligand_atom_count,
            pocket_atom_count=pocket_atom_count,
            selected_interaction_types=list(request.interaction_types),
            notes=self._build_summary_notes(interactions, counts, unsupported),
        )
        records = [self._to_interaction_record(item) for item in interactions]
        summary.interactions = interactions
        summary.interaction_counts = dict(counts)
        summary.result = summary.to_result(
            request=request,
            interactions=records,
            metadata={
                "profile_name": request.profile_name,
                "water_atom_count": water_atom_count,
                "ion_atom_count": ion_atom_count,
            },
        )
        summary.water_atom_count = water_atom_count
        summary.ion_atom_count = ion_atom_count
        return summary

    def _build_ligand_selection(self, complex_name: str, ligand: LigandTarget, input_mode: str = "complex") -> str:
        if input_mode == "docking" and ligand.object_name:
            return f"({ligand.object_name})"
        parts = [complex_name, f"resi '{ligand.resi}'", f"resn '{ligand.resn}'"]
        if ligand.chain:
            parts.append(f"chain '{ligand.chain}'")
        return "(" + " and ".join(parts) + ")"

    def _build_target_token(self, ligand: LigandTarget) -> str:
        if ligand.object_name:
            base = ligand.object_name
        else:
            base = f"{ligand.resn}_{ligand.resi}_{ligand.chain or 'NA'}"
        cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", base).strip("_")
        return cleaned or "ligand"

    def _build_summary_notes(
        self,
        interactions: List[Dict[str, object]],
        counts: Counter,
        unsupported: List[str],
    ) -> List[str]:
        if not interactions:
            notes = ["No interaction candidates were detected with the current prototype rules."]
            if getattr(self, "_last_water_count", 0):
                notes.append(f"Nearby water atoms considered: {self._last_water_count}")
            if getattr(self, "_last_ion_count", 0):
                notes.append(f"Nearby ion atoms preserved: {self._last_ion_count}")
            if unsupported:
                notes.append(
                    "Not implemented yet in this prototype run: " + ", ".join(unsupported)
                )
            return notes

        notes = [f"Detected {len(interactions)} interaction candidate(s)."]
        if getattr(self, "_last_water_count", 0):
            notes.append(f"Nearby water atoms considered: {self._last_water_count}")
        if getattr(self, "_last_ion_count", 0):
            notes.append(f"Nearby ion atoms preserved: {self._last_ion_count}")
        for kind, count in sorted(counts.items()):
            notes.append(f"{kind}: {count}")
        if unsupported:
            notes.append("Not implemented yet in this prototype run: " + ", ".join(unsupported))
        return notes

    def _implemented_interaction_types(self) -> set:
        return {"hydrogen_bond", "salt_bridge", "pi_pi_stacking", "pi_cation"}

    def _to_interaction_record(self, interaction: Dict[str, object]) -> InteractionRecord:
        ligand_atoms = []
        if "ligand_atom_index" in interaction:
            ligand_atoms.append(int(interaction["ligand_atom_index"]))

        partner_atoms = []
        if "protein_atom_index" in interaction:
            partner_atoms.append(int(interaction["protein_atom_index"]))

        measurements = {}
        for key in ("distance", "angle"):
            if key in interaction:
                measurements[key] = float(interaction[key])

        metadata = dict(interaction)
        for key in ("kind", "ligand_atom_index", "protein_atom_index", "distance", "angle", "protein_residue_label"):
            metadata.pop(key, None)

        return InteractionRecord(
            interaction_type=str(interaction["kind"]),
            ligand_atoms=ligand_atoms,
            partner_atoms=partner_atoms,
            partner_label=str(interaction.get("protein_residue_label", "")),
            measurements=measurements,
            metadata=metadata,
        )

    def _collect_interactions(self, request: AnalysisRequest) -> List[Dict[str, object]]:
        interactions: List[Dict[str, object]] = []

        if "hydrogen_bond" in request.interaction_types:
            interactions.extend(self._find_hydrogen_bonds(request))
        if "salt_bridge" in request.interaction_types:
            interactions.extend(self._find_salt_bridges(request))
        if "pi_pi_stacking" in request.interaction_types:
            interactions.extend(self._find_pi_pi(request))
        if "pi_cation" in request.interaction_types:
            interactions.extend(self._find_pi_cation(request))

        return interactions

    def _find_hydrogen_bonds(self, request: AnalysisRequest) -> List[Dict[str, object]]:
        settings = self.config.interaction_config("hydrogen_bond", request.profile_name)
        cutoff = float(settings.get("cutoff", 3.2))
        ligand_sel = f"({request.ligand_selection} and elem N+O+S)"
        pocket_sel = f"({request.pocket_selection} and elem N+O+S)"
        pairs = self.cmd.find_pairs(ligand_sel, pocket_sel, mode=1, cutoff=cutoff)
        interactions = self._pairs_to_interactions(
            request=request,
            pairs=pairs,
            kind="hydrogen_bond",
            prefix="mp_hb_",
            color=str(settings.get("color", "yellow")),
            width=float(settings.get("width", 3)),
        )
        if bool(settings.get("include_waters", True)):
            water_settings = self.config.interaction_config("water_hydrogen_bond", request.profile_name)
            water_cutoff = float(water_settings.get("cutoff", cutoff))
            water_sel = f"({request.water_selection} and elem O)"
            water_pairs = self.cmd.find_pairs(ligand_sel, water_sel, mode=1, cutoff=water_cutoff)
            interactions.extend(
                self._pairs_to_interactions(
                    request=request,
                    pairs=water_pairs,
                    kind="water_hydrogen_bond",
                    prefix="mp_whb_",
                    color=str(water_settings.get("color", settings.get("color", "yellow"))),
                    width=float(water_settings.get("width", settings.get("width", 3))),
                    role="ligand_to_water",
                    partner_base_selection=request.water_selection,
                    partner_category="water",
                )
            )
        return interactions

    def _find_salt_bridges(self, request: AnalysisRequest) -> List[Dict[str, object]]:
        settings = self.config.interaction_config("salt_bridge", request.profile_name)
        cutoff = float(settings.get("cutoff", 4.5))
        protein_negative = (
            f"({request.pocket_selection} and resn {self._IONIC_NEGATIVE_RESIDUES} and elem O)"
        )
        protein_positive = (
            f"({request.pocket_selection} and resn {self._IONIC_POSITIVE_RESIDUES} and elem N)"
        )
        ligand_positive = f"({request.ligand_selection} and elem N)"
        ligand_negative = f"({request.ligand_selection} and elem O)"

        interactions = []
        interactions.extend(
            self._pairs_to_interactions(
                request=request,
                pairs=self.cmd.find_pairs(ligand_positive, protein_negative, mode=1, cutoff=cutoff),
                kind="salt_bridge",
                prefix="mp_salt_",
                color=str(settings.get("color", "magenta")),
                width=float(settings.get("width", 4)),
                role="ligand_positive_to_protein_negative",
            )
        )
        interactions.extend(
            self._pairs_to_interactions(
                request=request,
                pairs=self.cmd.find_pairs(ligand_negative, protein_positive, mode=1, cutoff=cutoff),
                kind="salt_bridge",
                prefix="mp_salt_",
                color=str(settings.get("color", "magenta")),
                width=float(settings.get("width", 4)),
                role="ligand_negative_to_protein_positive",
            )
        )
        return interactions

    def _find_pi_pi(self, request: AnalysisRequest) -> List[Dict[str, object]]:
        settings = self.config.interaction_config("pi_pi_stacking", request.profile_name)
        face_settings = dict(settings.get("face_to_face", {}))
        edge_settings = dict(settings.get("edge_to_face", {}))
        face_cutoff = float(face_settings.get("cutoff", settings.get("cutoff", 4.4)))
        face_angle_max = float(face_settings.get("angle_max", settings.get("angle_max", 30.0)))
        edge_cutoff = float(edge_settings.get("cutoff", settings.get("cutoff", 5.5)))
        edge_angle_min = float(edge_settings.get("min_angle", settings.get("angle_tshape_min", 60.0)))
        color = str(settings.get("color", "cyan"))
        width = float(settings.get("width", 4))

        ligand_rings = self._get_ligand_ring_data(request.ligand_selection)
        protein_rings = self._get_protein_ring_data(request.pocket_selection)
        interactions = []

        for ligand_ring in ligand_rings:
            for protein_ring in protein_rings:
                distance = float(np.linalg.norm(ligand_ring["centroid"] - protein_ring["centroid"]))

                cosine = float(np.clip(np.dot(ligand_ring["normal"], protein_ring["normal"]), -1.0, 1.0))
                angle = float(np.degrees(np.arccos(abs(cosine))))
                is_face = distance <= face_cutoff and angle <= face_angle_max
                is_edge = distance <= edge_cutoff and angle >= edge_angle_min
                if not is_face and not is_edge:
                    continue

                interaction_mode = "parallel" if is_face else "t_shaped"
                interactions.append(
                    {
                        "kind": "pi_pi_stacking",
                        "interaction_type": "pi_pi_stacking",
                        "mode": interaction_mode,
                        "distance": distance,
                        "angle": angle,
                        "color": color,
                        "width": width,
                        "prefix": "mp_pipi_",
                        "object_name": f"mp_pipi_{request.token}_{len(interactions):03d}",
                        "start": ligand_ring["centroid"].tolist(),
                        "end": protein_ring["centroid"].tolist(),
                        "ligand_centroid": ligand_ring["centroid"].tolist(),
                        "protein_centroid": protein_ring["centroid"].tolist(),
                        "protein_residue_label": protein_ring["residue_label"],
                        "protein_selection": protein_ring["residue_selection"],
                    }
                )
        return interactions

    def _find_pi_cation(self, request: AnalysisRequest) -> List[Dict[str, object]]:
        settings = self.config.interaction_config("pi_cation", request.profile_name)
        cutoff = float(settings.get("cutoff", 6.6))
        angle_max = float(settings.get("angle_max", 30.0))
        color = str(settings.get("color", "green"))
        width = float(settings.get("width", 4))
        ligand_rings = self._get_ligand_ring_data(request.ligand_selection)
        protein_cations = (
            f"({request.pocket_selection} and (resn LYS+ARG) and name NZ+NH1+NH2+NE)"
        )
        interactions = []
        near_atoms = []
        self.cmd.iterate(
            f"({protein_cations} within {cutoff:.2f} of {request.ligand_selection})",
            "near_atoms.append((model, index, chain, resi, resn, name))",
            space={"near_atoms": near_atoms},
        )

        for ring_index, ligand_ring in enumerate(ligand_rings):
            for model_name, atom_index, chain, resi, resn, name in near_atoms:
                atom_coords = self.cmd.get_atom_coords(self._atom_selection(model_name, atom_index))
                direction = np.array(atom_coords, dtype=float) - ligand_ring["centroid"]
                distance = float(np.linalg.norm(direction))
                if distance > cutoff:
                    continue
                if distance == 0:
                    continue
                angle = float(
                    np.degrees(
                        np.arccos(
                            abs(
                                float(
                                    np.clip(
                                        np.dot(direction / distance, ligand_ring["normal"]),
                                        -1.0,
                                        1.0,
                                    )
                                )
                            )
                        )
                    )
                )
                if angle > angle_max:
                    continue

                interactions.append(
                    {
                        "kind": "pi_cation",
                        "interaction_type": "pi_cation",
                        "distance": distance,
                        "angle": angle,
                        "color": color,
                        "width": width,
                        "prefix": "mp_pcat_",
                        "object_name": f"mp_pcat_{request.token}_{ring_index:02d}_{atom_index}",
                        "start": ligand_ring["centroid"].tolist(),
                        "end": list(atom_coords),
                        "ligand_centroid": ligand_ring["centroid"].tolist(),
                        "protein_model": model_name,
                        "protein_atom_index": int(atom_index),
                        "protein_residue_label": f"{chain}:{resi}:{resn}",
                        "protein_selection": (
                            f"({request.pocket_selection} and chain '{chain}' and resi '{resi}' and resn '{resn}')"
                        ),
                        "protein_atom_name": name,
                    }
                )

        return interactions

    def _pairs_to_interactions(
        self,
        request: AnalysisRequest,
        pairs: Sequence[Tuple[Tuple[str, int], Tuple[str, int]]],
        kind: str,
        prefix: str,
        color: str,
        width: float,
        role: Optional[str] = None,
        partner_base_selection: Optional[str] = None,
        partner_category: str = "protein",
    ) -> List[Dict[str, object]]:
        interactions: List[Dict[str, object]] = []
        seen_pairs = set()
        seen_ligand_atoms = set()
        seen_protein_atoms = set()
        ranked_pairs = []

        for pair in pairs:
            ligand_model = str(pair[0][0])
            protein_model = str(pair[1][0])
            ligand_atom_index = int(pair[0][1])
            protein_atom_index = int(pair[1][1])
            ligand_coords = np.array(self.cmd.get_atom_coords(self._atom_selection(ligand_model, ligand_atom_index)))
            protein_coords = np.array(self.cmd.get_atom_coords(self._atom_selection(protein_model, protein_atom_index)))
            distance = float(np.linalg.norm(ligand_coords - protein_coords))
            ranked_pairs.append((distance, ligand_model, ligand_atom_index, protein_model, protein_atom_index))

        ranked_pairs.sort(key=lambda item: item[0])

        for pair_index, pair in enumerate(ranked_pairs):
            distance, ligand_model, ligand_atom_index, protein_model, protein_atom_index = pair
            pair_key = (ligand_model, ligand_atom_index, protein_model, protein_atom_index, kind)
            if pair_key in seen_pairs:
                continue
            ligand_key = (ligand_model, ligand_atom_index)
            protein_key = (protein_model, protein_atom_index)
            if ligand_key in seen_ligand_atoms or protein_key in seen_protein_atoms:
                continue
            seen_pairs.add(pair_key)
            seen_ligand_atoms.add(ligand_key)
            seen_protein_atoms.add(protein_key)

            protein_residue_label = self._residue_label_from_atom_index(protein_model, protein_atom_index)
            protein_residue_selection = self._residue_selection_from_atom_index(
                partner_base_selection or request.pocket_selection,
                protein_model,
                protein_atom_index,
            )
            interactions.append(
                {
                    "kind": kind,
                    "interaction_type": kind,
                    "role": role,
                    "color": color,
                    "width": width,
                    "prefix": prefix,
                    "object_name": f"{prefix}{request.token}_{pair_index:03d}",
                    "distance": distance,
                    "ligand_model": ligand_model,
                    "protein_model": protein_model,
                    "ligand_atom_index": ligand_atom_index,
                    "protein_atom_index": protein_atom_index,
                    "start_selection": self._atom_selection(ligand_model, ligand_atom_index),
                    "end_selection": self._atom_selection(protein_model, protein_atom_index),
                    "protein_residue_label": protein_residue_label,
                    "protein_selection": protein_residue_selection,
                    "partner_category": partner_category,
                    "partner_display": "spheres" if partner_category == "water" else "sticks",
                }
            )

        return interactions

    def _residue_label_from_atom_index(self, model_name: str, atom_index: int) -> str:
        residue_info: Dict[str, str] = {}
        self.cmd.iterate(
            self._atom_selection(model_name, atom_index),
            "residue_info.update({'chain': chain, 'resi': resi, 'resn': resn})",
            space={"residue_info": residue_info},
        )
        chain = residue_info.get("chain", "")
        return f"{chain}:{residue_info.get('resi', '?')}:{residue_info.get('resn', '?')}"

    def _residue_selection_from_atom_index(self, base_selection: str, model_name: str, atom_index: int) -> str:
        residue_info: Dict[str, str] = {}
        self.cmd.iterate(
            self._atom_selection(model_name, atom_index),
            "residue_info.update({'chain': chain, 'resi': resi, 'resn': resn})",
            space={"residue_info": residue_info},
        )

        parts = [base_selection, f"resi '{residue_info.get('resi', '')}'", f"resn '{residue_info.get('resn', '')}'"]
        if residue_info.get("chain", ""):
            parts.append(f"chain '{residue_info['chain']}'")
        return "(" + " and ".join(parts) + ")"

    def _atom_selection(self, model_name: str, atom_index: int) -> str:
        return f"({model_name} and index {int(atom_index)})"

    def _repair_standard_protein_aromatic_bonds(self, selection: str) -> None:
        for residue_name, bonds in self._STANDARD_AROMATIC_BONDS.items():
            residue_selection = f"({selection} and resn {residue_name})"
            if self.cmd.count_atoms(residue_selection) == 0:
                continue

            residue_ids = []
            self.cmd.iterate(
                residue_selection,
                "residue_ids.append((model, chain, resi))",
                space={"residue_ids": residue_ids},
            )
            for model_name, chain, resi in sorted(set(residue_ids)):
                for atom_name_1, atom_name_2 in bonds:
                    atom_sel_1 = (
                        f"({model_name} and resn {residue_name} and resi '{resi}' and name {atom_name_1})"
                    )
                    atom_sel_2 = (
                        f"({model_name} and resn {residue_name} and resi '{resi}' and name {atom_name_2})"
                    )
                    if chain:
                        atom_sel_1 = atom_sel_1[:-1] + f" and chain '{chain}')"
                        atom_sel_2 = atom_sel_2[:-1] + f" and chain '{chain}')"
                    if self.cmd.count_atoms(atom_sel_1) != 1 or self.cmd.count_atoms(atom_sel_2) != 1:
                        continue
                    try:
                        self.cmd.bond(atom_sel_1, atom_sel_2, mode=1)
                    except Exception:
                        continue

    def _get_ligand_ring_data(self, ligand_selection: str) -> List[Dict[str, object]]:
        ring_indices = self._get_ligand_rings(ligand_selection)
        rings = []
        for ring in ring_indices:
            selection = f"({ligand_selection}) and index " + "+".join(map(str, ring))
            centroid, normal = self._centroid_and_normal(selection)
            if centroid is None or normal is None:
                continue
            rings.append(
                {
                    "atom_indices": ring,
                    "centroid": centroid,
                    "normal": normal,
                }
            )
        return rings

    def _get_ligand_rings(self, ligand_selection: str) -> List[List[int]]:
        model = self.cmd.get_model(f"byring ({ligand_selection} and not elem H)")
        atoms = model.atom
        if not atoms:
            return []

        adjacency = {index: set() for index in range(len(atoms))}
        for bond in model.bond:
            first, second = bond.index
            adjacency[first].add(second)
            adjacency[second].add(first)

        rings = set()

        def find_cycles(start: int, current: int, path: List[int]) -> None:
            if len(path) > 7:
                return
            if len(path) >= 5 and start in adjacency[current]:
                rings.add(tuple(sorted(path)))
                return
            for neighbor in adjacency[current]:
                if neighbor not in path:
                    find_cycles(start, neighbor, path + [neighbor])

        for atom_index in range(len(atoms)):
            find_cycles(atom_index, atom_index, [atom_index])

        return [[atoms[model_index].index for model_index in ring] for ring in sorted(rings)]

    def _get_protein_ring_data(self, pocket_selection: str) -> List[Dict[str, object]]:
        residue_ids = []
        residue_resn = {}
        self.cmd.iterate(
            f"({pocket_selection} and resn {'+'.join(self._PROTEIN_RING_RESIDUES)})",
            "residue_ids.append((chain, resi)); residue_resn[(chain, resi)] = resn",
            space={"residue_ids": residue_ids, "residue_resn": residue_resn},
        )

        rings = []
        for chain, resi in sorted(set(residue_ids)):
            resn = residue_resn[(chain, resi)]
            residue_selection = f"({pocket_selection} and resi '{resi}'"
            if chain:
                residue_selection += f" and chain '{chain}'"
            residue_selection += ")"
            ring_atom_names = self._STANDARD_AROMATIC_RING_ATOMS.get(resn, ())
            if ring_atom_names:
                ring_selection = residue_selection + " and name " + "+".join(ring_atom_names)
            else:
                ring_selection = residue_selection + " and sidechain and not name CB"
            centroid, normal = self._centroid_and_normal(ring_selection)
            if centroid is None or normal is None:
                continue
            rings.append(
                {
                    "centroid": centroid,
                    "normal": normal,
                    "residue_label": f"{chain}:{resi}:{resn}",
                    "residue_selection": residue_selection,
                }
            )
        return rings

    def _centroid_and_normal(self, selection: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        coords = self.cmd.get_coords(selection)
        if coords is None or len(coords) < 3:
            return None, None

        points = np.array(coords, dtype=float)
        centroid = points.mean(axis=0)
        centered = points - centroid
        _, _, vh = np.linalg.svd(centered)
        normal = vh[2, :]

        norm = np.linalg.norm(normal)
        if norm == 0:
            return None, None
        return centroid, normal / norm
