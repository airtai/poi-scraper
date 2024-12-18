from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
from urllib.parse import urlparse

from fastagency.logging import get_logger

from poi_scraper.database import PoiDatabase, ScrapingStatistics
from poi_scraper.poi_types import PoiData, PoiManagerProtocol, ValidatePoiAgentProtocol
from poi_scraper.scraper import Scraper
from poi_scraper.statistics import Link, Site
from poi_scraper.utils import filter_same_domain_urls

logger = get_logger(__name__)


class PoiManager(PoiManagerProtocol):
    def __init__(
        self,
        base_url: str,
        poi_validator: ValidatePoiAgentProtocol,
        task_name: str,
        db_path: Path,
    ):
        """Initialize the POIManager with a base URL.

        This constructor sets up the initial state of the POIManager, including
        the base URL, domain, visited URLs set, URL priority queue, POI list,
        and lists for storing links with scores.

        Args:
            base_url (str): The base URL to start managing points of interest from.
            poi_validator (ValidatePoiAgentProtocol): The agent to validate points of interest.
            task_name (str): The name of the task.
            db_path (Path): The path to the database file.
        """
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.poi_validator = poi_validator
        self.db = PoiDatabase(db_path)
        self.current_url = ""
        self._urls_with_scores: Dict[str, List[Tuple[str, Literal[1, 2, 3, 4, 5]]]] = {}

        # Initialize or resume task with all state
        self.task_id, site_obj = self.db.create_or_get_task(task_name, base_url)

        if site_obj:
            self.homepage = site_obj.site_obj.urls[base_url]
        else:
            self.homepage = Link.create(parent=None, url=base_url, estimated_score=5)
            self._save_state_in_db()

    def _save_state_in_db(self) -> None:
        # Save new task state in the database
        self.db.save_task_state(
            self.task_id,
            ScrapingStatistics(
                site_obj=self.homepage.site,
            ),
        )

    def register_poi(self, poi: PoiData) -> str:
        """Register a new Point of Interest (POI)."""
        poi_validation_result = self.poi_validator.validate(
            poi.name, poi.description, poi.category, poi.location
        )

        if not poi_validation_result.is_valid:
            return f"POI validation failed for: {poi.name, poi.description}"

        # Check if POI already exists
        if self.db.is_poi_duplicate(self.task_id, poi):
            return f"POI already exists: {poi.name}"

        # Add POI to the database
        self.db.add_poi(self.task_id, self.current_url, poi)

        return f"POI registered: {poi.name}, Category: {poi.category}, Location: {poi.location}"

    def register_url(self, url: str, score: Literal[1, 2, 3, 4, 5]) -> str:
        """Register a new URL with its score."""
        self._urls_with_scores.setdefault(self.current_url, []).append((url, score))
        return f"Link registered: {url}, AI score: {score}"

    def process(
        self,
        *,
        scraper: Scraper,
        max_links_to_scrape: int = 50,
        min_scraping_score: Optional[int] = None,
    ) -> Tuple[Dict[str, List[PoiData]], Site]:
        # Create scraper function
        scrape = scraper.create(self)

        # Get the site object for the website
        site = self.homepage.site

        # Initialize unvisited links, defaulting to homepage if none exist
        unvisited_links = site.get_sorted_unvisited_links(min_scraping_score) or [
            self.homepage
        ]

        # Set initial value for urls_scraped counter
        urls_scraped = 0

        while unvisited_links and urls_scraped < max_links_to_scrape:
            # Increment the counter
            urls_scraped += 1

            # Process the highest scoring link first
            current_link = unvisited_links[0]
            self.current_url = current_link.url

            logger.info(f"Current URL: {self.current_url}")
            logger.info(f"Current URL Score: {current_link.score}")
            logger.info(f"All URLs: {site.get_url_scores()}")

            # Process URL
            scrape(self.current_url)

            # Process newly found URLs
            new_urls = self._urls_with_scores.get(self.current_url, [])
            same_domain_urls = filter_same_domain_urls(new_urls, self.base_domain)

            # Record the visit
            pois_found = bool(
                self.db.get_all_pois(self.task_id).get(self.current_url, [])
            )
            current_link.record_visit(
                poi_found=pois_found,
                urls_found=same_domain_urls,
            )

            # Save current state in the database
            self._save_state_in_db()

            # Get next batch of unvisited links
            unvisited_links = site.get_sorted_unvisited_links(min_scraping_score)

        # All URLs processed, mark task as complete
        self.db.mark_task_completed(self.task_id)
        return self.db.get_all_pois(self.task_id), site
