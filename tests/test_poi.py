import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional
from unittest import TestCase

from poi_scraper.poi import Link, PoiDatabase, PoiManager, Scraper
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

    def create(self, poi_manager: PoiManager) -> Callable[[str], str]:
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

    def create(self, poi_manager: PoiManager) -> Callable[[str], str]:
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
        self.workflow_name = "Test Workflow"

        self.poi_validator = MockValidatePoiAgent()
        self.mock_scrape = MockScraper(self)

        # Create manager with explicit db path
        self.manager = PoiManager(
            base_url=self.base_url,
            poi_validator=self.poi_validator,
            workflow_name=self.workflow_name,
            db_path=self.db_path,
        )

    def tearDown(self) -> None:
        # Clean up the database
        if self.db_path.exists():
            self.db_path.unlink()

    def verify_workflow_state(self, workflow_id: int, expected_status: str) -> None:
        """Verify the state of the workflow in the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
            )
            workflow = cursor.fetchone()

            assert workflow is not None, f"No workflow found with ID {workflow_id}"
            assert workflow["status"] == expected_status
            assert workflow["name"] == self.workflow_name
            assert workflow["base_url"] == self.base_url

            if expected_status == "completed":
                assert workflow["queue_state"] is None
                assert workflow["all_urls_scores"] is None
                assert workflow["less_score_urls"] is None

    def verify_pois(
        self, workflow_id: int, expected_pois: Dict[str, List[PoiData]]
    ) -> None:
        """Verify the POIs in the database."""
        # Get POIs from database
        db = PoiDatabase(self.db_path)
        actual_pois = db.get_all_pois(workflow_id)

        # Compare with expected POIs
        assert (
            actual_pois == expected_pois
        ), f"POIs in database don't match expected.\nGot: {actual_pois}\nExpected: {expected_pois}"

    def test_new_and_resume_workflow(self) -> None:
        """Test complete workflow execution from scratch."""
        # verify initial workflow state
        self.verify_workflow_state(self.manager.workflow_id, "in_progress")

        # Process base URL
        pois, site = self.manager.process(self.mock_scrape)

        # Verify POIs
        expected_pois = {
            self.base_url: [
                PoiData("name_1", "Description 1", "Category 1", "Location 1"),
                PoiData("name_2", "Description 2", "Category 2", "Location 2"),
                PoiData("name_3", "Description 3", "Category 3", "Location 3"),
            ]
        }
        self.verify_pois(self.manager.workflow_id, expected_pois)

        # Verify final workflow state
        self.verify_workflow_state(self.manager.workflow_id, "completed")

        # Verify site structure
        expected_urls = {
            "https://www.example.com": 5,
            "https://www.example.com/3": 0.774,
            "https://www.example.com/4": 1.774,
            "https://www.example.com/5": 2.774,
        }

        assert site.get_url_scores(decimals=3) == expected_urls

        # Simulate resume workflow
        resumed_manager = PoiManager(
            base_url=self.base_url,
            poi_validator=self.poi_validator,
            workflow_name=self.workflow_name,
            db_path=self.db_path,
        )

        resume_mock_scraper = ResumeMockScraper(self)
        pois_resume, site_resume = resumed_manager.process(resume_mock_scraper)

        expected_pois_resume = {
            self.base_url: [
                PoiData("Beach POI", "Beach Description", "Beach", "Location 2"),
                PoiData("name_1", "Description 1", "Category 1", "Location 1"),
                PoiData("name_2", "Description 2", "Category 2", "Location 2"),
                PoiData("name_3", "Description 3", "Category 3", "Location 3"),
            ]
        }

        self.verify_pois(resumed_manager.workflow_id, expected_pois_resume)
