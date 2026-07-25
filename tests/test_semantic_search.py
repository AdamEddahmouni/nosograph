"""
Tests for the Semantic Search module (Phase 16).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))  # noqa: I001

from semantic_search.engine import CHROMADB_AVAILABLE, ST_AVAILABLE, SemanticSearchEngine

# ---- Dependency checks ----

def test_chromadb_available():
    """Verify ChromaDB is installed."""
    assert CHROMADB_AVAILABLE, "chromadb required: pip install chromadb"


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

    monkeypatch.setattr("semantic_search.engine.PUBMED_CACHE", tmp_path / "pubmed_cache.json")
    test_articles = [
        {"pmid": "123", "title": "Test Article", "abstract": "Test abstract text", "year": "2024", "journal": "Test J"},
    ]
    (tmp_path / "pubmed_cache.json").write_text(json.dumps(test_articles))

    engine = SemanticSearchEngine()
    articles = engine.load_articles()
    assert len(articles) == 1
    assert articles[0]["pmid"] == "123"


def test_load_articles_missing_cache():
    engine = SemanticSearchEngine()
    # Mock PUBMED_CACHE to non-existent path
    import semantic_search.engine as e
    original = e.PUBMED_CACHE
    e.PUBMED_CACHE = Path("/nonexistent/cache.json")
    try:
        articles = engine.load_articles()
        assert articles == []
    finally:
        e.PUBMED_CACHE = original


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
    monkeypatch.setattr("semantic_search.engine.PUBMED_CACHE", cache_path)
    monkeypatch.setattr("semantic_search.engine.CHROMA_DIR", tmp_path / "chroma")

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
    from semantic_search.report import escape_html
    assert escape_html("<script>") == "&lt;script&gt;"
    assert escape_html(None) == ""


@pytest.mark.slow
def test_generate_semantic_report():
    from semantic_search.report import generate_semantic_report

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
def test_run_semantic_search_empty_collection():
    """Search without indexed collection returns empty results."""
    import semantic_search.engine as e
    original = e.CHROMA_DIR
    e.CHROMA_DIR = Path("/nonexistent/semantic_chroma_test")
    try:
        from web_api.services.semantic_service import run_semantic_search
        result = run_semantic_search("lupus treatment", top_k=5)
        assert result["query"] == "lupus treatment"
        assert result["total_results"] == 0
    finally:
        e.CHROMA_DIR = original


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
