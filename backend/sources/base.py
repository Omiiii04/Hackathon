"""
backend/sources/base.py
-------------------------
Abstract base class for all evidence retrievers.
"""
from abc import ABC, abstractmethod
from typing import List


class BaseRetriever(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(self, claim: str, max_results: int = 5) -> list:
        """Fetch evidence items for the claim. Returns List[EvidenceItem]."""
        ...
