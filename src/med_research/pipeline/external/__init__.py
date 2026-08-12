"""External database connectors and API integration modules."""

from .client import fetch_json
from .opentargets import OpenTargetsClient
from .gtex import GTExClient
from .chembl_uniprot import ChEMBLClient, UniProtClient
from .biorxiv import BioRxivClient

__all__ = [
    "fetch_json",
    "OpenTargetsClient",
    "GTExClient",
    "ChEMBLClient",
    "UniProtClient",
    "BioRxivClient",
]
