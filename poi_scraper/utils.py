import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Tuple
from urllib.parse import urlparse

from fastagency import UI

from poi_scraper.poi_types import PoiData


@contextmanager
def get_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return (
            result.scheme in ["http", "https"]
            and bool(result.netloc)
            and result.netloc.startswith("www.")
        )
    except Exception:
        return False


def generate_poi_markdown_table(
    pois: dict[str, list[PoiData]],
) -> str:
    table_header = "| Sno | URL | Name | Category | Location | Description |\n| --- | --- | --- | --- | --- | --- |\n"
    table_rows = "\n".join(
        [
            f"| {i+1} | {url} | {poi.name} | {poi.category} | {poi.location} | {poi.description} |"
            for i, (url, poi_list) in enumerate(pois.items())
            for poi in poi_list
        ]
    )
    return table_header + table_rows


def get_base_url(ui: UI) -> str:
    while True:
        base_url = ui.text_input(
            sender="Workflow",
            recipient="User",
            prompt="Great! Please provide the URL of the website you want to collect Points of Interest (POI) data from. Example: https://www.example.com",
        )
        if is_valid_url(base_url):
            break
        ui.text_message(
            sender="Workflow",
            recipient="User",
            body="The provided URL is not valid. Please enter a valid URL. Example: https://www.example.com",
        )

    return str(base_url)


def is_unique_name(name: str, db_path: Path) -> bool:
    try:
        statement = "SELECT COUNT(*) FROM tasks WHERE name = ?"
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(statement, (name,))
            return bool(cursor.fetchone()[0] == 0)
    except sqlite3.OperationalError:
        return True


def get_name_for_task(ui: UI, db_path: Path) -> str:
    while True:
        name: str = ui.text_input(
            sender="Workflow",
            recipient="User",
            prompt="Please provide a name for the scraping task. You can use this name to restart the task if it gets stuck or to view the results.",
        )

        # If database is not created yet, return the name
        if not db_path.exists():
            break

        if is_unique_name(name, db_path):
            break

        ui.text_message(
            sender="Workflow",
            recipient="User",
            body="Oops! The name you provided is already taken. Please provide a different name.",
        )

    return name


def get_all_tasks(db_path: Path, in_progress: bool = False) -> List[Dict[str, Any]]:
    """Get all tasks from the database."""
    try:
        statement = (
            "SELECT * FROM tasks WHERE status != 'completed'"
            if in_progress
            else "SELECT * FROM tasks"
        )
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(statement)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


def start_or_resume_task(ui: UI, db_path: Path) -> Tuple[str, str]:
    # Check if there are any incomplete tasks
    inprogress_tasks = get_all_tasks(db_path=db_path, in_progress=True)

    if inprogress_tasks:
        answer = ui.multiple_choice(
            sender="Workflow",
            recipient="User",
            prompt="Incomplete scraping tasks found. Do you want to resume any of them?",
            choices=["Yes", "No"],
            single=True,
        )
        if answer == "Yes":
            incomplete_task_names = [task["name"] for task in inprogress_tasks]
            selected_task = ui.multiple_choice(
                sender="Workflow",
                recipient="User",
                prompt="Which scraping tasks do you want to resume?",
                choices=incomplete_task_names,
                single=True,
            )
            ui.text_message(
                sender="Workflow",
                recipient="User",
                body=f"Resuming scraping task for {selected_task}.",
            )
            # get the url for the selected_task from incomplete_tasks
            selected_task_base_url = next(
                task["base_url"]
                for task in inprogress_tasks
                if task["name"] == selected_task
            )
            return selected_task, selected_task_base_url

    # Get valid URL from user
    name = get_name_for_task(ui, db_path)
    base_url = get_base_url(ui)
    # base_url = "https://www.infofazana.hr/en"
    # base_url = "www.medulinriviera.info"

    ui.text_message(
        sender="Workflow",
        recipient="User",
        body=f"Starting POI collection for base_url: {base_url}.",
    )

    return name, base_url


def get_all_pois(task_id: int, db_path: Path) -> List[Dict[str, str]]:
    statement = "SELECT * FROM pois WHERE task_id = ?"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(statement, (task_id,))
        pois = cursor.fetchall()

    return [
        {
            "name": poi["name"],
            "url": poi["url"],
            "description": poi["description"],
            "category": poi["category"],
            "location": poi["location"],
        }
        for poi in pois
    ]


def filter_same_domain_urls(
    urls_found: List[Tuple[str, Literal[1, 2, 3, 4, 5]]], base_domain: str
) -> dict[str, Literal[1, 2, 3, 4, 5]]:
    base_domain_parsed = urlparse(base_domain)
    base_domain_netloc = base_domain_parsed.netloc or base_domain_parsed.path
    return {
        url: score
        for url, score in urls_found
        if urlparse(url).netloc == base_domain_netloc
    }
