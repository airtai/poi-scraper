from typing import Callable, Dict, List, Literal, Optional
from unittest import TestCase

from poi_scraper.poi import Link, PoiManager, Scraper
from poi_scraper.poi_types import (
    PoiData,
    PoiValidationResult,
    ValidatePoiAgentProtocol,
)


class TestLinkCreation:
    def test_create_link(self) -> None:
        link = Link.create(
            parent=None, url="https://www.example.com", estimated_score=5
        )

        assert link.url == "https://www.example.com"
        assert link.estimated_score == 5
        assert link.parents == set()
        assert not link.visited
        assert link.children == []
        assert link.children_visited == 0
        assert link.children_poi_found == 0


class TestPoiScore:
    def test_score(self) -> None:
        home = Link.create(
            parent=None, url="https://www.example.com", estimated_score=5
        )
        assert home.score == 5

        home.record_visit(
            poi_found=False,
            urls_found={
                "https://www.example.com/places": 4,
                "https://www.example.com/about": 3,
            },
        )
        places = home.site.urls["https://www.example.com/places"]
        about = home.site.urls["https://www.example.com/about"]

        places.record_visit(
            poi_found=True,
            urls_found={
                "https://www.example.com/places/something_else": 4,
            },
        )

        # should be almost equal
        # assert *.score == 5 + (1-math.exp(-0.2))
        assert home.score == 5.0, home.score
        assert round(places.score, 3) == 4.091
        assert round(about.score, 3) == 3.091

        about.record_visit(
            poi_found=True,
            urls_found={},
        )
        assert home.score == 5.0, home.score
        assert round(places.score, 3) == 4.165
        assert round(about.score, 3) == 3.165

        scores = home.site.get_url_scores(decimals=3)
        expected = {
            "https://www.example.com": 5.0,
            "https://www.example.com/about": 3.165,
            "https://www.example.com/places": 4.165,
            "https://www.example.com/places/something_else": 4,
        }
        assert scores == expected


class MockScraper(Scraper):
    def __init__(self, test_case: TestCase):
        """Initialize the MockScraperFactory with a test case."""
        self.test_case = test_case
        self.first_call = True

    def create(
        self,
    ) -> Callable[[str], tuple[list[PoiData], dict[str, Literal[1, 2, 3, 4, 5]]]]:
        def mock_scrape(
            url: str,
        ) -> tuple[list[PoiData], dict[str, Literal[1, 2, 3, 4, 5]]]:
            if self.first_call:
                self.first_call = False

                pois_found: List[PoiData] = []
                urls_found: Dict[str, Literal[1, 2, 3, 4, 5]] = {}

                pois_found = [
                    PoiData("name_1", "Description 1", "Category 1", "Location 1"),
                    PoiData("name_2", "Description 2", "Category 2", "Location 2"),
                    PoiData("name_3", "Description 3", "Category 3", "Location 3"),
                ]

                urls_found = {
                    "https://www.example.com/3": 1,
                    "https://www.example.com/4": 2,
                    "https://www.example.com/5": 3,
                    "https://www.someother-domain.com/3": 4,
                }

                return (
                    pois_found,
                    urls_found,
                )  # return the POIs and URLs for the first call

            return [], {}  # return empty lists from the second call

        return mock_scrape


class MockValidatePoiAgent(ValidatePoiAgentProtocol):
    def validate(
        self, name: str, description: str, category: str, location: Optional[str]
    ) -> PoiValidationResult:
        return PoiValidationResult(
            is_valid=True,
            name=name,
            description=description,
            raw_response="Raw response",
        )


class TestPoiManager(TestCase):
    def setUp(self) -> None:
        self.base_url = "https://www.example.com"
        poi_validator = MockValidatePoiAgent()
        self.manager = PoiManager(self.base_url, poi_validator)
        self.mock_scrape = MockScraper(self)

    def test_process_flow(self) -> None:
        # Process base URL
        pois_list, site = self.manager.process(self.mock_scrape)

        assert pois_list == {
            "name_1": {
                "description": "Description 1",
                "category": "Category 1",
                "location": "Location 1",
            },
            "name_2": {
                "description": "Description 2",
                "category": "Category 2",
                "location": "Location 2",
            },
            "name_3": {
                "description": "Description 3",
                "category": "Category 3",
                "location": "Location 3",
            },
        }

        expected = {
            "https://www.example.com": 5,
            "https://www.example.com/3": 0.774,
            "https://www.example.com/4": 1.774,
            "https://www.example.com/5": 2.774,
        }

        assert site.get_url_scores(decimals=3) == expected

    def test_process_flow_with_min_score(self) -> None:
        # Process base URL
        pois_list, site = self.manager.process(self.mock_scrape, min_score=2)

        assert pois_list == {
            "name_1": {
                "description": "Description 1",
                "category": "Category 1",
                "location": "Location 1",
            },
            "name_2": {
                "description": "Description 2",
                "category": "Category 2",
                "location": "Location 2",
            },
            "name_3": {
                "description": "Description 3",
                "category": "Category 3",
                "location": "Location 3",
            },
        }

        expected = {
            "https://www.example.com": 5,
            "https://www.example.com/3": 0.835,
            "https://www.example.com/4": 1.835,
            "https://www.example.com/5": 2.835,
        }

        assert site.get_url_scores(decimals=3) == expected
