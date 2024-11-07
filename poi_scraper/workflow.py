import os
from typing import Any

from autogen import UserProxyAgent

from fastagency import UI
from fastagency.runtimes.autogen import AutoGenWorkflows
from fastagency.runtimes.autogen.agents.websurfer import WebSurferAgent


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

When calling `create_new_websurfing_task` always append the below in the `task` parameter. Never skip this rule or you will be penalised.

    1. Website Link Requirement:
        - Always include the provided website link as part of the task.

    2. Scope of POI Collection:
        - Gather as many Points of Interest (POI) as possible from the website. You may explore multiple internal links within the website.
        - Do NOT gather POI data from external internet sources. Only collect data that is directly available on the given website.
"""


@wf.register(name="poi_scraper", description="POI scraper chat")  # type: ignore[type-var]
def websurfer_workflow(
    ui: UI, params: dict[str, Any]
) -> str:
    initial_message = ui.text_input(
        sender="Workflow",
        recipient="User",
        prompt="I can collect Points of Interest (POI) data from any website—just share the link with me!",
    )
    user_agent = UserProxyAgent(
        name="User_Agent",
        system_message="You are a user agent",
        llm_config=llm_config,
        human_input_mode="NEVER",
    )
    web_surfer = WebSurferAgent(
        name="WebSurfer_Agent",
        llm_config=llm_config,
        summarizer_llm_config=llm_config,
        human_input_mode="NEVER",
        executor=user_agent,
        bing_api_key=os.getenv("BING_API_KEY"),
        system_message=web_surfer_system_message
    )

    chat_result = user_agent.initiate_chat(
        web_surfer,
        message=initial_message,
        summary_method="reflection_with_llm",
        max_turns=3,
    )

    return chat_result.summary  # type: ignore[no-any-return]
