from typing import Literal, Optional, Union
from urllib.parse import urlparse

from fastagency import UI


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def generate_poi_markdown_table(
    registered_pois: dict[str, dict[str, Union[str, Optional[str]]]],
) -> str:
    table_header = "| Sno | Name | Category | Location | Description |\n| --- | --- | --- | --- | --- |\n"
    table_rows = "\n".join(
        [
            f"| {i+1} | {name} | {poi['category']} | {poi['location']} | {poi['description']} |"
            for i, (name, poi) in enumerate(registered_pois.items())
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
    urls_found: dict[str, Literal[1, 2, 3, 4, 5]], base_domain: str
) -> dict[str, Literal[1, 2, 3, 4, 5]]:
    return {
        url: score
        for url, score in urls_found.items()
        if urlparse(url).netloc == base_domain
    }
