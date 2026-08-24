"""
Base Abstract Web Scraper Interface for Direct Airline Web Fares.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseWebScraper(ABC):
    """Abstract base class for modular airline web scrapers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scraper service (e.g., 'Frontier Direct Web Scraper')."""
        pass

    @property
    @abstractmethod
    def airline_code(self) -> str:
        """IATA carrier code (e.g., 'F9')."""
        pass

    @abstractmethod
    def search_fares(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers_count: int = 1,
        cabin_class: str = "economy",
    ) -> list[dict[str, Any]]:
        """
        Execute fare extraction for direct web-exclusive fares.

        Returns list of standardized offer dictionary summaries.
        """
        pass
