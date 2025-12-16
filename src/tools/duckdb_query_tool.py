from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, List, Optional

import duckdb
from smolagents import Tool

from .duckdb_schema_manager import SchemaManager

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASES_ROOT = PROJECT_ROOT / "databases"

__all__ = ["DuckDBQueryTool", "DEFAULT_DATABASES_ROOT", "StructuredQueryResult"]


@dataclass(slots=True)
class StructuredQueryResult:
    """Structured DuckDB query response suitable for JSON serialisation."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    database: Optional[str] = None
    project: Optional[str] = None
    message: Optional[str] = None


class DuckDBQueryTool(Tool):
    """Tool that locates DuckDB databases and executes SQL queries on demand."""

    name = "duckdb_query"
    output_type = "string"
    description = (
        "Discovers DuckDB database files under configured search roots and executes SQL queries against them. "
        "If no SQL is provided or list_only is true, the tool returns the list of available DuckDB files."
    )
    inputs = {
        "sql": {
            "type": "string",
            "description": (
                "SQL query to execute. Leave empty to only list available DuckDB databases."
            ),
            "nullable": True,
        },
        "database": {
            "type": "string",
            "description": (
                "Optional path or filename of the DuckDB file to query. "
                "If omitted, the tool selects the configured default or the sole discovered database."
            ),
            "nullable": True,
        },
        "list_only": {
            "type": "boolean",
            "description": (
                "When true, only returns the list of discovered DuckDB databases without executing SQL."
            ),
            "nullable": True,
        },
        "create_project": {
            "type": "boolean",
            "description": (
                "When true, creates a new DuckDB project "
                "(provide the desired project name via the 'project' field)."
            ),
            "nullable": True,
        },
        "project": {
            "type": "string",
            "description": (
                "Project name (DuckDB file name without extension) to target when multiple databases exist."
            ),
            "nullable": True,
        },
        "project_description": {
            "type": "string",
            "description": (
                "Optional description to store alongside the project metadata when creating a new project."
            ),
            "nullable": True,
        },
        "output_format": {
            "type": "string",
            "description": "Format for results: 'text' (default), 'table', or 'csv'.",
            "nullable": True,
        },
        "csv_path": {
            "type": "string",
            "description": "Optional filesystem path to export results as CSV.",
            "nullable": True,
        },
        "plan": {
            "type": "string",
            "description": (
                "Implementation plan explaining the reasoning behind this query "
                "(tables chosen, joins, filters, etc.)."
            ),
            "nullable": True,
        },
    }
    outputs = {
        "result": {
            "type": "string",
            "description": "Human-readable description of the discovery results or query output.",
        }
    }

    def __init__(
        self,
        search_roots: Iterable[Path] | None = None,
        default_database: Optional[Path] = None,
    ) -> None:
        super().__init__()
        roots = list(search_roots) if search_roots else [DEFAULT_DATABASES_ROOT]
        self.search_roots = [root.expanduser().resolve() for root in roots]
        self.default_database = default_database.expanduser().resolve() if default_database else None
        self.current_database: Optional[Path] = None
        if self.default_database and self.default_database.exists():
            self.current_database = self.default_database
        self.schema_manager = SchemaManager()
        if self.current_database:
            self.schema_manager.set_database(self.current_database)

    def forward(
        self,
        sql: str = "",
        database: Optional[str] = None,
        list_only: bool = False,
        create_project: Optional[bool] = False,
        project: Optional[str] = None,
        output_format: str = "text",
        csv_path: Optional[str] = None,
        project_description: Optional[str] = None,
        plan: Optional[str] = None,
    ) -> str:
        available = self._discover_databases()

        if create_project:
            if not project or not project.strip():
                raise ValueError("To create a project, supply the desired project name via the 'project' argument.")
            created_path = self._create_project(project, description=project_description or "")
            self.current_database = created_path
            self.schema_manager.set_database(created_path)
            return f"Created new DuckDB project at {created_path}"

        if list_only or not sql.strip():
            return self._format_discovery(available)

        target = self._resolve_database(database, project, available)
        format_choice = (output_format or "text").strip().lower()
        if format_choice not in {"text", "table", "csv"}:
            raise ValueError("output_format must be one of: 'text', 'table', or 'csv'.")

        self.current_database = target
        self.schema_manager.set_database(target)
        try:
            with duckdb.connect(str(target)) as conn:
                cursor = conn.execute(sql)
                description = cursor.description
                if description:
                    columns = [column[0] for column in description]
                    rows = cursor.fetchall()
                    if format_choice == "table":
                        formatted = self._format_table(columns, rows)
                    elif format_choice == "csv":
                        formatted = self._format_csv(columns, rows)
                    else:
                        formatted = self._format_text(columns, rows)
                else:
                    conn.commit()
                    formatted = "Statement executed successfully (no result set returned)."
        except duckdb.Error as exc:
            raise ValueError(f"DuckDB execution error: {exc}") from exc

        export_note = ""
        if csv_path:
            export_target = Path(csv_path).expanduser().resolve()
            export_target.parent.mkdir(parents=True, exist_ok=True)
            with export_target.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                if description:
                    writer.writerow(columns)
                    writer.writerows(rows)
                else:
                    writer.writerow(["message"])
                    writer.writerow([formatted])
            export_note = f"\nCSV export saved to {export_target}"

        header = f"Database: {target} (project: {target.stem})\n"
        tables_in_query = self._extract_tables(sql)
        schema_info = (
            self.schema_manager.describe_tables(tables_in_query)
            if tables_in_query
            else self.schema_manager.project_summary()
        )
        result_text = header + formatted + export_note
        if schema_info:
            result_text += "\n" + schema_info
        return result_text

    # Helper methods -----------------------------------------------------
    def _discover_databases(self) -> List[Path]:
        discovered: List[Path] = []
        seen: set[Path] = set()

        for root in self.search_roots:
            if root.is_file() and root.suffix.lower() == ".duckdb":
                resolved = root.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    discovered.append(resolved)
                continue

            if not root.is_dir():
                continue

            for candidate in root.rglob("*.duckdb"):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    discovered.append(resolved)

        discovered.sort()
        return discovered

    def discover_databases(self) -> List[Path]:
        """Public helper that returns the discovered DuckDB database files."""
        return self._discover_databases()

    def _resolve_database(self, database: Optional[str], project: Optional[str], available: List[Path]) -> Path:
        if database:
            candidate = Path(database).expanduser()
            if candidate.exists():
                return candidate.resolve()

            for root in self.search_roots:
                nested = (root / candidate).resolve()
                if nested.exists():
                    return nested

            matches = [path for path in available if path.name == candidate.name]
            if matches:
                return matches[0]
            raise ValueError(f"Requested database '{database}' was not found among discovered DuckDB files.")

        if project:
            normalized = project.strip().lower()
            if not normalized:
                raise ValueError("Provided project name is empty. Supply a valid project identifier.")

            for path in available:
                # Check both stem and relative path for matches
                if path.stem.lower() == normalized or path.name.lower() == normalized:
                    return path

                # Also check relative path with subdirectories
                for root in self.search_roots:
                    try:
                        rel = path.relative_to(root)
                        rel_name = str(rel.with_suffix("")).replace("\\", "/").lower()
                        if rel_name == normalized:
                            return path
                    except ValueError:
                        continue

            available_projects = ", ".join(path.stem for path in available) or "<none>"
            raise ValueError(
                f"Project '{project}' was not found. Available projects: {available_projects}. "
                "Use project=<name> matching a DuckDB file."
            )

        # If current_database is already set (from UI), use it
        if self.current_database and self.current_database.exists():
            return self.current_database

        if self.default_database and self.default_database.exists():
            return self.default_database

        if len(available) == 1:
            return available[0]

        if not available:
            raise ValueError("No DuckDB databases were discovered. Provide a database path or add DuckDB files.")

        listing = "\n".join(f"{path} (project: {path.stem})" for path in available)
        raise ValueError(
            "Multiple DuckDB projects detected. Specify one using the 'project' argument (matching the DuckDB file name "  # noqa
            "without extension) or provide an explicit 'database' path.\n"
            f"Available options:\n{listing}"
        )

    @staticmethod
    def _format_discovery(available: List[Path]) -> str:
        if not available:
            return "No DuckDB databases found under the configured search roots."

        # Return a minimal response without the full list (the list is shown in UI)
        return f"Found {len(available)} DuckDB project(s). Use the UI to select a project."

    @staticmethod
    def _format_table(columns: List[str], rows: List[tuple]) -> str:
        if not rows:
            return "Query executed successfully but returned no rows."

        str_rows = [[DuckDBQueryTool._stringify(value) for value in row] for row in rows]
        col_widths = [len(col) for col in columns]

        for row in str_rows:
            for idx, value in enumerate(row):
                col_widths[idx] = max(col_widths[idx], len(value))

        # Use Markdown-compatible pipe format with outer pipes
        header = "| " + " | ".join(col.ljust(col_widths[idx]) for idx, col in enumerate(columns)) + " |"
        separator = "| " + " | ".join("-" * col_widths[idx] for idx in range(len(columns))) + " |"
        data_lines = [
            "| " + " | ".join(value.ljust(col_widths[idx]) for idx, value in enumerate(row)) + " |"
            for row in str_rows
        ]

        table = "\n".join([header, separator, *data_lines])
        return f"\n{table}"

    @staticmethod
    def _format_text(columns: List[str], rows: List[tuple]) -> str:
        if not rows:
            return "Query executed successfully but returned no rows."

        # Use Markdown-compatible pipe format
        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join("-" * max(3, len(col)) for col in columns) + " |"

        lines = [header, separator]
        for row in rows:
            lines.append("| " + " | ".join(DuckDBQueryTool._stringify(value) for value in row) + " |")
        return "\n".join(lines)

    @staticmethod
    def _format_csv(columns: List[str], rows: List[tuple]) -> str:
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(columns)
        writer.writerows(rows)
        return buffer.getvalue().strip()

    @staticmethod
    def _stringify(value: object) -> str:
        if value is None:
            return ""

        if isinstance(value, (float, Decimal)):
            val_float = float(value)
            # If the number is very big (millions), no decimals
            if abs(val_float) >= 1_000_000:
                return f"{val_float:,.0f}"

            # If it's effectively an integer, show as integer
            if isinstance(value, float) and value.is_integer():
                return f"{int(value)}"
            if isinstance(value, Decimal) and value % 1 == 0:
                return f"{int(value)}"

            # Otherwise limit to 2 decimals
            return f"{val_float:.2f}"

        return str(value)

    def _slugify(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
        return cleaned.lower()

    def _create_project(self, name: str, *, description: str = "") -> Path:
        display_name = name.strip()
        if not display_name:
            raise ValueError("Project name must not be empty.")
        slug = self._slugify(display_name)
        if not slug:
            raise ValueError("Project name must contain alphanumeric characters.")

        root = self.search_roots[0] if self.search_roots else DEFAULT_DATABASES_ROOT
        root.mkdir(parents=True, exist_ok=True)

        candidate = root / f"{slug}.duckdb"
        counter = 1
        while candidate.exists():
            candidate = root / f"{slug}_{counter}.duckdb"
            counter += 1

        with duckdb.connect(str(candidate)) as conn:
            conn.execute("SELECT 1")

        manager = SchemaManager()
        manager.set_database(candidate)
        manager.set_project_metadata(display_name=display_name, description=description)
        return candidate

    @staticmethod
    def _jsonify(value: object) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (bytes, bytearray, memoryview)):
            return value.hex()
        return str(value)

    def execute_structured(
        self,
        sql: str,
        *,
        database: Optional[str] = None,
        project: Optional[str] = None,
        result_limit: Optional[int] = None,
    ) -> StructuredQueryResult:
        """
        Execute SQL and return structured results ready for JSON serialisation.

        Parameters
        ----------
        sql:
            SQL statement to execute. Required.
        database/project:
            Optional hints for the DuckDB file to target.
        result_limit:
            Optional maximum number of rows to include in the response. When exceeded the data is truncated.
        """

        if not sql or not sql.strip():
            raise ValueError("SQL query is required.")

        available = self._discover_databases()
        target = self._resolve_database(database, project, available)

        self.current_database = target
        self.schema_manager.set_database(target)

        try:
            with duckdb.connect(str(target)) as conn:
                cursor = conn.execute(sql)
                description = cursor.description
                if not description:
                    conn.commit()
                    return StructuredQueryResult(
                        columns=[],
                        rows=[],
                        row_count=0,
                        truncated=False,
                        database=str(target),
                        project=target.stem,
                        message="Statement executed successfully (no result set returned).",
                    )

                columns = [column[0] for column in description]
                fetched_rows = cursor.fetchall()
        except duckdb.Error as exc:
            raise ValueError(f"DuckDB execution error: {exc}") from exc

        total_rows = len(fetched_rows)
        truncated = False
        if result_limit is not None and result_limit >= 0 and total_rows > result_limit:
            fetched_rows = fetched_rows[:result_limit]
            truncated = True

        serialised_rows = [
            [self._jsonify(value) for value in row] for row in fetched_rows
        ]

        return StructuredQueryResult(
            columns=columns,
            rows=serialised_rows,
            row_count=total_rows,
            truncated=truncated,
            database=str(target),
            project=target.stem,
            message=None,
        )

    def list_tables_in_database(self, *, include_views: bool = False) -> List[str]:
        """
        Return the ordered list of tables (and optionally views) present in the active DuckDB database.

        Parameters
        ----------
        include_views:
            When ``True`` also returns views alongside base tables.
        """

        if not self.current_database:
            raise ValueError("No DuckDB database selected. Choose a project first.")

        table_types: list[str] = ["BASE TABLE"]
        if include_views:
            table_types.append("VIEW")

        placeholders_tables = ", ".join("?" for _ in table_types)
        schema_exclusions = ["information_schema", "pg_catalog"]
        placeholders_schemas = ", ".join("?" for _ in schema_exclusions)

        query = f"""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type IN ({placeholders_tables})
              AND table_schema NOT IN ({placeholders_schemas})
            ORDER BY lower(table_schema), lower(table_name), table_name
        """

        try:
            with duckdb.connect(str(self.current_database)) as conn:
                rows = conn.execute(query, table_types + schema_exclusions).fetchall()
        except duckdb.Error as exc:
            raise ValueError(f"Failed to read tables from DuckDB: {exc}") from exc

        results: list[str] = []
        for schema, name in rows:
            schema_name = str(schema or "").strip()
            table_name = str(name or "").strip()
            if not table_name:
                continue

            if schema_name and schema_name.lower() not in {"main"}:
                results.append(f"{schema_name}.{table_name}")
            else:
                results.append(table_name)

        return results

    @property
    def current_project(self) -> Optional[str]:
        if self.current_database:
            return self.current_database.stem
        return None

    @staticmethod
    def _extract_tables(sql: str) -> List[str]:
        if not sql:
            return []
        pattern = re.compile(r"\b(?:from|join)\s+([^\s;]+)", flags=re.IGNORECASE)
        tables: list[str] = []
        seen_lower: set[str] = set()
        for match in pattern.findall(sql):
            candidate = match.strip().strip(",")
            candidate = candidate.strip("`\"[]")
            if candidate:
                table_name = candidate.split(".")[-1]
                lowered = table_name.lower()
                if lowered not in seen_lower:
                    seen_lower.add(lowered)
                    tables.append(table_name)
        return tables

    def fetch_table_schema(self, table: str) -> List[dict[str, object]]:
        if not self.current_database:
            raise ValueError("No DuckDB database selected. Choose a project first.")
        escaped = table.replace("'", "''")
        try:
            with duckdb.connect(str(self.current_database)) as conn:
                cursor = conn.execute(f"PRAGMA table_info('{escaped}')")
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
        except duckdb.Error as exc:
            raise ValueError(f"Failed to inspect table '{table}': {exc}") from exc
        return [dict(zip(columns, row)) for row in rows]
