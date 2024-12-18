import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional
from unittest import TestCase

from poi_scraper.database import PoiDatabase
from poi_scraper.poi_manager import PoiManager
from poi_scraper.poi_types import (
    PoiData,
    PoiManagerProtocol,
    PoiValidationResult,
    ValidatePoiAgentProtocol,
)
from poi_scraper.scraper import Scraper


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


class MockScraper(Scraper):
    def __init__(self, test_case: TestCase):
        """Initialize the MockScraperFactory with a test case."""
        self.test_case = test_case
        self.first_call = True

    def create(self, poi_manager: PoiManagerProtocol) -> Callable[[str], str]:
        def mock_scrape(
            url: str,
        ) -> str:
            if self.first_call:
                # only for the first call, register the POIs and the URLs
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

                for poi in pois_found:
                    poi_manager.register_poi(poi)

                for url, score in urls_found.items():
                    poi_manager.register_url(url, score)

            return "Successful"

        return mock_scrape


class ResumeMockScraper(Scraper):
    def __init__(self, test_case: TestCase):
        """Mock scraper that handles two batches of POIs."""
        self.test_case = test_case

    def create(self, poi_manager: PoiManagerProtocol) -> Callable[[str], str]:
        def mock_scrape(url: str) -> str:
            self.first_call = False
            poi_manager.register_poi(
                PoiData("Beach POI", "Beach Description", "Beach", "Location 2")
            )
            return "Success"

        return mock_scrape


class TestPoiManager(TestCase):
    def setUp(self) -> None:
        self.db_path = Path("test_poi_data.db")
        if self.db_path.exists():
            self.db_path.unlink()

        self.base_url = "https://www.example.com"
        self.task_name = "Test Workflow"

        self.poi_validator = MockValidatePoiAgent()
        self.mock_scrape = MockScraper(self)

        # Create manager with explicit db path
        self.manager = PoiManager(
            base_url=self.base_url,
            poi_validator=self.poi_validator,
            task_name=self.task_name,
            db_path=self.db_path,
        )

    def tearDown(self) -> None:
        # Clean up the database
        if self.db_path.exists():
            self.db_path.unlink()

    def verify_task_state(self, task_id: int, expected_status: str) -> None:
        """Verify the state of the task in the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            task = cursor.fetchone()

            assert task is not None, f"No task found with ID {task_id}"
            assert task["status"] == expected_status
            assert task["name"] == self.task_name
            assert task["base_url"] == self.base_url
            assert task["site_obj"] is not None

    def verify_pois(
        self, task_id: int, expected_pois: Dict[str, List[PoiData]]
    ) -> None:
        """Verify the POIs in the database."""
        # Get POIs from database
        db = PoiDatabase(self.db_path)
        actual_pois = db.get_all_pois(task_id)

        # Compare with expected POIs
        assert (
            actual_pois == expected_pois
        ), f"POIs in database don't match expected.\nGot: {actual_pois}\nExpected: {expected_pois}"

    def test_new_and_resume_task(self) -> None:
        """Test complete task execution from scratch."""
        # verify initial task state
        self.verify_task_state(self.manager.task_id, "in_progress")

        # Process base URL
        pois, site = self.manager.process(
            scraper=self.mock_scrape,
            max_links_to_scrape=2,
        )

        # Test for checking only the first 2 links are visited and the rest are not
        all_site_links = list(site.urls.values())
        visited_links = [link for link in all_site_links if link.visited]
        assert len(visited_links) == 2
        assert visited_links[0].url == "https://www.example.com", visited_links[0].url
        assert visited_links[1].url == "https://www.example.com/5", visited_links[1].url

        unvisited_links = [link for link in all_site_links if not link.visited]
        assert len(unvisited_links) == 2
        assert unvisited_links[0].url == "https://www.example.com/3", unvisited_links[
            0
        ].url
        assert unvisited_links[1].url == "https://www.example.com/4", unvisited_links[
            1
        ].url

        # Verify POIs
        expected_pois = {
            self.base_url: [
                PoiData("name_1", "Description 1", "Category 1", "Location 1"),
                PoiData("name_2", "Description 2", "Category 2", "Location 2"),
                PoiData("name_3", "Description 3", "Category 3", "Location 3"),
            ]
        }
        self.verify_pois(self.manager.task_id, expected_pois)

        # Verify final task state
        self.verify_task_state(self.manager.task_id, "completed")

        # Verify site structure
        expected_urls = {
            "https://www.example.com": 5,
            "https://www.example.com/3": 0.909,
            "https://www.example.com/4": 1.909,
            "https://www.example.com/5": 2.909,
        }

        assert site.get_url_scores(decimals=3) == expected_urls

        # Simulate resume task
        resumed_manager = PoiManager(
            base_url=self.base_url,
            poi_validator=self.poi_validator,
            task_name=self.task_name,
            db_path=self.db_path,
        )

        resume_mock_scraper = ResumeMockScraper(self)
        pois_resume, site_resume = resumed_manager.process(scraper=resume_mock_scraper)

        expected_pois_resume = {
            self.base_url: [
                PoiData("name_1", "Description 1", "Category 1", "Location 1"),
                PoiData("name_2", "Description 2", "Category 2", "Location 2"),
                PoiData("name_3", "Description 3", "Category 3", "Location 3"),
            ],
            "https://www.example.com/4": [
                PoiData("Beach POI", "Beach Description", "Beach", "Location 2")
            ],
        }

        self.verify_pois(resumed_manager.task_id, expected_pois_resume)
