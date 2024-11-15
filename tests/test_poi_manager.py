from typing import Callable, Optional
from unittest import TestCase

from poi_scraper.poi_manager import PoiManager
from poi_scraper.poi_types import (
    PoiData,
    PoiValidationResult,
    ScraperFactoryProtocol,
    ValidatePoiAgentProtocol,
)


class MockScraperFactory(ScraperFactoryProtocol):
    def __init__(self, test_case: TestCase):
        """Initialize the MockScraperFactory with a test case."""
        self.test_case = test_case

    def create_scraper(self, poi_manager: PoiManager) -> Callable[[str], str]:
        def mock_scraper(url: str) -> str:
            poi_manager.register_poi(
                PoiData("name_1", "Description 1", "Category 1", "Location 1")
            )
            poi_manager.register_poi(
                PoiData("name_2", "Description 2", "Category 2", "Location 2")
            )
            poi_manager.register_poi(
                PoiData("name_3", "Description 3", "Category 3", "Location 3")
            )
            poi_manager.register_link("https://example.com/3", 0.1)
            poi_manager.register_link("https://example.com/4", 0.6)
            poi_manager.register_link("https://example.com/5", 0.7)
            poi_manager.register_link("https://example.com/6", 0.8)
            return "Chat summary"

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
        self.base_url = "https://example.com"
        poi_validator = MockValidatePoiAgent()
        self.manager = PoiManager(self.base_url, poi_validator)
        self.mock_factory = MockScraperFactory(self)

    def test_should_process_url(self) -> None:
        # Same domain
        valid_urls = [
            "https://example.com/about",
            "https://example.com/contact",
            "https://example.com/locations/1",
        ]

        # Different domain
        invalid_urls = [
            "https://other.com/about",
            "http://test.example.com",  # subdomain
            "https://example.org",
        ]

        for url in valid_urls:
            assert self.manager._should_process_url(url)

        for url in invalid_urls:
            assert not self.manager._should_process_url(url)

    def test_add_to_queue(self) -> None:
        urls = [
            ("https://example.com/1", 0.8),
            ("https://example.com/2", 0.9),
            ("https://example.com/3", 0.7),
        ]

        # Add URLs to queue
        for url, score in urls:
            self.manager._add_to_queue(url, score)

        # Verify queue order (highest score first)
        assert self.manager.url_queue.get().url == "https://example.com/2"
        assert self.manager.url_queue.get().url == "https://example.com/1"
        assert self.manager.url_queue.get().url == "https://example.com/3"

    def test_calculate_depth_score(self) -> None:
        test_cases = [
            ("https://example.com", 0.0),
            ("https://example.com/about", 0.3),
            ("https://example.com/about/team", 0.5),
            ("https://example.com/about/team/member", 0.7),
            ("https://example.com/a/b/c/d", 0.9),
            ("https://example.com/a/b/c/d/e", 0.9),
        ]

        for url, expected_score in test_cases:
            assert self.manager._calculate_depth_score(url) == expected_score

    def test_calculate_final_score(self) -> None:
        test_cases = [
            (0.0, 0.0, 0.0),  # min scores
            (1.0, 0.9, 0.94),  # max scores
            (0.5, 0.5, 0.5),  # middle scores
        ]

        for ai_score, depth_score, expected in test_cases:
            result = self.manager._calculate_final_score(ai_score, depth_score)
            assert round(result, 2) == round(expected, 2)

    def test_process_flow(self) -> None:
        # Process base URL
        pois = self.manager.process(self.mock_factory)

        # Verify visited set
        assert self.base_url in self.manager.visited_urls

        # Verify queue processing
        assert len(pois.keys()) == 3
        assert pois["name_1"]["description"] == "Description 1"
        assert self.manager.visited_urls == {
            self.base_url,
            "https://example.com/4",
            "https://example.com/5",
            "https://example.com/6",
        }
        assert self.manager.url_queue.qsize() == 0
