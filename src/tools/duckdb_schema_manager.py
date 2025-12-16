from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional, Set
from uuid import uuid4


class SchemaManager:
    """Handles persistence and summarisation of DuckDB schema metadata."""

    def __init__(self) -> None:
        self.project_path: Optional[Path] = None
        self.schema_path: Optional[Path] = None
        self.schema: dict[str, Any] = {}

    def set_database(self, db_path: Path) -> None:
        self.project_path = db_path.resolve()
        schema_filename = f"{self.project_path.stem}.schema.json"
        self.schema_path = self.project_path.parent / schema_filename
        if self.schema_path.exists():
            try:
                self.schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.schema = self._empty_schema()
        else:
            self.schema = self._empty_schema()
            self._save()

        # Ensure modern metadata fields exist
        project_id = self.project_path.stem if self.project_path else "unknown_project"
        display_name = self.schema.get("project_display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            self.schema["project_display_name"] = self.schema.get("project") or project_id
        if "project_description" not in self.schema or not isinstance(self.schema["project_description"], str):
            self.schema["project_description"] = ""
        if "project" not in self.schema or not isinstance(self.schema["project"], str):
            self.schema["project"] = project_id
        if "version" not in self.schema or not isinstance(self.schema["version"], str):
            self.schema["version"] = "1.0.0"
        if "query_instructions" not in self.schema or not isinstance(self.schema["query_instructions"], str):
            self.schema["query_instructions"] = ""
        if not isinstance(self.schema.get("diagrams"), list):
            self.schema["diagrams"] = []
        if not isinstance(self.schema.get("queries"), list):
            self.schema["queries"] = []
        self._save()

    def _empty_schema(self) -> dict[str, Any]:
        project = self.project_path.stem if self.project_path else "unknown_project"
        return {
            "project": project,
            "project_display_name": project,
            "project_description": "",
            "version": "1.0.0",
            "query_instructions": "",
            "tables": {},
            "diagrams": [],
            "queries": [],
        }

    def _save(self) -> None:
        if not self.schema_path:
            raise RuntimeError("Schema path is undefined; call set_database first.")
        self.schema_path.write_text(json.dumps(self.schema, indent=2, ensure_ascii=False), encoding="utf-8")

    # Public operations -------------------------------------------------
    def get_schema_json(self) -> str:
        if not self.schema:
            return "{}"
        return json.dumps(self.schema, indent=2, ensure_ascii=False)

    def list_tables(self) -> List[str]:
        tables = self.schema.get("tables", {})
        return sorted(tables.keys())

    def get_project_metadata(self) -> dict[str, str]:
        display_name = str(self.schema.get("project_display_name") or self.schema.get("project") or "")
        description = str(self.schema.get("project_description") or "")
        version = str(self.schema.get("version") or "1.0.0")
        query_instructions = str(self.schema.get("query_instructions") or "")
        return {
            "display_name": display_name,
            "description": description,
            "version": version,
            "query_instructions": query_instructions,
        }

    def set_project_metadata(
        self,
        *,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        version: Optional[str] = None,
        query_instructions: Optional[str] = None,
    ) -> dict[str, str]:
        changed = False
        if display_name is not None:
            cleaned = display_name.strip()
            if cleaned != self.schema.get("project_display_name"):
                self.schema["project_display_name"] = cleaned
                self.schema["project"] = cleaned
                changed = True
        if description is not None:
            if description != self.schema.get("project_description"):
                self.schema["project_description"] = description
                changed = True
        if version is not None:
            cleaned_ver = version.strip()
            if cleaned_ver != self.schema.get("version"):
                self.schema["version"] = cleaned_ver
                changed = True
        if query_instructions is not None:
            if query_instructions != self.schema.get("query_instructions"):
                self.schema["query_instructions"] = query_instructions
                changed = True

        if changed:
            self._save()

        return self.get_project_metadata()

    def list_fields(self, table: Optional[str] = None) -> dict[str, List[str]]:
        tables = self.schema.get("tables", {})
        if not tables:
            return {}

        target_tables: dict[str, dict] = {}
        if table:
            record = self._find_table_record(table, tables)
            if not record:
                return {}
            target_tables = {record["name"]: record["data"]}
        else:
            target_tables = {name: data for name, data in tables.items()}

        result: dict[str, List[str]] = {}
        for table_name, data in target_tables.items():
            fields = data.get("fields") or {}
            result[table_name] = sorted(fields.keys())
        return result

    def set_project_description(self, description: str) -> None:
        self.schema["project_description"] = description
        self._save()

    # Diagram persistence ------------------------------------------------
    def _ensure_diagram_section(self) -> list[dict[str, Any]]:
        diagrams = self.schema.get("diagrams")
        if not isinstance(diagrams, list):
            diagrams = []
        self.schema["diagrams"] = diagrams
        return diagrams

    def list_diagrams(self) -> list[dict[str, Any]]:
        diagrams = self.schema.get("diagrams")
        if isinstance(diagrams, list):
            return diagrams
        return []

    def save_diagram(
        self,
        *,
        name: str,
        description: str | None,
        tables: list[dict[str, Any]] | None,
        diagram_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_diagram_section()
        target_id = diagram_id or uuid4().hex
        cleaned_name = name.strip() or "Untitled diagram"
        cleaned_description = (description or "").strip()
        stored_tables: list[dict[str, float | str]] = []
        for entry in tables or []:
            if not isinstance(entry, dict):
                continue
            raw_name = str(entry.get("name") or "").strip()
            if not raw_name:
                continue
            try:
                x = float(entry.get("x", 0))
                y = float(entry.get("y", 0))
                width = entry.get("width")
                if width is not None:
                    width = float(width)
            except (TypeError, ValueError):
                continue
            
            table_data = {"name": raw_name, "x": x, "y": y}
            if width is not None:
                table_data["width"] = width
            stored_tables.append(table_data)

        diagram_record = {
            "id": target_id,
            "name": cleaned_name,
            "description": cleaned_description,
            "tables": stored_tables,
        }
        diagrams = self.schema["diagrams"]
        assert isinstance(diagrams, list)
        if diagram_id:
            replaced = False
            for index, existing in enumerate(diagrams):
                if existing.get("id") == diagram_id:
                    diagrams[index] = diagram_record
                    replaced = True
                    break
            if not replaced:
                diagrams.append(diagram_record)
        else:
            diagrams.append(diagram_record)
        self._save()
        return diagram_record

    def delete_diagram(self, diagram_id: str) -> bool:
        diagrams = self.schema.get("diagrams")
        if not isinstance(diagrams, list):
            return False
        initial_count = len(diagrams)
        self.schema["diagrams"] = [diagram for diagram in diagrams if diagram.get("id") != diagram_id]
        if len(self.schema["diagrams"]) != initial_count:
            self._save()
            return True
        return False

    def get_diagram(self, diagram_id: str) -> dict[str, Any] | None:
        diagrams = self.schema.get("diagrams")
        if not isinstance(diagrams, list):
            return None
        for diagram in diagrams:
            if diagram.get("id") == diagram_id:
                return diagram
        return None

    # Query persistence -------------------------------------------------
    def _ensure_query_section(self) -> list[dict[str, Any]]:
        queries = self.schema.get("queries")
        if not isinstance(queries, list):
            queries = []
        self.schema["queries"] = queries
        return queries

    def list_queries(self) -> list[dict[str, Any]]:
        queries = self.schema.get("queries")
        if isinstance(queries, list):
            return queries
        return []

    def save_query(
        self,
        *,
        name: str,
        description: str | None,
        sql: str,
        limit: int | None = None,
        query_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_query_section()
        cleaned_sql = (sql or "").strip()
        if not cleaned_sql:
            raise ValueError("SQL text cannot be empty.")
        target_id = query_id or uuid4().hex
        cleaned_name = name.strip() or "Untitled query"
        cleaned_description = (description or "").strip()
        limit_value: int | None = None
        if isinstance(limit, (int, float)):
            try:
                normalized = int(limit)
            except (TypeError, ValueError):
                normalized = None
            if normalized and normalized > 0:
                limit_value = normalized

        record: dict[str, Any] = {
            "id": target_id,
            "name": cleaned_name,
            "description": cleaned_description,
            "sql": cleaned_sql,
            "limit": limit_value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        queries = self.schema["queries"]
        assert isinstance(queries, list)
        if query_id:
            replaced = False
            for index, existing in enumerate(queries):
                if existing.get("id") == query_id:
                    queries[index] = record
                    replaced = True
                    break
            if not replaced:
                queries.append(record)
        else:
            queries.append(record)
        self._save()
        return record

    def delete_query(self, query_id: str) -> bool:
        queries = self.schema.get("queries")
        if not isinstance(queries, list):
            return False
        initial_count = len(queries)
        self.schema["queries"] = [query for query in queries if query.get("id") != query_id]
        if len(self.schema["queries"]) != initial_count:
            self._save()
            return True
        return False

    def get_query(self, query_id: str) -> dict[str, Any] | None:
        queries = self.schema.get("queries")
        if not isinstance(queries, list):
            return None
        for query in queries:
            if query.get("id") == query_id:
                return query
        return None

    def update_table(
        self,
        table: str,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
    ) -> dict[str, Any]:
        record = self._ensure_table(table)
        if short_description is not None:
            record["short_description"] = short_description
        if long_description is not None:
            record["long_description"] = long_description
        self._save()
        return record

    def delete_table(self, table: str) -> bool:
        tables = self.schema.get("tables", {})
        if table not in tables:
            return False
        del tables[table]
        self._save()
        return True

    def update_field(
        self,
        table: str,
        field: str,
        *,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
        nullability: Optional[str] = None,
        data_type: Optional[str] = None,
        values: Optional[dict[str, str]] = None,
        ignored: Optional[bool] = None,
    ) -> dict[str, Any]:
        table_record = self._ensure_table(table)
        fields = table_record.setdefault("fields", {})
        field_record = fields.setdefault(
            field,
            {
                "short_description": "",
                "long_description": "",
                "nullability": "",
                "data_type": "",
                "values": {},
                "ignored": False,
            },
        )
        if short_description is not None:
            field_record["short_description"] = short_description
        if long_description is not None:
            field_record["long_description"] = long_description
        if nullability is not None:
            field_record["nullability"] = nullability
        if data_type is not None:
            field_record["data_type"] = data_type
        if values is not None:
            field_record["values"] = values
        if ignored is not None:
            field_record["ignored"] = ignored
        self._save()
        return field_record

    def delete_field(self, table: str, field: str) -> bool:
        table_record = self.get_table(table)
        if not table_record:
            return False

        fields = table_record.get("fields", {})

        # Resolve actual key respecting case
        actual_field = None
        for key in fields.keys():
            if key == field or key.lower() == field.lower():
                actual_field = key
                break

        if actual_field is None:
            return False

        # Remove the field
        del fields[actual_field]

        # Remove relationships defined on this table using this field
        relationships = table_record.get("relationships") or []
        table_record["relationships"] = [
            rel for rel in relationships
            if rel.get("field") != actual_field
        ]

        # Remove relationships in other tables referencing this field
        for table_name, other_table in (self.schema.get("tables") or {}).items():
            rels = other_table.get("relationships") or []
            other_table["relationships"] = [
                rel for rel in rels
                if not (
                    rel.get("related_table") == table
                    and rel.get("related_field") == actual_field
                )
            ]

        self._save()
        return True

    def rename_field(self, table: str, old_name: str, new_name: str) -> dict[str, Any]:
        if not new_name or new_name == old_name:
            return self.get_field(table, old_name) or {}

        table_record = self._ensure_table(table)
        fields = table_record.setdefault("fields", {})
        if old_name not in fields and old_name.lower() not in (name.lower() for name in fields):
            raise ValueError(f"Field '{old_name}' not found in table '{table}'.")

        # Resolve actual key respecting case
        actual_old = None
        for key in fields.keys():
            if key == old_name or key.lower() == old_name.lower():
                actual_old = key
                break

        if actual_old is None:
            raise ValueError(f"Field '{old_name}' not found in table '{table}'.")

        metadata = fields.pop(actual_old)
        fields[new_name] = metadata

        # Update relationships defined on this table
        relationships = table_record.get("relationships") or []
        for rel in relationships:
            if rel.get("field") == actual_old:
                rel["field"] = new_name

        # Update relationships in other tables referencing this field
        for table_name, other_table in (self.schema.get("tables") or {}).items():
            rels = other_table.get("relationships") or []
            for rel in rels:
                if (
                    rel.get("related_table") == table
                    and rel.get("related_field") == actual_old
                ):
                    rel["related_field"] = new_name

        self._save()
        return metadata

    def add_relationship(
        self,
        table: str,
        field: str,
        related_table: str,
        related_field: str,
        relationship_type: Optional[str] = None,
    ) -> dict[str, Any]:
        table_record = self._ensure_table(table)
        relationships = table_record.setdefault("relationships", [])
        rel = {
            "field": field,
            "related_table": related_table,
            "related_field": related_field,
            "type": relationship_type or "unspecified",
        }
        relationships.append(rel)
        self._save()
        return rel

    def set_relationships(self, table: str, relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
        record = self._ensure_table(table)
        normalised: list[dict[str, Any]] = []
        for rel in relationships:
            field = (rel.get("field") or rel.get("column") or "").strip()
            related_table = (rel.get("related_table") or rel.get("table") or "").strip()
            rel_field = (rel.get("related_field") or rel.get("column_name") or "").strip()
            rel_type = rel.get("relationship_type") or rel.get("type") or ""
            if not field or not related_table or not rel_field:
                continue
            normalised.append(
                {
                    "field": field,
                    "related_table": related_table,
                    "related_field": rel_field,
                    "type": rel_type or "unspecified",
                }
            )
        record["relationships"] = normalised
        self._save()
        return normalised

    def describe_tables(self, table_names: Iterable[str]) -> str:
        tables = self.schema.get("tables", {})
        matched: list[str] = []
        for name in table_names:
            record = self._find_table_record(name, tables)
            if not record:
                continue
            line = f"Table '{record['name']}'"
            short_desc = record["data"].get("short_description")
            long_desc = record["data"].get("long_description")
            details: list[str] = []
            if short_desc:
                details.append(short_desc)
            if long_desc:
                details.append(long_desc)
            if details:
                line += ": " + " | ".join(details)
            fields = record["data"].get("fields") or {}
            if fields:
                field_lines = []
                for field_name, field_info in fields.items():
                    summary_bits = []
                    if field_info.get("short_description"):
                        summary_bits.append(field_info["short_description"])
                    if field_info.get("data_type"):
                        summary_bits.append(f"Type: {field_info['data_type']}")
                    if field_info.get("nullability"):
                        summary_bits.append(f"Nullability: {field_info['nullability']}")
                    if field_info.get("values"):
                        values_text = ", ".join(f"{k}={v}" for k, v in field_info["values"].items())
                        summary_bits.append(f"Values: {values_text}")
                    summary = "; ".join(summary_bits) if summary_bits else ""
                    field_lines.append(f"  - {field_name}: {summary}".rstrip(": "))
                if field_lines:
                    line += "\n" + "\n".join(field_lines)
            matched.append(line)
        if matched:
            return "Schema details:\n" + "\n".join(matched)

        if tables:
            available = ", ".join(sorted(tables.keys()))
            return f"No schema details found for tables {', '.join(table_names)}. Available tables: {available}."

        return "No schema metadata recorded yet."

    def project_summary(self) -> str:
        description = self.schema.get("project_description")
        tables = self.schema.get("tables", {})
        if not tables and not description:
            return "No schema metadata recorded yet."
        lines = []
        if description:
            lines.append(f"Project description: {description}")
        if tables:
            lines.append("Documented tables: " + ", ".join(sorted(tables.keys())))
        return "\n".join(lines)

    # Internal helpers --------------------------------------------------
    def _ensure_table(self, table: str) -> dict[str, Any]:
        if "tables" not in self.schema:
            self.schema["tables"] = {}
        tables = self.schema["tables"]
        record = tables.get(table)
        if not record:
            record = {"short_description": "", "long_description": "", "fields": {}, "relationships": []}
            tables[table] = record
        return record

    def _find_table_record(self, table: str, tables: dict) -> Optional[dict]:
        if table in tables:
            return {"name": table, "data": tables[table]}
        lowered = table.lower()
        for key, value in tables.items():
            if key.lower() == lowered:
                return {"name": key, "data": value}
        return None

    def get_table(self, table: str) -> Optional[dict]:
        tables = self.schema.get("tables", {})
        record = self._find_table_record(table, tables)
        if record:
            return record["data"]
        return None

    def get_field(self, table: str, field: str) -> Optional[dict]:
        table_record = self.get_table(table)
        if not table_record:
            return None
        fields = table_record.get("fields", {})
        if field in fields:
            return fields[field]
        lowered = field.lower()
        for key, value in fields.items():
            if key.lower() == lowered:
                return value
        return None

    def fields_needing_input(self, table: Optional[str] = None) -> list[dict[str, Any]]:
        tables = self.schema.get("tables", {})
        items: list[tuple[str, dict]] = []
        if table:
            record = self._find_table_record(table, tables)
            if record:
                items.append((record["name"], record["data"]))
        else:
            items.extend(tables.items())

        pending: list[dict[str, Any]] = []
        for table_name, record in items:
            fields = record.get("fields", {})
            for field_name, metadata in fields.items():
                missing: list[str] = []
                if not metadata.get("short_description"):
                    missing.append("short_description")
                if not metadata.get("long_description"):
                    missing.append("long_description")
                if not metadata.get("data_type"):
                    missing.append("data_type")
                if not metadata.get("nullability"):
                    missing.append("nullability")
                if missing:
                    pending.append({"table": table_name, "field": field_name, "missing": missing})
        return pending

    def format_pending_fields(self, table: Optional[str] = None) -> str:
        pending = self.fields_needing_input(table)
        if not pending:
            return "All documented fields have descriptions and metadata."
        lines = ["Fields needing attention:"]
        for item in pending:
            missing_list = ", ".join(item["missing"])
            lines.append(f"- {item['table']}.{item['field']}: missing {missing_list}")
        return "\n".join(lines)

    def format_table_summary(self, table: str) -> str:
        tables = self.schema.get("tables", {})
        record = self._find_table_record(table, tables)
        if not record:
            return f"No documentation found for table '{table}'."
        data = record["data"]
        lines = [f"Table '{record['name']}'"]
        if data.get("short_description"):
            lines.append(f"Short: {data['short_description']}")
        if data.get("long_description"):
            lines.append(f"Long: {data['long_description']}")
        fields = data.get("fields", {})
        if fields:
            lines.append("Fields:")
            for field_name, metadata in fields.items():
                parts = []
                if metadata.get("short_description"):
                    parts.append(metadata["short_description"])
                if metadata.get("data_type"):
                    parts.append(f"Type: {metadata['data_type']}")
                if metadata.get("nullability"):
                    parts.append(f"Nullability: {metadata['nullability']}")
                if metadata.get("values"):
                    values_text = ", ".join(f"{k}={v}" for k, v in metadata["values"].items())
                    parts.append(f"Values: {values_text}")
                if metadata.get("long_description"):
                    parts.append(f"Details: {metadata['long_description']}")
                summary = "; ".join(parts) if parts else "No details recorded."
                lines.append(f"  - {field_name}: {summary}")
        relationships = data.get("relationships") or []
        if relationships:
            lines.append("Relationships:")
            for rel in relationships:
                rel_desc = (
                    f"{record['name']}.{rel.get('field')} -> "
                    f"{rel.get('related_table')}.{rel.get('related_field')} "
                )
                if rel.get("type"):
                    rel_desc += f"({rel['type']}) "
                lines.append(f"  - {rel_desc.strip()}")
        return "\n".join(lines)

    def collect_related_tables(self, base_tables: Iterable[str]) -> Set[str]:
        tables = self.schema.get("tables", {})
        resolved: Set[str] = set()
        queue: List[str] = []
        for table in base_tables:
            record = self._find_table_record(table, tables)
            if record:
                name = record["name"]
                resolved.add(name)
                queue.append(name)

        while queue:
            current = queue.pop(0)
            record = self._find_table_record(current, tables)
            if not record:
                continue
            relationships = record["data"].get("relationships") or []
            for rel in relationships:
                related_table = rel.get("related_table")
                if not related_table:
                    continue
                related_record = self._find_table_record(related_table, tables)
                if not related_record:
                    continue
                name = related_record["name"]
                if name not in resolved:
                    resolved.add(name)
                    queue.append(name)
        return resolved

    def format_mermaid(self, tables_subset: Optional[Iterable[str]] = None) -> str:
        tables = self.schema.get("tables", {})
        selected_tables = set()
        if tables_subset:
            for table in tables_subset:
                record = self._find_table_record(table, tables)
                if record:
                    selected_tables.add(record["name"])
        else:
            selected_tables = set(tables.keys())

        if not selected_tables:
            return "%% No tables documented; Mermaid ER diagram cannot be generated."

        lines = ["erDiagram"]
        for table_name in sorted(selected_tables):
            record = tables.get(table_name)
            if not record:
                continue
            lines.append(f"  {table_name} {{")
            fields = record.get("fields", {})
            for field_name, metadata in fields.items():
                data_type = metadata.get("data_type") or "UNKNOWN"
                short_desc = metadata.get("short_description") or ""
                lines.append(f"    {data_type} {field_name} \"{short_desc}\"")
            lines.append("  }")

        for table_name in sorted(selected_tables):
            record = tables.get(table_name)
            if not record:
                continue
            relationships = record.get("relationships") or []
            for rel in relationships:
                related_table = rel.get("related_table")
                if not related_table or related_table not in selected_tables:
                    continue
                related_record = tables.get(related_table)
                if not related_record:
                    continue
                left = table_name
                right = related_table
                arrow = self._relationship_to_mermaid(rel)
                lines.append(f"  {left} {arrow} {right}")

        return "\n".join(lines)

    @staticmethod
    def _relationship_to_mermaid(rel: dict) -> str:
        rel_type = (rel.get("type") or "").lower()
        if "many" in rel_type and "one" in rel_type:
            if rel_type.startswith("many"):
                return "}o--||"
            return "||--o{"
        if "many" in rel_type:
            return "}o--o{"
        if "one" in rel_type:
            return "||--||"
        return "}o--o{"
