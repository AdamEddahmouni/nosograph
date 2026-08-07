"""
Adverse Event Profiling Engine

Scores drugs based on disease-specific adverse-event profiles.
Evaluates safety across 4 dimensions:
  1. Disease Symptom Overlap (inverted): Do adverse events mimic disease symptoms?
  2. Severity Burden (inverted): How severe are the most common adverse events?
  3. Chronic Use Safety: Is the drug safe for long-term use?
  4. Disease-Specific Risk: Does the active disease risk profile indicate concern?

Usage:
    python adverse_events/profiler.py              # Full analysis
    python adverse_events/profiler.py --drug belimumab  # Single drug
    python adverse_events/profiler.py --export-html  # Generate report
"""

import argparse
import functools
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"
PROFILES_PATH = DATA_DIR / "profiles.json"
DISEASE_PROFILE_FILENAME = "adverse_events.json"

# ── Legacy SLE symptom vocabulary retained for compatibility ───────────

LUPUS_SYMPTOMS = [
    "fatigue",
    "arthralgia",
    "arthritis",
    "joint pain",
    "rash",
    "photosensitivity",
    "malar rash",
    "discoid rash",
    "renal impairment",
    "nephritis",
    "proteinuria",
    "anemia",
    "leukopenia",
    "thrombocytopenia",
    "neuropsychiatric",
    "seizure",
    "psychosis",
    "cognitive dysfunction",
    "serositis",
    "pleuritis",
    "pericarditis",
    "fever",
    "oral ulcers",
    "mucosal ulcers",
    "alopecia",
    "raynaud",
]


def _load_disease_profile_payload(disease_id: str) -> dict:
    """Load and validate the explicit profile contract owned by one disease."""
    from med_research.diseases.base import Disease

    disease = Disease(disease_id)
    payload = disease.get_adverse_event_profile()
    if not isinstance(payload, dict):
        raise ValueError(f"Safety profile for '{disease_id}' must be a JSON object")
    profiles = payload.get("profiles", [])
    if not isinstance(profiles, list):
        raise ValueError(f"Safety profiles for '{disease_id}' must be a list")
    if not payload.get("source"):
        raise ValueError(f"Safety profile for '{disease_id}' has no source")
    if not payload.get("limitations"):
        raise ValueError(f"Safety profile for '{disease_id}' has no limitations")
    if disease_id != "sle":
        defaults = payload.get("default_profile")
        required_defaults = {
            "common_ae", "severe_ae", "disease_overlap_ae",
            "severity_burden", "chronic_use_safety", "disease_specific_risk",
            "monitoring_required", "evidence_grade",
        }
        if not isinstance(defaults, dict) or not required_defaults <= set(defaults):
            missing = sorted(required_defaults - set(defaults or {}))
            raise ValueError(
                f"Safety profile for '{disease_id}' has incomplete default_profile: {', '.join(missing)}"
            )

    catalog_ids = {
        str(drug.get("id"))
        for drug in disease.load_drugs().get("drugs", [])
        if drug.get("id")
    }
    profile_ids = []
    for profile in profiles:
        if not isinstance(profile, dict) or not profile.get("drug_id"):
            raise ValueError(f"Safety profile for '{disease_id}' contains an invalid drug entry")
        profile_ids.append(str(profile["drug_id"]))
    unknown = sorted(set(profile_ids) - catalog_ids)
    if unknown:
        raise ValueError(
            f"Safety profile for '{disease_id}' references unknown drugs: {', '.join(unknown)}"
        )
    return payload


def _validate_profile_values(profile: dict, disease_id: str) -> None:
    """Validate bounded safety fields before any scoring occurs."""
    for field in ("severity_burden", "chronic_use_safety", "disease_specific_risk"):
        value = profile.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 10:
            raise ValueError(
                f"Safety profile for '{disease_id}' has invalid {field}: {value!r}"
            )
    for field in ("common_ae", "severe_ae", "disease_overlap_ae", "black_box_warnings"):
        if not isinstance(profile.get(field, []), list):
            raise ValueError(
                f"Safety profile for '{disease_id}' has invalid {field}; expected a list"
            )
    if not isinstance(profile.get("monitoring_required", ""), str):
        raise ValueError(
            f"Safety profile for '{disease_id}' has invalid monitoring_required"
        )


def _merge_profile(
    defaults: dict,
    explicit: dict,
    drug: dict,
    disease_id: str,
    payload: dict | None = None,
) -> dict:
    """Materialize one disease drug profile without cross-disease fallback."""
    drug_id = str(drug.get("id", drug.get("drug_id", "")))
    drug_name = drug.get("name", drug.get("drug_name", drug_id))
    profile = {**defaults, **explicit}
    profile["drug_id"] = drug_id
    profile["drug_name"] = drug_name
    profile["disease_id"] = disease_id
    profile["profile_source"] = (payload or {}).get(
        "profile_source", (payload or {}).get("source", "disease_adverse_events.json")
    )
    profile["profile_curated_inputs"] = list((payload or {}).get("curated_inputs", []))
    profile["profile_inferred_inputs"] = list((payload or {}).get("inferred_inputs", []))
    profile["limitations"] = list(
        dict.fromkeys([*(payload or {}).get("limitations", []), *profile.get("limitations", [])])
    )
    # Normalize legacy SLE source fields once at the compatibility boundary.
    profile["disease_overlap_ae"] = profile.get(
        "disease_overlap_ae", profile.get("lupus_overlap_ae", [])
    )
    profile["disease_specific_risk"] = profile.get(
        "disease_specific_risk", profile.get("dil_risk", 0)
    )
    # Keep old consumers working while disease-neutral fields are authoritative.
    profile["lupus_overlap_ae"] = profile["disease_overlap_ae"]
    profile["dil_risk"] = profile["disease_specific_risk"]
    profile.setdefault("evidence_grade", "inferred_class_default")
    return profile


def load_profiles(disease_id: str = "sle") -> dict:
    """Load profiles for the selected disease's drug catalog.

    SLE keeps its legacy 26-drug profile set for compatibility. Every
    non-SLE profile is materialized only from that disease's own explicit JSON
    contract and its own drug catalog; no SLE profile is reused.
    """
    payload = _load_disease_profile_payload(disease_id)
    explicit = {
        str(profile.get("drug_id")): profile
        for profile in payload.get("profiles", [])
        if isinstance(profile, dict) and profile.get("drug_id")
    }

    if disease_id == "sle" and not explicit:
        legacy = _get_default_profiles()
        profiles = {
            drug_id: _merge_profile({}, profile, profile, disease_id, payload)
            for drug_id, profile in legacy.items()
        }
        for profile in profiles.values():
            _validate_profile_values(profile, disease_id)
        return profiles

    from med_research.diseases.base import Disease

    drugs = Disease(disease_id).load_drugs().get("drugs", [])
    defaults = payload.get("default_profile", {})
    profiles = {}
    for drug in drugs:
        drug_id = str(drug.get("id", ""))
        if not drug_id:
            continue
        profiles[drug_id] = _merge_profile(
            defaults,
            explicit.get(drug_id, {}),
            drug,
            disease_id,
            payload,
        )
        _validate_profile_values(profiles[drug_id], disease_id)
    return profiles


def _get_default_profiles() -> dict:
    """Return curated default profiles for all 26 KG drugs."""
    profiles = {
        "belimumab": {
            "drug_id": "belimumab",
            "drug_name": "Belimumab (Benlysta)",
            "common_ae": [
                "nausea", "diarrhea", "pyrexia", "nasopharyngitis",
                "bronchitis", "insomnia", "depression", "migraine",
                "infusion reactions", "hypersensitivity",
            ],
            "severe_ae": [
                "serious infections", "progressive multifocal leukoencephalopathy (rare)",
                "hypersensitivity reactions", "infusion reactions",
            ],
            "lupus_overlap_ae": ["depression", "pyrexia"],
            "severity_burden": 3,
            "chronic_use_safety": 8,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "Infection monitoring; no routine lab monitoring required",
        },
        "anifrolumab": {
            "drug_id": "anifrolumab",
            "drug_name": "Anifrolumab (Saphnelo)",
            "common_ae": [
                "nasopharyngitis", "upper respiratory tract infection",
                "bronchitis", "infusion reactions", "herpes zoster",
                "cough",
            ],
            "severe_ae": [
                "serious infections", "herpes zoster (disseminated)",
                "hypersensitivity reactions",
            ],
            "lupus_overlap_ae": ["cough"],
            "severity_burden": 3,
            "chronic_use_safety": 8,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "Infection monitoring; herpes zoster risk counseling",
        },
        "voclosporin": {
            "drug_id": "voclosporin",
            "drug_name": "Voclosporin (Lupkynis)",
            "common_ae": [
                "glomerular filtration rate decreased", "hypertension",
                "diarrhea", "headache", "anemia", "cough",
                "urinary tract infection", "upper abdominal pain",
            ],
            "severe_ae": [
                "nephrotoxicity", "hypertension", "neurotoxicity",
                "serious infections", "lymphoma (rare)", "skin cancer (rare)",
            ],
            "lupus_overlap_ae": ["anemia", "headache"],
            "severity_burden": 5,
            "chronic_use_safety": 5,
            "dil_risk": 0,
            "black_box_warnings": [
                "Increased risk of serious infections",
                "Increased risk of malignancy (lymphoma, skin cancer)",
            ],
            "monitoring_required": "Renal function (eGFR), blood pressure, drug levels, CBC",
        },
        "hydroxychloroquine": {
            "drug_id": "hydroxychloroquine",
            "drug_name": "Hydroxychloroquine (Plaquenil)",
            "common_ae": [
                "nausea", "abdominal pain", "diarrhea", "headache",
                "rash", "pruritus",
            ],
            "severe_ae": [
                "retinopathy (with long-term use)", "cardiomyopathy (rare)",
                "severe hypoglycemia", "neuropsychiatric effects (rare)",
            ],
            "lupus_overlap_ae": ["rash"],
            "severity_burden": 2,
            "chronic_use_safety": 9,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "Annual retinal screening after 5 years; baseline ophthalmologic exam",
        },
        "mycophenolate": {
            "drug_id": "mycophenolate",
            "drug_name": "Mycophenolate Mofetil (CellCept)",
            "common_ae": [
                "diarrhea", "nausea", "vomiting", "abdominal pain",
                "leukopenia", "anemia", "thrombocytopenia",
            ],
            "severe_ae": [
                "serious infections", "lymphoma (rare)", "skin cancer (rare)",
                "progressive multifocal leukoencephalopathy (rare)",
                "pure red cell aplasia (rare)", "gastrointestinal bleeding",
            ],
            "lupus_overlap_ae": ["leukopenia", "anemia", "thrombocytopenia"],
            "severity_burden": 5,
            "chronic_use_safety": 6,
            "dil_risk": 0,
            "black_box_warnings": [
                "Increased risk of congenital malformations (pregnancy Category D)",
                "Increased risk of serious infections",
                "Increased risk of lymphoma",
            ],
            "monitoring_required": "CBC, pregnancy testing, infection monitoring",
        },
        "cyclophosphamide": {
            "drug_id": "cyclophosphamide",
            "drug_name": "Cyclophosphamide (Cytoxan)",
            "common_ae": [
                "nausea", "vomiting", "alopecia", "bone marrow suppression",
                "leukopenia", "hemorrhagic cystitis", "infertility",
            ],
            "severe_ae": [
                "bone marrow failure", "hemorrhagic cystitis", "bladder cancer",
                "secondary malignancies (leukemia, lymphoma)",
                "severe infections", "cardiotoxicity (high dose)",
                "pulmonary fibrosis", "infertility (permanent)",
            ],
            "lupus_overlap_ae": ["alopecia", "leukopenia"],
            "severity_burden": 9,
            "chronic_use_safety": 1,
            "dil_risk": 1,
            "black_box_warnings": [
                "Myelosuppression", "Hemorrhagic cystitis",
                "Secondary malignancies", "Fetal harm",
            ],
            "monitoring_required": "CBC, urinalysis, renal/hepatic function, fertility counseling",
        },
        "rituximab": {
            "drug_id": "rituximab",
            "drug_name": "Rituximab (Rituxan)",
            "common_ae": [
                "infusion reactions", "pyrexia", "chills", "asthenia",
                "nausea", "headache", "pruritus", "rash",
            ],
            "severe_ae": [
                "serious infusion reactions", "hepatitis B reactivation",
                "progressive multifocal leukoencephalopathy (rare)",
                "serious infections", "cardiac arrhythmias",
                "tumor lysis syndrome",
            ],
            "lupus_overlap_ae": ["pyrexia", "rash", "headache"],
            "severity_burden": 5,
            "chronic_use_safety": 6,
            "dil_risk": 1,
            "black_box_warnings": [
                "Fatal infusion reactions",
                "Severe mucocutaneous reactions",
                "Hepatitis B reactivation",
                "Progressive multifocal leukoencephalopathy",
            ],
            "monitoring_required": "Hepatitis B/C screening, CBC, cardiac monitoring during infusion",
        },
        "prednisone": {
            "drug_id": "prednisone",
            "drug_name": "Prednisone (Corticosteroids)",
            "common_ae": [
                "weight gain", "insomnia", "mood changes", "hyperglycemia",
                "hypertension", "osteoporosis", "cataracts", "glaucoma",
                "skin thinning", "increased appetite", "fluid retention",
                "avascular necrosis",
            ],
            "severe_ae": [
                "avascular necrosis of femoral head", "osteoporosis with fracture",
                "adrenal suppression", "severe infections",
                "Cushing syndrome", "peptic ulcer", "pancreatitis",
                "psychosis (rare)",
            ],
            "lupus_overlap_ae": ["mood changes", "psychosis"],
            "severity_burden": 7,
            "chronic_use_safety": 2,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "Blood pressure, glucose, bone density, ophthalmologic exam",
        },
        "tacrolimus": {
            "drug_id": "tacrolimus",
            "drug_name": "Tacrolimus (Prograf)",
            "common_ae": [
                "tremor", "headache", "hypertension", "nausea",
                "diarrhea", "renal dysfunction", "hyperglycemia",
                "hypomagnesemia", "hyperkalemia",
            ],
            "severe_ae": [
                "nephrotoxicity", "neurotoxicity", "hypertension",
                "hyperglycemia/diabetes", "serious infections",
                "lymphoma (rare)", "skin cancer (rare)",
            ],
            "lupus_overlap_ae": ["headache", "renal dysfunction"],
            "severity_burden": 5,
            "chronic_use_safety": 5,
            "dil_risk": 0,
            "black_box_warnings": [
                "Increased risk of malignancy (lymphoma, skin cancer)",
                "Increased risk of serious infections",
            ],
            "monitoring_required": "Renal function, drug levels, blood pressure, glucose, CBC",
        },
        "azathioprine": {
            "drug_id": "azathioprine",
            "drug_name": "Azathioprine (Imuran)",
            "common_ae": [
                "leukopenia", "nausea", "vomiting", "hepatotoxicity",
                "pancreatitis (rare)", "infection risk",
            ],
            "severe_ae": [
                "bone marrow suppression", "hepatotoxicity",
                "pancreatitis", "severe infections",
                "lymphoma (rare)", "skin cancer (rare)",
            ],
            "lupus_overlap_ae": ["leukopenia"],
            "severity_burden": 5,
            "chronic_use_safety": 5,
            "dil_risk": 1,
            "black_box_warnings": [
                "Increased risk of malignancy",
                "TPMT deficiency can cause severe myelotoxicity",
            ],
            "monitoring_required": "TPMT testing pre-initiation, CBC, LFTs, pregnancy testing",
        },
        "baricitinib": {
            "drug_id": "baricitinib",
            "drug_name": "Baricitinib (Olumiant)",
            "common_ae": [
                "upper respiratory tract infection", "nausea",
                "herpes zoster", "herpes simplex", "hyperlipidemia",
                "increased creatine phosphokinase",
            ],
            "severe_ae": [
                "serious infections", "herpes zoster (disseminated)",
                "thrombosis (venous thromboembolism)", "major adverse cardiovascular events",
                "malignancy", "gastrointestinal perforation (rare)",
            ],
            "lupus_overlap_ae": [],
            "severity_burden": 5,
            "chronic_use_safety": 6,
            "dil_risk": 0,
            "black_box_warnings": [
                "Risk of serious infections",
                "Increased mortality in RA patients >50 with CV risk factors",
            ],
            "monitoring_required": "CBC, LFTs, lipids, TB screening, viral hepatitis screening",
        },
        "obinutuzumab": {
            "drug_id": "obinutuzumab",
            "drug_name": "Obinutuzumab (Gazyva)",
            "common_ae": [
                "infusion reactions", "neutropenia", "thrombocytopenia",
                "pyrexia", "cough", "nausea",
            ],
            "severe_ae": [
                "serious infusion reactions", "hepatitis B reactivation",
                "progressive multifocal leukoencephalopathy (rare)",
                "neutropenia (severe)", "thrombocytopenia (severe)",
                "serious infections",
            ],
            "lupus_overlap_ae": ["neutropenia", "thrombocytopenia", "pyrexia"],
            "severity_burden": 6,
            "chronic_use_safety": 6,
            "dil_risk": 0,
            "black_box_warnings": [
                "Hepatitis B reactivation",
                "Progressive multifocal leukoencephalopathy",
            ],
            "monitoring_required": "CBC, hepatitis B/C screening, infection monitoring",
        },
        "acalabrutinib": {
            "drug_id": "acalabrutinib",
            "drug_name": "Acalabrutinib (Calquence)",
            "common_ae": [
                "headache", "diarrhea", "fatigue", "myalgia",
                "bruising", "nausea", "rash",
            ],
            "severe_ae": [
                "hemorrhage", "atrial fibrillation/flutter",
                "serious infections", "second primary malignancies",
                "cytopenias",
            ],
            "lupus_overlap_ae": ["fatigue", "rash", "headache", "myalgia"],
            "severity_burden": 5,
            "chronic_use_safety": 6,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "CBC, cardiac monitoring (atrial fibrillation), bleeding risk assessment",
        },
        "avacopan": {
            "drug_id": "avacopan",
            "drug_name": "Avacopan (Tavneos)",
            "common_ae": [
                "nausea", "headache", "hypertension", "diarrhea",
                "vomiting", "rash", "paresthesia",
            ],
            "severe_ae": [
                "hepatotoxicity", "serious infections",
                "angioedema", "hypersensitivity reactions",
            ],
            "lupus_overlap_ae": ["headache", "rash"],
            "severity_burden": 4,
            "chronic_use_safety": 6,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "LFTs (hepatotoxicity monitoring), infection monitoring",
        },
        "cyclosporine": {
            "drug_id": "cyclosporine",
            "drug_name": "Cyclosporine (Neoral / Sandimmune)",
            "common_ae": [
                "renal dysfunction", "hypertension", "tremor",
                "hirsutism", "gingival hyperplasia", "hyperlipidemia",
                "nausea",
            ],
            "severe_ae": [
                "nephrotoxicity", "hypertension", "neurotoxicity",
                "serious infections", "lymphoma (rare)", "skin cancer (rare)",
                "hepatotoxicity",
            ],
            "lupus_overlap_ae": ["renal dysfunction"],
            "severity_burden": 6,
            "chronic_use_safety": 5,
            "dil_risk": 0,
            "black_box_warnings": [
                "Nephrotoxicity", "Hypertension",
                "Increased risk of malignancy",
                "Increased risk of serious infections",
            ],
            "monitoring_required": "Renal function, blood pressure, drug levels, lipids, CBC",
        },
        "dimethyl_fumarate": {
            "drug_id": "dimethyl_fumarate",
            "drug_name": "Dimethyl Fumarate (Tecfidera)",
            "common_ae": [
                "flushing", "abdominal pain", "diarrhea", "nausea",
                "vomiting", "pruritus", "rash",
            ],
            "severe_ae": [
                "progressive multifocal leukoencephalopathy (rare)",
                "lymphopenia (severe)", "hepatic injury",
                "anaphylaxis",
            ],
            "lupus_overlap_ae": ["rash"],
            "severity_burden": 4,
            "chronic_use_safety": 7,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "CBC (lymphocyte counts), LFTs",
        },
        "iscalimab": {
            "drug_id": "iscalimab",
            "drug_name": "Iscalimab (CFZ533 / anti-CD40)",
            "common_ae": [
                "upper respiratory tract infection", "headache",
                "nasopharyngitis", "nausea",
            ],
            "severe_ae": [
                "serious infections", "thromboembolic events (theoretical)",
                "hypersensitivity reactions",
            ],
            "lupus_overlap_ae": ["headache"],
            "severity_burden": 3,
            "chronic_use_safety": 7,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "Infection monitoring; investigational safety profile evolving",
        },
        "ravulizumab": {
            "drug_id": "ravulizumab",
            "drug_name": "Ravulizumab (Ultomiris)",
            "common_ae": [
                "upper respiratory tract infection", "headache",
                "diarrhea", "nausea", "pyrexia",
            ],
            "severe_ae": [
                "meningococcal infection (life-threatening)",
                "other encapsulated bacterial infections",
                "infusion reactions",
            ],
            "lupus_overlap_ae": ["headache", "pyrexia"],
            "severity_burden": 5,
            "chronic_use_safety": 8,
            "dil_risk": 0,
            "black_box_warnings": [
                "Risk of serious and life-threatening meningococcal infections",
            ],
            "monitoring_required": "Meningococcal vaccination required pre-treatment; infection monitoring",
        },
        "rozanolixizumab": {
            "drug_id": "rozanolixizumab",
            "drug_name": "Rozanolixizumab (Rystiggo)",
            "common_ae": [
                "headache", "infections", "diarrhea", "pyrexia",
                "injection site reactions",
            ],
            "severe_ae": [
                "serious infections", "hypersensitivity reactions",
                "immunogenicity",
            ],
            "lupus_overlap_ae": ["headache", "pyrexia"],
            "severity_burden": 3,
            "chronic_use_safety": 7,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "Infection monitoring; IgG levels",
        },
        "tofacitinib": {
            "drug_id": "tofacitinib",
            "drug_name": "Tofacitinib (Xeljanz)",
            "common_ae": [
                "upper respiratory tract infection", "headache",
                "diarrhea", "nasopharyngitis", "hypertension",
                "hyperlipidemia", "herpes zoster",
            ],
            "severe_ae": [
                "serious infections", "herpes zoster (disseminated)",
                "thrombosis (venous thromboembolism)", "major adverse cardiovascular events",
                "malignancy", "gastrointestinal perforation (rare)",
                "hepatic injury",
            ],
            "lupus_overlap_ae": ["headache"],
            "severity_burden": 6,
            "chronic_use_safety": 5,
            "dil_risk": 0,
            "black_box_warnings": [
                "Risk of serious infections",
                "Increased risk of mortality, thrombosis, and malignancy (RA patients)",
            ],
            "monitoring_required": "CBC, LFTs, lipids, TB screening, viral hepatitis screening",
        },
        "deucravacitinib": {
            "drug_id": "deucravacitinib",
            "drug_name": "Deucravacitinib (Sotyktu)",
            "common_ae": [
                "upper respiratory tract infection", "nasopharyngitis",
                "headache", "diarrhea", "nausea",
                "herpes simplex",
            ],
            "severe_ae": [
                "serious infections", "malignancy (potential)",
                "herpes simplex (disseminated, rare)",
                "increased creatine phosphokinase",
            ],
            "lupus_overlap_ae": ["headache"],
            "severity_burden": 3,
            "chronic_use_safety": 7,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "Infection monitoring, TB screening, viral hepatitis screening",
        },
        "dapirolizumab_pegol": {
            "drug_id": "dapirolizumab_pegol",
            "drug_name": "Dapirolizumab Pegol (Anti-CD40L Fab-PEG)",
            "common_ae": [
                "injection site reactions", "upper respiratory tract infection",
                "headache", "nausea",
            ],
            "severe_ae": [
                "serious infections", "thromboembolic events (theoretical risk mitigated by PEGylated Fab design)",
                "hypersensitivity reactions",
            ],
            "lupus_overlap_ae": ["headache"],
            "severity_burden": 3,
            "chronic_use_safety": 7,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "Infection monitoring; investigational safety profile evolving",
        },
        "litifilimab": {
            "drug_id": "litifilimab",
            "drug_name": "Litifilimab (Anti-BDCA2 / BIIB059)",
            "common_ae": [
                "injection site reactions", "upper respiratory tract infection",
                "headache", "nasopharyngitis",
            ],
            "severe_ae": [
                "serious infections", "hypersensitivity reactions",
            ],
            "lupus_overlap_ae": ["headache"],
            "severity_burden": 2,
            "chronic_use_safety": 7,
            "dil_risk": 0,
            "black_box_warnings": [],
            "monitoring_required": "Infection monitoring; investigational safety profile evolving",
        },
        "iberdomide": {
            "drug_id": "iberdomide",
            "drug_name": "Iberdomide (CC-220 / Cereblon Modulator)",
            "common_ae": [
                "neutropenia", "thrombocytopenia", "anemia",
                "infections", "fatigue", "diarrhea", "nausea",
            ],
            "severe_ae": [
                "neutropenia (severe)", "thrombocytopenia (severe)",
                "serious infections", "thromboembolic events",
                "second primary malignancies (potential, class effect)",
            ],
            "lupus_overlap_ae": ["neutropenia", "thrombocytopenia", "anemia", "fatigue"],
            "severity_burden": 6,
            "chronic_use_safety": 5,
            "dil_risk": 0,
            "black_box_warnings": [
                "Fetal harm (contraindicated in pregnancy)",
                "Venous/arterial thromboembolism risk",
            ],
            "monitoring_required": "CBC, pregnancy testing, thrombosis risk assessment",
        },
        "teclistamab": {
            "drug_id": "teclistamab",
            "drug_name": "Teclistamab (Tecvayli / BCMAxCD3 Bispecific)",
            "common_ae": [
                "cytokine release syndrome", "neutropenia", "anemia",
                "thrombocytopenia", "infections", "fatigue",
                "injection site reactions", "pyrexia",
            ],
            "severe_ae": [
                "cytokine release syndrome (Grade 3-4)", "immune effector cell-associated neurotoxicity syndrome (ICANS)",
                "severe infections", "cytopenias (prolonged)",
                "hypogammaglobulinemia",
            ],
            "lupus_overlap_ae": ["neutropenia", "anemia", "thrombocytopenia", "fatigue", "pyrexia"],
            "severity_burden": 8,
            "chronic_use_safety": 3,
            "dil_risk": 0,
            "black_box_warnings": [
                "Cytokine release syndrome",
                "Neurologic toxicity including ICANS",
            ],
            "monitoring_required": "Hospitalization for initial doses; CBC; infection monitoring; immunoglobulin levels",
        },
        "anti_cd19_cart": {
            "drug_id": "anti_cd19_cart",
            "drug_name": "Anti-CD19 CAR-T Cell Therapy",
            "common_ae": [
                "cytokine release syndrome", "neurotoxicity",
                "B cell aplasia", "hypogammaglobulinemia",
                "infections", "pyrexia", "fatigue",
                "cytopenias",
            ],
            "severe_ae": [
                "cytokine release syndrome (Grade 3-4)", "immune effector cell-associated neurotoxicity syndrome (ICANS)",
                "prolonged B cell aplasia (requiring immunoglobulin replacement)",
                "serious infections", "secondary malignancies",
                "cytopenias (prolonged)", "hemophagocytic lymphohistiocytosis (rare)",
            ],
            "lupus_overlap_ae": ["neurotoxicity", "fatigue", "pyrexia"],
            "severity_burden": 9,
            "chronic_use_safety": 2,
            "dil_risk": 0,
            "black_box_warnings": [
                "Cytokine release syndrome",
                "Neurologic toxicities",
                "Secondary malignancies",
            ],
            "monitoring_required": "Hospitalization required; CBC; infection monitoring; immunoglobulin replacement",
        },
    }
    return profiles


def count_disease_symptom_overlap(profile: dict, disease_id: str = "sle") -> int:
    """Count adverse events overlapping the active disease's symptoms."""
    from med_research.diseases.base import Disease

    symptoms = Disease(disease_id).get_symptom_overlap_terms()
    overlap_terms = profile.get(
        "disease_overlap_ae",
        profile.get("lupus_overlap_ae", []) if disease_id == "sle" else profile.get("common_ae", []),
    )
    overlap = 0
    for ae in overlap_terms:
        for symptom in symptoms:
            if symptom.lower() in ae.lower():
                overlap += 1
                break
    return overlap


def score_disease_overlap(profile: dict, disease_id: str = "sle") -> float:
    """Score active-disease symptom overlap (0-10; higher is safer)."""
    n_overlap = count_disease_symptom_overlap(profile, disease_id)
    if n_overlap == 0:
        return 10.0
    if n_overlap <= 2:
        return 8.0
    if n_overlap <= 3:
        return 6.0
    if n_overlap <= 5:
        return 4.0
    return 2.0


def count_lupus_symptom_overlap(profile: dict, disease_id: str = "sle") -> int:
    """Backward-compatible alias for :func:`count_disease_symptom_overlap`."""
    return count_disease_symptom_overlap(profile, disease_id)


def score_lupus_overlap(profile: dict, disease_id: str = "sle") -> float:
    """Backward-compatible alias for :func:`score_disease_overlap`."""
    return score_disease_overlap(profile, disease_id)


def score_severity_burden(profile: dict) -> float:
    """Convert severity burden (1-10 raw) to 0-10 score (higher = safer)."""
    raw = profile.get("severity_burden", 5)
    return 10.0 - raw


def score_chronic_safety(profile: dict) -> float:
    """Score chronic use safety from the raw 1-10 rating."""
    return float(profile.get("chronic_use_safety", 5))


@functools.lru_cache(maxsize=16)
def _load_disease_specific_risk(disease_id: str = "sle") -> dict:
    """Load the disease's configured risk categories.

    Returns a dict with "high_risk", "moderate_risk", "low_risk" drug
    lists, defaulting to empty lists when no config exists.
    """
    try:
        from med_research.diseases.base import Disease
        risk = Disease(disease_id).get_disease_risk_config()
    except Exception:
        risk = {}
    if not isinstance(risk, dict):
        risk = {}
    return {
        "high_risk": risk.get("high_risk", []) or [],
        "moderate_risk": risk.get("moderate_risk", []) or [],
        "low_risk": risk.get("low_risk", []) or [],
    }


def _config_disease_specific_risk(profile: dict, disease_id: str = "sle") -> float | None:
    """Return a disease-specific risk score from the disease config.

    Drugs listed in the config's high/moderate risk lists are scored
    (higher returned value = lower risk), matching the neutral risk scale.
    Returns None when the drug is not in the config lists, so the
    profile-based score is used as fallback.
    """
    risk = _load_disease_specific_risk(disease_id)
    drug_id = str(profile.get("drug_id", "")).lower()
    drug_name = str(profile.get("drug_name", "")).lower()

    def hit(items):
        for item in items:
            item = str(item).lower()
            if drug_id and (drug_id == item or drug_id in item or item in drug_id):
                return True
            if drug_name and (item in drug_name or drug_name in item):
                return True
        return False

    if hit(risk["high_risk"]):
        return 2.0
    if hit(risk["moderate_risk"]):
        return 5.0
    if hit(risk["low_risk"]):
        return 7.5
    return None


def score_disease_specific_risk(profile: dict, disease_id: str = "sle") -> float:
    """Score configured disease-specific risk (0-10; higher is safer)."""
    configured = _config_disease_specific_risk(profile, disease_id)
    if configured is not None:
        return configured
    raw = profile.get("disease_specific_risk", profile.get("dil_risk", 0))
    if raw == 0:
        return 10.0
    if raw == 1:
        return 5.0
    return 2.0


def score_dil_risk(profile: dict, disease_id: str = "sle") -> float:
    """Backward-compatible alias for disease-specific risk scoring."""
    return score_disease_specific_risk(profile, disease_id)


def compute_adverse_event_score(profile: dict, disease_id: str = "sle") -> dict:
    """Compute the adverse event safety score for a single drug.

    Returns dict with individual dimension scores and composite score.
    """
    disease_overlap = score_disease_overlap(profile, disease_id)
    severity = score_severity_burden(profile)
    chronic = score_chronic_safety(profile)
    disease_risk = score_disease_specific_risk(profile, disease_id)

    weights = {
        "disease_symptom_overlap": 0.35,
        "severity_burden": 0.30,
        "chronic_use_safety": 0.25,
        "disease_specific_risk": 0.10,
    }

    composite = (
        disease_overlap * weights["disease_symptom_overlap"]
        + severity * weights["severity_burden"]
        + chronic * weights["chronic_use_safety"]
        + disease_risk * weights["disease_specific_risk"]
    )

    return {
        "drug_id": profile["drug_id"],
        "drug_name": profile["drug_name"],
        "disease_id": disease_id,
        "disease_symptom_overlap_score": round(disease_overlap, 1),
        "disease_overlap_score": round(disease_overlap, 1),
        "lupus_symptom_overlap_score": round(disease_overlap, 1),
        "severity_burden_score": round(severity, 1),
        "chronic_use_safety_score": round(chronic, 1),
        "disease_specific_risk_score": round(disease_risk, 1),
        "dil_risk_score": round(disease_risk, 1),
        "composite_safety_score": round(composite, 2),
        "n_disease_overlap_ae": count_disease_symptom_overlap(profile, disease_id),
        "disease_overlap_ae": profile.get("disease_overlap_ae", profile.get("lupus_overlap_ae", [])),
        "n_lupus_overlap_ae": count_disease_symptom_overlap(profile, disease_id),
        "lupus_overlap_ae": profile.get("disease_overlap_ae", profile.get("lupus_overlap_ae", [])),
        "evidence_grade": profile.get("evidence_grade", "inferred_class_default"),
        "profile_source": profile.get("profile_source", "disease_adverse_events.json"),
        "profile_curated_inputs": profile.get("profile_curated_inputs", []),
        "profile_inferred_inputs": profile.get("profile_inferred_inputs", []),
        "limitations": profile.get("limitations", []),
        "black_box_warnings": profile.get("black_box_warnings", []),
        "monitoring_required": profile.get("monitoring_required", ""),
        "n_severe_ae": len(profile.get("severe_ae", [])),
    }


def score_all_drugs(progress_callback=None, disease_id: str = "sle") -> list:
    """Score all drugs and return sorted list by composite safety score.

    Args:
        progress_callback: Optional callable(percent, message) for progress.
        disease_id: Disease whose configured risk categories adjust
            disease-specific risk scoring.

    Returns:
        List of safety scores sorted by composite_safety_score descending.
    """
    from med_research.diseases.coverage import module_coverage

    coverage = module_coverage(
        disease_id,
        "safety",
        ("symptoms", "adverse_event_profile", "safety_risk"),
    )
    if not coverage.is_runnable:
        cb = progress_callback or (lambda p, m: None)
        cb(100, "Safety analysis blocked by incomplete disease coverage")
        return []

    cb = progress_callback or (lambda p, m: None)
    profiles = load_profiles(disease_id)

    cb(10, f"Profiling {len(profiles)} drugs for adverse events...")

    results = []
    for _drug_id, profile in profiles.items():
        results.append(compute_adverse_event_score(profile, disease_id))

    results.sort(key=lambda x: x["composite_safety_score"], reverse=True)

    cb(50, "Saving profiles...")
    # Preserve the legacy SLE cache contract, but never overwrite it with
    # another disease's profiles or scores.
    profile_list = list(profiles.values())
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if disease_id == "sle":
        PROFILES_PATH.write_text(
            json.dumps({"profiles": profile_list}, indent=2),
            encoding="utf-8",
        )

    # Keep disease-specific score caches isolated from the legacy SLE cache.
    scores_path = DATA_DIR / ("safety_scores.json" if disease_id == "sle" else f"safety_scores_{disease_id}.json")
    scores_path.write_text(
        json.dumps({"safety_scores": results}, indent=2),
        encoding="utf-8",
    )

    cb(100, f"Safety profiling complete: {len(results)} drugs scored")

    return results


def get_drug_profile(drug_id: str, disease_id: str = "sle") -> dict:
    """Get the adverse-event profile and active-disease score for one drug."""
    from med_research.diseases.coverage import module_coverage
    coverage = module_coverage(
        disease_id,
        "safety",
        ("symptoms", "adverse_event_profile", "safety_risk"),
    )
    if not coverage.is_runnable:
        return {"coverage": coverage.to_dict(), "status": "blocked"}
    profiles = load_profiles(disease_id)
    profile = profiles.get(drug_id)
    if not profile:
        return {}
    score = compute_adverse_event_score(profile, disease_id=disease_id)
    return {**profile, **score, "coverage": coverage.to_dict(), "status": "ready"}


def get_safety_summary(disease_id: str = "sle", results: list | None = None) -> dict:
    """Get safety summary statistics for the active disease."""
    results = score_all_drugs(disease_id=disease_id) if results is None else results
    scores = [r["composite_safety_score"] for r in results]

    from med_research.diseases.coverage import module_coverage

    coverage = module_coverage(
        disease_id,
        "safety",
        ("symptoms", "adverse_event_profile", "safety_risk"),
    )
    payload = _load_disease_profile_payload(disease_id) if coverage.is_runnable else {}
    return {
        "disease_id": disease_id,
        "total_drugs": len(results),
        "avg_safety_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "safest_drug": results[0]["drug_name"] if results else "",
        "safest_score": results[0]["composite_safety_score"] if results else 0,
        "riskiest_drug": results[-1]["drug_name"] if results else "",
        "riskiest_score": results[-1]["composite_safety_score"] if results else 0,
        "drugs_with_bbw": sum(1 for r in results if r.get("black_box_warnings")),
        "drugs_with_disease_specific_risk": sum(1 for r in results if r["disease_specific_risk_score"] < 10.0),
        "drugs_with_dil_risk": sum(1 for r in results if r["disease_specific_risk_score"] < 10.0),
        "coverage": coverage.to_dict(),
        "status": "limited_coverage" if coverage.level == "partial" else ("ready" if coverage.is_runnable else "blocked"),
        "profile_source": payload.get("profile_source", payload.get("source", "")),
        "profile_curated_inputs": payload.get("curated_inputs", []),
        "profile_inferred_inputs": payload.get("inferred_inputs", []),
        "limitations": payload.get("limitations", []),
    }


def print_analysis(results: list):
    """Print summary analysis."""
    logger.info("\n" + "=" * 75)
    logger.info("🛡️  ADVERSE EVENT PROFILING SUMMARY")
    logger.info("=" * 75)

    disease_id = results[0].get("disease_id", "sle") if results else "sle"
    summary = get_safety_summary(disease_id=disease_id, results=results)
    logger.info(f"\n  Total drugs profiled for {disease_id}: {summary['total_drugs']}")
    logger.info(f"  Average safety score: {summary['avg_safety_score']}")
    logger.info(f"  Safest drug: {summary['safest_drug']} ({summary['safest_score']:.1f})")
    logger.info(f"  Riskiest drug: {summary['riskiest_drug']} ({summary['riskiest_score']:.1f})")
    logger.info(f"  Drugs with black box warnings: {summary['drugs_with_bbw']}")
    logger.info(f"  Drugs with disease-specific risk: {summary['drugs_with_disease_specific_risk']}")

    logger.info("\n  Top 10 safest drugs:")
    for i, r in enumerate(results[:10], 1):
        bbw = f" [BBW: {len(r['black_box_warnings'])}]" if r.get("black_box_warnings") else ""
        logger.info(f"    {i:2d}. {r['drug_name']} — {r['composite_safety_score']:.1f}{bbw}")

    logger.info("\n  Bottom 5 highest-risk drugs:")
    for i, r in enumerate(results[-5:], 1):
        bbw = f" [BBW: {len(r['black_box_warnings'])}]" if r.get("black_box_warnings") else ""
        logger.info(f"    {i:2d}. {r['drug_name']} — {r['composite_safety_score']:.1f}{bbw}")


def main():
    parser = argparse.ArgumentParser(
        description="Adverse Event Profiler — disease-specific safety scoring"
    )
    parser.add_argument("--disease", "-d", default="sle", help="Disease ID")
    parser.add_argument("--drug", type=str, help="Show profile for a specific drug ID")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    if args.drug:
        profile = get_drug_profile(args.drug, disease_id=args.disease)
        if profile and profile.get("status") != "blocked" and profile.get("drug_name"):
            print(f"\n🛡️  Safety Profile: {profile['drug_name']}")
            print(f"   Composite Safety Score: {profile.get('composite_safety_score', 'N/A')}")
            print(f"   Disease Symptom Overlap: {profile.get('disease_symptom_overlap_score', 'N/A')}/10")
            print(f"   Severity Burden:         {profile.get('severity_burden_score', 'N/A')}/10")
            print(f"   Chronic Use Safety:      {profile.get('chronic_use_safety_score', 'N/A')}/10")
            print(f"   Disease-Specific Risk:   {profile.get('disease_specific_risk_score', 'N/A')}/10")
            print(f"   Black Box Warnings:      {profile.get('black_box_warnings', [])}")
            print(f"   Disease Overlap AEs:      {profile.get('disease_overlap_ae', [])}")
        else:
            if profile and profile.get("status") == "blocked":
                print(f"Safety analysis blocked for {args.disease}.")
            else:
                print(f"Drug '{args.drug}' not found in safety database.")
            return 1
        return 0

    results = score_all_drugs(disease_id=args.disease)
    if not results:
        print(f"Safety analysis is unavailable for {args.disease}.")
        return 1
    print_analysis(results)

    if args.export_html:
        from med_research.pipeline.adverse_events.report import generate_html_report
        generate_html_report(results, disease_id=args.disease)
        print("\n✅ HTML report generated: adverse_events/report.html")

    return 0


if __name__ == "__main__":
    raise SystemExit(main() or 0)
