import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastagency import UI
from fastagency.runtimes.autogen import AutoGenWorkflows

from poi_scraper.agents import ValidatePoiAgent
from poi_scraper.poi_manager import PoiManager
from poi_scraper.scraper import Scraper
from poi_scraper.utils import (
    generate_poi_markdown_table,
    get_all_pois,
    get_all_tasks,
    start_or_resume_task,
)

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

# Database path
DB_PATH = Path("poi_data.db")


@wf.register(name="poi_scraper", description="POI scraper chat")  # type: ignore[misc]
def websurfer_workflow(ui: UI, params: dict[str, Any]) -> str:
    task_name, base_url = start_or_resume_task(ui, DB_PATH)

    # Initialize POI manager
    poi_validator = ValidatePoiAgent(llm_config=llm_config)
    poi_manager = PoiManager(
        base_url=base_url,
        poi_validator=poi_validator,
        task_name=task_name,
        db_path=DB_PATH,
    )

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
def show_poi_task(ui: UI, params: dict[str, Any]) -> str:
    all_tasks = get_all_tasks(db_path=DB_PATH)

    if not all_tasks:
        ui.text_message(
            sender="Workflow",
            recipient="User",
            body="No POI's found. Please run the scraper first.",
        )
        return "No POI's found."

    task_names = [task["name"] for task in all_tasks]

    selected_task = ui.multiple_choice(
        sender="Workflow",
        recipient="User",
        prompt="Click on the task to show the POI's",
        choices=task_names,
        single=True,
    )

    # Query the pois table for the selected task
    selected_task_id = next(
        task["id"] for task in all_tasks if task["name"] == selected_task
    )

    while True:
        pois_data = get_all_pois(selected_task_id, DB_PATH)

        table = pd.DataFrame(pois_data).to_markdown()

        ui.text_message(
            sender="Workflow",
            recipient="User",
            body=f"List of all registered POIs for {selected_task}:\n{table}",
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
