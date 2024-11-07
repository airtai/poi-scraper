import os
from typing import Annotated, Any, Optional

from autogen import AssistantAgent, register_function

from fastagency import UI
from fastagency.runtimes.autogen import AutoGenWorkflows
from fastagency.runtimes.autogen.tools import WebSurferTool


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

web_surfer_system_message = """You are a web surfer tasked with identifying Points of Interest (POI)
 on the provided website link. For each POI, gather the following information:

- Name – The name of the POI.
- Category – The type of POI (choose from the list below).
- Description – A brief description of the POI.
- Location – The physical location, including latitude and longitude coordinates.

IMPORTANT:

When calling `create_new_websurfing_task` always append the below in the `task` parameter. Never 
skip this rule or you will be penalised.

    1. Website Link Requirement:
        - Always include the provided website link as part of the task.

    2. Scope of POI Collection:
        - Gather as many Points of Interest (POI) as possible from the website. You may explore multiple internal links within the website.
        - Do NOT gather POI data from external internet sources. Only collect data that is directly available on the given website.

    3. Output format:
        - While returning the collected POI's, you MUST encode it as a JSON string. For example:
            {
                "name": "Marina Beach",
                "description": "A lovely beach located in chennai",
                "category": "Beach",
                "location": {"latitude": 13.0532752 , "longitude": 80.2832887 }
            }
"""



# loop this 
@wf.register(name="poi_scraper", description="POI scraper chat")  # type: ignore[type-var]
def websurfer_workflow(
    ui: UI, params: dict[str, Any]
) -> str:
    
    def register_poi(
            name: Annotated[str, "The name of POI"], 
            description: Annotated[str, "The descrption of POI"], 
            category: Annotated[str, "The category of the POI"],
            location: Annotated[Optional[str], "The location of the POI"] = None
            ):
        ui.text_message(sender="WebSurfer", recipient="POI Database", body=f"POI name: {name}, description: {description}, category: {category}, location: {location}")
        return "POI registered"
    
    url = ui.text_input(
        sender="Workflow",
        recipient="User",
        prompt="I can collect Points of Interest (POI) data from any website—just share the link with me!",
    )

    initial_message = f"Please collect all the Points of Interest (POI) data from this link: {url}. For every POI, please call `register_poi` function."

    assistant_agent = AssistantAgent(
        name="Assistant_Agent",
        system_message="You are a user agent",
        llm_config=llm_config,
        human_input_mode="NEVER",
    )

    web_surfer = AssistantAgent(
        name="WebSurfer_Agent",
        system_message=web_surfer_system_message,
        llm_config=llm_config,
        human_input_mode="NEVER",
    )
    
    web_surfer_tool = WebSurferTool(
        name_prefix="Web_Surfer_Tool",
        llm_config=llm_config,
        summarizer_llm_config=llm_config,
        bing_api_key=os.getenv("BING_API_KEY"),
    )

#     web_surfer_tool.initial_message = f"""
# The focus is on the provided url and all its subpages. You need to extract maximum POI's from the website. AFTER visiting the home page, create a step-by-step plan BEFORE visiting the subpages.
# For every subpage you visit, do the below:
#     - Visit the page completely, you should not miss any section in the web page
#     - Identify all the POI's in the page
#     - Click on all the relevant links on the page and repeat this process
#     - Do NOT visit the same page multiple times, but only once!
#     - If your co-speaker repeats the same message, inform him that you have already answered to that message and ask him to proceed with the task.
#         e.g. "I have already answered to that message, please proceed with the task or you will be penalized!"
# """

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
        max_turns=5,
    )

    return chat_result.summary  # type: ignore[no-any-return]
