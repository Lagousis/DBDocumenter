"""Datalake manager for coordinating multiple datalake adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .azure_storage_adapter import ProjectMetadata

from .azure_storage_adapter import AzureStorageAdapter


@dataclass
class DatalakeConfig:
    """Configuration for a datalake."""

    name: str
    type: str  # Currently only "azure_storage"
    connection_string: str
    container_name: str = "dbdocumenter"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "connection_string": self.connection_string,
            "container_name": self.container_name,
        }


class DatalakeManager:
    """Manages multiple datalakes and coordinates operations."""

    def __init__(self, datalake_configs: list[DatalakeConfig] | None = None):
        """
        Initialize datalake manager.

        Args:
            datalake_configs: List of datalake configurations
        """
        self.datalakes: dict[str, AzureStorageAdapter] = {}
        self.configs: dict[str, DatalakeConfig] = {}
        # Track which configs came from environment (read-only) vs runtime (can be persisted)
        self.env_configs: set[str] = set()

        if datalake_configs:
            for config in datalake_configs:
                self.add_datalake(config, from_env=True)

    def add_datalake(self, config: DatalakeConfig, from_env: bool = False) -> None:
        """
        Add a datalake to the manager.

        Args:
            config: Datalake configuration
            from_env: Whether this config came from environment variable (read-only)

        Raises:
            ValueError: If datalake type is not supported or name already exists
        """
        if config.name in self.datalakes:
            raise ValueError(f"Datalake '{config.name}' already exists")

        if config.type == "azure_storage":
            adapter = AzureStorageAdapter(
                connection_string=config.connection_string,
                container_name=config.container_name,
            )
            self.datalakes[config.name] = adapter
            self.configs[config.name] = config
            if from_env:
                self.env_configs.add(config.name)
        else:
            raise ValueError(f"Unsupported datalake type: {config.type}")

    def remove_datalake(self, name: str) -> bool:
        """
        Remove a datalake from the manager.

        Args:
            name: Name of the datalake to remove

        Returns:
            True if datalake was removed, False if not found
        """
        if name in self.datalakes:
            del self.datalakes[name]
            if name in self.configs:
                del self.configs[name]
            if name in self.env_configs:
                self.env_configs.discard(name)
            return True
        return False

    def list_datalakes(self) -> list[str]:
        """
        List all configured datalake names.

        Returns:
            List of datalake names
        """
        return sorted(self.datalakes.keys())

    def get_datalake_info(self, name: str) -> dict[str, str] | None:
        """
        Get full information about a datalake including storage account name.

        Args:
            name: Name of the datalake

        Returns:
            Dictionary with datalake info or None if not found
        """
        if name not in self.configs:
            return None

        config = self.configs[name]
        info = {
            "name": config.name,
            "type": config.type,
            "container_name": config.container_name,
        }

        # Extract storage account name from connection string for Azure Storage
        if config.type == "azure_storage":
            try:
                # Connection string format: AccountName=xxx;AccountKey=yyy;...
                parts = config.connection_string.split(";")
                for part in parts:
                    if part.startswith("AccountName="):
                        info["storage_account"] = part.split("=", 1)[1]
                        break
            except Exception:
                info["storage_account"] = "Unknown"

        return info

    def get_persistable_configs(self) -> list[DatalakeConfig]:
        """
        Get list of datalake configs that should be persisted to file.
        Excludes configs that came from environment variables.

        Returns:
            List of DatalakeConfig objects that are not from environment
        """
        return [
            config
            for name, config in self.configs.items()
            if name not in self.env_configs
        ]

    def get_datalake(self, name: str) -> AzureStorageAdapter | None:
        """
        Get a datalake adapter by name.

        Args:
            name: Name of the datalake

        Returns:
            Datalake adapter or None if not found
        """
        return self.datalakes.get(name)

    def list_projects(self, datalake_name: str) -> list[ProjectMetadata]:
        """
        List projects in a specific datalake.

        Args:
            datalake_name: Name of the datalake

        Returns:
            List of project metadata

        Raises:
            ValueError: If datalake not found
        """
        adapter = self.get_datalake(datalake_name)
        if not adapter:
            raise ValueError(f"Datalake '{datalake_name}' not found")

        return adapter.list_projects()

    def download_project(
        self,
        datalake_name: str,
        project_name: str,
        version: str,
        local_dir: Path,
        *,
        overwrite: bool = False,
    ) -> tuple[Path, Path]:
        """
        Download a project from a datalake.

        Args:
            datalake_name: Name of the datalake
            project_name: Name of the project
            version: Version to download
            local_dir: Local directory to download to
            overwrite: Whether to overwrite existing files

        Returns:
            Tuple of (duckdb_path, schema_path)

        Raises:
            ValueError: If datalake not found
        """
        adapter = self.get_datalake(datalake_name)
        if not adapter:
            raise ValueError(f"Datalake '{datalake_name}' not found")

        return adapter.download_project(project_name, version, local_dir, overwrite=overwrite)

    def upload_project(
        self,
        datalake_name: str,
        project_name: str,
        version: str,
        duckdb_path: Path,
        schema_path: Path,
        schema_only: bool = False,
    ) -> None:
        """
        Upload a project to a datalake.

        Args:
            datalake_name: Name of the datalake
            project_name: Name of the project
            version: Version string
            duckdb_path: Path to local DuckDB file
            schema_path: Path to local schema JSON file
            schema_only: Whether to upload only the schema file

        Raises:
            ValueError: If datalake not found
        """
        adapter = self.get_datalake(datalake_name)
        if not adapter:
            raise ValueError(f"Datalake '{datalake_name}' not found")

        adapter.upload_project(project_name, version, duckdb_path, schema_path, schema_only=schema_only)

    def delete_project(self, datalake_name: str, project_name: str, version: str) -> None:
        """
        Delete a project version from a datalake.

        Args:
            datalake_name: Name of the datalake
            project_name: Name of the project
            version: Version to delete

        Raises:
            ValueError: If datalake not found
        """
        adapter = self.get_datalake(datalake_name)
        if not adapter:
            raise ValueError(f"Datalake '{datalake_name}' not found")

        adapter.delete_project(project_name, version)

    def project_exists(self, datalake_name: str, project_name: str, version: str) -> bool:
        """
        Check if a project version exists in a datalake.

        Args:
            datalake_name: Name of the datalake
            project_name: Name of the project
            version: Version to check

        Returns:
            True if the project version exists

        Raises:
            ValueError: If datalake not found
        """
        adapter = self.get_datalake(datalake_name)
        if not adapter:
            raise ValueError(f"Datalake '{datalake_name}' not found")

        return adapter.project_exists(project_name, version)

    def get_latest_version(self, datalake_name: str, project_name: str) -> str | None:
        """
        Get the latest version of a project in a datalake.

        Args:
            datalake_name: Name of the datalake
            project_name: Name of the project

        Returns:
            Latest version string or None if project doesn't exist

        Raises:
            ValueError: If datalake not found
        """
        adapter = self.get_datalake(datalake_name)
        if not adapter:
            raise ValueError(f"Datalake '{datalake_name}' not found")

        return adapter.get_latest_version(project_name)

    def get_all_projects(self) -> dict[str, list[ProjectMetadata]]:
        """
        Get all projects from all datalakes.

        Returns:
            Dictionary mapping datalake name to list of project metadata
        """
        result: dict[str, list[ProjectMetadata]] = {}

        for name in self.list_datalakes():
            try:
                result[name] = self.list_projects(name)
            except Exception:
                # Skip datalakes that fail to list
                result[name] = []

        return result
