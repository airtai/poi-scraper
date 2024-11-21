import os
from typing import Any

from fastagency import UI
from fastagency.runtimes.autogen import AutoGenWorkflows

from poi_scraper.agents import ValidatePoiAgent
from poi_scraper.poi import PoiManager, Scraper
from poi_scraper.utils import generate_poi_markdown_table

llm_config = {
    "config_list": [
        {
            "model": "gpt-4o-mini",
            "api_key": os.getenv("OPENAI_API_KEY"),
        }
    ],
    "temperature": 0.8,
}

wf = AutoGenWorkflows()


@wf.register(name="poi_scraper", description="POI scraper chat")  # type: ignore[misc]
def websurfer_workflow(ui: UI, params: dict[str, Any]) -> str:
    # Get valid URL from user
    base_url = "https://www.medulinriviera.info"  # get_url_from_user(ui)

    # Initialize POI manager
    poi_validator = ValidatePoiAgent(llm_config=llm_config)
    poi_manager = PoiManager(base_url, poi_validator)

    # Create scraper factory
    scraper = Scraper(llm_config)

    # Process
    pois_list, site = poi_manager.process(scraper)

    table = generate_poi_markdown_table(pois_list)
    ui.text_message(
        sender="Workflow",
        recipient="User",
        body=f"List of all registered POIs:\n{table}",
    )

    ui.text_message(
        sender="Workflow",
        recipient="User",
        body=f"List of all new links:\n{site.get_url_scores(decimals=3)}",
    )

    return f"POI collection completed for {base_url}."
