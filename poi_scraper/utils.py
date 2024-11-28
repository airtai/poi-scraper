from typing import List, Literal, Tuple
from urllib.parse import urlparse

from fastagency import UI

from poi_scraper.poi_types import PoiData


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return (
            result.scheme in ["http", "https"]
            and bool(result.netloc)
            and result.netloc.startswith("www.")
        )
    except Exception:
        return False


def generate_poi_markdown_table(
    pois: dict[str, list[PoiData]],
) -> str:
    table_header = "| Sno | URL | Name | Category | Location | Description |\n| --- | --- | --- | --- | --- | --- |\n"
    table_rows = "\n".join(
        [
            f"| {i+1} | {url} | {poi.name} | {poi.category} | {poi.location} | {poi.description} |"
            for i, (url, poi_list) in enumerate(pois.items())
            for poi in poi_list
        ]
    )
    return table_header + table_rows


def get_url_from_user(ui: UI) -> str:
    while True:
        webpage_url = ui.text_input(
            sender="Workflow",
            recipient="User",
            prompt="I can collect Points of Interest (POI) data from any webpage—just share the link with me!",
        )
        if is_valid_url(webpage_url):
            break
        ui.text_message(
            sender="Workflow",
            recipient="User",
            body="The provided URL is not valid. Please enter a valid URL. Example: https://www.example.com",
        )
    return str(webpage_url)


def filter_same_domain_urls(
    urls_found: List[Tuple[str, Literal[1, 2, 3, 4, 5]]], base_domain: str
) -> dict[str, Literal[1, 2, 3, 4, 5]]:
    base_domain_parsed = urlparse(base_domain)
    base_domain_netloc = base_domain_parsed.netloc or base_domain_parsed.path
    return {
        url: score
        for url, score in urls_found
        if urlparse(url).netloc == base_domain_netloc
    }
