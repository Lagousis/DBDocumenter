from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional

from dotenv import load_dotenv
from openai import APIConnectionError, AzureOpenAI, RateLimitError

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

try:
    if __package__:
        from .tools.duckdb_chart_tool import DuckDBChartTool
        from .tools.duckdb_query_tool import DEFAULT_DATABASES_ROOT, DuckDBQueryTool
        from .tools.duckdb_schema_tool import DuckDBSchemaTool
    else:  # pragma: no cover - script entry compatibility
        from tools.duckdb_chart_tool import DuckDBChartTool
        from tools.duckdb_query_tool import DEFAULT_DATABASES_ROOT, DuckDBQueryTool
        from tools.duckdb_schema_tool import DuckDBSchemaTool
except ImportError:  # pragma: no cover - fallback when executed directly
    # Allow execution via `python agent.py` from the src directory
    sys.path.append(str(Path(__file__).resolve().parent))
    from tools.duckdb_chart_tool import DuckDBChartTool
    from tools.duckdb_query_tool import DEFAULT_DATABASES_ROOT, DuckDBQueryTool
    from tools.duckdb_schema_tool import DuckDBSchemaTool

DEFAULT_AZURE_ENDPOINT = "https://slagousis-eastus-resource.cognitiveservices.azure.com/"
BOOL_TRUE = {"1", "true", "yes", "on"}

__all__ = [
    "DuckDBChartTool",
    "DuckDBQueryTool",
    "DuckDBSchemaTool",
    "DuckDBWorkspaceConfig",
    "DuckDBComponents",
    "resolve_duckdb_workspace",
    "create_duckdb_components",
    "create_duckdb_agent",
    "run_agent",
    "main",
]


class DirectOpenAIAgent:
    """Agent using Azure OpenAI function calling for DuckDB queries."""

    def __init__(
        self,
        *,
        client: AzureOpenAI,
        model: str,
        query_tool: DuckDBQueryTool,
        schema_tool: DuckDBSchemaTool,
        chart_tool: DuckDBChartTool,
        system_prompt: str,
        max_iterations: int = 10,
        max_history_messages: int = 20,
    ) -> None:
        self.client = client
        self.model = model
        self.query_tool = query_tool
        self.schema_tool = schema_tool
        self.chart_tool = chart_tool
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.max_history_messages = max_history_messages
        self._last_sql_query: Optional[str] = None
        self._last_implementation_plan: Optional[str] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.execution_metadata: Dict[str, Any] = {}
        self._cancelled: bool = False

        # Link tools back to agent for SQL/plan capture
        self.query_tool._agent_ref = self  # type: ignore[attr-defined]
        self.schema_tool._agent_ref = self  # type: ignore[attr-defined]
        self.chart_tool._agent_ref = self  # type: ignore[attr-defined]

        # Define function schemas
        self.functions: List[Dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "duckdb_query",
                    "description": "Execute a SQL query against the DuckDB database and return results",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "The SQL query to execute"
                            },
                            "output_format": {
                                "type": "string",
                                "enum": ["text", "table", "csv"],
                                "description": (
                                    "Preferred output formatting for results. "
                                    "Use 'table' for tabular output."
                                ),
                            },
                            "plan": {
                                "type": "string",
                                "description": (
                                    "Implementation plan explaining table selection, columns, "
                                    "joins, filters, and reasoning"
                                )
                            }
                        },
                        "required": ["sql"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "duckdb_schema",
                    "description": (
                        "Get or update schema information about tables, fields, relationships, and saved queries. "
                        "Use this to understand database structure OR to document the database."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": [
                                    "list_tables",
                                    "list_fields",
                                    "get_table_info",
                                    "list_saved_queries",
                                    "get_full_schema",
                                    "update_field",
                                    "update_table",
                                    "update_fields_batch",
                                    "infer_nullability"
                                ],
                                "description": (
                                    "list_tables: show all tables, "
                                    "list_fields: show fields for a table, "
                                    "get_table_info: detailed info with relationships, "
                                    "list_saved_queries: show saved SQL queries, "
                                    "get_full_schema: complete schema summary, "
                                    "update_field: update field metadata (desc, type, nullability), "
                                    "update_table: update table metadata (desc), "
                                    "update_fields_batch: update multiple fields (requires fields_json), "
                                    "infer_nullability: check all fields in a table for null values"
                                )
                            },
                            "table_name": {
                                "type": "string",
                                "description": "Table name (required for most actions)"
                            },
                            "field_name": {
                                "type": "string",
                                "description": "Field name (required for update_field)"
                            },
                            "fields_json": {
                                "type": "string",
                                "description": (
                                    "JSON string list of fields for update_fields_batch. "
                                    "Can include 'nullability' (use 'NULL'/'NOT NULL')."
                                ),
                            },
                            "short_description": {
                                "type": "string",
                                "description": "Short summary for table/field (for update actions)"
                            },
                            "long_description": {
                                "type": "string",
                                "description": "Detailed description for table/field (for update actions)"
                            },
                            "data_type": {
                                "type": "string",
                                "description": "Data type for field (for update_field)"
                            },
                            "nullability": {
                                "type": "string",
                                "description": (
                                    "Nullability status. Standard values: 'NULL', 'NOT NULL'. "
                                    "Do not use 'nullable' or 'not nullable'."
                                ),
                            }
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "duckdb_chart",
                    "description": (
                        "Execute a SQL query and return data formatted for chart visualization. "
                        "Use this when the user explicitly requests a chart (bar, line, pie, scatter, area) "
                        "or asks to visualize data graphically."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "The SQL query to execute for chart data"
                            },
                            "chart_type": {
                                "type": "string",
                                "enum": ["bar", "horizontal-bar", "line", "pie", "scatter", "area"],
                                "description": "Type of chart to create"
                            },
                            "title": {
                                "type": "string",
                                "description": "Chart title (optional, will be auto-generated if not provided)"
                            },
                            "x_label": {
                                "type": "string",
                                "description": "X-axis label (optional, defaults to first column name)"
                            },
                            "y_label": {
                                "type": "string",
                                "description": "Y-axis label (optional, defaults to value column name)"
                            },
                            "plan": {
                                "type": "string",
                                "description": (
                                    "Implementation plan explaining table selection, columns, "
                                    "aggregations, and reasoning"
                                )
                            }
                        },
                        "required": ["sql", "chart_type"]
                    }
                }
            }
        ]

    def _trim_conversation_history(self) -> None:
        """
        Trim conversation history to prevent token limit issues.
        Keeps system message + most recent messages up to max_history_messages.
        """
        if len(self.conversation_history) <= self.max_history_messages + 1:
            # +1 for system message
            return

        # Separate system message from conversation
        system_messages = [msg for msg in self.conversation_history if msg.get("role") == "system"]
        other_messages = [msg for msg in self.conversation_history if msg.get("role") != "system"]

        # Keep only the most recent messages
        if len(other_messages) > self.max_history_messages:
            other_messages = other_messages[-self.max_history_messages:]

        # Reconstruct history: system + recent messages
        self.conversation_history = system_messages + other_messages

    def cancel(self) -> None:
        """Cancel the current agent execution."""
        self._cancelled = True
        print("DEBUG: Cancellation requested")

    def run(
        self,
        prompt: str,
        *,
        reset: bool = False,
        images: Optional[List[Dict[str, str]]] = None,
        on_step: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> str:
        """Execute the agent with function calling loop."""
        start_time = time.time()
        tools_used = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        api_calls = 0

        if on_step:
            on_step("Thinking...")

        # Store callback for tools to use
        self._on_step = on_step

        if reset:
            self.conversation_history = []
            self._last_sql_query = None
            self._last_implementation_plan = None

        # Clear last SQL and plan before running
        self._last_sql_query = None
        self._last_implementation_plan = None

        # Add system message if conversation is empty
        if not self.conversation_history:
            self.conversation_history.append({
                "role": "system",
                "content": self.system_prompt
            })

        # Add user message - support multimodal if images are provided
        if images:
            # Construct multimodal message with text and images
            content_parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
            for img in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": img["data"]  # data should be base64 data URL like "data:image/jpeg;base64,..."
                    }
                })
            self.conversation_history.append({
                "role": "user",
                "content": content_parts
            })
        else:
            # Text-only message
            self.conversation_history.append({
                "role": "user",
                "content": prompt
            })

        # Function calling loop
        for iteration in range(self.max_iterations):
            # Check for cancellation
            if self._cancelled:
                print("DEBUG: Agent execution cancelled by user")
                self._cancelled = False  # Reset for next run
                return "Operation cancelled by user."
            
            api_calls += 1

            print(f"DEBUG: Agent iteration {iteration + 1}/{self.max_iterations}")
            
            # Notify about iteration progress
            if on_step and iteration > 0:
                on_step(f"Processing step {iteration + 1}...")

            # Trim conversation history to prevent token limit issues
            self._trim_conversation_history()

            try:
                # Cast types for Pylance
                messages_param: Iterable[ChatCompletionMessageParam] = self.conversation_history  # type: ignore
                tools_param: Iterable[ChatCompletionToolParam] = self.functions  # type: ignore

                print("DEBUG: Making API call to Azure OpenAI...")
                api_start_time = time.time()

                # Implement retry logic for RateLimitError
                max_retries = 3
                retry_count = 0
                response = None

                while True:
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages_param,
                            tools=tools_param,
                            tool_choice="auto"
                        )
                        break
                    except RateLimitError as e:
                        retry_count += 1
                        if retry_count > max_retries:
                            raise

                        # Default wait time
                        wait_time = 20 * retry_count

                        # Try to extract wait time from error message
                        import re
                        match = re.search(r"retry after (\d+) seconds", str(e), re.IGNORECASE)
                        if match:
                            wait_time = int(match.group(1)) + 5  # Add 5s buffer

                        print(
                            f"DEBUG: Rate limit reached. Retrying in {wait_time} seconds... "
                            f"(Attempt {retry_count}/{max_retries})"
                        )
                        time.sleep(wait_time)

                api_elapsed = time.time() - api_start_time
                print(f"DEBUG: API call completed in {api_elapsed:.2f}s")
            except APIConnectionError as e:
                # Enhance the error message with the endpoint
                raise RuntimeError(
                    f"Connection failed to Azure OpenAI endpoint: {self.client.base_url}. "
                    "Please check your internet connection and the AZURE_OPENAI_ENDPOINT setting."
                ) from e
            except RateLimitError as e:
                raise RuntimeError(
                    "Rate limit exceeded. Please wait before making more requests."
                ) from e

            # Capture token usage
            if hasattr(response, 'usage') and response.usage:
                total_prompt_tokens += response.usage.prompt_tokens or 0
                total_completion_tokens += response.usage.completion_tokens or 0

            message = response.choices[0].message

            # Normalize tool_calls to list of dicts for history consistency
            tool_calls_data = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    if isinstance(tc, dict):
                        tool_calls_data.append(tc)
                    else:
                        # Convert Pydantic model/object to dict
                        tool_calls_data.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        })

            # Add assistant message to history
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": tool_calls_data if tool_calls_data else None
            })

            # If no tool calls, we're done
            if not message.tool_calls:
                result = message.content or ""
                break

            # Execute tool calls
            for tool_call in message.tool_calls:
                if isinstance(tool_call, dict):
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])
                    tool_id = tool_call["id"]
                else:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    tool_id = tool_call.id

                print(f"DEBUG: Executing tool '{function_name}' with args: {function_args}")

                if on_step:
                    step_msg = f"Executing {function_name}..."
                    if function_name == "duckdb_schema":
                        action = function_args.get("action")
                        if action == "update_fields_batch":
                            step_msg = f"Updating multiple fields in {function_args.get('table_name')}..."
                        elif action == "infer_nullability":
                            step_msg = f"Checking nullability for {function_args.get('table_name')}..."
                        elif action == "update_field":
                            step_msg = (
                                f"Updating field {function_args.get('table_name')}."
                                f"{function_args.get('field_name')}..."
                            )
                    elif function_name == "duckdb_query":
                        step_msg = "Running SQL query..."

                    on_step(step_msg)

                tool_start_time = time.time()

                # Track tool usage
                tools_used.append({
                    "name": function_name,
                    "arguments": function_args,
                    "id": tool_id
                })

                # Execute the appropriate tool with error handling
                try:
                    if function_name == "duckdb_query":
                        self._last_sql_query = function_args.get("sql")
                        self._last_implementation_plan = function_args.get("plan")
                        tool_result = self.query_tool(
                            sql=function_args["sql"],
                            plan=function_args.get("plan"),
                            output_format=function_args.get("output_format", "table"),
                        )
                    elif function_name == "duckdb_schema":
                        tool_result = self.schema_tool(
                            action=function_args["action"],
                            table_name=function_args.get("table_name"),
                            field_name=function_args.get("field_name"),
                            short_description=function_args.get("short_description"),
                            long_description=function_args.get("long_description"),
                            data_type=function_args.get("data_type"),
                            nullability=function_args.get("nullability"),
                            fields_json=function_args.get("fields_json")
                        )
                    elif function_name == "duckdb_chart":
                        tool_result = self.chart_tool(
                            sql=function_args["sql"],
                            chart_type=function_args.get("chart_type", "bar"),
                            title=function_args.get("title", ""),
                            x_label=function_args.get("x_label", ""),
                            y_label=function_args.get("y_label", ""),
                            plan=function_args.get("plan", "")
                        )
                    else:
                        tool_result = f"Unknown function: {function_name}"
                except Exception as e:
                    # Capture tool execution errors and return them as tool results
                    tool_result = f"Error executing {function_name}: {str(e)}"
                    print(f"Tool execution error: {tool_result}")

                tool_elapsed = time.time() - tool_start_time
                print(f"DEBUG: Tool '{function_name}' completed in {tool_elapsed:.2f}s")

                if on_step:
                    on_step(f"Finished {function_name} ({tool_elapsed:.2f}s)")

                # Truncate very long tool results to prevent token overflow
                tool_result_str = str(tool_result)
                max_tool_result_length = 50000  # Increased to allow larger tables
                if len(tool_result_str) > max_tool_result_length:
                    tool_result_str = (
                        tool_result_str[:max_tool_result_length] +
                        f"\n... [truncated {len(tool_result_str) - max_tool_result_length} characters]"
                    )

                # Add tool response to history
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": tool_result_str
                })
        else:
            # Max iterations reached
            result = "Maximum iterations reached without completion."

        # Calculate execution time
        execution_time = time.time() - start_time

        # Store execution metadata
        self.execution_metadata = {
            "tools_used": tools_used,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "api_calls": api_calls,
            "execution_time_seconds": round(execution_time, 2),
            "iterations": iteration + 1 if iteration < self.max_iterations else self.max_iterations,
            "model": self.model
        }

        # Post-process: Check if chart tool was used and inject chart block
        chart_tool_used = False
        chart_json = None
        for tool_usage in tools_used:
            if tool_usage["name"] == "duckdb_chart":
                chart_tool_used = True
                # Find the corresponding tool result in conversation history
                for msg in reversed(self.conversation_history):
                    if msg.get("role") == "tool" and msg.get("content"):
                        try:
                            # Try to parse as JSON to verify it's chart data
                            content = msg["content"]
                            parsed = json.loads(content)
                            if "chart_type" in parsed or "labels" in parsed:
                                chart_json = content
                                break
                        except (json.JSONDecodeError, KeyError):
                            continue
                break

        if isinstance(result, str) and chart_tool_used and chart_json:
            # Check if agent already included chart block
            has_chart_block = "```chart" in result.lower()

            # If no chart block, inject it
            if not has_chart_block:
                result = f"```chart\n{chart_json}\n```\n\n{result}"
            else:
                # If chart block exists, ensure it contains the SQL field
                # If the agent stripped it, we should try to inject the full JSON
                # This is a simple heuristic: if the tool result has 'sql' but the output block doesn't
                if '"sql":' in chart_json and '"sql":' not in result:
                    # Replace the first chart block with the full tool output
                    import re
                    pattern = re.compile(r"```chart\n[\s\S]*?```", re.IGNORECASE)
                    result = pattern.sub(f"```chart\n{chart_json}\n```", result, count=1)

        # Post-process: if duckdb_query was used, ensure results include a Markdown table.
        # This prevents the model from summarizing results into a single line.
        def _extract_tabular_lines(tool_text: str) -> list[str]:
            lines = [line.rstrip("\r") for line in (tool_text or "").split("\n")]
            # Skip the leading database header lines.
            start_idx = 0
            for i, line in enumerate(lines):
                if "|" in line:
                    start_idx = i
                    break
            table_lines: list[str] = []
            for line in lines[start_idx:]:
                if not line.strip():
                    # Stop at first blank line after we started capturing.
                    if table_lines:
                        break
                    continue

                if "|" in line or line.strip().replace("-", "").replace("+", "").strip() == "":
                    table_lines.append(line)
                    continue

                # Stop when we hit schema metadata / narrative.
                if table_lines:
                    break
            return table_lines

        def _pipe_table_to_markdown(table_lines: list[str]) -> str:
            if not table_lines:
                return ""

            # Remove obvious ASCII borders (e.g., +----+----+)
            cleaned = [ln for ln in table_lines if not ln.strip().startswith("+")]
            if not cleaned:
                return ""

            # Find header as first line with pipes.
            header_line = next((ln for ln in cleaned if "|" in ln), "")
            if not header_line:
                return ""

            def split_row(line: str) -> list[str]:
                # Split by pipe, but handle the outer pipes correctly
                # A line like "| a | b |" split by "|" gives ['', ' a ', ' b ', '']
                parts = line.strip().split("|")
                # Remove the first and last empty strings resulting from outer pipes
                if len(parts) >= 2 and parts[0] == "" and parts[-1] == "":
                    parts = parts[1:-1]

                return [p.strip() for p in parts]

            headers = split_row(header_line)
            if not headers:
                return ""

            rows: list[list[str]] = []
            for ln in cleaned[cleaned.index(header_line) + 1:]:
                # Skip separator-ish lines
                stripped = ln.strip()
                if not stripped:
                    continue
                if "-+-" in stripped:
                    continue
                if all(ch in "-:|+ " for ch in stripped):
                    continue
                if "|" not in ln:
                    continue
                row = split_row(ln)
                if row and len(row) == len(headers):
                    rows.append(row)

            # If only header present, still render a table
            sep = "| " + " | ".join(["---"] * len(headers)) + " |"
            md = ["| " + " | ".join(headers) + " |", sep]
            for row in rows:
                md.append("| " + " | ".join(row) + " |")
            return "\n".join(md)

        if isinstance(result, str):
            used_query = any(t.get("name") == "duckdb_query" for t in tools_used)

            def _has_markdown_table(text: str) -> bool:
                """Return True only for a real Markdown table (header + separator row)."""
                import re

                # Require two consecutive lines: a pipe header and a separator line with at least one dash.
                pattern = re.compile(
                    r"(?m)^\s*\|.*\|\s*$\r?\n^\s*\|(?=[\s\-:|]*-)[\s\-:|]+\|\s*$"
                )
                return bool(pattern.search(text or ""))

            if used_query:
                # Find the best query result from CURRENT run (prefer largest table)
                best_query_text = ""
                max_rows = -1

                # Get IDs of duckdb_query calls in this run
                current_query_ids = {
                    t["id"] for t in tools_used
                    if t["name"] == "duckdb_query" and "id" in t
                }

                print(f"DEBUG POST-PROCESS: Found {len(current_query_ids)} duckdb_query IDs in this run")

                # Iterate tool outputs to find the most significant duckdb_query result from THIS run
                for msg in self.conversation_history:
                    if msg.get("role") == "tool" and msg.get("tool_call_id"):
                        tid = msg["tool_call_id"]
                        if tid in current_query_ids:
                            content = msg["content"]
                            print(f"DEBUG POST-PROCESS: Found tool output for query ID {tid}")
                            print(f"DEBUG POST-PROCESS: Content length: {len(content)}")
                            print(f"DEBUG POST-PROCESS: First 500 chars of content:\n{content[:500]}")
                            # Extract lines to count data rows
                            lines = _extract_tabular_lines(content)
                            print(f"DEBUG POST-PROCESS: Extracted {len(lines)} table lines")
                            # Count lines that look like data (contain | and aren't separators)
                            row_count = 0
                            for line in lines:
                                stripped = line.strip()
                                if "|" in line and not all(c in "-|+ " for c in stripped):
                                    row_count += 1

                            print(f"DEBUG POST-PROCESS: Counted {row_count} rows in tool output")

                            # Prefer result with more rows; if equal, prefer later one
                            if row_count >= max_rows:
                                max_rows = row_count
                                best_query_text = content

                print(f"DEBUG POST-PROCESS: Best query has {max_rows} rows")

                # Check if the agent already included the full table
                # Now that frontend parsing is fixed, we only append if the agent didn't include it
                if best_query_text and max_rows > 0:
                    table_lines = _extract_tabular_lines(best_query_text)
                    md_table = _pipe_table_to_markdown(table_lines)
                    print(f"DEBUG POST-PROCESS: Generated markdown table with {md_table.count(chr(10))+1} lines")

                    if md_table:
                        # Check if the agent already included this table (normalize for comparison)
                        # Remove commas and extra whitespace to handle formatting differences
                        normalized_table = md_table.replace(',', '').replace(' ', '')
                        normalized_result = result.replace(',', '').replace(' ', '')

                        if normalized_table in normalized_result:
                            print("DEBUG POST-PROCESS: Agent already included the full table, skipping append")
                        else:
                            print("DEBUG POST-PROCESS: Agent did NOT include full table, appending")
                            result = f"{result}\n\n{md_table}"
                            print(f"DEBUG POST-PROCESS: Final result length: {len(result)}")
                else:
                    print(
                        "DEBUG POST-PROCESS: No table to append "
                        f"(best_query_text={bool(best_query_text)}, max_rows={max_rows})"
                    )

        # Post-process: inject SQL and plan markers if captured
        if self._last_sql_query and isinstance(result, str):
            has_sql = "```sql" in result.lower()
            has_plan = "[PLAN:" in result

            # If agent didn't include SQL, prepend it
            if not has_sql:
                result = f"```sql\n{self._last_sql_query}\n```\n\n{result}"

            # Add plan marker BEFORE the SQL block if we have one
            if self._last_implementation_plan and not has_plan:
                plan_marker = f"[PLAN:{self._last_implementation_plan}]"
                sql_block_start = result.lower().find("```sql")
                if sql_block_start >= 0:
                    result = result[:sql_block_start] + plan_marker + "\n" + result[sql_block_start:]
                else:
                    result = f"{plan_marker}\n{result}"

        # Clear callback
        self._on_step = None
        return result


@dataclass(frozen=True, slots=True)
class DuckDBWorkspaceConfig:
    """Resolved DuckDB workspace configuration shared by the CLI and the web server."""

    search_roots: list[Path]
    default_database: Optional[Path]
    duckdb_executable: Optional[Path]


@dataclass(slots=True)
class DuckDBComponents:
    """Concrete DuckDB tooling wired together for interactive usage."""

    query_tool: DuckDBQueryTool
    schema_tool: DuckDBSchemaTool
    chart_tool: DuckDBChartTool


def resolve_duckdb_workspace(
    *,
    search_roots: Iterable[str | Path] | None = None,
    default_database: Optional[str | Path] = None,
    duckdb_executable: Optional[str | Path] = None,
) -> DuckDBWorkspaceConfig:
    """
    Resolve DuckDB workspace configuration from explicit arguments or environment variables.

    This helper centralises configuration so both the CLI agent and the FastAPI server reuse the same logic.
    """

    load_dotenv()

    if search_roots is None:
        env_roots = os.environ.get("DUCKDB_SEARCH_ROOTS")
        if env_roots:
            roots_iterable = [Path(path.strip()) for path in env_roots.split(os.pathsep) if path.strip()]
        else:
            roots_iterable = [DEFAULT_DATABASES_ROOT]
    else:
        roots_iterable = [Path(path) for path in search_roots]

    resolved_roots = [root.expanduser().resolve() for root in roots_iterable]

    resolved_default: Optional[Path]
    if default_database is None:
        default_env = os.environ.get("DUCKDB_PATH")
        resolved_default = Path(default_env).expanduser().resolve() if default_env else None
    else:
        resolved_default = Path(default_database).expanduser().resolve()

    resolved_executable: Optional[Path]
    if duckdb_executable is None:
        env_executable = os.environ.get("DUCKDB_EXECUTABLE")
        resolved_executable = Path(env_executable).expanduser().resolve() if env_executable else None
    else:
        resolved_executable = Path(duckdb_executable).expanduser().resolve()

    return DuckDBWorkspaceConfig(
        search_roots=resolved_roots,
        default_database=resolved_default if resolved_default and resolved_default.exists() else resolved_default,
        duckdb_executable=(
            resolved_executable if resolved_executable and resolved_executable.exists() else resolved_executable
        ),
    )


def create_duckdb_components(
    config: DuckDBWorkspaceConfig,
    *,
    emit_status: bool = True,
) -> DuckDBComponents:
    """
    Instantiate DuckDB tools using the provided workspace configuration.

    Parameters
    ----------
    config:
        Resolved workspace paths for DuckDB assets.
    emit_status:
        When true, prints console messages describing discovered projects (useful for the CLI).
    """

    tool = DuckDBQueryTool(
        search_roots=config.search_roots,
        default_database=config.default_database,
    )
    available_projects = tool.discover_databases()

    if emit_status and tool.search_roots:
        primary_root = tool.search_roots[0]
        print(f"DuckDB databases directory: {primary_root}")
        if len(tool.search_roots) > 1:
            additional_roots = ", ".join(str(root) for root in tool.search_roots[1:])
            print(f"Additional search roots: {additional_roots}")
        print("Available DuckDB projects:")
        if available_projects:
            for path in available_projects:
                print(f"- {path.stem}")
        else:
            print("- <none>")

    schema_tool = DuckDBSchemaTool(tool)
    chart_tool = DuckDBChartTool(
        db_path=str(config.default_database) if config.default_database else None,
        default_database=str(config.default_database) if config.default_database else None
    )

    return DuckDBComponents(
        query_tool=tool,
        schema_tool=schema_tool,
        chart_tool=chart_tool,
    )


def create_duckdb_agent(
    *,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    azure_endpoint: Optional[str] = None,
    api_version: Optional[str] = None,
    search_roots: Iterable[str | Path] | None = None,
    default_database: Optional[str | Path] = None,
    duckdb_executable: Optional[str | Path] = None,
    max_steps: int = 10,
    timeout: float = 120.0,
    max_retries: int = 5,
    emit_status: bool = True,
) -> DirectOpenAIAgent:
    """
    Build a DirectOpenAIAgent equipped with DuckDB tools.

    Parameters
    ----------
    model_name:
        Azure OpenAI deployment name. If ``None`` the value from ``AZURE_OPENAI_DEPLOYMENT`` is used, falling back
        to ``"gpt-5"``.
    api_key:
        Azure OpenAI API key. If omitted, resolved from ``AZURE_OPENAI_API_KEY``.
    azure_endpoint:
        Azure OpenAI endpoint URL. If omitted, resolved from ``AZURE_OPENAI_ENDPOINT`` or the default resource URL.
    api_version:
        Azure OpenAI API version to use. Resolved from ``AZURE_OPENAI_API_VERSION`` when not provided.
    search_roots:
        Iterable of filesystem paths searched recursively for ``*.duckdb`` files. Defaults to the repo's ``databases``
        directory or paths listed in ``DUCKDB_SEARCH_ROOTS`` (os.pathsep separated).
    default_database:
        Preferred DuckDB file to use when more than one is present. Defaults to ``DUCKDB_PATH`` if available.
    duckdb_executable:
        Path to the DuckDB CLI executable. Defaults to ``DUCKDB_EXECUTABLE`` if available.
    max_steps:
        Maximum number of function calling iterations permitted for the agent.
    timeout:
        Timeout for Azure OpenAI API calls in seconds.
    max_retries:
        Maximum number of retries for Azure OpenAI API calls.
    emit_status:
        When true, prints DuckDB workspace information during initialization (defaults to True for CLI usage).
    """

    config = resolve_duckdb_workspace(
        search_roots=search_roots,
        default_database=default_database,
        duckdb_executable=duckdb_executable,
    )

    model_name = model_name or os.environ.get("AZURE_OPENAI_DEPLOYMENT") or "gpt-5"
    azure_endpoint = azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT") or DEFAULT_AZURE_ENDPOINT
    api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Azure OpenAI API key is required. Set AZURE_OPENAI_API_KEY in your environment variables."
        )
    api_version = api_version or os.environ.get("AZURE_OPENAI_API_VERSION")
    if not api_version:
        raise RuntimeError(
            "Azure OpenAI API version is required. Set AZURE_OPENAI_API_VERSION in your environment variables."
        )

    components = create_duckdb_components(config, emit_status=emit_status)
    tool = components.query_tool
    schema_tool = components.schema_tool
    chart_tool = components.chart_tool

    # Create Azure OpenAI client
    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=azure_endpoint,
        timeout=timeout,
        max_retries=max_retries
    )

    if os.environ.get("AZURE_OPENAI_SKIP_CHECK", "").strip().lower() not in BOOL_TRUE:
        _validate_azure_openai_connection(client, azure_endpoint)

    system_prompt = (
        "You are the DBDocumenter assistant for working with DuckDB databases. "
        "Focus your responses on the DuckDB schemas, tables, and data available in this project. "
        "If a user asks about unrelated topics, redirect them to questions about the documented datasets. "
        "\n\n"
        "Guideline: Check schema before writing SQL\n"
        "Before executing SQL queries, please follow these steps:\n"
        "1. Use duckdb_schema tool with action='list_tables' to see available tables\n"
        "2. If you need column information, use duckdb_schema with action='list_fields' and table_name parameter\n"
        "3. If you know a column name but not the table, use duckdb_schema "
        "with action='search_fields' and query='column_name'\n"
        "4. Write the SQL query using the EXACT table and column names from the schema\n"
        "5. Verify table and column names using the schema tool\n"
        "6. Avoid asking the user for table names if you can find them yourself using search_fields.\n"
        "\n"
        "This prevents errors like querying non-existent tables. "
        "The schema tool is fast and should be used liberally.\n"
        "\n\n"
        "CHART VISUALIZATION:\n"
        "When a user requests a CHART, GRAPH, or VISUALIZATION (e.g., 'show bar chart', 'create a line graph'):\n"
        "1. Use the duckdb_chart tool instead of duckdb_query\n"
        "2. Specify the chart_type: 'bar', 'line', 'pie', 'scatter', or 'area'\n"
        "3. Write SQL that returns data suitable for charting:\n"
        "   - First column: labels/categories (x-axis)\n"
        "   - Remaining columns: numeric values (y-axis/series)\n"
        "4. The tool will return chart data as JSON\n"
        "5. In your response, include the COMPLETE chart JSON (do not remove the 'sql' field) "
        "in a ```chart code block\n"
        "6. Explain what the chart shows after the chart block\n"
        "\n"
        "Example: User asks 'orders per year and month in bar chart'\n"
        "Use: duckdb_chart(sql='SELECT YEAR(date), MONTH(date), COUNT(*) FROM orders GROUP BY 1,2', "
        "chart_type='bar', title='Orders by Month')\n"
        "Then in your response:\n"
        "```chart\n"
        "{...chart JSON from tool...}\n"
        "```\n"
        "This chart shows the distribution of orders across years and months.\n"
        "\n\n"
        "FORMATTING GUIDELINE:\n"
        "When executing a SQL query using duckdb_query for DATA queries, please:\n"
        "1. Briefly explain your reasoning (1-2 sentences)\n"
        "2. Call the tool with the 'plan' parameter containing a detailed implementation plan that includes:\n"
        "   - Which table(s) you selected and why\n"
        "   - What columns or aggregations you're using\n"
        "   - Any JOINs, filters (WHERE), or groupings and the reasoning behind them\n"
        "   - Why you chose this approach (e.g., performance, data accuracy)\n"
        "3. Include the SQL query in a ```sql code block in your response\n"
        "4. Show the results below the SQL block formatted as a Markdown table. "
        "You MUST use the standard Markdown table format with a header row, "
        "a separator row (e.g. |---|---|), and outer pipes (e.g. | col1 | col2 |).\n"
        "   - ALWAYS include a header row with column names.\n"
        "   - ALWAYS include the separator row.\n"
        "   - Even if there is only one row of results, format it as a table.\n"
        "This is required for all data queries. Metadata queries don't need detailed plans.\n"
        "\n\n"
        "WORKFLOW FOR DATA QUERIES:\n"
        "When a user asks about data (not just metadata), follow these steps:\n"
        "1. FIRST: Use duckdb_schema to check what tables exist and their columns\n"
        "2. THEN: Use the duckdb_query tool to execute a SQL query against the database\n"
        "   - Use output_format='table' in the tool call to get pre-formatted tables.\n"
        "3. Add a LIMIT clause (default LIMIT 20) ONLY for queries that return multiple rows\n"
        "   (e.g., SELECT * FROM table)\n"

        "\n"
        "COHORT QUERIES (IMPORTANT):\n"
        "If the user asks for a cohort based on a customer's FIRST-EVER order month, you MUST compute "
        "the first order date over ALL orders first (do NOT apply the month filter before computing first order).\n"
        "Correct pattern:\n"
        "- CTE first_order AS (SELECT customer_id, MIN(order_date) AS first_order_date "
        "FROM orders GROUP BY customer_id)\n"
        "- CTE nov_customers AS (SELECT DISTINCT customer_id FROM orders "
        "WHERE order_date in Nov-2025 AND other filters)\n"
        "- Final: JOIN nov_customers -> first_order; cohort = strftime(first_order_date, '%Y-%m'); "
        "GROUP BY cohort; ORDER BY cohort\n"
        "   - DO NOT add LIMIT for aggregation queries (COUNT, SUM, AVG, MAX, MIN, GROUP BY, etc.)\n"
        "   - Aggregations already return a small result set\n"
        "4. In your response, FIRST show the SQL in a ```sql code block\n"
        "5. THEN show the results\n"
        "6. For multi-row results, format as a markdown table using pipe separators (|)\n"
        "   - Include header row with column names\n"
        "   - Include separator row with dashes (---)\n"
        "   - Each data row should use pipes to separate columns\n"
        "   - Example: | column1 | column2 |\\n| --- | --- |\\n| value1 | value2 |\n"
        "7. For single-value results (one row, one column), you may present as plain text\n"
        "8. Format numeric values intelligently:\n"
        "   - For large numbers (> 1,000,000), do not show decimals (e.g., 1,234,567)\n"
        "   - For other decimal numbers, limit to 2 decimal places (e.g., 123.45)\n"
        "   - Use thousands separators for readability where appropriate\n"
        "9. Show the data directly. Avoid asking for permission to show results.\n"
        "   - If the user asks for a list, show the list.\n"
        "   - If the user asks for a count, show the count.\n"
        "   - Avoid saying 'I can show you the results' - just show them.\n"
        "   - Avoid saying 'The results are available' - display them in the table format.\n"
        "\n"
        "Example workflows:\n"
        "User asks: 'Show me the delivery methods'\n"
        "Your response should be:\n"
        "```sql\n"
        "SELECT * FROM delivery_methods LIMIT 10\n"
        "```\n"
        "| id | name | description |\n"
        "| --- | --- | --- |\n"
        "| 1 | Pickup | Customer pickup |\n"
        "| 2 | Delivery | Home delivery |\n"
        "\n"
        "User asks: 'How many orders?'\n"
        "Step 1: Check schema for tables containing 'order'\n"
        "Step 2: Write SQL using the correct table name\n"
        "Your response should be:\n"
        "```sql\n"
        "SELECT COUNT(*) FROM orders\n"
        "```\n"
        "117381\n"
        "\n"
        "User asks: 'Orders per status?'\n"
        "Your response should be:\n"
        "```sql\n"
        "SELECT status, COUNT(*) as order_count FROM orders GROUP BY status\n"
        "```\n"
        "| status | order_count |\n"
        "| --- | --- |\n"
        "| 0 | 12295 |\n"
        "| 8 | 101937 |\n"
        "\n"
        "Do not just show the result without the SQL. Always show both.\n"
        "\n\n"
        "DATABASE CONTEXT:\n"
        "- The active project and database are already selected for you\n"
        "- When calling duckdb_query, you do NOT need to specify the 'database' or 'project' parameters\n"
        "- The tool will automatically use the currently active database\n"
        "- Simply call: duckdb_query(sql='your query here')\n"
        "\n\n"
        "OTHER GUIDELINES:\n"
        "- For schema details, use the duckdb_schema tool with actions: list_tables, list_fields, or get_schema\n"
        "- When showing data, select 3-4 important columns unless the user specifies otherwise\n"
        "- Use DuckDB-specific syntax for queries\n"
        "   - If a query fails, show the query to the user and attempt to fix it\n"
        "- Write SQL and results directly in your answer as markdown, not as Python code or print statements\n"
        "\n\n"
        "DATA CLEANING AND ROBUSTNESS:\n"
        "- Real-world data is often dirty. When casting strings to dates or numbers, ALWAYS use safe functions:\n"
        "  - Use TRY_CAST(col AS TYPE) instead of CAST(col AS TYPE)\n"
        "  - Use TRY_STRPTIME(col, 'format') instead of STRPTIME(col, 'format')\n"
        "- These functions return NULL on failure instead of crashing the query.\n"
        "- If you encounter 'Invalid Input Error', it means you need to use these safe functions.\n"
        "- CHECK DATA TYPES: strptime() ONLY works on string (VARCHAR) columns.\n"
        "  - If a column is already DATE or TIMESTAMP, do NOT use strptime().\n"
        "  - Check the schema first. If it's a DATE, use it directly.\n"
        "- REGEX FUNCTIONS: Use 'regexp_matches(string, pattern)' instead of 'regexp_match'.\n"
        "\n\n"
        "DOCUMENTATION UPDATES:\n"
        "If the user provides metadata, descriptions, or a data dictionary (e.g., from an uploaded file or image):\n"
        "1. FIRST: Check the actual database schema using duckdb_schema(action='list_fields', table_name='...')\n"
        "   to see ALL fields in the table (both documented and undocumented).\n"
        "2. Parse the user-provided information to identify field names and descriptions.\n"
        "3. Match field names from the file to the actual database fields (case-insensitive, handle variations).\n"
        "4. Use duckdb_schema(action='update_fields_batch') to SAVE/CREATE documentation for ALL matching fields.\n"
        "5. IMPORTANT: The update_field/update_fields_batch actions will CREATE field documentation\n"
        "   if it doesn't exist yet. You CAN document fields that exist in the database but aren't in the schema.\n"
        "6. DATA TYPE INFERENCE: When updating field documentation:\n"
        "   - The system will automatically sample actual data from the database to infer accurate data types\n"
        "   - You can provide a data_type if you know it, but generic types like 'VARCHAR' will be refined\n"
        "   - For example, if field values look like UUIDs, the system will detect and use 'UUID' type\n"
        "   - This ensures data types are based on actual data patterns, not just user descriptions\n"
        "7. Do NOT just list the metadata in the chat; persist it to the schema.\n"
        "8. Example workflow:\n"
        "   a) User uploads Excel with field descriptions for 'members' table\n"
        "   b) Call: duckdb_schema(action='list_fields', table_name='members') to see all fields\n"
        "   c) Match Excel data to actual field names (handle spacing, underscores, etc.)\n"
        "   d) Call: duckdb_schema(action='update_fields_batch', table_name='members', "
        "fields_json='[{\"name\": \"contact_civility_title\", \"short_description\": \"Civility title\"}, "
        "{\"name\": \"email\", \"short_description\": \"User email\"}]')\n"
        "   e) The system will automatically sample data to detect types (e.g., UUID fields)\n"
        "   f) Report: 'Updated documentation for 2 fields in members table'\n"
    )

    agent = DirectOpenAIAgent(
        client=client,
        model=model_name,
        query_tool=tool,
        schema_tool=schema_tool,
        chart_tool=chart_tool,
        system_prompt=system_prompt,
        max_iterations=max_steps,
        max_history_messages=20,  # Keep last 20 messages to prevent token overflow
    )

    # Store tool references for backward compatibility
    agent.duckdb_tool = tool  # type: ignore[attr-defined]
    agent.duckdb_schema_tool = schema_tool  # type: ignore[attr-defined]
    agent.duckdb_chart_tool = chart_tool  # type: ignore[attr-defined]

    return agent


def _validate_azure_openai_connection(client: AzureOpenAI, endpoint: str) -> None:
    """Ensure the Azure OpenAI credentials are valid before returning the agent."""
    try:
        # Simple test - list models to verify connection
        client.models.list()
    except Exception as exc:  # pragma: no cover - depends on environment configuration
        raise RuntimeError(
            "Azure OpenAI connectivity test failed. Check AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and "
            "AZURE_OPENAI_API_VERSION. "
            f"Endpoint attempted: {endpoint}. "
            f"Details: {exc}"
        ) from exc


def run_agent(prompt: str, **agent_kwargs) -> str:
    """Helper to create the agent and run a single prompt."""
    agent = create_duckdb_agent(**agent_kwargs)
    return agent.run(prompt)


def _parse_cli_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive DuckDB assistant powered by smolagents and Azure OpenAI.")
    parser.add_argument(
        "--prompt",
        help="Run a single-turn interaction with the given prompt instead of starting the chat loop.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
        help="Azure OpenAI deployment name to use. Defaults to AZURE_OPENAI_DEPLOYMENT or 'gpt-5'.",
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        help="Azure OpenAI endpoint URL. Defaults to AZURE_OPENAI_ENDPOINT or the configured resource base URL.",
    )
    parser.add_argument(
        "--api-version",
        default=os.environ.get("AZURE_OPENAI_API_VERSION"),
        help="Azure OpenAI API version (required if not set in environment).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("AZURE_OPENAI_API_KEY"),
        help="Azure OpenAI API key (required if not set in environment).",
    )
    parser.add_argument(
        "--search-root",
        action="append",
        default=None,
        help="Additional directories (can be repeated) to search for DuckDB files.",
    )
    parser.add_argument(
        "--default-db",
        default=os.environ.get("DUCKDB_PATH"),
        help="Preferred DuckDB file to use when multiple are discovered.",
    )
    parser.add_argument(
        "--duckdb-exe",
        default=os.environ.get("DUCKDB_EXECUTABLE"),
        help="Path to duckdb.exe. Defaults to DUCKDB_EXECUTABLE environment variable.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=8,
        help="Maximum number of reasoning/tool-call iterations for the agent.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    load_dotenv()
    args = _parse_cli_args(argv or sys.argv[1:])

    try:
        agent = create_duckdb_agent(
            model_name=args.model,
            api_key=args.api_key,
            azure_endpoint=args.endpoint,
            api_version=args.api_version,
            search_roots=args.search_root,
            default_database=args.default_db,
            duckdb_executable=args.duckdb_exe,
            max_steps=args.max_steps,
        )
    except Exception as exc:  # pragma: no cover - initialization errors
        print(f"Failed to initialize agent: {exc}", file=sys.stderr)
        return 1

    if args.prompt:
        try:
            response = agent.run(args.prompt, reset=True)
        except Exception as exc:  # pragma: no cover - runtime errors
            print(f"Agent failed: {exc}", file=sys.stderr)
            return 1
        print(response)
        return 0

    print("DuckDB Agent chat. Type 'exit' or 'quit' to leave.")
    reset = True
    while True:
        try:
            tool_ref = getattr(agent, "duckdb_tool", None)
            project_label = ""
            if tool_ref and getattr(tool_ref, "current_project", None):
                project_label = f"[project: {tool_ref.current_project}] "
            user_input = input(f"{project_label}You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            break

        try:
            response = agent.run(user_input, reset=reset)
        except Exception as exc:
            print(f"Agent error: {exc}", file=sys.stderr)
            reset = False
            continue

        output = response
        if isinstance(output, dict):
            output = output.get("output", output)
        print(f"Agent: {output}")
        reset = False

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
