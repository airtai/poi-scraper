import os
from typing import Annotated, Any, Optional

from autogen import AssistantAgent, register_function
from fastagency import UI
from fastagency.runtimes.autogen import AutoGenWorkflows

from poi_scraper.custom_web_surfer import CustomWebSurferTool
from poi_scraper.poi_manager import PoiManager
from poi_scraper.utils import generate_poi_markdown_table, get_url_from_user

system_message = """You are a web surfer agent tasked with identifying Points of Interest (POI) on a given webpage.
Your objective is to find and list all notable POIs where people can visit or hang out.

Instructions:

    - Scrape only the given webpage to identify POIs (do not explore any child pages or external links).
    - ALWAYS visit the full webpage before collecting POIs.
    - NEVER call `register_poi_data` and `register_new_link` without visiting the full webpage. This is a very important instruction and you will be penalised if you do so.
    - After visiting the webpage and identifying the POIs, you MUST call the `register_poi_data` function to record the POI.
    - If you find any new links on the webpage, you can call the `register_new_link` function to record the link along with the score (0.0 to 1.0) indicating the relevance of the link to the POIs.

Ensure that you strictly follow these instructions to capture accurate POI data."""

llm_config = {
    "config_list": [
        {
            "model": "gpt-4o-mini",
            # "model": "gpt-4o",
            "api_key": os.getenv("OPENAI_API_KEY"),
        }
    ],
    "temperature": 0.8,
}

wf = AutoGenWorkflows()


@wf.register(name="poi_scraper", description="POI scraper chat")  # type: ignore[misc]
def websurfer_workflow(ui: UI, params: dict[str, Any]) -> str:
    # poi_data = PoiDataBase(llm_config, ui)

    # Get valid URL from user
    base_url = get_url_from_user(ui)

    # Initialize POI manager
    poi_manager = PoiManager(base_url)

    def register_poi_data(
        name: Annotated[str, "The name of POI"],
        description: Annotated[str, "The descrption of POI"],
        category: Annotated[str, "The category of the POI"],
        location: Annotated[Optional[str], "The location of the POI"] = None,
        # todo: url: Annotated[str, "The URL of the POI"] = None
    ) -> str:
        return poi_manager.register_new_poi(name, description, category, location)

    def register_new_link(url: str, score: float) -> str:
        return poi_manager.register_new_link(url, score)

    # Create agents and tools
    assistant_agent = AssistantAgent(
        name="Assistant_Agent",
        system_message="You are a helpful agent",
        llm_config=llm_config,
        human_input_mode="NEVER",
    )

    web_surfer = AssistantAgent(
        name="WebSurfer_Agent",
        system_message=system_message,
        llm_config=llm_config,
        human_input_mode="NEVER",
    )

    web_surfer_tool = CustomWebSurferTool(
        name_prefix="Web_Surfer_Tool",
        llm_config=llm_config,
        summarizer_llm_config=llm_config,
        bing_api_key=os.getenv("BING_API_KEY"),
    )

    web_surfer_tool.register(
        caller=web_surfer,
        executor=assistant_agent,
    )

    register_function(
        register_poi_data,
        caller=web_surfer,
        executor=assistant_agent,
        name="register_poi_data",
        description="Register Point of Interest (POI)",
    )

    register_function(
        register_new_link,
        caller=web_surfer,
        executor=assistant_agent,
        name="register_new_link",
        description="Register new link with score",
    )

    def scrape_poi_data(url: str) -> str:
        initial_message = f"""Please collect all the Points of Interest (POI) data and links present in the webpage {url} along with the score."""
        chat_result = assistant_agent.initiate_chat(
            web_surfer,
            message=initial_message,
            summary_method="reflection_with_llm",
            max_turns=3,
        )
        return str(chat_result.summary)

    poi_manager.process(scrape_poi_data)

    table = generate_poi_markdown_table(poi_manager.poi_list)
    ui.text_message(
        sender="Workflow",
        recipient="User",
        body=f"List of all registered POIs:\n{table}",
    )

    # table = generate_poi_markdown_table(poi_data.un_registered_pois)
    # ui.text_message(
    #     sender="Workflow",
    #     recipient="User",
    #     body=f"List of all unregistered POIs:\n{table}",
    # )

    ui.text_message(
        sender="Workflow",
        recipient="User",
        body=f"List of all new links:\n{poi_manager.all_links_with_scores}",
    )

    return f"POI collection completed for {base_url}."
