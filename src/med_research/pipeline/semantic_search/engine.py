"""
Semantic Literature Search Engine

Indexes cached PubMed articles into a ChromaDB vector store using
sentence-transformers embeddings, then enables search by meaning
instead of keyword matching.

Usage:
    python semantic_search/engine.py --index           # Index cached articles
    python semantic_search/engine.py --query "drugs that suppress interferon in lupus" --top 10
    python semantic_search/engine.py --index --export-html  # Index + report
"""

import argparse
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from med_research.diseases.coverage import ModuleCoverage
from med_research.pipeline.progress import StandardProgress, _tick, cli_progress
from med_research.pipeline.results import SemanticHit

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
CHROMA_DIR = Path("data/chroma/semantic")
# Literature-mining data dir (same layout the miner writes to)
LIT_DATA_DIR = Path(__file__).parent.parent / "literature_mining" / "data"

# ---- Optional dependencies with graceful fallback (lazy-loaded for fast startup) ----


def _is_package_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


CHROMADB_AVAILABLE = _is_package_available("chromadb")
ST_AVAILABLE = _is_package_available("sentence_transformers")
chromadb: Any = None

last_coverage = None


def _chromadb_collection_errors() -> tuple:
    """Exception types raised when a Chroma collection is missing."""
    if CHROMADB_AVAILABLE:
        try:
            from chromadb.errors import NotFoundError

            return (NotFoundError, ValueError, RuntimeError)
        except ImportError:
            pass
    return (ValueError, RuntimeError)


def resolve_semantic_coverage(disease_id: str) -> ModuleCoverage:
    """Return disease-scoped semantic search readiness including optional deps."""
    from med_research.diseases.coverage import module_coverage

    cov = module_coverage(disease_id, "semantic", ("genes", "drugs", "pubmed_queries"))
    if not cov.is_runnable:
        return cov
    warnings = list(cov.warnings)
    missing_deps: list[str] = []
    if not CHROMADB_AVAILABLE:
        missing_deps.append("chromadb")
    if not ST_AVAILABLE:
        missing_deps.append("sentence-transformers")
    if missing_deps:
        warnings.append("Optional dependencies missing: " + ", ".join(missing_deps) + ".")
        return ModuleCoverage(
            disease_id=disease_id,
            module="semantic",
            level="partial",
            status="limited_coverage",
            curated_inputs=list(cov.curated_inputs),
            warnings=warnings,
        )
    return cov


def _check_deps():
    """Check and report missing dependencies."""
    missing = []
    if not CHROMADB_AVAILABLE:
        missing.append("chromadb (pip install chromadb)")
    if not ST_AVAILABLE:
        missing.append("sentence-transformers (pip install sentence-transformers)")
    if missing:
        logger.info(f"Missing dependencies: {', '.join(missing)}")
        return False
    return True


# ---- ChromaDB Indexing ----


class SemanticSearchEngine:
    """Embedding-based semantic search over PubMed abstracts."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", disease_id: str = "sle"):
        self.model_name = model_name
        self.disease_id = disease_id
        self.model: Any = None
        self.client: Any = None
        self.collection: Any = None
        self._articles: list[Any] = []

    @property
    def collection_name(self) -> str:
        """Per-disease Chroma collection; legacy name kept for SLE."""
        if self.disease_id == "sle":
            return "pubmed_abstracts"
        return f"pubmed_abstracts_{self.disease_id}"

    def _cache_path(self) -> Path:
        """Resolve the legacy PubMed cache path for this disease."""
        from med_research.pipeline.literature_mining.miner import literature_cache_path

        return literature_cache_path(self.disease_id)

    def load_articles(self) -> list:
        """Load cached PubMed articles for the engine's disease."""
        from med_research.pipeline.literature_mining.miner import load_literature_articles

        articles = load_literature_articles(self.disease_id, use_cache=True)
        if articles is None:
            cache = self._cache_path()
            logger.info(f"No PubMed cache found at {cache}")
            logger.info("Run: python literature_mining/miner.py first")
            return []

        logger.info(f"Loaded {len(articles)} cached articles")
        self._articles = articles
        return articles

    def _ensure_deps(self):
        if not _check_deps():
            raise ImportError("Install missing dependencies listed above.")

    def _load_model(self):
        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name} ...")
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model_name)
            logger.info(
                f"   Model loaded ({self.model.get_sentence_embedding_dimension()}-dim embeddings)"
            )

    def _ensure_collection(self):
        if self.collection is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            import chromadb

            self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            # Delete existing collection on re-index to avoid duplicates
            try:
                self.client.delete_collection(self.collection_name)
            except _chromadb_collection_errors() as exc:
                logger.debug("No existing collection to delete: %s", exc)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": f"PubMed abstracts for {self.disease_id} research"},
            )

    def index_articles(
        self,
        articles: list[Any] | None = None,
        batch_size: int = 50,
        progress_callback: StandardProgress | None = None,
    ) -> int:
        """Embed and index article abstracts into ChromaDB.

        Returns number of articles indexed.
        """
        self._ensure_deps()
        self._load_model()
        self._ensure_collection()

        if articles is None:
            articles = self.load_articles()
        if not articles:
            return 0

        logger.info(f"Indexing {len(articles)} articles in batches of {batch_size} ...")
        total = 0

        for i in range(0, len(articles), batch_size):
            batch = articles[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(articles) + batch_size - 1) // batch_size
            _tick(progress_callback, "indexing articles", batch_num, total_batches)
            texts = [
                (a.get("title", "") or "") + " " + (a.get("abstract", "") or "") for a in batch
            ]
            ids = [a.get("pmid", f"art_{i + j}") for j, a in enumerate(batch)]
            metadatas = [
                {
                    "pmid": a.get("pmid", ""),
                    "title": (a.get("title", "") or "")[:200],
                    "year": a.get("year", ""),
                    "journal": a.get("journal", "")[:100],
                }
                for a in batch
            ]

            embeddings = self.model.encode(texts, show_progress_bar=False).tolist()

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=texts,
            )
            total += len(batch)
            logger.info(f"   [{total}/{len(articles)}] indexed")

        logger.info(f"Done — {total} articles indexed into {CHROMA_DIR}")
        return total

    def search(
        self,
        query: str,
        top_k: int = 20,
        progress_callback: StandardProgress | None = None,
    ) -> list[SemanticHit]:
        """Semantic search for articles matching the query."""
        global last_coverage
        last_coverage = resolve_semantic_coverage(self.disease_id)
        if not last_coverage.is_runnable:
            return []

        if not _check_deps():
            return []

        # Load existing collection (don't recreate)
        if self.collection is None:
            try:
                import chromadb
            except ImportError:
                import sys

                chromadb = getattr(sys.modules.get(__name__), "chromadb", None)
                if chromadb is None:
                    return []

            self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            try:
                self.collection = self.client.get_collection(self.collection_name)
            except _chromadb_collection_errors() as exc:
                logger.info("No indexed collection found for %s: %s", self.collection_name, exc)
                _tick(progress_callback, "semantic search", 1, 1)
                return []

        self._load_model()
        _tick(progress_callback, "semantic search", 1, 1)
        query_embedding = self.model.encode(query).tolist()
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
        )

        formatted: list[SemanticHit] = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results["distances"] else 0
                # Convert distance to similarity score (cosine distance → 0-10 scale)
                similarity = round(max(0, (1 - dist) * 10), 2)
                formatted.append(
                    {
                        "rank": i + 1,
                        "pmid": meta.get("pmid", doc_id),
                        "title": meta.get("title", "")[:200],
                        "year": meta.get("year", ""),
                        "journal": meta.get("journal", ""),
                        "similarity": similarity,
                    }
                )

        return formatted

    def get_indexed_count(self) -> int:
        """Return number of indexed articles."""
        if not CHROMADB_AVAILABLE:
            return 0
        if self.collection is None:
            import chromadb

            self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            try:
                self.collection = self.client.get_collection(self.collection_name)
            except _chromadb_collection_errors() as exc:
                logger.debug("Indexed collection unavailable for %s: %s", self.collection_name, exc)
                return 0
        return int(self.collection.count())


# ---- CLI ----


def main():
    parser = argparse.ArgumentParser(
        description="Semantic Literature Search — embedding-based PubMed search"
    )
    parser.add_argument(
        "--index", action="store_true", help="Index cached PubMed articles into vector DB"
    )
    parser.add_argument("--query", type=str, help="Semantic search query (natural language)")
    parser.add_argument("--top", type=int, default=20, help="Number of results (default: 20)")
    parser.add_argument("--disease", "-d", default="sle", help="Disease ID (default: sle)")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    engine = SemanticSearchEngine(disease_id=args.disease)
    results: list = []

    if args.index:
        articles = engine.load_articles()
        if articles:
            engine.index_articles(articles, progress_callback=cli_progress)

    if args.query:
        results = engine.search(args.query, top_k=args.top, progress_callback=cli_progress)
        if results:
            logger.info(f"\n{'=' * 70}")
            logger.info(f'🔍 SEMANTIC SEARCH: "{args.query}"')
            logger.info(f"{'=' * 70}")
            logger.info(f"\n  Found {len(results)} results:\n")
            for r in results:
                logger.info(
                    f"  #{r['rank']:<3} [{r['similarity']:.1f}] [{r['year']}] {r['title'][:90]}"
                )
                logger.info(f"       {r.get('journal', '')}")
        else:
            logger.info("No results found. Try running --index first.")

    if args.export_html:
        from med_research.pipeline.provenance import build_provenance
        from med_research.pipeline.semantic_search.report import generate_semantic_report

        query = args.query or "(all articles)"
        search_results = results if args.query else []
        indexed = engine.get_indexed_count()
        provenance = build_provenance(
            disease_id=args.disease,
            module="semantic_search",
            sources=["pubmed"],
            query=query,
            cache_or_live="cache",
        )
        generate_semantic_report(
            search_results,
            query,
            indexed,
            disease_id=args.disease,
            provenance=provenance,
        )
        logger.info("\n✅ HTML report generated: semantic_search/report.html")

    return 0


if __name__ == "__main__":
    import sys

    from med_research.cli import main as cli_main

    sys.exit(cli_main() or 0)
