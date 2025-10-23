from __future__ import annotations

import csv
import re
from io import StringIO
from pathlib import Path
from typing import Iterable, List, Optional

import duckdb
from smolagents import Tool

from .duckdb_schema_manager import SchemaManager

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASES_ROOT = PROJECT_ROOT / "databases"

__all__ = ["DuckDBQueryTool", "DEFAULT_DATABASES_ROOT"]


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
            "description": "SQL query to execute. Leave empty to only list available DuckDB databases.",
            "nullable": True,
        },
        "database": {
            "type": "string",
            "description": "Optional path or filename of the DuckDB file to query. "
            "If omitted, the tool selects the configured default or the sole discovered database.",
            "nullable": True,
        },
        "list_only": {
            "type": "boolean",
            "description": "When true, only returns the list of discovered DuckDB databases without executing SQL.",
            "nullable": True,
        },
        "project": {
            "type": "string",
            "description": "Project name (DuckDB file name without extension) to target when multiple databases exist.",
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
        project: Optional[str] = None,
        output_format: str = "text",
        csv_path: Optional[str] = None,
    ) -> str:
        available = self._discover_databases()

        if list_only or not sql.strip():
            return self._format_discovery(available)

        target = self._resolve_database(database, project, available)
        format_choice = (output_format or "text").strip().lower()
        if format_choice not in {"text", "table", "csv"}:
            raise ValueError("output_format must be one of: 'text', 'table', or 'csv'.")

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
        footer = "\n" + self._format_discovery(available)
        self.current_database = target
        result_text = header + formatted + export_note
        if schema_info:
            result_text += "\n" + schema_info
        result_text += footer
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
                if path.stem.lower() == normalized or path.name.lower() == normalized:
                    return path

            available_projects = ", ".join(path.stem for path in available) or "<none>"
            raise ValueError(
                f"Project '{project}' was not found. Available projects: {available_projects}. "
                "Use project=<name> matching a DuckDB file."
            )

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

        lines = ["Discovered DuckDB databases:"]
        lines.extend(f"- {path} (project: {path.stem})" for path in available)
        return "\n".join(lines)

    @staticmethod
    def _format_table(columns: List[str], rows: List[tuple]) -> str:
        if not rows:
            return "Query executed successfully but returned no rows."

        str_rows = [[DuckDBQueryTool._stringify(value) for value in row] for row in rows]
        col_widths = [len(col) for col in columns]

        for row in str_rows:
            for idx, value in enumerate(row):
                col_widths[idx] = max(col_widths[idx], len(value))

        header = " | ".join(col.ljust(col_widths[idx]) for idx, col in enumerate(columns))
        separator = "-+-".join("-" * col_widths[idx] for idx in range(len(columns)))
        data_lines = [
            " | ".join(value.ljust(col_widths[idx]) for idx, value in enumerate(row)) for row in str_rows
        ]

        table = "\n".join([header, separator, *data_lines])
        return f"\n{table}"

    @staticmethod
    def _format_text(columns: List[str], rows: List[tuple]) -> str:
        if not rows:
            return "Query executed successfully but returned no rows."

        lines = ["\t".join(columns)]
        for row in rows:
            lines.append("\t".join(DuckDBQueryTool._stringify(value) for value in row))
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
        return str(value)

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
