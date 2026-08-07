"""
Tests for the Semantic Search module (Phase 16).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))  # noqa: I001

from med_research.pipeline.semantic_search.engine import (
    CHROMADB_AVAILABLE,
    ST_AVAILABLE,
    SemanticSearchEngine,
)

# ---- Dependency checks ----

@pytest.mark.slow
@pytest.mark.skipif(not CHROMADB_AVAILABLE, reason="chromadb not installed")
def test_chromadb_available():
    """Verify ChromaDB is installed."""
    assert CHROMADB_AVAILABLE, "chromadb required: pip install chromadb"


@pytest.mark.slow
@pytest.mark.skipif(not ST_AVAILABLE, reason="sentence-transformers not installed")
def test_sentence_transformers_available():
    """Verify sentence-transformers is installed."""
    assert ST_AVAILABLE, "sentence-transformers required: pip install sentence-transformers"


# ---- Engine ----

def test_engine_initialization():
    engine = SemanticSearchEngine()
    assert engine.model_name == "all-MiniLM-L6-v2"
    assert engine.model is None
    assert engine.collection is None


def test_load_articles_uses_cache(tmp_path, monkeypatch):
    import json

    import med_research.pipeline.semantic_search.engine as engine_mod
    # SLE without a per-disease cache falls back to the legacy shared cache
    # under LIT_DATA_DIR, so point it at a temp dir and write there.
    monkeypatch.setattr(engine_mod, "LIT_DATA_DIR", tmp_path)
    test_articles = [
        {"pmid": "123", "title": "Test Article", "abstract": "Test abstract text", "year": "2024", "journal": "Test J"},
    ]
    (tmp_path / "pubmed_cache.json").write_text(json.dumps(test_articles))

    engine = SemanticSearchEngine()
    articles = engine.load_articles()
    assert len(articles) == 1
    assert articles[0]["pmid"] == "123"


def test_load_articles_missing_cache(tmp_path, monkeypatch):
    import med_research.pipeline.semantic_search.engine as engine_mod
    # Point the data dir at an empty temp dir so no cache is found
    monkeypatch.setattr(engine_mod, "LIT_DATA_DIR", tmp_path)
    engine = SemanticSearchEngine()
    articles = engine.load_articles()
    assert articles == []


# ---- Disease threading ----

def test_engine_accepts_disease_id():
    engine = SemanticSearchEngine(disease_id="ra")
    assert engine.disease_id == "ra"
    assert engine.collection_name == "pubmed_abstracts_ra"


def test_collection_name_legacy_for_sle():
    engine = SemanticSearchEngine(disease_id="sle")
    assert engine.collection_name == "pubmed_abstracts"


def test_cache_path_per_disease(tmp_path, monkeypatch):
    """Non-SLE diseases always resolve their per-disease cache."""
    import med_research.pipeline.semantic_search.engine as engine_mod

    monkeypatch.setattr(engine_mod, "LIT_DATA_DIR", tmp_path)
    # Legacy shared cache exists, but RA must NOT fall back to it
    (tmp_path / "pubmed_cache.json").write_text("[]")
    engine = SemanticSearchEngine(disease_id="ra")
    assert engine._cache_path() == tmp_path / "pubmed_cache_ra.json"


def test_cache_path_legacy_fallback_for_sle(tmp_path, monkeypatch):
    """SLE falls back to the legacy shared cache when no per-disease cache exists."""
    import med_research.pipeline.semantic_search.engine as engine_mod

    monkeypatch.setattr(engine_mod, "LIT_DATA_DIR", tmp_path)
    engine = SemanticSearchEngine(disease_id="sle")
    # Legacy cache is resolved from the same absolute LIT_DATA_DIR
    assert engine._cache_path() == tmp_path / "pubmed_cache.json"


def test_cache_path_sle_prefers_per_disease(tmp_path, monkeypatch):
    """SLE uses its per-disease cache when one exists."""
    import med_research.pipeline.semantic_search.engine as engine_mod

    monkeypatch.setattr(engine_mod, "LIT_DATA_DIR", tmp_path)
    (tmp_path / "pubmed_cache_sle.json").write_text("[]")
    legacy = tmp_path / "legacy_pubmed_cache.json"
    legacy.write_text("[]")
    monkeypatch.setattr(engine_mod, "PUBMED_CACHE", legacy)
    engine = SemanticSearchEngine(disease_id="sle")
    assert engine._cache_path() == tmp_path / "pubmed_cache_sle.json"


def test_load_articles_reads_per_disease_cache(tmp_path, monkeypatch):
    """load_articles reads the disease-specific cache file."""
    import json

    import med_research.pipeline.semantic_search.engine as engine_mod

    monkeypatch.setattr(engine_mod, "LIT_DATA_DIR", tmp_path)
    articles = [{"pmid": "9", "title": "RA article", "abstract": "RA abstract"}]
    (tmp_path / "pubmed_cache_ra.json").write_text(json.dumps(articles))

    engine = SemanticSearchEngine(disease_id="ra")
    loaded = engine.load_articles()
    assert len(loaded) == 1
    assert loaded[0]["pmid"] == "9"


def test_search_uses_per_disease_collection(tmp_path, monkeypatch):
    """search/get_indexed_count look up the disease-specific collection."""
    import types

    import med_research.pipeline.semantic_search.engine as engine_mod

    if getattr(engine_mod, "chromadb", None) is None:
        monkeypatch.setattr(engine_mod, "CHROMADB_AVAILABLE", True)

    looked_up = []

    class FakeCollection:
        def count(self):
            return 3

        def query(self, **kwargs):
            return {"ids": [[]], "metadatas": None, "distances": None}

    class FakeClient:
        def get_collection(self, name):
            looked_up.append(name)
            return FakeCollection()

    monkeypatch.setattr(
        engine_mod,
        "chromadb",
        types.SimpleNamespace(PersistentClient=lambda path: FakeClient()),
    )
    monkeypatch.setattr(engine_mod, "CHROMA_DIR", tmp_path / "chroma")
    engine = SemanticSearchEngine(disease_id="ra")
    # Avoid loading the embedding model just to verify collection lookup
    class FakeModel:
        def encode(self, text):
            return type("Vec", (), {"tolist": lambda self: [0.1] * 4})()
    engine.model = FakeModel()
    monkeypatch.setattr(SemanticSearchEngine, "_load_model", lambda self: None)
    monkeypatch.setattr(engine_mod, "_check_deps", lambda: True)
    assert engine.get_indexed_count() == 3
    assert looked_up == ["pubmed_abstracts_ra"]
    engine.collection = None
    assert engine.search("jak inhibitors", top_k=5) == []
    assert looked_up == ["pubmed_abstracts_ra", "pubmed_abstracts_ra"]


def test_run_semantic_search_accepts_disease_id(tmp_path, monkeypatch):
    """Web service passes disease_id into the engine."""
    import med_research.pipeline.semantic_search.engine as engine_mod
    from med_research.pipeline.semantic_search.engine import SemanticSearchEngine
    from med_research.web.services.semantic_service import run_semantic_search

    # Redirect Chroma to an empty temp dir so get_indexed_count() returns 0
    # without touching the real index.
    monkeypatch.setattr(engine_mod, "CHROMA_DIR", tmp_path / "chroma")

    original = SemanticSearchEngine.__init__
    captured = {}

    def fake_init(self, model_name="all-MiniLM-L6-v2", disease_id="sle"):
        captured["disease_id"] = disease_id
        self.model_name = model_name
        self.disease_id = disease_id
        self.model = None
        self.client = None
        self.collection = None
        self._articles = []

    SemanticSearchEngine.__init__ = fake_init
    try:
        run_semantic_search("btk inhibitors", top_k=3, disease_id="ibd")
        assert captured["disease_id"] == "ibd"
    finally:
        SemanticSearchEngine.__init__ = original


# ---- Index & Search (requires sentence-transformers + chromadb) ----

@pytest.mark.slow
def test_index_and_search(tmp_path, monkeypatch):
    """Full pipeline: index a few test articles, then search."""
    import json

    # Prepare test articles
    test_articles = [
        {"pmid": "1", "title": "JAK inhibition in lupus nephritis",
         "abstract": "Baricitinib reduced proteinuria and anti-dsDNA in SLE patients.", "year": "2024", "journal": "NEJM"},
        {"pmid": "2", "title": "B cell depletion with rituximab",
         "abstract": "Rituximab improved renal outcomes in refractory lupus nephritis.", "year": "2023", "journal": "Lancet"},
        {"pmid": "3", "title": "Vitamin D supplementation in elderly",
         "abstract": "Vitamin D did not reduce fracture risk in nursing home residents.", "year": "2022", "journal": "BMJ"},
    ]

    cache_path = tmp_path / "pubmed_cache.json"
    cache_path.write_text(json.dumps(test_articles))
    monkeypatch.setattr("med_research.pipeline.semantic_search.engine.LIT_DATA_DIR", tmp_path)
    monkeypatch.setattr("med_research.pipeline.semantic_search.engine.CHROMA_DIR", tmp_path / "chroma")

    engine = SemanticSearchEngine()
    articles = engine.load_articles()
    assert len(articles) == 3

    # Index
    count = engine.index_articles(articles)
    assert count == 3

    # Search — should find lupus-relevant articles, not vitamin D
    results = engine.search("lupus treatment", top_k=3)
    assert len(results) >= 2
    # Article #1 (JAK/lupus) should rank higher than #3 (vitamin D)
    titles = [r["title"] for r in results]
    assert any("JAK" in t for t in titles)
    assert any("rituximab" in t for t in titles)
    # Vitamin D article should be last
    if "Vitamin D" in titles:
        assert titles.index([t for t in titles if "Vitamin D" in t][0]) == len(titles) - 1 or any(
            r["similarity"] < results[0]["similarity"] * 0.5 for r in results if "Vitamin D" in r["title"]
        )


# ---- Report ----

def test_escape_html_semantic():
    from med_research.pipeline.semantic_search.report import escape_html
    assert escape_html("<script>") == "&lt;script&gt;"
    assert escape_html(None) == ""


@pytest.mark.slow
def test_generate_semantic_report():
    from med_research.pipeline.semantic_search.report import generate_semantic_report

    results = [
        {"rank": 1, "pmid": "123", "title": "JAK inhibition in SLE", "year": "2024",
         "journal": "NEJM", "similarity": 9.2},
    ]
    path = generate_semantic_report(results, "lupus treatment", 150)
    assert "report.html" in path
    assert Path(path).exists()
    Path(path).unlink(missing_ok=True)


# ---- API Service ----

@pytest.mark.slow
def test_run_semantic_search_empty_collection(tmp_path, monkeypatch):
    """Search without indexed collection returns empty results."""
    import med_research.pipeline.semantic_search.engine as engine_mod
    # Patch the module the service actually imports (the top-level
    # `semantic_search.engine` alias is a separate module object).
    monkeypatch.setattr(engine_mod, "CHROMA_DIR", tmp_path / "no_index")
    from med_research.web.services.semantic_service import run_semantic_search
    result = run_semantic_search("lupus treatment", top_k=5)
    assert result["query"] == "lupus treatment"
    assert result["total_results"] == 0


# ---- CLI ----

@pytest.mark.slow
def test_semantic_cli_help():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "semantic", "--help"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "semantic" in result.stdout.lower()
