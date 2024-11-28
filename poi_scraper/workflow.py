import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastagency import UI
from fastagency.runtimes.autogen import AutoGenWorkflows

from poi_scraper.agents import ValidatePoiAgent
from poi_scraper.poi import PoiManager, Scraper
from poi_scraper.utils import generate_poi_markdown_table, get_url_from_user

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
    base_url = get_url_from_user(ui)
    # base_url = "https://www.infofazana.hr/en"
    # base_url = "www.medulinriviera.info"

    ui.text_message(
        sender="Workflow",
        recipient="User",
        body=f"Starting POI collection for {base_url}.",
    )

    # Initialize POI manager
    poi_validator = ValidatePoiAgent(llm_config=llm_config)
    poi_manager = PoiManager(base_url, poi_validator)

    # Create scraper factory
    scraper = Scraper(llm_config)

    # Process
    pois, site = poi_manager.process(scraper, 5)

    table = generate_poi_markdown_table(pois)
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


@wf.register(name="show_poi", description="Show scraped POI's")  # type: ignore[misc]
def show_poi_workflow(ui: UI, params: dict[str, Any]) -> str:
    path = Path("poi_data.csv")
    # load the pandas dataframe from disk

    while True:
        try:
            df = pd.read_csv(path)
        except FileNotFoundError:
            ui.text_message(
                sender="Workflow",
                recipient="User",
                body="No POI's found. Please run the scraper first.",
            )
            break

        # generate markdown table
        table = df.to_markdown()

        ui.text_message(
            sender="Workflow",
            recipient="User",
            body=f"List of all registered POIs:\n{table}",
        )

        answer = ui.multiple_choice(
            sender="Workflow",
            recipient="User",
            prompt="Do you want to check the POI's again?",
            choices=["Yes", "No"],
            single=True,
        )

        if answer == "No":
            break

    return "POI's shown successfully."
