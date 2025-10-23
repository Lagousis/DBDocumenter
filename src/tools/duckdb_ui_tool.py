from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Optional

from smolagents import Tool

from .duckdb_query_tool import DuckDBQueryTool

__all__ = ["DuckDBLaunchUITool"]


class DuckDBLaunchUITool(Tool):
    """Tool that launches the DuckDB web UI for a selected project database."""

    name = "duckdb_ui"
    output_type = "string"
    description = (
        "Prepares the command to open the DuckDB graphical UI (`duckdb.exe -ui`) for the chosen database. "
        "It prints the command first and only executes it when run=true. "
        "If the executable is not found in the project directory, provide its full path."
    )
    inputs = {
        "project": {
            "type": "string",
            "description": "Project name (DuckDB filename without extension) to open.",
            "nullable": True,
        },
        "database": {
            "type": "string",
            "description": "Explicit path to the DuckDB file to open.",
            "nullable": True,
        },
        "executable": {
            "type": "string",
            "description": "Path to duckdb.exe when it is not located in the project root.",
            "nullable": True,
        },
        "run": {
            "type": "boolean",
            "description": "Set to true to let the agent execute the launch command after you confirm.",
            "nullable": True,
        },
    }
    outputs = {
        "result": {
            "type": "string",
            "description": "Status message describing the DuckDB UI launch result or instructions for the user.",
        }
    }

    def __init__(self, duckdb_tool: DuckDBQueryTool, default_executable: Optional[Path] = None) -> None:
        super().__init__()
        self.duckdb_tool = duckdb_tool
        self.default_executable = (
            default_executable.expanduser().resolve()
            if default_executable
            else (Path.cwd() / "duckdb.exe").resolve()
        )

    def forward(
        self,
        project: Optional[str] = None,
        database: Optional[str] = None,
        executable: Optional[str] = None,
        run: Optional[bool] = None,
    ) -> dict[str, str]:
        exe_candidate = Path(executable).expanduser() if executable else self.default_executable
        if not exe_candidate.is_absolute():
            exe_candidate = (Path.cwd() / exe_candidate).resolve()
        if not exe_candidate.exists():
            return {
                "result": (
                    "DuckDB executable was not found. Please provide the full path to duckdb.exe using the "
                    "'executable' argument."
                )
            }

        available = self.duckdb_tool.discover_databases()
        if not available:
            return {"result": "No DuckDB databases were discovered under the configured search roots."}

        try:
            target = self.duckdb_tool._resolve_database(database=database, project=project, available=available)
        except ValueError as exc:
            return {"result": str(exc)}

        run_flag = False
        if isinstance(run, str):
            run_flag = run.strip().lower() in {"1", "true", "yes", "on", "y"}
        elif run:
            run_flag = True

        self.duckdb_tool.current_database = target
        if self.duckdb_tool.schema_manager:
            self.duckdb_tool.schema_manager.set_database(target)

        # The param ui must be lowercase -UI does not work
        command = [str(exe_candidate), str(target), "-ui"]
        if os.name == "nt":
            command_display = subprocess.list2cmdline(command)
        else:
            command_display = shlex.join(command)

        if not run_flag:
            return {
                "result": (
                    "To open the DuckDB UI yourself, run this command in a terminal:\n"
                    f"{command_display}\n\n"
                    "If you would like me to run it for you, call the duckdb_ui tool again with run=true."
                )
            }

        popen_kwargs: dict[str, object] = {"cwd": str(exe_candidate.parent)}
        if os.name == "nt":
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                popen_kwargs["creationflags"] = getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP"
                )  # type: ignore[attr-defined]
        else:
            popen_kwargs["start_new_session"] = True
        try:
            subprocess.Popen(command, **popen_kwargs)
        except FileNotFoundError:
            return {
                "result": (
                    f"Failed to launch DuckDB UI because the executable at '{exe_candidate}' was not found. "
                    "Provide a valid path using the 'executable' argument."
                )
            }
        except Exception as exc:  # pragma: no cover - system dependent
            return {"result": f"Failed to launch DuckDB UI: {exc}"}

        return {
            "result": (
                f"DuckDB UI launching for project '{target.stem}'. Command executed:\n{command_display}"
            )
        }
