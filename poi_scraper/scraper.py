import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Literal, Optional

from autogen import AssistantAgent, register_function
from fastagency.logging import get_logger

from poi_scraper.agents.custom_web_surfer import (
    URL_IDENTIFICATION_INSTRUCTION_MSG,
    CustomWebSurferTool,
)
from poi_scraper.poi_types import PoiData, PoiManagerProtocol

logger = get_logger(__name__)


@dataclass
class Scraper:
    """A scraper factory that creates a callable scraper function."""

    llm_config: Dict[str, Any]
    system_message: str = (
        """You are a web surfer agent tasked with collecting Points of Interest (POIs) and URLs from a given webpage.

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
        - If you find any new urls that point to the English version of the webpage, you MUST call the `register_url` function to record the url along with the score (1 - 5) indicating the relevance of the link to the POIs.

    2. Collect POIs:

        - Identify notable POIs, such as landmarks, attractions, or places where people can visit or hang out.
        - For each POI, gather the following details:
            - Name: The name of the POI.
            - Location: Where the POI is located (e.g., city or region).
            - Category: The type of POI (e.g., Beach, Park, Museum).
            - Description: A short summary of the POI.

    3. Collect URLs:"""
        + URL_IDENTIFICATION_INSTRUCTION_MSG
        + """

Termination:
    - Once you have collected all the POIs and URLs from the webpage, you can terminate the chat by sending only "TERMINATE" as the message.
"""
    )

    def _is_termination_msg(self, msg: Dict[str, Any]) -> bool:
        """Check if the message is a termination message."""
        # check the view port here

        return bool(msg["content"] == "TERMINATE")

    def create(self, poi_manager: PoiManagerProtocol) -> Callable[[str], str]:
        """Factory method to create a scraper function.

        Args:
            poi_manager (PoiManagerProtocol): The POI manager instance for registering POIs and URLs.

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
