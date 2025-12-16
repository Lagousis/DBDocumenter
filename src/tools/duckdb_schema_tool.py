from __future__ import annotations

import json
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
                "get_full_schema (complete schema with all tables and fields), "
                "search_fields (search for fields across all tables), "
                "update_field (update field metadata), "
                "update_table (update table metadata), "
                "update_fields_batch (update multiple fields at once), "
                "infer_nullability (check all fields in a table for null values)."
            ),
            "nullable": False,
        },
        "table_name": {
            "type": "string",
            "description": "Target table name.",
            "nullable": True,
        },
        "query": {
            "type": "string",
            "description": "Search query for search_fields action.",
            "nullable": True,
        },
        "field_name": {
            "type": "string",
            "description": "Target field name (required for update_field).",
            "nullable": True,
        },
        "fields_json": {
            "type": "string",
            "description": (
                "JSON string list of fields for update_fields_batch. "
                "Example: '[{\"name\": \"col1\", \"short_description\": \"desc\", \"nullability\": \"NOT NULL\"}]'"
            ),
            "nullable": True,
        },
        "short_description": {
            "type": "string",
            "description": "Short description/summary for the table or field.",
            "nullable": True,
        },
        "long_description": {
            "type": "string",
            "description": "Detailed description for the table or field.",
            "nullable": True,
        },
        "data_type": {
            "type": "string",
            "description": "Data type for the field (e.g., INTEGER, VARCHAR).",
            "nullable": True,
        },
        "nullability": {
            "type": "string",
            "description": "Nullability status. Standard values: 'NULL', 'NOT NULL'.",
            "nullable": True,
        },
        "description": {
            "type": "string",
            "description": "Deprecated. Use long_description instead.",
            "nullable": True,
        },
        "ignored": {
            "type": "boolean",
            "description": "Whether to ignore this field in documentation and analysis.",
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
        field_name: Optional[str] = None,
        query: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
        data_type: Optional[str] = None,
        nullability: Optional[str] = None,
        description: Optional[str] = None,  # Backward compatibility
        fields_json: Optional[str] = None,
        ignored: Optional[bool] = None,
    ) -> dict[str, str]:
        if not action:
            raise ValueError("Action is required.")

        self._ensure_project_context()
        manager = self.query_tool.schema_manager

        normalized_action = action.strip().lower()

        # Handle backward compatibility for description -> long_description
        if description and not long_description:
            long_description = description

        # Batch update fields
        if normalized_action == "update_fields_batch":
            if not table_name or not fields_json:
                raise ValueError("table_name and fields_json are required for update_fields_batch.")

            try:
                fields_data = json.loads(fields_json)
                if not isinstance(fields_data, list):
                    raise ValueError("fields_json must be a JSON list of objects.")

                results = []
                for field_item in fields_data:
                    f_name = field_item.get("name") or field_item.get("field_name")
                    if not f_name:
                        continue

                    # Report progress if agent callback is available
                    if hasattr(self, "_agent_ref") and hasattr(self._agent_ref, "_on_step") and self._agent_ref._on_step:
                        self._agent_ref._on_step(f"Updating field {table_name}.{f_name}...")

                    # If data_type is not provided or is generic, try to infer from sample data
                    provided_type = field_item.get("data_type")
                    inferred_type = provided_type
                    
                    if provided_type and provided_type.upper() in ["VARCHAR", "TEXT", "STRING", "UNKNOWN"]:
                        try:
                            # Sample data to infer more accurate type
                            sample_sql = (
                                f'SELECT DISTINCT "{f_name}" FROM "{table_name}" '
                                f'WHERE "{f_name}" IS NOT NULL LIMIT 10'
                            )
                            sample_result = self.query_tool.execute_structured(sample_sql)
                            
                            if sample_result and hasattr(sample_result, 'rows') and sample_result.rows:
                                sample_values = [str(row[0]) for row in sample_result.rows if row]
                                
                                # Check for UUID pattern
                                uuid_pattern_count = 0
                                for val in sample_values:
                                    # UUID format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
                                    parts = val.split('-')
                                    if len(parts) == 5 and len(parts[0]) == 8 and len(parts[1]) == 4 and \
                                       len(parts[2]) == 4 and len(parts[3]) == 4 and len(parts[4]) == 12:
                                        try:
                                            # Check if all parts are hex
                                            all(int(part, 16) for part in parts)
                                            uuid_pattern_count += 1
                                        except ValueError:
                                            pass
                                
                                # If most values look like UUIDs, use UUID type
                                if uuid_pattern_count >= len(sample_values) * 0.8:
                                    inferred_type = "UUID"
                        except Exception as e:
                            # If sampling fails, use provided type or default
                            print(f"Warning: Could not sample data for {table_name}.{f_name}: {e}")
                            pass

                    manager.update_field(
                        table_name,
                        f_name,
                        short_description=field_item.get("short_description"),
                        long_description=field_item.get("long_description"),
                        data_type=inferred_type,
                        nullability=field_item.get("nullability")
                    )
                    results.append(f_name)

                return {"result": f"Updated metadata for {len(results)} fields in {table_name}: {', '.join(results)}"}
            except Exception as e:
                return {"result": f"Failed to batch update fields: {str(e)}"}

        # Infer nullability for all fields in a table
        if normalized_action == "infer_nullability":
            if not table_name:
                raise ValueError("table_name is required for infer_nullability action.")

            try:
                # 1. Get all fields
                columns = self.query_tool.fetch_table_schema(table_name)
                if not columns:
                    return {"result": f"Table {table_name} not found or has no columns."}

                # 2. Build query to count nulls for each column
                select_parts = []
                col_names = []
                for col in columns:
                    name = col.get('name')
                    if name:
                        col_names.append(name)
                        # Use SUM(CASE...) to count nulls
                        select_parts.append(f'SUM(CASE WHEN "{name}" IS NULL THEN 1 ELSE 0 END) as "{name}"')

                if not select_parts:
                    return {"result": "No columns found to check."}

                sql = f'SELECT {", ".join(select_parts)} FROM "{table_name}"'
                
                # 3. Execute query
                result = self.query_tool.execute_structured(sql)
                
                if not result or not result.rows:
                    return {"result": "Failed to execute nullability check query."}

                # 4. Process results and update metadata
                row = result.rows[0]
                updates = []
                
                for i, count in enumerate(row):
                    col_name = result.columns[i]

                    # Report progress
                    if hasattr(self, "_agent_ref") and hasattr(self._agent_ref, "_on_step") and self._agent_ref._on_step:
                        self._agent_ref._on_step(f"Updating nullability for {table_name}.{col_name}...")

                    has_nulls = count > 0
                    nullability = "NULL" if has_nulls else "NOT NULL"
                    
                    manager.update_field(
                        table_name,
                        col_name,
                        nullability=nullability
                    )
                    updates.append(f"{col_name}: {nullability} ({count} nulls)")

                return {"result": f"Inferred nullability for {len(updates)} fields in {table_name}:\n" + "\n".join(updates)}

            except Exception as e:
                return {"result": f"Failed to infer nullability: {str(e)}"}

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

            # 1. Get actual fields from DuckDB
            db_fields = {}
            try:
                columns = self.query_tool.fetch_table_schema(table_name)
                for col in columns:
                    name = col.get('name')
                    if name:
                        db_fields[str(name).lower()] = {
                            "name": name,
                            "type": col.get('type', col.get('column_type', 'unknown'))
                        }
            except Exception:
                # If table doesn't exist in DB, we might still have documentation for it
                pass

            # 2. Get documented fields
            table_record = manager.get_table(table_name)
            doc_fields = {}
            if table_record and table_record.get("fields"):
                doc_fields = {k.lower(): (k, v) for k, v in table_record["fields"].items()}

            # 3. Merge and format
            all_field_names = sorted(list(set(db_fields.keys()) | set(doc_fields.keys())))

            if not all_field_names:
                return {"result": f"No fields found for table {table_name}."}

            lines = []
            for lower_name in all_field_names:
                # Prefer documented name casing, fallback to DB name
                display_name = doc_fields.get(lower_name, (db_fields.get(lower_name, {}).get("name"), {}))[0]
                doc_data = doc_fields.get(lower_name, (None, {}))[1]

                # Skip ignored fields
                if doc_data.get("ignored"):
                    continue

                # Get data type from DB (truth) or docs (fallback)
                db_type = db_fields.get(lower_name, {}).get("type")
                doc_type = doc_data.get("data_type")

                final_type = db_type or doc_type or "unknown"

                line = f"- {display_name} ({final_type})"

                # Include both short and long descriptions for SQL context
                short_desc = doc_data.get("short_description")
                long_desc = doc_data.get("long_description")
                
                descriptions = []
                if short_desc:
                    descriptions.append(short_desc)
                if long_desc:
                    # Limit long description to reasonable length
                    if len(long_desc) > 200:
                        long_desc = long_desc[:197] + "..."
                    descriptions.append(long_desc)
                
                if descriptions:
                    line += ": " + " | ".join(descriptions)
                elif lower_name not in doc_fields:
                    line += " [Undocumented]"

                lines.append(line)

            return {"result": f"Fields in {table_name}:\n" + "\n".join(lines)}

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
                    if field_data.get("ignored"):
                        continue
                    data_type = field_data.get("data_type", "")
                    short_desc = field_data.get("short_description", "")
                    long_desc = field_data.get("long_description", "")
                    nullability = field_data.get("nullability", "")
                    field_line = f"  - {field_name}"
                    if data_type:
                        field_line += f" ({data_type})"
                    if nullability:
                        field_line += f" [{nullability}]"

                    descriptions = []
                    if short_desc:
                        descriptions.append(short_desc)
                    if long_desc:
                        descriptions.append(long_desc)

                    if descriptions:
                        field_line += ": " + " | ".join(descriptions)
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
                    if field_data.get("ignored"):
                        continue
                    data_type = field_data.get("data_type", "")
                    lines.append(f"    - {field_name} ({data_type})")

            return {"result": "\n".join(lines)}

        # Update field metadata
        if normalized_action == "update_field":
            if not table_name or not field_name:
                raise ValueError("table_name and field_name are required for update_field.")

            try:
                manager.update_field(
                    table_name,
                    field_name,
                    short_description=short_description,
                    long_description=long_description,
                    data_type=data_type,
                    nullability=nullability,
                    ignored=ignored
                )
                return {"result": f"Updated metadata for {table_name}.{field_name}."}
            except Exception as e:
                return {"result": f"Failed to update field: {str(e)}"}

        # Update table metadata
        if normalized_action == "update_table":
            if not table_name:
                raise ValueError("table_name is required for update_table.")

            try:
                manager.update_table(
                    table_name,
                    short_description=short_description,
                    long_description=long_description
                )
                return {"result": f"Updated metadata for table {table_name}."}
            except Exception as e:
                return {"result": f"Failed to update table: {str(e)}"}

        # Backward compatibility for update_field_description
        if normalized_action == "update_field_description":
            if not table_name or not field_name:
                raise ValueError("table_name and field_name are required.")
            # Use the mapped long_description (from description arg if present)
            try:
                manager.update_field(table_name, field_name, long_description=long_description)
                return {"result": f"Updated description for {table_name}.{field_name}."}
            except Exception as e:
                return {"result": f"Failed to update field: {str(e)}"}

        # Search fields across all tables
        if normalized_action == "search_fields":
            if not query:
                raise ValueError("query is required for search_fields action.")
            
            search_term = query.lower()
            matches = []
            
            # Get all tables
            try:
                tables = self.query_tool.list_tables_in_database()
            except Exception:
                tables = manager.list_tables()
            
            if not tables:
                return {"result": "No tables found to search."}
                
            for table in tables:
                # Report progress
                if hasattr(self, "_agent_ref") and hasattr(self._agent_ref, "_on_step") and self._agent_ref._on_step:
                    self._agent_ref._on_step(f"Searching in table {table}...")

                # Check table name match
                if search_term in table.lower():
                    matches.append(f"Table: {table} (Name match)")
                
                # Check fields
                try:
                    columns = self.query_tool.fetch_table_schema(table)
                    for col in columns:
                        col_name = col.get('name', '')
                        if search_term in str(col_name).lower():
                            col_type = col.get('type', col.get('column_type', 'unknown'))
                            matches.append(f"Field: {table}.{col_name} ({col_type})")
                except Exception:
                    pass
                    
                # Check documentation
                table_record = manager.get_table(table)
                if table_record:
                    # Check table description
                    t_desc = (table_record.get("short_description") or "") + " " + (table_record.get("long_description") or "")
                    if search_term in t_desc.lower():
                         matches.append(f"Table: {table} (Description match)")
                         
                    # Check field descriptions
                    fields = table_record.get("fields", {})
                    for f_name, f_data in fields.items():
                        if f_data.get("ignored"):
                            continue
                        f_desc = (f_data.get("short_description") or "") + " " + (f_data.get("long_description") or "")
                        if search_term in f_desc.lower():
                             matches.append(f"Field: {table}.{f_name} (Description match)")

            if not matches:
                return {"result": f"No matches found for '{query}'."}
            
            # Deduplicate and sort
            unique_matches = sorted(list(set(matches)))
            return {"result": f"Search results for '{query}':\n" + "\n".join(unique_matches)}

        raise ValueError(
            f"Unknown action '{action}'. Supported: list_tables, list_fields, "
            "get_table_info, list_saved_queries, get_full_schema, update_field, update_table, update_fields_batch."
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
