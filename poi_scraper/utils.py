import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Tuple
from urllib.parse import urlparse

from fastagency import UI
from fastagency.logging import get_logger

from poi_scraper.poi_types import PoiData

logger = get_logger(__name__)


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
    all_pois = [poi for url, poi_list in pois.items() for poi in poi_list]
    table_header = "| Sno | Name | Category | Location | Description |\n| --- | --- | --- | --- | --- |\n"
    table_rows = "\n".join(
        [
            f"| {i+1} | {poi.name} | {poi.category} | {poi.location} | {poi.description} |"
            for i, poi in enumerate(all_pois)
        ]
    )
    return table_header + table_rows


def generated_formatted_scores(scores: Dict[str, float]) -> str:
    table_header = "| Sno | Url | Score |\n| --- | --- | --- |\n"
    table_rows = "\n".join(
        [
            f"| {i+1} | {url} | {score} |"
            for i, (url, score) in enumerate(scores.items())
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


def get_all_tasks(db_path: Path) -> List[Dict[str, Any]]:
    """Get all tasks from the database."""
    try:
        statement = "SELECT * FROM tasks"
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(statement)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        logger.info(f"Error in get_all_tasks: {e!s}")
        return []


def start_or_resume_task(ui: UI, db_path: Path) -> Tuple[str, str]:
    # Check if there are any incomplete tasks
    all_tasks = get_all_tasks(db_path=db_path)

    if all_tasks:
        answer = ui.multiple_choice(
            sender="Workflow",
            recipient="User",
            prompt="Would you like to restart any of the previous scraping tasks?",
            choices=["Yes", "No"],
            single=True,
        )
        if answer == "Yes":
            previous_task_names = [task["name"] for task in all_tasks]
            selected_task = ui.multiple_choice(
                sender="Workflow",
                recipient="User",
                prompt="Which scraping tasks do you want to restart?",
                choices=previous_task_names,
                single=True,
            )
            ui.text_message(
                sender="Workflow",
                recipient="User",
                body=f"Restarting scraping task for {selected_task}.",
            )
            # get the url for the selected_task from incomplete_tasks
            selected_task_base_url = next(
                task["base_url"] for task in all_tasks if task["name"] == selected_task
            )
            return selected_task, selected_task_base_url

    # Get valid URL from user
    name = get_name_for_task(ui, db_path)
    base_url = get_base_url(ui)

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


def get_max_links_to_scrape(ui: UI) -> int:
    while True:
        max_links_to_scrape: int = ui.text_input(
            sender="Workflow",
            recipient="User",
            prompt="Please enter a number between 1 and 20 (inclusive) to set the maximum number of links to scrape from the website in a single session. You can restart the task anytime to scrape additional links.",
        )

        try:
            max_links_to_scrape = int(max_links_to_scrape)
            if 1 <= max_links_to_scrape <= 20:
                break
            else:
                ui.text_message(
                    sender="Workflow",
                    recipient="User",
                    body="Please enter a number between 1 and 20.",
                )
        except ValueError:
            ui.text_message(
                sender="Workflow",
                recipient="User",
                body="The value you entered is not a valid number. Please enter a number between 1 and 20.",
            )
            continue
    return max_links_to_scrape
