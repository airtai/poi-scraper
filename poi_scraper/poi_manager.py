from typing import Any, Optional
from urllib.parse import urlparse

from poi_scraper.poi_types import (
    Link,
    PageStats,
    PoiData,
    ScraperFactoryProtocol,
    SessionMemory,
    ValidatePoiAgentProtocol,
)


class PoiManager:
    def __init__(
        self,
        base_url: str,
        poi_validator: ValidatePoiAgentProtocol,
        max_pages: int = 100,
    ):
        """Initialize the POIManager with a base URL.

        This constructor sets up the initial state of the POIManager, including
        the base URL, domain, visited URLs set, URL priority queue, POI list,
        and lists for storing links with scores.

        Args:
            base_url (str): The base URL to start managing points of interest from.
            poi_validator (ValidatePoiAgentProtocol): The agent to validate points of interest.
            max_pages (int): The maximum number of pages to process. Defaults to 100.
        """
        self.base_url = base_url
        self.poi_validator = poi_validator
        self.base_domain = urlparse(base_url).netloc
        self.session_memory = SessionMemory(base_url)
        self.max_pages = max_pages

    def _initialize_page_stats(self, current_url: str) -> None:
        self.session_memory.pages[current_url] = PageStats(
            pois=[],
            description="",
            children_success_rate=0.0,
            last_n_pages_poi_count=[],
            unvisited_links=[],
        )

    def register_poi(self, poi: PoiData) -> str:
        """Register a new Point of Interest (POI)."""
        poi_validation_result = self.poi_validator.validate(
            poi.name, poi.description, poi.category, poi.location
        )

        if not poi_validation_result.is_valid:
            return f"POI validation failed for: {poi.name, poi.description}"

        if poi.current_url not in self.session_memory.pages:
            self._initialize_page_stats(poi.current_url)

        self.session_memory.pages[poi.current_url].pois.append(poi)
        return f"POI registered: {poi.name}, Category: {poi.category}, Location: {poi.location}"

    def register_link(
        self, current_url: str, outgoing_url: str, score: int, justification: str
    ) -> str:
        """Register a new link with its AI score."""
        if current_url not in self.session_memory.pages:
            self._initialize_page_stats(current_url)

        self.session_memory.pages[current_url].unvisited_links.append(
            Link(url=outgoing_url, initial_score=score, justification=justification)
        )

        return f"Link registered: {outgoing_url}, AI score: {score}"

    def _format_available_links(self) -> str:
        """Format all available unvisited links across all pages for LLM."""
        available_links = [
            f"URL: {link.url}\n"
            f"Found on: {page_url}\n"
            f"Initial Score: {link.initial_score}\n"
            f"Justification: {link.justification}\n"
            for page_url, page_stats in self.session_memory.pages.items()
            for link in page_stats.unvisited_links
            if link.url not in self.session_memory.visited_urls
        ]
        return "\n".join(available_links)

    # def _format_pattern_stats(self) -> str:
    #     """Format pattern statistics for LLM to analyze."""
    #     stats = []
    #     pattern_stats = self.session_memory.patterns.items()
    #     for pattern, data in pattern_stats:
    #         success_rate = (
    #             data.success_count / (data.success_count + data.failure_count)
    #             if data.success_count + data.failure_count > 0
    #             else 0
    #         )
    #         stats.append(f"Pattern: {pattern}\nSuccess Rate: {success_rate}\n")
    #     return "\n".join(stats)

    # def _format_recent_performance(self) -> str:
    #     """Format recent performance statistics for LLM to analyze."""
    #     performance = []
    #     for url, stats in self.session_memory.pages.items():
    #         performance.append(f"URL: {url}\nPOI Count: {len(stats.pois)}\nChildren Success Rate: {stats.children_success_rate}\nRecent Child POI Counts: {stats.last_n_pages_poi_count}\n")
    #     return "\n".join(performance)

    def process(self, scraper_factory: ScraperFactoryProtocol) -> str:
        """Main processing loop for POI extraction."""
        # Create scraper function
        scraper = scraper_factory.create_scraper(self)
        pages_visited = 0

        while pages_visited < self.max_pages:
            try:
                # The scraper will:
                # 1. Look at session_memory to decide which URL to scrape
                # 2. Scrape that URL
                # 3. Return results including which URL was scraped
                scraping_result = scraper(self.session_memory)

                # Update memory with current page results
                self._update_memory(scraping_result)

                # Check if the LLM has made a decision to terminate. Implies that the LLM has found all the POIs in the
                # website and does not need to continue crawling
                if scraping_result.decision == "TERMINATE":
                    break

                pages_visited += 1

            except Exception:  # nosec
                # print("Error processing URL")
                # print(e)
                # raise e
                continue

        return self._generate_report()

    def _update_memory(self, scraping_result: Any) -> None:
        """Update session memory after scraping a page.

        Args:
            scraping_result: Dictionary containing:
                - current_url: str (URL that was actually scraped)
                - description: str (page summary)
        """
        current_url = scraping_result.current_url

        # 1. Mark URL as visited
        self.session_memory.visited_urls.add(current_url)

        # 2. Create new page stats
        pois = self.session_memory.pages[current_url].pois
        self.session_memory.pages[current_url] = PageStats(
            pois=pois,
            description=scraping_result.description,
            children_success_rate=0.0,
            last_n_pages_poi_count=[],
            unvisited_links=self.session_memory.pages[current_url].unvisited_links,
        )

        # 3. Update parent's statistics if parent exists
        parent_url = self._find_parent_url(current_url)
        if parent_url:
            # Get the parent page stats
            parent_stats = self.session_memory.pages[parent_url]

            # Update last_n_pages_poi_count
            parent_stats.last_n_pages_poi_count.append(len(pois))
            # if the length exceeds 2, then keep only the last 2 elements
            if len(parent_stats.last_n_pages_poi_count) > 2:
                parent_stats.last_n_pages_poi_count = (
                    parent_stats.last_n_pages_poi_count[-2:]
                )

            # Update children_success_rate
            successful_children = sum(
                1
                for link in parent_stats.unvisited_links
                if link.url in self.session_memory.visited_urls
                and len(self.session_memory.pages[link.url].pois)
                > 0  # if at least one poi is found in the child page
            )

            total_visited_children = sum(
                1
                for link in parent_stats.unvisited_links
                if link.url in self.session_memory.visited_urls
            )

            parent_stats.children_success_rate = (
                successful_children / total_visited_children
                if total_visited_children > 0
                else 0.0
            )

        # 4. Update pattern statistics
        if len(pois) > 0:
            self.session_memory.patterns[scraping_result.current_url].success_count += 1
        else:
            self.session_memory.patterns[scraping_result.current_url].failure_count += 1

    def _find_parent_url(self, current_url: str) -> Optional[str]:
        """Find parent URL by checking which page has this URL in its unvisited_links."""
        for url, page_stats in self.session_memory.pages.items():
            if any(link.url == current_url for link in page_stats.unvisited_links):
                return url
        return None  # For homepage or if parent not found

    def _generate_report(self) -> str:
        """Generate a simple report in markdown format showing URLs and their POI counts,ordered by number of POIs found."""
        # Calculate basic statistics
        total_pois = sum(len(page.pois) for page in self.session_memory.pages.values())
        total_pages = len(self.session_memory.visited_urls)

        # Create sorted list of pages by POI count
        page_stats = [
            {"url": url, "poi_count": len(stats.pois)}
            for url, stats in self.session_memory.pages.items()
        ]
        page_stats.sort(key=lambda x: x["poi_count"], reverse=True)  # type: ignore

        # Generate Markdown Report
        report = f"""# Crawl Results for {self.base_url}

Total Pages Crawled: {total_pages}
Total POIs Found: {total_pois}

## POIs Found Per Page
| URL | POIs Found |
|-----|------------|
"""
        # Add rows for each page
        for page in page_stats:
            report += f"| {page['url']} | {page['poi_count']} |\n"

        return report
