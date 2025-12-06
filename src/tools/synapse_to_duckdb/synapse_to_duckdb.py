from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence, Union, cast

import duckdb

pyodbc_import_error: Optional[ImportError] = None
try:  # Import lazily to provide a clearer error if dependencies are missing.
    import pyodbc  # type: ignore
except ImportError as exc:  # pragma: no cover - exercised when dependency is missing
    pyodbc = None  # type: ignore
    pyodbc_import_error = exc

pandas_import_error: Optional[ImportError] = None
try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover - exercised when dependency is missing
    pd = None  # type: ignore
    pandas_import_error = exc

if TYPE_CHECKING:  # pragma: no cover - hints only
    import pyodbc  # noqa: F401
    from duckdb import DuckDBPyConnection

__all__ = ["SynapseConnectionConfig", "copy_synapse_objects_to_duckdb"]


@dataclass(frozen=True, kw_only=True)
class SynapseConnectionConfig:
    """
    Encapsulates the information required to connect to an Azure Synapse SQL endpoint.

    Parameters
    ----------
    server:
        The fully qualified Synapse server host, e.g. ``your-workspace.sql.azuresynapse.net``.
    database:
        Database name to connect to.
    username:
        SQL username or Active Directory user (when using ActiveDirectoryPassword authentication).
    password:
        Password for the supplied user.
    driver:
        Name of the installed ODBC driver. Defaults to ``ODBC Driver 18 for SQL Server``.
    port:
        TCP port for the endpoint. Synapse SQL uses ``1433`` by default.
    encrypt:
        When ``True`` (default) TLS is enforced for the connection.
    trust_server_certificate:
        Set to ``True`` only if you need to trust the server certificate without validation.
    timeout:
        Connection timeout in seconds (defaults to 30).
    authentication:
        Optional authentication mode, e.g. ``ActiveDirectoryPassword`` or ``SqlPassword``.
    extra_params:
        Additional key-value pairs appended to the ODBC connection string.
    """

    server: str
    database: str
    username: str
    password: str
    driver: str = "ODBC Driver 18 for SQL Server"
    port: int = 1433
    encrypt: bool = True
    trust_server_certificate: bool = False
    timeout: int = 30
    authentication: Optional[str] = None
    extra_params: Mapping[str, str] = field(default_factory=dict)

    def build_connection_string(self) -> str:
        """Return a complete ODBC connection string for pyodbc."""
        settings: list[str] = [
            f"Driver={{{self.driver}}}",
            f"Server=tcp:{self.server},{self.port}",
            f"Database={self.database}",
            f"Uid={self.username}",
            f"Pwd={self.password}",
            f"Encrypt={'yes' if self.encrypt else 'no'}",
            f"TrustServerCertificate={'yes' if self.trust_server_certificate else 'no'}",
            f"Connection Timeout={self.timeout}",
        ]

        if self.authentication:
            settings.append(f"Authentication={self.authentication}")

        if self.extra_params:
            settings.extend(f"{key}={value}" for key, value in self.extra_params.items())

        return ";".join(settings)


def copy_synapse_objects_to_duckdb(
    connection_config: SynapseConnectionConfig,
    duckdb_path: Union[str, Path],
    objects: Sequence[Mapping[str, object]],
    *,
    overwrite_existing: bool = True,
) -> None:
    """
    Copy data from Azure Synapse SQL views or ad-hoc queries into local DuckDB tables.

    Parameters
    ----------
    connection_config:
        Connection details for the Synapse endpoint.
    duckdb_path:
        Destination DuckDB database file path (use ``':memory:'`` for an in-memory database).
    objects:
        Iterable of mapping objects. Each mapping must contain one of:

        - ``view``: fully qualified view name to pull with ``SELECT *``.
        - ``query``: explicit SQL query text to execute.

        Optional keys:

        - ``destination_table``: Name of the DuckDB table to create/replace.
          Defaults to the view name (minus schema) or ``result_{index}`` for queries.
        - ``params``: Either a mapping of parameter names to values (in placeholder order) or a sequence of positional
          values for parametrised queries using ``?`` placeholders.
        - ``limit``: Optional positive integer restricting the number of rows copied from a view.
        - ``order_by``: Optional ``ORDER BY`` clause applied when copying a view; typically used with ``limit``.

    Parameters
    ----------
    overwrite_existing:
        When ``True`` (default), existing DuckDB tables with the same destination name are replaced. When ``False``,
        already-present tables are left untouched and logged as skipped.

    Raises
    ------
    ImportError
        If required dependencies (pyodbc or pandas) are missing.
    ValueError
        If neither (or both) of ``view`` and ``query`` are supplied for an item.

    Examples
    --------
    >>> config = SynapseConnectionConfig(
    ...     server="myworkspace.sql.azuresynapse.net",
    ...     database="sales",
    ...     username="etl_user",
    ...     password="S3cret!",
    ... )
    >>> copy_synapse_objects_to_duckdb(
    ...     config,
    ...     duckdb_path="local.duckdb",
    ...     objects=[
    ...         {"view": "dbo.CustomerDimension"},
    ...         {
    ...             "query": "SELECT TOP 100 * FROM dbo.FactSales WHERE SaleDate >= ?",
    ...             "params": {"SaleDate": "2024-01-01"},
    ...             "destination_table": "recent_sales",
    ...         },
    ...     ],
    ... )
    """

    if pyodbc is None:
        raise ImportError(
            "pyodbc is required to connect to Azure Synapse. Install it with `pip install pyodbc`."
        ) from pyodbc_import_error

    if pd is None:
        raise ImportError(
            "pandas is required for data transfer. Install it with `pip install pandas`."
        ) from pandas_import_error

    duck_path = Path(duckdb_path).expanduser()
    connection_string = connection_config.build_connection_string()

    with closing(pyodbc.connect(connection_string)) as synapse_conn, closing(
        duckdb.connect(str(duck_path))
    ) as duck_conn:
        for index, obj in enumerate(objects, start=1):
            _copy_single_object(index, obj, synapse_conn, duck_conn, overwrite_existing)


def _copy_single_object(
    index: int,
    obj: Mapping[str, object],
    synapse_conn: "pyodbc.Connection",  # type: ignore
    duck_conn: DuckDBPyConnection,
    overwrite_existing: bool,
) -> None:
    view_name = cast(Optional[str], obj.get("view"))
    query_text = cast(Optional[str], obj.get("query"))

    if bool(view_name) == bool(query_text):
        raise ValueError(
            f"Item #{index} must supply exactly one of 'view' or 'query' (received {obj})."
        )

    if view_name:
        default_destination = str(view_name).split(".")[-1]
        limit_value = obj.get("limit")
        order_by_value = obj.get("order_by")

        limit_clause: Optional[int] = None
        if limit_value is not None:
            try:
                limit_clause = int(cast(Any, limit_value))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"'limit' for item #{index} must be an integer value.") from exc
            if limit_clause <= 0:
                raise ValueError(f"'limit' for item #{index} must be greater than zero (received {limit_clause}).")

        order_by_clause: Optional[str] = None
        if order_by_value is not None:
            if not isinstance(order_by_value, str) or not order_by_value.strip():
                raise ValueError(f"'order_by' for item #{index} must be a non-empty string if provided.")
            order_by_clause = order_by_value.strip()

        if limit_clause is not None:
            query_text = f"SELECT TOP ({limit_clause}) * FROM {view_name}"
        else:
            query_text = f"SELECT * FROM {view_name}"

        if order_by_clause:
            query_text += f" ORDER BY {order_by_clause}"
    else:
        default_destination = f"result_{index}"

    raw_destination = obj.get("destination_table")
    if raw_destination is None:
        destination = default_destination
    else:
        destination = str(raw_destination).strip() or default_destination
    exists_already = _table_exists(destination, duck_conn)

    if exists_already and not overwrite_existing:
        print(f"- Skipping '{destination}' (already exists in DuckDB).")
        return

    action_note = " (replacing existing table)" if exists_already else ""
    print(f"- Copying into '{destination}'{action_note}...")

    params = _normalise_params(obj.get("params"), index)
    df = _fetch_dataframe(index, str(query_text), params, synapse_conn)
    df = _coerce_dataframe_types(df)

    temp_name = f"synapse_tmp_{index}"
    duck_conn.register(temp_name, df)

    try:
        escaped_destination = _quote_identifier(str(destination))
        duck_conn.execute(f"CREATE OR REPLACE TABLE {escaped_destination} AS SELECT * FROM {temp_name}")
    finally:
        duck_conn.unregister(temp_name)
    print(f"  Finished '{destination}'.")


def _normalise_params(raw_params: object, index: int) -> Optional[tuple[Any, ...]]:
    if raw_params is None:
        return None

    if isinstance(raw_params, Mapping):
        return tuple(raw_params.values())

    if isinstance(raw_params, SequenceABC) and not isinstance(raw_params, (str, bytes, bytearray)):
        return tuple(raw_params)

    raise ValueError(f"'params' for item #{index} must be a mapping or sequence of values.")


def _fetch_dataframe(
    index: int,
    query: str,
    params: Optional[tuple[Any, ...]],
    synapse_conn: "pyodbc.Connection",  # type: ignore
) -> "pd.DataFrame":  # type: ignore
    if pd is None:
        raise RuntimeError("pandas is unavailable while fetching data from Synapse.")

    cursor = synapse_conn.cursor()
    try:
        # Prevent "rows affected" messages from interfering with result sets
        cursor.execute("SET NOCOUNT ON")
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
        except Exception as e:
            # Retry with ANSI_WARNINGS OFF if truncation error occurs
            if "String or binary data would be truncated" in str(e):
                try:
                    cursor.execute("SET ANSI_WARNINGS OFF")
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                except Exception as retry_e:
                    _raise_execution_error(index, query, params, retry_e)
            else:
                _raise_execution_error(index, query, params, e)

        # Skip past any non-result-set messages (e.g. from triggers or SET commands)
        while cursor.description is None:
            if not cursor.nextset():
                break

        if cursor.description is None:
            info_lines = [f"Query for item #{index} did not return a result set (cursor.description is None)."]
            info_lines.append("This typically means:")
            info_lines.append("- The view/table exists but has no column definitions")
            info_lines.append("- The view is a stored procedure or non-SELECT object")
            info_lines.append("- The query executed but returned no metadata")
            info_lines.append("\nExecuted SQL:")
            info_lines.append(query.strip())
            if params:
                info_lines.append(f"Parameters: {list(params)}")
            info_lines.append(f"\nRow count returned: {cursor.rowcount}")
            raise ValueError(
                "\n".join(info_lines)
            )

        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
    finally:
        cursor.close()

    assert pd is not None  # Satisfy type checkers; guarded above.
    return pd.DataFrame.from_records(rows, columns=columns)


def _raise_execution_error(
    index: int, query: str, params: Optional[tuple[Any, ...]], error: Exception
) -> None:
    info_lines = [f"Failed to execute query for item #{index}."]
    info_lines.append(f"Error: {error}")
    info_lines.append("Executed SQL:")
    info_lines.append(query.strip())
    if params:
        info_lines.append(f"Parameters: {list(params)}")
    info_lines.append("\nPossible causes:")
    info_lines.append("- View/table does not exist in the database")
    info_lines.append("- Insufficient permissions to access the object")
    info_lines.append("- Invalid SQL syntax")
    raise ValueError("\n".join(info_lines)) from error


def _quote_identifier(identifier: str) -> str:
    parts = identifier.split(".")
    quoted_parts: list[str] = []
    for part in parts:
        cleaned = part.strip()
        if not cleaned:
            raise ValueError(f"Invalid destination identifier segment in '{identifier}'.")
        escaped = cleaned.replace('"', '""')
        quoted_parts.append(f'"{escaped}"')
    return ".".join(quoted_parts)


def _table_exists(destination: str, duck_conn: DuckDBPyConnection) -> bool:
    schema, table = _split_destination(destination)
    if schema:
        result = duck_conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE lower(table_schema) = ? AND lower(table_name) = ? LIMIT 1",
            [schema.lower(), table.lower()],
        ).fetchone()
    else:
        result = duck_conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE lower(table_name) = ? LIMIT 1",
            [table.lower()],
        ).fetchone()
    return result is not None


def _split_destination(destination: str) -> tuple[Optional[str], str]:
    raw_parts = destination.split(".")
    if len(raw_parts) == 1:
        return (None, _strip_identifier(raw_parts[0]))

    table_part = _strip_identifier(raw_parts[-1])
    schema_part = ".".join(_strip_identifier(part) for part in raw_parts[:-1])
    return (schema_part, table_part)


def _strip_identifier(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith('"') and cleaned.endswith('"'):
        return cleaned[1:-1].replace('""', '"')
    if cleaned.startswith("[") and cleaned.endswith("]"):
        return cleaned[1:-1]
    if cleaned.startswith("`") and cleaned.endswith("`"):
        return cleaned[1:-1]
    return cleaned.strip("'")


def _coerce_dataframe_types(df: "pd.DataFrame") -> "pd.DataFrame":  # type: ignore[valid-type]
    """Attempt to coerce object-typed columns to numerics when every value is parseable."""
    if pd is None:
        raise RuntimeError("pandas is required to coerce dataframe types.")

    assert pd is not None  # Narrow for static analysis.
    result = df.copy()
    for column in result.columns:
        series = result[column]
        if pd.api.types.is_object_dtype(series):
            converted = pd.to_numeric(series, errors="coerce")
            if converted.isna().any():
                original_na = series.isna()
                if converted.isna().equals(original_na):
                    result[column] = converted
            else:
                result[column] = converted
    return result
