"""Registry-wide tests for the typed pipeline architecture."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, get_origin
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from med_research.diseases.coverage import ModuleCoverage, module_coverage
from med_research.pipeline.base import PipelineRunResult
from med_research.pipeline.dispatch import execute_module
from med_research.pipeline.registry import get_module, list_modules
from med_research.pipeline.results import (
    RESULT_CONTRACTS,
    validate_result_contract,
)

# These adapters return concrete objects rather than TypedDict payloads.
# NetworkX and Pydantic validate those two boundaries independently.
_NON_TYPED_CONTRACT_MODULES = frozenset({"knowledge_graph", "evidence_workspace"})
_SOURCE_ROOT = Path(__file__).parents[1] / "src" / "med_research"
_DISPATCH_SOURCE = _SOURCE_ROOT / "pipeline" / "dispatch.py"

pytestmark = pytest.mark.unit


class _DirectAdapterMethodVisitor(ast.NodeVisitor):
    """Find adapter execution/reporting calls that bypass ``pipeline.dispatch``."""

    _ADAPTER_METHODS = frozenset({"run", "report", "build_provenance"})
    _ADAPTER_RECEIVER_NAMES = frozenset(
        {"adapter", "module", "pipeline_module", "registered_module"}
    )

    def __init__(self, path: Path) -> None:
        self.path = path
        self.registry_get_module_names = {"get_module"}
        self.registry_module_names = {"registry"}
        self.base_module_names = {"BasePipelineModule"}
        self.adapter_names: set[str] = set()
        self.violations: list[str] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "med_research.pipeline.registry":
            for alias in node.names:
                if alias.name == "get_module":
                    self.registry_get_module_names.add(alias.asname or alias.name)
        elif node.module == "med_research.pipeline.base":
            for alias in node.names:
                if alias.name == "BasePipelineModule":
                    self.base_module_names.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "med_research.pipeline.registry":
                self.registry_module_names.add(alias.asname or "registry")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self._is_registry_get_module(node.value):
            for target in node.targets:
                self.adapter_names.update(self._target_names(target))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._is_registry_get_module(node.value) or self._mentions_base_module(node.annotation):
            self.adapter_names.update(self._target_names(node.target))
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        if node.annotation is not None and self._mentions_base_module(node.annotation):
            self.adapter_names.add(node.arg)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr in self._ADAPTER_METHODS:
            receiver = node.func.value
            if self._is_adapter_receiver(receiver):
                self.violations.append(f"{self.path}:{node.lineno}: {ast.unparse(node)}")
        self.generic_visit(node)

    def _is_registry_get_module(self, node: ast.AST | None) -> bool:
        if not isinstance(node, ast.Call):
            return False
        function = node.func
        if isinstance(function, ast.Name):
            return function.id in self.registry_get_module_names
        return (
            isinstance(function, ast.Attribute)
            and function.attr == "get_module"
            and isinstance(function.value, ast.Name)
            and function.value.id in self.registry_module_names
        )

    def _is_adapter_receiver(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.adapter_names or node.id in self._ADAPTER_RECEIVER_NAMES
        if isinstance(node, ast.Attribute):
            return node.attr in self._ADAPTER_RECEIVER_NAMES
        return self._is_registry_get_module(node)

    def _mentions_base_module(self, node: ast.AST) -> bool:
        return any(
            isinstance(child, ast.Name) and child.id in self.base_module_names
            for child in ast.walk(node)
        )

    @staticmethod
    def _target_names(node: ast.AST) -> set[str]:
        if isinstance(node, ast.Name):
            return {node.id}
        if isinstance(node, (ast.Tuple, ast.List)):
            names: set[str] = set()
            for element in node.elts:
                names.update(_DirectAdapterMethodVisitor._target_names(element))
            return names
        return set()


def _iter_python_sources(root: Path):
    """Yield relevant codebase Python files, bypassing 10,000+ auto-scaffolded disease folders."""
    for p in root.glob("*.py"):
        yield p
    diseases_dir = root / "diseases"
    if diseases_dir.exists():
        for p in diseases_dir.glob("*.py"):
            yield p
    for subdir in ("pipeline", "web", "biomed"):
        d = root / subdir
        if d.exists():
            yield from d.rglob("*.py")


def _find_direct_adapter_methods() -> list[str]:
    """Return adapter execution/reporting calls outside the unified dispatcher."""
    violations: list[str] = []
    for path in _iter_python_sources(_SOURCE_ROOT):
        if path.resolve() == _DISPATCH_SOURCE.resolve():
            continue
        tree = ast.parse(path.read_bytes(), filename=str(path))
        visitor = _DirectAdapterMethodVisitor(path)
        visitor.visit(tree)
        violations.extend(visitor.violations)
    return violations


def _sample_result(contract: Any) -> Any:
    """Create the smallest valid payload for a registry result contract."""
    return [] if get_origin(contract) is list else {}


def _iter_api_routes(app: Any) -> list[Any]:
    """Return every registered ``APIRoute`` regardless of FastAPI version.

    FastAPI >= 0.140 wraps included routers in ``_IncludedRouter`` objects
    (exposed via ``effective_route_contexts()``) instead of flattening
    ``APIRoute`` instances directly into ``app.routes``, so a plain
    ``isinstance(route, APIRoute)`` scan silently finds nothing. The
    ``hasattr`` guard keeps the helper compatible with both layouts.
    """
    from fastapi.routing import APIRoute

    routes: list[Any] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
        elif hasattr(route, "effective_route_contexts"):
            for context in route.effective_route_contexts():
                original = getattr(context, "original_route", None)
                if isinstance(original, APIRoute):
                    routes.append(original)
    return routes


@pytest.mark.parametrize("module_id", list_modules())
def test_registered_module_has_typed_dispatch_contract(
    module_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every registered module has one typed result and report seam.

    The engine is replaced with a contract-shaped payload so this remains
    deterministic and cheap. The test still exercises the real dispatch path:
    coverage gating, result validation, progress callback forwarding, report
    provenance, and report-path packaging.
    """
    module = get_module(module_id)
    contract = RESULT_CONTRACTS.get(module_id)
    if contract is None:
        assert module_id in _NON_TYPED_CONTRACT_MODULES
        payload: Any = {}
    else:
        payload = _sample_result(contract)

    coverage = ModuleCoverage(
        disease_id="ra",
        module=getattr(module, "_COVERAGE_MODULE", module_id),
        level="full",
        status="ready",
        curated_inputs=list(module.coverage_inputs()),
    )
    report_path = tmp_path / f"{module_id}.html"
    run = MagicMock(return_value=payload)
    build_provenance = MagicMock(return_value={"module": module_id, "fingerprint": "test"})
    report = MagicMock(return_value=report_path)
    monkeypatch.setattr(module, "run", run)
    monkeypatch.setattr(module, "build_provenance", build_provenance)
    monkeypatch.setattr(module, "report", report)

    calls: list[tuple[str, int, int]] = []

    def progress(step: str, current: int, total: int) -> None:
        calls.append((step, current, total))

    with (
        patch("med_research.pipeline.dispatch.get_module", return_value=module),
        patch("med_research.pipeline.dispatch.module_coverage", return_value=coverage),
    ):
        result = execute_module(
            module_id,
            "ra",
            export_html=True,
            progress_callback=progress,
        )

    assert isinstance(result, PipelineRunResult)
    assert result.success is True
    assert result.data == payload
    assert result.report_path == report_path
    assert result.provenance == {"module": module_id, "fingerprint": "test"}
    run.assert_called_once()
    engine_progress = run.call_args.kwargs["progress_callback"]
    assert callable(engine_progress)
    engine_progress("contract", 1, 1)
    assert calls == [("contract", 1, 1)]
    build_provenance.assert_called_once()
    report.assert_called_once_with(payload, "ra", provenance=result.provenance)


def test_registered_adapter_methods_are_only_called_by_dispatch() -> None:
    """Prevent production code from bypassing centralized execution and reporting."""
    violations = _find_direct_adapter_methods()
    assert not violations, (
        "Registered adapter .run(), .report(), and .build_provenance() calls "
        "must go through med_research.pipeline.dispatch:\n" + "\n".join(violations)
    )


def test_registry_catalog_contains_generated_module_metadata() -> None:
    """Aliases, DAG metadata, coverage inputs, and schemas come from adapters."""
    from med_research.pipeline.registry import list_modules, module_catalog

    catalog = module_catalog()
    assert [entry["module_id"] for entry in catalog] == list_modules()

    literature = next(entry for entry in catalog if entry["module_id"] == "literature_mining")
    assert "literature" in literature["aliases"]
    assert literature["coverage_module"] == "literature"
    assert literature["coverage_inputs"]
    assert literature["depends_on"] == ["knowledge_graph"]
    assert literature["result_contract"] == "LiteratureMiningResult"
    assert literature["response_schema"]["title"] == "LiteratureMiningResult"
    assert "request_schema" in literature
    assert literature["request_validators"] == literature["request_schema"]["validators"]
    assert literature["request_validators"] == []
    assert "max_articles" in literature["request_schema"]["properties"]
    assert "graph" not in literature["request_schema"]["properties"]

    workspace = next(entry for entry in catalog if entry["module_id"] == "evidence_workspace")
    assert workspace["request_validators"] == workspace["request_schema"]["validators"]
    assert {rule["id"] for rule in workspace["request_validators"]} == {
        "sources_non_empty",
        "date_range_order",
    }
    assert workspace["persisted_request_schema_version"] == "1.0"
    assert workspace["persisted_result_schema_version"] == "1.1"
    assert workspace["persisted_request_schema"]["properties"]["schema_version"]["const"] == "1.0"
    assert workspace["persisted_result_schema"]["properties"]["schema_version"]["const"] == "1.1"

    knowledge_graph = next(entry for entry in catalog if entry["module_id"] == "knowledge_graph")
    assert knowledge_graph["result_contract"] == "KnowledgeGraphResult"
    assert knowledge_graph["response_schema"]["type"] == "object"


def test_workspace_request_schema_matches_research_request_contract() -> None:
    """Keep registry metadata aligned with Workspace validation and defaults."""
    from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
    from med_research.pipeline.registry import module_request_schema

    registry_schema = module_request_schema("evidence_workspace")
    request_schema = ResearchRequest.model_json_schema()
    registry_fields = registry_schema["properties"]
    request_fields = {
        name: definition
        for name, definition in request_schema["properties"].items()
        if name != "disease_id"
    }

    assert set(registry_fields) == set(request_fields)
    assert registry_schema["required"] == ["question"]
    assert request_schema["required"] == ["disease_id", "question"]
    assert registry_schema["validators"] == [
        {
            "id": "sources_non_empty",
            "type": "min_items",
            "field": "sources",
            "value": 1,
            "message": "at least one evidence source is required",
        },
        {
            "id": "date_range_order",
            "type": "field_comparison",
            "fields": ["date_from", "date_to"],
            "operator": "<=",
            "allow_missing": True,
            "message": "date_from must be on or before date_to",
        },
    ]

    def non_null_branch(definition: dict[str, Any]) -> dict[str, Any]:
        branches = definition.get("anyOf")
        if not branches:
            return definition
        return next(branch for branch in branches if branch.get("type") != "null")

    for name, request_definition in request_fields.items():
        registry_definition = registry_fields[name]
        request_branch = non_null_branch(request_definition)
        if name == "sources":
            assert registry_definition["body_type"] == "array"
            assert registry_definition["items"]["enum"] == request_branch["items"]["enum"]
            assert registry_definition["minItems"] == 1
        else:
            for key in (
                "type",
                "format",
                "enum",
                "minimum",
                "maximum",
                "minLength",
                "maxLength",
            ):
                if key in request_branch:
                    assert registry_definition.get(key) == request_branch[key], (
                        f"Workspace field '{name}' drifted for {key}"
                    )

        if request_definition.get("default") is not None:
            registry_default = registry_definition.get(
                "body_default", registry_definition.get("default")
            )
            assert registry_default == request_definition["default"], (
                f"Workspace field '{name}' default drifted"
            )

    # JSON Schema cannot express these cross-field and collection validators;
    # keep executable checks beside the metadata comparison so removing a
    # ResearchRequest validator also breaks this contract test.
    with pytest.raises(ValidationError):
        ResearchRequest(disease_id="sle", question="targets", sources=[])
    with pytest.raises(ValidationError):
        ResearchRequest(
            disease_id="sle",
            question="targets",
            date_from="2025-02-01",
            date_to="2025-01-01",
        )


def test_workspace_generated_cli_and_web_models_match_contract() -> None:
    """Keep generated CLI and JSON-body models aligned with Workspace input."""
    import argparse

    from med_research.cli import _build_parser
    from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
    from med_research.pipeline.registry import module_request_schema
    from med_research.web.models.jobs import module_body_request_model

    registry_schema = module_request_schema("evidence_workspace")
    request_schema = ResearchRequest.model_json_schema()
    body_schema = module_body_request_model("evidence_workspace").model_json_schema()

    def non_null_branch(definition: dict[str, Any]) -> dict[str, Any]:
        branches = definition.get("anyOf")
        if not branches:
            return definition
        return next(branch for branch in branches if branch.get("type") != "null")

    # The generated FastAPI body model includes the server-visible disease_id;
    # all other fields must carry the same type, enum, bounds, and defaults as
    # the domain request model.
    assert set(body_schema["properties"]) == set(request_schema["properties"])
    assert body_schema["required"] == request_schema["required"]
    for name, request_definition in request_schema["properties"].items():
        body_definition = body_schema["properties"][name]
        request_branch = non_null_branch(request_definition)
        body_branch = non_null_branch(body_definition)
        for key in (
            "type",
            "format",
            "enum",
            "minimum",
            "maximum",
            "minLength",
            "maxLength",
        ):
            if key in request_branch:
                assert body_branch.get(key) == request_branch[key], (
                    f"Generated Workspace body field '{name}' drifted for {key}"
                )
        if "default" in request_definition:
            assert body_definition.get("default") == request_definition["default"]

    body_model = module_body_request_model("evidence_workspace")
    assert body_model.model_validate(
        {"disease_id": "sle", "question": "Find targets", "sources": ["pubmed"]}
    ).sources == ("pubmed",)
    with pytest.raises(ValidationError):
        body_model.model_validate({"disease_id": "sle", "question": "Find targets", "sources": []})
    with pytest.raises(ValidationError):
        body_model.model_validate(
            {"disease_id": "sle", "question": "Find targets", "candidate_type": "invalid"}
        )

    # The specialized Workspace CLI is generated from the same registry
    # properties, with disease_id represented by its established --disease
    # flag and sources represented as a comma-separated string.
    parser = _build_parser()
    subparsers = next(action for action in parser._actions if action.dest == "command")
    workspace_parser = subparsers.choices["workspace"]
    actions = {action.dest: action for action in workspace_parser._actions}
    schema_fields = set(registry_schema["properties"])
    assert schema_fields <= set(actions)
    assert "disease" in actions

    question_action = actions["question"]
    assert question_action.required is True
    assert "-q" in question_action.option_strings
    max_evidence_action = actions["max_evidence"]
    assert max_evidence_action.default == registry_schema["properties"]["max_evidence"]["default"]
    assert max_evidence_action.type("50") == 50
    with pytest.raises(argparse.ArgumentTypeError):
        max_evidence_action.type("0")

    candidate_action = actions["candidate_type"]
    assert candidate_action.choices == registry_schema["properties"]["candidate_type"]["enum"]
    llm_action = actions["enable_llm"]
    assert llm_action.default is True
    assert llm_action.const is False
    assert llm_action.option_strings == ["--no-llm"]

    parsed = parser.parse_args(
        [
            "workspace",
            "--disease",
            "sle",
            "--question",
            "Find targets",
            "--sources",
            "pubmed,gwas",
            "--candidate-type",
            "targets",
            "--max-evidence",
            "25",
            "--model",
            "gpt-test",
        ]
    )
    assert parsed.model == "gpt-test"
    assert parsed.max_evidence == 25
    assert parsed.candidate_type == "targets"


def test_workspace_persisted_versions_are_exposed_in_openapi() -> None:
    """System and run-history OpenAPI metadata expose persisted schema versions."""
    from med_research.web.main import app

    openapi = app.openapi()
    catalog_schema = openapi["components"]["schemas"]["PipelineModuleCatalogEntry"]
    assert "persisted_request_schema_version" in catalog_schema["properties"]
    assert "persisted_result_schema_version" in catalog_schema["properties"]
    assert (
        openapi["paths"]["/api/system/modules"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/PipelineModulesResponse"
    )

    run_schema = openapi["components"]["schemas"]["WorkspaceRunResponse"]
    assert run_schema["properties"]["request_schema_version"]["const"] == "1.0"
    assert run_schema["properties"]["result_schema_version"]["const"] == "1.1"
    assert run_schema["properties"]["request"]["$ref"] == "#/components/schemas/WorkspaceRequestV1"
    assert (
        run_schema["properties"]["dossier"]["anyOf"][0]["$ref"]
        == "#/components/schemas/WorkspaceResultV1"
    )


def test_registry_catalog_generates_application_routes() -> None:
    """CLI, Celery, and web routes are derived from one registry catalog."""
    from med_research.pipeline.registry import (
        celery_task_routes,
        module_catalog,
        module_job_aliases,
    )

    catalog = module_catalog()
    aliases = module_job_aliases()
    routes = celery_task_routes()

    assert {entry["module_id"] for entry in catalog} == set(list_modules())
    for entry in catalog:
        module_id = entry["module_id"]
        assert entry["cli_command"]
        assert entry["cli_help"]
        assert module_id in entry["job_aliases"]
        cli_alias = entry["cli_command"].replace("-", "_")
        assert aliases[cli_alias] == module_id
        assert entry["celery_task"] in routes
        assert routes[entry["celery_task"]]["queue"] == "pipeline"
        assert routes[entry["celery_task"]]["routing_key"] == f"pipeline.{module_id}"


def test_catalog_celery_routes_have_registered_tasks() -> None:
    """Every catalog task route points to a registered Celery task."""
    from med_research.pipeline.registry import module_catalog
    from med_research.web.tasks.analysis_tasks import celery_app

    for entry in module_catalog():
        assert entry["celery_task"] in celery_app.tasks


def test_generated_cli_entry_point_uses_registry_metadata() -> None:
    """Modules without specialized handlers still receive a CLI command."""
    from med_research.cli import _build_parser

    args = _build_parser().parse_args(
        ["enrichment", "--disease", "ra", "--untargeted-only", "--no-cache"]
    )
    assert args.registry_module_id == "enrichment"
    assert args.disease == "ra"
    assert args.untargeted_only is True
    assert args.no_cache is True


def test_pipeline_gateway_exposes_typed_boundaries(tmp_path: Path) -> None:
    """CLI, web, and Celery callers can share one gateway facade."""
    from med_research.pipeline.gateway import PipelineGateway

    gateway = PipelineGateway()
    expected_result = PipelineRunResult(success=True, data={"hits": []})
    expected_coverage = MagicMock(spec=ModuleCoverage)
    expected_provenance = {"module": "gwas", "fingerprint": "test"}
    expected_report = tmp_path / "gwas.html"

    with (
        patch(
            "med_research.pipeline.dispatch.execute_module", return_value=expected_result
        ) as execute,
        patch(
            "med_research.pipeline.dispatch.module_coverage_for", return_value=expected_coverage
        ) as coverage,
        patch(
            "med_research.pipeline.dispatch.build_module_provenance",
            return_value=expected_provenance,
        ) as provenance,
        patch(
            "med_research.pipeline.dispatch.render_module_report", return_value=expected_report
        ) as report,
    ):
        result = gateway.execute("gwas", "ra", export_html=True, max_studies=5)
        metadata = gateway.coverage("gwas", "ra")
        built = gateway.provenance("gwas", "ra", run_id="test")
        path = gateway.report("gwas", {"hits": []}, "ra", run_id="test")

    execute.assert_called_once_with(
        "gwas", "ra", export_html=True, progress_callback=None, max_studies=5
    )
    coverage.assert_called_once_with("gwas", "ra")
    provenance.assert_called_once_with("gwas", "ra", run_id="test")
    report.assert_called_once_with("gwas", {"hits": []}, "ra", run_id="test")
    assert result is expected_result
    assert metadata is expected_coverage
    assert built == expected_provenance
    assert path == expected_report


def test_result_contract_validation_preserves_payload() -> None:
    """Validation catches malformed records without replacing raw result data."""
    payload = {"status": "ready", "custom_runtime_field": [1, 2, 3]}
    assert validate_result_contract("gwas", payload) is payload

    with pytest.raises(ValidationError):
        validate_result_contract("adverse_events", [{"drug_id": "incomplete"}])


def test_pipeline_run_result_is_generic_at_runtime() -> None:
    """The envelope can carry a concrete result type without changing its API."""
    result: PipelineRunResult[list[dict[str, int]]] = PipelineRunResult(
        success=True,
        data=[{"count": 1}],
    )
    assert result.data == [{"count": 1}]
    assert result.errors == []


@pytest.mark.parametrize(
    ("module_id", "route_path"),
    [
        ("gwas", "/api/bioinformatics/gwas"),
        ("enrichment", "/api/bioinformatics/enrichment"),
        ("ppi", "/api/bioinformatics/ppi"),
        ("literature_mining", "/api/literature"),
        ("virtual_screening", "/api/screening"),
        ("clinical_trials", "/api/trials"),
        ("ml_predictor", "/api/ml/predict"),
        ("drug_synergy", "/api/synergy/pairs"),
        ("adverse_events", "/api/safety/profiles"),
        ("gene_expression", "/api/expression/correlate"),
        ("car_t_predictor", "/api/cart/suitability"),
        ("biomarker_discovery", "/api/biomarker/discover"),
        ("semantic_search", "/api/semantic/search"),
        ("evidence_gather", "/api/evidence/gather"),
        ("cross_disease", "/api/cross-disease/overlap"),
        ("drug_repurposing", "/api/repurpose/candidates"),
        ("knowledge_graph", "/api/kg/stats"),
    ],
)
def test_api_routes_validate_contract_backed_results(
    module_id: str,
    route_path: str,
) -> None:
    """Every public module route has FastAPI response-model validation."""
    from med_research.web.main import app

    assert module_id in RESULT_CONTRACTS or module_id in _NON_TYPED_CONTRACT_MODULES
    route = next(route for route in _iter_api_routes(app) if route.path == route_path)
    assert route.response_model is not None


def test_module_coverage_contract_exposes_status_and_inputs() -> None:
    """Coverage metadata is available before any engine work starts."""
    for module_id in list_modules():
        module = get_module(module_id)
        assert module.module_id == module_id
        inputs = module.coverage_inputs()
        coverage = module_coverage(
            "ra",
            getattr(module, "_COVERAGE_MODULE", module_id),
            inputs,
        )
        assert coverage.disease_id == "ra"
        assert coverage.status in {"ready", "limited_coverage", "blocked"}
        assert isinstance(getattr(module, "_COVERAGE_MODULE", module_id), str)
