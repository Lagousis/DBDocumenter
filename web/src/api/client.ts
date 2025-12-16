import axios from "axios";

import type {
    AIAssistFieldRequest,
    AIAssistFieldResponse,
    AutoDescribeRequest,
    AutoDescribeResponse,
    ChatHistorySaveRequest,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ChatSessionSummary,
    DatabaseStatsResponse,
    DatalakeAddRequest,
    DatalakeInfo,
    DatalakeProjectInfo,
    DatalakeTestConnectionRequest,
    DatalakeTestConnectionResponse,
    DiagramRecord,
    DiagramSaveRequest,
    FieldUpdateRequest,
    FieldUpdateResponse,
    ProjectCreateRequest,
    ProjectInfo,
    ProjectUpdateRequest,
    QueryAssistRequest,
    QueryAssistResponse,
    QueryErrorAssistRequest,
    QueryErrorAssistResponse,
    QueryRecord,
    QueryRequest,
    QueryResponse,
    QuerySaveRequest,
    ReclaimSpaceRequest,
    ReclaimSpaceResponse,
    SchemaResponse,
    SyncDownloadRequest,
    SyncDownloadResponse,
    SyncUploadRequest,
    SyncUploadResponse,
    TableDeleteDataRequest,
    TableUpdateRequest,
    TableUpdateResponse,
    UndocumentedField,
} from "../types/api";

const parsedTimeout = Number.parseInt(import.meta.env.VITE_API_TIMEOUT ?? "", 10);
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: Number.isFinite(parsedTimeout) && parsedTimeout > 0 ? parsedTimeout : 600000, // Increased default timeout to 600s (10m) to match backend resilience
});

export async function fetchProjects(): Promise<ProjectInfo[]> {
  const { data } = await api.get<ProjectInfo[]>("/projects");
  return data;
}

export async function updateProject(payload: ProjectUpdateRequest): Promise<ProjectInfo> {
  const { data } = await api.patch<ProjectInfo>("/projects", payload);
  return data;
}

export async function createProject(payload: ProjectCreateRequest): Promise<ProjectInfo> {
  const { data } = await api.post<ProjectInfo>("/projects", payload);
  return data;
}

export async function fetchSchema(params: { project?: string; database?: string } = {}): Promise<SchemaResponse> {
  const { data } = await api.get<SchemaResponse>("/schema", { params: { ...params, _t: Date.now() } });
  return data;
}

export async function fetchTables(params: { project?: string; database?: string } = {}): Promise<string[]> {
  const { data } = await api.get<string[]>("/schema/tables", { params: { ...params, _t: Date.now() } });
  return data;
}

export async function fetchDatabaseStats(params: { project?: string; database?: string } = {}): Promise<DatabaseStatsResponse> {
  const { data } = await api.get<DatabaseStatsResponse>("/schema/stats", { params: { ...params, _t: Date.now() } });
  return data;
}

export async function runQuery(payload: QueryRequest): Promise<QueryResponse> {
  const { data } = await api.post<QueryResponse>("/query", payload);
  return data;
}

export async function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/chat", payload);
  return data;
}

export async function sendChatStream(
  payload: ChatRequest,
  onChunk: (chunk: { 
    type: string; 
    message?: string; 
    reply?: string; 
    error?: string; 
    database?: string; 
    metadata?: ChatResponse['metadata'] 
  }) => void
): Promise<void> {
  const response = await fetch(`${api.defaults.baseURL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data.trim()) {
          try {
            const chunk = JSON.parse(data);
            onChunk(chunk);
          } catch (e) {
            console.error("Failed to parse SSE data:", e, data);
          }
        }
      }
    }
  }
}

export async function fetchChatHistory(project: string): Promise<ChatSessionSummary[]> {
  const { data } = await api.get<ChatSessionSummary[]>("/chat/history", { params: { project } });
  return data;
}

export async function fetchChatSession(sessionId: string, project: string): Promise<ChatSession> {
  const { data } = await api.get<ChatSession>(`/chat/history/${sessionId}`, { params: { project } });
  return data;
}

export async function saveChatSession(payload: ChatHistorySaveRequest): Promise<ChatSession> {
  const { data } = await api.post<ChatSession>("/chat/history", payload);
  return data;
}

export async function deleteChatSession(sessionId: string, project: string): Promise<void> {
  await api.delete(`/chat/history/${sessionId}`, { params: { project } });
}

export async function updateFieldMetadata(payload: FieldUpdateRequest): Promise<FieldUpdateResponse> {
  const { data } = await api.post<FieldUpdateResponse>("/schema/field/update", payload);
  return data;
}

export async function updateTableMetadata(payload: TableUpdateRequest): Promise<TableUpdateResponse> {
  const { data } = await api.post<TableUpdateResponse>("/schema/table/update", payload);
  return data;
}

export async function deleteTable(table: string, params: { project?: string; database?: string } = {}): Promise<void> {
  await api.delete(`/schema/table/${table}`, { params });
}

export async function deleteTableData(payload: TableDeleteDataRequest): Promise<void> {
  await api.post("/schema/table/delete-data", payload);
}

export async function autoDescribeField(payload: AutoDescribeRequest): Promise<AutoDescribeResponse> {
  const { data } = await api.post<AutoDescribeResponse>("/schema/field/describe", payload);
  return data;
}

export async function aiAssistField(payload: AIAssistFieldRequest): Promise<AIAssistFieldResponse> {
  const { data } = await api.post<AIAssistFieldResponse>("/schema/field/ai-assist", payload);
  return data;
}

export async function fetchUndocumentedFields(
  params: { table: string; project?: string; database?: string },
): Promise<UndocumentedField[]> {
  const { data } = await api.get<UndocumentedField[]>("/schema/fields/undocumented", { params: { ...params, _t: Date.now() } });
  return data;
}

export async function fetchDiagrams(params: { project?: string; database?: string } = {}): Promise<DiagramRecord[]> {
  const { data } = await api.get<DiagramRecord[]>("/diagrams", { params });
  return data;
}

export async function saveDiagram(payload: DiagramSaveRequest): Promise<DiagramRecord> {
  const { data } = await api.post<DiagramRecord>("/diagrams", payload);
  return data;
}

export async function deleteDiagram(diagramId: string, params: { project?: string; database?: string } = {}): Promise<void> {
  await api.delete(`/diagrams/${diagramId}`, { params });
}

export async function fetchQueries(params: { project?: string; database?: string } = {}): Promise<QueryRecord[]> {
  const { data } = await api.get<QueryRecord[]>("/queries", { params });
  return data;
}

export async function saveQuery(payload: QuerySaveRequest): Promise<QueryRecord> {
  const { data } = await api.post<QueryRecord>("/queries", payload);
  return data;
}

export async function deleteQuery(queryId: string, params: { project?: string; database?: string } = {}): Promise<void> {
  await api.delete(`/queries/${queryId}`, { params });
}

// Datalake sync API functions
export async function fetchDatalakes(): Promise<DatalakeInfo[]> {
  const { data } = await api.get<DatalakeInfo[]>("/datalakes");
  return data;
}

export async function fetchDatalakeProjects(datalakeName: string): Promise<DatalakeProjectInfo[]> {
  const { data } = await api.get<DatalakeProjectInfo[]>(`/datalakes/${datalakeName}/projects`);
  return data;
}

export async function downloadProject(payload: SyncDownloadRequest): Promise<SyncDownloadResponse> {
  const { data } = await api.post<SyncDownloadResponse>("/sync/download", payload);
  return data;
}

export async function uploadProject(payload: SyncUploadRequest): Promise<SyncUploadResponse> {
  const { data } = await api.post<SyncUploadResponse>("/sync/upload", payload);
  return data;
}

export async function testDatalakeConnection(
  payload: DatalakeTestConnectionRequest
): Promise<DatalakeTestConnectionResponse> {
  const { data } = await api.post<DatalakeTestConnectionResponse>("/datalakes/test", payload);
  return data;
}

export async function addDatalake(payload: DatalakeAddRequest): Promise<DatalakeInfo> {
  const { data } = await api.post<DatalakeInfo>("/datalakes", payload);
  return data;
}

export async function deleteDatalake(datalakeName: string): Promise<void> {
  await api.delete(`/datalakes/${datalakeName}`);
}

export async function deleteDatalakeProject(
  datalakeName: string,
  projectName: string,
  version: string
): Promise<void> {
  await api.delete(`/datalakes/${datalakeName}/projects/${projectName}/${version}`);
}

export async function reclaimSpace(payload: ReclaimSpaceRequest): Promise<ReclaimSpaceResponse> {
  const { data } = await api.post<ReclaimSpaceResponse>("/schema/reclaim-space", payload);
  return data;
}

export async function assistQuery(payload: QueryAssistRequest): Promise<QueryAssistResponse> {
  const { data } = await api.post<QueryAssistResponse>("/query/assist", payload);
  return data;
}

export async function assistQueryError(payload: QueryErrorAssistRequest): Promise<QueryErrorAssistResponse> {
  const { data } = await api.post<QueryErrorAssistResponse>("/query/assist-error", payload);
  return data;
}

export async function deleteField(
  table: string,
  field: string,
  params: { project?: string; database?: string } = {},
): Promise<void> {
  await api.delete(`/schema/field/${table}/${field}`, { params });
}

export async function fetchProjectDocumentation(projectName: string): Promise<{ markdown: string }> {
  const { data } = await api.get<{ markdown: string }>(`/projects/${encodeURIComponent(projectName)}/documentation`);
  return data;
}

export async function exportProjectLLM(projectName: string): Promise<any> {
  const { data } = await api.get<any>(`/projects/${encodeURIComponent(projectName)}/export/llm`);
  return data;
}
