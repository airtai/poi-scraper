from urllib.parse import urlparse

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def get_all_unique_sub_urls(webpage_url: str) -> str:
    return [
        # "https://www.infofazana.hr/en/",
        # "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/paradise-for-cyclists-and-walking/", 
        "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/water-sports/", 
        # "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/for-sea-lovers/",
        # "https://www.medulinriviera.info/attractions/",

    ]

def generate_poi_markdown_table(registered_pois: dict[str, dict[str, str]]) -> str:
        table_header = "| Sno | Name | Category | Location | Description |\n| --- | --- | --- | --- | --- |\n"
        table_rows = "\n".join(
            [
                f"| {i+1} | {name} | {poi['category']} | {poi['location']} | {poi['description']} |"
                for i, (name, poi) in enumerate(registered_pois.items())
            ]
        )
        return table_header + table_rows