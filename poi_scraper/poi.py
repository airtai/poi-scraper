import math
import os
import statistics
from dataclasses import dataclass, field
from queue import PriorityQueue
from typing import Any, Callable, List, Literal, Optional, Union
from urllib.parse import urlparse

from autogen import AssistantAgent
from autogen.agentchat.chat import ChatResult

from poi_scraper.agents.custom_web_surfer import CustomWebSurferTool
from poi_scraper.poi_types import (
    CustomWebSurferAnswer,
    PoiData,
    ValidatePoiAgentProtocol,
)
from poi_scraper.utils import filter_same_domain_urls


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
    system_message: str = """You are a web surfer agent tasked with collecting Points of Interest (POIs) from a given webpage.

Instructions:
    1. Scrape the webpage:
        - You MUST use the 'Web_Surfer_Tool' to scrape the webpage. This tool will extract POIs and URLs from the webpage for you.
        - Focus only on the provided webpage. Do not explore child pages or external links.
        - Ensure you scroll through the entire webpage to capture all visible content.

    2. Collect POIs:

        - Identify notable POIs, such as landmarks, attractions, or places where people can visit or hang out.
        - For each POI, gather the following details:
            - Name: The name of the POI.
            - Location: Where the POI is located (e.g., city or region).
            - Category: The type of POI (e.g., Beach, Park, Museum).
            - Description: A short summary of the POI.

    3. Identify URLs:

        - List all URLs found on the page.
        - Assign a relevance score (1-5) to each URL:
            - 5: Very likely to lead to more POIs (e.g., “places,” “activities,” “landmarks”).
            - 1: Unlikely to lead to POIs (e.g., “contact-us,” “terms-and-conditions”).

Output format:

    - Return the data as a JSON object containing:
        - pois_found: A list of POIs with their details.
        - urls_found: A dictionary of URLs with their relevance scores.

    - Example Output:
        {
            "task": "Collect POIs and URLs from the webpage",
            "is_successful": true,
            "pois_found": [
                {
                    "name": "Golden Gate Bridge",
                    "location": "San Francisco",
                    "category": "Landmark",
                    "description": "Iconic suspension bridge..."
                }
            ],
            "urls_found": {
                "https://example.com/places": 5,
                "https://example.com/about": 3
            }
        }

Common Mistakes to Avoid:
    - Do not include any additional text or formatting in the final JSON output.
"""

    @property
    def example_answer(self) -> CustomWebSurferAnswer:
        return CustomWebSurferAnswer.get_example_answer()

    @property
    def error_message(self) -> str:
        return f"""Please output the JSON-encoded answer only in the following format before trying to terminate the chat.

IMPORTANT:
  - NEVER enclose JSON-encoded answer in any other text or formatting including '```json' ... '```' or similar!
  - Do not include any additional text or formatting in the final JSON output.

EXAMPLE:

{self.example_answer.model_dump_json()}

NEGATIVE EXAMPLES:

1. Do NOT include 'TERMINATE' in the same message as the JSON-encoded answer!

{self.example_answer.model_dump_json()}

TERMINATE

2. Do NOT include triple backticks or similar!

```json
{self.example_answer.model_dump_json()}
```

THE LAST ERROR MESSAGE:

{self.last_is_termination_msg_error}
"""

    def _is_termination_msg(self, msg: dict[str, Any]) -> bool:
        try:
            CustomWebSurferAnswer.model_validate_json(msg["content"])
            return True
        except Exception as e:
            self.last_is_termination_msg_error = str(e)
            return False

    def _check_for_error(self, chat_result: ChatResult) -> Optional[str]:
        messages = [msg["content"] for msg in chat_result.chat_history]
        last_message = messages[-1]

        try:
            CustomWebSurferAnswer.model_validate_json(last_message)
        except Exception:
            return self.error_message

        return None

    def create(
        self,
    ) -> Callable[[str], tuple[list[PoiData], dict[str, Literal[1, 2, 3, 4, 5]]]]:
        """Factory method to create a scraper function.

        Returns:
            Callable that takes a URL and returns tuple of:
            - List of POI data dictionaries
            - List of tuples containing (url, relevance_score)
        """
        assistant_agent = AssistantAgent(
            name="Assistant_Agent",
            system_message="You are a helpful agent",
            llm_config=self.llm_config,
            human_input_mode="NEVER",
            is_termination_msg=self._is_termination_msg,
        )

        web_surfer_agent = AssistantAgent(
            name="WebSurfer_Agent",
            system_message=self.system_message,
            llm_config=self.llm_config,
            human_input_mode="NEVER",
        )

        web_surfer_tool = CustomWebSurferTool(
            name_prefix="Web_Surfer_Tool",
            llm_config=self.llm_config,
            summarizer_llm_config=self.llm_config,
            bing_api_key=os.getenv("BING_API_KEY"),
        )

        web_surfer_tool.register(
            caller=web_surfer_agent,
            executor=assistant_agent,
        )

        def scrape(url: str) -> tuple[list[PoiData], dict[str, Literal[1, 2, 3, 4, 5]]]:
            """Scrape the URL for POI data and relevant urls."""
            message: Optional[str] = f"Please collect all POIs and urla from {url}"
            clear_history = True

            while message is not None:
                chat_result = assistant_agent.initiate_chat(
                    web_surfer_agent,
                    message=message,
                    summary_method="reflection_with_llm",
                    max_turns=3,
                    clear_history=clear_history,
                )
                message = self._check_for_error(chat_result)
                clear_history = False

            return self._transform_chat_result(chat_result)

        return scrape

    def _transform_chat_result(
        self, chat_result: ChatResult
    ) -> tuple[list[PoiData], dict[str, Literal[1, 2, 3, 4, 5]]]:
        messages = [msg["content"] for msg in chat_result.chat_history]
        last_message = messages[-1]

        websurfer_answer_obj = CustomWebSurferAnswer.model_validate_json(last_message)
        return websurfer_answer_obj.pois_found, websurfer_answer_obj.urls_found


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
        self.base_domain = urlparse(base_url).netloc
        self.url_queue: PriorityQueue[Link] = PriorityQueue()
        self.pois: dict[str, dict[str, Union[str, Optional[str]]]] = {}
        self.urls_with_less_score: dict[str, int] = {}

    def _register_pois(self, pois: List[PoiData]) -> None:
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

    def _add_new_links_to_queue(
        self, link: Link, min_score: Optional[int] = None
    ) -> None:
        """Add unvisited links to queue if they meet score threshold."""
        queue_urls = {link.url for link in self.url_queue.queue}

        for new_link in link.site.urls.values():
            if new_link.visited or new_link.url in queue_urls:
                continue

            if not min_score or new_link.score >= min_score:
                self.url_queue.put(new_link)
            else:
                self.urls_with_less_score[new_link.url] = new_link.estimated_score

    def process(
        self, scraper: Scraper, min_score: Optional[int] = None
    ) -> tuple[dict[str, dict[str, Union[str, Optional[str]]]], Site]:
        # Create scraper function
        scrape = scraper.create()

        # Initialize with base URL
        homepage = Link.create(parent=None, url=self.base_url, estimated_score=5)

        # Add the homepage to the queue
        self.url_queue.put(homepage)

        while not self.url_queue.empty():
            link = self.url_queue.get()

            # Process URL using AI
            pois_found, urls_found = scrape(link.url)

            # Remove urls that are not from the same domain
            same_domain_urls = filter_same_domain_urls(urls_found, self.base_domain)

            # Record the visit
            link.record_visit(
                poi_found=len(pois_found) > 0,
                urls_found=same_domain_urls,
            )

            # Register the POIs found
            self._register_pois(pois_found)

            # Add the new links to the queue
            self._add_new_links_to_queue(link, min_score)

        return self.pois, homepage.site
