"""
DuckDB Chart Tool - Executes queries and returns data formatted for chart visualization.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .duckdb_query_tool import DuckDBQueryTool


class DuckDBChartTool:
    """Tool for executing queries and formatting results for charts."""

    def __init__(self, db_path: Optional[str] = None, default_database: Optional[str] = None):
        """Initialize the chart tool with database path."""
        db = Path(default_database) if default_database else None
        self.query_tool = DuckDBQueryTool(default_database=db)
        self.current_database: Optional[str] = None

    def __call__(
        self,
        sql: str,
        chart_type: str = "bar",
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        plan: str = ""
    ) -> str:
        """
        Execute a SQL query and return formatted chart data.

        Args:
            sql: The SQL query to execute
            chart_type: Type of chart (bar, line, pie, scatter, area)
            title: Chart title
            x_label: X-axis label
            y_label: Y-axis label
            plan: Implementation reasoning for the query

        Returns:
            JSON string with chart configuration and data
        """
        # Set the current database on the query tool if we have one
        if self.current_database:
            db_path = Path(self.current_database)
            self.query_tool.current_database = db_path

        # Execute the query using the query tool's structured method for clean JSON output
        try:
            result_obj = self.query_tool.execute_structured(
                sql=sql,
                result_limit=None  # No limit for charts
            )

            # Check if there was an error message
            if result_obj.message and "error" in result_obj.message.lower():
                return json.dumps({
                    "error": result_obj.message,
                    "chartType": chart_type,
                    "sql": sql,
                    "plan": plan
                })

            # Format data for charting
            chart_data = self._format_chart_data(
                columns=result_obj.columns,
                rows=result_obj.rows,
                chart_type=chart_type,
                title=title,
                x_label=x_label,
                y_label=y_label
            )

            # Add metadata
            chart_data["sql"] = sql
            chart_data["plan"] = plan
            chart_data["row_count"] = result_obj.row_count
            chart_data["truncated"] = result_obj.truncated
            chart_data["database"] = result_obj.database
            chart_data["project"] = result_obj.project

            # Return as JSON
            return json.dumps(chart_data, default=str)

        except ValueError as e:
            return json.dumps({
                "error": f"Query execution failed: {str(e)}",
                "chartType": chart_type,
                "sql": sql,
                "plan": plan
            })
        except Exception as e:
            import traceback
            return json.dumps({
                "error": f"Failed to generate chart: {str(e)}",
                "chartType": chart_type,
                "sql": sql,
                "plan": plan,
                "traceback": traceback.format_exc()
            }, default=str)

    def _format_chart_data(
        self,
        columns: List[str],
        rows: List[List[Any]],
        chart_type: str,
        title: str,
        x_label: str,
        y_label: str
    ) -> Dict[str, Any]:
        """
        Format query results into chart-ready data structure.

        For most charts, we expect:
        - First column: labels (x-axis or categories)
        - Remaining columns: values (y-axis or series)

        Special handling:
        - If we have exactly 3 columns and first 2 appear to be groupings (year/month, category/subcategory),
          combine them into a single label
        """
        if not rows or not columns:
            return {
                "chartType": str(chart_type),
                "title": str(title or "Chart"),
                "xLabel": str(x_label),
                "yLabel": str(y_label),
                "labels": [],
                "datasets": [],
                "message": "No data to display"
            }

        # Helper function to safely convert values to primitive types
        def to_primitive(val: Any) -> Any:
            """Convert any value to a JSON-serializable primitive."""
            if val is None:
                return None
            if isinstance(val, (str, int, float, bool)):
                return val
            # Convert everything else to string
            return str(val)

        # Special case: 3 columns where first two are grouping dimensions
        # (e.g., year, month, count or category, subcategory, value)
        if len(columns) == 3:
            # Check if the last column appears to be numeric (the measure)
            last_col_numeric = True
            for row in rows[:5]:  # Check first few rows
                val = row[2]
                if val is not None:
                    try:
                        float(val)
                    except (ValueError, TypeError):
                        last_col_numeric = False
                        break

            if last_col_numeric:
                # Combine first two columns as labels - convert to strings
                labels = []
                for row in rows:
                    v0 = to_primitive(row[0])
                    v1 = to_primitive(row[1])
                    if v0 is not None and v1 is not None:
                        labels.append(f"{v0}-{v1}")
                    else:
                        labels.append("")

                # Third column is the data - convert to float
                data_values = []
                for row in rows:
                    val = row[2]
                    try:
                        num_val = float(val) if val is not None else 0.0
                        data_values.append(num_val)
                    except (ValueError, TypeError):
                        data_values.append(0.0)

                datasets = [{
                    "label": str(columns[2]),
                    "data": data_values
                }]

                return {
                    "chartType": str(chart_type),
                    "title": str(title or f"{columns[2]} by {columns[0]} and {columns[1]}"),
                    "xLabel": str(x_label or f"{columns[0]}-{columns[1]}"),
                    "yLabel": str(y_label or columns[2]),
                    "labels": labels,
                    "datasets": datasets
                }

        # Standard case: First column as labels, remaining columns as datasets
        labels = [str(to_primitive(row[0])) if row[0] is not None else "" for row in rows]

        # Extract datasets from remaining columns
        datasets = []
        for col_idx in range(1, len(columns)):
            data_values = []
            for row in rows:
                val = row[col_idx]
                try:
                    num_val = float(val) if val is not None else 0.0
                    data_values.append(num_val)
                except (ValueError, TypeError):
                    data_values.append(0.0)

            dataset = {
                "label": str(columns[col_idx]),
                "data": data_values
            }
            datasets.append(dataset)

        # If only one column, treat it as values with row numbers as labels
        if len(columns) == 1:
            labels = [str(i + 1) for i in range(len(rows))]
            data_values = []
            for row in rows:
                val = row[0]
                try:
                    num_val = float(val) if val is not None else 0.0
                    data_values.append(num_val)
                except (ValueError, TypeError):
                    data_values.append(0.0)

            datasets = [{
                "label": str(columns[0]),
                "data": data_values
            }]

        return {
            "chartType": str(chart_type),
            "title": str(title or f"{columns[1] if len(columns) > 1 else columns[0]} by {columns[0]}"),
            "xLabel": str(x_label or columns[0]),
            "yLabel": str(y_label or (columns[1] if len(columns) > 1 else "Value")),
            "labels": labels,
            "datasets": datasets
        }
