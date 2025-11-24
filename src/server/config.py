from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(slots=True)
class DatalakeConfig:
    """Configuration for a datalake."""

    name: str
    type: str
    connection_string: str
    container_name: str = "dbdocumenter"


# Path to the datalakes configuration file
DATALAKES_CONFIG_FILE = Path.cwd() / "datalakes.config.json"


def save_datalakes_config(datalakes: List[DatalakeConfig]) -> None:
    """Save datalakes configuration to file."""
    try:
        data = [
            {
                "name": dl.name,
                "type": dl.type,
                "connection_string": dl.connection_string,
                "container_name": dl.container_name,
            }
            for dl in datalakes
        ]
        DATALAKES_CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Warning: Failed to save datalakes config: {e}")


def load_datalakes_from_file() -> List[DatalakeConfig]:
    """Load datalakes configuration from file."""
    datalakes: List[DatalakeConfig] = []
    if DATALAKES_CONFIG_FILE.exists():
        try:
            data = json.loads(DATALAKES_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        datalakes.append(
                            DatalakeConfig(
                                name=item.get("name", ""),
                                type=item.get("type", "azure_storage"),
                                connection_string=item.get("connection_string", ""),
                                container_name=item.get("container_name", "dbdocumenter"),
                            )
                        )
        except Exception as e:
            print(f"Warning: Failed to load datalakes config: {e}")
    return datalakes


@dataclass(slots=True)
class ServerSettings:
    """Runtime configuration for the FastAPI server."""

    host: str = "127.0.0.1"
    port: int = 8000
    allowed_origins: List[str] = field(default_factory=list)
    query_default_limit: int = 200
    agent_max_steps: int = 8
    datalakes: List[DatalakeConfig] = field(default_factory=list)

    @classmethod
    def load(cls) -> "ServerSettings":
        host = os.environ.get("DBDOC_API_HOST", "127.0.0.1")
        port_value = os.environ.get("DBDOC_API_PORT", "8000")
        try:
            port = int(port_value)
        except ValueError:
            port = 8000

        origins_raw = os.environ.get("DBDOC_CORS_ORIGINS", "")
        origins = [origin.strip() for origin in origins_raw.split(",") if origin.strip()]
        if not origins:
            origins = ["http://localhost:5173"]

        query_limit_value = os.environ.get("DBDOC_QUERY_LIMIT", "")
        try:
            query_default_limit = int(query_limit_value) if query_limit_value else 200
        except ValueError:
            query_default_limit = 200

        max_steps_value = os.environ.get("DBDOC_AGENT_MAX_STEPS", "")
        try:
            agent_max_steps = int(max_steps_value) if max_steps_value else 8
        except ValueError:
            agent_max_steps = 8

        # Load datalakes configuration from JSON environment variable
        datalakes: List[DatalakeConfig] = []
        datalakes_json = os.environ.get("DBDOC_DATALAKES", "")
        if datalakes_json:
            try:
                datalakes_data = json.loads(datalakes_json)
                if isinstance(datalakes_data, list):
                    for item in datalakes_data:
                        if isinstance(item, dict):
                            datalakes.append(
                                DatalakeConfig(
                                    name=item.get("name", ""),
                                    type=item.get("type", "azure_storage"),
                                    connection_string=item.get("connection_string", ""),
                                    container_name=item.get("container_name", "dbdocumenter"),
                                )
                            )
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, ignore and continue with empty list
                pass

        # Also load datalakes from config file (if exists)
        file_datalakes = load_datalakes_from_file()

        # Merge file-based datalakes, avoiding duplicates
        existing_names = {dl.name for dl in datalakes}
        for file_dl in file_datalakes:
            if file_dl.name not in existing_names:
                datalakes.append(file_dl)
                existing_names.add(file_dl.name)

        return cls(
            host=host,
            port=port,
            allowed_origins=origins,
            query_default_limit=query_default_limit,
            agent_max_steps=agent_max_steps,
            datalakes=datalakes,
        )


__all__ = [
    "ServerSettings",
    "DatalakeConfig",
    "save_datalakes_config",
    "load_datalakes_from_file",
    "DATALAKES_CONFIG_FILE",
]
