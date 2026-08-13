"""Pydantic models for cross-disease analysis endpoints."""

from pydantic import BaseModel


class CrossDiseaseResponse(BaseModel):
    shared_genes: dict | list = {}
    shared_drugs: dict | list = {}
    shared_pathways: dict | list = {}
    disease_similarity: list | dict = []
    multi_disease_drugs: list = []
    disease_count: int = 0
    diseases: list = []
    disease_summary: dict = {}
    coverage: dict = {}
    status: str = "ready"
