import math
import os
import statistics
from dataclasses import dataclass, field
from queue import PriorityQueue
from typing import Any, Callable, List, Literal, Optional, Union

from autogen import AssistantAgent

from poi_scraper.agents.custom_web_surfer import CustomWebSurferTool
from poi_scraper.poi_types import (
    PoiData,
    ValidatePoiAgentProtocol,
)


@dataclass
class Site:
    urls: dict[str, "Link"]

    def get_url_scores(self, decimals: int = 5) -> dict[str, float]:
        """Return the scores of all the URLs in the site.

        Returns:
            dict[str, float]: The scores of all the URLs in the site.

        """
        return {url: round(link.score, decimals) for url, link in self.urls.items()}


@dataclass
class Link:
    site: Site
    url: str
    estimated_score: Literal[1, 2, 3, 4, 5]
    parents: set["Link"]

    # to be set after visiting the link
    visited: bool = False
    children: list["Link"] = field(default_factory=list)
    children_visited: int = 0
    children_poi_found: int = 0

    # add hash function to make Link hashable
    def __hash__(self) -> int:
        """Return the hash of the link."""
        return hash(self.url)

    def __lt__(self, other: "Link") -> bool:
        """Compare two Link objects for less-than based on their scores.

        This method is used to order Link objects in a priority queue,
        where higher scores have higher priority.

        Args:
            other (Link): The other Link object to compare against.

        Returns:
            bool: True if the score of this Link is greater than the score of the other Link, False otherwise.
        """
        return self.score > other.score  # Reverse for priority queue (highest first)

    @classmethod
    def create(
        cls, parent: Optional["Link"], url: str, estimated_score: Literal[1, 2, 3, 4, 5]
    ) -> "Link":
        """Create a new link.

        Params:
            parent (Link): The parent link.
            url (str): The URL of the link.
            estimated_score (Literal[1, 2, 3, 4, 5]): The estimated score of the link.

        Returns:
            Link: The new link.

        """
        # check if we already have a link for this URL
        if parent and url in parent.site.urls:
            site = parent.site
            link = parent.site.urls[url]
            link.parents.add(parent)
        else:
            site = Site(urls={}) if parent is None else parent.site
            parents = {parent} if parent else set()
            link = cls(
                url=url, estimated_score=estimated_score, parents=parents, site=site
            )
        site.urls[url] = link

        return link

    @property
    def _parent_correction(self) -> float:
        # no visits to my children => no correction of my estimates
        if self.children_visited == 0:
            return 0

        # goes from -0.5 to 0.5 as children_poi_found goes from 0 to children_visited
        correction = 1 * (self.children_poi_found / self.children_visited - 0.5)

        # goes from 0.2 to 1 as children_visited goes from 1 to infinity
        confidence = 1 - math.exp(-0.2 * self.children_visited)

        return correction * confidence

    @property
    def score(self) -> float:
        """Calculate the score of the link.

        Returns:
            float: The score of the link, or None if the score cannot be calculated.

        """
        # no parents => no correction
        if not self.parents:
            return self.estimated_score

        correction = statistics.mean(
            parent._parent_correction for parent in self.parents
        )

        # corrects the estimated score based on the correction and confidence (+/- 0.5)
        return self.estimated_score + correction

    def _record_children_visit(self, poi_found: bool) -> None:
        """Record that a child link has been visited.

        Params:
            poi_found (bool): Whether the child link contains a point of interest.

        """
        self.children_visited += 1
        if poi_found:
            self.children_poi_found += 1

    def record_visit(
        self, poi_found: bool, urls_found: dict[str, Literal[1, 2, 3, 4, 5]]
    ) -> None:
        """Record that the link has been visited.

        If the link has a parent, increment the parent's children_visited count.

        Params:
            poi_found (bool): Whether the link contains a point of interest.
            children (set[Link]): The children of the link.
        """
        self.visited = True
        self.children = [
            Link.create(
                url=url,
                estimated_score=estimated_score,
                parent=self,
            )
            for url, estimated_score in urls_found.items()
        ]
        for parent in self.parents:
            parent._record_children_visit(poi_found)


@dataclass
class Scraper:
    """A scraper factory that creates a callable scraper function."""

    llm_config: dict[str, Any]
    system_message: str = """You are a web surfer agent..."""  # your existing message

    def create(
        self,
    ) -> Callable[[str], tuple[list[PoiData], dict[str, Literal[1, 2, 3, 4, 5]]]]:
        """Factory method to create a scraper function.

        Returns:
            Callable that takes a URL and returns tuple of:
            - List of POI data dictionaries
            - List of tuples containing (url, relevance_score)
        """
        assistant_agent = self._create_assistant()
        web_surfer_agent = self._create_web_surfer_agent()
        web_surfer_tool = self._create_web_surfer_tool()

        web_surfer_tool.register(
            caller=web_surfer_agent,
            executor=assistant_agent,
        )

        def scrape(url: str) -> tuple[list[PoiData], dict[str, Literal[1, 2, 3, 4, 5]]]:
            """Scrape the URL for POI data and relevant links."""
            message = f"Please collect all POIs and links from {url}"
            result = assistant_agent.initiate_chat(
                web_surfer_agent,
                message=message,
                summary_method="reflection_with_llm",
                max_turns=3,
            )
            # todo: Make sure the model returns the formatted output
            return self._parse_result(result.summary)

        return scrape

    def _parse_result(
        self, summary: str
    ) -> tuple[list[PoiData], dict[str, Literal[1, 2, 3, 4, 5]]]:
        # Parse the summary to extract POI data and links
        return [], {}

    def _create_assistant(self) -> AssistantAgent:
        """Creates the assistant agent."""
        return AssistantAgent(
            name="Assistant_Agent",
            system_message="You are a helpful agent",
            llm_config=self.llm_config,
            human_input_mode="NEVER",
        )

    def _create_web_surfer_agent(self) -> AssistantAgent:
        """Creates the web surfer agent."""
        return AssistantAgent(
            name="WebSurfer_Agent",
            system_message=self.system_message,
            llm_config=self.llm_config,
            human_input_mode="NEVER",
        )

    def _create_web_surfer_tool(self) -> CustomWebSurferTool:
        """Creates the web surfer tool."""
        return CustomWebSurferTool(
            name_prefix="Web_Surfer_Tool",
            llm_config=self.llm_config,
            summarizer_llm_config=self.llm_config,
            bing_api_key=os.getenv("BING_API_KEY"),
        )


class PoiManager:
    def __init__(self, base_url: str, poi_validator: ValidatePoiAgentProtocol):
        """Initialize the POIManager with a base URL.

        This constructor sets up the initial state of the POIManager, including
        the base URL, domain, visited URLs set, URL priority queue, POI list,
        and lists for storing links with scores.

        Args:
            base_url (str): The base URL to start managing points of interest from.
            poi_validator (ValidatePoiAgentProtocol): The agent to validate points of interest.
        """
        self.base_url = base_url
        self.poi_validator = poi_validator
        # self.base_domain = urlparse(base_url).netloc
        self.url_queue: PriorityQueue[Link] = PriorityQueue()
        self.pois: dict[str, dict[str, Union[str, Optional[str]]]] = {}

    def register_pois(self, pois: List[PoiData]) -> None:
        """Register the new Point of Interests (POI)."""
        for poi in pois:
            poi_validation_result = self.poi_validator.validate(
                poi.name, poi.description, poi.category, poi.location
            )

            if poi_validation_result.is_valid:
                self.pois[poi.name] = {
                    "description": poi.description,
                    "category": poi.category,
                    "location": poi.location,
                }

    def process(
        self, scraper: Scraper
    ) -> tuple[dict[str, dict[str, Union[str, Optional[str]]]], Site]:
        # Create scraper function
        scrape_func = scraper.create()

        # Initialize with base URL
        homepage = Link.create(parent=None, url=self.base_url, estimated_score=5)

        # Add the homepage to the queue
        self.url_queue.put(homepage)
        while not self.url_queue.empty():
            link = self.url_queue.get()

            # Process URL using AI
            pois_found, urls_found = scrape_func(link.url)

            # Record the visit
            link.record_visit(
                poi_found=len(pois_found) > 0,
                urls_found=urls_found,
            )

            # Register the POIs found
            self.register_pois(pois_found)

            # Add the new links to the queue
            for new_link in link.site.urls.values():
                if not new_link.visited:
                    exists_in_queue = any(
                        link.url == new_link.url for link in self.url_queue.queue
                    )
                    if not exists_in_queue:
                        self.url_queue.put(new_link)

        return self.pois, homepage.site
