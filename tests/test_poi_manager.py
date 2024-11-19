from typing import Callable, Optional
from unittest import TestCase

from poi_scraper.poi_manager import PoiManager
from poi_scraper.poi_types import (
    PoiData,
    PoiValidationResult,
    ScraperFactoryProtocol,
    ScraperResult,
    SessionMemory,
    ValidatePoiAgentProtocol,
)


class MockScraperFactory(ScraperFactoryProtocol):
    def __init__(self, test_case: TestCase):
        """Initialize the MockScraperFactory with a test case."""
        self.test_case = test_case
        self.call_count = 0

    def create_scraper(
        self, poi_manager: PoiManager
    ) -> Callable[[SessionMemory], ScraperResult]:
        def mock_scraper(session_memory: SessionMemory) -> ScraperResult:
            self.call_count += 1
            current_url = "https://www.example.com"

            # Register POIs
            pois = [
                PoiData(
                    "https://www.example.com",
                    "name_1",
                    "Description 1",
                    "Category 1",
                    "Location 1",
                ),
                PoiData(
                    "https://www.example.com",
                    "name_2",
                    "Description 2",
                    "Category 2",
                    "Location 2",
                ),
                PoiData(
                    "https://www.example.com",
                    "name_3",
                    "Description 3",
                    "Category 3",
                    "Location 3",
                ),
            ]

            # Register some outgoing links
            poi_manager.register_link(
                current_url,
                "https://www.example.com/about",
                5,
                "Important looking page",
            )
            poi_manager.register_link(
                current_url, "https://www.example.com/contact", 1, "Contact page"
            )

            # Register POIs after links
            for poi in pois:
                poi_manager.register_poi(poi)

            return ScraperResult(
                current_url=current_url,
                description="Test page description",
                decision="TERMINATE" if self.call_count >= 1 else "CONTINUE",
            )

        return mock_scraper


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
        self.mock_factory = MockScraperFactory(self)

    def test_register_poi(self) -> None:
        # Register POI
        result = self.manager.register_poi(
            PoiData(
                "https://www.example.com", "name", "description", "category", "location"
            )
        )
        assert self.manager.session_memory.pages[self.base_url].pois[0].name == "name"
        assert "POI registered" in result

    def test_register_link(self) -> None:
        # Register link
        result = self.manager.register_link(
            self.base_url, "https://www.example.com/1", 1, "Justification"
        )

        assert (
            self.manager.session_memory.pages[self.base_url].unvisited_links[0].url
            == "https://www.example.com/1"
        )
        assert "Link registered" in result

    def test_process_flow(self) -> None:
        # Process base URL
        report = self.manager.process(self.mock_factory)

        # Verify visited set
        assert self.base_url in self.manager.session_memory.visited_urls

        # Verify report format and content
        assert "# Crawl Results for" in report
        assert "Total Pages Crawled:" in report
        assert "Total POIs Found:" in report
        assert "## POIs Found Per Page" in report

        # Verify session memory updates
        assert "https://www.example.com" in self.manager.session_memory.visited_urls

        # Verify pattern statistics
        assert (
            self.manager.session_memory.patterns[
                "https://www.example.com"
            ].success_count
            == 1
        )

        # Additional verifications
        assert (
            len(self.manager.session_memory.pages["https://www.example.com"].pois) == 3
        )
        assert (
            len(
                self.manager.session_memory.pages[
                    "https://www.example.com"
                ].unvisited_links
            )
            == 2
        )

    def test_find_parent_url(self) -> None:
        # Setup parent-child relationship
        parent_url = "https://www.example.com"
        child_url = "https://www.example.com/child"

        self.manager.register_link(parent_url, child_url, 4, "Test justification")

        # Test finding parent URL
        found_parent = self.manager._find_parent_url(child_url)
        assert found_parent == parent_url

        # Test with non-existent child
        non_existent = self.manager._find_parent_url(
            "https://www.example.com/nonexistent"
        )
        assert non_existent is None

    def test_initialize_page_stats(self) -> None:
        # Initialize page stats
        self.manager._initialize_page_stats("https://www.example.com")

        # Verify page stats initialization
        assert self.manager.session_memory.pages["https://www.example.com"].pois == []
        assert (
            self.manager.session_memory.pages["https://www.example.com"].description
            == ""
        )
        assert (
            self.manager.session_memory.pages[
                "https://www.example.com"
            ].children_success_rate
            == 0.0
        )
        assert (
            self.manager.session_memory.pages[
                "https://www.example.com"
            ].last_n_pages_poi_count
            == []
        )
        assert (
            self.manager.session_memory.pages["https://www.example.com"].unvisited_links
            == []
        )
