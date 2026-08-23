"""
CLI package initialization.
"""

from .menu import DuffelCLI, main
from .parser import PromptExtractor

__all__ = ["DuffelCLI", "PromptExtractor", "main"]
