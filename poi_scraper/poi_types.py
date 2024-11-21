from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Callable, Literal, Optional, Protocol

from pydantic import BaseModel, Field

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


class CustomWebSurferAnswer(BaseModel):
    task: Annotated[
        str,
        Field(
            ...,
            description="A concise description of the task that was executed, such as collecting POI data and links from a webpage.",
        ),
    ]
    is_successful: Annotated[
        bool,
        Field(
            ...,
            description="Indicates whether the task was completed successfully without errors or issues.",
        ),
    ]
    pois_found: Annotated[
        list[PoiData],
        Field(
            ...,
            description="A list containing details of all Points of Interest (POIs) identified on the webpage, including the name, location, category, and description of each POI.",
        ),
    ]
    urls_found: Annotated[
        dict[str, Literal[1, 2, 3, 4, 5]],
        Field(
            ...,
            description="A dictionary mapping each URL found on the webpage to its relevance score (1-5), where higher scores indicate a greater likelihood of containing more POIs.",
        ),
    ]

    @staticmethod
    def get_example_answer() -> "CustomWebSurferAnswer":
        return CustomWebSurferAnswer(
            task="Visit https://www.kayak.co.in/Chennai.13827.guide, collect Points of Interest (POI) data, extract all clickable links, and assign each link a relevance score from 1 to 5 (1 = very unlikely to lead to more POIs, 5 = very likely to lead to more POIs)",
            is_successful=True,
            pois_found=[
                {
                    "name": "Marina Beach",
                    "location": "Chennai",
                    "category": "Beach",
                    "description": "Marina Beach is a natural urban beach in Chennai, Tamil Nadu, India, along the Bay of Bengal. The beach runs from near Fort St. George in the north to Foreshore Estate in the south, a distance of 6.0 km (3.7 mi), making it the longest natural urban beach in the country.",
                },
                {
                    "name": "Kapaleeshwarar Temple",
                    "location": "Chennai",
                    "category": "Temple",
                    "description": "Kapaleeshwarar Temple is a temple of Shiva located in Mylapore, Chennai in the Indian state of Tamil Nadu. The form of Shiva's consort Parvati worshipped at this temple is called Karpagambal.",
                },
                {
                    "name": "Arignar Anna Zoological Park",
                    "location": "Chennai",
                    "category": "Zoo",
                    "description": "Arignar Anna Zoological Park, also known as the Vandalur Zoo, is a zoological garden located in Vandalur, a suburb in the southwestern part of Chennai, Tamil Nadu, about 31 kilometers from the city center and 15 kilometers from Chennai Airport.",
                },
                {
                    "name": "Guindy National Park",
                    "location": "Chennai",
                    "category": "National Park",
                    "description": "Guindy National Park is a 2.70 km2 (1.04 sq mi) Protected area of Tamil Nadu, located in Chennai, South India, is the 8th smallest National Park of India and one of the very few national parks situated inside a city.",
                },
            ],
            urls_found={
                "https://www.kayak.co.in/Chennai.13827.guide": 5,
                "https://www.kayak.co.in/Chennai.13827.guide/places": 5,
                "https://www.kayak.co.in/Chennai.13827.guide/login": 1,
                "https://www.kayak.co.in/Chennai.13827.guide/hotels/Taj-Coromandel": 5,
                "https://www.kayak.co.in/Chennai.13827.guide/nightlife": 4,
            },
        )


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
