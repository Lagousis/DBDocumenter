import { defineStore } from "pinia";

import {
    createProject as createProjectApi,
    deleteChatSession,
    deleteDiagram as deleteDiagramApi,
    deleteQuery as deleteQueryApi,
    fetchChatHistory,
    fetchChatSession,
    fetchDiagrams,
    fetchProjects,
    fetchQueries,
    fetchSchema,
    fetchTables,
    runQuery,
    saveChatSession,
    saveDiagram as saveDiagramApi,
    saveQuery as saveQueryApi,
    sendChatStream,
    updateProject
} from "../api/client";
import type {
    ChatResponse,
    ChatSessionSummary,
    DiagramRecord,
    DiagramTablePosition,
    ProjectInfo,
    QueryRecord,
    QueryResponse
} from "../types/api";

interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: number;
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

interface QueryTabState {
  id: string;
  type: "query";
  title: string;
  sql: string;
  limit: number;
  result: QueryResponse | null;
  errorMessage: string;
  loading: boolean;
  queryId?: string;
  queryDescription?: string;
  hasUnsavedChanges?: boolean;
  lastSavedSql?: string;
  lastSavedLimit?: number;
}

interface DiagramTabState {
  id: string;
  type: "diagram";
  title: string;
  primaryTable: string;
  tables: string[];
  selectedTables?: string[];
  layout?: Record<string, { x: number; y: number; width?: number }>;
  diagramId?: string;
  diagramDescription?: string;
  hasUnsavedChanges?: boolean;
}

interface MarkdownTabState {
  id: string;
  type: "markdown";
  title: string;
  content: string;
}

interface ChartTabState {
  id: string;
  type: "chart";
  title: string;
  chartType: "bar" | "horizontal-bar" | "line" | "pie" | "scatter" | "area";
  data: {
    labels: string[];
    datasets: Array<{
      label: string;
      data: number[];
      color?: string;
    }>;
  };
  xLabel: string;
  yLabel: string;
  sql?: string;
  plan?: string;
}

type WorkspaceTab = QueryTabState | DiagramTabState | MarkdownTabState | ChartTabState;

function normaliseQueryLimit(limit: number | null | undefined): number {
  if (typeof limit === "number" && Number.isFinite(limit) && limit > 0) {
    return Math.floor(limit);
  }
  return DEFAULT_QUERY_LIMIT;
}

function refreshQueryDirtyFlag(tab: QueryTabState): void {
  if (typeof tab.lastSavedSql === "undefined") {
    tab.lastSavedSql = tab.sql ?? "";
  }
  if (typeof tab.lastSavedLimit === "undefined") {
    tab.lastSavedLimit = typeof tab.limit === "number" ? tab.limit : DEFAULT_QUERY_LIMIT;
  }
  const baselineSql = tab.lastSavedSql ?? "";
  const baselineLimit = tab.lastSavedLimit ?? DEFAULT_QUERY_LIMIT;
  tab.hasUnsavedChanges = (tab.sql ?? "") !== baselineSql || (tab.limit ?? DEFAULT_QUERY_LIMIT) !== baselineLimit;
}

const DEFAULT_QUERY_LIMIT = Number(import.meta.env.VITE_DEFAULT_QUERY_LIMIT ?? 200);
const SQL_PLACEHOLDER = "SELECT 1;";
const STORAGE_SELECTED_TABLE_KEY = "schemaSelectedTable";
const STORAGE_CHAT_PANEL_KEY = "chatPanelCollapsed";
const STORAGE_CHAT_WIDTH_KEY = "chatPanelWidth";
const STORAGE_QUERY_EDITOR_HEIGHT_KEY = "queryEditorHeight";
const STORAGE_ACTIVE_PROJECT_KEY = "activeProject";

function makeId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function loadQueryEditorHeight(): number {
  if (typeof window === "undefined") {
    return 200;
  }
  const stored = window.localStorage.getItem(STORAGE_QUERY_EDITOR_HEIGHT_KEY);
  const parsed = stored ? Number.parseInt(stored, 10) : NaN;
  if (Number.isFinite(parsed) && parsed >= 100 && parsed <= 800) {
    return parsed;
  }
  return 200;
}

function loadSchemaWidth(): number {
  if (typeof window === "undefined") {
    return 280;
  }
  const stored = window.localStorage.getItem("schemaPanelWidth");
  const parsed = stored ? Number.parseInt(stored, 10) : NaN;
  if (Number.isFinite(parsed) && parsed >= 200 && parsed <= 500) {
    return parsed;
  }
  return 280;
}

function loadChatCollapsed(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.localStorage.getItem(STORAGE_CHAT_PANEL_KEY) === "true";
}

function loadChatWidth(): number {
  if (typeof window === "undefined") {
    return 320;
  }
  const stored = window.localStorage.getItem(STORAGE_CHAT_WIDTH_KEY);
  const parsed = stored ? Number.parseInt(stored, 10) : NaN;
  if (Number.isFinite(parsed) && parsed >= 240 && parsed <= 1200) {
    return parsed;
  }
  return 320;
}

export const useSessionStore = defineStore("session", {
  state: () => ({
    projects: [] as ProjectInfo[],
    activeProject: undefined as string | undefined,
    activeDatabase: undefined as string | undefined,
    schema: null as Record<string, unknown> | null,
    tables: [] as string[],
    chatHistory: [] as ChatEntry[],
    selectedTable: undefined as string | undefined,
    isSchemaCollapsed: false,
    isChatCollapsed: loadChatCollapsed(),
    schemaPanelWidth: loadSchemaWidth(),
    chatPanelWidth: loadChatWidth(),
    queryEditorHeight: loadQueryEditorHeight(),
    lastExpandedSchemaWidth: undefined as number | undefined,
    lastExpandedChatWidth: undefined as number | undefined,
    workspaceTabs: [] as WorkspaceTab[],
    activeWorkspaceTabId: undefined as string | undefined,
    queryTabCounter: 1,
    diagramTabCounter: 1,
    loadingProjects: false,
    loadingChat: false,
    errorMessage: "" as string,
    projectDialogOpen: false,
    projectDialogMode: "edit" as "edit" | "create",
    projectDialogInitialName: "",
    projectDialogInitialDescription: "",
    projectDialogInitialVersion: "",
    projectDialogInitialQueryInstructions: "",
    diagrams: [] as DiagramRecord[],
    diagramsLoading: false,
    diagramError: "",
    diagramSavePromptTabId: null as string | null,
    diagramCloseRequestTabId: null as string | null,
    queries: [] as QueryRecord[],
    queriesLoading: false,
    queryError: "",
    chatSessions: [] as ChatSessionSummary[],
    chatSessionsLoading: false,
    chatSessionsError: "",
    currentSessionId: undefined as string | undefined,
    draggedTable: null as string | null,
    chatAbortController: null as AbortController | null,
    chatStatusMessage: "Thinking..." as string,
  }),
  getters: {
    hasProjects(state): boolean {
      return state.projects.length > 0;
    },
    currentProjectLabel(state): string | undefined {
      return state.activeProject;
    },
    selectedTableDetails(state): { name: string; data: Record<string, any> } | null {
      if (!state.selectedTable) {
        return null;
      }

      const schemaTables = ((state.schema ?? {}) as Record<string, any>).tables as
        | Record<string, any>
        | undefined;
      const tables = schemaTables ?? {};
      const selectedLower = state.selectedTable.toLowerCase();
      const match = Object.keys(tables).find((name) => name.toLowerCase() === selectedLower);
      if (match) {
        return { name: match, data: tables[match] ?? {} };
      }

      const fallbackName =
        state.tables.find((table) => table.toLowerCase() === selectedLower) ?? state.selectedTable;

      return {
        name: fallbackName,
        data: {
          short_description: "",
          long_description: "",
          fields: {},
          relationships: [],
        },
      };
    },
    activeWorkspaceTab(state): WorkspaceTab | undefined {
      if (!state.activeWorkspaceTabId) {
        return undefined;
      }
      return state.workspaceTabs.find((tab) => tab.id === state.activeWorkspaceTabId);
    },
    activeProjectInfo(state): ProjectInfo | undefined {
      return state.projects.find((project) => project.name === state.activeProject);
    },
    activeProjectDisplayName(): string | undefined {
      return this.activeProjectInfo?.display_name ?? this.activeProjectInfo?.name;
    },
    activeProjectDescription(): string {
      return this.activeProjectInfo?.description ?? "";
    },
  },
  actions: {
    async initialize(): Promise<void> {
      await this.loadProjects();
      if (this.activeProject || this.activeDatabase) {
        await this.refreshMetadata();
      }
      this.ensureDefaultQueryTab();
    },
    async loadProjects(): Promise<void> {
      this.loadingProjects = true;
      this.errorMessage = "";
      try {
        const projects = await fetchProjects();
        this.projects = projects;
        
        // Try to restore the last selected project from localStorage
        let selectedProject: ProjectInfo | undefined;
        if (typeof window !== "undefined") {
          const storedProjectName = window.localStorage.getItem(STORAGE_ACTIVE_PROJECT_KEY);
          if (storedProjectName) {
            selectedProject = projects.find((item) => item.name === storedProjectName);
          }
        }
        
        // Fall back to the active project or first project if not found
        if (!selectedProject) {
          selectedProject = projects.find((item) => item.is_active) ?? projects[0];
        }
        
        this.activeProject = selectedProject?.name;
        this.activeDatabase = selectedProject?.path;
        this._synchroniseActiveProject(this.activeProject);
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : "Failed to load projects.";
        throw error;
      } finally {
        this.loadingProjects = false;
      }
    },
    openProjectDialog(mode: "edit" | "create"): void {
      this.projectDialogMode = mode;
      if (mode === "edit") {
        const info = this.activeProjectInfo;
        if (!info) {
          return;
        }
        this.projectDialogInitialName = info?.display_name ?? info?.name ?? "";
        this.projectDialogInitialDescription = info?.description ?? "";
        this.projectDialogInitialVersion = info?.version ?? "";
        this.projectDialogInitialQueryInstructions = info?.query_instructions ?? "";
      } else {
        this.projectDialogInitialName = "";
        this.projectDialogInitialDescription = "";
        this.projectDialogInitialVersion = "";
        this.projectDialogInitialQueryInstructions = "";
      }
      this.projectDialogOpen = true;
    },
    closeProjectDialog(): void {
      this.projectDialogOpen = false;
    },
    async selectProject(name: string | undefined): Promise<void> {
      // Reset workspace state
      this.workspaceTabs = [];
      this.activeWorkspaceTabId = undefined;
      this.queryTabCounter = 1;
      this.diagramTabCounter = 1;
      this.clearChatHistory();
      
      if (!name) {
        this.activeProject = undefined;
        this.activeDatabase = undefined;
        this.schema = null;
        this.tables = [];
        this.selectedTable = undefined;
        this.diagrams = [];
        this.diagramError = "";
        this.queries = [];
        this.queryError = "";
        this.queriesLoading = false;
        this.currentSessionId = undefined;
        this._synchroniseActiveProject(undefined);
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(STORAGE_SELECTED_TABLE_KEY);
          window.localStorage.removeItem(STORAGE_ACTIVE_PROJECT_KEY);
        }
        this.ensureDefaultQueryTab();
        return;
      }
      const match = this.projects.find((item) => item.name === name);
      if (!match) {
        throw new Error(`Project '${name}' was not found.`);
      }
      this.activeProject = match.name;
      this.activeDatabase = match.path;
      this.currentSessionId = undefined;
      this._synchroniseActiveProject(this.activeProject);
      
      // Persist the selected project to localStorage
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_ACTIVE_PROJECT_KEY, match.name);
        window.localStorage.removeItem(STORAGE_SELECTED_TABLE_KEY);
      }
      
      await this.refreshMetadata();
      this.ensureDefaultQueryTab();
    },
    async updateActiveProjectDetails(
      displayName: string,
      description: string,
      version: string,
      queryInstructions?: string,
    ): Promise<ProjectInfo> {
      const info = this.activeProjectInfo;
      if (!info) {
        throw new Error("No active project selected.");
      }
      const updated = await updateProject({
        path: info.path,
        display_name: displayName,
        description,
        version,
        query_instructions: queryInstructions,
      });
      this._applyProjectUpdate(updated);
      return updated;
    },
    async createProjectEntry(name: string, description: string, queryInstructions?: string): Promise<ProjectInfo> {
      const created = await createProjectApi({ name, description, query_instructions: queryInstructions });

      // Reset workspace state for the new project
      this.workspaceTabs = [];
      this.activeWorkspaceTabId = undefined;
      this.queryTabCounter = 1;
      this.diagramTabCounter = 1;
      this.clearChatHistory();

      this._applyProjectUpdate({ ...created, is_active: created.is_active });
      this.activeProject = created.name;
      this.activeDatabase = created.path;
      this._synchroniseActiveProject(this.activeProject);
      
      // Persist the newly created project to localStorage
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_ACTIVE_PROJECT_KEY, created.name);
      }
      
      await this.refreshMetadata();
      this.ensureDefaultQueryTab();
      return created;
    },
    _applyProjectUpdate(updated: ProjectInfo): void {
      const index = this.projects.findIndex((item) => item.path === updated.path);
      const merged: ProjectInfo = {
        name: updated.name,
        path: updated.path,
        display_name: updated.display_name,
        subdirectory: updated.subdirectory,
        description: updated.description,
        is_active: updated.is_active,
        version: updated.version,
        query_instructions: updated.query_instructions,
      };
      if (index !== -1) {
        this.projects.splice(index, 1, merged);
      } else {
        this.projects.push(merged);
      }
      if (this.activeProject === merged.name) {
        this.activeDatabase = merged.path;
      }
      if (this.schema && typeof this.schema === "object") {
        const schemaRecord = this.schema as Record<string, any>;
        schemaRecord.project_description = merged.description ?? "";
        if (merged.display_name) {
          schemaRecord.project_display_name = merged.display_name;
        }
      }
      this._synchroniseActiveProject(this.activeProject);
    },
    _synchroniseActiveProject(name: string | undefined): void {
      for (const project of this.projects) {
        project.is_active = Boolean(name && project.name === name);
      }
    },
    async refreshMetadata(): Promise<void> {
      if (!this.activeProject && !this.activeDatabase) {
        this.schema = null;
        this.tables = [];
        return;
      }
      const params = {
        project: this.activeProject,
        database: this.activeDatabase,
      };
      const [schemaResponse, tableList] = await Promise.all([
        fetchSchema(params),
        fetchTables(params),
      ]);
      this.schema = schemaResponse.schema;
      const schemaRecord = (schemaResponse.schema ?? {}) as Record<string, any>;
      const projectDescription = typeof schemaRecord.project_description === "string" ? schemaRecord.project_description : "";
      const projectDisplayNameRaw = schemaRecord.project_display_name ?? schemaRecord.project ?? null;
      const projectDisplayName =
        typeof projectDisplayNameRaw === "string" && projectDisplayNameRaw.trim()
          ? projectDisplayNameRaw
          : this.activeProjectDisplayName ?? this.activeProject ?? "";
      const queryInstructions = typeof schemaRecord.query_instructions === "string" ? schemaRecord.query_instructions : "";
      const info = this.activeProjectInfo;
      if (info) {
        this._applyProjectUpdate({
          ...info,
          display_name: projectDisplayName,
          description: projectDescription,
          query_instructions: queryInstructions,
          is_active: info.is_active,
        });
      }
      this.tables = tableList;
      if (this.tables.length === 0) {
        this.selectedTable = undefined;
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(STORAGE_SELECTED_TABLE_KEY);
        }
      } else if (
        this.selectedTable &&
        !this.tables.some((table) => table.toLowerCase() === this.selectedTable?.toLowerCase())
      ) {
        this.selectedTable = this.tables[0];
        if (typeof window !== "undefined") {
          window.localStorage.setItem(STORAGE_SELECTED_TABLE_KEY, this.selectedTable);
        }
      } else if (!this.selectedTable) {
        let stored: string | null = null;
        if (typeof window !== "undefined") {
          stored = window.localStorage.getItem(STORAGE_SELECTED_TABLE_KEY);
        }
        const matched =
          stored && this.tables.some((table) => table.toLowerCase() === stored!.toLowerCase())
            ? stored
            : this.tables[0];
        this.selectedTable = matched;
        if (typeof window !== "undefined" && matched) {
          window.localStorage.setItem(STORAGE_SELECTED_TABLE_KEY, matched);
        }
      }
      await this.loadDiagrams().catch(() => undefined);
      await this.loadQueries().catch(() => undefined);
    },
    async sendMessage(
      message: string, 
      file?: { name: string; content: string },
      images?: Array<{ data: string; name: string }>
    ): Promise<ChatResponse> {
      if (!message.trim() && !file && (!images || images.length === 0)) {
        throw new Error("Message, file, or image is required.");
      }
      const userEntry: ChatEntry = {
        id: makeId(),
        role: "user",
        text: message,
        timestamp: Date.now(),
      };
      this.chatHistory.push(userEntry);
      
      // Add a placeholder assistant message that will be updated
      const assistantEntry: ChatEntry = {
        id: makeId(),
        role: "assistant",
        text: "",
        timestamp: Date.now(),
      };
      this.chatHistory.push(assistantEntry);
      
      this.loadingChat = true;
      
      // Create abort controller for this request
      this.chatAbortController = new AbortController();
      
      try {
        let finalResponse: ChatResponse = { reply: "", database: undefined };
        
        await sendChatStream(
          {
            message,
            project: this.activeProject,
            database: this.activeDatabase,
            file_content: file?.content,
            filename: file?.name,
            session_id: this.currentSessionId,
            images,
          },
          (chunk: { 
            type: string; 
            message?: string; 
            reply?: string; 
            error?: string; 
            database?: string; 
            metadata?: ChatResponse['metadata'];
            session_id?: string;
          }) => {
            if (chunk.type === "status" && chunk.message) {
              // Update the assistant message with status
              assistantEntry.text = chunk.message;
              this.chatStatusMessage = chunk.message;
            } else if (chunk.type === "response" && chunk.reply) {
              // Update with the actual response
              assistantEntry.text = chunk.reply;
              finalResponse.reply = chunk.reply;
              finalResponse.database = chunk.database;
              if (chunk.session_id) {
                this.currentSessionId = chunk.session_id;
                finalResponse.session_id = chunk.session_id;
              }
              // Store execution metadata
              if (chunk.metadata) {
                assistantEntry.metadata = chunk.metadata;

                // Check if schema was updated and refresh if needed
                if (chunk.metadata.tools_used) {
                  const hasSchemaUpdate = chunk.metadata.tools_used.some((tool: any) => 
                    tool.name === "duckdb_schema" && 
                    ["update_field", "update_table", "update_fields_batch", "update_field_description"].includes(tool.arguments?.action)
                  );
                  
                  if (hasSchemaUpdate) {
                    this.refreshMetadata();
                  }
                }
              }
            } else if (chunk.type === "error" && chunk.error) {
              // Show error
              assistantEntry.text = `Error: ${chunk.error}`;
              throw new Error(chunk.error);
            } else if (chunk.type === "done") {
              // Final database update
              if (chunk.database) {
                this.activeDatabase = chunk.database;
              }
              if (chunk.session_id) {
                this.currentSessionId = chunk.session_id;
              }
            }
          },
          this.chatAbortController.signal
        );
        
        return finalResponse;
      } catch (error) {
        // Check if this is an abort error (user cancelled)
        if (error instanceof Error && (error.name === 'AbortError' || error.message.includes('aborted'))) {
          // User cancelled - update the assistant message instead of removing it
          assistantEntry.text = "Operation cancelled by user.";
          return { reply: "Operation cancelled by user.", database: undefined };
        }
        
        // Remove the assistant message on other errors
        const index = this.chatHistory.indexOf(assistantEntry);
        if (index > -1) {
          this.chatHistory.splice(index, 1);
        }
        throw error;
      } finally {
        this.loadingChat = false;
        this.chatAbortController = null;
        this.chatStatusMessage = "Thinking...";
      }
    },
    stopChat(): void {
      if (this.chatAbortController) {
        this.chatAbortController.abort();
        this.chatAbortController = null;
        this.loadingChat = false;
      }
    },
    clearChatHistory(): void {
      this.chatHistory = [];
      this.currentSessionId = undefined;
    },
    async loadChatHistory(): Promise<void> {
        if (!this.activeProject) return;
        this.chatSessionsLoading = true;
        this.chatSessionsError = "";
        try {
            this.chatSessions = await fetchChatHistory(this.activeProject);
        } catch (error) {
            this.chatSessionsError = error instanceof Error ? error.message : "Failed to load chat history";
        } finally {
            this.chatSessionsLoading = false;
        }
    },
    async loadChatSession(sessionId: string): Promise<void> {
        if (!this.activeProject) return;
        try {
            const session = await fetchChatSession(sessionId, this.activeProject);
            // Convert ChatMessage[] to ChatEntry[]
            this.chatHistory = session.messages
                .filter(msg => msg.role === "user" || msg.role === "assistant")
                .map(msg => ({
                    id: makeId(),
                    role: msg.role as "user" | "assistant",
                    text: msg.content,
                    timestamp: msg.timestamp ? msg.timestamp * 1000 : Date.now(), // Convert from seconds to milliseconds
                }));
            this.currentSessionId = sessionId;
        } catch (error) {
            console.error("Failed to load chat session", error);
            throw error;
        }
    },
    async saveCurrentChatSession(): Promise<void> {
        if (!this.activeProject || this.chatHistory.length === 0) return;
        
        const messages = this.chatHistory.map(entry => ({
            role: entry.role,
            content: entry.text
        }));
        
        try {
            await saveChatSession({
                project: this.activeProject,
                messages
            });
            await this.loadChatHistory(); // Refresh list
        } catch (error) {
            console.error("Failed to save chat session", error);
            throw error;
        }
    },
    async deleteChatSession(sessionId: string): Promise<void> {
        if (!this.activeProject) return;
        try {
            await deleteChatSession(sessionId, this.activeProject);
            this.chatSessions = this.chatSessions.filter(s => s.id !== sessionId);
        } catch (error) {
            console.error("Failed to delete chat session", error);
            throw error;
        }
    },
    async loadDiagrams(): Promise<void> {
      if (!this.activeProject && !this.activeDatabase) {
        this.diagrams = [];
        this.diagramError = "";
        return;
      }
      this.diagramsLoading = true;
      this.diagramError = "";
      try {
        const records = await fetchDiagrams({
          project: this.activeProject,
          database: this.activeDatabase,
        });
        this.diagrams = records;
      } catch (error) {
        this.diagramError = error instanceof Error ? error.message : "Unable to load diagrams.";
        throw error;
      } finally {
        this.diagramsLoading = false;
      }
    },
    async loadQueries(): Promise<void> {
      if (!this.activeProject && !this.activeDatabase) {
        this.queries = [];
        this.queryError = "";
        return;
      }
      this.queriesLoading = true;
      this.queryError = "";
      try {
        const records = await fetchQueries({
          project: this.activeProject,
          database: this.activeDatabase,
        });
        this.queries = records;
      } catch (error) {
        this.queryError = error instanceof Error ? error.message : "Unable to load queries.";
        throw error;
      } finally {
        this.queriesLoading = false;
      }
    },
    async saveDiagramLayout(payload: {
      name: string;
      description: string;
      tables: DiagramTablePosition[];
      diagramId?: string | null;
    }): Promise<DiagramRecord> {
      if (!payload.tables.length) {
        throw new Error("Add at least one table to save a diagram.");
      }
      if (!this.activeProject && !this.activeDatabase) {
        throw new Error("Select a project before saving a diagram.");
      }
      const record = await saveDiagramApi({
        name: payload.name,
        description: payload.description,
        tables: payload.tables,
        project: this.activeProject,
        database: this.activeDatabase,
        diagram_id: payload.diagramId ?? undefined,
      });
      const filtered = this.diagrams.filter((diagram) => diagram.id !== record.id);
      this.diagrams = [record, ...filtered];
      return record;
    },
    async deleteDiagramRecord(id: string): Promise<void> {
      if (!this.activeProject && !this.activeDatabase) {
        throw new Error("Select a project before deleting diagrams.");
      }
      await deleteDiagramApi(id, { project: this.activeProject, database: this.activeDatabase });
      this.diagrams = this.diagrams.filter((diagram) => diagram.id !== id);
    },
    async saveQueryForTab(
      tabId: string,
      payload: { name: string; description: string; queryId?: string | null },
    ): Promise<QueryRecord> {
      const tab = this.workspaceTabs.find(
        (item): item is QueryTabState => item.id === tabId && item.type === "query",
      );
      if (!tab) {
        throw new Error("Query tab not found.");
      }
      const sqlText = tab.sql ?? "";
      if (!sqlText.trim()) {
        throw new Error("Provide a SQL query before saving.");
      }
      if (!this.activeProject && !this.activeDatabase) {
        throw new Error("Select a project before saving a query.");
      }
      const targetQueryId = payload.queryId === null
        ? undefined
        : payload.queryId ?? tab.queryId ?? undefined;

      const record = await saveQueryApi({
        name: payload.name,
        description: payload.description,
        sql: tab.sql,
        limit: tab.limit,
        project: this.activeProject,
        database: this.activeDatabase,
        query_id: targetQueryId,
      });
      const filtered = this.queries.filter((query) => query.id !== record.id);
      this.queries = [record, ...filtered];
      tab.queryId = record.id;
      tab.queryDescription = record.description ?? "";
      tab.title = record.name || tab.title;
      tab.lastSavedSql = tab.sql;
      tab.lastSavedLimit = tab.limit;
      refreshQueryDirtyFlag(tab);
      return record;
    },
    async deleteQueryRecord(id: string): Promise<void> {
      if (!this.activeProject && !this.activeDatabase) {
        throw new Error("Select a project before deleting queries.");
      }
      await deleteQueryApi(id, { project: this.activeProject, database: this.activeDatabase });
      this.queries = this.queries.filter((query) => query.id !== id);
    },
    async updateQueryRecord(id: string, name: string, description: string): Promise<QueryRecord> {
      if (!this.activeProject && !this.activeDatabase) {
        throw new Error("Select a project before updating a query.");
      }
      const existing = this.queries.find((q) => q.id === id);
      if (!existing) {
        throw new Error("Query not found.");
      }
      
      const record = await saveQueryApi({
        name,
        description,
        sql: existing.sql,
        limit: existing.limit ?? undefined,
        project: this.activeProject,
        database: this.activeDatabase,
        query_id: id,
      });
      
      const filtered = this.queries.filter((query) => query.id !== record.id);
      this.queries = [record, ...filtered];
      
      // Also update any open tabs that reference this query
      for (const tab of this.workspaceTabs) {
        if (tab.type === "query" && tab.queryId === id) {
          tab.title = record.name;
          tab.queryDescription = record.description ?? "";
        }
      }
      
      return record;
    },
    openQueryFromSaved(id: string): string | undefined {
      const record = this.queries.find((query) => query.id === id);
      if (!record) {
        return undefined;
      }
      const initialSql = record.sql || SQL_PLACEHOLDER;
      const handlerLimit = normaliseQueryLimit(record.limit ?? undefined);
      return this.createQueryTab({
        sql: initialSql,
        title: record.name || `Query ${this.queryTabCounter}`,
        makeActive: true,
        queryId: record.id,
        description: record.description ?? "",
        limit: handlerLimit,
      });
    },
    openDiagramFromSaved(id: string): string | undefined {
      const record = this.diagrams.find((diagram) => diagram.id === id);
      if (!record) {
        return undefined;
      }
      const tables = record.tables
        .map((entry) => entry.name?.trim())
        .filter((name): name is string => Boolean(name));
      if (!tables.length) {
        return undefined;
      }
      const layout: Record<string, { x: number; y: number; width?: number }> = {};
      for (const entry of record.tables) {
        const trimmed = entry.name?.trim();
        if (!trimmed) {
          continue;
        }
        layout[trimmed] = { x: entry.x, y: entry.y, width: entry.width };
      }
      return this.createDiagramTab({
        tables,
        primaryTable: tables[0],
        title: record.name || `Diagram: ${tables[0]}`,
        makeActive: true,
        layout,
        diagramId: record.id,
        diagramDescription: record.description ?? "",
      });
    },
    selectTable(name: string | undefined): void {
      if (!name) {
        this.selectedTable = undefined;
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(STORAGE_SELECTED_TABLE_KEY);
        }
        return;
      }
      this.selectedTable = name;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_SELECTED_TABLE_KEY, name);
      }
    },
    setSelectedTable(name: string | null): void {
      if (!name) {
        this.selectedTable = undefined;
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(STORAGE_SELECTED_TABLE_KEY);
        }
        return;
      }
      this.selectedTable = name;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_SELECTED_TABLE_KEY, name);
      }
    },
    toggleSchemaPanel(): void {
      this.isSchemaCollapsed = !this.isSchemaCollapsed;
      if (this.isSchemaCollapsed) {
        this.lastExpandedSchemaWidth = this.schemaPanelWidth;
      } else if (this.lastExpandedSchemaWidth) {
        this.schemaPanelWidth = this.lastExpandedSchemaWidth;
      }
    },
    toggleChatPanel(): void {
      this.setChatPanel(!this.isChatCollapsed);
    },
    setChatPanel(collapsed: boolean): void {
      if (collapsed) {
        this.lastExpandedChatWidth = this.chatPanelWidth;
      } else if (this.lastExpandedChatWidth) {
        this.chatPanelWidth = this.lastExpandedChatWidth;
      }
      this.isChatCollapsed = collapsed;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_CHAT_PANEL_KEY, String(collapsed));
      }
    },
    setSchemaPanel(collapsed: boolean): void {
      this.isSchemaCollapsed = collapsed;
      if (collapsed) {
        this.lastExpandedSchemaWidth = this.schemaPanelWidth;
      }
    },
    setSchemaPanelWidth(width: number): void {
      const clamped = Math.min(Math.max(width, 220), 500);
      this.schemaPanelWidth = clamped;
      if (typeof window !== "undefined") {
        window.localStorage.setItem("schemaPanelWidth", String(clamped));
      }
    },
    setChatPanelWidth(width: number): void {
      const clamped = Math.min(Math.max(width, 240), 1200);
      this.chatPanelWidth = clamped;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_CHAT_WIDTH_KEY, String(clamped));
      }
    },
    setQueryEditorHeight(height: number) {
      this.queryEditorHeight = height;
      window.localStorage.setItem(STORAGE_QUERY_EDITOR_HEIGHT_KEY, String(height));
    },
    ensureDefaultQueryTab(): void {
      if (this.workspaceTabs.length === 0) {
        this.createQueryTab({ makeActive: true });
      }
    },
    setActiveWorkspaceTab(id: string | undefined): void {
      if (!id) {
        this.activeWorkspaceTabId = undefined;
        return;
      }
      const exists = this.workspaceTabs.some((tab) => tab.id === id);
      if (exists) {
        this.activeWorkspaceTabId = id;
      }
    },
    createQueryTab(
      payload: { sql?: string; title?: string; makeActive?: boolean; queryId?: string; description?: string; limit?: number } = {},
    ): string {
      const id = makeId();
      const counter = this.queryTabCounter++;
      const title = payload.title ?? `SQL ${counter}`;
      const initialSql = payload.sql ?? SQL_PLACEHOLDER;
      const normalizedLimit = normaliseQueryLimit(payload.limit ?? undefined);
      const tab: QueryTabState = {
        id,
        type: "query",
        title,
        sql: initialSql,
        limit: normalizedLimit,
        result: null,
        errorMessage: "",
        loading: false,
        queryId: payload.queryId,
        queryDescription: payload.description ?? "",
        hasUnsavedChanges: false,
        lastSavedSql: initialSql,
        lastSavedLimit: normalizedLimit,
      };
      refreshQueryDirtyFlag(tab);
      this.workspaceTabs.push(tab);
      if (payload.makeActive !== false) {
        this.activeWorkspaceTabId = id;
      }
      return id;
    },
    createMarkdownTab(
      payload: { content: string; title?: string; makeActive?: boolean } = { content: "" },
    ): string {
      const id = makeId();
      const title = payload.title ?? "Implementation Plan";
      const tab: MarkdownTabState = {
        id,
        type: "markdown",
        title,
        content: payload.content,
      };
      this.workspaceTabs.push(tab);
      if (payload.makeActive !== false) {
        this.activeWorkspaceTabId = id;
      }
      return id;
    },
    createChartTab(
      payload: {
        chartType: "bar" | "horizontal-bar" | "line" | "pie" | "scatter" | "area";
        data: {
          labels: string[];
          datasets: Array<{
            label: string;
            data: number[];
            color?: string;
          }>;
        };
        title?: string;
        xLabel?: string;
        yLabel?: string;
        sql?: string;
        plan?: string;
        makeActive?: boolean;
      }
    ): string {
      const id = makeId();
      const title = payload.title ?? "Chart";
      const tab: ChartTabState = {
        id,
        type: "chart",
        title,
        chartType: payload.chartType,
        data: payload.data,
        xLabel: payload.xLabel ?? "",
        yLabel: payload.yLabel ?? "",
        sql: payload.sql,
        plan: payload.plan,
      };
      this.workspaceTabs.push(tab);
      if (payload.makeActive !== false) {
        this.activeWorkspaceTabId = id;
      }
      return id;
    },
    updateQueryTabSql(id: string, sql: string): void {
      const tab = this.workspaceTabs.find((item): item is QueryTabState => item.id === id && item.type === "query");
      if (tab) {
        tab.sql = sql;
        refreshQueryDirtyFlag(tab);
      }
    },
    updateQueryTabLimit(id: string, limit: number): void {
      const tab = this.workspaceTabs.find((item): item is QueryTabState => item.id === id && item.type === "query");
      if (tab) {
        const normalized = normaliseQueryLimit(limit);
        tab.limit = normalized;
        refreshQueryDirtyFlag(tab);
      }
    },
    async runQueryForTab(id: string, overrideSql?: string): Promise<QueryResponse> {
      const tab = this.workspaceTabs.find((item): item is QueryTabState => item.id === id && item.type === "query");
      if (!tab) {
        throw new Error(`Query tab '${id}' not found.`);
      }
      const sql = overrideSql ?? tab.sql ?? "";
      if (!sql.trim()) {
        tab.errorMessage = "Provide a SQL query before executing.";
        throw new Error(tab.errorMessage);
      }
      tab.errorMessage = "";
      tab.loading = true;
      try {
        const result = await runQuery({
          sql,
          project: this.activeProject,
          database: this.activeDatabase,
          limit: tab.limit ?? DEFAULT_QUERY_LIMIT,
        });
        tab.result = result;
        if (result.project) {
          this.activeProject = result.project;
        }
        if (result.database) {
          this.activeDatabase = result.database;
        }
        return result;
      } catch (error: any) {
        tab.result = null;
        if (error.response?.data?.detail) {
          tab.errorMessage = error.response.data.detail;
        } else {
          tab.errorMessage = error instanceof Error ? error.message : "Query failed.";
        }
        throw error;
      } finally {
        tab.loading = false;
      }
    },
    createDiagramTab(payload: {
      tables: string[];
      primaryTable?: string;
      title?: string;
      makeActive?: boolean;
      layout?: Record<string, { x: number; y: number }>;
      diagramId?: string;
      diagramDescription?: string;
    }): string {
      const tables = (payload.tables ?? []).filter((name) => Boolean(name));
      if (!tables.length) {
        throw new Error("Diagram tab requires at least one table.");
      }
      const id = makeId();
      const counter = this.diagramTabCounter++;
      const primary = payload.primaryTable ?? tables[0];
      const title = payload.title ?? `Diagram ${counter}: ${primary}`;
      const tab: DiagramTabState = {
        id,
        type: "diagram",
        title,
        primaryTable: primary,
        tables,
        selectedTables: [...tables],
        layout: payload.layout ? { ...payload.layout } : undefined,
        diagramId: payload.diagramId,
        diagramDescription: payload.diagramDescription,
        hasUnsavedChanges: false,
      };
      this.workspaceTabs.push(tab);
      if (payload.makeActive !== false) {
        this.activeWorkspaceTabId = id;
      }
      return id;
    },
    markDiagramDirty(tabId: string, dirty: boolean): void {
      const tab = this.workspaceTabs.find(
        (candidate): candidate is DiagramTabState => candidate.type === "diagram" && candidate.id === tabId,
      );
      if (!tab) {
        return;
      }
      tab.hasUnsavedChanges = dirty;
    },
    updateDiagramMetadata(tabId: string, title: string, description: string): void {
      const tab = this.workspaceTabs.find(
        (candidate): candidate is DiagramTabState => candidate.type === "diagram" && candidate.id === tabId,
      );
      if (!tab) {
        return;
      }
      tab.title = title;
      tab.diagramDescription = description;
      tab.hasUnsavedChanges = true;
    },
    requestDiagramSave(tabId: string, closeAfter = false): void {
      this.diagramSavePromptTabId = tabId;
      if (closeAfter) {
        this.diagramCloseRequestTabId = tabId;
      }
      this.setActiveWorkspaceTab(tabId);
    },
    clearDiagramSavePrompt(tabId?: string | null): void {
      if (!tabId || this.diagramSavePromptTabId === tabId) {
        this.diagramSavePromptTabId = null;
      }
      if (!tabId || this.diagramCloseRequestTabId === tabId) {
        this.diagramCloseRequestTabId = null;
      }
    },
    createDiagramTabForTable(tableName: string | undefined): string | undefined {
      if (!tableName) {
        return undefined;
      }
      const schemaTables = ((this.schema ?? {}) as Record<string, any>).tables as
        | Record<string, any>
        | undefined;
      const entries = Object.entries(schemaTables ?? {});
      const targetLower = tableName.toLowerCase();
      const match = entries.find(([name]) => name.toLowerCase() === targetLower);
      const resolvedName = match ? match[0] : tableName;
      const related = new Set<string>([resolvedName]);

      const baseRecord = match ? (match[1] as Record<string, any>) : undefined;
      const baseRelationships = (baseRecord?.relationships ?? []) as Array<Record<string, any>>;

      const resolveName = (candidate: string | undefined): string | undefined => {
        if (!candidate) {
          return undefined;
        }
        const lowered = candidate.toLowerCase();
        const matched = entries.find(([name]) => name.toLowerCase() === lowered);
        return matched ? matched[0] : candidate;
      };

      for (const rel of baseRelationships) {
        const relatedTable = resolveName(rel.related_table);
        if (relatedTable) {
          related.add(relatedTable);
        }
      }

      for (const [table, data] of entries) {
        const relationships = (data.relationships ?? []) as Array<Record<string, any>>;
        for (const rel of relationships) {
          const relatedTable = (rel.related_table ?? "").toString().toLowerCase();
          if (relatedTable && relatedTable === resolvedName.toLowerCase()) {
            related.add(table);
          }
        }
      }

      const tables = Array.from(related);
      if (!tables.length) {
        return undefined;
      }
      return this.createDiagramTab({
        tables,
        primaryTable: resolvedName,
        title: `Diagram: ${resolvedName}`,
        makeActive: true,
      });
    },
    addTableToDiagram(tabId: string, tableName: string | undefined): boolean {
      if (!tableName) {
        return false;
      }
      const tab = this.workspaceTabs.find(
        (candidate): candidate is DiagramTabState => candidate.type === "diagram" && candidate.id === tabId,
      );
      if (!tab) {
        return false;
      }
      const lowered = tableName.toLowerCase();
      if (tab.tables.some((name) => name.toLowerCase() === lowered)) {
        return false;
      }
      const selection = tab.selectedTables ?? tab.tables;
      tab.tables = [...tab.tables, tableName];
      tab.selectedTables = Array.from(new Set([...selection, tableName]));
      tab.hasUnsavedChanges = true;
      return true;
    },
    removeTableFromDiagram(tabId: string, tableName: string): void {
      const tab = this.workspaceTabs.find(
        (candidate): candidate is DiagramTabState => candidate.type === "diagram" && candidate.id === tabId,
      );
      if (!tab) {
        return;
      }
      const lowered = tableName.toLowerCase();
      tab.tables = tab.tables.filter((name) => name.toLowerCase() !== lowered);
      tab.selectedTables = (tab.selectedTables ?? tab.tables).filter((name) => name.toLowerCase() !== lowered);
      if (tab.layout) {
        const matchKey = Object.keys(tab.layout).find((key) => key.toLowerCase() === lowered);
        if (matchKey) {
          delete tab.layout[matchKey];
          if (Object.keys(tab.layout).length === 0) {
            tab.layout = undefined;
          }
        }
      }
      if (tab.primaryTable.toLowerCase() === lowered) {
        tab.primaryTable = tab.tables[0] ?? "";
      }
      tab.hasUnsavedChanges = true;
      if (!tab.tables.length) {
        this.closeWorkspaceTab(tabId);
      }
    },
    selectDiagramTable(tabId: string, tableName: string): void {
      const tab = this.workspaceTabs.find(
        (candidate): candidate is DiagramTabState => candidate.type === "diagram" && candidate.id === tabId,
      );
      if (!tab) {
        return;
      }
      tab.selectedTables = Array.from(new Set([tableName, ...(tab.selectedTables ?? [])]));
      this.setSelectedTable(tableName);
    },
    openMarkdownTab(title: string, content: string): void {
      const id = `markdown-${Date.now()}`;
      this.workspaceTabs.push({
        id,
        type: "markdown",
        title,
        content,
      });
      this.activeWorkspaceTabId = id;
    },
    closeWorkspaceTab(id: string): void {
      const index = this.workspaceTabs.findIndex((tab) => tab.id === id);
      if (index === -1) {
        return;
      }
      const tab = this.workspaceTabs[index];
      if (
        tab &&
        tab.type === "diagram" &&
        tab.hasUnsavedChanges &&
        typeof window !== "undefined" &&
        !this.diagramCloseRequestTabId
      ) {
        const continueClosing = window.confirm(
          "This diagram has unsaved changes. Press OK to close without saving, or Cancel to keep editing.",
        );
        if (!continueClosing) {
          return;
        }
      } else if (tab && tab.type === "query" && tab.hasUnsavedChanges && typeof window !== "undefined") {
        const continueClosing = window.confirm(
          "This query has unsaved changes. Press OK to close without saving, or Cancel to keep editing.",
        );
        if (!continueClosing) {
          return;
        }
      }
      const wasActive = this.activeWorkspaceTabId === id;
      this.workspaceTabs.splice(index, 1);
      if (this.workspaceTabs.length === 0) {
        this.activeWorkspaceTabId = undefined;
        this.ensureDefaultQueryTab();
        return;
      }
      if (wasActive) {
        const next = this.workspaceTabs[index] ?? this.workspaceTabs[index - 1] ?? this.workspaceTabs[0];
        this.activeWorkspaceTabId = next?.id;
      }
    },
    updateDiagramLayout(tabId: string, tableName: string, position: { x: number; y: number; width?: number }): void {
      const tab = this.workspaceTabs.find(
        (item): item is DiagramTabState => item.id === tabId && item.type === "diagram",
      );
      if (tab) {
        if (!tab.layout) {
          tab.layout = {};
        }
        tab.layout[tableName] = position;
      }
    },
    updateQueryTab(id: string, updates: Partial<QueryTabState>): void {
      const tab = this.workspaceTabs.find((item): item is QueryTabState => item.id === id && item.type === "query");
      if (tab) {
        Object.assign(tab, updates);
        refreshQueryDirtyFlag(tab);
      }
    },
  },
});

export type { ChartTabState, DiagramTabState, MarkdownTabState, QueryTabState, WorkspaceTab };

