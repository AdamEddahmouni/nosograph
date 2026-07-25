"""
Biomedical Named Entity Recognition (NER) — spaCy + Regex Hybrid

Provides a unified entity extraction interface that:
  1. Always uses dictionary-based matching against KG entities (fast, no deps)
  2. Optionally layers spaCy/scispacy biomedical NER on top (if installed)
  3. Falls back to regex-based biomedical patterns when spaCy isn't available

The dictionary matching in crossref.py is the primary approach since it's
domain-tuned. This module catches entities NOT in the dictionary — novel
targets, off-label drug uses, emerging disease associations.

Usage:
    from literature_mining.ner import BiomedicalNER

    ner = BiomedicalNER()
    novel = ner.extract_novel_entities("abstract text here...", known_set)
    # novel = {"chemicals": [...], "diseases": [...], "genes": [...]}
"""

import re

# ── Lazy spaCy import ────────────────────────────────────────────────────

SPACY_AVAILABLE = False
_spacy_nlp = None
_spacy_is_biomedical = False


def _try_load_spacy():
    """Try to load spaCy with a biomedical model. Returns True if a model loaded."""
    global SPACY_AVAILABLE, _spacy_nlp, _spacy_is_biomedical

    if _spacy_nlp is not None:
        return SPACY_AVAILABLE

    try:
        import spacy

        # Try biomedical models first (scispacy)
        for model_name in [
            "en_ner_bc5cdr_md",      # BioCreative V CDR model
            "en_core_sci_sm",          # scispacy small
            "en_core_sci_md",          # scispacy medium
            "en_ner_craft_md",         # CRAFT model
            "en_ner_jnlpba_md",        # JNLPBA model
        ]:
            try:
                _spacy_nlp = spacy.load(model_name)
                SPACY_AVAILABLE = True
                _spacy_is_biomedical = True
                return True
            except OSError:
                continue

        # Generic model as last resort (no biomedical labels, but still useful for ORG/GPE)
        try:
            _spacy_nlp = spacy.load("en_core_web_sm")
            SPACY_AVAILABLE = True
            _spacy_is_biomedical = False
            return True
        except OSError:
            pass

    except ImportError:
        pass

    SPACY_AVAILABLE = False
    return False


# ── Biomedical entity labels (spaCy) ────────────────────────────────────

BIOMEDICAL_LABELS = {
    "CHEMICAL": "chemicals",
    "DISEASE": "diseases",
    "GENE": "genes",
    "DNA": "genes",
    "RNA": "genes",
    "CELL_LINE": "cell_lines",
    "CELL_TYPE": "cell_types",
    "PROTEIN": "genes",
}

GENERIC_LABELS = {
    "ORG": "organizations",
    "GPE": "locations",
}


# ── Regex-based biomedical patterns (fallback) ──────────────────────────

# Gene symbol pattern: uppercase letters + optional numbers (BTK, TYK2, STAT4)
# Also catches CD markers (CD20, CD11b), interleukins (IL-6, IL-12), and IFN types
_GENE_PATTERN = re.compile(
    r'\b(?:[A-Z]{2,}[0-9]*[A-Z]*(?:\.[0-9]+)?'          # BTK, TYK2, STAT4, IRF5
    r'|CD[0-9]+[a-z]?'                                     # CD20, CD11b
    r'|IL-[0-9]+[A-Za-z]*'                                 # IL-6, IL-12, IL-23
    r'|IFN-[αβγ][A-Za-z]*'                                 # IFN-α, IFN-β
    r'|TNF-?[αβ]?'                                         # TNF-α, TNF
    r'|TLR[0-9]+'                                          # TLR7, TLR9
    r'|NF-?κB'                                             # NF-κB
    r'|[A-Z][a-z]{2,}(?:\s+(?:kinase|receptor|factor|ligand|phosphatase|channel|transporter))'  # Bruton tyrosine kinase
    r')(?!\w)'  # use (?!\w) instead of \b for Greek letter support
)

# Drug-like terms: therapeutic suffixes and known drug naming patterns
_DRUG_PATTERN = re.compile(
    r'\b(?:[A-Z][a-z]+(?:mab|nib|cept|mide|stat|zole|pril|sartan|oxin|mycin|cycline|floxacin|vir|asone|olone|profen|azosin|dipine|tidine|prazole|gliptin|gliflozin|parib|lisib|sertib|citinib)'
    r'|[A-Z][a-z]+(?: monoclonal antibody| inhibitor| antagonist| agonist| modulator)'
    r')\b'
)

# Disease mentions: condition suffixes, lupus-specific, autoimmune patterns
_DISEASE_PATTERN = re.compile(
    r'\b(?:[A-Z][a-z]+(?:itis|osis|emia|opathy|plasia|penia|cytosis|sclerosis)'
    r'|lupus(?:\s+nephritis)?'
    r'|nephritis'
    r'|vasculitis'
    r'|arthritis'
    r'|scleroderma'
    r'|Sjögren\'s(?:\s+syndrome)?'
    r'|myositis'
    r'|(?:autoimmune|chronic|systemic|refractory|severe)\s+[a-z]+'
    r'|[a-z]+\s+(?:syndrome|disease|disorder|failure)'
    r')\b',
    re.IGNORECASE,
)

# Chemical compound patterns
_CHEMICAL_PATTERN = re.compile(
    r'\b(?:[A-Z][a-z]+(?:ic acid|ate|ide|one|ol|ine|ium|ase|ogen|phin|phan|mide|zone|zole|tide|zine|mine|dine|pine|phine|done|sone|sterol)'
    r'|hydroxy[a-z]+'
    r'|[A-Z][a-z]+ interferon'
    r')\b'
)


class BiomedicalNER:
    """
    Biomedical NER using regex patterns (always) + spaCy (if biomedical model available).

    The dictionary-based matching in crossref.py is the primary approach.
    This class provides a secondary layer that catches entities NOT in
    the knowledge graph dictionary.

    Regex patterns always run — no model downloads needed.
    spaCy biomedical models (scispacy/BC5CDR) layer on top if installed.
    """

    def __init__(self):
        self.spacy_available = _try_load_spacy()

    def extract_novel_entities(
        self, text: str, known_entities: set = None
    ) -> dict:
        """
        Extract biomedical entities from text that are NOT in the known set.

        Always runs regex patterns first. If a biomedical spaCy model is
        available, merges its results on top.

        Returns dict with keys: chemicals, diseases, genes
        """
        if known_entities is None:
            known_entities = set()

        # Always run regex as base
        results = self._extract_regex(text, known_entities)

        # Layer spaCy on top if a biomedical model is available
        if self.spacy_available and _spacy_is_biomedical and _spacy_nlp is not None:
            spacy_results = self._extract_spacy(text, known_entities)
            results = self._merge_results(results, spacy_results)

        return results

    def _merge_results(self, base: dict, overlay: dict) -> dict:
        """Merge spaCy results into regex results, avoiding duplicates."""
        merged = dict(base)
        for key, values in overlay.items():
            existing = set(v.lower() for v in merged.get(key, []))
            new = [v for v in values if v.lower() not in existing]
            if new:
                merged.setdefault(key, []).extend(new)
                # Keep sorted by position (approximation: keep existing order)
                seen = set()
                unique = []
                for item in merged[key]:
                    if item.lower() not in seen:
                        seen.add(item.lower())
                        unique.append(item)
                merged[key] = unique[:30]  # Allow more with spaCy
        return merged

    def _extract_spacy(self, text: str, known_entities: set) -> dict:
        """Extract entities using spaCy biomedical model."""
        try:
            doc = _spacy_nlp(text[:10000])
        except Exception:
            return {}

        results = {}

        for ent in doc.ents:
            label = ent.label_
            if label in BIOMEDICAL_LABELS:
                key = BIOMEDICAL_LABELS[label]
            elif label in GENERIC_LABELS:
                key = GENERIC_LABELS[label]
            else:
                continue

            entity_text = ent.text.strip().lower()
            if len(entity_text) < 4 or entity_text in known_entities:
                continue

            results.setdefault(key, []).append(
                {"text": ent.text.strip(), "label": label, "start": ent.start_char}
            )

        return self._deduplicate_results(results)

    def _extract_regex(self, text: str, known_entities: set) -> dict:
        """Extract entities using regex biomedical patterns."""
        results = {}

        # Extract genes
        for match in _GENE_PATTERN.finditer(text):
            entity = match.group().strip()
            lower = entity.lower()
            if len(lower) >= 3 and lower not in known_entities:
                results.setdefault("genes", []).append(
                    {"text": entity, "label": "GENE", "start": match.start()}
                )

        # Extract drugs
        for match in _DRUG_PATTERN.finditer(text):
            entity = match.group().strip()
            lower = entity.lower()
            if len(lower) >= 4 and lower not in known_entities:
                results.setdefault("chemicals", []).append(
                    {"text": entity, "label": "CHEMICAL", "start": match.start()}
                )

        # Extract diseases
        for match in _DISEASE_PATTERN.finditer(text):
            entity = match.group().strip()
            lower = entity.lower()
            if len(lower) >= 4 and lower not in known_entities:
                results.setdefault("diseases", []).append(
                    {"text": entity, "label": "DISEASE", "start": match.start()}
                )

        # Extract chemicals
        for match in _CHEMICAL_PATTERN.finditer(text):
            entity = match.group().strip()
            lower = entity.lower()
            if len(lower) >= 4 and lower not in known_entities:
                # Avoid double-counting entities already caught as drugs
                if "chemicals" in results:
                    already = {e["text"].lower() for e in results["chemicals"]}
                    if lower in already:
                        continue
                results.setdefault("chemicals", []).append(
                    {"text": entity, "label": "CHEMICAL", "start": match.start()}
                )

        return self._deduplicate_results(results)

    def _deduplicate_results(self, results: dict) -> dict:
        """Deduplicate and sort extracted entities by position."""
        cleaned = {}
        for key, items in results.items():
            seen = set()
            unique = []
            for item in items:
                lower = item["text"].lower()
                if lower not in seen:
                    seen.add(lower)
                    unique.append(item)
            unique.sort(key=lambda x: x["start"])
            cleaned[key] = [u["text"] for u in unique[:20]]
        return cleaned

    def get_installation_hint(self) -> str:
        """Return installation instructions for spaCy biomedical NER."""
        if self.spacy_available and _spacy_is_biomedical:
            return "[scispacy] Biomedical NER is active (BC5CDR/scispacy model loaded)."
        elif self.spacy_available:
            return "[spacy] Generic model loaded -- regex NER provides biomedical coverage."

        return (
            "[regex] Regex-based biomedical NER is active (no model downloads needed).\n"
            "  Install spaCy + scispacy for enhanced precision:\n"
            "    pip install spacy scispacy\n"
            "    pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/"
            "releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz\n"
            "  Or use a BioCreative model:\n"
            "    pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/"
            "releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz"
        )
