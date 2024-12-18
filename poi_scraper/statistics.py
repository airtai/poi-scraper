import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Set


@dataclass
class Site:
    urls: Dict[str, "Link"]

    def __getstate__(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Serializes the Site object by capturing the essential state of all Links.

        This method creates a simpler structure that avoids circular references by
        storing just the core data about each URL and its relationships.
        """
        state = {
            "url_data": {
                url: {
                    "url": link.url,
                    "estimated_score": link.estimated_score,
                    "parent_urls": [parent.url for parent in link.parents]
                    if link.parents
                    else [],
                    "visited": link.visited,
                    "children_urls": [child.url for child in link.children],
                    "children_visited": link.children_visited,
                    "children_poi_found": link.children_poi_found,
                }
                for url, link in self.urls.items()
            }
        }

        return state

    def __setstate__(self, state: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
        """Reconstructs the Site and all its Links from the serialized state.

        This method follows a two-phase reconstruction:
        1. Creates all Link objects with their basic properties
        2. Establishes the relationships between Links
        """
        # Phase 1: Create bare Links with their basic properties
        self.urls = {}
        for url, link_data in state["url_data"].items():
            # Create a new Link object with basic properties
            link = Link(
                site=self,
                url=link_data["url"],
                estimated_score=link_data["estimated_score"],
                parents=set(),  # Parents will be added in Phase 2
                visited=link_data["visited"],
                children=[],  # Children will be added in Phase 2
                children_visited=link_data["children_visited"],
                children_poi_found=link_data["children_poi_found"],
            )
            self.urls[url] = link

        # Phase 2: Establish relationships between Links
        for url, link_data in state["url_data"].items():
            current_link = self.urls[url]

            # Add parent Links
            current_link.parents = (
                {self.urls[parent_url] for parent_url in link_data["parent_urls"]}  # type: ignore
                if link_data["parent_urls"]
                else set()
            )

            # Add children Links
            current_link.children = [
                self.urls[child_url] for child_url in link_data["children_urls"]
            ]

    def get_url_scores(self, decimals: int = 5) -> Dict[str, float]:
        """Return the scores of all the URLs in the site.

        Returns:
            Dict[str, float]: The scores of all the URLs in the site.

        """
        return {url: round(link.score, decimals) for url, link in self.urls.items()}

    def get_sorted_unvisited_links(
        self, min_scraping_score: Optional[int] = None
    ) -> List["Link"]:
        """Get unvisited links from the site, sorted by score in descending order.

        Args:
            min_scraping_score (Optional[int]): The minimum score required for the link.

        Returns:
            List[Link]: The unvisited links from the site, sorted by score in descending order.

        """
        # Get all URLs from the site
        all_links = self.urls.values()

        # Filter for unvisited links and apply score threshold if provided
        unvisited = [
            link
            for link in all_links
            if not link.visited
            and (min_scraping_score is None or link.score >= min_scraping_score)
        ]

        # Sort the unvisited links by score in descending order
        return sorted(unvisited, key=lambda x: x.score, reverse=True)


@dataclass
class Link:
    site: Site
    url: str
    estimated_score: Literal[1, 2, 3, 4, 5]
    parents: Set["Link"]

    # to be set after visiting the link
    visited: bool = False
    children: List["Link"] = field(default_factory=list)
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
            if link.parents:
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
