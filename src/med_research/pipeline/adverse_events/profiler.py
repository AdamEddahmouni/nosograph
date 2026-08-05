"""
Adverse Event Profiling Engine

Scores drugs based on adverse event profiles relevant to lupus patients.
Evaluates safety across 4 dimensions:
  1. Lupus Symptom Overlap (inverted): Do adverse events mimic lupus symptoms?
  2. Severity Burden (inverted): How severe are the most common adverse events?
  3. Chronic Use Safety: Is the drug safe for long-term use?
  4. Drug-Induced Lupus Risk: Does the drug carry a risk of DIL?

Usage:
    python adverse_events/profiler.py              # Full analysis
    python adverse_events/profiler.py --drug belimumab  # Single drug
    python adverse_events/profiler.py --export-html  # Generate report
"""

import argparse
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

# ── Core lupus symptoms for overlap analysis ───────────────────────────

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


def load_profiles() -> dict:
    """Load adverse event profiles indexed by drug ID."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if PROFILES_PATH.exists():
        data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        return {p["drug_id"]: p for p in data["profiles"]}
    return _get_default_profiles()


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


def count_lupus_symptom_overlap(profile: dict) -> int:
    """Count how many adverse events overlap with lupus symptoms."""
    overlap = 0
    for ae in profile.get("lupus_overlap_ae", []):
        for symptom in LUPUS_SYMPTOMS:
            if symptom.lower() in ae.lower():
                overlap += 1
                break
    return overlap


def score_lupus_overlap(profile: dict) -> float:
    """Score lupus symptom overlap (0-10, higher = less overlap = safer)."""
    n_overlap = count_lupus_symptom_overlap(profile)
    if n_overlap == 0:
        return 10.0
    if n_overlap <= 2:
        return 8.0
    if n_overlap <= 3:
        return 6.0
    if n_overlap <= 5:
        return 4.0
    return 2.0


def score_severity_burden(profile: dict) -> float:
    """Convert severity burden (1-10 raw) to 0-10 score (higher = safer)."""
    raw = profile.get("severity_burden", 5)
    return 10.0 - raw


def score_chronic_safety(profile: dict) -> float:
    """Score chronic use safety from the raw 1-10 rating."""
    return float(profile.get("chronic_use_safety", 5))


def score_dil_risk(profile: dict) -> float:
    """Score drug-induced lupus risk (0-10, higher = lower risk)."""
    raw = profile.get("dil_risk", 0)
    if raw == 0:
        return 10.0
    if raw == 1:
        return 5.0
    return 2.0


def compute_adverse_event_score(profile: dict) -> dict:
    """Compute the adverse event safety score for a single drug.

    Returns dict with individual dimension scores and composite score.
    """
    lupus_overlap = score_lupus_overlap(profile)
    severity = score_severity_burden(profile)
    chronic = score_chronic_safety(profile)
    dil = score_dil_risk(profile)

    weights = {
        "lupus_symptom_overlap": 0.35,
        "severity_burden": 0.30,
        "chronic_use_safety": 0.25,
        "dil_risk": 0.10,
    }

    composite = (
        lupus_overlap * weights["lupus_symptom_overlap"]
        + severity * weights["severity_burden"]
        + chronic * weights["chronic_use_safety"]
        + dil * weights["dil_risk"]
    )

    return {
        "drug_id": profile["drug_id"],
        "drug_name": profile["drug_name"],
        "lupus_symptom_overlap_score": round(lupus_overlap, 1),
        "severity_burden_score": round(severity, 1),
        "chronic_use_safety_score": round(chronic, 1),
        "dil_risk_score": round(dil, 1),
        "composite_safety_score": round(composite, 2),
        "n_lupus_overlap_ae": count_lupus_symptom_overlap(profile),
        "lupus_overlap_ae": profile.get("lupus_overlap_ae", []),
        "black_box_warnings": profile.get("black_box_warnings", []),
        "monitoring_required": profile.get("monitoring_required", ""),
        "n_severe_ae": len(profile.get("severe_ae", [])),
    }


def score_all_drugs(progress_callback=None) -> list:
    """Score all drugs and return sorted list by composite safety score.

    Args:
        progress_callback: Optional callable(percent, message) for progress.

    Returns:
        List of safety scores sorted by composite_safety_score descending.
    """
    cb = progress_callback or (lambda p, m: None)
    profiles = load_profiles()

    cb(10, f"Profiling {len(profiles)} drugs for adverse events...")

    results = []
    for _drug_id, profile in profiles.items():
        results.append(compute_adverse_event_score(profile))

    results.sort(key=lambda x: x["composite_safety_score"], reverse=True)

    cb(50, "Saving profiles...")
    # Save profiles to JSON for persistence
    profile_list = list(profiles.values())
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_PATH.write_text(
        json.dumps({"profiles": profile_list}, indent=2),
        encoding="utf-8",
    )

    # Save safety scores
    scores_path = DATA_DIR / "safety_scores.json"
    scores_path.write_text(
        json.dumps({"safety_scores": results}, indent=2),
        encoding="utf-8",
    )

    cb(100, f"Safety profiling complete: {len(results)} drugs scored")

    return results


def get_drug_profile(drug_id: str) -> dict:
    """Get the adverse event profile and score for a specific drug."""
    profiles = load_profiles()
    profile = profiles.get(drug_id)
    if not profile:
        return {}
    score = compute_adverse_event_score(profile)
    return {**profile, **score}


def get_safety_summary() -> dict:
    """Get platform-wide safety summary statistics."""
    results = score_all_drugs()
    scores = [r["composite_safety_score"] for r in results]

    return {
        "total_drugs": len(results),
        "avg_safety_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "safest_drug": results[0]["drug_name"] if results else "",
        "safest_score": results[0]["composite_safety_score"] if results else 0,
        "riskiest_drug": results[-1]["drug_name"] if results else "",
        "riskiest_score": results[-1]["composite_safety_score"] if results else 0,
        "drugs_with_bbw": sum(1 for r in results if r.get("black_box_warnings")),
        "drugs_with_dil_risk": sum(1 for r in results if r["dil_risk_score"] < 10.0),
    }


def print_analysis(results: list):
    """Print summary analysis."""
    logger.info("\n" + "=" * 75)
    logger.info("🛡️  ADVERSE EVENT PROFILING SUMMARY")
    logger.info("=" * 75)

    summary = get_safety_summary()
    logger.info(f"\n  Total drugs profiled: {summary['total_drugs']}")
    logger.info(f"  Average safety score: {summary['avg_safety_score']}")
    logger.info(f"  Safest drug: {summary['safest_drug']} ({summary['safest_score']:.1f})")
    logger.info(f"  Riskiest drug: {summary['riskiest_drug']} ({summary['riskiest_score']:.1f})")
    logger.info(f"  Drugs with black box warnings: {summary['drugs_with_bbw']}")
    logger.info(f"  Drugs with DIL risk: {summary['drugs_with_dil_risk']}")

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
        description="Adverse Event Profiler — Safety scoring for lupus drug library"
    )
    parser.add_argument("--drug", type=str, help="Show profile for a specific drug ID")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    if args.drug:
        profile = get_drug_profile(args.drug)
        if profile:
            print(f"\n🛡️  Safety Profile: {profile['drug_name']}")
            print(f"   Composite Safety Score: {profile.get('composite_safety_score', 'N/A')}")
            print(f"   Lupus Overlap:          {profile.get('lupus_symptom_overlap_score', 'N/A')}/10")
            print(f"   Severity Burden:        {profile.get('severity_burden_score', 'N/A')}/10")
            print(f"   Chronic Use Safety:     {profile.get('chronic_use_safety_score', 'N/A')}/10")
            print(f"   DIL Risk:               {profile.get('dil_risk_score', 'N/A')}/10")
            print(f"   Black Box Warnings:     {profile.get('black_box_warnings', [])}")
            print(f"   Lupus Overlap AEs:      {profile.get('lupus_overlap_ae', [])}")
        else:
            print(f"Drug '{args.drug}' not found in safety database.")
        return

    results = score_all_drugs()
    print_analysis(results)

    if args.export_html:
        from med_research.pipeline.adverse_events.report import generate_html_report
        generate_html_report(results)
        print("\n✅ HTML report generated: adverse_events/report.html")

    return results


if __name__ == "__main__":
    main()
