from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProjectInfo(BaseModel):
    name: str
    path: str
    display_name: str
    subdirectory: str = ""
    description: str = ""
    is_active: bool = False
    version: Optional[str] = None
    query_instructions: Optional[str] = None


class ProjectUpdateRequest(BaseModel):
    path: str = Field(..., description="Absolute filesystem path to the DuckDB project.")
    display_name: Optional[str] = Field(None, description="Human-friendly project display name.")
    description: Optional[str] = Field(None, description="Project description text.")
    version: Optional[str] = Field(None, description="Project version string.")
    query_instructions: Optional[str] = Field(None, description="Instructions for LLM query generation.")


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., description="Display name for the new DuckDB project.")
    description: Optional[str] = Field("", description="Optional project description.")
    query_instructions: Optional[str] = Field("", description="Optional query instructions.")


class QueryRequest(BaseModel):
    sql: str = Field(..., description="SQL query to execute.")
    project: Optional[str] = Field(None, description="Optional project name to target.")
    database: Optional[str] = Field(None, description="Explicit DuckDB file path to target.")
    limit: Optional[int] = Field(None, ge=1, description="Maximum number of rows to return.")


class QueryResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    truncated: bool
    database: Optional[str] = None
    project: Optional[str] = None
    message: Optional[str] = None


class QueryRecord(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    sql: str
    limit: Optional[int] = None
    updated_at: Optional[str] = None


class QuerySaveRequest(BaseModel):
    project: Optional[str] = None
    database: Optional[str] = None
    name: str
    description: Optional[str] = ""
    sql: str
    limit: Optional[int] = None
    query_id: Optional[str] = Field(None, alias="query_id")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to send to the assistant.")
    reset: bool = Field(False, description="When true, resets the conversation history.")
    project: Optional[str] = Field(None, description="Optional project name to activate before responding.")
    database: Optional[str] = Field(
        None, description="Explicit DuckDB file path to activate before responding."
    )
    file_content: Optional[str] = Field(
        None,
        description="Optional file content (text or base64) to include in context."
    )
    filename: Optional[str] = Field(None, description="Optional filename for the uploaded content.")
    session_id: Optional[str] = Field(
        None, description="Optional session ID to continue an existing chat."
    )
    images: Optional[List[Dict[str, str]]] = Field(
        None, description="Optional list of images with 'data' (base64) and 'name' fields."
    )


class ChatResponse(BaseModel):
    reply: str
    database: Optional[str] = None
    session_id: Optional[str] = None


class SchemaResponse(BaseModel):
    schema_data: dict[str, Any] = Field(..., alias="schema")

    class Config:
        populate_by_name = True


class UndocumentedField(BaseModel):
    name: str
    data_type: Optional[str] = Field(None, description="Data type reported by DuckDB, when available.")


class RelationshipPayload(BaseModel):
    related_table: str = Field(..., description="Target table name of the relationship.")
    related_field: str = Field(..., description="Field in the related table.")
    relationship_type: Optional[str] = Field(None, alias="type")

    class Config:
        populate_by_name = True


class FieldUpdateRequest(BaseModel):
    project: Optional[str] = Field(None, description="Optional project name to switch context.")
    database: Optional[str] = Field(None, description="Optional database path to switch context.")
    table: str
    field: str
    new_field_name: Optional[str] = Field(None, description="New field name to rename the field.")
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    nullability: Optional[str] = None
    allow_null: Optional[bool] = Field(None, description="When set, toggles nullability.")
    data_type: Optional[str] = None
    values: Optional[Dict[str, str]] = None
    relationships: Optional[List[RelationshipPayload]] = None
    ignored: Optional[bool] = None


class FieldUpdateResponse(BaseModel):
    table: str
    field: str
    metadata: Dict[str, Any]


class TableUpdateRequest(BaseModel):
    project: Optional[str] = Field(None, description="Optional project name to switch context.")
    database: Optional[str] = Field(None, description="Optional database path to switch context.")
    table: str
    short_description: Optional[str] = None
    long_description: Optional[str] = None


class TableUpdateResponse(BaseModel):
    table: str
    metadata: Dict[str, Any]


class AutoDescribeRequest(BaseModel):
    project: Optional[str] = None
    database: Optional[str] = None
    table: str
    field: str
    current_short_description: Optional[str] = None
    current_long_description: Optional[str] = None
    data_type: Optional[str] = None
    description_type: Optional[str] = None


class AutoDescribeResponse(BaseModel):
    description: str


class AIAssistFieldRequest(BaseModel):
    project: Optional[str] = None
    database: Optional[str] = None
    table: str
    field: str


class AIAssistFieldResponse(BaseModel):
    short_description: str
    long_description: str
    data_type: str
    nullable: bool


class DiagramTablePosition(BaseModel):
    name: str
    x: float
    y: float
    width: Optional[float] = None


class DiagramRecord(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    tables: List[DiagramTablePosition] = Field(default_factory=list)


class DiagramSaveRequest(BaseModel):
    project: Optional[str] = None
    database: Optional[str] = None
    name: str
    description: Optional[str] = ""
    tables: List[DiagramTablePosition] = Field(default_factory=list)
    diagram_id: Optional[str] = Field(None, alias="diagram_id")


class DatalakeInfo(BaseModel):
    """Information about a configured datalake."""

    name: str
    type: str
    container_name: str = "dbdocumenter"
    storage_account: str = "Unknown"


class DatalakeProjectInfo(BaseModel):
    """Information about a project in a datalake."""

    name: str
    version: str
    display_name: str
    description: str
    last_modified: str
    size_bytes: int
    db_size_bytes: int = 0
    schema_size_bytes: int = 0


class DatalakeAddRequest(BaseModel):
    """Request to add a new datalake."""

    name: str
    type: str = "azure_storage"
    connection_string: str
    container_name: str = "dbdocumenter"


class DatalakeTestConnectionRequest(BaseModel):
    """Request to test datalake connection."""

    type: str = "azure_storage"
    connection_string: str


class DatalakeTestConnectionResponse(BaseModel):
    """Response from testing datalake connection."""

    success: bool
    message: str
    containers: list[str] = Field(default_factory=list)


class SyncDownloadRequest(BaseModel):
    """Request to download a project from a datalake."""

    datalake_name: str
    project_name: str
    version: str
    overwrite: bool = False
    rename_existing: bool = False


class SyncUploadRequest(BaseModel):
    """Request to upload a project to a datalake."""

    datalake_name: str
    project_path: str
    new_version: Optional[str] = None
    schema_only: bool = False


class SyncDownloadResponse(BaseModel):
    """Response from a download operation."""

    success: bool
    project_name: str
    version: str
    duckdb_path: str
    schema_path: str
    message: Optional[str] = None


class SyncUploadResponse(BaseModel):
    """Response from an upload operation."""

    success: bool
    project_name: str
    version: str
    message: Optional[str] = None


class TableDeleteDataRequest(BaseModel):
    project: Optional[str] = Field(None, description="Optional project name to switch context.")
    database: Optional[str] = Field(None, description="Optional database path to switch context.")
    table: str
    mode: str = Field(..., description="Deletion mode: 'all', 'subset', or 'filter'.")
    keep_count: Optional[int] = Field(None, description="Number of rows to keep (for subset mode).")
    sort_column: Optional[str] = Field(None, description="Column to sort by (for subset mode).")
    sort_order: Optional[str] = Field(None, description="Sort order: 'ASC' or 'DESC' (for subset mode).")
    filter_condition: Optional[str] = Field(
        None,
        description="SQL WHERE clause condition (rows to keep for filter mode)."
    )


class TableStats(BaseModel):
    name: str
    row_count: int
    size_bytes: Optional[int] = None
    size_pretty: str = "N/A"


class DatabaseStatsResponse(BaseModel):
    tables: List[TableStats]
    total_size_bytes: Optional[int] = None
    total_size_pretty: Optional[str] = None


class ReclaimSpaceRequest(BaseModel):
    project: Optional[str] = None
    database: Optional[str] = None


class ReclaimSpaceResponse(BaseModel):
    success: bool
    message: str
    old_size_bytes: Optional[int] = None
    new_size_bytes: Optional[int] = None
    freed_bytes: Optional[int] = None
    freed_pretty: Optional[str] = None


class QueryAssistRequest(BaseModel):
    sql: str = Field(..., description="The SQL query to improve or fix.")
    project: Optional[str] = Field(None, description="Optional project name context.")
    database: Optional[str] = Field(None, description="Optional database path context.")


class QueryAssistResponse(BaseModel):
    sql: str


class QueryErrorAssistRequest(BaseModel):
    sql: str = Field(..., description="The SQL query that failed.")
    error: str = Field(..., description="The error message returned by the database.")
    project: Optional[str] = Field(None, description="Optional project name to target.")
    database: Optional[str] = Field(None, description="Explicit DuckDB file path to target.")


class QueryErrorAssistResponse(BaseModel):
    explanation: str
    fixed_sql: str


class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = ""
    timestamp: Optional[float] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatSession(BaseModel):
    id: str
    project: str
    created_at: float
    description: str
    messages: List[ChatMessage]


class ChatSessionSummary(BaseModel):
    id: str
    project: str
    created_at: float
    description: str
    message_count: int


class ChatHistorySaveRequest(BaseModel):
    project: str
    messages: List[ChatMessage]
    session_id: Optional[str] = None


__all__ = [
    "ProjectInfo",
    "ProjectUpdateRequest",
    "ProjectCreateRequest",
    "QueryRequest",
    "QueryResponse",
    "QueryRecord",
    "QuerySaveRequest",
    "ChatRequest",
    "ChatResponse",
    "SchemaResponse",
    "UndocumentedField",
    "FieldUpdateRequest",
    "FieldUpdateResponse",
    "TableUpdateRequest",
    "TableUpdateResponse",
    "AutoDescribeRequest",
    "AutoDescribeResponse",
    "AIAssistFieldRequest",
    "AIAssistFieldResponse",
    "DiagramTablePosition",
    "DiagramRecord",
    "DiagramSaveRequest",
    "DatalakeInfo",
    "DatalakeProjectInfo",
    "DatalakeAddRequest",
    "SyncDownloadRequest",
    "SyncUploadRequest",
    "SyncDownloadResponse",
    "SyncUploadResponse",
    "TableDeleteDataRequest",
    "TableStats",
    "DatabaseStatsResponse",
    "ReclaimSpaceRequest",
    "ReclaimSpaceResponse",
    "QueryAssistRequest",
    "QueryAssistResponse",
    "ChatMessage",
    "ChatSession",
    "ChatSessionSummary",
    "ChatHistorySaveRequest",
]
