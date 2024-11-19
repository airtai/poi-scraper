from typing import Optional
from unittest import TestCase

from poi_scraper.poi_manager import PoiManager
from poi_scraper.poi_types import (
    Link,
    PageStats,
    PatternStats,
    PoiData,
    PoiValidationResult,
    SessionMemory,
    ValidatePoiAgentProtocol,
)
from poi_scraper.scraper import ScraperFactory


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


class TestScraperFactory(TestCase):
    def setUp(self) -> None:
        self.base_url = "https://example.com"
        poi_validator = MockValidatePoiAgent()
        self.manager = PoiManager(self.base_url, poi_validator)
        self.factory = ScraperFactory(
            {
                "config_list": [
                    {
                        "model": "some_model",
                        "api_key": "some_key",
                    }
                ],
                "temperature": 0.8,
            }
        )

    def test_format_initial_message_for_initial_scraping(self) -> None:
        base_url = "https://example.com"
        session_memory = SessionMemory(base_url)
        message = self.factory._format_initial_message(session_memory)

        assert message == "Please collect all POIs and links from: https://example.com"

    def test_format_initial_message_for_continue_scraping(self) -> None:
        base_url = "https://example.com"
        session_memory = SessionMemory(
            base_url=base_url,
            visited_urls={"https://example.com"},
            pages={
                "https://example.com": PageStats(
                    pois=[
                        PoiData(
                            "https://example.com",
                            "POI 1",
                            "Description 1",
                            "Category 1",
                            "Location 1",
                        ),
                        PoiData(
                            "https://example.com",
                            "POI 2",
                            "Description 2",
                            "Category 2",
                            "Location 2",
                        ),
                    ],
                    description="",
                    children_success_rate=1.0,
                    last_n_pages_poi_count=[2],
                    unvisited_links=[
                        Link(
                            "https://example.com/about",
                            1,
                            "Informational page",
                        ),
                        Link(
                            "https://example.com/places",
                            5,
                            "Places page",
                        ),
                    ],
                )
            },
            patterns={
                "https://example.com": PatternStats(
                    success_count=1,
                    failure_count=0,
                )
            },
        )
        actual_message = self.factory._format_initial_message(session_memory)

        expected_message = """Below is the statistics of the current scraping session:

1. Unvisited Links Available:
  - Url: https://example.com/about
    Initial Score: 1
    Justification: Informational page
   - Url: https://example.com/places
    Initial Score: 5
    Justification: Places page


3. Recent Performance:
  - https://example.com: 2 POIs found


4. Pattern Performance:
  - https://example.com: 1/1 success

"""

        assert actual_message == expected_message
