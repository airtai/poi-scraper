# this should smartly pick the url to work on and register the scraped results.


import os
from typing import Any, Callable

from autogen import AssistantAgent, register_function

from poi_scraper.agents.custom_web_surfer import CustomWebSurferTool
from poi_scraper.poi_manager import PoiManager
from poi_scraper.poi_types import (
    PoiData,
    ScraperFactoryProtocol,
    ScraperResult,
    SessionMemory,
)


class ScraperFactory(ScraperFactoryProtocol):
    def __init__(self, llm_config: dict[str, Any]) -> None:
        """Initialize the ScraperFactory with the LLM configuration.

        Args:
            llm_config (dict[str, Any]): The configuration for the LLM model.
        """
        self.llm_config = llm_config
        self.system_message = """You are a specialized web crawler agent that selects URLs likely to contain
Points of Interest (POIs). You'll receive the statistics of the website to help you make informed decisions.

A POI could be: tourist attractions, business locations, service centers, landmarks, or any specific location with physical presence.

Instructions:

Step 1: Look at "Unvisited Links Available"
- Each link has an Initial Score (1-5) and Justification
- Higher scores suggest higher likelihood of POIs but these are initial guesses and may not be accurate

Step 2: Check "Recent Performance"
- Shows how many POIs were found in recently visited pages
- If last 2 pages had 0 POIs, this indicates current pattern is not working
- In such cases, ignore current pattern and try URLs from a different pattern

Step 3: Review "Pattern Performance"
- Shows how many child URLs under a parent pattern were successful
- Example: "https://www.visitchennai.com/attractions/<category>: 2/3 success" means:
 * Under parent URL pattern "https://www.visitchennai.com/attractions"
 * Out of 3 child URLs visited (https://www.visitchennai.com/attractions/temples, https://www.visitchennai.com/attractions/museums, etc.)
 * 2 of them contained POIs
- Prefer patterns where child URLs consistently yield POIs

Step 4: Make ONE of these two decisions:

A) Select a URL to visit:
  Response format:
  URL: [paste the full URL]
  Reason: [explain why this URL is promising based on its score AND pattern performance]

B) Terminate the search:
  Response format:
  Decision: TERMINATE
  Reason: [explain why no URLs are worth visiting]
  Note: This will end the chat session and mark the task as complete


TERMINATE when:
1. All remaining unvisited URLs match patterns that historically failed
2. Only administrative/utility pages remain

Example 1 (Positive Case):
Current Status:
1. Unvisited Links Available:
  - https://www.visitchennai.com//attractions/temples
    Initial Score: 5
    Justification: Directory of temples
  - https://www.visitchennai.com//attractions/museums
    Initial Score: 4
    Justification: List of museums

2. Recent Performance:
  - https://www.visitchennai.com//attractions: 4 POIs found
  - https://www.visitchennai.com//attractions/parks: 3 POIs found

3. Pattern Performance:
  - https://www.visitchennai.com//attractions/<category>: 3/3 success

Example Response:
URL: https://www.visitchennai.com//attractions/temples
Reason: High initial score (5), parent pattern https://www.visitchennai.com//attractions has perfect success rate (3/3 child URLs had POIs), recent pages are finding POIs consistently

Example 2 (Terminate Case):
Current Status:
1. Unvisited Links Available:
  - https://www.visitchennai.com//contact-us
    Initial Score: 1
    Justification: Contact information page
  - https://www.visitchennai.com//login
    Initial Score: 1
    Justification: User login page
  - https://www.visitchennai.com//faq
    Initial Score: 1
    Justification: Help page

2. Recent Performance:
  - https://www.visitchennai.com//about-us: 0 POIs found
  - https://www.visitchennai.com//terms: 0 POIs found

3. Pattern Performance:
  - https://www.visitchennai.com//info/<page>: 0/3 success

Example Response:
Decision: TERMINATE
Reason: Only administrative pages remain (contact, login, faq), all with low scores (1). Last 2 pages found no POIs, and parent pattern /info has 0% success rate.
"""

    def _format_initial_message(self, session_memory: SessionMemory) -> str:
        if not session_memory.pages:
            return f"Please collect all POIs and links from: {session_memory.base_url}"

        unvisited_links = " ".join(
            [
                f"  - Url: {link.url}\n    Initial Score: {link.initial_score}\n    Justification: {link.justification}\n"
                for page in session_memory.pages.values()
                for link in page.unvisited_links
                if link.url not in session_memory.visited_urls
            ]
        )

        recent_performance = "".join(
            [
                f"  - {url}: {len(stats.pois)} POIs found\n"
                for url, stats in list(session_memory.pages.items())[
                    -5:
                ]  # Last 5 pages
            ]
        )

        pattern_performance = "".join(
            [
                f"  - {pattern}: {stats.success_count}/{stats.success_count + stats.failure_count} success\n"
                for pattern, stats in session_memory.patterns.items()
            ]
        )

        return f"""Below is the statistics of the current scraping session:

1. Unvisited Links Available:
{unvisited_links}

3. Recent Performance:
{recent_performance}

4. Pattern Performance:
{pattern_performance}
"""

    def create_scraper(
        self, poi_manager: PoiManager
    ) -> Callable[[SessionMemory], ScraperResult]:
        assistant_agent = AssistantAgent(
            name="Assistant_Agent",
            system_message="You are a helpful agent",
            llm_config=self.llm_config,
            human_input_mode="NEVER",
        )

        web_surfer = AssistantAgent(
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
            caller=web_surfer,
            executor=assistant_agent,
        )

        # Register the functions with proper type conversion
        def register_poi(poi_data: dict[str, str]) -> str:
            poi = PoiData(**poi_data)
            poi_manager.register_poi(poi)
            return f"POI registered: {poi_data['name']}"

        register_function(
            register_poi,
            caller=web_surfer,
            executor=assistant_agent,
            name="register_poi",
            description="Register Point of Interest (POI)",
        )

        def register_link(
            current_url: str, outgoing_url: str, score: int, justification: str
        ) -> str:
            poi_manager.register_link(current_url, outgoing_url, score, justification)
            return f"Link registered: {outgoing_url}, AI score: {score}"

        register_function(
            register_link,
            caller=web_surfer,
            executor=assistant_agent,
            name="register_new_link",
            description="Register new link with score",
        )

        def scrape_poi_data(
            session_memory: SessionMemory,
        ) -> ScraperResult:
            initial_message = self._format_initial_message(session_memory)
            chat_result: ScraperResult = assistant_agent.initiate_chat(
                web_surfer,
                message=initial_message,
                summary_method="reflection_with_llm",
                max_turns=3,
            )

            return chat_result

        return scrape_poi_data
