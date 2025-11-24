from __future__ import annotations

from typing import Optional

from smolagents import Tool

from .duckdb_query_tool import DuckDBQueryTool

__all__ = ["DuckDBSchemaTool"]


class DuckDBSchemaTool(Tool):
    """Tool that manages schema documentation for DuckDB projects."""

    name = "duckdb_schema"
    output_type = "string"
    description = (
        "Retrieves schema information about DuckDB tables, fields, relationships, and saved queries. "
        "Use this tool to understand the database structure before writing SQL queries. "
        "Available actions: list_tables, list_fields, get_table_info, list_saved_queries, get_full_schema."
    )
    inputs = {
        "action": {
            "type": "string",
            "description": (
                "Operation to perform: "
                "list_tables (show all tables), "
                "list_fields (show fields for a table), "
                "get_table_info (detailed table info with fields and relationships), "
                "list_saved_queries (show saved SQL queries), "
                "get_full_schema (complete schema with all tables and fields)."
            ),
            "nullable": False,
        },
        "table_name": {
            "type": "string",
            "description": "Target table name for list_fields or get_table_info actions.",
            "nullable": True,
        },
    }
    outputs = {
        "result": {
            "type": "string",
            "description": "Outcome message or schema content.",
        }
    }

    def __init__(self, query_tool: DuckDBQueryTool) -> None:
        super().__init__()
        self.query_tool = query_tool

    def forward(
        self,
        action: Optional[str] = None,
        table_name: Optional[str] = None,
    ) -> dict[str, str]:
        if not action:
            raise ValueError("Action is required.")

        self._ensure_project_context()
        manager = self.query_tool.schema_manager

        normalized_action = action.strip().lower()

        # List all tables with descriptions
        if normalized_action == "list_tables":
            tables = manager.list_tables()
            if not tables:
                # Fallback to actual DuckDB tables if schema is empty
                try:
                    db_tables = self.query_tool.list_tables_in_database()
                    if db_tables:
                        lines = [f"- {table}" for table in db_tables]
                        return {"result": "Available tables:\n" + "\n".join(lines)}
                except Exception:
                    pass
                return {"result": "No tables found in database."}

            lines = []
            for table in tables:
                table_record = manager.get_table(table) or {}
                short_desc = table_record.get("short_description") or ""
                field_count = len(table_record.get("fields") or {})
                if short_desc:
                    lines.append(f"- {table}: {short_desc} ({field_count} documented fields)")
                else:
                    lines.append(f"- {table} ({field_count} documented fields)")
            return {"result": "Available tables:\n" + "\n".join(lines)}

        # List fields for a specific table
        if normalized_action == "list_fields":
            if not table_name:
                raise ValueError("table_name is required for list_fields action.")

            # Try documented schema first
            table_record = manager.get_table(table_name)
            if table_record and table_record.get("fields"):
                fields = table_record["fields"]
                lines = []
                for field_name, field_data in fields.items():
                    data_type = field_data.get("data_type", "")
                    short_desc = field_data.get("short_description", "")
                    if short_desc:
                        lines.append(f"- {field_name} ({data_type}): {short_desc}")
                    else:
                        lines.append(f"- {field_name} ({data_type})")
                return {"result": f"Fields in {table_name}:\n" + "\n".join(lines)}

            # Fallback to actual DuckDB schema
            try:
                columns = self.query_tool.fetch_table_schema(table_name)
                if columns:
                    lines = [
                        f"- {col.get('name')} ({col.get('type', col.get('column_type', 'unknown'))})"
                        for col in columns
                        if col.get('name')
                    ]
                    return {"result": f"Fields in {table_name}:\n" + "\n".join(lines)}
            except Exception as e:
                return {"result": f"Error fetching fields for {table_name}: {str(e)}"}

            return {"result": f"No fields found for table {table_name}."}

        # Get detailed table information with relationships
        if normalized_action == "get_table_info":
            if not table_name:
                raise ValueError("table_name is required for get_table_info action.")

            table_record = manager.get_table(table_name)
            if not table_record:
                # Try to get basic info from DuckDB
                try:
                    columns = self.query_tool.fetch_table_schema(table_name)
                    if columns:
                        lines = ["Table: " + table_name, "\nFields:"]
                        for col in columns:
                            col_name = col.get('name')
                            col_type = col.get('type', col.get('column_type', 'unknown'))
                            if col_name:
                                lines.append(f"  - {col_name}: {col_type}")
                        return {"result": "\n".join(lines)}
                except Exception:
                    pass
                return {"result": f"Table {table_name} not found."}

            result_lines = [f"Table: {table_name}"]
            if table_record.get("short_description"):
                result_lines.append(f"Description: {table_record['short_description']}")
            if table_record.get("long_description"):
                result_lines.append(f"Details: {table_record['long_description']}")

            fields = table_record.get("fields", {})
            if fields:
                result_lines.append("\nFields:")
                for field_name, field_data in fields.items():
                    data_type = field_data.get("data_type", "")
                    desc = field_data.get("short_description", "")
                    nullability = field_data.get("nullability", "")
                    field_line = f"  - {field_name}"
                    if data_type:
                        field_line += f" ({data_type})"
                    if nullability:
                        field_line += f" [{nullability}]"
                    if desc:
                        field_line += f": {desc}"
                    result_lines.append(field_line)

            relationships = table_record.get("relationships", [])
            if relationships:
                result_lines.append("\nRelationships:")
                for rel in relationships:
                    field = rel.get("field")
                    related_table = rel.get("related_table")
                    related_field = rel.get("related_field")
                    rel_type = rel.get("type", "reference")
                    result_lines.append(
                        f"  - {field} -> {related_table}.{related_field} ({rel_type})"
                    )

            return {"result": "\n".join(result_lines)}

        # List saved queries
        if normalized_action == "list_saved_queries":
            queries = manager.list_queries()
            if not queries:
                return {"result": "No saved queries found."}

            lines = ["Saved queries:"]
            for query in queries:
                name = query.get("name", "Untitled")
                description = query.get("description", "")
                sql = query.get("sql", "")
                if description:
                    lines.append(f"\n- {name}: {description}")
                else:
                    lines.append(f"\n- {name}")
                if sql:
                    # Show first 100 chars of SQL
                    sql_preview = sql[:100] + "..." if len(sql) > 100 else sql
                    lines.append(f"  SQL: {sql_preview}")
            return {"result": "\n".join(lines)}

        # Get full schema summary
        if normalized_action == "get_full_schema":
            tables = manager.list_tables()
            if not tables:
                return {"result": "No schema information available."}

            lines = ["Database Schema Summary:\n"]
            for table in tables:
                table_record = manager.get_table(table) or {}
                short_desc = table_record.get("short_description", "")
                fields = table_record.get("fields", {})

                lines.append(f"\nTable: {table}")
                if short_desc:
                    lines.append(f"  Description: {short_desc}")
                lines.append(f"  Fields ({len(fields)}):")
                for field_name, field_data in fields.items():
                    data_type = field_data.get("data_type", "")
                    lines.append(f"    - {field_name} ({data_type})")

            return {"result": "\n".join(lines)}

        raise ValueError(
            f"Unknown action '{action}'. Supported: list_tables, list_fields, "
            "get_table_info, list_saved_queries, get_full_schema."
        )

    def _ensure_project_context(self) -> None:
        if not self.query_tool.current_database:
            available = self.query_tool._discover_databases()
            if not available:
                raise RuntimeError("No DuckDB databases available.")
            if len(available) > 1:
                raise RuntimeError(
                    "Multiple DuckDB projects detected. "
                    "The project should already be set from the UI."
                )
            self.query_tool.current_database = available[0]
            self.query_tool.schema_manager.set_database(available[0])
