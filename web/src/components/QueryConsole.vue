<template>
  <div class="query-console">
    <div class="toolbar">
      <div class="toolbar-actions">
        <div class="button-group">
          <button 
            type="button" 
            class="secondary-button icon-button" 
            @click="undo" 
            :disabled="historyIndex <= 0" 
            title="Undo"
          >
            ↩
          </button>
          <button 
            type="button" 
            class="secondary-button icon-button" 
            @click="redo" 
            :disabled="historyIndex >= history.length - 1" 
            title="Redo"
          >
            ↪
          </button>
          <button 
            type="button" 
            class="secondary-button ai-button" 
            @click="handleAiAssist" 
            :disabled="aiLoading || !sql.trim()" 
            title="Use AI to fix or improve query based on comments"
          >
            {{ aiLoading ? "Thinking..." : "✨ AI Assist" }}
          </button>
          <div class="separator"></div>
          <button type="button" class="secondary-button" @click="openSaveDialog">
            Save
          </button>
          <button type="button" class="secondary-button" :disabled="loading" @click="run">
            {{ loading ? "Running..." : "Run" }}
          </button>
        </div>
        <label title="Maximum number of rows to fetch from the database">
          Rows:
          <input v-model.number="limit" type="number" min="1" max="10000" />
        </label>
      </div>
    </div>
    <textarea
      v-model="sql"
      spellcheck="false"
      placeholder="SELECT * FROM your_table LIMIT 10;"
      @input="handleInput"
    ></textarea>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    
    <div v-if="result" class="result-block">
      <div class="result-meta">
        <span>Rows: {{ result.rows.length }} / {{ result.row_count }}</span>
        <span v-if="result.truncated">Result truncated to {{ limit }} rows.</span>
        <span v-if="result.message">{{ result.message }}</span>
      </div>
      <div class="table-wrapper" v-if="result.rows.length > 0">
        <table>
          <thead>
            <tr>
              <th v-for="column in result.columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in result.rows" :key="idx">
              <td v-for="(cell, colIdx) in row" :key="colIdx">
                {{ formatCell(cell) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">Query executed successfully but returned no rows.</div>
    </div>
    <div v-else class="empty-state">Run a query to see results.</div>
    <QuerySaveDialog
      :visible="showSaveDialog"
      :loading="saveDialogLoading"
      :error="saveDialogError"
      :default-name="tab.title"
      :default-description="tab.queryDescription ?? ''"
      @close="closeSaveDialog"
      @submit="handleSaveQuery"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { assistQuery } from "../api/client";
import { useSessionStore, type QueryTabState } from "../stores/session";
import QuerySaveDialog from "./QuerySaveDialog.vue";

const props = defineProps<{
  tab: QueryTabState;
}>();

const sessionStore = useSessionStore();

const sql = computed<string>({
  get: () => props.tab.sql,
  set: (value) => sessionStore.updateQueryTabSql(props.tab.id, value),
});

const limit = computed<number>({
  get: () => props.tab.limit,
  set: (value) => sessionStore.updateQueryTabLimit(props.tab.id, Number(value)),
});

const loading = computed(() => props.tab.loading);
const errorMessage = computed(() => props.tab.errorMessage);
const result = computed(() => props.tab.result);

const showSaveDialog = ref(false);
const saveDialogError = ref("");
const saveDialogLoading = ref(false);

// History for Undo/Redo
const history = ref<string[]>([]);
const historyIndex = ref(-1);
const isNavigatingHistory = ref(false);
const aiLoading = ref(false);

// Initialize history with current value
watch(() => props.tab.sql, (newVal) => {
  if (history.value.length === 0) {
     history.value.push(newVal);
     historyIndex.value = 0;
     return;
  }
  
  if (isNavigatingHistory.value) {
    isNavigatingHistory.value = false;
    return;
  }

  // Only push if different from current history head
  if (newVal !== history.value[historyIndex.value]) {
    // If we are not at the end of history, discard future
    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1);
    }
    history.value.push(newVal);
    historyIndex.value++;
  }
}, { immediate: true });

// Debounce input to avoid too many history entries
let debounceTimer: number | null = null;
function handleInput() {
  // The watch handles the history push, but we might want to debounce the actual store update if we were managing local state.
  // Since sql is computed with a setter that updates the store immediately, the watch triggers immediately.
  // To implement debounced history, we would need to decouple the watch from the immediate store update or manage history differently.
  // For now, we'll accept granular history or rely on the fact that users pause.
  // Actually, let's try to debounce the history push in the watch? No, watch triggers on value change.
  // We can't easily debounce the watch effect without delaying the history update.
}

function undo() {
  if (historyIndex.value > 0) {
    isNavigatingHistory.value = true;
    historyIndex.value--;
    sql.value = history.value[historyIndex.value];
  }
}

function redo() {
  if (historyIndex.value < history.value.length - 1) {
    isNavigatingHistory.value = true;
    historyIndex.value++;
    sql.value = history.value[historyIndex.value];
  }
}

async function handleAiAssist() {
  if (!sql.value.trim()) return;
  
  aiLoading.value = true;
  try {
    const response = await assistQuery({
      sql: sql.value,
      project: sessionStore.activeProject?.name,
      database: sessionStore.activeDatabase,
    });
    
    // Update SQL with the response
    // This will trigger the watch and add to history, so it's undoable
    sql.value = response.sql;
  } catch (error) {
    console.error("AI Assist failed", error);
    const msg = (error as any).response?.data?.detail || (error instanceof Error ? error.message : String(error));
    alert("AI Assist failed: " + msg);
  } finally {
    aiLoading.value = false;
  }
}

function formatCell(cell: unknown): string {
  if (cell === null || cell === undefined) {
    return "";
  }
  return String(cell);
}

async function run(): Promise<void> {
  try {
    await sessionStore.runQueryForTab(props.tab.id);
  } catch (error) {
    // error message stored on tab state; optionally log for debugging
    if (import.meta.env.DEV) {
      console.warn("Query execution failed", error);
    }
  }
}

function copyToNewTab(): void {
  sessionStore.createQueryTab({ sql: sql.value });
}

function openSaveDialog(): void {
  saveDialogError.value = "";
  showSaveDialog.value = true;
}

function closeSaveDialog(): void {
  if (saveDialogLoading.value) {
    return;
  }
  saveDialogError.value = "";
  showSaveDialog.value = false;
}

async function handleSaveQuery(payload: { name: string; description: string }): Promise<void> {
  if (saveDialogLoading.value) {
    return;
  }
  let targetQueryId: string | null | undefined = props.tab.queryId;
  if (props.tab.queryId) {
    const overwrite = window.confirm(
      "This query already exists. Select OK to overwrite it, or Cancel to save as a new query.",
    );
    if (!overwrite) {
      targetQueryId = null;
    }
  }
  saveDialogLoading.value = true;
  saveDialogError.value = "";
  try {
    await sessionStore.saveQueryForTab(props.tab.id, {
      name: payload.name,
      description: payload.description,
      queryId: targetQueryId,
    });
    showSaveDialog.value = false;
  } catch (error) {
    saveDialogError.value = error instanceof Error ? error.message : "Failed to save query.";
  } finally {
    saveDialogLoading.value = false;
  }
}
</script>

<style scoped>
.query-console {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  height: 100%;
  overflow: hidden;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.button-group {
  display: flex;
  gap: 0.25rem;
  align-items: center;
}

.separator {
  width: 1px;
  height: 20px;
  background-color: #cbd5e1;
  margin: 0 0.5rem;
}

.secondary-button {
  background-color: transparent;
  color: #b26a45;
  border: 1px solid #d89b6c;
  border-radius: 6px;
  padding: 0.45rem 0.9rem;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.secondary-button:hover {
  background-color: #9a5838;
  border-color: #9a5838;
  color: #ffffff;
}

.secondary-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.secondary-button:disabled:hover {
  background-color: transparent;
  border-color: #d89b6c;
  color: #b26a45;
}

.icon-button {
  padding: 0.45rem 0.6rem;
  font-size: 1.1rem;
  line-height: 1;
}

.ai-button {
  background-color: #f0f9ff;
  border-color: #bae6fd;
  color: #0284c7;
}

.ai-button:hover {
  background-color: #0284c7;
  border-color: #0284c7;
  color: #ffffff;
}

.ai-button:disabled:hover {
  background-color: #f0f9ff;
  border-color: #bae6fd;
  color: #0284c7;
}

textarea {
  min-height: 120px;
  border-radius: 8px;
  border: 1px solid #cbd5f5;
  padding: 0.75rem;
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 0.9rem;
  resize: vertical;
}

textarea:focus {
  outline: none;
  border: 2px solid #b26a45;
}

label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: #334155;
}

label input[type="number"] {
  width: 80px;
  border: 1px solid #cbd5f5;
  border-radius: 4px;
  padding: 0.35rem 0.5rem;
  font-size: 0.9rem;
}

label input[type="number"]:focus {
  outline: none;
  border-color: #b26a45;
}

.result-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
  min-height: 0;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.85rem;
  color: #475569;
}

.table-wrapper {
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  flex: 1;
  min-height: 0;
  max-height: 100%;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

th,
td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid #e2e8f0;
  border-right: 1px solid #e2e8f0;
  text-align: left;
  white-space: nowrap;
}

td:last-child,
th:last-child {
  border-right: none;
}

th {
  background-color: #f1f5f9;
  font-weight: 600;
}

.error {
  color: #b91c1c;
  font-size: 0.85rem;
}
</style>
