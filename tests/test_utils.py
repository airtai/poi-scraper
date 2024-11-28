import unittest
from typing import Literal, Tuple

from poi_scraper.utils import filter_same_domain_urls, is_valid_url


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
