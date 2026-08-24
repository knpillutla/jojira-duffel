"""
Web Scraper Registry & Parallel Execution Engine.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from .base import BaseWebScraper
from .frontier import FrontierScraper


class ScraperRegistry:
    """Registry managing and executing modular web scrapers concurrently."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._scrapers: list[BaseWebScraper] = [FrontierScraper()]

    def register(self, scraper: BaseWebScraper) -> None:
        """Register a new modular web scraper instance."""
        self._scrapers.append(scraper)

    def search_all_scrapers(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers_count: int = 1,
        cabin_class: str = "economy",
    ) -> list[dict[str, Any]]:
        """
        Execute all active web scrapers in parallel worker threads.

        Returns merged list of standardized external web fare offer summaries.
        """
        if not self.enabled or not self._scrapers:
            return []

        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(self._scrapers)) as executor:
            future_to_scraper = {
                executor.submit(
                    scraper.search_fares,
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    passengers_count=passengers_count,
                    cabin_class=cabin_class,
                ): scraper
                for scraper in self._scrapers
            }

            for future in as_completed(future_to_scraper):
                scraper = future_to_scraper[future]
                try:
                    fares = future.result()
                    if fares:
                        results.extend(fares)
                except Exception as err:
                    # Non-blocking error handling for external scrapers
                    pass

        return results
