from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional, Protocol

if TYPE_CHECKING:
    from poi_scraper.poi_manager import PoiManager


@dataclass
class PoiData:
    name: str
    description: str
    category: str
    location: Optional[str] = None


@dataclass
class LinkData:
    url: str
    score: float


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


class PoiCollector(Protocol):
    def register_poi(self, poi: PoiData) -> str: ...
    def register_link(self, link: LinkData) -> str: ...


class ScraperFactoryProtocol(Protocol):
    def create_scraper(self, poi_manager: "PoiManager") -> Callable[[str], str]: ...
