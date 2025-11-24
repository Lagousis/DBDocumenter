"""Azure Blob Storage adapter for datalake operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from azure.storage.blob import BlobServiceClient, ContainerClient


@dataclass
class ProjectMetadata:
    """Metadata for a project stored in datalake."""

    name: str
    version: str
    display_name: str
    description: str
    last_modified: str
    size_bytes: int  # Total size (for backward compatibility)
    db_size_bytes: int = 0  # DuckDB file size
    schema_size_bytes: int = 0  # Schema JSON file size

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "last_modified": self.last_modified,
            "size_bytes": self.size_bytes,
            "db_size_bytes": self.db_size_bytes,
            "schema_size_bytes": self.schema_size_bytes,
        }


class AzureStorageAdapter:
    """Adapter for Azure Blob Storage operations."""

    def __init__(self, connection_string: str, container_name: str = "dbdocumenter"):
        """
        Initialize Azure Storage adapter.

        Args:
            connection_string: Azure Storage connection string
            container_name: Container name for storing projects (default: dbdocumenter)
        """
        self.blob_service = BlobServiceClient.from_connection_string(connection_string)
        self.container_name = container_name
        self._ensure_container()

    def _ensure_container(self) -> None:
        """Ensure the container exists, create if it doesn't."""
        try:
            container_client = self.blob_service.get_container_client(self.container_name)
            if not container_client.exists():
                self.blob_service.create_container(self.container_name)
        except Exception as e:
            raise RuntimeError(f"Failed to ensure container '{self.container_name}': {e}") from e

    def _get_container_client(self) -> ContainerClient:
        """Get container client."""
        return self.blob_service.get_container_client(self.container_name)

    def _blob_path(self, project_name: str, version: str, filename: str) -> str:
        """
        Generate blob path in format: dbdocumenter/project_name/version/filename.

        Args:
            project_name: Name of the project
            version: Version string (e.g., "1.0.0")
            filename: File name (e.g., "myproject.duckdb" or "myproject.schema.json")

        Returns:
            Blob path string
        """
        return f"dbdocumenter/{project_name}/{version}/{filename}"

    def list_projects(self) -> list[ProjectMetadata]:
        """
        List all projects available in the datalake.

        Returns:
            List of ProjectMetadata objects
        """
        container = self._get_container_client()
        projects: dict[tuple[str, str], dict] = {}  # Store file info temporarily

        try:
            # List all blobs with size information included
            # Note: list_blobs() returns BlobProperties which includes 'size' attribute
            for blob in container.list_blobs(include=['metadata']):
                parts = blob.name.split("/")
                if len(parts) != 4:  # dbdocumenter/project_name/version/filename
                    continue

                folder, project_name, version, filename = parts

                # Verify it's in the dbdocumenter folder
                if folder != "dbdocumenter":
                    continue

                key = (project_name, version)

                # Initialize project entry if not exists
                if key not in projects:
                    projects[key] = {
                        "name": project_name,
                        "version": version,
                        "display_name": project_name,
                        "description": "",
                        "last_modified": "",
                        "db_size": 0,
                        "schema_size": 0,
                    }

                # Get blob size - use the size property from BlobProperties
                # If list_blobs doesn't populate size, we need to get blob client
                blob_size = blob.size if hasattr(blob, 'size') and blob.size is not None else 0

                # If size is still 0, try getting it from blob client
                if blob_size == 0:
                    try:
                        blob_client = container.get_blob_client(blob.name)
                        properties = blob_client.get_blob_properties()
                        blob_size = properties.size
                    except Exception:
                        blob_size = 0

                # Track file sizes
                if filename.endswith(".duckdb"):
                    projects[key]["db_size"] = blob_size
                    if blob.last_modified:
                        projects[key]["last_modified"] = blob.last_modified.isoformat()
                elif filename.endswith(".schema.json"):
                    projects[key]["schema_size"] = blob_size
                    if blob.last_modified and not projects[key]["last_modified"]:
                        projects[key]["last_modified"] = blob.last_modified.isoformat()

                    # Download and parse schema.json to get display name and description
                    try:
                        blob_client = container.get_blob_client(blob.name)
                        schema_data = blob_client.download_blob().readall()
                        schema = json.loads(schema_data)
                        projects[key]["display_name"] = schema.get("project_display_name", project_name)
                        projects[key]["description"] = schema.get("project_description", "")
                    except Exception:
                        pass  # Keep default values

        except Exception as e:
            raise RuntimeError(f"Failed to list projects from datalake: {e}") from e

        # Convert to ProjectMetadata objects
        result = []
        for info in projects.values():
            result.append(ProjectMetadata(
                name=info["name"],
                version=info["version"],
                display_name=info["display_name"],
                description=info["description"],
                last_modified=info["last_modified"],
                size_bytes=info["db_size"] + info["schema_size"],
                db_size_bytes=info["db_size"],
                schema_size_bytes=info["schema_size"],
            ))

        return sorted(result, key=lambda p: (p.name, p.version))

    def download_project(
        self,
        project_name: str,
        version: str,
        local_dir: Path,
        *,
        overwrite: bool = False,
    ) -> tuple[Path, Path]:
        """
        Download a project from the datalake to local directory.

        Args:
            project_name: Name of the project
            version: Version to download
            local_dir: Local directory to download to
            overwrite: Whether to overwrite existing files

        Returns:
            Tuple of (duckdb_path, schema_path)

        Raises:
            FileExistsError: If files exist and overwrite is False
            RuntimeError: If download fails
        """
        container = self._get_container_client()
        local_dir.mkdir(parents=True, exist_ok=True)

        duckdb_filename = f"{project_name}.duckdb"
        schema_filename = f"{project_name}.schema.json"

        duckdb_local = local_dir / duckdb_filename
        schema_local = local_dir / schema_filename

        # Check if files exist
        if not overwrite:
            if duckdb_local.exists() or schema_local.exists():
                raise FileExistsError(
                    "Project files already exist locally. "
                    "Use overwrite=True or rename existing files."
                )

        try:
            # Download DuckDB file
            duckdb_blob = self._blob_path(project_name, version, duckdb_filename)
            blob_client = container.get_blob_client(duckdb_blob)
            with open(duckdb_local, "wb") as f:
                f.write(blob_client.download_blob().readall())

            # Download schema file
            schema_blob = self._blob_path(project_name, version, schema_filename)
            blob_client = container.get_blob_client(schema_blob)
            with open(schema_local, "wb") as f:
                f.write(blob_client.download_blob().readall())

            return (duckdb_local, schema_local)

        except Exception as e:
            # Clean up partial downloads
            if duckdb_local.exists():
                duckdb_local.unlink()
            if schema_local.exists():
                schema_local.unlink()
            raise RuntimeError(f"Failed to download project '{project_name}' v{version}: {e}") from e

    def upload_project(
        self,
        project_name: str,
        version: str,
        duckdb_path: Path,
        schema_path: Path,
        schema_only: bool = False,
    ) -> None:
        """
        Upload a project to the datalake using chunked upload for better reliability.

        Args:
            project_name: Name of the project
            version: Version string
            duckdb_path: Path to local DuckDB file
            schema_path: Path to local schema JSON file
            schema_only: Whether to upload only the schema file

        Raises:
            FileNotFoundError: If local files don't exist
            RuntimeError: If upload fails
        """
        if not schema_only and not duckdb_path.exists():
            raise FileNotFoundError(f"DuckDB file not found: {duckdb_path}")
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        container = self._get_container_client()

        try:
            # Upload DuckDB file with chunking (4MB chunks) if not schema_only
            if not schema_only:
                # Use project_name for blob name to ensure canonical naming
                blob_name = f"{project_name}.duckdb"
                duckdb_blob = self._blob_path(project_name, version, blob_name)
                blob_client = container.get_blob_client(duckdb_blob)
                with open(duckdb_path, "rb") as f:
                    blob_client.upload_blob(
                        f,
                        overwrite=True,
                        max_concurrency=4,  # Use parallel uploads
                    )

            # Upload schema file
            # Use project_name for blob name to ensure canonical naming
            blob_name = f"{project_name}.schema.json"
            schema_blob = self._blob_path(project_name, version, blob_name)
            blob_client = container.get_blob_client(schema_blob)
            with open(schema_path, "rb") as f:
                blob_client.upload_blob(f, overwrite=True)

        except Exception as e:
            raise RuntimeError(f"Failed to upload project '{project_name}' v{version}: {e}") from e

    def delete_project(self, project_name: str, version: str) -> None:
        """
        Delete a project version from the datalake.

        Args:
            project_name: Name of the project
            version: Version to delete

        Raises:
            RuntimeError: If deletion fails
        """
        container = self._get_container_client()

        try:
            # Delete all blobs in the dbdocumenter/project/version directory
            prefix = f"dbdocumenter/{project_name}/{version}/"
            blobs_to_delete = container.list_blobs(name_starts_with=prefix)

            for blob in blobs_to_delete:
                blob_client = container.get_blob_client(blob.name)
                blob_client.delete_blob()

        except Exception as e:
            raise RuntimeError(f"Failed to delete project '{project_name}' v{version}: {e}") from e

    def project_exists(self, project_name: str, version: str) -> bool:
        """
        Check if a project version exists in the datalake.

        Args:
            project_name: Name of the project
            version: Version to check

        Returns:
            True if the project version exists
        """
        container = self._get_container_client()

        try:
            # Check if schema file exists
            schema_blob = self._blob_path(project_name, version, f"{project_name}.schema.json")
            blob_client = container.get_blob_client(schema_blob)
            return blob_client.exists()
        except Exception:
            return False

    def get_latest_version(self, project_name: str) -> Optional[str]:
        """
        Get the latest version of a project.

        Args:
            project_name: Name of the project

        Returns:
            Latest version string or None if project doesn't exist
        """
        projects = self.list_projects()
        versions = [p.version for p in projects if p.name == project_name]

        if not versions:
            return None

        # Simple semantic version sort (assumes format like "1.0.0")
        try:
            sorted_versions = sorted(
                versions,
                key=lambda v: tuple(int(x) for x in v.split(".")),
                reverse=True,
            )
            return sorted_versions[0]
        except (ValueError, AttributeError):
            # Fallback to string sort if not semantic versioning
            return sorted(versions, reverse=True)[0]
