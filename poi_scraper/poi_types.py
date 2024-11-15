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
    def create_scraper(self, poi_manager: "PoiManager") -> Callable[[str], str]: ...


class ValidatePoiAgentProtocol(Protocol):
    def validate(
        self, name: str, description: str, category: str, location: Optional[str]
    ) -> PoiValidationResult: ...
