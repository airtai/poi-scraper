from typing import Optional, Union
from urllib.parse import urlparse


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
