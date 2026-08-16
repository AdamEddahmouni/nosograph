"""External database connectors and API integration modules."""

from .biorxiv import BioRxivClient
from .chembl_uniprot import ChEMBLClient, UniProtClient
from .client import fetch_json
from .gtex import GTExClient
from .opentargets import OpenTargetsClient

__all__ = [
    "fetch_json",
    "OpenTargetsClient",
    "GTExClient",
    "ChEMBLClient",
    "UniProtClient",
    "BioRxivClient",
]
