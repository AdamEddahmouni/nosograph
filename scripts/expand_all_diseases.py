"""Bulk expand disease registry and scaffold all candidate diseases from Open Targets bulk store.

Usage:
    python scripts/expand_all_diseases.py --limit 2000 --workers 16
    python scripts/expand_all_diseases.py --all --workers 16
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.bulk_scaffold import bulk_harvest, print_bulk_harvest_summary
from med_research.diseases.scaffold import load_disease_registry, sanitize_id
from med_research.diseases.bulk_store import OpenTargetsBulkStore

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "src" / "med_research" / "diseases" / "disease_registry.json"
CANDIDATES_PATH = ROOT / "data" / "candidates" / "disease_candidates.json"


def categorize_disease(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["cancer", "carcinoma", "lymphoma", "leukemia", "sarcoma", "melanoma", "neoplasm", "tumor", "glioma", "myeloma", "adenocarcinoma", "blastoma", "malignan", "oncolog"]):
        return "oncology"
    if any(k in n for k in ["cardiac", "heart", "artery", "cardiovascular", "hypertension", "tachycardia", "cardiomyopathy", "aorta", "arrhythmia", "ischemic", "thrombosis", "vascular", "atherosclerosis"]):
        return "cardiovascular"
    if any(k in n for k in ["brain", "neuropathy", "epilepsy", "parkinson", "alzheimer", "dementia", "sclerosis", "ataxia", "dystonia", "encephalopathy", "palsy", "stroke", "headache", "neuralgia", "neurolog", "paralysis", "seizure", "chorea", "neuro"]):
        return "neurology"
    if any(k in n for k in ["diabetes", "metabolic", "obesity", "hypercholesterolemia", "lipid", "glycogen", "amyloidosis", "porphyria", "hyperuricemia", "storage disease"]):
        return "metabolic"
    if any(k in n for k in ["kidney", "renal", "nephritis", "glomerulo", "nephropathy", "nephrotic", "cystinuria", "dialysis"]):
        return "nephrology"
    if any(k in n for k in ["liver", "hepatic", "cirrhosis", "hepatitis", "fatty liver", "cholestasis", "jaundice", "biliary"]):
        return "hepatology"
    if any(k in n for k in ["lung", "pulmonary", "asthma", "pneumonia", "copd", "bronchitis", "respiratory", "pleural", "pneumothorax", "bronchiectasis"]):
        return "pulmonology"
    if any(k in n for k in ["skin", "dermatitis", "psoriasis", "eczema", "alopecia", "rosacea", "urticaria", "pemphigus", "cutaneous", "erythema", "pruritus", "acne", "keloid", "epidermolys"]):
        return "dermatology"
    if any(k in n for k in ["bone", "joint", "arthritis", "osteoporosis", "fracture", "tendon", "fasciitis", "muscular", "dystrophy", "myopathy", "spondylitis", "scoliosis"]):
        return "musculoskeletal"
    if any(k in n for k in ["eye", "retina", "glaucoma", "macular", "cataract", "cornea", "uveitis", "conjunctivitis", "blindness", "keratitis", "optic", "vision", "ocular"]):
        return "ophthalmology"
    if any(k in n for k in ["infection", "bacterial", "viral", "fungal", "parasitic", "tuberculosis", "malaria", "hiv", "herpes", "influenza", "sepsis", "covid", "measles", "rubella", "syphilis", "chlamydia", "gonorrhea", "meningitis", "encephalitis", "abscess", "microbial", "candidiasis", "aspergillosis", "fever"]):
        return "infectious"
    if any(k in n for k in ["anemia", "thrombocytopenia", "neutropenia", "leukopenia", "hemophilia", "coagulation", "sickle", "thalassemia", "hematolog", "pancytopenia", "purpura"]):
        return "hematology"
    if any(k in n for k in ["depression", "anxiety", "schizophrenia", "bipolar", "autism", "adhd", "psych", "addiction", "substance", "eating disorder", "ptsd", "ocd"]):
        return "psychiatry"
    if any(k in n for k in ["thyroid", "adrenal", "pituitary", "ovarian", "prostate", "testicular", "endometriosis", "menopause", "hypogonadism", "cushing", "addison", "parathyroid"]):
        return "endocrine_reproductive"
    if any(k in n for k in ["crohn", "colitis", "gastritis", "ulcer", "celiac", "irritable bowel", "esophagitis", "gastro", "intestinal", "pancreatitis", "dyspepsia", "reflux", "bowel"]):
        return "gastroenterology"
    if any(k in n for k in ["lupus", "rheumatoid", "autoimmune", "scleroderma", "sjogren", "vasculitis", "antiphospholipid", "sarcoidosis"]):
        return "autoimmune"
    if any(k in n for k in ["syndrome", "congenital", "hereditary", "genetic", "dystrophy", "deficiency", "malformation", "dysplasia"]):
        return "rare_genetic"
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description="Expand disease registry and scaffold all candidates")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of new candidate diseases to add")
    parser.add_argument("--all", action="store_true", help="Add all available candidates")
    parser.add_argument("--workers", type=int, default=16, help="Parallel harvest worker count")
    args = parser.parse_args()

    # Load current disease registry
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        registry_data = json.load(f)

    existing_ids = {sanitize_id(d["id"]) for d in registry_data["diseases"]}
    existing_efos = {d["efo_id"] for d in registry_data["diseases"] if d.get("efo_id")}

    # Load candidates
    if not CANDIDATES_PATH.exists():
        print(f"Candidates file {CANDIDATES_PATH} not found. Collecting now...")
        from subprocess import call
        call([sys.executable, str(ROOT / "scripts" / "collect_disease_candidates.py"), "--limit", "10000", "--min-genes", "1"])

    with open(CANDIDATES_PATH, encoding="utf-8") as f:
        cand_payload = json.load(f)

    candidates = cand_payload.get("candidates", [])
    added = 0

    for cand in candidates:
        efo = cand.get("efo_id")
        did = sanitize_id(cand["name"])

        if not did or len(did) < 3 or did in existing_ids:
            continue
        if efo and efo in existing_efos:
            continue

        category = categorize_disease(cand["name"])
        entry = {
            "id": did,
            "name": cand["name"],
            "category": category,
        }
        if efo:
            entry["efo_id"] = efo

        registry_data["diseases"].append(entry)
        existing_ids.add(did)
        if efo:
            existing_efos.add(efo)
        added += 1

        if args.limit and added >= args.limit:
            break

    # Save registry
    registry_data["diseases"].sort(key=lambda d: (d.get("category", ""), d.get("name", "")))
    registry_data["description"] = (
        f"Curated disease registry for batch scaffolding. "
        f"{len(registry_data['diseases'])} diseases across major therapeutic areas."
    )

    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Added {added} new diseases to registry. Total registry entries: {len(registry_data['diseases'])}")

    # Bulk harvest all new entries
    print(f"Starting parallel bulk harvest across {len(registry_data['diseases'])} diseases using {args.workers} workers...")
    harvest_report = bulk_harvest(
        repair=True,
        workers=args.workers,
        use_gwas=False,
        use_reactome=False,
    )
    print_bulk_harvest_summary(harvest_report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
