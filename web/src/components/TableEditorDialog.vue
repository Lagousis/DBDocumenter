<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel">
        <header class="dialog-header">
          <div>
            <h3>{{ table }}</h3>
            <p>Edit table metadata</p>
          </div>
          <button type="button" class="icon-button" @click="handleClose" aria-label="Close dialog">
            ×
          </button>
        </header>

        <div class="dialog-body">
          <div v-if="!showDeletePanel">
            <label class="block">
              <span class="label">Short description</span>
              <input v-model="form.short_description" type="text" />
            </label>

            <label class="block">
              <span class="label">Long description</span>
              <textarea v-model="form.long_description" rows="4" />
            </label>
          </div>

          <div v-else class="delete-panel">
            <div class="warning-box">
              <p><strong>Warning:</strong> This will permanently delete data from the table. The schema will be preserved.</p>
            </div>

            <div class="current-stats" v-if="rowCount !== null">
              Current row count: <strong>{{ rowCount }}</strong>
            </div>

            <label class="block">
              <span class="label">Deletion Mode</span>
              <div class="radio-group">
                <label class="radio-label">
                  <input type="radio" v-model="deleteForm.mode" value="all" />
                  <span>Delete all rows</span>
                </label>
                <label class="radio-label">
                  <input type="radio" v-model="deleteForm.mode" value="subset" />
                  <span>Keep a specific count of rows</span>
                </label>
                <label class="radio-label">
                  <input type="radio" v-model="deleteForm.mode" value="filter" />
                  <span>Use a filter to select rows to RETAIN</span>
                </label>
              </div>
            </label>

            <div v-if="deleteForm.mode === 'subset'" class="subset-options">
              <label class="block">
                <span class="label">Rows to keep</span>
                <input type="number" v-model.number="deleteForm.keep_count" min="1" />
              </label>

              <div class="grid two">
                <label class="block">
                  <span class="label">Sort by column</span>
                  <select v-model="deleteForm.sort_column">
                    <option v-for="col in fieldNames" :key="col" :value="col">{{ col }}</option>
                  </select>
                </label>

                <label class="block">
                  <span class="label">Order</span>
                  <select v-model="deleteForm.sort_order">
                    <option value="ASC">Ascending (Keep first)</option>
                    <option value="DESC">Descending (Keep last)</option>
                  </select>
                </label>
              </div>
            </div>

            <div v-if="deleteForm.mode === 'filter'" class="subset-options">
              <label class="block">
                <span class="label">Filter Condition (SQL WHERE clause for rows to KEEP)</span>
                <textarea 
                  v-model="deleteForm.filter_condition" 
                  rows="3" 
                  placeholder="e.g. status = 'active' OR created_at >= '2023-01-01'"
                ></textarea>
              </label>

              <div class="filter-actions">
                <button 
                  type="button" 
                  class="secondary-button small" 
                  @click="calculateFilterStats"
                  :disabled="!deleteForm.filter_condition || filterStats.calculating"
                >
                  {{ filterStats.calculating ? 'Calculating...' : 'Preview Counts' }}
                </button>
              </div>

              <div v-if="filterStats.error" class="error-box">
                <p><strong>Error:</strong> {{ filterStats.error }}</p>
                <button 
                  type="button" 
                  class="secondary-button small" 
                  @click="fixFilterWithAI"
                  :disabled="fixingFilter"
                >
                  {{ fixingFilter ? 'Fixing...' : 'Fix with AI' }}
                </button>
              </div>

              <div v-if="filterStats.calculated" class="stats-box">
                <div class="stat-row">
                  <span class="stat-label">Total rows:</span>
                  <span class="stat-value">{{ filterStats.total_rows }}</span>
                </div>
                <div class="stat-row delete-row">
                  <span class="stat-label">To be deleted:</span>
                  <span class="stat-value">{{ filterStats.deleted_rows }} ({{ filterStats.percent_deleted }}%)</span>
                </div>
                <div class="stat-row retain-row">
                  <span class="stat-label">To be retained:</span>
                  <span class="stat-value">{{ filterStats.retained_rows }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <footer class="dialog-footer">
          <template v-if="!showDeletePanel">
            <button type="button" class="secondary-button danger" @click="showDeletePanel = true">Delete data</button>
            <div class="spacer"></div>
            <button type="button" class="secondary-button" @click="handleClose">Cancel</button>
            <button type="button" class="secondary-button" @click="handleSave" :disabled="saving">
              {{ saving ? "Saving..." : "Save" }}
            </button>
          </template>
          <template v-else>
            <button type="button" class="secondary-button" @click="showDeletePanel = false">Back</button>
            <div class="spacer"></div>
            <button type="button" class="secondary-button danger" @click="handleDeleteData" :disabled="saving || !isDeleteValid">
              {{ saving ? "Deleting..." : "Confirm Delete" }}
            </button>
          </template>
        </footer>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import { deleteTableData, runQuery, sendChat, updateTableMetadata } from "../api/client";
import { useSessionStore } from "../stores/session";

const props = defineProps<{
  visible: boolean;
  table: string;
}>();

const emit = defineEmits<{
  (e: "update:visible", value: boolean): void;
  (e: "saved"): void;
  (e: "deleted"): void;
}>();

const sessionStore = useSessionStore();
const saving = ref(false);
const showDeletePanel = ref(false);
const rowCount = ref<number | null>(null);

interface TableForm {
  short_description: string;
  long_description: string;
}

const form = ref<TableForm>({
  short_description: "",
  long_description: "",
});

const deleteForm = reactive({
  mode: 'all' as 'all' | 'subset' | 'filter',
  keep_count: 100,
  sort_column: '',
  sort_order: 'DESC' as 'ASC' | 'DESC',
  filter_condition: '',
});

const filterStats = reactive({
  calculating: false,
  error: null as string | null,
  total_rows: 0,
  deleted_rows: 0,
  retained_rows: 0,
  percent_deleted: 0,
  calculated: false,
});

const fixingFilter = ref(false);

const tableRecord = computed(() => {
  const schemaData = sessionStore.schema;
  if (!schemaData || !schemaData.tables) {
    return {};
  }
  const tables = schemaData.tables as Record<string, any>;
  return tables[props.table] || {};
});

const fieldNames = computed(() => {
  const fields = tableRecord.value.fields || {};
  return Object.keys(fields).sort();
});

const isDeleteValid = computed(() => {
  if (deleteForm.mode === 'all') return true;
  if (deleteForm.mode === 'subset') return deleteForm.keep_count > 0 && !!deleteForm.sort_column;
  if (deleteForm.mode === 'filter') return !!deleteForm.filter_condition && !filterStats.error;
  return false;
});

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      form.value.short_description = tableRecord.value.short_description || "";
      form.value.long_description = tableRecord.value.long_description || "";
      showDeletePanel.value = false;
      
      // Reset delete form
      deleteForm.mode = 'all';
      deleteForm.keep_count = 100;
      deleteForm.sort_column = fieldNames.value[0] || '';
      deleteForm.sort_order = 'DESC';
      deleteForm.filter_condition = '';
      rowCount.value = null;
      resetFilterStats();
    }
  },
  { immediate: true }
);

watch(showDeletePanel, (val) => {
  if (val) {
    fetchRowCount();
  }
});

async function fetchRowCount() {
  try {
    const res = await runQuery({
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
      sql: `SELECT COUNT(*) FROM "${props.table}"`
    });
    if (res.rows && res.rows[0]) {
      rowCount.value = Number(res.rows[0][0]);
    }
  } catch (e) {
    console.error("Failed to fetch row count", e);
  }
}

function resetFilterStats() {
  filterStats.calculating = false;
  filterStats.error = null;
  filterStats.total_rows = 0;
  filterStats.deleted_rows = 0;
  filterStats.retained_rows = 0;
  filterStats.percent_deleted = 0;
  filterStats.calculated = false;
}

watch(() => deleteForm.filter_condition, () => {
  if (filterStats.calculated || filterStats.error) {
    resetFilterStats();
  }
});

async function calculateFilterStats() {
  if (!deleteForm.filter_condition) return;
  
  filterStats.calculating = true;
  filterStats.error = null;
  
  try {
    // Get total count
    const totalRes = await runQuery({
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
      sql: `SELECT COUNT(*) FROM "${props.table}"`
    });
    
    // Get retained count (matching filter)
    const retainedRes = await runQuery({
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
      sql: `SELECT COUNT(*) FROM "${props.table}" WHERE ${deleteForm.filter_condition}`
    });

    if (totalRes.rows && retainedRes.rows) {
      const total = Number(totalRes.rows[0][0]);
      const retained = Number(retainedRes.rows[0][0]);
      const deleted = total - retained;
      
      filterStats.total_rows = total;
      filterStats.deleted_rows = deleted;
      filterStats.retained_rows = retained;
      filterStats.percent_deleted = total > 0 ? Math.round((deleted / total) * 100) : 0;
      filterStats.calculated = true;
    }
  } catch (e: any) {
    console.error("Filter calculation error", e);
    // Extract error message from response if available
    const msg = e.response?.data?.detail || e.message || "Unknown error";
    filterStats.error = msg;
  } finally {
    filterStats.calculating = false;
  }
}

async function fixFilterWithAI() {
  if (!filterStats.error) return;
  
  fixingFilter.value = true;
  try {
    const schemaSummary = Object.entries(tableRecord.value.fields || {})
      .map(([name, meta]: [string, any]) => `${name} (${meta.data_type})`)
      .join(", ");

    const prompt = `I am trying to RETAIN rows in table "${props.table}" with condition: "${deleteForm.filter_condition}".
I got this error: "${filterStats.error}".
The table schema is: ${schemaSummary}.
Please provide a corrected SQL WHERE clause condition to select the rows to KEEP. Return ONLY the condition text, nothing else.`;

    const response = await sendChat({
      message: prompt,
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
    });

    if (response.reply) {
      // Strip any markdown code blocks if present
      let fixed = response.reply.trim();
      if (fixed.startsWith("```sql")) fixed = fixed.substring(6);
      if (fixed.startsWith("```")) fixed = fixed.substring(3);
      if (fixed.endsWith("```")) fixed = fixed.substring(0, fixed.length - 3);
      
      deleteForm.filter_condition = fixed.trim();
      // Auto-recalculate to verify
      await calculateFilterStats();
    }
  } catch (e) {
    console.error("AI fix failed", e);
    alert("Failed to get AI suggestion.");
  } finally {
    fixingFilter.value = false;
  }
}

function handleClose(): void {
  emit("update:visible", false);
}

async function handleSave(): Promise<void> {
  saving.value = true;
  try {
    await updateTableMetadata({
      project: sessionStore.activeProject || undefined,
      database: sessionStore.activeDatabase || undefined,
      table: props.table,
      short_description: form.value.short_description,
      long_description: form.value.long_description,
    });

    await sessionStore.refreshMetadata();
    emit("saved");
    emit("update:visible", false);
  } catch (error) {
    console.error("Failed to update table metadata:", error);
    alert("Failed to update table metadata. Please try again.");
  } finally {
    saving.value = false;
  }
}

async function handleDeleteData(): Promise<void> {
  if (!confirm(`Are you sure you want to delete data from "${props.table}"? This cannot be undone.`)) {
    return;
  }
  
  saving.value = true;
  try {
    await deleteTableData({
      project: sessionStore.activeProject || undefined,
      database: sessionStore.activeDatabase || undefined,
      table: props.table,
      mode: deleteForm.mode,
      keep_count: deleteForm.mode === 'subset' ? deleteForm.keep_count : undefined,
      sort_column: deleteForm.mode === 'subset' ? deleteForm.sort_column : undefined,
      sort_order: deleteForm.mode === 'subset' ? deleteForm.sort_order : undefined,
      filter_condition: deleteForm.mode === 'filter' ? deleteForm.filter_condition : undefined,
    });

    // No need to refresh metadata as schema hasn't changed, but maybe good to signal success
    alert("Data deleted successfully.");
    emit("update:visible", false);
  } catch (error) {
    console.error("Failed to delete table data:", error);
    alert("Failed to delete table data. Please try again.");
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
/* ... existing styles ... */
.delete-panel {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.warning-box {
  background: #fff5f5;
  border: 1px solid #feb2b2;
  color: #c53030;
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
}

.warning-box p {
  margin: 0;
}

.current-stats {
  font-size: 0.95rem;
  color: #4a5568;
  padding: 0 0.25rem;
}

.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.95rem;
  color: #3d3129;
}

.subset-options {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-left: 1.5rem;
  border-left: 2px solid rgba(178, 106, 69, 0.2);
}

.grid.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

select {
  width: 100%;
  border: 1px solid rgba(178, 106, 69, 0.3);
  border-radius: 10px;
  padding: 0.5rem 0.65rem;
  font-size: 0.9rem;
  background: #fefbf6;
  color: #3d3129;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(47, 38, 32, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  z-index: 1000;
}

.dialog-panel {
  width: min(640px, 100%);
  max-height: 90vh;
  background: #fdf9f3;
  border-radius: 20px;
  box-shadow: 0 24px 50px rgba(47, 38, 32, 0.22);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(178, 106, 69, 0.2);
  background: rgba(253, 248, 241, 0.9);
}

.dialog-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #4f4035;
}

.dialog-header p {
  margin: 0.35rem 0 0;
  font-size: 0.85rem;
  color: #7a6a5d;
}

.dialog-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
}

.dialog-footer {
  padding: 0.9rem 1.25rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  border-top: 1px solid rgba(178, 106, 69, 0.18);
  background: rgba(253, 248, 241, 0.9);
}

.spacer {
  flex: 1;
}

.block {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.label {
  font-weight: 600;
  color: #5c4b3f;
  font-size: 0.9rem;
}

input[type="text"],
textarea {
  border: 1px solid rgba(178, 106, 69, 0.3);
  border-radius: 10px;
  padding: 0.5rem 0.65rem;
  font-size: 0.9rem;
  background: #fefbf6;
  color: #3d3129;
  font-family: inherit;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

input[type="text"]:focus,
textarea:focus {
  outline: none;
  border-color: rgba(178, 106, 69, 0.65);
  box-shadow: 0 0 0 3px rgba(178, 106, 69, 0.15);
}

textarea {
  resize: vertical;
  min-height: 80px;
  line-height: 1.5;
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

.secondary-button.danger {
  color: #c0392b;
  border-color: #e74c3c;
}

.secondary-button.danger:hover {
  background-color: #c0392b;
  border-color: #c0392b;
  color: #ffffff;
}

.icon-button {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: 1px solid rgba(178, 106, 69, 0.28);
  background: rgba(253, 248, 241, 0.92);
  color: #b26a45;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
  font-size: 1.5rem;
  padding: 0;
}

.secondary-button.small {
  padding: 0.25rem 0.6rem;
  font-size: 0.85rem;
}

.filter-actions {
  margin-top: 0.5rem;
}

.error-box {
  background: #fff5f5;
  border: 1px solid #feb2b2;
  color: #c53030;
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-items: flex-start;
}

.error-box p {
  margin: 0;
  word-break: break-word;
}

.stats-box {
  background: #f0fff4;
  border: 1px solid #9ae6b4;
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.stat-row {
  display: flex;
  justify-content: space-between;
}

.stat-label {
  color: #4a5568;
}

.stat-value {
  font-weight: 600;
  color: #2d3748;
}

.delete-row .stat-value {
  color: #e53e3e;
}

.retain-row .stat-value {
  color: #38a169;
}
</style>
