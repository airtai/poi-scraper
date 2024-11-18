# this should smartly pick the url to work on and register the scraped results.


import os
from typing import Any, Callable, Dict

from autogen import AssistantAgent, register_function

from poi_scraper.agents.custom_web_surfer import CustomWebSurferTool
from poi_scraper.poi_manager import PoiManager
from poi_scraper.poi_types import PoiData, ScraperFactoryProtocol, SessionMemory


class ScraperFactory(ScraperFactoryProtocol):
    def __init__(self, llm_config: dict[str, Any]) -> None:
        """Initialize the ScraperFactory with the LLM configuration.

        Args:
            llm_config (dict[str, Any]): The configuration for the LLM model.
        """
        self.llm_config = llm_config
        self.system_message = """You are a web surfer agent tasked with identifying Points of Interest (POI) on a given webpage.
Your objective is to find and list all notable POIs where people can visit or hang out.

Instructions:

    - Scrape only the given webpage to identify POIs (do not explore any child pages or external links).
    - ALWAYS visit the full webpage before collecting POIs.
    - NEVER call `register_poi` and `register_new_link` without visiting the full webpage. This is a very important instruction and you will be penalised if you do so.
    - After visiting the webpage and identifying the POIs, you MUST call the `register_poi` function to record the POI.
    - If you find any new links on the webpage, you can call the `register_new_link` function to record the link along with the score (1 - 5) indicating the relevance of the link to the POIs.

Ensure that you strictly follow these instructions to capture accurate POI data."""

    def create_scraper(self, poi_manager: PoiManager) -> Callable[[str], str]:
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

        def register_link(url: str, score: float) -> str:
            poi_manager.register_link(url, score)
            return f"Link registered: {url}, AI score: {score}"

        register_function(
            register_link,
            caller=web_surfer,
            executor=assistant_agent,
            name="register_new_link",
            description="Register new link with score",
        )

        def scrape_poi_data(
            session_memory: SessionMemory,
        ) -> Dict[str, Any]:  # this needs to send the formatted data to the poi_manager
            # the initial message sould give the session memory for every page
            initial_message = f"Please collect all POIs and links from {url}"
            chat_result = assistant_agent.initiate_chat(
                web_surfer,
                message=initial_message,
                summary_method="reflection_with_llm",
                max_turns=3,
            )
            return str(chat_result.summary)

        return scrape_poi_data
