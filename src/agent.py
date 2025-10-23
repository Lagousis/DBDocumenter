from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from dotenv import load_dotenv

try:
    if __package__:
        from .tools.duckdb_diagram_tool import DuckDBDiagramTool
        from .tools.duckdb_query_tool import DEFAULT_DATABASES_ROOT, DuckDBQueryTool
        from .tools.duckdb_schema_tool import DuckDBSchemaTool
        from .tools.duckdb_ui_tool import DuckDBLaunchUITool
    else:  # pragma: no cover - script entry compatibility
        from tools.duckdb_diagram_tool import DuckDBDiagramTool
        from tools.duckdb_query_tool import DEFAULT_DATABASES_ROOT, DuckDBQueryTool
        from tools.duckdb_schema_tool import DuckDBSchemaTool
        from tools.duckdb_ui_tool import DuckDBLaunchUITool
except ImportError:  # pragma: no cover - fallback when executed directly
    # Allow execution via `python agent.py` from the src directory
    sys.path.append(str(Path(__file__).resolve().parent))
    from tools.duckdb_diagram_tool import DuckDBDiagramTool
    from tools.duckdb_query_tool import DEFAULT_DATABASES_ROOT, DuckDBQueryTool
    from tools.duckdb_schema_tool import DuckDBSchemaTool
    from tools.duckdb_ui_tool import DuckDBLaunchUITool

try:
    from smolagents import CodeAgent
    from smolagents.models import AzureOpenAIServerModel
except ImportError as exc:  # pragma: no cover - dependency guard
    raise ImportError(
        "The 'smolagents' package is required. Install it with `pip install smolagents[duckdb]`."
    ) from exc
else:
    try:
        from smolagents import models as _smol_models
    except ImportError:  # pragma: no cover - safety net
        _smol_models = None
    else:
        _original_supports_stop_parameter = _smol_models.supports_stop_parameter

        def _patched_supports_stop_parameter(model_id: str) -> bool:
            if model_id and model_id.split("/")[-1].startswith("gpt-5"):
                return False
            return _original_supports_stop_parameter(model_id)

        _smol_models.supports_stop_parameter = _patched_supports_stop_parameter

DEFAULT_AZURE_ENDPOINT = "https://slagousis-eastus-resource.cognitiveservices.azure.com/"
BOOL_TRUE = {"1", "true", "yes", "on"}

__all__ = [
    "DuckDBQueryTool",
    "DuckDBSchemaTool",
    "DuckDBDiagramTool",
    "DuckDBLaunchUITool",
    "create_duckdb_agent",
    "run_agent",
    "main",
]


class SchemaAwareCodeAgent(CodeAgent):
    """CodeAgent that relies on explicit tool calls for schema access instead of auto-injecting metadata."""

    def __init__(self, *, schema_tool: DuckDBSchemaTool, **kwargs) -> None:
        self._system_prompt: Optional[str] = kwargs.pop("system_prompt", None)
        super().__init__(**kwargs)
        self.schema_tool = schema_tool
        self._system_prompt_shared = False

    def run(self, prompt: str, *, reset: bool = False, **kwargs):
        if reset:
            self._system_prompt_shared = False

        segments: list[str] = []

        if self._system_prompt and not self._system_prompt_shared:
            segments.append(f"System instructions:\n{self._system_prompt}")
            self._system_prompt_shared = True

        segments.append(f"User request:\n{prompt}")
        prompt_to_send = "\n\n".join(segments)

        return super().run(prompt_to_send, reset=reset, **kwargs)


def create_duckdb_agent(
    *,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    azure_endpoint: Optional[str] = None,
    api_version: Optional[str] = None,
    search_roots: Iterable[str | Path] | None = None,
    default_database: Optional[str | Path] = None,
    duckdb_executable: Optional[str | Path] = None,
    max_steps: int = 8,
) -> CodeAgent:
    """
    Build a SMOL CodeAgent equipped with the DuckDBQueryTool.

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
        Maximum number of reasoning/tool-call iterations permitted for the agent.
    """

    load_dotenv()

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

    if search_roots is None:
        env_roots = os.environ.get("DUCKDB_SEARCH_ROOTS")
        if env_roots:
            search_roots = [Path(path.strip()) for path in env_roots.split(os.pathsep) if path.strip()]
        else:
            search_roots = [DEFAULT_DATABASES_ROOT]
    else:
        search_roots = [Path(path) for path in search_roots]

    if default_database is None:
        default_env = os.environ.get("DUCKDB_PATH")
        default_database = Path(default_env) if default_env else None
    else:
        default_database = Path(default_database)

    if duckdb_executable is None:
        env_executable = os.environ.get("DUCKDB_EXECUTABLE")
        duckdb_executable_path = Path(env_executable) if env_executable else None
    else:
        duckdb_executable_path = Path(duckdb_executable)

    tool = DuckDBQueryTool(
        search_roots=[Path(root) for root in search_roots],
        default_database=default_database,
    )
    if tool.search_roots:
        primary_root = tool.search_roots[0]
        print(f"DuckDB databases directory: {primary_root}")
        if len(tool.search_roots) > 1:
            additional_roots = ", ".join(str(root) for root in tool.search_roots[1:])
            print(f"Additional search roots: {additional_roots}")
    available_projects = tool.discover_databases()
    print("Available DuckDB projects:")
    if available_projects:
        for path in available_projects:
            print(f"- {path.stem}")
    else:
        print("- <none>")
    schema_tool = DuckDBSchemaTool(tool)

    llm = AzureOpenAIServerModel(
        model_id=model_name,
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version,
    )

    if os.environ.get("AZURE_OPENAI_SKIP_CHECK", "").strip().lower() not in BOOL_TRUE:
        _validate_azure_openai_connection(llm, azure_endpoint)

    diagram_tool = DuckDBDiagramTool(tool)
    ui_tool = DuckDBLaunchUITool(tool, default_executable=duckdb_executable_path)

    system_prompt = (
        "You are the DBDocumenter assistant. Restrict every response to the DuckDB schemas, tables, and data "
        "available through this project. When a user asks about unrelated topics, politely redirect them toward "
        "questions about the documented datasets or available queries. When a user requests an ER diagram, "
        "ask for their preferred image filename (fill out extension if not provided) and call the duckdb_diagram tool "
        "with thatimage_path. "
        "Only return a text-only summary without exporting an image if the user explicitly opts out of image "
        "generation. "
        "When you need schema details, call the 'duckdb_schema' tool (actions: list_tables, list_fields, get_schema) "
        "instead of assuming the schema is already in context. When a user wants to open the DuckDB graphical "
        "interface or browse the database visually, launch the 'duckdb_ui' tool (provide the project name when "
        "multiple databases exist). "
        "All fields that exist in the documented schema are considered documented if the have any description. "
        "Check the tables in the DB for fields that are missing documentation and offer to document them when asked. "
        "Be careful with the data in the schema json, do not delete useful information. "
        "When asked to show data select a few important columns (3-4) and limit the number of rows to 10, "
        "except if asked explicity for specific columns or number of rows. "
        "The DB you quering is duckdb, so use duckdb specific syntax. "
        "When a query fails show the query to the user and continue to try to fix it. "
    )

    agent = SchemaAwareCodeAgent(
        schema_tool=schema_tool,
        tools=[tool, schema_tool, diagram_tool, ui_tool],
        model=llm,
        max_steps=max_steps,
        additional_authorized_imports=["duckdb"],
        system_prompt=system_prompt,
    )
    agent.duckdb_tool = tool  # type: ignore[attr-defined]
    agent.duckdb_schema_tool = schema_tool  # type: ignore[attr-defined]
    agent.duckdb_diagram_tool = diagram_tool  # type: ignore[attr-defined]
    agent.duckdb_ui_tool = ui_tool  # type: ignore[attr-defined]
    return agent


def _validate_azure_openai_connection(model: AzureOpenAIServerModel, endpoint: str) -> None:
    """Ensure the Azure OpenAI credentials are valid before returning the agent."""
    try:
        client = model.create_client()
    except Exception as exc:  # pragma: no cover - depends on environment configuration
        raise RuntimeError(
            "Failed to create Azure OpenAI client. Check AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and "
            "AZURE_OPENAI_API_VERSION. "
            f"Endpoint attempted: {endpoint}. "
            f"Details: {exc}"
        ) from exc

    errors: list[Exception] = []

    if hasattr(client, "models") and hasattr(client.models, "list"):
        try:
            client.models.list()
            return
        except Exception as exc:  # pragma: no cover - depends on service
            errors.append(exc)

    last_error = errors[-1] if errors else None
    detail = f" Details: {last_error}" if last_error else ""
    raise RuntimeError(
        "Azure OpenAI connectivity test failed. Ensure the deployment name, endpoint, and API version are correct "
        f"and that the resource is reachable. Endpoint attempted: {endpoint}.{detail}"
    ) from last_error


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

        output = response.output if hasattr(response, "output") else response
        if isinstance(output, dict):
            output = output.get("output", output)
        print(f"Agent: {output}")
        reset = False

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
