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
    <div class="editor-container" :style="{ height: sessionStore.queryEditorHeight + 'px' }">
      <textarea
        v-model="sql"
        spellcheck="false"
        placeholder="SELECT * FROM your_table LIMIT 10;"
        @input="handleInput"
      ></textarea>
      <div class="resize-handle" @mousedown="startResize"></div>
    </div>
    <div v-if="errorMessage" class="error-container">
      <div class="error-header">
        <p class="error-message">{{ errorMessage }}</p>
        <button 
          type="button" 
          class="secondary-button ai-fix-button" 
          @click="handleAiFix" 
          :disabled="aiErrorLoading"
        >
          {{ aiErrorLoading ? "Analyzing..." : "✨ Fix with AI" }}
        </button>
      </div>
      
      <div v-if="aiErrorResult" class="ai-error-result">
        <div class="ai-explanation">
          <strong>AI Explanation:</strong> {{ aiErrorResult.explanation }}
        </div>
        <div class="ai-fix-actions">
          <pre class="fixed-sql">{{ aiErrorResult.fixed_sql }}</pre>
          <button 
            type="button" 
            class="primary-button" 
            @click="applyAiFix"
          >
            Apply Fix
          </button>
        </div>
      </div>
    </div>  
    
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
              <th 
                v-for="column in result.columns" 
                :key="column"
                class="header-cell"
              >
                <div class="th-content">
                  <span @click="toggleSort(column)" class="col-name">{{ column }}</span>
                  <span v-if="sortColumn === column" class="sort-indicator">
                    {{ sortDirection === 'asc' ? '▲' : '▼' }}
                  </span>
                  <button class="filter-btn" @click.stop="toggleFilterMenu(column, $event)" :class="{ active: isFilterActive(column) }">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
                    </svg>
                  </button>
                  
                  <div v-if="activeFilterColumn === column" class="filter-dropdown" @click.stop>
                    <div class="filter-header">
                        <strong>Filter {{ column }}</strong>
                    </div>
                    <div class="filter-actions">
                        <button class="text-btn" @click="selectAll">All</button>
                        <button class="text-btn" @click="deselectAll">None</button>
                    </div>
                    <div class="filter-list">
                        <label v-for="(val, vIdx) in distinctValues" :key="vIdx" class="filter-item">
                          <input type="checkbox" :checked="isValueSelected(val)" @change="toggleFilterValue(val)">
                          <span class="val-text">{{ formatCell(val) || '(empty)' }}</span>
                        </label>
                    </div>
                    <div class="filter-footer">
                        <button class="secondary-button small" @click="clearFilter(column)">Clear Filter</button>
                        <button class="primary-button small" @click="activeFilterColumn = null">Close</button>
                    </div>
                  </div>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in sortedRows" :key="idx">
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
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { assistQuery, assistQueryError, saveQuery } from "../api/client";
import { useSessionStore, type QueryTabState } from "../stores/session";
import type { QueryErrorAssistResponse } from "../types/api";
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

// Filtering
const activeFilterColumn = ref<string | null>(null);
const filters = ref<Record<string, Set<any>>>({});

function handleClickOutside(event: MouseEvent) {
  if (activeFilterColumn.value) {
    const target = event.target as HTMLElement;
    if (!target.closest('.filter-dropdown') && !target.closest('.filter-btn')) {
      activeFilterColumn.value = null;
    }
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});

const distinctValues = computed(() => {
  if (!activeFilterColumn.value || !result.value) return [];
  const colIndex = result.value.columns.indexOf(activeFilterColumn.value);
  if (colIndex === -1) return [];
  
  const values = new Set();
  for (const row of result.value.rows) {
    values.add(row[colIndex]);
    if (values.size >= 100) break;
  }
  return Array.from(values).sort();
});

const filteredRows = computed(() => {
  if (!result.value || !result.value.rows) return [];
  let rows = result.value.rows;
  
  for (const [col, allowedValues] of Object.entries(filters.value)) {
    const colIndex = result.value.columns.indexOf(col);
    if (colIndex === -1) continue;
    rows = rows.filter(row => allowedValues.has(row[colIndex]));
  }
  return rows;
});

function toggleFilterMenu(column: string, event: MouseEvent) {
  if (activeFilterColumn.value === column) {
    activeFilterColumn.value = null;
  } else {
    activeFilterColumn.value = column;
  }
}

function isFilterActive(column: string) {
  return !!filters.value[column];
}

function isValueSelected(val: any) {
  if (!activeFilterColumn.value) return false;
  const currentFilters = filters.value[activeFilterColumn.value];
  if (!currentFilters) return true; // No filter = all selected
  return currentFilters.has(val);
}

function toggleFilterValue(val: any) {
  if (!activeFilterColumn.value) return;
  const col = activeFilterColumn.value;
  
  let currentFilters = filters.value[col];
  if (!currentFilters) {
    currentFilters = new Set(distinctValues.value);
    filters.value[col] = currentFilters;
  }
  
  if (currentFilters.has(val)) {
    currentFilters.delete(val);
  } else {
    currentFilters.add(val);
  }
  
  filters.value = { ...filters.value };
}

function selectAll() {
  if (!activeFilterColumn.value) return;
  const newFilters = { ...filters.value };
  delete newFilters[activeFilterColumn.value];
  filters.value = newFilters;
}

function deselectAll() {
  if (!activeFilterColumn.value) return;
  const newFilters = { ...filters.value };
  newFilters[activeFilterColumn.value] = new Set();
  filters.value = newFilters;
}

function clearFilter(column: string) {
    const newFilters = { ...filters.value };
    delete newFilters[column];
    filters.value = newFilters;
    activeFilterColumn.value = null;
}

// Sorting
const sortColumn = ref<string | null>(null);
const sortDirection = ref<'asc' | 'desc'>('asc');

const sortedRows = computed(() => {
  if (!filteredRows.value) return [];
  
  const rows = [...filteredRows.value];
  if (!sortColumn.value || !result.value) return rows;
  
  const colIndex = result.value.columns.indexOf(sortColumn.value);
  if (colIndex === -1) return rows;
  
  return rows.sort((a, b) => {
    const valA = a[colIndex];
    const valB = b[colIndex];
    
    if (valA === valB) return 0;
    if (valA === null || valA === undefined) return 1;
    if (valB === null || valB === undefined) return -1;
    
    if (valA < valB) return sortDirection.value === 'asc' ? -1 : 1;
    if (valA > valB) return sortDirection.value === 'asc' ? 1 : -1;
    return 0;
  });
});

function toggleSort(column: string) {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortColumn.value = column;
    sortDirection.value = 'asc';
  }
}

// Resizing
const isResizing = ref(false);
const startY = ref(0);
const startHeight = ref(0);

function startResize(event: MouseEvent) {
  isResizing.value = true;
  startY.value = event.clientY;
  startHeight.value = sessionStore.queryEditorHeight;
  
  document.addEventListener('mousemove', handleResize);
  document.addEventListener('mouseup', stopResize);
  document.body.style.cursor = 'row-resize';
  document.body.style.userSelect = 'none';
}

function handleResize(event: MouseEvent) {
  if (!isResizing.value) return;
  
  const deltaY = event.clientY - startY.value;
  const newHeight = Math.max(100, Math.min(800, startHeight.value + deltaY));
  sessionStore.setQueryEditorHeight(newHeight);
}

function stopResize() {
  isResizing.value = false;
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
}

// History for Undo/Redo
const history = ref<string[]>([]);
const historyIndex = ref(-1);
const isNavigatingHistory = ref(false);
const aiLoading = ref(false);
const aiErrorLoading = ref(false);
const aiErrorResult = ref<QueryErrorAssistResponse | null>(null);

// Initialize history with current value
watch(() => props.tab.sql, (newVal) => {
  if (aiErrorResult.value) {
    aiErrorResult.value = null;
  }
  if (history.value.length === 0) {
     history.value.push(newVal);
     historyIndex.value = 0;
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

function handleInput() {
  // Debounce input to avoid too many history entries
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
  aiErrorResult.value = null;
  try {
    const response = await assistQuery({
      sql: sql.value,
      project: sessionStore.activeProject,
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

async function handleAiFix() {
  if (!errorMessage.value) return;
  
  aiErrorLoading.value = true;
  aiErrorResult.value = null;
  
  try {
    const response = await assistQueryError({
      sql: sql.value,
      error: errorMessage.value,
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
    });
    aiErrorResult.value = response;
  } catch (error) {
    console.error("AI Fix failed", error);
    const msg = (error as any).response?.data?.detail || (error instanceof Error ? error.message : String(error));
    alert("AI Fix failed: " + msg);
  } finally {
    aiErrorLoading.value = false;
  }
}

function applyAiFix() {
  if (aiErrorResult.value) {
    sql.value = aiErrorResult.value.fixed_sql;
    aiErrorResult.value = null;
  }
}

async function handleSaveQuery(payload: { name: string; description: string }) {
  saveDialogLoading.value = true;
  saveDialogError.value = "";
  try {
    const savedQuery = await saveQuery({
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
      name: payload.name,
      description: payload.description,
      sql: sql.value,
      limit: limit.value,
      query_id: props.tab.queryId,
    });
    
    sessionStore.updateQueryTab(props.tab.id, {
      title: savedQuery.name,
      queryId: savedQuery.id,
      queryDescription: savedQuery.description || undefined,
    });
    
    saveDialogLoading.value = false;
    closeSaveDialog();
  } catch (error) {
    console.error("Failed to save query", error);
    saveDialogError.value = (error as any).response?.data?.detail || (error instanceof Error ? error.message : String(error));
  } finally {
    saveDialogLoading.value = false;
  }
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

async function run(): Promise<void> {
  aiErrorResult.value = null;
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

function formatCell(cell: unknown): string {
  if (cell === null || cell === undefined) {
    return "";
  }
  return String(cell);
}
</script>

<style scoped>
.query-console {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
  background-color: #f1f1f1;
  border-bottom: 1px solid #ddd;
}

.toolbar-actions {
  display: flex;
  align-items: center;
}

.button-group {
  display: flex;
  align-items: center;
}

.secondary-button {
  background-color: transparent;
  border: 1px solid #007bff;
  color: #007bff;
  padding: 0.375rem 0.75rem;
  margin-right: 0.5rem;
  cursor: pointer;
  border-radius: 0.25rem;
  font-size: 0.875rem;
}

.secondary-button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.icon-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  margin-right: 0.5rem;
  border: none;
  background: none;
  color: inherit;
  font-size: 1rem;
  cursor: pointer;
}

.ai-button {
  background-color: #28a745;
  border-color: #28a745;
  color: white;
}

.ai-button:disabled {
  background-color: #c3e6cb;
  border-color: #c3e6cb;
  color: #155724;
}

.separator {
  width: 1px;
  height: 24px;
  background-color: #ddd;
  margin: 0 0.5rem;
}

label {
  font-size: 0.875rem;
  margin-right: 1rem;
}

input[type="number"] {
  width: 4rem;
  padding: 0.25rem;
  margin-left: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 0.25rem;
  font-size: 0.875rem;
}

.editor-container {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100px;
  max-height: 800px;
}

textarea {
  flex: 1;
  padding: 1rem;
  border: 1px solid #ddd;
  border-radius: 0.25rem;
  font-family: monospace;
  font-size: 0.875rem;
  resize: none;
  outline: none;
}

textarea:focus {
  border-color: #007bff;
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
}

.resize-handle {
  height: 6px;
  background-color: #f1f1f1;
  cursor: row-resize;
  border-top: 1px solid #ddd;
  border-bottom: 1px solid #ddd;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: background-color 0.2s;
}

.resize-handle:hover, .resize-handle:active {
  background-color: #e2e6ea;
}

.resize-handle::after {
  content: "";
  width: 30px;
  height: 2px;
  background-color: #ccc;
  border-radius: 1px;
}

.error-container {
  background-color: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 0.25rem;
  padding: 1rem;
  margin-top: 1rem;
}

.error-header {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  align-items: flex-start;
}

.error-message {
  margin: 0;
  color: #721c24;
}

.ai-error-result {
  margin-top: 1rem;
  padding: 1rem;
  border: 1px solid #007bff;
  border-radius: 0.25rem;
  background-color: #e7f1ff;
}

.ai-explanation {
  margin-bottom: 0.5rem;
  color: #004085;
}

.fixed-sql {
  background-color: #f1f1f1;
  padding: 0.5rem;
  border-radius: 0.25rem;
  font-family: monospace;
  font-size: 0.875rem;
  overflow-x: auto;
}

.primary-button {
  background-color: #007bff;
  border-color: #007bff;
  color: white;
  padding: 0.375rem 0.75rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.primary-button:disabled {
  background-color: #cce5ff;
  border-color: #b8daff;
  color: #004085;
}

.result-block {
  margin-top: 1rem;
  padding: 0;
  border: 1px solid #28a745;
  border-radius: 0.25rem;
  background-color: white;
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0;
  padding: 0.5rem;
  background-color: #d4edda;
  border-bottom: 1px solid #28a745;
}

.table-wrapper {
  flex: 1;
  overflow: auto;
  border: none;
  background-color: white;
  margin-bottom: 0;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

th, td {
  border: 1px solid #dee2e6;
  padding: 0.5rem;
  text-align: left;
}

th {
  background-color: #e9ecef;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
  cursor: pointer;
  user-select: none;
}

th:hover {
  background-color: #dee2e6;
}

.sort-indicator {
  margin-left: 0.25rem;
  font-size: 0.75rem;
}

th {
  background-color: #e9ecef;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
}

tbody tr:nth-child(even) {
  background-color: #f8f9fa;
}

tbody tr:hover {
  background-color: #e2e6ea;
}

.empty-state {
  text-align: center;
  color: #6c757d;
  padding: 1rem;
  border: 1px dashed #ccc;
  border-radius: 0.25rem;
}

.header-cell {
  position: relative;
}

.th-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.col-name {
  flex: 1;
  cursor: pointer;
}

.filter-btn {
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.3;
  padding: 2px;
  margin-left: 4px;
  display: flex;
  align-items: center;
}

.filter-btn:hover, .filter-btn.active {
  opacity: 1;
  color: #007bff;
}

.filter-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  background: white;
  border: 1px solid #ccc;
  box-shadow: 0 2px 10px rgba(0,0,0,0.2);
  z-index: 100;
  min-width: 200px;
  max-height: 300px;
  display: flex;
  flex-direction: column;
  border-radius: 4px;
  font-weight: normal;
  color: #333;
  text-align: left;
}

.filter-header {
  padding: 8px;
  border-bottom: 1px solid #eee;
  background: #f9f9f9;
}

.filter-actions {
  padding: 4px 8px;
  border-bottom: 1px solid #eee;
  display: flex;
  gap: 8px;
}

.text-btn {
  background: none;
  border: none;
  color: #007bff;
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0;
}

.text-btn:hover {
  text-decoration: underline;
}

.filter-list {
  overflow-y: auto;
  padding: 4px 0;
  flex: 1;
  max-height: 200px;
}

.filter-item {
  display: flex;
  align-items: center;
  padding: 4px 8px;
  cursor: pointer;
}

.filter-item:hover {
  background-color: #f1f1f1;
}

.filter-item input {
  margin-right: 8px;
}

.val-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

.filter-footer {
  padding: 8px;
  border-top: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  background: #f9f9f9;
}

.small {
  padding: 2px 6px;
  font-size: 0.75rem;
}
</style>
