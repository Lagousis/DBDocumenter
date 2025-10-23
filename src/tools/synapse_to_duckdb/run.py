from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Mapping

from dotenv import load_dotenv

if __package__:
    from .synapse_to_duckdb import SynapseConnectionConfig, copy_synapse_objects_to_duckdb
else:  # pragma: no cover - script entry compatibility
    from synapse_to_duckdb import SynapseConnectionConfig, copy_synapse_objects_to_duckdb

BOOL_TRUE = {"1", "true", "yes", "on"}


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def optional_env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in BOOL_TRUE


def optional_env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive path
        raise RuntimeError(f"Environment variable {name} must be an integer.") from exc


def parse_extra_params(raw: str) -> Mapping[str, str]:
    params: Dict[str, str] = {}
    for segment in raw.split(";"):
        trimmed = segment.strip()
        if not trimmed or "=" not in trimmed:
            continue
        key, value = trimmed.split("=", 1)
        params[key.strip()] = value.strip()
    return params


def gather_objects() -> List[Mapping[str, object]]:
    objects: List[Mapping[str, object]] = []

    views_env = os.environ.get("SYNAPSE_VIEWS", "")
    if views_env:
        for view in views_env.split(","):
            cleaned = view.strip()
            if cleaned:
                objects.append({"view": cleaned})

    queries_json = os.environ.get("SYNAPSE_QUERIES_JSON", "").strip()
    if queries_json:
        try:
            parsed = json.loads(queries_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("SYNAPSE_QUERIES_JSON must contain valid JSON.") from exc

        if not isinstance(parsed, list):
            raise RuntimeError("SYNAPSE_QUERIES_JSON must be a JSON array of query objects.")

        for idx, entry in enumerate(parsed, start=1):
            if not isinstance(entry, Mapping):
                raise RuntimeError(f"Query entry #{idx} must be a JSON object.")
            objects.append(dict(entry))

    if not objects:
        raise RuntimeError(
            "No objects to copy. Provide SYNAPSE_VIEWS (comma separated) and/or SYNAPSE_QUERIES_JSON (JSON array)."
        )

    return objects


def test_synapse_connection(config: SynapseConnectionConfig) -> None:
    try:
        import pyodbc
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("pyodbc is required to verify the Synapse connection.") from exc

    with closing(pyodbc.connect(config.build_connection_string())) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        finally:
            cursor.close()
    print("Confirmed connection to Azure Synapse.")


def _parse_cli_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy objects from Azure Synapse SQL into a local DuckDB database."
    )
    parser.add_argument(
        "--duckdb-path",
        "--duckdb",
        dest="duckdb_path",
        help="Path to the DuckDB database that will receive the copied objects. "
        "Overrides the DUCKDB_PATH environment variable. Defaults to local.duckdb.",
    )
    return parser.parse_args(argv)


def _resolve_duckdb_path(raw: str) -> str:
    candidate = raw.strip()
    if not candidate:
        candidate = "local.duckdb"

    if not candidate.lower().endswith(".duckdb"):
        candidate = f"{candidate}.duckdb"

    target_path = Path(candidate).expanduser()
    directory = target_path.parent if target_path.parent != Path("") else Path.cwd()
    expected_name = target_path.name

    try:
        for existing in directory.iterdir():
            if existing.is_file() and existing.suffix.lower() == ".duckdb":
                if existing.name.lower() == expected_name.lower():
                    return str(existing.resolve())
    except FileNotFoundError:
        pass

    return str(target_path)


def main(argv: List[str] | None = None) -> int:
    load_dotenv()

    args = _parse_cli_args(argv or sys.argv[1:])
    overwrite_existing = optional_env_bool("SYNAPSE_OVERWRITE_EXISTING", False)

    config = SynapseConnectionConfig(
        server=require_env("SYNAPSE_SERVER"),
        database=require_env("SYNAPSE_DATABASE"),
        username=require_env("SYNAPSE_USERNAME"),
        password=require_env("SYNAPSE_PASSWORD"),
        driver=os.environ.get("SYNAPSE_DRIVER", "ODBC Driver 18 for SQL Server"),
        port=optional_env_int("SYNAPSE_PORT", 1433),
        encrypt=optional_env_bool("SYNAPSE_ENCRYPT", True),
        trust_server_certificate=optional_env_bool("SYNAPSE_TRUST_SERVER_CERTIFICATE", False),
        timeout=optional_env_int("SYNAPSE_TIMEOUT", 30),
        authentication=os.environ.get("SYNAPSE_AUTHENTICATION"),
        extra_params=parse_extra_params(os.environ.get("SYNAPSE_EXTRA_PARAMS", "")),
    )

    print(f"Attempting to connect to Azure Synapse at {config.server}...")
    test_synapse_connection(config)

    requested_duckdb = args.duckdb_path or os.environ.get("DUCKDB_PATH", "local.duckdb")
    duckdb_path = _resolve_duckdb_path(requested_duckdb)
    objects = gather_objects()

    if overwrite_existing:
        print("Existing DuckDB tables will be replaced if encountered.")
    else:
        print("Existing DuckDB tables will be kept; matching tables are skipped.")

    print(f"Copying {len(objects)} object(s) into DuckDB at {duckdb_path}...")
    copy_synapse_objects_to_duckdb(
        config,
        duckdb_path,
        objects,
        overwrite_existing=overwrite_existing,
    )
    print(f"Completed processing {len(objects)} object(s) for DuckDB at {duckdb_path}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - entry point error reporting
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
