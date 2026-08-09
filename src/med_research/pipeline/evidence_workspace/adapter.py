"""Registry adapter for the evidence-to-hypothesis workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier, ResearchRequest
from med_research.pipeline.evidence_workspace.sources import EvidenceSource
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module


def _default_question(disease_id: str) -> str:
    from med_research.diseases.base import Disease

    disease = Disease(disease_id)
    return f"Treatment targets for {disease.profile.name}"


def _research_request(disease_id: str, **opts: Unpack[AdapterOptions]) -> ResearchRequest:
    request = opts.get("request")
    if isinstance(request, ResearchRequest):
        return request

    request_fields = set(ResearchRequest.model_fields)
    request_kwargs = {
        key: value for key, value in opts.items() if key in request_fields
    }
    request_kwargs.setdefault("disease_id", disease_id)
    request_kwargs.setdefault("question", _default_question(disease_id))
    return ResearchRequest.model_validate(request_kwargs)


@register_module
class EvidenceWorkspaceModule(BasePipelineModule):
    """Adapter around ``evidence_workspace.workspace`` dossier orchestration."""

    _COVERAGE_MODULE = "evidence_workspace"

    @property
    def module_id(self) -> str:
        return "evidence_workspace"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ()

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> EvidenceDossier:
        from med_research.pipeline.evidence_workspace.workspace import run_workspace

        request = _research_request(disease_id, **opts)
        return run_workspace(
            request,
            # The workspace option maps source names to EvidenceSource objects,
            # unlike the list-of-names ``sources`` option of the other modules.
            sources=cast(dict[str, EvidenceSource] | None, opts.get("sources")),
            graph=opts.get("graph"),
            llm_client=opts.get("llm_client"),
            model=opts.get("model"),
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: EvidenceDossier,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.evidence_workspace.report import write_html

        dossier = results
        if provenance is not None:
            manifest = dict(results.manifest)
            manifest["provenance"] = provenance
            dossier = results.model_copy(update={"manifest": manifest})

        output = Path(__file__).parent / f"report_{disease_id}.html"
        return write_html(dossier, output)

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> dict:
        sources = opts.get("sources") or ("pubmed", "clinical_trials")
        extra: dict[str, Any] = {
            key: value
            for key, value in opts.items()
            if key not in {"sources", "question", "cache_or_live", "candidate_type"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=list(sources),
            query=opts.get("question") or _default_question(disease_id),
            cache_or_live=opts.get("cache_or_live", "cache"),
            scoring={
                "ranking": "support/contradiction/recency/quality heuristic",
                "candidate_type": opts.get("candidate_type", "both"),
            },
            **extra,
        )
