import math
import os
import pickle
import statistics
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple
from urllib.parse import urlparse

from autogen import AssistantAgent, register_function
from fastagency.logging import get_logger

from poi_scraper.agents.custom_web_surfer import CustomWebSurferTool
from poi_scraper.poi_types import (
    PoiData,
    ValidatePoiAgentProtocol,
)
from poi_scraper.utils import filter_same_domain_urls, get_connection

logger = get_logger(__name__)


@dataclass
class Site:
    urls: Dict[str, "Link"]

    def get_url_scores(self, decimals: int = 5) -> Dict[str, float]:
        """Return the scores of all the URLs in the site.

        Returns:
            Dict[str, float]: The scores of all the URLs in the site.

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
        self, poi_found: bool, urls_found: Dict[str, Literal[1, 2, 3, 4, 5]]
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

    llm_config: Dict[str, Any]
    system_message: str = """You are a web surfer agent tasked with collecting Points of Interest (POIs) and URLs from a given webpage.

Instructions:
    1. Scrape the webpage:

        - You MUST use the 'Web_Surfer_Tool' to scrape the webpage. This tool will extract POIs and URLs from the webpage for you.
        - Focus only on the provided webpage. Do not explore child pages or external links.
        - Ensure you scroll through the entire webpage to capture all visible content.
        - NEVER call `register_poi` and `register_url` without visiting the full webpage. This is a very important instruction and you will be penalised if you do so.
        - After visiting the webpage and identifying the POIs, you MUST call the `register_poi` function to record the POI.
        - You need to call `register_poi` function for each POI found on the webpage. Do not call the function with list of all POIs at once.
            - Correct example: `register_poi({"name": "POI1", "location": "City", "category": "Park", "description": "Description"})`
            - Incorrect example: `register_poi([{"name": "POI1", "location": "City", "category": "Park", "description": "Description"}, {"name": "POI2", "location": "City", "category": "Park", "description": "Description"}])`
        - If you find any new urls on the webpage, you MUST call the `register_url` function to record the url along with the score (1 - 5) indicating the relevance of the link to the POIs.

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

Termination:
    - Once you have collected all the POIs and URLs from the webpage, you can terminate the chat by sending only "TERMINATE" as the message.
"""

    def _is_termination_msg(self, msg: Dict[str, Any]) -> bool:
        """Check if the message is a termination message."""
        # check the view port here

        return bool(msg["content"] == "TERMINATE")

    def create(self, poi_manager: "PoiManager") -> Callable[[str], str]:
        """Factory method to create a scraper function.

        Args:
            poi_manager (PoiManager): The POI manager instance for registering POIs and URLs.

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

        # register websurfer tool
        web_surfer_tool.register(
            caller=web_surfer_agent,
            executor=assistant_agent,
        )

        # Register the functions to register POIs
        def register_poi(
            name: str, description: str, category: str, location: Optional[str] = None
        ) -> str:
            try:
                poi = PoiData(
                    name=name,
                    description=description,
                    category=category,
                    location=location,
                )
                poi_manager.register_poi(poi)
                return f"POI registered: {name}"
            except Exception as e:
                logger.info(f"Failed to register POI: {e!s}")
                return f"Failed to register POI: {e!s}"

        register_function(
            register_poi,
            caller=web_surfer_agent,
            executor=assistant_agent,
            name="register_poi",
            description="Register Point of Interest (POI)",
        )

        # Register the functions to register URLs with scores
        def register_url(url: str, score: Literal[1, 2, 3, 4, 5]) -> str:
            poi_manager.register_url(url, score)
            return f"Link registered: {url}, AI score: {score}"

        register_function(
            register_url,
            caller=web_surfer_agent,
            executor=assistant_agent,
            name="register_url",
            description="Register new url with score",
        )

        def scrape(url: str) -> str:
            """Scrape the URL for POI data and relevant urls."""
            message = f"Collect all the Points of Interest (POIs) from the webpage {url}, along with any URLs that are likely to lead to additional POIs."

            chat_result = assistant_agent.initiate_chat(
                web_surfer_agent,
                message=message,
                summary_method="reflection_with_llm",
                max_turns=3,
            )

            return str(chat_result.summary)

        return scrape


@dataclass
class WorkflowState:
    """Contains the complete state of a workflow."""

    urls: List[Link]
    homepage: Link
    all_urls_with_scores: Dict[str, List[Tuple[str, Literal[1, 2, 3, 4, 5]]]]
    urls_with_less_score: Dict[str, int]


class PoiDatabase:
    def __init__(self, db_path: Path) -> None:
        """Initialize the POI database."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database."""
        create_tables_sql = """
        -- Workflows table with status and queue state
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            status TEXT NOT NULL,
            queue_state BLOB,  -- Stores serialized queue and homepage
            all_urls_scores BLOB,   -- Stores all_urls_with_scores dictionary
            less_score_urls BLOB,  -- Stores urls_with_less_score dictionary
            UNIQUE(name)
        );

        -- POIs table
        CREATE TABLE IF NOT EXISTS pois (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        );

        -- Create index for faster POI lookups
        CREATE INDEX IF NOT EXISTS idx_pois_workflow ON pois(workflow_id, name);
        """
        with get_connection(self.db_path) as conn:
            for statement in create_tables_sql.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.commit()

    def create_or_get_workflow(
        self, name: str, base_url: str
    ) -> Tuple[int, Optional[WorkflowState]]:
        """Create a new workflow or get existing one with all state."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, queue_state, all_urls_scores, less_score_urls FROM workflows WHERE name = ?",
                (name,),
            )
            workflow = cursor.fetchone()

            if workflow:
                if workflow["queue_state"] is not None:
                    queue_state = pickle.loads(  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                        workflow["queue_state"]
                    )
                    url_scores = (
                        pickle.loads(  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                            workflow["all_urls_scores"]
                        )
                        if workflow["all_urls_scores"]
                        else {}
                    )
                    less_score_urls = (
                        pickle.loads(  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                            workflow["less_score_urls"]
                        )
                        if workflow["less_score_urls"]
                        else {}
                    )

                    return workflow["id"], WorkflowState(
                        urls=queue_state[0],
                        homepage=queue_state[1],
                        all_urls_with_scores=url_scores,
                        urls_with_less_score=less_score_urls,
                    )
                return workflow["id"], None

            # Create new workflow if it doesn't exist
            cursor = conn.execute(
                """INSERT INTO workflows (
                        name,base_url, status, queue_state, all_urls_scores, less_score_urls
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                (name, base_url, "in_progress", None, None, None),
            )

            conn.commit()
            return cursor.lastrowid, None  # type: ignore

    def save_workflow_state(self, workflow_id: int, state: WorkflowState) -> None:
        """Save the state of the workflow in the database."""
        with get_connection(self.db_path) as conn:
            queue_state = pickle.dumps(  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                (state.urls, state.homepage)
            )
            url_scores = pickle.dumps(  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                state.all_urls_with_scores
            )
            less_score_urls = pickle.dumps(  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                state.urls_with_less_score
            )

            conn.execute(
                """UPDATE workflows SET queue_state = ?, all_urls_scores = ?, less_score_urls = ? WHERE id = ?""",
                (queue_state, url_scores, less_score_urls, workflow_id),
            )
            conn.commit()

    def is_poi_deplicate(self, workflow_id: int, poi: PoiData) -> bool:
        """Check if the POI already exists in the database."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM pois WHERE workflow_id = ? AND name = ? LIMIT 1",
                (workflow_id, poi.name),
            )
            return bool(cursor.fetchone())

    def add_poi(self, workflow_id: int, url: str, poi: PoiData) -> None:
        """Add a new POI to the database."""
        if self.is_poi_deplicate(workflow_id, poi):
            return

        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT INTO pois (workflow_id, url, name, description, category, location) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    workflow_id,
                    url,
                    poi.name,
                    poi.description,
                    poi.category,
                    poi.location,
                ),
            )
            conn.commit()

    def get_all_pois(self, workflow_id: int) -> Dict[str, List[PoiData]]:
        """Retrieve all POIs for a workflow grouped by URL."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT url, name, description, category, location FROM pois WHERE workflow_id = ? ORDER BY url",
                (workflow_id,),
            )
            pois = cursor.fetchall()

        ret_val = {}
        # Group POIs by URL
        for url, group_pois in groupby(pois, key=lambda x: x["url"]):
            ret_val[url] = [
                PoiData(
                    name=poi["name"],
                    description=poi["description"],
                    category=poi["category"],
                    location=poi["location"],
                )
                for poi in group_pois
            ]
        return ret_val

    def mark_workflow_completed(self, workflow_id: int) -> None:
        """Mark workflow as completed and clear queue state."""
        with get_connection(self.db_path) as conn:
            conn.execute(
                """UPDATE workflows SET status = 'completed',
                    queue_state = NULL,
                    all_urls_scores = NULL,
                    less_score_urls = NULL WHERE id = ?""",
                (workflow_id,),
            )
            conn.commit()


class PoiManager:
    def __init__(
        self,
        base_url: str,
        poi_validator: ValidatePoiAgentProtocol,
        workflow_name: str,
        db_path: Path,
    ):
        """Initialize the POIManager with a base URL.

        This constructor sets up the initial state of the POIManager, including
        the base URL, domain, visited URLs set, URL priority queue, POI list,
        and lists for storing links with scores.

        Args:
            base_url (str): The base URL to start managing points of interest from.
            poi_validator (ValidatePoiAgentProtocol): The agent to validate points of interest.
            workflow_name (str): The name of the workflow.
            db_path (Path): The path to the database file.
        """
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.poi_validator = poi_validator
        self.db = PoiDatabase(db_path)

        # Initialize or resume workflow with all state
        self.workflow_id, state = self.db.create_or_get_workflow(
            workflow_name, base_url
        )

        if state:
            self.urls = state.urls
            self.homepage = state.homepage
            self._all_urls_with_scores = state.all_urls_with_scores
            self.urls_with_less_score = state.urls_with_less_score

        else:
            self.homepage = Link.create(parent=None, url=base_url, estimated_score=5)
            self.urls = [self.homepage]
            self._all_urls_with_scores = {}
            self.urls_with_less_score = {}
            self._save_state_in_db()

        self.current_url = ""

    def _save_state_in_db(self) -> None:
        # Save new workflow state in the database
        self.db.save_workflow_state(
            self.workflow_id,
            WorkflowState(
                urls=self.urls,
                homepage=self.homepage,
                all_urls_with_scores=self._all_urls_with_scores,
                urls_with_less_score=self.urls_with_less_score,
            ),
        )

    def _add_url(self, link: Link, min_score: Optional[int] = None) -> None:
        """Add unvisited links to queue if they meet score threshold."""
        if link.visited or link.url in {url.url for url in self.urls}:
            return

        if not min_score or link.score >= min_score:
            self.urls.append(link)

            # Keep urls sorted by score (descending)
            self.urls.sort(key=lambda x: x.score, reverse=True)

        else:
            self.urls_with_less_score[link.url] = link.estimated_score

    def register_poi(self, poi: PoiData) -> str:
        """Register a new Point of Interest (POI)."""
        poi_validation_result = self.poi_validator.validate(
            poi.name, poi.description, poi.category, poi.location
        )

        if not poi_validation_result.is_valid:
            return f"POI validation failed for: {poi.name, poi.description}"

        # Check if POI already exists
        if self.db.is_poi_deplicate(self.workflow_id, poi):
            return f"POI already exists: {poi.name}"

        # Add POI to the database
        self.db.add_poi(self.workflow_id, self.current_url, poi)

        return f"POI registered: {poi.name}, Category: {poi.category}, Location: {poi.location}"

    def register_url(self, url: str, score: Literal[1, 2, 3, 4, 5]) -> str:
        """Register a new URL with its score."""
        self._all_urls_with_scores.setdefault(self.current_url, []).append((url, score))
        return f"Link registered: {url}, AI score: {score}"

    def process(
        self, scraper: Scraper, min_score: Optional[int] = None
    ) -> Tuple[Dict[str, List[PoiData]], Site]:
        # Create scraper function
        scrape = scraper.create(self)
        site = self.homepage.site

        while self.urls:
            link = self.urls.pop(0)

            if link.visited:
                continue

            # Set the current URL
            self.current_url = link.url

            # Process URL
            scrape(link.url)

            # Get only the new urls that were added from the current iteration
            new_urls = self._all_urls_with_scores.get(self.current_url, [])
            same_domain_urls = filter_same_domain_urls(new_urls, self.base_domain)

            # Record the visit
            pois_found = bool(self.db.get_all_pois(self.workflow_id).get(link.url, []))
            link.record_visit(
                poi_found=pois_found,
                urls_found=same_domain_urls,
            )

            # Add the new links
            for new_link in link.site.urls.values():
                self._add_url(new_link, min_score)

            # Save workflow state after each iteration to database
            self._save_state_in_db()

        # Mark workflow as completed in the database
        self.db.mark_workflow_completed(self.workflow_id)

        return self.db.get_all_pois(self.workflow_id), site
