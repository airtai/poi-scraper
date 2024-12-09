import pickle  # nosec B403
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from poi_scraper.poi_types import PoiData
from poi_scraper.statistics import Site
from poi_scraper.utils import get_connection


@dataclass
class ScrapingStatistics:
    """Contains the complete state of a scraping task."""

    site_obj: Site


class PoiDatabase:
    def __init__(self, db_path: Path) -> None:
        """Initialize the POI database."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database."""
        create_tables_sql = """
        -- tasks table with status and queue state
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            status TEXT NOT NULL,
            site_obj BLOB,  -- Stores serialized queue and homepage
            UNIQUE(name)
        );

        -- POIs table
        CREATE TABLE IF NOT EXISTS pois (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        -- Create index for faster POI lookups
        CREATE INDEX IF NOT EXISTS idx_pois_task ON pois(task_id, name);
        """
        with get_connection(self.db_path) as conn:
            for statement in create_tables_sql.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.commit()

    def create_or_get_task(
        self, name: str, base_url: str
    ) -> Tuple[int, Optional[ScrapingStatistics]]:
        """Create a new task or get existing one with all state."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, site_obj FROM tasks WHERE name = ?",
                (name,),
            )
            task = cursor.fetchone()

            if task:
                if task["site_obj"] is not None:
                    # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                    site_obj = pickle.loads(  # nosec B301
                        task["site_obj"]
                    )
                    return task["id"], ScrapingStatistics(
                        site_obj=site_obj,
                    )
                return task["id"], None

            # Create new task if it doesn't exist
            cursor = conn.execute(
                """INSERT INTO tasks (
                        name, base_url, status, site_obj
                    ) VALUES (?, ?, ?, ?)""",
                (name, base_url, "in_progress", None),
            )

            conn.commit()
            return cursor.lastrowid, None  # type: ignore

    def save_task_state(self, task_id: int, statistics: ScrapingStatistics) -> None:
        """Save the statistics of the task in the database."""
        with get_connection(self.db_path) as conn:
            site_obj = pickle.dumps(  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                statistics.site_obj,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
            conn.execute(
                """UPDATE tasks SET site_obj = ? WHERE id = ?""",
                (site_obj, task_id),
            )
            conn.commit()

    def is_poi_duplicate(self, task_id: int, poi: PoiData) -> bool:
        """Check if the POI already exists in the database."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM pois WHERE task_id = ? AND name = ? LIMIT 1",
                (task_id, poi.name),
            )
            return bool(cursor.fetchone())

    def add_poi(self, task_id: int, url: str, poi: PoiData) -> None:
        """Add a new POI to the database."""
        if self.is_poi_duplicate(task_id, poi):
            return

        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT INTO pois (task_id, url, name, description, category, location) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    url,
                    poi.name,
                    poi.description,
                    poi.category,
                    poi.location,
                ),
            )
            conn.commit()

    def get_all_pois(self, task_id: int) -> Dict[str, List[PoiData]]:
        """Retrieve all POIs for a task grouped by URL."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT url, name, description, category, location FROM pois WHERE task_id = ? ORDER BY url",
                (task_id,),
            )
            pois = cursor.fetchall()

        ret_val = {}
        # Group POIs by URL
        for url, group_pois in groupby(pois, key=lambda x: x["url"]):
            ret_val[url] = [
                PoiData(
                    name=poi["name"],
                    description=poi["description"],
                    category=poi["category"],
                    location=poi["location"],
                )
                for poi in group_pois
            ]
        return ret_val

    def mark_task_completed(self, task_id: int) -> None:
        """Mark task as completed and clear queue state."""
        with get_connection(self.db_path) as conn:
            conn.execute(
                """UPDATE tasks SET status = 'completed', site_obj = NULL WHERE id = ?""",
                (task_id,),
            )
            conn.commit()
