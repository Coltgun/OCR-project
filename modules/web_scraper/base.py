"""
WebScraper ABC — stub for future novel/fiction web scraping with chapter detection.

Do NOT implement this class until the web_scraper module is formally scoped.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterator

from core.registry import Registrable
from core.types import Chapter


class WebScraper(Registrable):
    """Abstract base for web scraping implementations (future feature)."""

    @abstractmethod
    def scrape(self, url: str, config: dict) -> Iterator[Chapter]:
        """Scrape *url* and yield Chapter objects in reading order.

        Args:
            url:    URL of the novel index page or first chapter page.
            config: Full application config dict.

        Yields:
            Chapter objects with text already populated (no OCR needed).
        """
