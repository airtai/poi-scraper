import pickle  # nosec B403
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from poi_scraper.poi_types import PoiData
from poi_scraper.statistics import Link
from poi_scraper.utils import get_connection


@dataclass
class WorkflowState:
    """Contains the complete state of a workflow."""

    homepage: Link


class PoiDatabase:
    def __init__(self, db_path: Path) -> None:
        """Initialize the POI database."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database."""
        create_tables_sql = """
        -- Workflows table with status and queue state
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            status TEXT NOT NULL,
            queue_state BLOB,  -- Stores serialized queue and homepage
            UNIQUE(name)
        );

        -- POIs table
        CREATE TABLE IF NOT EXISTS pois (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        );

        -- Create index for faster POI lookups
        CREATE INDEX IF NOT EXISTS idx_pois_workflow ON pois(workflow_id, name);
        """
        with get_connection(self.db_path) as conn:
            for statement in create_tables_sql.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.commit()

    def create_or_get_workflow(
        self, name: str, base_url: str
    ) -> Tuple[int, Optional[WorkflowState]]:
        """Create a new workflow or get existing one with all state."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, queue_state FROM workflows WHERE name = ?",
                (name,),
            )
            workflow = cursor.fetchone()

            if workflow:
                if workflow["queue_state"] is not None:
                    # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                    queue_state = pickle.loads(  # nosec B301
                        workflow["queue_state"]
                    )

                    return workflow["id"], WorkflowState(
                        homepage=queue_state,
                    )
                return workflow["id"], None

            # Create new workflow if it doesn't exist
            cursor = conn.execute(
                """INSERT INTO workflows (
                        name,base_url, status, queue_state
                    ) VALUES (?, ?, ?, ?)""",
                (name, base_url, "in_progress", None),
            )

            conn.commit()
            return cursor.lastrowid, None  # type: ignore

    def save_workflow_state(self, workflow_id: int, state: WorkflowState) -> None:
        """Save the state of the workflow in the database."""
        with get_connection(self.db_path) as conn:
            queue_state = pickle.dumps(  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                state.homepage
            )
            conn.execute(
                """UPDATE workflows SET queue_state = ? WHERE id = ?""",
                (queue_state, workflow_id),
            )
            conn.commit()

    def is_poi_deplicate(self, workflow_id: int, poi: PoiData) -> bool:
        """Check if the POI already exists in the database."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM pois WHERE workflow_id = ? AND name = ? LIMIT 1",
                (workflow_id, poi.name),
            )
            return bool(cursor.fetchone())

    def add_poi(self, workflow_id: int, url: str, poi: PoiData) -> None:
        """Add a new POI to the database."""
        if self.is_poi_deplicate(workflow_id, poi):
            return

        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT INTO pois (workflow_id, url, name, description, category, location) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    workflow_id,
                    url,
                    poi.name,
                    poi.description,
                    poi.category,
                    poi.location,
                ),
            )
            conn.commit()

    def get_all_pois(self, workflow_id: int) -> Dict[str, List[PoiData]]:
        """Retrieve all POIs for a workflow grouped by URL."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT url, name, description, category, location FROM pois WHERE workflow_id = ? ORDER BY url",
                (workflow_id,),
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

    def mark_workflow_completed(self, workflow_id: int) -> None:
        """Mark workflow as completed and clear queue state."""
        with get_connection(self.db_path) as conn:
            conn.execute(
                """UPDATE workflows SET status = 'completed', queue_state = NULL WHERE id = ?""",
                (workflow_id,),
            )
            conn.commit()
