"""Derive disease-local drug-safety inputs from a module's own knowledge graph.

Everything produced here is *inferred*, never curated. Every writer records that
fact in ``adverse_events.json`` through ``inferred_inputs`` and ``limitations``
so downstream reports can tell class-level inference apart from hand curation.

Data reality this module is built around
---------------------------------------
* ``drugs.json`` rows are one per drug-target pair, so the same drug id recurs
  with different targets. Derived profiles are therefore de-duplicated by drug.
* The ``adverse_effects`` field is effectively never populated by scaffolding,
  so per-drug adverse events cannot be read off the catalog. They are instead
  summarised from the drug's **pharmacologic class**, matched on the
  ``mechanism``/``type``/``target`` text the catalog does carry (ChEMBL-style
  class names such as ``"tubulin inhibitor"`` or
  ``"glucocorticoid receptor agonist"``). This mirrors the
  ``class_level_adverse_event_patterns`` approach already used by ``asthma``.
* ``category`` is usually empty, so it is not relied upon.

Design rules
------------
1. **No drug is silently dropped.** An empty ``DRUG_SAFETY_RISK`` is read by the
   safety profiler as "zero risk", which is a false safety signal. Drugs whose
   class cannot be resolved land in ``undetermined_risk`` instead of being
   labelled low risk or vanishing.
2. **Every emitted value is traceable** to the module's own data or to the
   explicit class table below. Where nothing is known, lists stay empty and the
   limitations say so rather than implying a clean safety record.

The tier scores are research heuristics for corpus triage. They are not
label-derived contraindications and not individualized clinical risk.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

RISK_TIERS: tuple[str, ...] = (
    "high_risk",
    "moderate_risk",
    "low_risk",
    "undetermined_risk",
)

#: Only these three tiers encode an actual safety opinion. ``undetermined_risk``
#: is an explicit "we could not resolve this drug's class" bucket.
CLASSIFIED_TIERS: tuple[str, ...] = ("high_risk", "moderate_risk", "low_risk")

AE_SCHEMA_VERSION = "1"
AE_SOURCE = "class_level_inference_from_disease_drug_catalog"
AE_EVIDENCE_GRADE = "inferred_class_default"

STANDARD_LIMITATIONS: tuple[str, ...] = (
    "Safety scores are research heuristics, not individualized clinical risk assessments.",
    "Adverse-event lists are class-level summaries, not label-derived contraindications "
    "or pharmacovigilance counts.",
    "Validate current labels and patient-specific contraindications before use.",
)

# ── Named-agent patterns ─────────────────────────────────────────────────
# Ordered checks: HIGH first, then LOW, then MODERATE. The order is load-bearing
# because some agents match more than one pattern, and this resolution order is
# already baked into curated configs.

_HIGH_RISK_PATTERNS = re.compile(
    r"interferon|anti-tnf|tnf inhibitor|tnf-alpha|checkpoint|alemtuzumab|"
    r"natalizumab|bleomycin|procainamide|hydralazine|isoniazid|minocycline|"
    r"pentamidine|diazoxide|paclitaxel|gemcitabine|bromocriptine|"
    r"ustekinumab|infliximab|adalimumab|etanercept|certolizumab|golimumab",
    re.I,
)
_MODERATE_RISK_PATTERNS = re.compile(
    r"jak inhibitor|janus kinase|azathioprine|methotrexate|sulfasalazine|"
    r"teriflunomide|dimethyl fumarate|cladribine|penicillamine|mercaptopurine|"
    r"tofacitinib|belimumab|rituximab|fingolimod|hydroxychloroquine|"
    r"glucocorticoid|corticosteroid|prednisone|mycophenolate|cyclosporine|"
    r"thalidomide|levamisole|gold salt|budesonide|thiazide",
    re.I,
)
_LOW_RISK_PATTERNS = re.compile(
    r"nsaid|mesalamine|insulin|metformin|ace inhibitor|proton pump|"
    r"pilocarpine|cevimeline|iloprost|calcium channel|glatiramer|"
    r"hydroxychloroquine|statins|oral contraceptive",
    re.I,
)


@dataclass(frozen=True)
class DrugClassRule:
    """A pharmacologic class recognised in ``mechanism``/``type`` text.

    ``tier`` is only used when no named-agent pattern matched; the adverse-event
    lists are used whenever the class is recognised, whatever the tier.
    """

    name: str
    pattern: re.Pattern[str]
    tier: str
    common_ae: tuple[str, ...] = ()
    severe_ae: tuple[str, ...] = ()


#: Class-level adverse-event summaries. These are deliberate, coarse textbook
#: summaries of the class - not of any individual drug - and every one of them is
#: reported as inferred downstream.
DRUG_CLASS_RULES: tuple[DrugClassRule, ...] = (
    DrugClassRule(
        name="cytotoxic_antimicrotubular",
        pattern=re.compile(r"tubulin|microtubule|vinca|taxane", re.I),
        tier="high_risk",
        common_ae=("nausea", "fatigue", "alopecia", "peripheral neuropathy"),
        severe_ae=("myelosuppression", "neutropenic sepsis", "peripheral neuropathy"),
    ),
    DrugClassRule(
        name="cytotoxic_dna_synthesis",
        pattern=re.compile(
            r"dna polymerase|topoisomerase|dna (intercal|damag)|alkylating|"
            r"antimetabol|cytotoxic",
            re.I,
        ),
        tier="high_risk",
        common_ae=("nausea", "fatigue", "mucositis", "myelosuppression"),
        severe_ae=("myelosuppression", "hepatotoxicity", "tumour lysis syndrome"),
    ),
    DrugClassRule(
        name="interferon_agonist",
        pattern=re.compile(r"interferon", re.I),
        tier="high_risk",
        common_ae=("flu-like symptoms", "fatigue", "myalgia"),
        severe_ae=("hepatotoxicity", "depression", "thyroid dysfunction"),
    ),
    DrugClassRule(
        name="corticosteroid",
        pattern=re.compile(r"glucocorticoid|corticosteroid|cortisol receptor", re.I),
        tier="moderate_risk",
        common_ae=("hyperglycaemia", "weight gain", "insomnia", "dyspepsia"),
        severe_ae=("adrenal suppression", "osteoporosis", "immunosuppression"),
    ),
    DrugClassRule(
        name="b_cell_depleting_antibody",
        pattern=re.compile(r"cd20|b-lymphocyte antigen|b cell deplet", re.I),
        tier="moderate_risk",
        common_ae=("infusion related reaction", "fatigue", "nausea"),
        severe_ae=(
            "progressive multifocal leukoencephalopathy",
            "sepsis",
            "hepatitis b reactivation",
        ),
    ),
    DrugClassRule(
        name="kinase_inhibitor",
        pattern=re.compile(
            r"tyrosine-protein kinase|kinase inhibitor|jak1|jak2|jak3|"
            r"egfr|erbb|vegfr|pdgfr|bcr-abl|btk|alk inhibitor",
            re.I,
        ),
        tier="moderate_risk",
        common_ae=("rash", "diarrhoea", "fatigue", "nausea"),
        severe_ae=("hepatotoxicity", "interstitial lung disease", "thromboembolism"),
    ),
    DrugClassRule(
        name="calcineurin_inhibitor",
        pattern=re.compile(r"fk506|calcineurin|cyclophilin", re.I),
        tier="moderate_risk",
        common_ae=("tremor", "headache", "hypertension"),
        severe_ae=("nephrotoxicity", "sepsis", "neurotoxicity"),
    ),
    DrugClassRule(
        name="phosphodiesterase_inhibitor",
        pattern=re.compile(r"phosphodiesterase|pde\d", re.I),
        tier="moderate_risk",
        common_ae=("nausea", "diarrhoea", "headache"),
        severe_ae=("weight loss", "psychiatric events"),
    ),
    DrugClassRule(
        name="growth_factor_receptor_agonist",
        pattern=re.compile(
            r"erythropoietin|colony stimulating factor|growth hormone receptor|"
            r"thrombopoietin",
            re.I,
        ),
        tier="moderate_risk",
        common_ae=("headache", "hypertension", "injection site reaction"),
        severe_ae=("thromboembolism", "pure red cell aplasia"),
    ),
    DrugClassRule(
        name="adrenergic_antagonist",
        # ``\bantagonist`` keeps this from being shadowed by the agonist rule, and
        # keeps "antagonist" from matching ``\bagonist`` below.
        pattern=re.compile(r"adrenergic receptor.*\bantagonist\b|beta blocker", re.I),
        tier="moderate_risk",
        common_ae=("fatigue", "bradycardia", "cold extremities"),
        severe_ae=("bronchospasm", "heart block", "hypoglycaemia"),
    ),
    DrugClassRule(
        name="cyclooxygenase_inhibitor",
        pattern=re.compile(r"cyclooxygenase|cox-?2|prostaglandin", re.I),
        tier="low_risk",
        common_ae=("dyspepsia", "nausea", "abdominal pain"),
        severe_ae=("gastrointestinal bleeding", "nephrotoxicity"),
    ),
    DrugClassRule(
        name="adrenergic_agonist",
        pattern=re.compile(r"adrenergic receptor.*\bagonist\b", re.I),
        tier="low_risk",
        common_ae=("tremor", "tachycardia", "headache"),
        severe_ae=("cardiac arrhythmia", "hypertension"),
    ),
    DrugClassRule(
        name="somatostatin_analogue",
        pattern=re.compile(r"somatostatin", re.I),
        tier="low_risk",
        common_ae=("diarrhoea", "abdominal pain", "nausea"),
        severe_ae=("cholelithiasis", "bradycardia"),
    ),
    DrugClassRule(
        name="gaba_modulator",
        pattern=re.compile(r"gaba|benzodiazepine|barbiturate", re.I),
        tier="low_risk",
        common_ae=("somnolence", "dizziness", "confusion"),
        severe_ae=("respiratory depression", "dependence"),
    ),
    DrugClassRule(
        name="antimicrobial_ribosomal",
        pattern=re.compile(r"ribosome|50s|30s|80s|elongation factor|folate synthesis", re.I),
        tier="low_risk",
        common_ae=("nausea", "diarrhoea", "abdominal pain"),
        severe_ae=("nephrotoxicity", "ototoxicity", "clostridioides difficile infection"),
    ),
    DrugClassRule(
        name="sodium_channel_blocker",
        pattern=re.compile(r"sodium channel", re.I),
        tier="low_risk",
        common_ae=("dizziness", "somnolence", "nausea"),
        severe_ae=("cardiac conduction disturbance", "respiratory depression"),
    ),
    DrugClassRule(
        name="serotonin_receptor_modulator",
        pattern=re.compile(r"serotonin|5-ht", re.I),
        tier="low_risk",
        common_ae=("headache", "dizziness", "constipation"),
        severe_ae=("qt prolongation", "serotonin syndrome"),
    ),
)

_AE_SPLIT = re.compile(r"[;,/]| and | with ")


def _drug_text(drug: Mapping[str, Any]) -> str:
    """Flatten the descriptive fields a class opinion can legitimately rest on."""
    parts = [
        drug.get("id", ""),
        drug.get("name", ""),
        drug.get("type", ""),
        drug.get("target", ""),
        drug.get("mechanism", ""),
        drug.get("category", ""),
        drug.get("adverse_effects", ""),
    ]
    return " ".join(str(p) for p in parts if p)


def _drug_label(drug: Mapping[str, Any]) -> str:
    drug_id = str(drug.get("id") or "")
    name = str(drug.get("name") or "").split("(")[0].strip()
    return (name or drug_id).lower()


def match_drug_class(text: str) -> DrugClassRule | None:
    """Return the first pharmacologic class recognised in ``text``, if any."""
    for rule in DRUG_CLASS_RULES:
        if rule.pattern.search(text):
            return rule
    return None


def classify_drug_tier(drug: Mapping[str, Any]) -> tuple[str, str]:
    """Return ``(tier, basis)`` for one drug.

    ``basis`` is ``"pattern"`` for a specific named-agent match, ``"class"`` for
    a pharmacologic-class match, and ``"undetermined"`` when nothing matched. The
    tier is never ``None``: an unresolved drug belongs in ``undetermined_risk``
    so it stays visible instead of being scored as safe by default.
    """
    text = _drug_text(drug)
    if _HIGH_RISK_PATTERNS.search(text):
        return "high_risk", "pattern"
    if _LOW_RISK_PATTERNS.search(text):
        return "low_risk", "pattern"
    if _MODERATE_RISK_PATTERNS.search(text):
        return "moderate_risk", "pattern"
    rule = match_drug_class(text)
    if rule is not None:
        return rule.tier, "class"
    return "undetermined_risk", "undetermined"


def _unique_drugs(drugs_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Collapse drug-target rows into one record per drug id.

    ``drugs.json`` stores one row per drug-target pair, so a drug with several
    targets appears several times. Rows are merged on ``id``; descriptive text is
    concatenated so a match on any target's text still recognises the class.
    """
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in drugs_payload.get("drugs", []) or []:
        if not isinstance(raw, Mapping):
            continue
        drug_id = str(raw.get("id") or "").strip()
        if not drug_id:
            continue
        if drug_id not in merged:
            merged[drug_id] = {
                "id": drug_id,
                "name": str(raw.get("name") or drug_id),
                "type": str(raw.get("type") or ""),
                "mechanism": str(raw.get("mechanism") or ""),
                "target": str(raw.get("target") or ""),
                "category": str(raw.get("category") or ""),
                "adverse_effects": str(raw.get("adverse_effects") or ""),
            }
            order.append(drug_id)
            continue
        entry = merged[drug_id]
        for key in ("mechanism", "target", "type", "category", "adverse_effects"):
            value = str(raw.get(key) or "").strip()
            if value and value not in entry[key]:
                entry[key] = f"{entry[key]} {value}".strip()
    return [merged[drug_id] for drug_id in order]


def derive_drug_safety_risk(
    drugs_payload: Mapping[str, Any],
) -> dict[str, list[str]]:
    """Bucket every drug in a ``drugs.json`` payload by inferred safety tier.

    Unlike the historical derivation, unclassifiable drugs are retained under
    ``undetermined_risk`` instead of being dropped.
    """
    tiers: dict[str, list[str]] = {tier: [] for tier in RISK_TIERS}
    for drug in _unique_drugs(drugs_payload):
        label = _drug_label(drug) or str(drug["id"])
        tier, _basis = classify_drug_tier(drug)
        if label not in tiers[tier]:
            tiers[tier].append(label)
    for tier in RISK_TIERS:
        tiers[tier] = sorted(tiers[tier])
    return tiers


def parse_adverse_effects(value: Any, limit: int = 8) -> list[str]:
    """Split a free-text ``adverse_effects`` field into normalised terms."""
    if not value:
        return []
    seen: list[str] = []
    for chunk in _AE_SPLIT.split(str(value)):
        term = re.sub(r"\s+", " ", chunk).strip(" .").lower()
        if len(term) < 3 or len(term) > 60:
            continue
        if term not in seen:
            seen.append(term)
        if len(seen) >= limit:
            break
    return seen


def _overlap(terms: Iterable[str], symptoms: Sequence[str]) -> list[str]:
    """Match AE terms against the module's own symptom list, loosely.

    Both sides are short clinical phrases, so the match is substring-based
    rather than exact. Anything matched this way is reported as inferred.
    """
    symptoms_cf = [s.strip().lower() for s in symptoms if str(s).strip()]
    hits: list[str] = []
    for term in terms:
        t = str(term).strip().lower()
        for symptom in symptoms_cf:
            if t and (t in symptom or symptom in t) and symptom not in hits:
                hits.append(symptom)
    return hits


def _bounded(value: float) -> int | float:
    return max(0, min(10, round(value, 1)))


def _tier_burden(risk: Mapping[str, Sequence[str]]) -> tuple[int | float, int | float]:
    """Return ``(disease_specific_risk, severity_burden)`` from tier occupancy.

    Both are 0-10 heuristics: the share of the catalog in the elevated tiers
    drives ``disease_specific_risk``, and how concentrated that share is in
    ``high_risk`` drives ``severity_burden``. Undetermined drugs do not count as
    dangerous, but they stop the score from reading as reassuring.
    """
    counts = {tier: len(risk.get(tier) or []) for tier in RISK_TIERS}
    total = sum(counts.values())
    if total == 0:
        return 0, 0
    elevated = counts["high_risk"] + counts["moderate_risk"]
    undetermined = counts["undetermined_risk"]
    disease_specific_risk = 10.0 * elevated / total
    disease_specific_risk += 2.0 * undetermined / total
    severity_burden = 0.0
    if elevated:
        severity_burden = 10.0 * counts["high_risk"] / total
    return _bounded(disease_specific_risk), _bounded(severity_burden)


def _drug_ae(drug: Mapping[str, Any]) -> tuple[list[str], list[str], str]:
    """Return ``(common_ae, severe_ae, basis)`` for one merged drug record.

    The catalog's own ``adverse_effects`` text wins when present. Otherwise the
    pharmacologic class supplies a coarse class-level summary. When neither is
    available the lists stay empty and ``basis`` says so - an empty list must not
    be read as "no adverse events".
    """
    text = str(drug.get("adverse_effects") or "").strip()
    if text:
        return parse_adverse_effects(text), [], "drug_adverse_effect_text"
    rule = match_drug_class(_drug_text(drug))
    if rule is not None:
        return list(rule.common_ae), list(rule.severe_ae), f"class:{rule.name}"
    return [], [], "unresolved"


def derive_adverse_events_payload(
    disease_id: str,
    drugs_payload: Mapping[str, Any],
    risk: Mapping[str, Sequence[str]] | None = None,
    *,
    symptoms: Sequence[str] = (),
) -> dict[str, Any]:
    """Build an ``adverse_events.json`` payload with explicit inferred provenance.

    The shape matches the contract enforced by
    :func:`med_research.pipeline.adverse_events.profiler._load_disease_profile_payload`:
    a non-empty ``source``, a non-empty ``limitations`` list, and a
    ``default_profile`` carrying the eight required keys. Every per-drug
    ``drug_id`` comes from the module's own catalog, so it is guaranteed to
    resolve.
    """
    drugs = _unique_drugs(drugs_payload)
    risk = risk or derive_drug_safety_risk(drugs_payload)

    default_common: list[str] = []
    default_severe: list[str] = []
    profiles: list[dict[str, Any]] = []
    unresolved = 0

    for drug in drugs:
        common, severe, basis = _drug_ae(drug)
        if basis == "unresolved":
            unresolved += 1
        for term in common:
            if term not in default_common:
                default_common.append(term)
        for term in severe:
            if term not in default_severe:
                default_severe.append(term)
        if not common and not severe:
            continue
        profiles.append(
            {
                "drug_id": str(drug["id"]),
                "common_ae": common,
                "severe_ae": severe,
                "disease_overlap_ae": _overlap(common + severe, symptoms),
                "evidence_grade": (AE_EVIDENCE_GRADE if basis.startswith("class:") else basis),
            }
        )

    disease_specific_risk, severity_burden = _tier_burden(risk)
    undetermined_count = len(risk.get("undetermined_risk") or [])

    limitations = list(STANDARD_LIMITATIONS)
    if unresolved:
        limitations.append(
            f"{unresolved} drug(s) have no recognisable pharmacologic class and no "
            "adverse-effect text: their empty adverse-event lists mean 'not known', "
            "not 'none'."
        )
    if undetermined_count:
        limitations.append(
            f"{undetermined_count} drug(s) are classified undetermined_risk: their "
            "absence from a risk tier is a gap in inference, not evidence of safety."
        )
    if not symptoms:
        limitations.append("No curated symptom list was available, so disease_overlap_ae is empty.")

    return {
        "schema_version": AE_SCHEMA_VERSION,
        "disease_id": disease_id,
        "source": AE_SOURCE,
        "coverage_level": "partial",
        "curated_inputs": ["disease_drug_catalog"],
        "inferred_inputs": [
            "drug_class_adverse_event_patterns",
            "drug_class_tier_mapping",
            "drug_symptom_overlap",
        ],
        "limitations": limitations,
        "default_profile": {
            "common_ae": sorted(default_common)[:12],
            "severe_ae": sorted(default_severe),
            "disease_overlap_ae": _overlap(default_common + default_severe, symptoms),
            "black_box_warnings": [],
            "severity_burden": severity_burden,
            "chronic_use_safety": _bounded(10.0 - severity_burden),
            "disease_specific_risk": disease_specific_risk,
            "monitoring_required": (
                "Class-level inference only: verify current labels and "
                "disease-specific contraindications before use."
            ),
            "evidence_grade": AE_EVIDENCE_GRADE,
        },
        "drug_safety_tiers": {tier: list(risk.get(tier) or []) for tier in RISK_TIERS},
        "profiles": profiles,
    }


def write_risk_config_section(disease_id: str, *, dry_run: bool = False) -> Path | None:
    """Rewrite only the ``DRUG_SAFETY_RISK`` block in a module's ``config.py``.

    Scope is deliberately limited to the risk block: the shared config writer can
    also emit CAR-T and screening sections, and backfilling safety must not
    clobber a hand-curated CAR-T or screening table. Returns ``None`` for SLE,
    whose config is manually curated.

    The writer itself lives in ``scripts/populate_disease_configs.py`` and is
    loaded the same way :func:`med_research.diseases.scaffold` loads it, so there
    is exactly one implementation of the block-replacement logic.
    """
    import importlib.util

    if disease_id == "sle":
        return None

    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "populate_disease_configs.py"
    spec = importlib.util.spec_from_file_location("populate_disease_configs", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load config writer at {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.write_config_sections(disease_id, dry_run=dry_run, sections=("risk",))
    return Path(result) if result is not None else None


def _diseases_root() -> Path:
    import med_research.diseases as diseases_pkg

    return Path(diseases_pkg.__file__).parent


def load_symptoms(disease_id: str) -> list[str]:
    """Read a module's curated ``SYMPTOMS`` list without importing its config."""
    from med_research.diseases.symptom_harvester import _read_config_symptoms

    return _read_config_symptoms(_diseases_root() / disease_id / "config.py")


def write_adverse_events_file(
    disease_id: str,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> Path | None:
    """Write ``data/adverse_events.json`` for one module.

    Returns the path written, or ``None`` when there was nothing to write (no
    drugs to describe) or the file already exists and ``overwrite`` is false.
    """
    data_dir = _diseases_root() / disease_id / "data"
    drugs_path = data_dir / "drugs.json"
    if not drugs_path.is_file():
        return None

    out_path = data_dir / "adverse_events.json"
    if out_path.is_file() and not overwrite:
        return None

    try:
        drugs_payload = json.loads(drugs_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (drugs_payload.get("drugs") or []):
        return None

    payload = derive_adverse_events_payload(
        disease_id,
        drugs_payload,
        symptoms=load_symptoms(disease_id),
    )
    if dry_run:
        return out_path
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path
