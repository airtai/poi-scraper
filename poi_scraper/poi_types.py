from collections import defaultdict
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
)

if TYPE_CHECKING:
    from poi_scraper.poi_manager import PoiManager


@dataclass
class ScraperResult:
    decision: Literal["TERMINATE", "CONTINUE"]
    current_url: str
    description: str


@dataclass
class PoiData:
    current_url: str
    name: str
    description: str
    category: str
    location: Optional[str] = None


@dataclass
class LinkData:
    url: str
    score: int


@dataclass
class ScoredURL:
    url: str
    score: int

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


@dataclass
class PoiValidationResult:
    """A class to represent the result of a POI (Point of Interest) validation.

    Attributes:
        is_valid (bool): Indicates whether the POI is valid.
        name (str): The name of the POI.
        description (str): The description of the POI.
        raw_response (str): The raw response from the validation process.
    """

    is_valid: bool
    name: str
    description: str
    raw_response: str


class PoiCollector(Protocol):
    def register_poi(self, poi: PoiData) -> str: ...
    def register_link(self, link: LinkData) -> str: ...


class ScraperFactoryProtocol(Protocol):
    def create_scraper(
        self, poi_manager: "PoiManager"
    ) -> Callable[["SessionMemory"], ScraperResult]: ...


class ValidatePoiAgentProtocol(Protocol):
    def validate(
        self, name: str, description: str, category: str, location: Optional[str]
    ) -> PoiValidationResult: ...


@dataclass
class PatternStats:
    success_count: int
    failure_count: int


@dataclass
class Link:
    url: str
    initial_score: int
    justification: str


@dataclass
class PageStats:
    pois: List[PoiData]  # pois found in page
    description: str  # summary of the page
    children_success_rate: (
        float  # how many child links found and how many of them has atleast one poi
    )
    last_n_pages_poi_count: List[int]  # recent child pages poi count
    unvisited_links: List[Link]  # after scraping, add the links present in the page


@dataclass
class SessionMemory:
    base_url: str
    visited_urls: Set[str] = field(default_factory=set)
    pages: Dict[str, PageStats] = field(default_factory=dict)
    patterns: Dict[str, PatternStats] = field(
        default_factory=lambda: defaultdict(
            lambda: PatternStats(success_count=0, failure_count=0)
        )
    )
