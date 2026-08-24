"""
Modular Airline Web Scrapers Package.
"""

from .base import BaseWebScraper
from .frontier import FrontierScraper
from .registry import ScraperRegistry

__all__ = ["BaseWebScraper", "FrontierScraper", "ScraperRegistry"]
