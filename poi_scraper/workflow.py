import os
from typing import Annotated, Any, Optional

from autogen import AssistantAgent, register_function

from fastagency import UI
from fastagency.runtimes.autogen import AutoGenWorkflows

from poi_scraper.custom_web_surfer import CustomWebSurferTool

system_message = """You are a web surfer agent tasked with identifying Points of Interest (POI) on a given webpage. 
Your objective is to find and list all notable POIs where people can visit or hang out. 

Instructions:

    - Scrape only the given webpage to identify POIs (do not explore any child pages or external links).
    - ALWAYS visit the full webpage before collecting POIs.
    - NEVER call `register_poi` without visiting the full webpage. This is a very important instruction and you will be penalised if you do so.
    - After visiting the webpage and identifying the POIs, you MUST call the `register_poi` function to record the POI.
    - Use continue_websurfing_task_with_additional_instructions at least 2 times after receiving the first response. Use message:
        "Please try to find more POIs, each subpage might have a few more!"

Ensure that you strictly follow these instructions to capture accurate POI data."""

llm_config = {
    "config_list": [
        {
            # "model": "gpt-4o-mini",
            "model": "gpt-4o",
            "api_key": os.getenv("OPENAI_API_KEY"),
        }
    ],
    "temperature": 0.8,
}

wf = AutoGenWorkflows()

@wf.register(name="poi_scraper", description="POI scraper chat")  # type: ignore[type-var]
def websurfer_workflow(
    ui: UI, params: dict[str, Any]
) -> str:
    
    def register_poi(
            name: Annotated[str, "The name of POI"], 
            description: Annotated[str, "The descrption of POI"], 
            category: Annotated[str, "The category of the POI"],
            location: Annotated[Optional[str], "The location of the POI"] = None
            ) -> str:
        ui.text_message(sender="WebSurfer", recipient="POI Database", body=f"POI name: {name}, description: {description}, category: {category}, location: {location}")
        return "POI registered"
    
    url = ui.text_input(
        sender="Workflow",
        recipient="User",
        prompt="I can collect Points of Interest (POI) data from any webpage—just share the link with me!",
    )

    initial_message = f"""Please collect all the Points of Interest (POI) data from this webpage: {url}."""

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
        register_poi,
        caller=web_surfer,
        executor=assistant_agent,
        name="register_poi",
        description="Register Point of Interest (POI)",
    )

    chat_result = assistant_agent.initiate_chat(
        web_surfer,
        message=initial_message,
        summary_method="reflection_with_llm",
        max_turns=7,
    )

    return chat_result.summary  # type: ignore[no-any-return]
