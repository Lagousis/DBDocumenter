from __future__ import annotations

import json
import re
from typing import Optional

from smolagents import Tool

from .duckdb_schema_manager import SchemaManager
from .duckdb_query_tool import DuckDBQueryTool

__all__ = ["DuckDBSchemaTool"]


class DuckDBSchemaTool(Tool):
    """Tool that manages schema documentation for DuckDB projects."""

    name = "duckdb_schema"
    output_type = "string"
    description = (
        "Reads or updates structured documentation about DuckDB projects, including table descriptions, "
        "field metadata, allowed values, relationships, and structured summaries of documented tables/fields."
    )
    inputs = {
        "action": {
            "type": "string",
            "description": "Operation to perform: get_schema, list_tables, list_fields, set_project_description, "
            "set_table, set_field, add_relationship, auto_document_table, list_pending_fields, summarize_table.",
            "nullable": False,
        },
        "project": {
            "type": "string",
            "description": "Optional project name to switch to before applying the action.",
            "nullable": True,
        },
        "table": {
            "type": "string",
            "description": "Target table name for table/field actions.",
            "nullable": True,
        },
        "field": {
            "type": "string",
            "description": "Target field/column name for field actions.",
            "nullable": True,
        },
        "short_description": {
            "type": "string",
            "description": "Short description text.",
            "nullable": True,
        },
        "long_description": {
            "type": "string",
            "description": "Longer narrative description.",
            "nullable": True,
        },
        "nullability": {
            "type": "string",
            "description": "Nullability information (e.g., nullable, not nullable).",
            "nullable": True,
        },
        "data_type": {
            "type": "string",
            "description": "Data type of the field.",
            "nullable": True,
        },
        "values_json": {
            "type": "string",
            "description": "JSON object mapping option values, e.g. {\"1\": \"B2B\"}.",
            "nullable": True,
        },
        "relationship_type": {
            "type": "string",
            "description": "Relationship type (e.g. foreign_key, reference).",
            "nullable": True,
        },
        "related_table": {
            "type": "string",
            "description": "Related table name when adding relationships.",
            "nullable": True,
        },
        "related_field": {
            "type": "string",
            "description": "Related field name when adding relationships.",
            "nullable": True,
        },
        "relationship_description": {
            "type": "string",
            "description": "Descriptive text for the relationship.",
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
        project: Optional[str] = None,
        table: Optional[str] = None,
        field: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
        nullability: Optional[str] = None,
        data_type: Optional[str] = None,
        values_json: Optional[str] = None,
        relationship_type: Optional[str] = None,
        related_table: Optional[str] = None,
        related_field: Optional[str] = None,
        relationship_description: Optional[str] = None,
    ) -> dict[str, str]:
        if not action:
            raise ValueError("Action is required.")

        self._ensure_project_context(project)
        manager = self.query_tool.schema_manager

        normalized_action = action.strip().lower()
        if normalized_action == "get_schema":
            return {"result": manager.get_schema_json()}
        if normalized_action == "list_tables":
            tables = manager.list_tables()
            if not tables:
                return {"result": "No tables have been documented yet."}
            lines = []
            for table_name in tables:
                table_record = manager.get_table(table_name) or {}
                field_count = len(table_record.get("fields") or {})
                short_desc = table_record.get("short_description") or ""
                details = [f"{field_count} field(s)"]
                if short_desc:
                    details.insert(0, short_desc)
                summary = " | ".join(details)
                lines.append(f"- {table_name}: {summary}")
            return {"result": "Documented tables:\n" + "\n".join(lines)}
        if normalized_action in {"list_fields", "list_table_fields"}:
            fields_map = manager.list_fields(table)
            if table and not fields_map:
                raise ValueError(f"Table '{table}' is not documented yet.")
            if not fields_map:
                return {"result": "No fields have been documented yet."}
            lines = []
            for table_name, fields in fields_map.items():
                if fields:
                    lines.append(f"- {table_name}: {', '.join(fields)}")
                else:
                    lines.append(f"- {table_name}: No fields documented yet.")
            return {"result": "Documented fields:\n" + "\n".join(lines)}
        if normalized_action == "set_project_description":
            if not long_description and not short_description:
                raise ValueError("Provide short_description or long_description to describe the project.")
            description_parts = []
            if short_description:
                description_parts.append(short_description)
            if long_description:
                description_parts.append(long_description)
            manager.set_project_description(" ".join(description_parts))
            return {"result": "Project description updated."}
        if normalized_action == "set_table":
            if not table:
                raise ValueError("Table name is required for set_table action.")
            record = manager.update_table(table, short_description=short_description, long_description=long_description)
            return {"result": f"Table '{table}' updated: {json.dumps(record, indent=2, ensure_ascii=False)}"}
        if normalized_action == "set_field":
            if not table or not field:
                raise ValueError("Both table and field names are required for set_field action.")
            values = self._parse_values(values_json) if values_json else None
            record = manager.update_field(
                table,
                field,
                short_description=short_description,
                long_description=long_description,
                nullability=nullability,
                data_type=data_type,
                values=values,
            )
            return {
                "result": f"Field '{table}.{field}' updated: {json.dumps(record, indent=2, ensure_ascii=False)}"
            }
        if normalized_action == "add_relationship":
            if not table or not field or not related_table or not related_field:
                raise ValueError("Table, field, related_table, and related_field are required for add_relationship.")
            record = manager.add_relationship(
                table,
                field,
                related_table,
                related_field,
                relationship_type=relationship_type,
                description=relationship_description,
            )
            return {
                "result": "Relationship recorded: " + json.dumps(record, indent=2, ensure_ascii=False)
            }

        if normalized_action == "auto_document_table":
            if not table:
                raise ValueError("Table name is required for auto_document_table action.")
            columns = self.query_tool.fetch_table_schema(table)
            if not columns:
                return {"result": f"No columns found for table '{table}'. Ensure the table exists in DuckDB."}

            manager.update_table(table, short_description=short_description, long_description=long_description)
            updated_fields = 0
            for column in columns:
                column_name = column.get("name")
                if not column_name:
                    continue
                existing = manager.get_field(table, column_name)
                updates: dict[str, Optional[str]] = {}
                column_type = column.get("type") or column.get("column_type")
                if column_type and (not existing or not existing.get("data_type")):
                    updates["data_type"] = column_type
                notnull = column.get("notnull")
                if notnull is not None:
                    nullability_value = "not nullable" if bool(notnull) else "nullable"
                    if not existing or not existing.get("nullability"):
                        updates["nullability"] = nullability_value
                if not existing or not existing.get("short_description"):
                    updates["short_description"] = self._generate_short_description(column_name)
                if updates:
                    manager.update_field(table, column_name, **updates)
                    updated_fields += 1

            pending_text = manager.format_pending_fields(table)
            summary = manager.format_table_summary(table)
            message = f"Auto-documented {updated_fields} field(s) for table '{table}'."
            if short_description or long_description:
                message += " Table descriptions updated."
            return {"result": f"{message}\n{pending_text}\n\n{summary}"}

        if normalized_action in {"list_pending_fields", "list_missing_fields"}:
            result = manager.format_pending_fields(table)
            return {"result": result}

        if normalized_action == "summarize_table":
            if not table:
                raise ValueError("Table name is required for summarize_table action.")
            summary = manager.format_table_summary(table)
            return {"result": summary}

        raise ValueError(
            "Unknown action. Supported actions: get_schema, list_tables, list_fields, set_project_description, set_table, set_field, "
            "add_relationship, auto_document_table, list_pending_fields, summarize_table."
        )

    def _ensure_project_context(self, project: Optional[str]) -> None:
        if project:
            available = self.query_tool._discover_databases()
            target = self.query_tool._resolve_database(None, project, available)
            self.query_tool.current_database = target
            self.query_tool.schema_manager.set_database(target)
            return

        if not self.query_tool.current_database:
            available = self.query_tool._discover_databases()
            if not available:
                raise RuntimeError("No DuckDB databases available to document.")
            if len(available) > 1:
                raise RuntimeError(
                    "Multiple DuckDB projects detected. Specify the target project name when using schema actions."
                )
            self.query_tool.current_database = available[0]
            self.query_tool.schema_manager.set_database(available[0])

    @staticmethod
    def _parse_values(values_json: str) -> dict[str, str]:
        try:
            parsed = json.loads(values_json)
        except json.JSONDecodeError as exc:
            raise ValueError("values_json must be a valid JSON object.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("values_json must decode to a JSON object mapping values to labels.")
        return {str(key): str(value) for key, value in parsed.items()}

    @staticmethod
    def _generate_short_description(name: str) -> str:
        cleaned = name.replace("_", " ").strip()
        if not cleaned:
            return "Field description pending."
        words = re.split(r"\s+", cleaned)
        title = " ".join(word.capitalize() for word in words if word)
        return title or "Field description pending."
