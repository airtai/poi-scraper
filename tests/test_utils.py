import unittest
from typing import Literal

from poi_scraper.utils import filter_same_domain_urls


class TestFilterSameDomainUrls(unittest.TestCase):
    def test_filter_same_domain_urls(self) -> None:
        urls_found: dict[str, Literal[1, 2, 3, 4, 5]] = {
            "http://example.com/page1": 1,
            "http://example.com/page2": 2,
            "http://otherdomain.com/page1": 3,
        }
        expected = {
            "http://example.com/page1": 1,
            "http://example.com/page2": 2,
        }

        actual = filter_same_domain_urls(urls_found, "example.com")
        assert actual == expected
