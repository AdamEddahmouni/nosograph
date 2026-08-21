"""Clinical Trials parsing utilities for the Matching Engine.

The implementation focuses on the public ClinicalTrials.gov bulk XML download.
It provides:
* ``ClinicalTrialsDownloader`` – fetches and extracts the XML archive.
* ``Trial`` – a simple SQLAlchemy model storing trial metadata and parsed criteria.
* ``TrialCriteriaParser`` – parses the free‑text inclusion/exclusion sections into
  structured rule dictionaries that can be consumed by the eligibility engine.

For the MVP we keep the parser lightweight and demonstrate extraction of age
ranges, biomarker thresholds, and organ‑function limits using regular
expressions.  The parser can be extended with more sophisticated NLP in the
future.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree  # type: ignore

from dataclasses import dataclass, field

try:
    from sqlalchemy import Column, Integer, String, Text, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    HAS_SQLALCHEMY = True
    Base = declarative_base()
except ImportError:
    HAS_SQLALCHEMY = False
    Base = object  # type: ignore

if HAS_SQLALCHEMY:

    class Trial(Base):  # type: ignore
        """SQLAlchemy model representing a ClinicalTrials.gov study."""

        __tablename__ = "trials"

        id = Column(Integer, primary_key=True, autoincrement=True)
        nct_id = Column(String, unique=True, nullable=False, index=True)
        title = Column(String, nullable=False)
        brief_summary = Column(Text)
        detailed_description = Column(Text)
        inclusion_criteria = Column(Text)
        exclusion_criteria = Column(Text)
        inclusion_rules = Column(Text)
        exclusion_rules = Column(Text)
        phase = Column(String, default="")
        status = Column(String, default="")

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def __repr__(self) -> str:
            return f"<Trial {self.nct_id!r}: {self.title!r}>"
else:

    @dataclass
    class Trial:  # type: ignore
        """Lightweight representation of a ClinicalTrials.gov study."""

        nct_id: str
        title: str
        brief_summary: str = ""
        detailed_description: str = ""
        inclusion_criteria: str = ""
        exclusion_criteria: str = ""
        inclusion_rules: any = field(default_factory=list)
        exclusion_rules: any = field(default_factory=list)
        phase: str = ""
        status: str = ""
        id: Optional[int] = None


class ClinicalTrialsDownloader:
    """Download and extract the ClinicalTrials.gov XML bulk archive.

    The public bulk download URL is:
    ``https://clinicaltrials.gov/api/query/full_studies?format=xml``
    but a large zipped snapshot is available at:
    ``https://clinicaltrials.gov/AllPublicXML.zip``.
    For the prototype we simply download the zip and extract the ``FullStudies``
    directory.
    """

    DEFAULT_URL = "https://clinicaltrials.gov/AllPublicXML.zip"

    def __init__(self, dest_dir: Path | str = Path("data/clinical_trials")):
        self.dest_dir = Path(dest_dir)
        self.dest_dir.mkdir(parents=True, exist_ok=True)

    def download(self, url: str | None = None) -> Path:
        url = url or self.DEFAULT_URL
        local_zip = self.dest_dir / "AllPublicXML.zip"
        # Stream download to avoid loading whole file into memory.
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(local_zip, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        # Extract
        with zipfile.ZipFile(local_zip, "r") as zip_ref:
            zip_ref.extractall(self.dest_dir)
        return self.dest_dir


class TrialCriteriaParser:
    """Parse inclusion/exclusion criteria text into simple rule dictionaries.

    The parser currently extracts the following rule types (if present):
    * Age range – e.g. "Age 18 to 65 Years"
    * Biomarker thresholds – e.g. "EGFR >= 10%"
    * Organ function limits – e.g. "Creatinine <= 1.5 mg/dL"

    Each rule is represented as a dict::

        {"type": "age", "min": 18, "max": 65}
        {"type": "biomarker", "name": "EGFR", "operator": ">=", "value": 10}
        {"type": "organ", "name": "creatinine", "operator": "<=", "value": 1.5}

    The list of rule dicts is stored as JSON in the ``Trial`` model.
    """

    AGE_RE = re.compile(
        r"age\s*(?:between|\d+\s*to|\d+-\d+)?\s*(\d{1,3})\s*(?:to|-)\s*(\d{1,3})", re.I
    )
    BIO_RE = re.compile(r"([A-Za-z0-9_]+)\s*(>=|<=|=|>|<)\s*([0-9.]+)\s*%?", re.I)
    ORG_RE = re.compile(
        r"(creatinine|bilirubin|alt|ast)\s*(>=|<=|=|>|<)\s*([0-9.]+)\s*(mg/dl|units?)", re.I
    )

    def _parse_section(self, text: str) -> List[Dict]:
        rules: List[Dict] = []
        # Age
        for m in self.AGE_RE.finditer(text):
            rules.append({"type": "age", "min": int(m.group(1)), "max": int(m.group(2))})
        # Biomarkers
        for m in self.BIO_RE.finditer(text):
            rules.append(
                {
                    "type": "biomarker",
                    "name": m.group(1).upper(),
                    "operator": m.group(2),
                    "value": float(m.group(3)),
                }
            )
        # Organ function
        for m in self.ORG_RE.finditer(text):
            rules.append(
                {
                    "type": "organ",
                    "name": m.group(1).lower(),
                    "operator": m.group(2),
                    "value": float(m.group(3)),
                }
            )
        return rules

    def parse(self, trial_xml: etree._Element) -> Tuple[List[Dict], List[Dict]]:
        """Extract inclusion and exclusion rule lists from a ``FullStudy`` element.

        Returns ``(inclusion_rules, exclusion_rules)``.
        """
        # Locate the criteria nodes – the XML schema uses ``EligibilityCriteria``
        # with sub‑elements ``InclusionCriteria`` and ``ExclusionCriteria``.
        inc_node = trial_xml.find(".//EligibilityCriteria/InclusionCriteria")
        exc_node = trial_xml.find(".//EligibilityCriteria/ExclusionCriteria")
        inc_text = inc_node.text if inc_node is not None else ""
        exc_text = exc_node.text if exc_node is not None else ""
        inc_rules = self._parse_section(inc_text or "")
        exc_rules = self._parse_section(exc_text or "")
        return inc_rules, exc_rules

    @staticmethod
    def _text_from_element(elem: etree._Element) -> str:
        # Helper to safely extract text content, handling CDATA and line breaks.
        return " ".join(elem.itertext()).strip() if elem is not None else ""

    def process_xml_file(self, xml_path: Path) -> List[Trial]:
        """Parse a single XML file (may contain multiple ``FullStudy`` entries).
        Returns a list of ``Trial`` objects ready for DB insertion.
        """
        try:
            if hasattr(etree, "XMLParser"):
                try:
                    parser = etree.XMLParser(recover=True)  # nosec B314 - offline CT.gov fixture/XML dumps
                    tree = etree.parse(str(xml_path), parser)  # nosec B314
                except TypeError:
                    tree = etree.parse(str(xml_path))  # nosec B314
            else:
                tree = etree.parse(str(xml_path))  # nosec B314
            root = tree.getroot()
        except Exception:
            return []

        trials: List[Trial] = []
        for study in root.findall(".//FullStudy"):
            nct_elem = study.find(".//NCTId")
            title_elem = study.find(".//OfficialTitle")
            if nct_elem is None or title_elem is None:
                continue
            nct_id = nct_elem.text.strip()
            title = title_elem.text.strip()
            # Raw criteria text for storage
            inc_text = self._text_from_element(
                study.find(".//EligibilityCriteria/InclusionCriteria")
            )
            exc_text = self._text_from_element(
                study.find(".//EligibilityCriteria/ExclusionCriteria")
            )
            inc_rules, exc_rules = self.parse(study)
            trial = Trial(
                nct_id=nct_id,
                title=title,
                brief_summary=self._text_from_element(study.find(".//BriefSummary")),
                detailed_description=self._text_from_element(study.find(".//DetailedDescription")),
                inclusion_criteria=inc_text,
                exclusion_criteria=exc_text,
                inclusion_rules=str(inc_rules),  # simple JSON‑like string for MVP
                exclusion_rules=str(exc_rules),
            )
            trials.append(trial)
        return trials

    def bulk_load(self, xml_dir: Path, session) -> int:
        """Iterate over all ``.xml`` files in ``xml_dir`` and insert trials.

        Returns the number of trials inserted.
        """
        count = 0
        for xml_file in xml_dir.rglob("*.xml"):
            trials = self.process_xml_file(xml_file)
            for tr in trials:
                session.merge(tr)  # upsert based on ``nct_id`` unique index
                count += 1
        session.commit()
        return count


# Helper to create a DB session – used by the CLI script.
def get_engine(db_url: str = "sqlite:///clinical_trials.db"):
    if not HAS_SQLALCHEMY:
        raise RuntimeError("SQLAlchemy is required for database session helpers.")
    return create_engine(db_url, echo=False, future=True)


def get_session(engine=None):
    if not HAS_SQLALCHEMY:
        raise RuntimeError("SQLAlchemy is required for database session helpers.")
    engine = engine or get_engine()
    Session = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)
    return Session()
