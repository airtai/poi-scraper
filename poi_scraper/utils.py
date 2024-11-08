from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def get_all_unique_sub_urls(webpage_url: str) -> str:
    return get_recursive_subpages(webpage_url)
    # return [
    #     "https://www.infofazana.hr/en/",
    #     "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/paradise-for-cyclists-and-walking/", 
    #     "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/water-sports/", 
    #     "https://www.infofazana.hr/en/what-to-see-do/outdoor-and-active-holidays/for-sea-lovers/",
    #     "https://www.medulinriviera.info/attractions/",

    # ]

def generate_poi_markdown_table(registered_pois: dict[str, dict[str, str]]) -> str:
        table_header = "| Sno | Name | Category | Location | Description |\n| --- | --- | --- | --- | --- |\n"
        table_rows = "\n".join(
            [
                f"| {i+1} | {name} | {poi['category']} | {poi['location']} | {poi['description']} |"
                for i, (name, poi) in enumerate(registered_pois.items())
            ]
        )
        return table_header + table_rows


# get all subpage links logic starts

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
}

MAX_SUBPAGES = 20  # Maximum number of subpages to collect
MAX_DEPTH = 2

def is_valid_url(url: str) -> bool:
    """Check if a URL is valid and returns a 200 status code."""
    try:
        response = requests.get(url, headers=headers, timeout=5)
        print(f"Checking {url}... {response.status_code}")
        return response.status_code == 200
    except requests.RequestException:
        return False

def should_skip_url(url):
    """Check if the URL contains patterns that we want to skip."""
    return '?' in url or '/#' in url

def get_valid_subpages_bfs(start_url, max_depth):
    """Use breadth-first search to get valid subpages within the same domain and path, up to max_depth and MAX_SUBPAGES."""
    base_domain = urlparse(start_url).netloc
    base_path = urlparse(start_url).path
    visited = set([start_url])  # Start with the initial URL as visited
    valid_links = set()
    queue = deque([(start_url, 0)])  # Queue stores (url, depth)

    while queue and len(valid_links) < MAX_SUBPAGES:
        url, depth = queue.popleft()
        
        # Stop if max_depth is reached
        if depth > max_depth:
            continue
        
        # Skip URLs containing unwanted patterns
        if should_skip_url(url):
            continue

        # Fetch and parse the page
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all subpage links
            for link in soup.find_all('a', href=True):
                full_url = urljoin(url, link['href'])
                link_domain = urlparse(full_url).netloc
                link_path = urlparse(full_url).path

                # Only consider links within the same domain and path
                if link_domain == base_domain and link_path.startswith(base_path) and full_url not in visited:
                    # Skip URLs containing unwanted patterns
                    if should_skip_url(full_url):
                        continue

                    visited.add(full_url)  # Mark as visited
                    # Check if the URL is valid and accessible
                    if is_valid_url(full_url):
                        valid_links.add(full_url)
                        queue.append((full_url, depth + 1))  # Add to queue for next level exploration

                    # Stop if we've reached MAX_SUBPAGES
                    if len(valid_links) >= MAX_SUBPAGES:
                        break

        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
    
    return valid_links

# Entry function with max_depth parameter
def get_recursive_subpages(url, max_depth=MAX_DEPTH):
    return get_valid_subpages_bfs(url, max_depth)
