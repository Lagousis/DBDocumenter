from __future__ import annotations

import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from smolagents import Tool

__all__ = ["DuckDBDiagramTool"]


class DuckDBDiagramTool(Tool):
    """Tool for generating ER diagrams from documented DuckDB schema using matplotlib."""

    name = "duckdb_diagram"
    output_type = "string"
    description = (
        "Creates ER diagrams for documented DuckDB projects using matplotlib. "
        "Can export rendered images and optionally include an ASCII summary."
    )
    inputs = {
        "tables": {
            "type": "string",
            "description": "Optional comma-separated list of tables to include. Leave empty for all tables.",
            "nullable": True,
        },
        "include_related": {
            "type": "boolean",
            "description": "When true, automatically include tables related to the selected tables.",
            "nullable": True,
        },
        "output_mermaid": {
            "type": "boolean",
            "description": "When true, include an ASCII text summary of the tables and relationships in the response.",
            "nullable": True,
        },
        "image_path": {
            "type": "string",
            "description": "Path to write the rendered diagram image (rendered with matplotlib). Supports .png/.svg. Mandatory unless requesting a text-only summary.",
            "nullable": True,
        },
        "project": {
            "type": "string",
            "description": "Optional project to switch to before generating the diagram.",
            "nullable": True,
        },
    }
    outputs = {
        "result": {
            "type": "string",
            "description": "ASCII summary (when requested) and log messages about exported files.",
        }
    }

    def __init__(self, query_tool: DuckDBQueryTool) -> None:
        super().__init__()
        self.query_tool = query_tool

    def forward(
        self,
        tables: Optional[str] = None,
        include_related: Optional[bool] = False,
        output_mermaid: Optional[bool] = None,
        image_path: Optional[str] = None,
        project: Optional[str] = None,
    ) -> dict[str, str]:
        self._ensure_project_context(project)
        manager = self.query_tool.schema_manager

        selected_tables: list[str] = []
        if tables:
            selected_tables = [table.strip() for table in tables.split(",") if table.strip()]

        if include_related:
            seeds = selected_tables or list(manager.schema.get("tables", {}).keys())
            expanded = manager.collect_related_tables(seeds)
            selected_tables = sorted(expanded)

        messages = []
        suggested_image_name: Optional[str] = None
        tables_dict = manager.schema.get("tables", {})

        def resolve_table(name: str) -> Optional[tuple[str, dict]]:
            if not tables_dict:
                return None
            if name in tables_dict:
                return name, tables_dict[name]
            lowered = name.lower()
            for table_name, table_data in tables_dict.items():
                if table_name.lower() == lowered:
                    return table_name, table_data
            return None

        table_records: list[tuple[str, dict]] = []
        included_names: set[str] = set()
        if selected_tables:
            for candidate in selected_tables:
                resolved = resolve_table(candidate)
                if resolved:
                    if resolved[0] in included_names:
                        continue
                    table_records.append(resolved)
                    included_names.add(resolved[0])
                else:
                    messages.append(f"Skipping '{candidate}' (no documentation found).")
        else:
            for table_name in sorted(tables_dict.keys()):
                table_records.append((table_name, tables_dict[table_name]))
                included_names.add(table_name)

        if not table_records:
            raise ValueError("No documented tables available to generate an ER diagram.")

        if image_path is None:
            suggestion_base = "diagram"
            if len(table_records) == 1:
                suggestion_base = f"{table_records[0][0]}"
            elif selected_tables:
                suggestion_base = "_".join(selected_tables[:2])
            suggestion_base = re.sub(r"[^A-Za-z0-9_-]+", "_", suggestion_base).strip("_") or "diagram"
            suggested_image_name = f"{suggestion_base}.png"
            messages.append(
                f"No image path supplied. Suggested filename: '{suggested_image_name}'. "
                "Please provide this or another preferred filename to save the ER diagram."
            )

        relationships: list[dict[str, Optional[str]]] = []
        for table_name, table_data in table_records:
            for rel in table_data.get("relationships") or []:
                related_table = rel.get("related_table")
                if not related_table:
                    continue
                resolved = resolve_table(str(related_table))
                if not resolved:
                    continue
                target_name, _ = resolved
                if target_name not in included_names:
                    continue
                relationships.append(
                    {
                        "source": table_name,
                        "target": target_name,
                        "field": rel.get("field"),
                        "related_field": rel.get("related_field"),
                        "type": rel.get("type"),
                        "description": rel.get("description"),
                    }
                )

        seen_relationships: set[tuple[str, str, str, str]] = set()
        unique_relationships: list[dict[str, Optional[str]]] = []
        for rel in relationships:
            key = (
                str(rel.get("source") or "").lower(),
                str(rel.get("target") or "").lower(),
                str(rel.get("field") or "").lower(),
                str(rel.get("related_field") or "").lower(),
            )
            if key in seen_relationships:
                continue
            seen_relationships.add(key)
            unique_relationships.append(rel)

        mermaid_text = ""
        if output_mermaid:
            mermaid_text = manager.format_mermaid(table for table, _ in table_records)

        export_message = ""
        if image_path:
            export_path = Path(image_path).expanduser().resolve()
            export_path.parent.mkdir(parents=True, exist_ok=True)
            if export_path.suffix.lower() not in {".png", ".svg"}:
                raise ValueError("image_path must end with .png or .svg for diagram export.")
            self._render_er_diagram(table_records, unique_relationships, export_path)
            export_message = f"Diagram exported to {export_path}"
            try:
                self._open_file(export_path)
                export_message += " (opened automatically)."
            except RuntimeError as exc:
                export_message += f". {exc}"

        summary_blocks: list[str] = []
        summary_blocks.append(self._generate_table_summary(table_records))
        if unique_relationships:
            summary_blocks.append(self._generate_relationship_summary(unique_relationships))
        if mermaid_text:
            summary_blocks.append("Mermaid ERD:\n" + mermaid_text)
        if export_message:
            summary_blocks.append(export_message)
        if suggested_image_name and not image_path:
            summary_blocks.append(f"Suggested image filename: {suggested_image_name}")

        messages.append("\n\n".join(summary_blocks).strip())
        return {"result": "\n\n".join(msg for msg in messages if msg).strip()}

    # Helper methods --------------------------------------------------
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
                raise RuntimeError("No DuckDB databases available for diagram generation.")
            if len(available) > 1:
                raise RuntimeError(
                    "Multiple DuckDB projects detected. Please specify the target project name for diagrams."
                )
            self.query_tool.current_database = available[0]
            self.query_tool.schema_manager.set_database(available[0])

    @staticmethod
    def _generate_table_summary(table_records: list[tuple[str, dict]]) -> str:
        lines = []
        for table_name, table_data in table_records:
            short_desc = table_data.get("short_description") or ""
            long_desc = table_data.get("long_description") or ""
            pieces = [table_name]
            if short_desc:
                pieces.append(short_desc)
            if long_desc:
                pieces.append(long_desc)
            header = " | ".join(pieces)
            lines.append(header)

            fields = table_data.get("fields") or {}
            if not fields:
                lines.append("  (no documented fields)")
                continue
            for field_name, metadata in fields.items():
                details = []
                if metadata.get("data_type"):
                    details.append(metadata["data_type"])
                if metadata.get("nullability"):
                    details.append(metadata["nullability"])
                if metadata.get("short_description"):
                    details.append(metadata["short_description"])
                if metadata.get("long_description"):
                    details.append(metadata["long_description"])
                if metadata.get("values"):
                    values_text = ", ".join(f"{k}={v}" for k, v in metadata["values"].items())
                    details.append(f"Values: {values_text}")
                summary = " | ".join(details) if details else "(no additional metadata)"
                lines.append(f"  - {field_name}: {summary}")

        return "Tables:\n" + "\n".join(lines)

    @staticmethod
    def _generate_relationship_summary(relationships: list[dict[str, Optional[str]]]) -> str:
        relation_set: set[str] = set()
        relations: list[str] = []
        for rel in relationships:
            source = rel.get("source")
            target = rel.get("target")
            if not source or not target:
                continue

            descriptor_parts = []
            if rel.get("field") and rel.get("related_field"):
                descriptor_parts.append(f"{rel['field']} -> {rel['related_field']}")
            elif rel.get("field"):
                descriptor_parts.append(str(rel["field"]))

            descriptor = ", ".join(descriptor_parts)
            detail = rel.get("description") or ""
            relation_line = f"{source} -> {target}"
            if rel.get("type"):
                relation_line += f" ({rel['type']})"
            if descriptor:
                relation_line += f" ({descriptor})"
            if detail:
                relation_line += f" - {detail}"
            if relation_line not in relation_set:
                relation_set.add(relation_line)
                relations.append(relation_line)

        if relations:
            return "Relationships:\n" + "\n".join(relations)
        return "Relationships:\n(none documented)"

    def _render_er_diagram(
        self,
        table_records: list[tuple[str, dict]],
        relationships: list[dict[str, Optional[str]]],
        export_path: Path,
    ) -> None:
        try:
            import matplotlib.pyplot as plt
            from matplotlib.patches import FancyBboxPatch
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Diagram export requires matplotlib. Install it with `pip install matplotlib` and retry."
            ) from exc

        if not table_records:
            raise RuntimeError("No tables available to render.")

        tables_payload: list[dict[str, object]] = []
        for name, data in table_records:
            fields_meta = data.get("fields", {}) if isinstance(data, dict) else {}
            field_lines: list[str] = []
            for field_name, metadata in fields_meta.items():
                if not isinstance(metadata, dict):
                    field_lines.append(str(field_name))
                    continue
                dtype = str(metadata.get("data_type") or "").strip()
                nullability = str(metadata.get("nullability") or "").strip()
                pieces = [field_name]
                if dtype:
                    pieces.append(dtype)
                if nullability:
                    pieces.append(nullability)
                field_lines.append(" | ".join(pieces))
            if not field_lines:
                field_lines.append("(no documented fields)")
            tables_payload.append({"name": name, "fields": field_lines})

        num_tables = len(tables_payload)
        positions: dict[str, tuple[float, float]] = {}
        if num_tables == 1:
            positions[tables_payload[0]["name"]] = (0.0, 0.0)
            radius = 2.0
        else:
            radius = max(4.0, num_tables * 1.5)
            for idx, table in enumerate(tables_payload):
                angle = (2 * math.pi * idx) / num_tables
                positions[table["name"]] = (radius * math.cos(angle), radius * math.sin(angle))

        renderables: list[dict[str, object]] = []
        max_extent = 0.0
        for table in tables_payload:
            name = str(table["name"])
            lines = [name] + list(table["fields"])
            max_chars = max(len(line) for line in lines)
            width = max(4.0, 0.18 * max_chars)
            height = max(1.6, 0.6 + 0.35 * (len(table["fields"]) or 1))
            x, y = positions.get(name, (0.0, 0.0))
            renderables.append(
                {
                    "name": name,
                    "fields": list(table["fields"]),
                    "position": (x, y),
                    "width": width,
                    "height": height,
                }
            )
            max_extent = max(
                max_extent,
                abs(x) + width / 2 + 0.5,
                abs(y) + height / 2 + 0.5,
            )

        limit = max(max_extent, radius + 1.5)
        fig_width = max(8.0, num_tables * 3.0)
        fig_height = max(6.0, num_tables * 2.2)
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-limit, limit)
        ax.set_aspect("equal")
        ax.axis("off")

        for item in renderables:
            name = item["name"]
            fields = item["fields"]
            x, y = item["position"]
            width = item["width"]
            height = item["height"]

            rect = FancyBboxPatch(
                (x - width / 2, y - height / 2),
                width,
                height,
                boxstyle="round,pad=0.3",
                linewidth=1.6,
                edgecolor="#2563eb",
                facecolor="#f8fafc",
            )
            ax.add_patch(rect)

            header_y = y + height / 2 - 0.35
            ax.text(
                x,
                header_y,
                name,
                fontsize=12,
                fontweight="bold",
                ha="center",
                va="top",
                color="#1f2937",
            )
            ax.plot(
                [x - width / 2 + 0.2, x + width / 2 - 0.2],
                [header_y - 0.25, header_y - 0.25],
                color="#93c5fd",
                linewidth=1.0,
            )

            for idx, field in enumerate(fields):
                y_pos = header_y - 0.6 - idx * 0.35
                ax.text(
                    x - width / 2 + 0.3,
                    y_pos,
                    field,
                    fontsize=10,
                    ha="left",
                    va="top",
                    family="monospace",
                    color="#1f2937",
                )

        for rel in relationships:
            source = rel.get("source")
            target = rel.get("target")
            if not source or not target:
                continue
            if source not in positions or target not in positions:
                continue
            if source == target:
                continue
            start = positions[source]
            end = positions[target]
            arrowprops = dict(arrowstyle="-|>", color="#475569", linewidth=1.4, shrinkA=18, shrinkB=18)
            ax.annotate("", xy=end, xytext=start, arrowprops=arrowprops)

            label_parts: list[str] = []
            if rel.get("field") and rel.get("related_field"):
                label_parts.append(f"{rel['field']} \u2192 {rel['related_field']}")
            elif rel.get("field"):
                label_parts.append(str(rel["field"]))
            if rel.get("type"):
                label_parts.append(str(rel["type"]))
            if rel.get("description"):
                label_parts.append(str(rel["description"]))
            if label_parts:
                label = "\n".join(label_parts)
                mid_x = (start[0] + end[0]) / 2
                mid_y = (start[1] + end[1]) / 2
                ax.text(
                    mid_x,
                    mid_y,
                    label,
                    fontsize=9,
                    ha="center",
                    va="center",
                    color="#1f2937",
                    bbox=dict(boxstyle="round,pad=0.3", fc="#ffffff", ec="#cbd5f5", alpha=0.9),
                )

        fig.tight_layout()
        fig.savefig(export_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

    @staticmethod
    def _open_file(path: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=True)
            else:
                subprocess.run(["xdg-open", str(path)], check=True)
        except Exception as exc:  # pragma: no cover - depends on host platform
            raise RuntimeError(f"Diagram saved to {path}, but automatic opening failed: {exc}") from exc

