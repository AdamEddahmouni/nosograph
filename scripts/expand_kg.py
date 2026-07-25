"""Knowledge Graph Expansion Script

Expands genes, drugs, pathways, and relationships for 5 autoimmune diseases
(SS, T1D, SSc, MS, IBD) and adds MODULATES edges to all 6 non-SLE diseases.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_graph", "data")

DISEASE_NAMES = {
    "ss": "Sjögren's Syndrome (SS)",
    "t1d": "Type 1 Diabetes (T1D)",
    "ssc": "Systemic Sclerosis (SSc)",
    "ms": "Multiple Sclerosis (MS)",
    "ibd": "Inflammatory Bowel Disease (IBD)",
    "ra": "Rheumatoid Arthritis (RA)",
}

EVIDENCE_KEYS = {
    "ss": "ss_evidence", "t1d": "t1d_evidence",
    "ssc": "ssc_evidence", "ms": "ms_evidence",
    "ibd": "ibd_evidence", "sle": "lupus_evidence",
    "ra": "ra_evidence",
}

# ─── HELPER ──────────────────────────────────────────────────────────
def load_json(disease_id, filename):
    path = os.path.join(DATA_DIR, disease_id, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(disease_id, filename, data):
    path = os.path.join(DATA_DIR, disease_id, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_counts(disease_id):
    g = load_json(disease_id, "genes.json")
    d = load_json(disease_id, "drugs.json")
    p = load_json(disease_id, "pathways.json")
    r = load_json(disease_id, "relationships.json")
    return len(g["genes"]), len(d["drugs"]), len(p["pathways"]), len(r["relationships"])

# ─── NEW GENES DATA ──────────────────────────────────────────────────
SS_NEW_GENES = [
    {"id": "TYK2", "name": "Tyrosine Kinase 2", "chromosome": "19p13.2", "function": "JAK family kinase mediating type I IFN, IL-12, and IL-23 signaling", "ss_evidence": "TYK2 mediates type I IFN signaling. TYK2 inhibition being explored for SS.", "odds_ratio": 1.3, "references": ["PMID:25435325"], "category": "JAK-STAT Signaling"},
    {"id": "TLR7", "name": "Toll-Like Receptor 7", "chromosome": "Xp22.2", "function": "Endosomal sensor of single-stranded RNA; drives type I IFN production in plasmacytoid DCs", "ss_evidence": "TLR7 is directly targeted by HCQ in SS. TLR7 sensing of Ro/SSA-RNA in pDCs drives IFN-α.", "odds_ratio": 1.4, "references": ["PMID:21037563"], "category": "Innate Immune Sensing"},
    {"id": "TLR9", "name": "Toll-Like Receptor 9", "chromosome": "3p21.2", "function": "Endosomal sensor of unmethylated CpG DNA; activates B cells and pDCs", "ss_evidence": "TLR9 senses CpG DNA; HCQ inhibits TLR9 activation reducing autoantibody production.", "odds_ratio": 1.2, "references": ["PMID:21037563"], "category": "Innate Immune Sensing"},
    {"id": "MYD88", "name": "Myeloid Differentiation Primary Response 88", "chromosome": "3p22.2", "function": "Universal adaptor protein for TLR7, TLR9, and IL-1 receptor family signaling", "ss_evidence": "Universal TLR adaptor driving IFN-α in salivary gland pDCs.", "odds_ratio": 1.2, "references": ["PMID:21037563"], "category": "Innate Immune Sensing"},
    {"id": "IFNAR1", "name": "IFN Alpha/Beta Receptor 1", "chromosome": "21q22.11", "function": "Receptor subunit for type I interferons (IFN-α/β)", "ss_evidence": "Anifrolumab target. Mediates type I IFN signaling in SS salivary glands.", "odds_ratio": 1.2, "references": ["PMID:20694012"], "category": "Type I Interferon Pathway"},
    {"id": "IFNA1", "name": "Interferon Alpha 1", "chromosome": "9p21.3", "function": "Type I interferon; key cytokine produced by pDCs", "ss_evidence": "IFN-α massively produced by pDCs in SS. Correlates with disease activity.", "odds_ratio": 1.3, "references": ["PMID:20694012"], "category": "Type I Interferon Pathway"},
    {"id": "IL6", "name": "Interleukin-6", "chromosome": "7p15.3", "function": "Pro-inflammatory cytokine driving Th17/Tfh differentiation and B cell activation", "ss_evidence": "Elevated in SS serum/saliva. Promotes Th17/Tfh differentiation.", "odds_ratio": 1.2, "references": ["PMID:21037563"], "category": "Pro-inflammatory Cytokine"},
    {"id": "CD40LG", "name": "CD40 Ligand", "chromosome": "Xq26.3", "function": "Costimulatory molecule on T cells engaging CD40 on B cells; drives germinal center responses", "ss_evidence": "CD40L overexpressed on SS T cells. Drives germinal center B cell responses.", "odds_ratio": 1.2, "references": ["PMID:27630099"], "category": "T Cell Costimulation / Tfh"},
    {"id": "FOXP3", "name": "Forkhead Box P3", "chromosome": "Xp11.23", "function": "Master transcription factor for regulatory T cell (Treg) development and function", "ss_evidence": "Treg dysfunction documented in SS. Low-dose IL-2 therapy being explored.", "odds_ratio": 1.15, "references": ["PMID:14645683"], "category": "Treg / Immune Regulation"},
    {"id": "CD19", "name": "CD19 Molecule", "chromosome": "16p11.2", "function": "Pan-B-cell surface protein; co-receptor that enhances BCR signaling", "ss_evidence": "Pan-B cell marker targeted by CAR-T. Being explored for severe SS.", "odds_ratio": 1.2, "references": ["PMID:28628108"], "category": "B Cell Signaling"},
    {"id": "AICDA", "name": "Activation-Induced Cytidine Deaminase", "chromosome": "12p13.31", "function": "Enzyme mediating somatic hypermutation and class switch recombination in B cells", "ss_evidence": "AID highly expressed in SS GC B cells. Links to lymphoma risk.", "odds_ratio": 1.3, "references": ["PMID:27630099"], "category": "B Cell / Germinal Center"},
]

T1D_NEW_GENES = [
    {"id": "TYK2", "name": "Tyrosine Kinase 2", "chromosome": "19p13.2", "function": "JAK family kinase mediating type I IFN, IL-12, and IL-23 signaling", "t1d_evidence": "TYK2 mediates type I IFN and IL-12 in islet-infiltrating cells.", "odds_ratio": 1.2, "references": ["PMID:25435325"], "category": "JAK-STAT Signaling"},
    {"id": "JAK1", "name": "Janus Kinase 1", "chromosome": "1p31.3", "function": "Tyrosine kinase mediating signaling for type I/II cytokine receptors", "t1d_evidence": "JAK1 transduces IFN-γ/IL-6 signals cytotoxic to β cells.", "odds_ratio": 1.2, "references": ["PMID:25435325"], "category": "JAK-STAT Signaling"},
    {"id": "FOXP3", "name": "Forkhead Box P3", "chromosome": "Xp11.23", "function": "Master transcription factor for regulatory T cell development and function", "t1d_evidence": "FOXP3+ Tregs deficient in T1D. Major therapeutic strategy.", "odds_ratio": 1.15, "references": ["PMID:14645683"], "category": "Treg / Immune Regulation"},
    {"id": "CTLA4", "name": "Cytotoxic T-Lymphocyte Associated Protein 4", "chromosome": "2q33.2", "function": "Inhibitory receptor on T cells competing with CD28 for B7 binding", "t1d_evidence": "Abatacept slowed C-peptide decline in TrialNet.", "odds_ratio": 1.25, "references": ["PMID:8817351"], "category": "T Cell Costimulation"},
    {"id": "GAD2", "name": "Glutamic Acid Decarboxylase 2 (GAD65)", "chromosome": "10p12.1", "function": "Catalyzes GABA synthesis; primary autoantigen in T1D", "t1d_evidence": "Primary T1D autoantigen. Anti-GAD65 antibodies in ~80% of patients.", "odds_ratio": None, "references": ["PMID:1697649"], "category": "β Cell Autoantigen"},
    {"id": "PTPRN", "name": "IA-2 / ICA512", "chromosome": "2q35", "function": "Transmembrane protein tyrosine phosphatase-like protein; major T1D autoantigen", "t1d_evidence": "Key T1D autoantigen biomarker. Predicts progression with >90% specificity.", "odds_ratio": None, "references": ["PMID:7544800"], "category": "β Cell Autoantigen"},
    {"id": "IL2", "name": "Interleukin-2", "chromosome": "4q27", "function": "Essential cytokine for Treg survival and function", "t1d_evidence": "IL-2 signaling impaired in T1D. Low-dose IL-2 therapy in Phase 2 trials.", "odds_ratio": 1.15, "references": ["PMID:19430480"], "category": "Treg / IL-2 Pathway"},
]

SSC_NEW_GENES = [
    {"id": "TYK2", "name": "Tyrosine Kinase 2", "chromosome": "19p13.2", "function": "JAK family kinase mediating type I IFN, IL-12, and IL-23 signaling", "ssc_evidence": "TYK2 mediates IL-12/IL-23 and type I IFN in SSc.", "odds_ratio": 1.2, "references": ["PMID:25435325"], "category": "JAK-STAT Signaling"},
    {"id": "TLR7", "name": "Toll-Like Receptor 7", "chromosome": "Xp22.2", "function": "Endosomal sensor of single-stranded RNA; drives type I IFN production in pDCs", "ssc_evidence": "TLR7 overexpressed in SSc skin. Sustains IFN-driven fibrosis.", "odds_ratio": 1.3, "references": ["PMID:21037563"], "category": "Innate Immune / TLR Signaling"},
    {"id": "IL6", "name": "Interleukin-6", "chromosome": "7p15.3", "function": "Pro-inflammatory cytokine driving Th17/Tfh differentiation and fibroblast activation", "ssc_evidence": "IL-6 markedly elevated in SSc. Tocilizumab FDA-approved for SSc-ILD.", "odds_ratio": 1.2, "references": ["PMID:21037563"], "category": "IL-6 / JAK-STAT"},
    {"id": "CTGF", "name": "Connective Tissue Growth Factor (CCN2)", "chromosome": "6q23.2", "function": "Matricellular protein enhancing TGF-β-driven fibrosis and ECM deposition", "ssc_evidence": "CTGF overexpressed in SSc. Enhances TGF-β-driven fibrosis.", "odds_ratio": 1.3, "references": ["PMID:31534227"], "category": "Fibrosis / TGF-β Signaling"},
    {"id": "SERPINE1", "name": "PAI-1", "chromosome": "7q22.1", "function": "Serpin that inhibits plasminogen activation and matrix degradation", "ssc_evidence": "PAI-1 elevated in SSc. Inhibits matrix degradation.", "odds_ratio": 1.25, "references": ["PMID:31534227"], "category": "Fibrosis / ECM Remodeling"},
    {"id": "SMAD3", "name": "SMAD Family Member 3", "chromosome": "15q22.33", "function": "Intracellular mediator of TGF-β signaling; drives collagen transcription", "ssc_evidence": "Constitutively phosphorylated in SSc fibroblasts. Drives collagen production.", "odds_ratio": 1.2, "references": ["PMID:14514736"], "category": "Fibrosis / TGF-β Signaling"},
    {"id": "COL1A1", "name": "Collagen Type I Alpha 1", "chromosome": "17q21.33", "function": "Major structural component of extracellular matrix", "ssc_evidence": "Massively overexpressed in SSc. Hallmark of fibrosis.", "odds_ratio": None, "references": ["PMID:14514736"], "category": "Fibrosis / ECM Component"},
    {"id": "CTLA4", "name": "Cytotoxic T-Lymphocyte Associated Protein 4", "chromosome": "2q33.2", "function": "Inhibitory receptor on T cells competing with CD28 for B7 binding", "ssc_evidence": "Abatacept in clinical trials for SSc.", "odds_ratio": 1.2, "references": ["PMID:8817351"], "category": "T Cell Costimulation"},
    {"id": "FOXP3", "name": "Forkhead Box P3", "chromosome": "Xp11.23", "function": "Master transcription factor for regulatory T cell development and function", "ssc_evidence": "Treg dysfunction documented in SSc.", "odds_ratio": 1.15, "references": ["PMID:14645683"], "category": "Treg / Immune Regulation"},
]

MS_NEW_GENES = [
    {"id": "TYK2", "name": "Tyrosine Kinase 2", "chromosome": "19p13.2", "function": "JAK family kinase mediating type I IFN, IL-12, and IL-23 signaling", "ms_evidence": "TYK2 mediates IL-12/IL-23 critical for CNS autoimmunity.", "odds_ratio": 1.2, "references": ["PMID:25435325"], "category": "JAK-STAT Signaling"},
    {"id": "MBP", "name": "Myelin Basic Protein", "chromosome": "18q23", "function": "Major structural component of CNS myelin; primary autoantigen in MS", "ms_evidence": "Prototype MS autoantigen. MBP-specific T cells in MS/EAE.", "odds_ratio": None, "references": ["PMID:24746690"], "category": "Myelin Autoantigen"},
    {"id": "MOG", "name": "Myelin Oligodendrocyte Glycoprotein", "chromosome": "6p21.33", "function": "Myelin protein on oligodendrocyte surface; target of autoantibodies", "ms_evidence": "Anti-MOG defines MOGAD spectrum overlapping MS.", "odds_ratio": None, "references": ["PMID:24746690"], "category": "Myelin Autoantigen"},
    {"id": "IL23R", "name": "Interleukin-23 Receptor", "chromosome": "1p31.3", "function": "Receptor subunit for IL-23; drives Th17 cell expansion", "ms_evidence": "IL23R R381Q protective variant (OR 0.6). Strong MS GWAS hit.", "odds_ratio": 0.6, "references": ["PMID:24746690"], "category": "Th17 / IL-23 Pathway"},
    {"id": "CD4", "name": "CD4 Molecule", "chromosome": "12p13.31", "function": "Coreceptor for MHC class II; defines helper T cell lineage", "ms_evidence": "CD4+ T cells are primary drivers of CNS inflammation in MS.", "odds_ratio": None, "references": ["PMID:24746690"], "category": "T Cell / Adaptive Immunity"},
    {"id": "CD8A", "name": "CD8a Molecule", "chromosome": "2p11.2", "function": "Coreceptor for MHC class I; defines cytotoxic T cell lineage", "ms_evidence": "CD8+ T cells dominate MS lesion infiltrates.", "odds_ratio": None, "references": ["PMID:24746690"], "category": "T Cell / Adaptive Immunity"},
    {"id": "JAK1", "name": "Janus Kinase 1", "chromosome": "1p31.3", "function": "Tyrosine kinase mediating signaling for type I/II cytokine receptors", "ms_evidence": "JAK1 mediates multiple MS-relevant cytokine signals.", "odds_ratio": 1.2, "references": ["PMID:25435325"], "category": "JAK-STAT Signaling"},
]

IBD_NEW_GENES = [
    {"id": "TYK2", "name": "Tyrosine Kinase 2", "chromosome": "19p13.2", "function": "JAK family kinase mediating type I IFN, IL-12, and IL-23 signaling", "ibd_evidence": "TYK2 mediates IL-12/IL-23 dominant pathogenic axis in IBD.", "odds_ratio": 1.2, "references": ["PMID:25435325"], "category": "JAK-STAT Signaling"},
    {"id": "NOD2", "name": "NOD2 / CARD15", "chromosome": "16q12.1", "function": "Intracellular pattern recognition receptor sensing MDP; activates NF-κB and autophagy", "ibd_evidence": "Strongest CD risk gene (OR 3-4). Impaired bacterial sensing.", "odds_ratio": 3.0, "references": ["PMID:11385576"], "category": "Innate Immune / Bacterial Sensing"},
    {"id": "ATG16L1", "name": "Autophagy Related 16 Like 1", "chromosome": "2q37.1", "function": "Essential autophagy component; regulates Paneth cell function", "ibd_evidence": "T300A variant CD risk OR 1.3. Impaired Paneth cell function.", "odds_ratio": 1.3, "references": ["PMID:17435757"], "category": "Autophagy / Innate Immunity"},
    {"id": "IL23R", "name": "Interleukin-23 Receptor", "chromosome": "1p31.3", "function": "Receptor subunit for IL-23; drives Th17 cell expansion", "ibd_evidence": "R381Q variant (OR 0.3). Strongest protective IBD allele.", "odds_ratio": 0.3, "references": ["PMID:17068223"], "category": "IL-23 / Th17 Axis"},
    {"id": "IL17A", "name": "Interleukin-17A", "chromosome": "6p12.2", "function": "Signature Th17 cytokine; drives mucosal inflammation", "ibd_evidence": "Elevated in IBD mucosa. Complex protective/pathogenic roles.", "odds_ratio": 1.15, "references": ["PMID:22936677"], "category": "Th17 / IL-23 Pathway"},
]

NEW_GENES = {"ss": SS_NEW_GENES, "t1d": T1D_NEW_GENES,
             "ssc": SSC_NEW_GENES, "ms": MS_NEW_GENES, "ibd": IBD_NEW_GENES}

# ─── NEW DRUGS ───────────────────────────────────────────────────────
SS_NEW_DRUGS = [
    {"id": "baricitinib", "name": "Baricitinib (Olumiant)", "type": "Small Molecule", "target": "JAK1/JAK2", "mechanism": "JAK1/JAK2 inhibitor blocking type I IFN, IL-6, and other cytokine signaling", "approval": "Phase 2 in SS being explored", "route": "Oral daily", "efficacy": "Phase 2 in SS being explored", "references": ["PMID:29969085"], "category": "JAK Inhibitor"},
    {"id": "tofacitinib", "name": "Tofacitinib (Xeljanz)", "type": "Small Molecule", "target": "JAK1/JAK3", "mechanism": "Pan-JAK inhibitor broadly blocking cytokine signaling through JAK-STAT pathways", "approval": "Case reports in refractory SS", "route": "Oral", "efficacy": "Case reports in refractory SS", "references": ["PMID:29969085"], "category": "JAK Inhibitor"},
    {"id": "deucravacitinib", "name": "Deucravacitinib (Sotyktu)", "type": "Small Molecule", "target": "TYK2", "mechanism": "Allosteric TYK2 inhibitor binding JH2 pseudokinase domain; blocks type I IFN, IL-12, IL-23", "approval": "Rational target for SS IFN/IL-12 axis", "route": "Oral daily", "efficacy": "Rational target for SS IFN/IL-12 axis", "references": ["PMID:28628108"], "category": "TYK2 Inhibitor"},
    {"id": "efgartigimod", "name": "Efgartigimod (Vyvgart)", "type": "Fc Fragment", "target": "FcRn", "mechanism": "FcRn blocker accelerating IgG degradation; reduces pathogenic autoantibodies", "approval": "Investigational for SS", "route": "IV weekly", "efficacy": "Reduces anti-Ro/SSA autoantibodies", "references": ["PMID:33958576"], "category": "FcRn Blocker"},
    {"id": "dazodalibep", "name": "Dazodalibep", "type": "Fusion Protein", "target": "CD40LG", "mechanism": "CD40L antagonist blocking T-B cell costimulation", "approval": "Phase 2 positive in SS", "route": "IV every 2-4 weeks", "efficacy": "Phase 2 positive in SS", "references": ["PMID:35145352"], "category": "Anti-CD40L"},
    {"id": "secukinumab", "name": "Secukinumab (Cosentyx)", "type": "Monoclonal Antibody", "target": "IL-17A", "mechanism": "Anti-IL-17A antibody neutralizing IL-17-driven inflammation", "approval": "Investigational for SS", "route": "Subcutaneous monthly", "efficacy": "Investigational for SS", "references": ["PMID:33958576"], "category": "Anti-IL-17A"},
]

NEW_DRUGS = {"ss": SS_NEW_DRUGS}

# ─── NEW PATHWAYS ────────────────────────────────────────────────────
SS_NEW_PATHWAYS = [
    {"id": "nfkb-inflammatory-ss", "name": "NF-κB / Inflammatory Cytokine Axis",
     "description": "Chronic NF-κB activation drives IL-6, TNF-α, and BAFF production. TNFAIP3/TNIP1 dysfunction leads to persistent NF-κB in salivary glands.",
     "key_components": ["TNFAIP3", "TNIP1", "NFKB1", "RELA", "IL6", "TNF", "IL1B", "BAFF"],
     "therapeutic_targets": ["Potential: JAK inhibitors"], "references": ["PMID:19165926"]},
    {"id": "fibrosis-lymphoma-ss", "name": "Tissue Remodeling, Fibrosis & Lymphoma",
     "description": "Chronic inflammation leads to gland destruction, fibrosis, and 15-20x lymphoma risk.",
     "key_components": ["TGFB1", "AICDA", "BCL2", "MYC", "BAFF", "CXCR5", "CXCL13"],
     "therapeutic_targets": ["Potential: Anti-BAFF, BTK inhibitors"], "references": ["PMID:27630099"]},
]

T1D_NEW_PATHWAYS = [
    {"id": "beta-cell-er-stress-t1d", "name": "β Cell ER Stress & Apoptosis",
     "description": "β cells sensitive to ER stress from high proinsulin synthesis. Cytokines induce ER stress → CHOP apoptosis.",
     "key_components": ["INS", "GLIS3", "PTPN2", "ERBB3", "TNF", "IL1B", "IFNG"],
     "therapeutic_targets": ["Potential: Anti-TNF, GLP-1 RAs"], "references": ["PMID:19430480"]},
    {"id": "treg-il2-t1d", "name": "Treg / IL-2 Immune Regulation",
     "description": "Impaired IL-2/Treg axis in T1D. Restoring Tregs is major therapeutic strategy.",
     "key_components": ["FOXP3", "IL2", "IL2RA", "CTLA4", "IL10", "BACH2", "PTPN22"],
     "therapeutic_targets": ["Low-dose IL-2", "Teplizumab", "Abatacept"], "references": ["PMID:24152931"]},
]

SSC_NEW_PATHWAYS = [
    {"id": "tgfb-fibrosis-ssc", "name": "TGF-β / Myofibroblast Fibrosis Cascade",
     "description": "Master profibrotic pathway. Autocrine TGF-β loops maintain fibrosis.",
     "key_components": ["TGFB1", "SMAD3", "COL1A1", "CTGF", "SERPINE1", "ACTA2", "PPARG"],
     "therapeutic_targets": ["Nintedanib", "Tocilizumab"], "references": ["PMID:14514736"]},
    {"id": "vascular-endothelin-ssc", "name": "Vascular Remodeling & Endothelin Pathway",
     "description": "SSc vasculopathy: endothelial injury, obliterative vasculopathy, PAH.",
     "key_components": ["EDN1", "EDNRA", "EDNRB", "NOS3", "VEGFA", "PDGFRB"],
     "therapeutic_targets": ["Bosentan", "Riociguat"], "references": ["PMID:31534227"]},
]

MS_NEW_PATHWAYS = [
    {"id": "th17-il23-ms", "name": "Th17 / IL-23 Autoimmune Axis",
     "description": "Th17 cells key drivers of CNS autoimmunity. IL-23 essential for Th17 pathogenicity.",
     "key_components": ["IL23A", "IL23R", "IL17A", "IL17F", "IL21", "IL22", "RORC", "STAT3", "TYK2"],
     "therapeutic_targets": ["Potential: Deucravacitinib"], "references": ["PMID:24746690"]},
    {"id": "bbb-trafficking-ms", "name": "Blood-Brain Barrier & Immune Cell Trafficking",
     "description": "BBB crossing is critical in MS. Natalizumab blocks VLA-4/VCAM-1.",
     "key_components": ["ITGA4", "ITGB1", "VCAM1", "ICAM1", "CXCL12", "CXCR4"],
     "therapeutic_targets": ["Natalizumab", "Potential: S1P modulators"], "references": ["PMID:24746690"]},
]

IBD_NEW_PATHWAYS = [
    {"id": "il23-th17-mucosal-ibd", "name": "IL-23 / Th17 Mucosal Inflammation",
     "description": "Dominant pathogenic axis in IBD. Strong GWAS support.",
     "key_components": ["IL23A", "IL23R", "IL17A", "IL17F", "IL22", "RORC", "STAT3", "TYK2"],
     "therapeutic_targets": ["Risankizumab", "Ustekinumab", "Potential: Deucravacitinib"], "references": ["PMID:17068223"]},
    {"id": "epithelial-autophagy-ibd", "name": "Epithelial Barrier & Autophagy",
     "description": "Impaired autophagy → Paneth cell dysfunction → microbial dysbiosis.",
     "key_components": ["NOD2", "ATG16L1", "IRGM", "IL22", "MUC2", "DEFA5"],
     "therapeutic_targets": ["Potential: IL-22-Fc"], "references": ["PMID:11385576"]},
]

NEW_PATHWAYS = {"ss": SS_NEW_PATHWAYS, "t1d": T1D_NEW_PATHWAYS,
                "ssc": SSC_NEW_PATHWAYS, "ms": MS_NEW_PATHWAYS,
                "ibd": IBD_NEW_PATHWAYS}

# ─── RELATIONSHIP GENERATORS ─────────────────────────────────────────
def build_ss_relationships(existing_genes, existing_drugs, existing_pathways):
    """Build all new relationships for SS."""
    gids = {g["id"] for g in existing_genes}
    dids = {d["id"] for d in existing_drugs}
    pids = {p["id"] for p in existing_pathways}
    dn = DISEASE_NAMES["ss"]
    rels = []

    # TARGETS: new drugs → genes
    targets_map = {
        "baricitinib": [("JAK1", "Baricitinib inhibits JAK1/JAK2, blocking type I IFN and IL-6 signaling in SS")],
        "tofacitinib": [("JAK1", "Tofacitinib inhibits JAK1/JAK3, broadly blocking cytokine-driven JAK-STAT signaling")],
        "deucravacitinib": [("TYK2", "Deucravacitinib is a highly selective allosteric TYK2 inhibitor, blocking type I IFN, IL-12, and IL-23 signaling")],
        "dazodalibep": [("CD40LG", "Dazodalibep blocks CD40L, inhibiting T-B cell costimulation")],
        "secukinumab": [("IL17A", "Secukinumab neutralizes IL-17A, reducing Th17-driven inflammation")],
    }
    for drug_id, targets_list in targets_map.items():
        if drug_id in dids:
            for tgt, desc in targets_list:
                if tgt in gids:
                    rels.append({"source": drug_id, "target": tgt, "type": "TARGETS", "description": desc})

    # TARGETS: existing SS drugs → new genes (if they already have target relationships, we supplement)
    # Actually, let's map existing drug->gene targets that might be missing
    extra_targets = [
        ("hydroxychloroquine", "MYD88", "Hydroxychloroquine indirectly inhibits TLR7/TLR9-MyD88 signaling by preventing endosome acidification"),
    ]
    for src, tgt, desc in extra_targets:
        if src in dids and tgt in gids:
            rels.append({"source": src, "target": tgt, "type": "TARGETS", "description": desc})

    # TREATS: new drugs → disease
    for drug_id in ["baricitinib", "tofacitinib", "deucravacitinib", "efgartigimod", "dazodalibep", "secukinumab"]:
        if drug_id in dids:
            rels.append({"source": drug_id, "target": dn, "type": "TREATS",
                         "description": f"{drug_id.replace('_', ' ').title()} is investigational for Sjögren's syndrome"})

    # ASSOCIATED_WITH: new genes → disease
    for g in SS_NEW_GENES:
        if g["id"] in gids:
            rels.append({"source": g["id"], "target": dn, "type": "ASSOCIATED_WITH",
                         "description": f"{g['name']} ({g['chromosome']}): {g['ss_evidence']}"})

    # PARTICIPATES_IN: genes → pathways
    gene_pathway_map_ss = {
        "TYK2": [("type1-ifn-signature-ss", "TYK2 mediates type I IFN and IL-12/IL-23 JAK-STAT signaling in SS"),
                 ("jak-stat-ss", "TYK2 is a JAK family kinase mediating type I IFN and IL-12/IL-23 signaling in SS")],
        "TLR7": [("tlr-innate-ss", "TLR7 senses Ro/SSA-RNA immune complexes in endosomes, triggering pDC IFN-α production"),
                 ("type1-ifn-signature-ss", "TLR7 activation in pDCs drives the type I IFN signature in SS")],
        "TLR9": [("tlr-innate-ss", "TLR9 senses CpG DNA immune complexes, driving B cell activation and autoantibody production")],
        "MYD88": [("tlr-innate-ss", "MyD88 is the universal TLR7/TLR9 adaptor driving IFN-α in salivary gland pDCs"),
                  ("type1-ifn-signature-ss", "MyD88 transduces TLR7/TLR9 signals driving the IFN signature")],
        "IFNAR1": [("type1-ifn-signature-ss", "IFNAR1 is the receptor for type I IFNs targeted by anifrolumab")],
        "IFNA1": [("type1-ifn-signature-ss", "IFN-α is massively produced by pDCs in SS salivary glands")],
        "IL6": [("nfkb-inflammatory-ss", "IL-6 is a key NF-κB target gene driving Th17/Tfh differentiation in SS")],
        "CD40LG": [("tfh-germinal-ss", "CD40L on Tfh cells engages CD40 on B cells, driving germinal center responses in SS")],
        "FOXP3": [("tfh-germinal-ss", "FOXP3+ Treg dysfunction contributes to uncontrolled Tfh-B cell responses in SS")],
        "CD19": [("bcell-baff-ss", "CD19 is a pan-B-cell co-receptor that amplifies BCR signaling; target of CAR-T")],
        "AICDA": [("fibrosis-lymphoma-ss", "AID is highly expressed in SS germinal center B cells, linking to lymphoma risk"),
                  ("bcell-baff-ss", "AID mediates somatic hypermutation in autoreactive B cells driven by BAFF")],
    }
    for gid, pw_list in gene_pathway_map_ss.items():
        if gid in gids:
            for pid, desc in pw_list:
                if pid in pids:
                    rels.append({"source": gid, "target": pid, "type": "PARTICIPATES_IN", "description": desc})

    # DRIVES: new pathways → disease
    pathway_drives_ss = {
        "nfkb-inflammatory-ss": "Chronic NF-κB activation drives IL-6, TNF-α, and BAFF production in SS salivary glands",
        "fibrosis-lymphoma-ss": "Chronic inflammation leads to gland destruction, fibrosis, and 15-20x lymphoma risk in SS",
    }
    for pid, desc in pathway_drives_ss.items():
        if pid in pids:
            rels.append({"source": pid, "target": dn, "type": "DRIVES", "description": desc})
    # Drive for existing pathways (in case they don't already exist for new genes):
    # (Already covered in DRIVES for all existing pathways)

    # MODULATES: drugs → pathways
    modulates_ss = [
        ("hydroxychloroquine", "tlr-innate-ss", "Hydroxychloroquine inhibits endosomal TLR7 and TLR9 activation"),
        ("belimumab", "bcell-baff-ss", "Belimumab neutralizes BAFF, reducing B cell survival signals in SS"),
        ("ianalumab", "bcell-baff-ss", "Ianalumab blocks BAFF-R and depletes BAFF-R+ B cells via ADCC"),
        ("iscalimab", "tfh-germinal-ss", "Iscalimab blocks CD40, inhibiting Tfh-B cell costimulation and GC formation"),
        ("abatacept", "tfh-germinal-ss", "Abatacept (CTLA4-Ig) blocks CD28-mediated T cell costimulation, indirectly reducing Tfh help"),
        ("rituximab_ss", "bcell-baff-ss", "Rituximab depletes CD20+ B cells, reducing B cell-driven autoantibody production"),
        ("baricitinib", "jak-stat-ss", "Baricitinib inhibits JAK1/JAK2, suppressing cytokine-driven JAK-STAT signaling in SS"),
        ("tofacitinib", "jak-stat-ss", "Tofacitinib broadly suppresses JAK-STAT signaling downstream of multiple proinflammatory cytokine receptors"),
        ("deucravacitinib", "type1-ifn-signature-ss", "Deucravacitinib blocks TYK2-dependent type I IFN signaling, reducing the IFN signature"),
        ("deucravacitinib", "jak-stat-ss", "Deucravacitinib selectively inhibits TYK2-mediated JAK-STAT signaling"),
        ("prednisone_ss", "nfkb-inflammatory-ss", "Prednisone activates glucocorticoid receptor, broadly suppressing NF-κB-mediated inflammatory gene transcription"),
        ("mycophenolate", "bcell-baff-ss", "Mycophenolate inhibits IMPDH, suppressing T and B lymphocyte proliferation"),
    ]
    for src, tgt, desc in modulates_ss:
        if src in dids and tgt in pids:
            rels.append({"source": src, "target": tgt, "type": "MODULATES", "description": desc})

    return rels


def build_t1d_relationships(existing_genes, existing_drugs, existing_pathways):
    gids = {g["id"] for g in existing_genes}
    dids = {d["id"] for d in existing_drugs}
    pids = {p["id"] for p in existing_pathways}
    dn = DISEASE_NAMES["t1d"]
    rels = []

    # ASSOCIATED_WITH: new genes → disease
    for g in T1D_NEW_GENES:
        if g["id"] in gids:
            rels.append({"source": g["id"], "target": dn, "type": "ASSOCIATED_WITH",
                         "description": f"{g['name']} ({g['chromosome']}): {g['t1d_evidence']}"})

    # PARTICIPATES_IN: genes → pathways
    gene_pathway_map = {
        "TYK2": [("type1-ifn", "TYK2 mediates type I IFN and IL-12 signaling in islet-infiltrating immune cells"),
                 ("tcell-insulitis", "TYK2 transduces IL-12 signals driving Th1 responses in insulitis")],
        "JAK1": [("beta-cell-er-stress", "JAK1 transduces IFN-γ/IL-6 signals that are directly cytotoxic to β cells"),
                 ("type1-ifn", "JAK1 partners with TYK2 to mediate type I IFN signaling in islet cells")],
        "FOXP3": [("il2-treg", "FOXP3 is the master transcription factor for Tregs; Tregs are deficient in T1D"),
                  ("treg-il2-t1d", "FOXP3+ Tregs are deficient in T1D; restoring Tregs is major therapeutic strategy")],
        "CTLA4": [("costim-checkpoint", "CTLA4 is the key inhibitory immune checkpoint competing with CD28 for B7 binding"),
                  ("treg-il2-t1d", "CTLA4 mediates Treg contact-dependent suppression of islet-reactive T cells")],
        "GAD2": [("hla-antigen-presentation", "GAD65 is a primary T1D autoantigen presented by HLA-DQ2/DQ8"),
                 ("tcell-insulitis", "GAD65 is a primary autoantigen targeted by autoreactive T cells in insulitis")],
        "PTPRN": [("hla-antigen-presentation", "IA-2 is a key T1D autoantigen biomarker predicting progression with >90% specificity"),
                  ("tcell-insulitis", "IA-2 autoantibodies predict progression to clinical T1D")],
        "IL2": [("il2-treg", "IL-2 is essential for Treg survival and function; IL-2 signaling impaired in T1D"),
                ("treg-il2-t1d", "IL-2 is the critical cytokine for Treg survival; low-dose IL-2 therapy in trials")],
    }
    for gid, pw_list in gene_pathway_map.items():
        if gid in gids:
            for pid, desc in pw_list:
                if pid in pids:
                    rels.append({"source": gid, "target": pid, "type": "PARTICIPATES_IN", "description": desc})

    # DRIVES: new pathways → disease
    pathway_drives = {
        "beta-cell-er-stress-t1d": "Cytokine-induced β cell ER stress triggers β cell apoptosis via CHOP and TXNIP/NLRP3 pathways",
        "treg-il2-t1d": "Impaired IL-2/Treg axis fails to suppress islet-reactive T cells, allowing unchecked autoimmune β cell destruction",
    }
    for pid, desc in pathway_drives.items():
        if pid in pids:
            rels.append({"source": pid, "target": dn, "type": "DRIVES", "description": desc})

    # MODULATES: drugs → pathways
    modulates = [
        ("teplizumab", "tcell-insulitis", "Teplizumab modulates CD3/TCR complex, inducing anergy in effector T cells and expanding Tregs"),
        ("golimumab", "beta-cell-er-stress", "Golimumab neutralizes TNF-α, reducing β cell ER stress and apoptosis"),
        ("golimumab", "tcell-insulitis", "Golimumab blocks TNF-α, reducing T cell-mediated β cell cytotoxicity"),
        ("abatacept", "costim-checkpoint", "Abatacept (CTLA4-Ig) blocks CD28 costimulation, reducing islet-reactive T cell activation"),
        ("rituximab", "tcell-insulitis", "Rituximab depletes CD20+ B cells involved in autoantigen presentation to islet-reactive T cells"),
        ("low_dose_il2", "il2-treg", "Low-dose IL-2 selectively expands FOXP3+ Tregs, restoring immune regulation"),
        ("low_dose_il2", "treg-il2-t1d", "Low-dose IL-2 directly targets the impaired IL-2/Treg axis in T1D"),
        ("verapamil", "beta-cell-er-stress", "Verapamil reduces TXNIP expression, protecting β cells from ER stress and inflammasome activation"),
        ("verapamil", "beta-cell-er-stress-t1d", "Verapamil reduces TXNIP, protecting β cells from ER stress and apoptosis"),
        ("ustekinumab", "tcell-insulitis", "Ustekinumab blocks IL-12/IL-23 p40, inhibiting Th1 and Th17 pathogenic responses"),
        ("gad_alum", "hla-antigen-presentation", "GAD-alum induces GAD65-specific immune tolerance by modulating antigen presentation"),
        ("anti_thymocyte_globulin", "tcell-insulitis", "ATG depletes effector T cells with relative Treg sparing, altering the Teff/Treg balance"),
    ]
    for src, tgt, desc in modulates:
        if src in dids and tgt in pids:
            rels.append({"source": src, "target": tgt, "type": "MODULATES", "description": desc})

    return rels


def build_ssc_relationships(existing_genes, existing_drugs, existing_pathways):
    gids = {g["id"] for g in existing_genes}
    dids = {d["id"] for d in existing_drugs}
    pids = {p["id"] for p in existing_pathways}
    dn = DISEASE_NAMES["ssc"]
    rels = []

    # ASSOCIATED_WITH
    for g in SSC_NEW_GENES:
        if g["id"] in gids:
            rels.append({"source": g["id"], "target": dn, "type": "ASSOCIATED_WITH",
                         "description": f"{g['name']} ({g['chromosome']}): {g['ssc_evidence']}"})

    # PARTICIPATES_IN
    gene_pathway_map = {
        "TYK2": [("il6-jak-stat", "TYK2 mediates IL-12/IL-23 and type I IFN signaling in SSc"),
                 ("innate-immune-tlr", "TYK2 mediates IFN responses downstream of TLR activation in SSc")],
        "TLR7": [("innate-immune-tlr", "TLR7 overexpressed in SSc skin; sustains IFN-driven fibrosis via DAMP sensing")],
        "IL6": [("il6-jak-stat", "IL-6 is markedly elevated in SSc; drives STAT3-mediated inflammation and fibrosis"),
                ("tgfb-fibrosis-ssc", "IL-6 synergizes with TGF-β to promote fibroblast activation and collagen production")],
        "CTGF": [("tgfbeta-fibrosis", "CTGF is overexpressed in SSc fibroblasts and enhances TGF-β-driven fibrosis"),
                 ("tgfb-fibrosis-ssc", "CTGF is a key downstream mediator of TGF-β profibrotic signaling")],
        "SERPINE1": [("tgfb-fibrosis-ssc", "PAI-1 is elevated in SSc and inhibits matrix degradation, promoting fibrosis")],
        "SMAD3": [("tgfbeta-fibrosis", "SMAD3 is constitutively phosphorylated in SSc fibroblasts, driving collagen transcription"),
                  ("tgfb-fibrosis-ssc", "SMAD3 is the central mediator of TGF-β-induced collagen production in SSc")],
        "COL1A1": [("tgfbeta-fibrosis", "Collagen type I is massively overexpressed in SSc skin and lung fibrosis"),
                   ("tgfb-fibrosis-ssc", "COL1A1 is the hallmark ECM component of SSc fibrosis")],
        "CTLA4": [("tcell-autoimmunity", "CTLA4 is the key T cell checkpoint; abatacept in clinical trials for SSc")],
        "FOXP3": [("tcell-autoimmunity", "Treg dysfunction documented in SSc; FOXP3+ Treg deficiency contributes to autoimmunity")],
    }
    for gid, pw_list in gene_pathway_map.items():
        if gid in gids:
            for pid, desc in pw_list:
                if pid in pids:
                    rels.append({"source": gid, "target": pid, "type": "PARTICIPATES_IN", "description": desc})

    # DRIVES
    pathway_drives = {
        "tgfb-fibrosis-ssc": "TGF-β is the master profibrotic pathway driving myofibroblast differentiation and collagen deposition in SSc",
        "vascular-endothelin-ssc": "Endothelin-1 driven vasculopathy causes PAH, digital ulcers, and Raynaud's phenomenon in SSc",
    }
    for pid, desc in pathway_drives.items():
        if pid in pids:
            rels.append({"source": pid, "target": dn, "type": "DRIVES", "description": desc})

    # MODULATES
    modulates = [
        ("nintedanib", "tgfbeta-fibrosis", "Nintedanib inhibits PDGFR/FGFR/VEGFR, suppressing fibroblast activation and fibrosis"),
        ("nintedanib", "tgfb-fibrosis-ssc", "Nintedanib blocks PDGFR/FGFR/VEGFR, interrupting TGF-β-driven myofibroblast fibrosis"),
        ("tocilizumab", "il6-jak-stat", "Tocilizumab blocks IL-6R, inhibiting JAK-STAT3-mediated inflammation and fibrosis"),
        ("rituximab", "bcell-dysregulation", "Rituximab depletes CD20+ B cells, reducing autoantibody production in SSc"),
        ("bosentan", "endothelin-vasculopathy", "Bosentan blocks ETA/ETB, reducing endothelin-1 mediated vasoconstriction and vascular remodeling"),
        ("bosentan", "vascular-endothelin-ssc", "Bosentan blocks ETA/ETB endothelin receptors, treating SSc-PAH and digital ulcers"),
        ("riociguat", "endothelin-vasculopathy", "Riociguat stimulates sGC, increasing cGMP and promoting pulmonary vasodilation in SSc-PAH"),
        ("riociguat", "vascular-endothelin-ssc", "Riociguat stimulates soluble guanylate cyclase, enhancing NO-mediated vasodilation in SSc"),
        ("belimumab", "bcell-dysregulation", "Belimumab neutralizes BAFF, reducing survival of autoreactive B cells in SSc"),
        ("methotrexate", "innate-immune-tlr", "Methotrexate exerts anti-inflammatory effects partially through adenosine-mediated NF-κB suppression"),
        ("prednisone", "innate-immune-tlr", "Prednisone broadly suppresses NF-κB-driven inflammatory gene transcription in SSc"),
        ("mycophenolate", "tcell-autoimmunity", "Mycophenolate suppresses T and B lymphocyte proliferation, reducing autoimmune responses in SSc"),
    ]
    for src, tgt, desc in modulates:
        if src in dids and tgt in pids:
            rels.append({"source": src, "target": tgt, "type": "MODULATES", "description": desc})

    return rels


def build_ms_relationships(existing_genes, existing_drugs, existing_pathways):
    gids = {g["id"] for g in existing_genes}
    dids = {d["id"] for d in existing_drugs}
    pids = {p["id"] for p in existing_pathways}
    dn = DISEASE_NAMES["ms"]
    rels = []

    # ASSOCIATED_WITH
    for g in MS_NEW_GENES:
        if g["id"] in gids:
            rels.append({"source": g["id"], "target": dn, "type": "ASSOCIATED_WITH",
                         "description": f"{g['name']} ({g['chromosome']}): {g['ms_evidence']}"})

    # PARTICIPATES_IN
    gene_pathway_map = {
        "TYK2": [("type1-ifn-ms", "TYK2 mediates type I IFN and IL-12/IL-23 signaling; critical for CNS autoimmunity"),
                 ("th17-axis-ms", "TYK2 mediates IL-23 receptor signaling critical for Th17 maintenance in MS")],
        "MBP": [("th17-axis-ms", "MBP is the prototype MS autoantigen; MBP-specific T cells drive CNS autoimmunity")],
        "MOG": [("th17-axis-ms", "Anti-MOG defines MOGAD spectrum overlapping MS; MOG is a key myelin autoantigen")],
        "IL23R": [("th17-axis-ms", "IL23R R381Q protective variant reduces IL-23 signaling; strong MS GWAS hit"),
                  ("th17-il23-ms", "IL-23R is the receptor for IL-23; protective R381Q variant reduces Th17 pathogenicity")],
        "CD4": [("th17-axis-ms", "CD4+ T cells are primary drivers of CNS inflammation in MS; Th1/Th17 polarization"),
                ("integrin-adhesion-ms", "CD4+ T cells require integrin-mediated adhesion for BBB transmigration into CNS")],
        "CD8A": [("integrin-adhesion-ms", "CD8+ T cells dominate MS lesion infiltrates and require BBB transmigration")],
        "JAK1": [("type1-ifn-ms", "JAK1 mediates multiple MS-relevant cytokine signals through JAK-STAT pathways"),
                 ("th17-il23-ms", "JAK1 transduces signals for IL-6 and type I IFN in Th17 differentiation")],
    }
    for gid, pw_list in gene_pathway_map.items():
        if gid in gids:
            for pid, desc in pw_list:
                if pid in pids:
                    rels.append({"source": gid, "target": pid, "type": "PARTICIPATES_IN", "description": desc})

    # DRIVES
    pathway_drives = {
        "th17-il23-ms": "Th17 cells produce IL-17, GM-CSF, and IL-22, disrupting BBB and promoting neuroinflammation in MS",
        "bbb-trafficking-ms": "VLA-4/VCAM-1-mediated lymphocyte adhesion and transmigration across the BBB is critical for MS lesion formation",
    }
    for pid, desc in pathway_drives.items():
        if pid in pids:
            rels.append({"source": pid, "target": dn, "type": "DRIVES", "description": desc})

    # MODULATES
    modulates = [
        ("ocrelizumab", "bcell-depletion-ms", "Ocrelizumab depletes CD20+ B cells, reducing antigen presentation and CNS-compartmentalized inflammation"),
        ("natalizumab", "integrin-adhesion-ms", "Natalizumab blocks α4-integrin (VLA-4), preventing lymphocyte BBB transmigration into CNS"),
        ("natalizumab", "bbb-trafficking-ms", "Natalizumab directly blocks VLA-4/VCAM-1 interaction, preventing immune cell BBB crossing"),
        ("ofatumumab", "bcell-depletion-ms", "Ofatumumab is a fully human anti-CD20 antibody depleting B cells in MS"),
        ("interferon_beta", "type1-ifn-ms", "IFN-β binds IFNAR1/IFNAR2, shifting cytokine balance from Th1/Th17 toward Th2/IL-10"),
        ("dimethyl_fumarate", "nfkb-nrf2-ms", "Dimethyl fumarate activates NRF2 antioxidant pathway and suppresses NF-κB-driven inflammation"),
        ("fingolimod", "s1p-modulation", "Fingolimod modulates S1P receptors, sequestering lymphocytes in lymph nodes"),
        ("evobrutinib", "btk-signaling-ms", "Evobrutinib is a CNS-penetrant BTK inhibitor targeting BCR and microglial signaling"),
        ("methylprednisolone", "nfkb-nrf2-ms", "Methylprednisolone broadly suppresses NF-κB-mediated CNS inflammation in acute relapses"),
        ("cladribine", "bcell-depletion-ms", "Cladribine is an immune reconstitution therapy selectively depleting lymphocytes"),
        ("teriflunomide", "th17-axis-ms", "Teriflunomide inhibits DHODH, reducing proliferation of activated pathogenic T and B cells"),
    ]
    for src, tgt, desc in modulates:
        if src in dids and tgt in pids:
            rels.append({"source": src, "target": tgt, "type": "MODULATES", "description": desc})

    return rels


def build_ibd_relationships(existing_genes, existing_drugs, existing_pathways):
    gids = {g["id"] for g in existing_genes}
    dids = {d["id"] for d in existing_drugs}
    pids = {p["id"] for p in existing_pathways}
    dn = DISEASE_NAMES["ibd"]
    rels = []

    # ASSOCIATED_WITH
    for g in IBD_NEW_GENES:
        if g["id"] in gids:
            rels.append({"source": g["id"], "target": dn, "type": "ASSOCIATED_WITH",
                         "description": f"{g['name']} ({g['chromosome']}): {g['ibd_evidence']}"})

    # PARTICIPATES_IN
    gene_pathway_map = {
        "TYK2": [("il23-th17-axis", "TYK2 mediates IL-23 receptor signaling critical for Th17 pathogenicity"),
                 ("jak-stat-cytokine", "TYK2 is a JAK family kinase mediating type I IFN, IL-12, and IL-23 signaling")],
        "NOD2": [("epithelial-barrier-autophagy", "NOD2 senses bacterial MDP and recruits ATG16L1; strongest CD genetic risk factor"),
                 ("epithelial-autophagy-ibd", "NOD2 is the strongest CD risk gene; impaired bacterial sensing leads to chronic inflammation")],
        "ATG16L1": [("epithelial-barrier-autophagy", "ATG16L1 T300A variant impairs autophagy and Paneth cell function"),
                    ("epithelial-autophagy-ibd", "ATG16L1 is essential for autophagosome formation; T300A variant impairs Paneth cells")],
        "IL23R": [("il23-th17-axis", "IL23R R381Q protective variant reduces IL-23 signaling; strongest protective IBD allele"),
                  ("il23-th17-mucosal-ibd", "IL-23R is the receptor for IL-23; R381Q is the strongest protective IBD allele (OR 0.3)")],
        "IL17A": [("il23-th17-axis", "IL-17A is the signature Th17 cytokine; elevated in IBD mucosa with complex roles"),
                  ("il23-th17-mucosal-ibd", "IL-17A is elevated in IBD mucosa; complex protective/pathogenic roles")],
    }
    for gid, pw_list in gene_pathway_map.items():
        if gid in gids:
            for pid, desc in pw_list:
                if pid in pids:
                    rels.append({"source": gid, "target": pid, "type": "PARTICIPATES_IN", "description": desc})

    # DRIVES
    pathway_drives = {
        "il23-th17-mucosal-ibd": "The IL-23/Th17 axis is the dominant pathogenic pathway in IBD, driving mucosal inflammation with strong GWAS support",
        "epithelial-autophagy-ibd": "Impaired autophagy and epithelial barrier function leads to microbial dysbiosis and chronic innate immune activation in IBD",
    }
    for pid, desc in pathway_drives.items():
        if pid in pids:
            rels.append({"source": pid, "target": dn, "type": "DRIVES", "description": desc})

    # MODULATES
    modulates = [
        ("infliximab", "tnf-alpha-signaling", "Infliximab neutralizes TNF-α, blocking TNFR1/TNFR2-mediated intestinal inflammation"),
        ("adalimumab", "tnf-alpha-signaling", "Adalimumab binds TNF-α, reducing NF-κB-driven mucosal inflammation in IBD"),
        ("vedolizumab", "leukocyte-trafficking", "Vedolizumab selectively blocks α4β7-MAdCAM-1, preventing gut-homing lymphocyte trafficking"),
        ("ustekinumab", "il23-th17-axis", "Ustekinumab blocks IL-12/IL-23 p40, inhibiting both Th1 and Th17 pathways in IBD"),
        ("ustekinumab", "il23-th17-mucosal-ibd", "Ustekinumab targets the shared p40 subunit of IL-12/IL-23, the dominant IBD pathogenic axis"),
        ("risankizumab", "il23-th17-axis", "Risankizumab selectively blocks IL-23 p19, inhibiting Th17/ILC3 responses in IBD"),
        ("risankizumab", "il23-th17-mucosal-ibd", "Risankizumab is a selective IL-23 inhibitor; first p19 inhibitor for IBD"),
        ("tofacitinib", "jak-stat-cytokine", "Tofacitinib inhibits JAK1/JAK3, broadly blocking multiple cytokine signals in UC"),
        ("upadacitinib", "jak-stat-cytokine", "Upadacitinib is a selective JAK1 inhibitor blocking IL-6/IFN signaling in IBD"),
        ("prednisone", "tnf-alpha-signaling", "Prednisone broadly suppresses NF-κB and AP-1 inflammatory gene transcription in the gut"),
        ("mesalamine", "tnf-alpha-signaling", "Mesalamine activates PPAR-γ and inhibits NF-κB, providing topical anti-inflammatory effects in the colonic mucosa"),
        ("azathioprine", "jak-stat-cytokine", "Azathioprine suppresses lymphocyte proliferation, reducing JAK-STAT-dependent immune cell activation"),
    ]
    for src, tgt, desc in modulates:
        if src in dids and tgt in pids:
            rels.append({"source": src, "target": tgt, "type": "MODULATES", "description": desc})

    return rels


def build_ra_modulates(existing_genes, existing_drugs, existing_pathways):
    dids = {d["id"] for d in existing_drugs}
    pids = {p["id"] for p in existing_pathways}
    rels = []

    modulates = [
        ("adalimumab", "tnf-signaling", "Adalimumab neutralizes TNF-α, blocking the dominant inflammatory pathway in RA synovium"),
        ("etanercept", "tnf-signaling", "Etanercept acts as a soluble TNFR2-Fc decoy receptor neutralizing TNF-α in RA"),
        ("infliximab", "tnf-signaling", "Infliximab binds and neutralizes TNF-α, blocking synovial inflammation in RA"),
        ("tocilizumab", "il6-jak-stat", "Tocilizumab blocks IL-6R, inhibiting JAK-STAT3-mediated inflammation and pannus formation"),
        ("sarilumab", "il6-jak-stat", "Sarilumab is a fully human anti-IL-6Rα antibody suppressing IL-6 signaling in RA"),
        ("tofacitinib", "il6-jak-stat", "Tofacitinib inhibits JAK1/JAK3, broadly blocking IL-6 and type I IFN signaling in RA"),
        ("baricitinib", "il6-jak-stat", "Baricitinib inhibits JAK1/JAK2, suppressing IL-6 and GM-CSF signaling in RA"),
        ("upadacitinib", "il6-jak-stat", "Upadacitinib is a selective JAK1 inhibitor blocking IL-6 and IFN signaling in RA"),
        ("abatacept", "tcell-costim", "Abatacept (CTLA4-Ig) blocks CD28-mediated T cell costimulation in RA"),
        ("rituximab", "bcell-autoantibody", "Rituximab depletes CD20+ B cells, reducing autoantibody production in RA"),
        ("hydroxychloroquine", "nfkb", "Hydroxychloroquine inhibits TLR7/9 activation, indirectly reducing NF-κB-mediated inflammation"),
        ("prednisone", "nfkb", "Prednisone activates GR leading to transrepression of NF-κB and AP-1 inflammatory gene programs"),
        ("sulfasalazine", "nfkb", "Sulfasalazine inhibits NF-κB and scavenges reactive oxygen species in RA synovium"),
        ("denosumab", "bone-erosion", "Denosumab binds RANKL, preventing RANK-RANKL interaction and inhibiting osteoclast-mediated bone erosion"),
        ("methotrexate", "nfkb", "Methotrexate leads to adenosine accumulation with anti-inflammatory effects via NF-κB suppression"),
        ("leflunomide", "tcell-costim", "Leflunomide inhibits DHODH, selectively reducing activated T lymphocyte proliferation"),
    ]
    for src, tgt, desc in modulates:
        if src in dids and tgt in pids:
            rels.append({"source": src, "target": tgt, "type": "MODULATES", "description": desc})

    return rels


# ─── MAIN ────────────────────────────────────────────────────────────
def main():
    for disease_id in ["ss", "t1d", "ssc", "ms", "ibd", "ra"]:
        before = get_counts(disease_id)
        print(f"\n{'='*60}")
        print(f"Processing: {disease_id.upper()} ({DISEASE_NAMES[disease_id]})")
        print(f"  Before: {before[0]} genes, {before[1]} drugs, {before[2]} pathways, {before[3]} relationships")

        # ── Load existing ──
        genes_data = load_json(disease_id, "genes.json")
        drugs_data = load_json(disease_id, "drugs.json")
        pathways_data = load_json(disease_id, "pathways.json")
        rels_data = load_json(disease_id, "relationships.json")

        existing_gene_ids = {g["id"] for g in genes_data["genes"]}
        existing_drug_ids = {d["id"] for d in drugs_data["drugs"]}
        existing_pathway_ids = {p["id"] for p in pathways_data["pathways"]}

        modified = False

        # ── Add new genes ──
        if disease_id in NEW_GENES:
            added = 0
            for g in NEW_GENES[disease_id]:
                if g["id"] not in existing_gene_ids:
                    genes_data["genes"].append(g)
                    existing_gene_ids.add(g["id"])
                    added += 1
            if added:
                modified = True
                print(f"  Added {added} genes")

        # ── Add new drugs ──
        if disease_id in NEW_DRUGS:
            added = 0
            for d in NEW_DRUGS[disease_id]:
                if d["id"] not in existing_drug_ids:
                    drugs_data["drugs"].append(d)
                    existing_drug_ids.add(d["id"])
                    added += 1
            if added:
                modified = True
                print(f"  Added {added} drugs")

        # ── Add new pathways ──
        if disease_id in NEW_PATHWAYS:
            added = 0
            for p in NEW_PATHWAYS[disease_id]:
                if p["id"] not in existing_pathway_ids:
                    pathways_data["pathways"].append(p)
                    existing_pathway_ids.add(p["id"])
                    added += 1
            if added:
                modified = True
                print(f"  Added {added} pathways")

        # ── Build and add new relationships ──
        new_rels = []
        if disease_id == "ss":
            new_rels = build_ss_relationships(genes_data["genes"], drugs_data["drugs"], pathways_data["pathways"])
        elif disease_id == "t1d":
            new_rels = build_t1d_relationships(genes_data["genes"], drugs_data["drugs"], pathways_data["pathways"])
        elif disease_id == "ssc":
            new_rels = build_ssc_relationships(genes_data["genes"], drugs_data["drugs"], pathways_data["pathways"])
        elif disease_id == "ms":
            new_rels = build_ms_relationships(genes_data["genes"], drugs_data["drugs"], pathways_data["pathways"])
        elif disease_id == "ibd":
            new_rels = build_ibd_relationships(genes_data["genes"], drugs_data["drugs"], pathways_data["pathways"])
        elif disease_id == "ra":
            new_rels = build_ra_modulates(genes_data["genes"], drugs_data["drugs"], pathways_data["pathways"])

        # Deduplicate relationships
        existing_rel_keys = set()
        for r in rels_data["relationships"]:
            existing_rel_keys.add((r["source"], r["target"], r["type"]))

        added_rels = 0
        for r in new_rels:
            key = (r["source"], r["target"], r["type"])
            if key not in existing_rel_keys:
                rels_data["relationships"].append(r)
                existing_rel_keys.add(key)
                added_rels += 1

        if added_rels:
            modified = True
            print(f"  Added {added_rels} relationships")

        # ── Save ──
        if modified:
            save_json(disease_id, "genes.json", genes_data)
            save_json(disease_id, "drugs.json", drugs_data)
            save_json(disease_id, "pathways.json", pathways_data)
            save_json(disease_id, "relationships.json", rels_data)
            after = get_counts(disease_id)
            print(f"  After:  {after[0]} genes, {after[1]} drugs, {after[2]} pathways, {after[3]} relationships")
            print(f"  CHANGED!")
        else:
            print(f"  No changes needed")

    print(f"\n{'='*60}")
    print("EXPANSION COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
