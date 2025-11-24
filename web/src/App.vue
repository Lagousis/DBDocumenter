<template>
  <div class="app-shell">
    <header>
      <div class="header-left">
        <button type="button" class="sidebar-toggle" @click="toggleSchemaPanel" aria-label="Toggle schema panel">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">
            <rect x="3.5" y="4.5" width="13" height="11" rx="1.5"></rect>
            <line x1="7.5" y1="4.5" x2="7.5" y2="15.5"></line>
          </svg>
        </button>
        <div class="brand">
          <span class="brand-icon">✻</span>
          <h1>DBDocumenter</h1>
        </div>
      </div>
      <div class="project-picker">
        <label class="project-label" for="project-select">Project</label>
        <div class="project-picker__field">
          <div class="project-select">
            <select
              id="project-select"
              :value="activeProject ?? ''"
              @change="handleProjectChange"
            >
              <option value="" disabled>Select a project</option>
              <option v-for="project in projects" :key="project.name" :value="project.name">
                {{ project.subdirectory ? `${project.subdirectory}/` : '' }}{{ project.display_name || project.name }}{{ project.version ? ` (v${project.version})` : '' }}
              </option>
            </select>
            <svg class="project-select__icon" width="12" height="8" viewBox="0 0 12 8" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10.5 1.5L6 6 1.5 1.5" stroke="#9A6432" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
          <button
            type="button"
            class="sidebar-toggle project-edit-toggle"
            :title="activeProjectInfo ? 'Edit project details' : 'Select a project to edit details'"
            :disabled="!activeProjectInfo"
            @click="openProjectEditor"
            aria-label="Edit project details"
          >
            <span aria-hidden="true">&#9998;</span>
            <span class="sr-only">Edit project details</span>
          </button>
        </div>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="sidebar-toggle sync-toggle"
          title="Sync with datalakes"
          aria-label="Open sync dialog"
          @click="openSyncDialog"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M14 6.5c-.4-1.8-2-3.2-3.9-3.2-1.5 0-2.8.8-3.5 2M4 11.5c.4 1.8 2 3.2 3.9 3.2 1.5 0 2.8-.8 3.5-2" />
            <path d="M14 3v3.5h-3.5" />
            <path d="M4 15v-3.5h3.5" />
          </svg>
        </button>
        <button
          type="button"
          class="sidebar-toggle diagrams-toggle"
          title="Browse saved diagrams"
          aria-label="Open saved diagram library"
          @click="openDiagramLibrary"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6">
            <rect x="2.5" y="4" width="9" height="9" rx="1.2" />
            <rect x="6.5" y="7" width="9" height="9" rx="1.2" />
            <path d="M5 1.5h3" />
            <path d="M1.5 5v3" />
          </svg>
        </button>
        <button
          type="button"
          class="sidebar-toggle queries-toggle"
          title="Browse saved queries"
          aria-label="Open saved query library"
          @click="openQueryLibrary"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M3 4.5h12" />
            <path d="M3 9h12" />
            <path d="M3 13.5h12" />
            <circle cx="5" cy="4.5" r="0.8" />
            <circle cx="5" cy="9" r="0.8" />
            <circle cx="5" cy="13.5" r="0.8" />
          </svg>
        </button>
        <button
          type="button"
          class="sidebar-toggle new-sql-toggle"
          title="New SQL tab"
          aria-label="Create new SQL tab"
          @click="createSqlTab"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M9 3v12" />
            <path d="M3 9h12" />
          </svg>
        </button>
        <button
          type="button"
          class="sidebar-toggle chat-toggle"
          :aria-pressed="!isChatCollapsed"
          :title="isChatCollapsed ? 'Show chat panel' : 'Hide chat panel'"
          @click="toggleChatPanel"
          aria-label="Toggle chat panel"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">
            <rect x="3" y="3.5" width="14" height="10" rx="2" />
            <path d="M7 15.5l3-2 3 2" />
          </svg>
        </button>
      </div>
    </header>
    <main class="main-flex">
      <aside
        v-show="!isSchemaCollapsed"
        class="schema-pane"
        :style="{ width: `${schemaPanelWidth}px` }"
      >
        <SchemaSidebar />
      </aside>
      <div v-show="!isSchemaCollapsed" class="schema-splitter" @mousedown="beginSchemaResize" />
      <section class="workspace">
        <WorkspaceTabs />
      </section>
      <div v-show="!isChatCollapsed" class="chat-splitter" @mousedown="beginChatResize" />
      <aside v-show="!isChatCollapsed" class="chat-pane" :style="{ width: `${chatPanelWidth}px` }">
        <ChatPanel />
      </aside>
    </main>

    <ProjectEditorDialog
      :visible="projectDialogOpen"
      :mode="projectDialogMode"
      :initial-name="projectDialogInitialName"
      :initial-description="projectDialogInitialDescription"
      :initial-version="projectDialogInitialVersion"
      :loading="projectDialogSaving"
      :error="projectDialogError"
      @close="handleProjectDialogClose"
      @submit="handleProjectDialogSubmit"
    />
    <DiagramLibraryDialog
      :visible="diagramLibraryVisible"
      :diagrams="diagrams"
      :loading="diagramsLoading"
      :error="diagramLibraryError || storeDiagramError"
      @close="closeDiagramLibrary"
      @refresh="refreshDiagramLibrary"
      @select="handleDiagramSelect"
      @delete="handleDiagramDelete"
    />
    <QueryLibraryDialog
      :visible="queryLibraryVisible"
      :queries="queries"
      :loading="queriesLoading"
      :error="queryLibraryError || storeQueryError"
      @close="closeQueryLibrary"
      @refresh="refreshQueryLibrary"
      @select="handleQuerySelect"
      @delete="handleQueryDelete"
    />
    <SyncDialog
      :is-open="syncDialogVisible"
      @close="closeSyncDialog"
      @refresh="refreshProjects"
    />
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from "pinia";
import { onMounted, onUnmounted, ref, watch } from "vue";

import ChatPanel from "./components/ChatPanel.vue";
import DiagramLibraryDialog from "./components/DiagramLibraryDialog.vue";
import ProjectEditorDialog from "./components/ProjectEditorDialog.vue";
import QueryLibraryDialog from "./components/QueryLibraryDialog.vue";
import SchemaSidebar from "./components/SchemaSidebar.vue";
import SyncDialog from "./components/SyncDialog.vue";
import WorkspaceTabs from "./components/WorkspaceTabs.vue";
import { useSessionStore } from "./stores/session";

const sessionStore = useSessionStore();
const {
  projects,
  activeProject,
  loadingProjects,
  isSchemaCollapsed,
  isChatCollapsed,
  schemaPanelWidth,
  chatPanelWidth,
  activeProjectInfo,
  projectDialogOpen,
  projectDialogMode,
  projectDialogInitialName,
  projectDialogInitialDescription,
  projectDialogInitialVersion,
  diagrams,
  diagramsLoading,
  diagramError: storeDiagramError,
  queries,
  queriesLoading,
  queryError: storeQueryError,
} = storeToRefs(sessionStore);

const isSchemaResizing = ref(false);
const isChatResizing = ref(false);
const projectDialogSaving = ref(false);
const projectDialogError = ref("");
const diagramLibraryVisible = ref(false);
const diagramLibraryError = ref("");
const queryLibraryVisible = ref(false);
const queryLibraryError = ref("");
const syncDialogVisible = ref(false);

watch(projectDialogOpen, (open) => {
  if (open) {
    projectDialogError.value = "";
    projectDialogSaving.value = false;
  }
});

onMounted(async () => {
  if (sessionStore.projects.length > 0) {
    return;
  }
  try {
    await sessionStore.initialize();
  } catch (error) {
    console.error("Failed to initialise session", error);
  }
});

async function handleProjectChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  const value = target.value || undefined;
  try {
    await sessionStore.selectProject(value);
  } catch (error) {
    console.error("Project selection failed", error);
  }
}

function toggleSchemaPanel() {
  sessionStore.toggleSchemaPanel();
}

function toggleChatPanel() {
  sessionStore.toggleChatPanel();
}

function openProjectEditor(): void {
  if (!activeProjectInfo.value) {
    return;
  }
  projectDialogError.value = "";
  sessionStore.openProjectDialog("edit");
}

function createSqlTab() {
  sessionStore.createQueryTab({ sql: "", makeActive: true });
}

async function openDiagramLibrary(): Promise<void> {
  diagramLibraryError.value = "";
  diagramLibraryVisible.value = true;
  try {
    await sessionStore.loadDiagrams();
  } catch (error) {
    diagramLibraryError.value = error instanceof Error ? error.message : "Failed to load diagrams.";
  }
}

function closeDiagramLibrary(): void {
  diagramLibraryVisible.value = false;
  diagramLibraryError.value = "";
}

async function handleDiagramSelect(diagramId: string): Promise<void> {
  try {
    const tabId = sessionStore.openDiagramFromSaved(diagramId);
    if (!tabId) {
      diagramLibraryError.value = "Diagram could not be opened.";
      return;
    }
    diagramLibraryVisible.value = false;
    diagramLibraryError.value = "";
  } catch (error) {
    diagramLibraryError.value = error instanceof Error ? error.message : "Unable to open diagram.";
  }
}

async function handleDiagramDelete(diagramId: string): Promise<void> {
  const confirmed = window.confirm("Delete this saved diagram?");
  if (!confirmed) {
    return;
  }
  try {
    await sessionStore.deleteDiagramRecord(diagramId);
  } catch (error) {
    diagramLibraryError.value = error instanceof Error ? error.message : "Failed to delete diagram.";
  }
}

async function refreshDiagramLibrary(): Promise<void> {
  try {
    await sessionStore.loadDiagrams();
    diagramLibraryError.value = "";
  } catch (error) {
    diagramLibraryError.value = error instanceof Error ? error.message : "Failed to refresh diagrams.";
  }
}

async function openQueryLibrary(): Promise<void> {
  queryLibraryError.value = "";
  queryLibraryVisible.value = true;
  try {
    await sessionStore.loadQueries();
  } catch (error) {
    queryLibraryError.value = error instanceof Error ? error.message : "Failed to load queries.";
  }
}

function closeQueryLibrary(): void {
  queryLibraryVisible.value = false;
  queryLibraryError.value = "";
}

async function refreshQueryLibrary(): Promise<void> {
  try {
    await sessionStore.loadQueries();
    queryLibraryError.value = "";
  } catch (error) {
    queryLibraryError.value = error instanceof Error ? error.message : "Failed to refresh queries.";
  }
}

function handleQuerySelect(queryId: string): void {
  sessionStore.openQueryFromSaved(queryId);
  closeQueryLibrary();
}

async function handleQueryDelete(queryId: string): Promise<void> {
  const confirmed = window.confirm("Delete this saved query?");
  if (!confirmed) {
    return;
  }
  try {
    await sessionStore.deleteQueryRecord(queryId);
  } catch (error) {
    queryLibraryError.value = error instanceof Error ? error.message : "Failed to delete query.";
  }
}

function beginSchemaResize(event: MouseEvent) {
  event.preventDefault();
  isSchemaResizing.value = true;
  const startX = event.clientX;
  const initialWidth = schemaPanelWidth.value;
  function handleMove(moveEvent: MouseEvent) {
    const delta = moveEvent.clientX - startX;
    sessionStore.setSchemaPanelWidth(initialWidth + delta);
  }
  function handleUp() {
    isSchemaResizing.value = false;
    window.removeEventListener("mousemove", handleMove);
    window.removeEventListener("mouseup", handleUp);
  }
  window.addEventListener("mousemove", handleMove);
  window.addEventListener("mouseup", handleUp);
}

function beginChatResize(event: MouseEvent) {
  event.preventDefault();
  isChatResizing.value = true;
  const startX = event.clientX;
  const initialWidth = chatPanelWidth.value;
  function handleMove(moveEvent: MouseEvent) {
    const delta = startX - moveEvent.clientX;
    sessionStore.setChatPanelWidth(initialWidth + delta);
  }
  function handleUp() {
    isChatResizing.value = false;
    window.removeEventListener("mousemove", handleMove);
    window.removeEventListener("mouseup", handleUp);
  }
  window.addEventListener("mousemove", handleMove);
  window.addEventListener("mouseup", handleUp);
}

onUnmounted(() => {
  if (isSchemaResizing.value || isChatResizing.value) {
    window.dispatchEvent(new MouseEvent("mouseup"));
  }
});

async function handleProjectDialogSubmit(payload: { name: string; description: string; version: string }): Promise<void> {
  if (projectDialogSaving.value) {
    return;
  }
  projectDialogSaving.value = true;
  projectDialogError.value = "";
  try {
    if (projectDialogMode.value === "create") {
      await sessionStore.createProjectEntry(payload.name, payload.description);
    } else {
      await sessionStore.updateActiveProjectDetails(payload.name, payload.description, payload.version);
    }
    sessionStore.closeProjectDialog();
  } catch (error) {
    projectDialogError.value = error instanceof Error ? error.message : "Failed to save project changes.";
  } finally {
    projectDialogSaving.value = false;
  }
}

function handleProjectDialogClose(): void {
  if (projectDialogSaving.value) {
    return;
  }
  projectDialogError.value = "";
  sessionStore.closeProjectDialog();
}

function openSyncDialog(): void {
  syncDialogVisible.value = true;
}

function closeSyncDialog(): void {
  syncDialogVisible.value = false;
}

async function refreshProjects(): Promise<void> {
  try {
    await sessionStore.initialize();
  } catch (error) {
    console.error("Failed to refresh projects", error);
  }
}
</script>
