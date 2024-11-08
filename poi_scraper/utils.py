def validate_url(webpage_url: str) -> bool:
    return True


def get_all_unique_sub_urls(webpage_url: str) -> str:
    return [
        "https://www.infofazana.hr/en/",
        # "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/paradise-for-cyclists-and-walking/", 
        "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/water-sports/", 
        # "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/for-sea-lovers/"
    ]