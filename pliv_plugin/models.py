"""Shared data models for the plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class LigandTarget:
    """One ligand instance inside a complex object."""

    chain: str = ""
    resi: str = ""
    resn: str = ""
    object_name: str = ""

    @property
    def label(self) -> str:
        if self.object_name:
            return self.object_name
        return f"{self.chain}:{self.resi}:{self.resn}"


@dataclass(frozen=True)
class AnalysisRequest:
    """Normalized request built from the GUI state."""

    input_mode: str
    complex_name: str
    ligand: LigandTarget
    interaction_types: List[str]
    profile_name: str
    token: str
    ligand_selection: str
    protein_selection: str
    pocket_selection: str
    water_selection: str
    ion_selection: str
    group_name: str


@dataclass
class AnalysisSummary:
    """Minimal summary object returned by the skeleton engine."""

    ligand_atom_count: int = 0
    pocket_atom_count: int = 0
    selected_interaction_types: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_result(
        self,
        request: Optional[AnalysisRequest] = None,
        interactions: Optional[List["InteractionRecord"]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AnalysisResult":
        """Promote the lightweight summary into a structured analysis payload."""

        return AnalysisResult(
            request=request,
            summary=self,
            interactions=list(interactions or []),
            metadata=dict(metadata or {}),
        )


@dataclass
class InteractionRecord:
    """Structured representation of one detected interaction."""

    interaction_type: str
    ligand_atoms: List[int] = field(default_factory=list)
    partner_atoms: List[int] = field(default_factory=list)
    partner_label: str = ""
    measurements: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Future-facing analysis payload with request, summary, and interaction rows."""

    request: Optional[AnalysisRequest] = None
    summary: AnalysisSummary = field(default_factory=AnalysisSummary)
    interactions: List[InteractionRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def interaction_count(self) -> int:
        return len(self.interactions)

    def interaction_types(self) -> List[str]:
        """Return unique interaction types in encounter order."""

        ordered_types: List[str] = []
        for record in self.interactions:
            if record.interaction_type not in ordered_types:
                ordered_types.append(record.interaction_type)
        return ordered_types
