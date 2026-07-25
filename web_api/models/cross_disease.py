"""Pydantic models for cross-disease analysis endpoints."""

from pydantic import BaseModel
from typing import Optional


class CrossDiseaseResponse(BaseModel):
    shared_genes: dict = {}
    shared_drugs: dict = {}
    shared_pathways: dict = {}
    disease_similarity: list = []
    multi_disease_drugs: list = []
    disease_count: int = 0
    diseases: list = []
    disease_summary: dict = {}
