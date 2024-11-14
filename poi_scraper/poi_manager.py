from dataclasses import dataclass
from queue import PriorityQueue
from typing import Callable, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse


@dataclass
class ScoredURL:
    url: str
    score: float

    def __lt__(self, other: "ScoredURL") -> bool:
        """Compare two ScoredURL objects for less-than based on their scores.

        This method is used to order ScoredURL objects in a priority queue,
        where higher scores have higher priority.

        Args:
            other (ScoredURL): The other ScoredURL object to compare against.

        Returns:
            bool: True if the score of this ScoredURL is greater than the score of the other ScoredURL, False otherwise.
        """
        return self.score > other.score  # Reverse for priority queue (highest first)


class PoiManager:
    def __init__(self, base_url: str):
        """Initialize the POIManager with a base URL.

        This constructor sets up the initial state of the POIManager, including
        the base URL, domain, visited URLs set, URL priority queue, POI list,
        and lists for storing links with scores.

        Args:
            base_url (str): The base URL to start managing points of interest from.
        """
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.visited_urls: Set[str] = set()
        self.url_queue: PriorityQueue[ScoredURL] = PriorityQueue()
        self.poi_list: dict[str, dict[str, Union[str, Optional[str]]]] = {}
        self.all_links_with_scores: List[Tuple[str, float]] = []
        self._current_url_links_with_scores: List[Tuple[str, float]] = []

    def register_new_poi(
        self, name: str, description: str, category: str, location: Optional[str]
    ) -> str:
        self.poi_list[name] = {
            "description": description,
            "category": category,
            "location": location,
        }
        return f"POI registered: {name}, Category: {category}, Location: {location}"

    def register_new_link(self, url: str, ai_score: float) -> str:
        self.all_links_with_scores.append((url, ai_score))
        return f"Link registered: {url}, AI score: {ai_score}"

    def process(
        self, scraper: Callable[[str], str]
    ) -> dict[str, dict[str, Union[str, Optional[str]]]]:
        # Initialize with base URL
        self._add_to_queue(self.base_url, 1.0)

        while not self.url_queue.empty():
            current_url = self.url_queue.get().url

            if current_url in self.visited_urls:
                continue

            try:
                # Process URL using AI
                scraper(current_url)

                # Process only new URLs
                self._current_url_links_with_scores = list(
                    set(self.all_links_with_scores)
                    - set(self._current_url_links_with_scores)
                )
                self._process_new_urls()

                # Mark URL as visited
                self.visited_urls.add(current_url)

            except Exception:
                # print(f"Error processing URL: {current_url}")
                # print(e)
                continue

        return self.poi_list

    def _process_new_urls(self) -> None:
        """Process new URLs and add them to queue."""
        for url, ai_score in self._current_url_links_with_scores:
            if self._should_process_url(url):
                depth_score = self._calculate_depth_score(url)
                final_score = self._calculate_final_score(ai_score, depth_score)
                self._add_to_queue(url, final_score)

    def _should_process_url(self, url: str) -> bool:
        """Check if URL should be processed."""
        if url in self.visited_urls:
            return False

        domain = urlparse(url).netloc
        return domain == self.base_domain

    def _calculate_depth_score(self, url: str) -> float:
        """Calculate depth score based on URL path."""
        depth = len(urlparse(url).path.split("/")) - 1
        if depth == 0:
            return 0.0
        if depth == 1:
            return 0.3
        if depth == 2:
            return 0.5
        if depth == 3:
            return 0.7
        return 0.9

    def _calculate_final_score(self, ai_score: float, depth_score: float) -> float:
        """Calculate final score combining AI and depth scores."""
        return (ai_score * 0.4) + (depth_score * 0.6)

    def _add_to_queue(self, url: str, score: float) -> None:
        """Add URL to priority queue."""
        self.url_queue.put(ScoredURL(url, score))
