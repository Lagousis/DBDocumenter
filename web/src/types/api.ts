export interface ProjectInfo {
  name: string;
  path: string;
  display_name: string;
  subdirectory?: string;
  description: string;
  is_active: boolean;
  version?: string;
  query_instructions?: string;
}

export interface ProjectUpdateRequest {
  path: string;
  display_name?: string;
  description?: string;
  version?: string;
  query_instructions?: string;
}

export interface ProjectCreateRequest {
  name: string;
  description?: string;
  query_instructions?: string;
}

export interface QueryResponse {
  columns: string[];
  rows: (string | number | boolean | null)[][];
  row_count: number;
  truncated: boolean;
  database?: string;
  project?: string;
  message?: string | null;
}

export interface QueryRecord {
  id: string;
  name: string;
  description?: string | null;
  sql: string;
  limit?: number | null;
  updated_at?: string | null;
}

export interface QuerySaveRequest {
  project?: string;
  database?: string;
  name: string;
  description?: string | null;
  sql: string;
  limit?: number;
  query_id?: string;
}

export interface RelationshipPayload {
  related_table: string;
  related_field: string;
  type?: string | null;
}

export interface FieldUpdateRequest {
  project?: string;
  database?: string;
  table: string;
  field: string;
  new_field_name?: string;
  short_description?: string | null;
  long_description?: string | null;
  nullability?: string | null;
  allow_null?: boolean | null;
  data_type?: string | null;
  values?: Record<string, string> | null;
  relationships?: RelationshipPayload[];
  ignored?: boolean;
}

export interface FieldUpdateResponse {
  table: string;
  field: string;
  metadata: Record<string, unknown>;
}

export interface TableUpdateRequest {
  project?: string;
  database?: string;
  table: string;
  short_description?: string | null;
  long_description?: string | null;
}

export interface TableUpdateResponse {
  table: string;
  metadata: Record<string, unknown>;
}

export interface AutoDescribeRequest {
  project?: string;
  database?: string;
  table: string;
  field: string;
  current_short_description?: string | null;
  current_long_description?: string | null;
  data_type?: string | null;
  description_type?: 'short' | 'long' | 'data_type';
}

export interface AutoDescribeResponse {
  description: string;
}

export interface AIAssistFieldRequest {
  project?: string;
  database?: string;
  table: string;
  field: string;
}

export interface AIAssistFieldResponse {
  short_description: string;
  long_description: string;
  data_type: string;
  nullable: boolean;
}

export interface QueryRequest {
  sql: string;
  project?: string;
  database?: string;
  limit?: number;
}

export interface ChatRequest {
  message: string;
  reset?: boolean;
  project?: string;
  database?: string;
  file_content?: string;
  filename?: string;
  session_id?: string;
  images?: Array<{ data: string; name: string }>;
}

export interface ChatResponse {
  reply: string;
  database?: string | null;
  session_id?: string;
  metadata?: {
    tools_used?: Array<{ name: string; arguments: any }>;
    total_tokens?: number;
    prompt_tokens?: number;
    completion_tokens?: number;
    api_calls?: number;
    execution_time_seconds?: number;
    iterations?: number;
    model?: string;
  };
}

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatSessionSummary {
  id: string;
  project: string;
  created_at: number;
  description: string;
  message_count: number;
}

export interface ChatSession {
  id: string;
  project: string;
  created_at: number;
  description: string;
  messages: ChatMessage[];
}

export interface ChatHistorySaveRequest {
  project: string;
  messages: ChatMessage[];
}

export interface SchemaResponse {
  schema: Record<string, unknown>;
}

export interface UndocumentedField {
  name: string;
  data_type?: string | null;
}

export interface DiagramTablePosition {
  name: string;
  x: number;
  y: number;
  width?: number;
}

export interface DiagramRecord {
  id: string;
  name: string;
  description?: string | null;
  tables: DiagramTablePosition[];
}

export interface DiagramSaveRequest {
  project?: string;
  database?: string;
  name: string;
  description?: string | null;
  tables: DiagramTablePosition[];
  diagram_id?: string;
}

// Datalake sync types
export interface DatalakeInfo {
  name: string;
  type: string;
  container_name: string;
  storage_account: string;
}

export interface DatalakeProjectInfo {
  name: string;
  version: string;
  display_name: string;
  description: string;
  last_modified: string;
  size_bytes: number;
  db_size_bytes: number;
  schema_size_bytes: number;
}

export interface DatalakeAddRequest {
  name: string;
  type: string;
  connection_string: string;
  container_name?: string;
}

export interface DatalakeTestConnectionRequest {
  type: string;
  connection_string: string;
}

export interface DatalakeTestConnectionResponse {
  success: boolean;
  message: string;
  containers: string[];
}

export interface SyncDownloadRequest {
  datalake_name: string;
  project_name: string;
  version: string;
  overwrite?: boolean;
  rename_existing?: boolean;
}

export interface SyncDownloadResponse {
  success: boolean;
  project_name: string;
  version: string;
  duckdb_path: string;
  schema_path: string;
  message?: string | null;
}

export interface SyncUploadRequest {
  datalake_name: string;
  project_path: string;
  new_version?: string | null;
  schema_only?: boolean;
}

export interface SyncUploadResponse {
  success: boolean;
  project_name: string;
  version: string;
  message?: string | null;
}

export interface TableDeleteDataRequest {
  project?: string;
  database?: string;
  table: string;
  mode: 'all' | 'subset' | 'filter';
  keep_count?: number;
  sort_column?: string;
  sort_order?: 'ASC' | 'DESC';
  filter_condition?: string;
}

export interface TableStats {
  name: string;
  row_count: number;
  size_bytes?: number | null;
  size_pretty: string;
}

export interface DatabaseStatsResponse {
  database_size_bytes: number;
  database_size_pretty: string;
  tables: TableStats[];
}

export interface ReclaimSpaceRequest {
  project?: string;
  database?: string;
}

export interface ReclaimSpaceResponse {
  success: boolean;
  message: string;
  original_size_bytes: number;
  new_size_bytes: number;
  reclaimed_bytes: number;
  reclaimed_pretty: string;
}

export interface QueryAssistRequest {
  sql: string;
  project?: string;
  database?: string;
}

export interface QueryAssistResponse {
  sql: string;
}

export interface QueryErrorAssistRequest {
  sql: string;
  error: string;
  project?: string;
  database?: string;
}

export interface QueryErrorAssistResponse {
  explanation: string;
  fixed_sql: string;
}
