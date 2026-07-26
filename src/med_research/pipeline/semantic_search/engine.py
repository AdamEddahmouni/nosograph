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
import json
from pathlib import Path

from med_research.logging_config import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent / "data"
CHROMA_DIR = Path("data/chroma/semantic")
PUBMED_CACHE = Path("literature_mining/data/pubmed_cache.json")

# ---- Optional dependencies with graceful fallback ----

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False


def _check_deps():
    """Check and report missing dependencies."""
    missing = []
    if not CHROMADB_AVAILABLE:
        missing.append("chromadb (pip install chromadb)")
    if not ST_AVAILABLE:
        missing.append("sentence-transformers (pip install sentence-transformers)")
    if missing:
        logger.error("Missing dependencies: %s", ', '.join(missing))
        return False
    return True


# ---- ChromaDB Indexing ----

class SemanticSearchEngine:
    """Embedding-based semantic search over PubMed abstracts."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.client = None
        self.collection = None
        self._articles = []

    def _ensure_deps(self):
        if not _check_deps():
            raise ImportError("Install missing dependencies listed above.")

    def _load_model(self):
        if self.model is None:
            logger.info("Loading embedding model: %s ...", self.model_name)
            self.model = SentenceTransformer(self.model_name)
            logger.info("   Model loaded (%s-dim embeddings)", self.model.get_sentence_embedding_dimension())

    def _ensure_collection(self):
        if self.collection is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            # Delete existing collection on re-index to avoid duplicates
            try:
                self.client.delete_collection("pubmed_abstracts")
            except Exception:
                pass
            self.collection = self.client.create_collection(
                name="pubmed_abstracts",
                metadata={"description": "PubMed abstracts for SLE/lupus research"},
            )

    def load_articles(self) -> list:
        """Load cached PubMed articles."""
        if not PUBMED_CACHE.exists():
            logger.warning("No PubMed cache found at %s", PUBMED_CACHE)
            logger.info("Run: python literature_mining/miner.py first")
            return []

        articles = json.loads(PUBMED_CACHE.read_text(encoding="utf-8"))
        logger.info("Loaded %d cached articles", len(articles))
        self._articles = articles
        return articles

    def index_articles(self, articles: list = None, batch_size: int = 50) -> int:
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

        logger.info("Indexing %d articles in batches of %d ...", len(articles), batch_size)
        total = 0

        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            texts = [(a.get("title", "") or "") + " " + (a.get("abstract", "") or "") for a in batch]
            ids = [a.get("pmid", f"art_{i+j}") for j, a in enumerate(batch)]
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
            logger.info("   [%d/%d] indexed", total, len(articles))

        logger.info("Done — %d articles indexed into %s", total, CHROMA_DIR)
        return total

    def search(self, query: str, top_k: int = 20) -> list:
        """Semantic search for articles matching the query."""
        self._ensure_deps()
        self._load_model()

        # Load existing collection (don't recreate)
        if self.collection is None:
            self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            try:
                self.collection = self.client.get_collection("pubmed_abstracts")
            except Exception:
                logger.warning("No indexed collection found. Run --index first.")
                return []

        query_embedding = self.model.encode(query).tolist()
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
        )

        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results["distances"] else 0
                # Convert distance to similarity score (cosine distance → 0-10 scale)
                similarity = round(max(0, (1 - dist) * 10), 2)
                formatted.append({
                    "rank": i + 1,
                    "pmid": meta.get("pmid", doc_id),
                    "title": meta.get("title", "")[:200],
                    "year": meta.get("year", ""),
                    "journal": meta.get("journal", ""),
                    "similarity": similarity,
                })

        return formatted

    def get_indexed_count(self) -> int:
        """Return number of indexed articles."""
        if self.collection is None:
            self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            try:
                self.collection = self.client.get_collection("pubmed_abstracts")
            except Exception:
                return 0
        return self.collection.count()


# ---- CLI ----

def main():
    parser = argparse.ArgumentParser(
        description="Semantic Literature Search — embedding-based PubMed search"
    )
    parser.add_argument("--index", action="store_true", help="Index cached PubMed articles into vector DB")
    parser.add_argument("--query", type=str, help="Semantic search query (natural language)")
    parser.add_argument("--top", type=int, default=20, help="Number of results (default: 20)")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    engine = SemanticSearchEngine()

    if args.index:
        articles = engine.load_articles()
        if articles:
            engine.index_articles(articles)

    if args.query:
        results = engine.search(args.query, top_k=args.top)
        if results:
            logger.info("\n%s", '=' * 70)
            logger.info("\U0001f50d SEMANTIC SEARCH: \"%s\"", args.query)
            logger.info("%s", '=' * 70)
            logger.info("\n  Found %d results:\n", len(results))
            for r in results:
                logger.info("  #%-3s [%.1f] [%s] %s", str(r['rank']), r['similarity'], r['year'], r['title'][:90])
                logger.info("       %s", r.get('journal', ''))
        else:
            logger.warning("No results found. Try running --index first.")

    if args.export_html:
        from med_research.pipeline.semantic_search.report import generate_semantic_report
        query = args.query or "(all articles)"
        results = results if args.query else []
        indexed = engine.get_indexed_count()
        generate_semantic_report(results, query, indexed)
        logger.info("\n\N{WHITE HEAVY CHECK MARK} HTML report generated: semantic_search/report.html")

    return 0


if __name__ == "__main__":
    main()
