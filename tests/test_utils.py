import unittest
from typing import Dict, List, Literal, Tuple

from poi_scraper.poi_types import PoiData
from poi_scraper.utils import (
    filter_same_domain_urls,
    generate_poi_markdown_table,
    generated_formatted_scores,
    is_valid_url,
)


class TestIsValidUrl(unittest.TestCase):
    def test_is_valid_url_valid(self) -> None:
        assert is_valid_url("http://www.example.com")
        assert is_valid_url("https://www.example.com")

    def test_is_valid_url_invalid(self) -> None:
        assert not is_valid_url("https://example.com/path?query=param#fragment")
        assert not is_valid_url("http://example.com")
        assert not is_valid_url("www.example.com")
        assert not is_valid_url("example.com")
        assert not is_valid_url("example")
        assert not is_valid_url("http://")
        assert not is_valid_url("https://")
        assert not is_valid_url("ftp://")
        assert not is_valid_url("ftp://www.example.com")


class TestFilterSameDomainUrls(unittest.TestCase):
    def test_filter_same_domain_urls(self) -> None:
        urls_found: list[Tuple[str, Literal[1, 2, 3, 4, 5]]] = [
            ("http://www.example.com/page1", 1),
            ("http://www.example.com/page2", 2),
            ("http://www.otherdomain.com/page1", 3),
        ]

        expected = {
            "http://www.example.com/page1": 1,
            "http://www.example.com/page2": 2,
        }

        cases = [
            # "http://example.com",
            "www.example.com",
            "http://www.example.com",
            "https://www.example.com",
        ]

        for case in cases:
            actual = filter_same_domain_urls(urls_found, case)
            assert actual == expected


class TestGeneratedFormattedScores(unittest.TestCase):
    def test_generated_formatted_scores(self) -> None:
        scores: Dict[str, float] = {
            "http://www.example.com/page1": 1.0,
            "http://www.example.com/page2": 2.5,
        }

        expected = """| Sno | Url | Score |\n| --- | --- | --- |
| 1 | http://www.example.com/page1 | 1.0 |
| 2 | http://www.example.com/page2 | 2.5 |"""

        actual = generated_formatted_scores(scores)
        assert actual == expected


class TestGeneratePoiMarkdownTable(unittest.TestCase):
    def test_generate_poi_markdown_table(self) -> None:
        pois: dict[str, List[PoiData]] = {
            "http://www.example.com/page1": [
                PoiData(
                    name="POI 1",
                    category="Category 1",
                    location="Location 1",
                    description="Description 1",
                ),
                PoiData(
                    name="POI 2",
                    category="Category 2",
                    location="Location 2",
                    description="Description 2",
                ),
            ],
            "http://www.example.com/page2": [
                PoiData(
                    name="POI 3",
                    category="Category 3",
                    location="Location 3",
                    description="Description 3",
                ),
            ],
        }

        expected = """| Sno | Name | Category | Location | Description |
| --- | --- | --- | --- | --- |
| 1 | POI 1 | Category 1 | Location 1 | Description 1 |
| 2 | POI 2 | Category 2 | Location 2 | Description 2 |
| 3 | POI 3 | Category 3 | Location 3 | Description 3 |"""

        actual = generate_poi_markdown_table(pois)
        assert actual == expected, actual
