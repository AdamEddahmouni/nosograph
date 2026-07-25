"""
Unit tests for the Lupus Clinical Trial Tracker.

Tests cover:
  - tracker.py: trial parsing, MoA categorization, phase ordering,
    KG entity loading, cross-referencing, stats computation
"""

import pytest

# ── Sample fixtures ───────────────────────────────────────────────────

@pytest.fixture
def sample_raw_trial():
    """A realistic ClinicalTrials.gov API response snippet."""
    return {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT00000001"},
            "statusModule": {
                "overallStatus": "RECRUITING",
                "whyStopped": "",
            },
            "descriptionModule": {
                "briefTitle": "Study of Belimumab in SLE",
                "briefSummary": "A Phase 3 trial of belimumab for systemic lupus erythematosus.",
            },
            "designModule": {
                "phases": ["PHASE3"],
                "enrollmentInfo": {"count": 500},
            },
            "armsInterventionsModule": {
                "interventions": [
                    {"name": "Belimumab", "type": "DRUG"},
                    {"name": "Placebo", "type": "DRUG"},
                ]
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "GSK", "class": "INDUSTRY"}
            },
            "conditionsModule": {
                "conditions": ["Systemic Lupus Erythematosus"]
            },
        }
    }


@pytest.fixture
def sample_raw_trial_phase2():
    """A Phase 2 trial with JAK inhibitor."""
    return {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT00000002"},
            "statusModule": {"overallStatus": "COMPLETED", "whyStopped": ""},
            "descriptionModule": {
                "briefTitle": "Baricitinib for SLE",
                "briefSummary": "Phase 2 trial of baricitinib JAK inhibitor.",
            },
            "designModule": {
                "phases": ["PHASE2"],
                "enrollmentInfo": {"count": 300},
            },
            "armsInterventionsModule": {
                "interventions": [
                    {"name": "Baricitinib", "type": "DRUG"},
                ]
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Eli Lilly", "class": "INDUSTRY"}
            },
            "conditionsModule": {
                "conditions": ["Systemic Lupus Erythematosus"]
            },
        }
    }


@pytest.fixture
def sample_parsed_trial():
    """A pre-parsed trial dict."""
    return {
        "nct_id": "NCT00000001",
        "title": "Study of Belimumab in SLE",
        "summary": "A Phase 3 trial of belimumab.",
        "status": "RECRUITING",
        "phases": ["PHASE3"],
        "primary_phase": "PHASE3",
        "phase_label": "Phase 3",
        "interventions": ["Belimumab", "Placebo"],
        "intervention_types": ["DRUG", "DRUG"],
        "sponsor_name": "GSK",
        "sponsor_class": "INDUSTRY",
        "enrollment": 500,
        "start_date": "",
        "completion_date": "",
        "why_stopped": "",
        "conditions": ["Systemic Lupus Erythematosus"],
    }


@pytest.fixture
def sample_kg_entities():
    """Minimal KG entities for testing."""
    return {
        "genes": {
            "BTK": {
                "id": "BTK",
                "name": "Bruton Tyrosine Kinase",
                "category": "B Cell Signaling",
            },
            "JAK1": {
                "id": "JAK1",
                "name": "Janus Kinase 1",
                "category": "JAK-STAT Signaling",
            },
            "BAFF": {
                "id": "BAFF",
                "name": "B Cell Activating Factor",
                "category": "B Cell Survival",
            },
        },
        "drugs": {
            "belimumab": {
                "id": "belimumab",
                "name": "Belimumab (Benlysta)",
                "target": "BAFF (BLyS)",
                "category": "Biologic - B Cell Modulation",
            },
            "baricitinib": {
                "id": "baricitinib",
                "name": "Baricitinib (Olumiant)",
                "target": "JAK1/JAK2",
                "category": "Targeted Synthetic - JAK Inhibitor",
            },
        },
    }


# ═══════════════════════════════════════════════════════════════════════
#  parse_trial tests
# ═══════════════════════════════════════════════════════════════════════

class TestParseTrial:
    """Tests for parse_trial()."""

    def test_parses_nct_id(self, sample_raw_trial):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        result = parse_trial(sample_raw_trial)
        assert result["nct_id"] == "NCT00000001"

    def test_parses_title(self, sample_raw_trial):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        result = parse_trial(sample_raw_trial)
        assert "Belimumab" in result["title"]

    def test_parses_status(self, sample_raw_trial):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        result = parse_trial(sample_raw_trial)
        assert result["status"] == "RECRUITING"

    def test_parses_phases(self, sample_raw_trial):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        result = parse_trial(sample_raw_trial)
        assert "PHASE3" in result["phases"]
        assert result["primary_phase"] == "PHASE3"
        assert result["phase_label"] == "Phase 3"

    def test_parses_interventions(self, sample_raw_trial):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        result = parse_trial(sample_raw_trial)
        assert "Belimumab" in result["interventions"]
        assert "DRUG" in result["intervention_types"]

    def test_parses_sponsor(self, sample_raw_trial):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        result = parse_trial(sample_raw_trial)
        assert result["sponsor_name"] == "GSK"
        assert result["sponsor_class"] == "INDUSTRY"

    def test_parses_enrollment(self, sample_raw_trial):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        result = parse_trial(sample_raw_trial)
        assert result["enrollment"] == 500

    def test_parses_conditions(self, sample_raw_trial):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        result = parse_trial(sample_raw_trial)
        assert "Systemic Lupus Erythematosus" in result["conditions"]

    def test_summary_truncated_to_500_chars(self):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        long_summary = {"protocolSection": {
            "identificationModule": {"nctId": "NCT"},
            "statusModule": {"overallStatus": "COMPLETED"},
            "descriptionModule": {
                "briefTitle": "Test",
                "briefSummary": "X" * 1000,
            },
            "designModule": {"phases": [], "enrollmentInfo": {}},
            "armsInterventionsModule": {"interventions": []},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "", "class": ""}},
            "conditionsModule": {"conditions": []},
        }}
        result = parse_trial(long_summary)
        assert len(result["summary"]) <= 500

    def test_empty_phases_handled(self):
        from med_research.pipeline.clinical_trials.tracker import parse_trial
        trial = {"protocolSection": {
            "identificationModule": {"nctId": "NCT"},
            "statusModule": {"overallStatus": "COMPLETED"},
            "descriptionModule": {"briefTitle": "Test", "briefSummary": ""},
            "designModule": {"phases": [], "enrollmentInfo": {}},
            "armsInterventionsModule": {"interventions": []},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "", "class": ""}},
            "conditionsModule": {"conditions": []},
        }}
        result = parse_trial(trial)
        assert result["phases"] == []
        assert result["primary_phase"] == ""


# ═══════════════════════════════════════════════════════════════════════
#  categorize_moa tests
# ═══════════════════════════════════════════════════════════════════════

class TestCategorizeMoa:
    """Tests for categorize_moa()."""

    def test_b_cell_targeting(self):
        from med_research.pipeline.clinical_trials.tracker import categorize_moa
        trial = {"title": "Anti-CD20 B cell depletion study", "interventions": ["Rituximab"], "summary": ""}
        assert categorize_moa(trial) == "B Cell Targeting"

    def test_jak_stat_inhibitor(self):
        from med_research.pipeline.clinical_trials.tracker import categorize_moa
        trial = {"title": "JAK inhibitor trial for SLE", "interventions": ["Tofacitinib"], "summary": ""}
        assert categorize_moa(trial) == "Type I IFN / JAK-STAT"

    def test_interferon_targeting(self):
        from med_research.pipeline.clinical_trials.tracker import categorize_moa
        trial = {"title": "Anti-IFNAR therapy", "interventions": ["Anifrolumab"], "summary": ""}
        assert categorize_moa(trial) == "Type I IFN / JAK-STAT"

    def test_complement_inhibitor(self):
        from med_research.pipeline.clinical_trials.tracker import categorize_moa
        trial = {"title": "Complement C5 inhibition", "interventions": ["Eculizumab"], "summary": ""}
        assert categorize_moa(trial) == "Complement"

    def test_car_t_cell_therapy(self):
        from med_research.pipeline.clinical_trials.tracker import categorize_moa
        trial = {"title": "CAR-T cell therapy for refractory lupus", "interventions": ["Anti-CD19 CAR-T"], "summary": ""}
        assert categorize_moa(trial) == "Cell Therapy"

    def test_cytokine_targeting(self):
        from med_research.pipeline.clinical_trials.tracker import categorize_moa
        trial = {"title": "IL-6 receptor blockade in SLE", "interventions": ["Tocilizumab"], "summary": ""}
        assert categorize_moa(trial) == "Cytokine / Chemokine"

    def test_t_cell_costimulation(self):
        from med_research.pipeline.clinical_trials.tracker import categorize_moa
        trial = {"title": "CD40 blockade in lupus", "interventions": ["Dapirolizumab"], "summary": ""}
        assert categorize_moa(trial) == "T Cell / Costimulation"

    def test_falls_back_to_other(self):
        from med_research.pipeline.clinical_trials.tracker import categorize_moa
        trial = {"title": "Unknown novel therapy", "interventions": ["Mystery Drug"], "summary": ""}
        assert categorize_moa(trial) == "Other Targeted"

    def test_matches_on_summary_when_title_empty(self):
        from med_research.pipeline.clinical_trials.tracker import categorize_moa
        trial = {"title": "Unknown therapy", "interventions": [], "summary": "Inhibiting complement C5a receptor reduces inflammation"}
        assert categorize_moa(trial) == "Complement"


# ═══════════════════════════════════════════════════════════════════════
#  phase ordering tests
# ═══════════════════════════════════════════════════════════════════════

class TestPrimaryPhase:
    """Tests for _primary_phase()."""

    def test_picks_highest_phase(self):
        from med_research.pipeline.clinical_trials.tracker import _primary_phase
        assert _primary_phase(["PHASE1", "PHASE2", "PHASE3"]) == "PHASE3"

    def test_handles_empty_list(self):
        from med_research.pipeline.clinical_trials.tracker import _primary_phase
        assert _primary_phase([]) == ""

    def test_single_phase(self):
        from med_research.pipeline.clinical_trials.tracker import _primary_phase
        assert _primary_phase(["PHASE2"]) == "PHASE2"

    def test_early_phase1_lower_than_phase1(self):
        from med_research.pipeline.clinical_trials.tracker import _primary_phase
        assert _primary_phase(["EARLY_PHASE1", "PHASE1"]) == "PHASE1"

    def test_phase4_highest(self):
        from med_research.pipeline.clinical_trials.tracker import _primary_phase
        assert _primary_phase(["PHASE1", "PHASE4", "PHASE2"]) == "PHASE4"


# ═══════════════════════════════════════════════════════════════════════
#  cross-referencing tests
# ═══════════════════════════════════════════════════════════════════════

class TestCrossReference:
    """Tests for cross_reference_trials()."""

    def test_matches_gene_by_id(self, sample_kg_entities):
        from med_research.pipeline.clinical_trials.tracker import cross_reference_trials
        trials = [{
            "title": "BTK inhibitor study",
            "interventions": ["Ibrutinib"],
            "summary": "Targeting BTK in lupus",
        }]
        results = cross_reference_trials(trials, sample_kg_entities)
        assert results[0]["kg_matches"]["gene_count"] >= 1
        matched_genes = [g["gene_id"] for g in results[0]["kg_matches"]["genes"]]
        assert "BTK" in matched_genes

    def test_matches_drug_by_name(self, sample_kg_entities):
        from med_research.pipeline.clinical_trials.tracker import cross_reference_trials
        trials = [{
            "title": "Belimumab trial",
            "interventions": ["Belimumab"],
            "summary": "BAFF blockade in SLE",
        }]
        results = cross_reference_trials(trials, sample_kg_entities)
        assert results[0]["kg_matches"]["drug_count"] >= 1
        matched_drugs = [d["drug_id"] for d in results[0]["kg_matches"]["drugs"]]
        assert "belimumab" in matched_drugs

    def test_no_match_returns_empty(self, sample_kg_entities):
        from med_research.pipeline.clinical_trials.tracker import cross_reference_trials
        trials = [{
            "title": "Completely unrelated study",
            "interventions": ["Sugar pill"],
            "summary": "Nothing to do with lupus genes",
        }]
        results = cross_reference_trials(trials, sample_kg_entities)
        assert not results[0]["kg_matches"]["has_match"]
        assert results[0]["kg_matches"]["gene_count"] == 0
        assert results[0]["kg_matches"]["drug_count"] == 0

    def test_has_match_flag(self, sample_kg_entities):
        from med_research.pipeline.clinical_trials.tracker import cross_reference_trials
        trials = [
            {"title": "BTK study", "interventions": ["Ibrutinib"], "summary": ""},
            {"title": "No match", "interventions": [], "summary": ""},
        ]
        results = cross_reference_trials(trials, sample_kg_entities)
        assert results[0]["kg_matches"]["has_match"]
        assert not results[1]["kg_matches"]["has_match"]


# ═══════════════════════════════════════════════════════════════════════
#  stats computation tests
# ═══════════════════════════════════════════════════════════════════════

class TestComputeStats:
    """Tests for _compute_stats()."""

    def test_counts_total_trials(self):
        from med_research.pipeline.clinical_trials.tracker import _compute_stats
        trials = [
            {"nct_id": "NCT1", "status": "RECRUITING", "phases": ["PHASE2"],
             "moa_category": "B Cell Targeting", "sponsor_name": "Sponsor A",
             "enrollment": 100, "kg_matches": {"has_match": True}},
            {"nct_id": "NCT2", "status": "COMPLETED", "phases": ["PHASE3"],
             "moa_category": "Type I IFN / JAK-STAT", "sponsor_name": "Sponsor B",
             "enrollment": 200, "kg_matches": {"has_match": False}},
        ]
        stats = _compute_stats(trials)
        assert stats["total_trials"] == 2

    def test_counts_statuses(self):
        from med_research.pipeline.clinical_trials.tracker import _compute_stats
        trials = [
            {"nct_id": "NCT1", "status": "RECRUITING", "phases": [], "moa_category": "X",
             "sponsor_name": "A", "enrollment": 0, "kg_matches": {"has_match": False}},
            {"nct_id": "NCT2", "status": "RECRUITING", "phases": [], "moa_category": "X",
             "sponsor_name": "A", "enrollment": 0, "kg_matches": {"has_match": False}},
            {"nct_id": "NCT3", "status": "COMPLETED", "phases": [], "moa_category": "X",
             "sponsor_name": "B", "enrollment": 0, "kg_matches": {"has_match": False}},
        ]
        stats = _compute_stats(trials)
        assert stats["statuses"]["RECRUITING"] == 2
        assert stats["statuses"]["COMPLETED"] == 1

    def test_counts_moas(self):
        from med_research.pipeline.clinical_trials.tracker import _compute_stats
        trials = [
            {"nct_id": "NCT1", "status": "RECRUITING", "phases": [], "moa_category": "B Cell Targeting",
             "sponsor_name": "A", "enrollment": 0, "kg_matches": {"has_match": False}},
            {"nct_id": "NCT2", "status": "RECRUITING", "phases": [], "moa_category": "B Cell Targeting",
             "sponsor_name": "A", "enrollment": 0, "kg_matches": {"has_match": False}},
        ]
        stats = _compute_stats(trials)
        assert stats["moas"]["B Cell Targeting"] == 2

    def test_computes_enrollment_stats(self):
        from med_research.pipeline.clinical_trials.tracker import _compute_stats
        trials = [
            {"nct_id": "NCT1", "status": "R", "phases": [], "moa_category": "X",
             "sponsor_name": "A", "enrollment": 100, "kg_matches": {"has_match": False}},
            {"nct_id": "NCT2", "status": "R", "phases": [], "moa_category": "X",
             "sponsor_name": "A", "enrollment": 200, "kg_matches": {"has_match": False}},
        ]
        stats = _compute_stats(trials)
        assert stats["total_enrollment"] == 300
        assert stats["avg_enrollment"] == 150

    def test_counts_kg_matched(self):
        from med_research.pipeline.clinical_trials.tracker import _compute_stats
        trials = [
            {"nct_id": "NCT1", "status": "R", "phases": [], "moa_category": "X",
             "sponsor_name": "A", "enrollment": 0, "kg_matches": {"has_match": True}},
            {"nct_id": "NCT2", "status": "R", "phases": [], "moa_category": "X",
             "sponsor_name": "A", "enrollment": 0, "kg_matches": {"has_match": False}},
        ]
        stats = _compute_stats(trials)
        assert stats["kg_matched_trials"] == 1


# ═══════════════════════════════════════════════════════════════════════
#  KG entity loading tests
# ═══════════════════════════════════════════════════════════════════════

class TestLoadKgEntities:
    """Tests for load_kg_entities()."""

    def test_loads_from_real_kg_files(self):
        from med_research.pipeline.clinical_trials.tracker import load_kg_entities
        entities = load_kg_entities()
        assert isinstance(entities, dict)
        assert "genes" in entities
        assert "drugs" in entities
        assert len(entities["genes"]) > 0
        assert len(entities["drugs"]) > 0

    def test_genes_have_expected_keys(self):
        from med_research.pipeline.clinical_trials.tracker import load_kg_entities
        entities = load_kg_entities()
        for gene_id, gene in entities["genes"].items():
            assert "name" in gene
            assert "category" in gene

    def test_drugs_have_expected_keys(self):
        from med_research.pipeline.clinical_trials.tracker import load_kg_entities
        entities = load_kg_entities()
        for drug_id, drug in entities["drugs"].items():
            assert "name" in drug
            assert "target" in drug


# ═══════════════════════════════════════════════════════════════════════
#  build crossref summary tests
# ═══════════════════════════════════════════════════════════════════════

class TestBuildCrossrefSummary:
    """Tests for _build_crossref_summary()."""

    def test_counts_gene_hits(self):
        from med_research.pipeline.clinical_trials.tracker import _build_crossref_summary
        trials = [
            {"nct_id": "NCT1", "title": "BTK study", "phase_label": "Phase 2",
             "status": "R", "kg_matches": {"has_match": True, "gene_count": 1, "drug_count": 0,
             "genes": [{"gene_id": "BTK"}], "drugs": []}, "moa_category": "X"},
            {"nct_id": "NCT2", "title": "BTK-JAK study", "phase_label": "Phase 2",
             "status": "R", "kg_matches": {"has_match": True, "gene_count": 2, "drug_count": 0,
             "genes": [{"gene_id": "BTK"}, {"gene_id": "JAK1"}], "drugs": []}, "moa_category": "X"},
        ]
        result = _build_crossref_summary(trials)
        assert result["gene_hits"]["BTK"] == 2
        assert result["gene_hits"]["JAK1"] == 1

    def test_counts_matched_trials(self):
        from med_research.pipeline.clinical_trials.tracker import _build_crossref_summary
        trials = [
            {"nct_id": "NCT1", "title": "Match", "phase_label": "Phase 2",
             "status": "R", "kg_matches": {"has_match": True, "gene_count": 1, "drug_count": 0,
             "genes": [{"gene_id": "BTK"}], "drugs": []}, "moa_category": "X"},
            {"nct_id": "NCT2", "title": "No match", "phase_label": "Phase 2",
             "status": "R", "kg_matches": {"has_match": False, "gene_count": 0, "drug_count": 0,
             "genes": [], "drugs": []}, "moa_category": "X"},
        ]
        result = _build_crossref_summary(trials)
        assert result["total_matched"] == 1
        assert len(result["trials_with_matches"]) == 1


# ═══════════════════════════════════════════════════════════════════════
#  report generation tests
# ═══════════════════════════════════════════════════════════════════════

class TestGenerateReport:
    """Tests for generate_ct_report()."""

    def test_generates_html_file(self, tmp_path):
        from med_research.pipeline.clinical_trials.report import generate_ct_report

        results = {
            "trials": [{
                "nct_id": "NCT00000001",
                "title": "Belimumab Trial",
                "summary": "A trial of belimumab",
                "status": "RECRUITING",
                "phases": ["PHASE3"],
                "primary_phase": "PHASE3",
                "phase_label": "Phase 3",
                "interventions": ["Belimumab"],
                "intervention_types": ["DRUG"],
                "sponsor_name": "GSK",
                "sponsor_class": "INDUSTRY",
                "enrollment": 500,
                "start_date": "2024-01-01",
                "completion_date": "2026-01-01",
                "why_stopped": "",
                "conditions": ["SLE"],
                "moa_category": "B Cell Targeting",
                "kg_matches": {
                    "has_match": True,
                    "gene_count": 2,
                    "drug_count": 1,
                    "genes": [{"gene_id": "BAFF", "gene_name": "BAFF", "category": "B Cell Survival"}],
                    "drugs": [{"drug_id": "belimumab", "drug_name": "Belimumab", "target": "BAFF", "category": "Biologic"}],
                },
            }],
            "stats": {
                "total_trials": 1,
                "kg_matched_trials": 1,
                "total_enrollment": 500,
                "avg_enrollment": 500,
                "statuses": {"RECRUITING": 1},
                "phases": {"Phase 3": 1},
                "moas": {"B Cell Targeting": 1},
                "top_sponsors": {"GSK": 1},
            },
            "kg_crossref": {
                "gene_hits": {"BAFF": 1},
                "drug_hits": {"belimumab": 1},
                "trials_with_matches": [{
                    "nct_id": "NCT00000001",
                    "title": "Belimumab Trial",
                    "phase": "Phase 3",
                    "status": "RECRUITING",
                    "gene_count": 2,
                    "drug_count": 1,
                    "genes": ["BAFF"],
                    "drugs": ["belimumab"],
                    "moa": "B Cell Targeting",
                }],
                "total_matched": 1,
            },
        }

        # Monkey-patch output path
        import med_research.pipeline.clinical_trials.report as ct_report
        original_path = ct_report.Path(__file__).parent if hasattr(ct_report.Path, '__call__') else ct_report.Path
        report_path = generate_ct_report(results)
        assert report_path.endswith("ct_report.html")

    def test_report_contains_expected_sections(self, tmp_path):
        from med_research.pipeline.clinical_trials.report import generate_ct_report

        results = {
            "trials": [{
                "nct_id": "NCT00000001",
                "title": "Belimumab Trial",
                "summary": "A trial of belimumab",
                "status": "RECRUITING",
                "phases": ["PHASE3"],
                "primary_phase": "PHASE3",
                "phase_label": "Phase 3",
                "interventions": ["Belimumab"],
                "intervention_types": ["DRUG"],
                "sponsor_name": "GSK",
                "sponsor_class": "INDUSTRY",
                "enrollment": 500,
                "start_date": "",
                "completion_date": "",
                "why_stopped": "",
                "conditions": ["SLE"],
                "moa_category": "B Cell Targeting",
                "kg_matches": {
                    "has_match": True, "gene_count": 2, "drug_count": 1,
                    "genes": [{"gene_id": "BAFF", "gene_name": "BAFF", "category": "B Cell Survival"}],
                    "drugs": [{"drug_id": "belimumab", "drug_name": "Belimumab", "target": "BAFF", "category": "Biologic"}],
                },
            }],
            "stats": {
                "total_trials": 1, "kg_matched_trials": 1, "total_enrollment": 500,
                "avg_enrollment": 500, "statuses": {"RECRUITING": 1},
                "phases": {"Phase 3": 1}, "moas": {"B Cell Targeting": 1},
                "top_sponsors": {"GSK": 1},
            },
            "kg_crossref": {
                "gene_hits": {"BAFF": 1}, "drug_hits": {"belimumab": 1},
                "trials_with_matches": [{"nct_id": "NCT00000001", "title": "Test", "phase": "Phase 3",
                 "status": "R", "gene_count": 1, "drug_count": 1, "genes": ["BAFF"],
                 "drugs": ["belimumab"], "moa": "B Cell"}],
                "total_matched": 1,
            },
        }

        report_path = generate_ct_report(results)
        html = open(report_path, encoding="utf-8").read()

        assert "Clinical Trial Tracker" in html
        assert "Phase Distribution" in html
        assert "KG-Cross-Referenced" in html
        assert "NCT00000001" in html
        assert "Belimumab" in html


# ═══════════════════════════════════════════════════════════════════════
#  escape_html tests
# ═══════════════════════════════════════════════════════════════════════

class TestEscapeHtml:
    """Tests for _escape_html in report.py."""

    def test_escapes_angle_brackets(self):
        from med_research.pipeline.clinical_trials.report import _escape_html
        assert "&lt;script&gt;" in _escape_html("<script>")

    def test_escapes_ampersand(self):
        from med_research.pipeline.clinical_trials.report import _escape_html
        assert "&amp;" in _escape_html("A & B")

    def test_empty_string_returns_empty(self):
        from med_research.pipeline.clinical_trials.report import _escape_html
        assert _escape_html("") == ""

    def test_none_returns_empty(self):
        from med_research.pipeline.clinical_trials.report import _escape_html
        assert _escape_html(None) == ""


# ═══════════════════════════════════════════════════════════════════════
#  hex_to_rgba tests
# ═══════════════════════════════════════════════════════════════════════

class TestHexToRgba:
    """Tests for _hex_to_rgba in report.py."""

    def test_converts_color(self):
        from med_research.pipeline.clinical_trials.report import _hex_to_rgba
        assert _hex_to_rgba("#4ade80") == "74,222,128,0.15"

    def test_returns_default_for_short(self):
        from med_research.pipeline.clinical_trials.report import _hex_to_rgba
        result = _hex_to_rgba("#fff")
        assert "120,120,144" in result

    def test_returns_default_for_empty(self):
        from med_research.pipeline.clinical_trials.report import _hex_to_rgba
        result = _hex_to_rgba("")
        assert "120,120,144" in result


