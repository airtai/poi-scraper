from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
from urllib.parse import urlparse

from poi_scraper.database import PoiDatabase, WorkflowState
from poi_scraper.poi_types import PoiData, PoiManagerProtocol, ValidatePoiAgentProtocol
from poi_scraper.scraper import Scraper
from poi_scraper.statistics import Link, Site
from poi_scraper.utils import filter_same_domain_urls


class PoiManager(PoiManagerProtocol):
    def __init__(
        self,
        base_url: str,
        poi_validator: ValidatePoiAgentProtocol,
        workflow_name: str,
        db_path: Path,
    ):
        """Initialize the POIManager with a base URL.

        This constructor sets up the initial state of the POIManager, including
        the base URL, domain, visited URLs set, URL priority queue, POI list,
        and lists for storing links with scores.

        Args:
            base_url (str): The base URL to start managing points of interest from.
            poi_validator (ValidatePoiAgentProtocol): The agent to validate points of interest.
            workflow_name (str): The name of the workflow.
            db_path (Path): The path to the database file.
        """
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.poi_validator = poi_validator
        self.db = PoiDatabase(db_path)

        # Initialize or resume workflow with all state
        self.workflow_id, state = self.db.create_or_get_workflow(
            workflow_name, base_url
        )

        if state:
            self.urls = state.urls
            self.homepage = state.homepage
            self._all_urls_with_scores = state.all_urls_with_scores
            self.urls_with_less_score = state.urls_with_less_score

        else:
            self.homepage = Link.create(parent=None, url=base_url, estimated_score=5)
            self.urls = [self.homepage]
            self._all_urls_with_scores = {}
            self.urls_with_less_score = {}
            self._save_state_in_db()

        self.current_url = ""

    def _save_state_in_db(self) -> None:
        # Save new workflow state in the database
        self.db.save_workflow_state(
            self.workflow_id,
            WorkflowState(
                urls=self.urls,
                homepage=self.homepage,
                all_urls_with_scores=self._all_urls_with_scores,
                urls_with_less_score=self.urls_with_less_score,
            ),
        )

    def _add_url(self, link: Link, min_score: Optional[int] = None) -> None:
        """Add unvisited links to queue if they meet score threshold."""
        if link.visited or link.url in {url.url for url in self.urls}:
            return

        if not min_score or link.score >= min_score:
            self.urls.append(link)

            # Keep urls sorted by score (descending)
            self.urls.sort(key=lambda x: x.score, reverse=True)

        else:
            self.urls_with_less_score[link.url] = link.estimated_score

    def register_poi(self, poi: PoiData) -> str:
        """Register a new Point of Interest (POI)."""
        poi_validation_result = self.poi_validator.validate(
            poi.name, poi.description, poi.category, poi.location
        )

        if not poi_validation_result.is_valid:
            return f"POI validation failed for: {poi.name, poi.description}"

        # Check if POI already exists
        if self.db.is_poi_deplicate(self.workflow_id, poi):
            return f"POI already exists: {poi.name}"

        # Add POI to the database
        self.db.add_poi(self.workflow_id, self.current_url, poi)

        return f"POI registered: {poi.name}, Category: {poi.category}, Location: {poi.location}"

    def register_url(self, url: str, score: Literal[1, 2, 3, 4, 5]) -> str:
        """Register a new URL with its score."""
        self._all_urls_with_scores.setdefault(self.current_url, []).append((url, score))
        return f"Link registered: {url}, AI score: {score}"

    def process(
        self, scraper: Scraper, min_score: Optional[int] = None
    ) -> Tuple[Dict[str, List[PoiData]], Site]:
        # Create scraper function
        scrape = scraper.create(self)
        site = self.homepage.site

        while self.urls:
            link = self.urls.pop(0)

            if link.visited:
                continue

            # Set the current URL
            self.current_url = link.url

            # Process URL
            scrape(link.url)

            # Get only the new urls that were added from the current iteration
            new_urls = self._all_urls_with_scores.get(self.current_url, [])
            same_domain_urls = filter_same_domain_urls(new_urls, self.base_domain)

            # Record the visit
            pois_found = bool(self.db.get_all_pois(self.workflow_id).get(link.url, []))
            link.record_visit(
                poi_found=pois_found,
                urls_found=same_domain_urls,
            )

            # Add the new links
            for new_link in link.site.urls.values():
                self._add_url(new_link, min_score)

            # Save workflow state after each iteration to database
            self._save_state_in_db()

        # Mark workflow as completed in the database
        self.db.mark_workflow_completed(self.workflow_id)

        return self.db.get_all_pois(self.workflow_id), site
