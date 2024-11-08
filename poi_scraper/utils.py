from urllib.parse import urlparse

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def get_all_unique_sub_urls(webpage_url: str) -> str:
    return [
        "https://www.infofazana.hr/en/",
        # "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/paradise-for-cyclists-and-walking/", 
        "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/water-sports/", 
        # "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/for-sea-lovers/"
    ]