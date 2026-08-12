"""
AI-Optimized Content Extraction Pipeline

Pre-processes PubMed abstracts to extract only sentences containing known
knowledge graph entities before passing them to the NER pipeline. This reduces
noise (~60% fewer tokens) and improves downstream processing speed.

Strategy: Heuristic sentence-level filtering that retains sentences mentioning
any known gene, drug, or pathway term from the knowledge graph. Falls back to
the full abstract if no sentences match (safety: never lose data).

Usage:
    from med_research.pipeline.literature_mining.content_extractor import ContentExtractor

    extractor = ContentExtractor(known_terms={"btk", "ibrutinib", "jak"})
    filtered = extractor.filter_abstract(abstract_text)
    # filtered = "Ibrutinib treated...BTK inhibition..." (kept sentences only)
"""

import re

# ── Sentence splitting ──────────────────────────────────────────────────

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _split_sentences(text: str) -> list:
    """Split text into sentences, preserving acronym-laden biomedical text.

    Uses a conservative regex that only splits on .!? followed by whitespace
    and a capital letter, avoiding false splits on:
      - Abbreviations like 'et al.', 'e.g.', 'i.e.', 'Dr.', 'vs.'
      - Decimal numbers like '5.3'
      - Uppercase acronyms at sentence boundaries (still splits correctly)
    """
    # Protect common abbreviation patterns
    protected = text
    protected = protected.replace("et al.", "et al@@")
    protected = protected.replace("e.g.", "e@g@@")
    protected = protected.replace("i.e.", "i@e@@")
    protected = protected.replace("Dr.", "Dr@@")
    protected = protected.replace("vs.", "vs@@")
    protected = protected.replace("Fig.", "Fig@@")
    protected = protected.replace("approx.", "approx@@")

    sentences = _SENTENCE_RE.split(protected)
    # Restore abbreviations
    sentences = [
        s.replace("et al@@", "et al.")
        .replace("e@g@@", "e.g.")
        .replace("i@e@@", "i.e.")
        .replace("Dr@@", "Dr.")
        .replace("vs@@", "vs.")
        .replace("Fig@@", "Fig.")
        .replace("approx@@", "approx.")
        for s in sentences
    ]
    return [s.strip() for s in sentences if s.strip()]


class ContentExtractor:
    """
    Filters abstracts to only sentences containing known KG entity terms.

    This is the "Idea E" from exa_ai_research.md — a pre-processing step that
    reduces NER input size by ~60% and cuts noise from irrelevant content
    (methods details, background citations, statistical methodology).
    """

    def __init__(self, known_terms: set[str] | None = None):
        """
        Args:
            known_terms: Set of lowercase entity terms to match against.
                         Typically built from KG genes, drugs, and pathways.
        """
        self.known_terms = known_terms or set()
        self.stats = {
            "abstracts_processed": 0,
            "total_sentences": 0,
            "kept_sentences": 0,
            "total_tokens": 0,
            "kept_tokens": 0,
            "fully_filtered": 0,
        }

    def filter_abstract(self, abstract: str) -> str:
        """Extract only sentences containing known KG entity terms.

        Args:
            abstract: Full PubMed abstract text.

        Returns:
            Filtered abstract containing only relevant sentences.
            Falls back to original text if no sentences match.
        """
        if not abstract or not self.known_terms:
            return abstract

        sentences = _split_sentences(abstract)
        if not sentences:
            return abstract

        total_tokens = len(abstract.split())
        self.stats["abstracts_processed"] += 1
        self.stats["total_sentences"] += len(sentences)
        self.stats["total_tokens"] += total_tokens

        kept = []
        for sentence in sentences:
            sent_lower = sentence.lower()
            for term in self.known_terms:
                if len(term) >= 3 and term in sent_lower:
                    kept.append(sentence)
                    break

        if not kept:
            # Safety: never discard all content — fall back to original
            self.stats["kept_sentences"] += len(sentences)
            self.stats["kept_tokens"] += total_tokens
            self.stats["fully_filtered"] += 1
            return abstract

        filtered = " ".join(kept)
        kept_tokens = len(filtered.split())
        self.stats["kept_sentences"] += len(kept)
        self.stats["kept_tokens"] += kept_tokens

        return filtered

    def filter_articles(self, articles: list) -> tuple:
        """Apply content extraction to a batch of articles.

        Args:
            articles: List of article dicts with 'abstract' and 'title' keys.

        Returns:
            (filtered_articles, stats) — articles with abstracts filtered,
            plus aggregated extraction statistics.
        """
        filtered = []
        for article in articles:
            fa = dict(article)
            original_abstract = fa.get("abstract", "")
            fa["abstract"] = self.filter_abstract(original_abstract)

            filtered.append(fa)

        return filtered, dict(self.stats)

    def build_terms_from_entities(self, entities: dict) -> set:
        """Extract search terms from KG entity dictionaries.

        Collects all gene/drug/pathway names, IDs, and synonyms into a
        flat set of lowercase terms for sentence-level filtering.

        Args:
            entities: Dict with 'genes', 'drugs', 'pathways' keys,
                      each mapping IDs to entity info dicts.

        Returns:
            Set of lowercase search terms.
        """
        terms = set()

        for entity_type in ("genes", "drugs", "pathways"):
            for entity_id, info in entities.get(entity_type, {}).items():
                # Add entity name
                name = info.get("name", "")
                if name:
                    terms.add(name.lower())

                # Add entity ID
                if entity_id:
                    terms.add(entity_id.lower())

                # Add synonyms
                for syn in info.get("synonyms", []):
                    terms.add(syn.lower())

                # Extract brand/generic names from drug names like "Ibrutinib (Imbruvica)"
                if entity_type == "drugs" and "(" in name and ")" in name:
                    brand = name.split("(")[1].split(")")[0].strip().lower()
                    generic = name.split("(")[0].strip().lower()
                    if brand:
                        terms.add(brand)
                    if generic:
                        terms.add(generic)

                # Add pathway description keywords
                if entity_type == "pathways":
                    desc = info.get("description", "")
                    if desc:
                        for word in desc.lower().split():
                            if len(word) > 4:
                                terms.add(word)

        return terms
