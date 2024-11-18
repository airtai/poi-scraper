from typing import Any, Callable, Dict, Optional
from unittest import TestCase

from poi_scraper.poi_manager import PoiManager
from poi_scraper.poi_types import (
    PoiData,
    PoiValidationResult,
    ScraperFactoryProtocol,
    SessionMemory,
    ValidatePoiAgentProtocol,
)


class MockScraperFactory(ScraperFactoryProtocol):
    def __init__(self, test_case: TestCase):
        """Initialize the MockScraperFactory with a test case."""
        self.test_case = test_case
        self.call_count = 0

    def create_scraper(self, poi_manager: PoiManager) -> Callable[[SessionMemory], Dict[str, Any]]:
        def mock_scraper(session_memory: SessionMemory) -> Dict[str, Any]:
            self.call_count += 1
            current_url = "https://example.com"

            # Register POIs
            pois = [
                PoiData("name_1", "Description 1", "Category 1", "Location 1"),
                PoiData("name_2", "Description 2", "Category 2", "Location 2"),
                PoiData("name_3", "Description 3", "Category 3", "Location 3"),
            ]

            # Register some outgoing links
            poi_manager.register_link(
                current_url, "https://example.com/about", 0.8, "Important looking page"
            )
            poi_manager.register_link(
                current_url, "https://example.com/contact", 0.6, "Contact page"
            )

            # Register POIs after links
            for poi in pois:
                poi_manager.register_poi(poi, current_url)

            return {
                "current_url": current_url,
                "pois": pois,
                "description": "Test page description",
                "outgoing_links": session_memory.pages[current_url].unvisited_links,
                "decision": "TERMINATE" if self.call_count >= 1 else "CONTINUE",
            }

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

    def test_register_poi(self) -> None:
        # Register POI
        result = self.manager.register_poi(
            PoiData("name", "description", "category", "location"), self.base_url
        )

        assert self.manager.session_memory.pages[self.base_url].pois[0].name == "name"
        assert "POI registered" in result

    def test_register_link(self) -> None:
        # Register link
        result = self.manager.register_link(
            self.base_url, "https://example.com/1", 0.8, "Justification"
        )

        assert (
            self.manager.session_memory.pages[self.base_url].unvisited_links[0].url
            == "https://example.com/1"
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
        assert "https://example.com" in self.manager.session_memory.visited_urls

        # Verify pattern statistics
        assert (
            self.manager.session_memory.patterns["https://example.com"].success_count
            == 1
        )

        # Additional verifications
        assert len(self.manager.session_memory.pages["https://example.com"].pois) == 3
        assert (
            len(
                self.manager.session_memory.pages["https://example.com"].unvisited_links
            )
            == 2
        )

    def test_find_parent_url(self) -> None:
        # Setup parent-child relationship
        parent_url = "https://example.com"
        child_url = "https://example.com/child"

        self.manager.register_link(parent_url, child_url, 0.8, "Test justification")

        # Test finding parent URL
        found_parent = self.manager._find_parent_url(child_url)
        assert found_parent == parent_url

        # Test with non-existent child
        non_existent = self.manager._find_parent_url("https://example.com/nonexistent")
        assert non_existent is None

    def test_initialize_page_stats(self) -> None:
        # Initialize page stats
        self.manager._initialize_page_stats("https://example.com")

        # Verify page stats initialization
        assert self.manager.session_memory.pages["https://example.com"].pois == []
        assert (
            self.manager.session_memory.pages["https://example.com"].description == ""
        )
        assert (
            self.manager.session_memory.pages[
                "https://example.com"
            ].children_success_rate
            == 0.0
        )
        assert (
            self.manager.session_memory.pages[
                "https://example.com"
            ].last_n_pages_poi_count
            == []
        )
        assert (
            self.manager.session_memory.pages["https://example.com"].unvisited_links
            == []
        )

    # def test_should_process_url(self) -> None:
    #     # Same domain
    #     valid_urls = [
    #         "https://example.com/about",
    #         "https://example.com/contact",
    #         "https://example.com/locations/1",
    #     ]

    #     # Different domain
    #     invalid_urls = [
    #         "https://other.com/about",
    #         "http://test.example.com",  # subdomain
    #         "https://example.org",
    #     ]

    #     for url in valid_urls:
    #         assert self.manager._should_process_url(url)

    #     for url in invalid_urls:
    #         assert not self.manager._should_process_url(url)

    # def test_add_to_queue(self) -> None:
    #     urls = [
    #         ("https://example.com/1", 0.8),
    #         ("https://example.com/2", 0.9),
    #         ("https://example.com/3", 0.7),
    #     ]

    #     # Add URLs to queue
    #     for url, score in urls:
    #         self.manager._add_to_queue(url, score)

    #     # Verify queue order (highest score first)
    #     assert self.manager.url_queue.get().url == "https://example.com/2"
    #     assert self.manager.url_queue.get().url == "https://example.com/1"
    #     assert self.manager.url_queue.get().url == "https://example.com/3"

    # def test_calculate_depth_score(self) -> None:
    #     test_cases = [
    #         ("https://example.com", 0.0),
    #         ("https://example.com/about", 0.3),
    #         ("https://example.com/about/team", 0.5),
    #         ("https://example.com/about/team/member", 0.7),
    #         ("https://example.com/a/b/c/d", 0.9),
    #         ("https://example.com/a/b/c/d/e", 0.9),
    #     ]

    #     for url, expected_score in test_cases:
    #         assert self.manager._calculate_depth_score(url) == expected_score

    # def test_calculate_final_score(self) -> None:
    #     test_cases = [
    #         (0.0, 0.0, 0.0),  # min scores
    #         (1.0, 0.9, 0.94),  # max scores
    #         (0.5, 0.5, 0.5),  # middle scores
    #     ]

    #     for ai_score, depth_score, expected in test_cases:
    #         result = self.manager._calculate_final_score(ai_score, depth_score)
    #         assert round(result, 2) == round(expected, 2)

    # def test_process_flow(self) -> None:
    #     # Process base URL
    #     pois = self.manager.process(self.mock_factory)

    #     # Verify visited set
    #     assert self.base_url in self.manager.visited_urls

    #     # Verify queue processing
    #     assert len(pois.keys()) == 3
    #     assert pois["name_1"]["description"] == "Description 1"
    #     assert self.manager.visited_urls == {
    #         self.base_url,
    #         "https://example.com/4",
    #         "https://example.com/5",
    #         "https://example.com/6",
    #     }
    #     assert self.manager.url_queue.qsize() == 0
