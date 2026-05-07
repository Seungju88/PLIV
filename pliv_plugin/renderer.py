"""Rendering helpers for plugin-owned PyMOL objects."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from typing import Any

from .config import ConfigManager
from .models import AnalysisRequest, AnalysisSummary

_INTERACTION_PREFIXES = {
    "hydrogen_bond": "mp_hb_",
    "water_hydrogen_bond": "mp_whb_",
    "halogen_bond": "mp_hal_",
    "salt_bridge": "mp_salt_",
    "pi_pi_stacking": "mp_pipi_",
    "pi_cation": "mp_pcat_",
    "hydrophobic_contact": "mp_hyd_",
}
_INTERACTION_RESULT_ATTRS = ("interaction_results", "interactions", "interaction_records")


def _default_cmd_api():
    from pymol import cmd

    return cmd


class InteractionRenderer:
    """Owns cleanup, naming, and view styling for plugin-managed objects."""

    def __init__(self, config: ConfigManager, cmd_api=None) -> None:
        self.config = config
        self.cmd = cmd_api or _default_cmd_api()
        self._stored_global_settings: dict[str, dict[str, str]] = {}

    def store_view_state(self, request: AnalysisRequest) -> str:
        scene_name = self._publication_scene_name(request)
        self._stored_global_settings[scene_name] = self._capture_global_visual_settings()
        self.cmd.refresh()
        self.cmd.scene(scene_name, "store", "", 1, 1, 1, 1, 1)
        return scene_name

    def restore_view_state(self, request: AnalysisRequest) -> bool:
        scene_name = self._publication_scene_name(request)
        try:
            self.cmd.scene(scene_name, "recall")
            self._restore_global_visual_settings(self._stored_global_settings.get(scene_name, {}))
            self.cmd.refresh()
            return True
        except Exception:
            return False

    def store_viewpoint(self, slot: int) -> str:
        view_name = self._viewpoint_name(slot)
        self.cmd.view(view_name, "store")
        return view_name

    def restore_viewpoint(self, slot: int) -> bool:
        view_name = self._viewpoint_name(slot)
        try:
            self.cmd.view(view_name, "recall")
            return True
        except Exception:
            return False

    def clear_plugin_objects(self) -> None:
        for prefix in self.config.get("render", "cleanup_prefixes", default=[]):
            self.cmd.delete(f"{prefix}*")

    def render_working_view(self, request: AnalysisRequest, summary: AnalysisSummary) -> None:
        self.cmd.show("cartoon", request.protein_selection)
        self.cmd.color("gray80", request.protein_selection)
        self.cmd.hide("lines", request.protein_selection)
        self.cmd.show("sticks", request.ligand_selection)
        self.cmd.util.cbag(request.ligand_selection)
        self._hide_nonpolar_hydrogens(request)
        self.cmd.group(
            request.group_name,
            f"{request.pocket_selection} {request.water_selection} {request.ion_selection} {request.ligand_selection}",
        )
        self._show_nearby_ions(request)
        self.render_summary_interactions(request, summary)
        self.cmd.hide("labels", request.group_name)
        self._show_interaction_partners(summary)
        self.cmd.zoom(request.ligand_selection, buffer=8)
        self.cmd.orient(request.ligand_selection)

    def apply_publication_view(self, request: AnalysisRequest, summary: AnalysisSummary | None = None) -> None:
        self.cmd.hide("everything", "all")
        self.cmd.show("cartoon", request.protein_selection)
        self.cmd.color("gray80", request.protein_selection)
        self.cmd.hide("lines", request.protein_selection)
        self.cmd.show("sticks", request.ligand_selection)
        self.cmd.util.cbag(request.ligand_selection)
        self._hide_nonpolar_hydrogens(request)
        self._show_nearby_ions(request)
        self.cmd.show("dashes", request.group_name)
        self.cmd.hide("labels", request.group_name)
        if summary is not None:
            self._show_interaction_partners(summary)

        self.cmd.bg_color(str(self.config.get("render", "publication", "background", default="white")))
        self.cmd.set(
            "ray_trace_mode",
            int(self.config.get("render", "publication", "ray_trace_mode", default=3)),
        )
        self.cmd.set(
            "ray_shadows",
            int(self.config.get("render", "publication", "ray_shadows", default=1)),
        )
        self.cmd.set(
            "ray_trace_gain",
            float(self.config.get("render", "publication", "ray_trace_gain", default=0.4)),
        )

    def interaction_prefix(self, interaction_type: str) -> str:
        """Return the cleanup-aware prefix for a plugin interaction family."""

        return _INTERACTION_PREFIXES.get(interaction_type, "mp_tmp_")

    def interaction_group_name(self, request: AnalysisRequest, interaction_type: str) -> str:
        """Build the family group name for one request-scoped interaction set."""

        return self._compose_plugin_name(
            self.interaction_prefix(interaction_type),
            request.token,
            interaction_type,
            "group",
        )

    def update_interaction_family_color(
        self,
        request: AnalysisRequest,
        interaction_type: str,
        color_value: str,
    ) -> bool:
        group_name = self.interaction_group_name(request, interaction_type)
        if group_name not in self.cmd.get_names("all"):
            return False
        pymol_color = self._normalize_pymol_color(color_value)
        self.cmd.color(pymol_color, group_name)
        self.cmd.set("dash_color", pymol_color, group_name)
        return True

    def interaction_object_name(
        self,
        request: AnalysisRequest,
        interaction_type: str,
        index: int,
        role: str = "dash",
    ) -> str:
        """Build a plugin-owned object name for one rendered interaction."""

        return self._compose_plugin_name(
            self.interaction_prefix(interaction_type),
            request.token,
            interaction_type,
            role,
            index,
        )

    def temporary_object_name(
        self,
        request: AnalysisRequest,
        purpose: str,
        index: int | None = None,
    ) -> str:
        """Build a plugin-owned helper object name for transient geometry anchors."""

        parts: list[Any] = [request.token, purpose]
        if index is not None:
            parts.append(index)
        return self._compose_plugin_name("mp_tmp_", *parts)

    def render_summary_interactions(self, request: AnalysisRequest, summary: AnalysisSummary) -> list[str]:
        """Render any structured interaction payload attached to the engine summary."""

        for attr in _INTERACTION_RESULT_ATTRS:
            interaction_results = getattr(summary, attr, None)
            if interaction_results:
                return self.render_interaction_results(
                    request,
                    interaction_results,
                    parent_group=request.group_name,
                )
        return []

    def render_interaction_results(
        self,
        request: AnalysisRequest,
        interaction_results: Any,
        *,
        parent_group: str | None = None,
    ) -> list[str]:
        """Render structured interaction results into plugin-owned PyMOL objects.

        The payload can be either:
        - a mapping of interaction family -> record(s)
        - a flat sequence of records with an ``interaction_type`` field
        - nested mappings containing ``records`` / ``items`` / ``interactions``
        """

        normalized = self._normalize_interaction_results(interaction_results)
        created_names: list[str] = []

        for interaction_type, records in normalized.items():
            family_group = self.interaction_group_name(request, interaction_type)
            family_members: list[str] = []

            for index, record in enumerate(records, start=1):
                family_members.extend(
                    self._render_interaction_record(
                        request,
                        interaction_type,
                        record,
                        index,
                    )
                )

            if not family_members:
                continue

            self._group_members(family_group, family_members)
            self.cmd.hide("labels", family_group)
            if parent_group:
                self.cmd.group(parent_group, family_group)
                self.cmd.hide("labels", parent_group)
            created_names.extend(family_members)

        return created_names

    def _render_interaction_record(
        self,
        request: AnalysisRequest,
        interaction_type: str,
        record: Mapping[str, Any],
        index: int,
    ) -> list[str]:
        anchors = self._resolve_distance_anchors(request, interaction_type, record, index)
        if anchors is None:
            return []

        start_ref, end_ref, helper_names = anchors
        distance_name = self.interaction_object_name(
            request,
            interaction_type,
            index,
            role=str(record.get("role", "dash")),
        )

        self.cmd.delete(distance_name)
        self.cmd.distance(distance_name, start_ref, end_ref)
        self.cmd.hide("labels", distance_name)
        self._style_interaction_object(distance_name, interaction_type, record)

        for helper_name in helper_names:
            self.cmd.hide("everything", helper_name)

        return [distance_name, *helper_names]

    def _resolve_distance_anchors(
        self,
        request: AnalysisRequest,
        interaction_type: str,
        record: Mapping[str, Any],
        index: int,
    ) -> tuple[str, str, list[str]] | None:
        selection_pair = self._selection_anchor_pair(record)
        if selection_pair is not None:
            return selection_pair[0], selection_pair[1], []

        coordinate_pair = self._coordinate_anchor_pair(record)
        if coordinate_pair is None:
            return None

        start_name = self.temporary_object_name(request, f"{interaction_type}_start", index)
        end_name = self.temporary_object_name(request, f"{interaction_type}_end", index)
        self._create_hidden_pseudoatom(start_name, coordinate_pair[0])
        self._create_hidden_pseudoatom(end_name, coordinate_pair[1])
        return start_name, end_name, [start_name, end_name]

    def _style_interaction_object(
        self,
        object_name: str,
        interaction_type: str,
        record: Mapping[str, Any],
    ) -> None:
        color = str(
            record.get("color")
            or self.config.get("interactions", interaction_type, "color", default="yellow")
        )
        pymol_color = self._normalize_pymol_color(color)
        width = float(
            record.get("width")
            or self.config.get("interactions", interaction_type, "width", default=3)
        )
        representation = str(record.get("representation", "dashes"))

        self.cmd.hide("labels", object_name)
        self.cmd.show(representation, object_name)
        self.cmd.color(pymol_color, object_name)
        self.cmd.set("dash_color", pymol_color, object_name)
        self.cmd.set("dash_width", width, object_name)

        dash_gap = record.get("dash_gap")
        if dash_gap is not None:
            self.cmd.set("dash_gap", float(dash_gap), object_name)

    def _create_hidden_pseudoatom(self, object_name: str, position: tuple[float, float, float]) -> None:
        self.cmd.delete(object_name)
        self.cmd.pseudoatom(object_name, pos=list(position))
        self.cmd.set(
            "sphere_scale",
            float(self.config.get("render", "helper_pseudoatom_scale", default=0.12)),
            object_name,
        )
        self.cmd.hide("everything", object_name)

    def _group_members(self, group_name: str, members: Sequence[str]) -> None:
        for member in dict.fromkeys(member for member in members if member):
            self.cmd.group(group_name, member)

    def _normalize_interaction_results(self, interaction_results: Any) -> dict[str, list[dict[str, Any]]]:
        normalized: dict[str, list[dict[str, Any]]] = {}

        if interaction_results is None:
            return normalized

        if self._looks_like_interaction_record(interaction_results):
            record = self._coerce_record(interaction_results)
            interaction_type = self._record_interaction_type(record)
            if record is not None and interaction_type:
                normalized.setdefault(interaction_type, []).append(record)
            return normalized

        if isinstance(interaction_results, Mapping):
            for interaction_type, payload in interaction_results.items():
                records = self._records_from_payload(payload, default_type=str(interaction_type))
                if records:
                    normalized.setdefault(str(interaction_type), []).extend(records)
            return normalized

        if self._is_non_string_sequence(interaction_results):
            for payload in interaction_results:
                for record in self._records_from_payload(payload):
                    interaction_type = self._record_interaction_type(record)
                    if interaction_type:
                        normalized.setdefault(interaction_type, []).append(record)

        return normalized

    def _records_from_payload(
        self,
        payload: Any,
        default_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if payload is None:
            return []

        if self._looks_like_interaction_record(payload):
            record = self._coerce_record(payload, default_type=default_type)
            return [record] if record is not None else []

        if isinstance(payload, Mapping):
            for nested_key in ("records", "items", "interactions", "results"):
                nested = payload.get(nested_key)
                if nested is not None:
                    return self._records_from_payload(nested, default_type=default_type)
            return []

        if self._is_non_string_sequence(payload):
            records: list[dict[str, Any]] = []
            for item in payload:
                record = self._coerce_record(item, default_type=default_type)
                if record is not None:
                    records.append(record)
            return records

        return []

    def _coerce_record(
        self,
        payload: Any,
        default_type: str | None = None,
    ) -> dict[str, Any] | None:
        if payload is None:
            return None

        if isinstance(payload, Mapping):
            record = dict(payload)
        elif is_dataclass(payload) and not isinstance(payload, type):
            record = asdict(payload)
        elif hasattr(payload, "__dict__"):
            record = {
                key: value
                for key, value in vars(payload).items()
                if not key.startswith("_")
            }
        else:
            return None

        if default_type and not record.get("interaction_type"):
            record["interaction_type"] = default_type
        elif record.get("family") and not record.get("interaction_type"):
            record["interaction_type"] = str(record["family"])
        elif record.get("kind") and not record.get("interaction_type"):
            record["interaction_type"] = str(record["kind"])

        return record

    def _show_interaction_partners(self, summary: AnalysisSummary) -> None:
        for attr in _INTERACTION_RESULT_ATTRS:
            interaction_results = getattr(summary, attr, None)
            if not interaction_results:
                continue

            normalized = self._normalize_interaction_results(interaction_results)
            shown = set()
            for records in normalized.values():
                for record in records:
                    partner_selection = self._as_selection_reference(record.get("protein_selection"))
                    if not partner_selection or partner_selection in shown:
                        continue
                    partner_display = str(record.get("partner_display", "sticks"))
                    self.cmd.show(partner_display, partner_selection)
                    self.cmd.util.cbaw(partner_selection)
                    if partner_display == "spheres":
                        self.cmd.set(
                            "sphere_scale",
                            float(self.config.get("render", "water_partner_scale", default=0.22)),
                            partner_selection,
                        )
                    shown.add(partner_selection)
            if shown:
                return

    def _show_nearby_ions(self, request: AnalysisRequest) -> None:
        if self.cmd.count_atoms(request.ion_selection) == 0:
            return
        self.cmd.show("spheres", request.ion_selection)
        self.cmd.set(
            "sphere_scale",
            float(self.config.get("render", "ion_partner_scale", default=0.28)),
            request.ion_selection,
        )

    def _hide_nonpolar_hydrogens(self, request: AnalysisRequest) -> None:
        nonpolar_hydrogens = (
            f"(({request.protein_selection}) or ({request.ligand_selection}) or ({request.pocket_selection})) "
            "and hydro and neighbor elem C"
        )
        self.cmd.hide("everything", nonpolar_hydrogens)

    def _normalize_pymol_color(self, color_value: str) -> str:
        if color_value.startswith("#") and len(color_value) == 7:
            return "0x" + color_value[1:].upper()
        return color_value

    def _publication_scene_name(self, request: AnalysisRequest) -> str:
        return self._compose_plugin_name("mp_scene_", request.token, "pre_publication")

    def _viewpoint_name(self, slot: int) -> str:
        return self._compose_plugin_name("mp_view_", f"slot_{slot}")

    def _capture_global_visual_settings(self) -> dict[str, str]:
        setting_names = ("bg_rgb", "ray_trace_mode", "ray_shadows", "ray_trace_gain")
        captured: dict[str, str] = {}
        for name in setting_names:
            captured[name] = str(self.cmd.get(name))
        return captured

    def _restore_global_visual_settings(self, settings: dict[str, str]) -> None:
        if not settings:
            return
        for name, value in settings.items():
            try:
                self.cmd.set(name, value)
            except Exception:
                continue

    def _record_interaction_type(self, record: Mapping[str, Any] | None) -> str | None:
        if not record:
            return None
        interaction_type = record.get("interaction_type") or record.get("family")
        if interaction_type is None:
            return None
        return str(interaction_type)

    def _looks_like_interaction_record(self, payload: Any) -> bool:
        record = self._coerce_record(payload)
        if record is None:
            return False
        return any(
            key in record
            for key in (
                "interaction_type",
                "family",
                "selection1",
                "selection2",
                "start_selection",
                "end_selection",
                "ligand_selection",
                "partner_selection",
                "protein_selection",
                "donor_selection",
                "acceptor_selection",
                "start",
                "end",
                "start_xyz",
                "end_xyz",
                "point1",
                "point2",
            )
        )

    def _selection_anchor_pair(self, record: Mapping[str, Any]) -> tuple[str, str] | None:
        selection_key_pairs = (
            ("start_selection", "end_selection"),
            ("selection1", "selection2"),
            ("from_selection", "to_selection"),
            ("ligand_selection", "partner_selection"),
            ("ligand_selection", "protein_selection"),
            ("donor_selection", "acceptor_selection"),
        )

        for start_key, end_key in selection_key_pairs:
            start_ref = self._as_selection_reference(record.get(start_key))
            end_ref = self._as_selection_reference(record.get(end_key))
            if start_ref and end_ref:
                return start_ref, end_ref

        return None

    def _coordinate_anchor_pair(
        self,
        record: Mapping[str, Any],
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        coordinate_key_pairs = (
            ("start", "end"),
            ("start_xyz", "end_xyz"),
            ("point1", "point2"),
            ("ligand_position", "partner_position"),
        )

        for start_key, end_key in coordinate_key_pairs:
            start_point = self._coerce_xyz(record.get(start_key))
            end_point = self._coerce_xyz(record.get(end_key))
            if start_point is not None and end_point is not None:
                return start_point, end_point

        return None

    def _as_selection_reference(self, value: Any) -> str | None:
        if isinstance(value, str):
            selection = value.strip()
            return selection or None
        return None

    def _coerce_xyz(self, value: Any) -> tuple[float, float, float] | None:
        if not self._is_non_string_sequence(value) or len(value) != 3:
            return None
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            return None

    def _compose_plugin_name(self, prefix: str, *parts: Any) -> str:
        cleaned_parts = [self._sanitize_name_part(part) for part in parts if part is not None]
        return prefix + "_".join(part for part in cleaned_parts if part)

    def _sanitize_name_part(self, value: Any) -> str:
        text = re.sub(r"[^0-9A-Za-z_]+", "_", str(value).strip())
        text = re.sub(r"_+", "_", text).strip("_")
        return text or "item"

    def _is_non_string_sequence(self, value: Any) -> bool:
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
