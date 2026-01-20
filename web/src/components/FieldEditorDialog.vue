<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel" :class="{ wide: showValuesPanel }">
        <header class="dialog-header">
          <div>
            <h3>{{ table }} · {{ field }}</h3>
            <p>Edit field metadata</p>
          </div>
          <button type="button" class="icon-button" @click="handleClose" aria-label="Close dialog">
            ×
          </button>
        </header>

        <div class="dialog-content">
          <div class="dialog-body">
            <label class="block">
              <span class="label">Field name</span>
              <input v-model="form.field_name" type="text" />
            </label>

            <label class="block">
              <span class="label">Short description</span>
              <input v-model="form.short_description" type="text" :disabled="generatingAI" />
            </label>

            <label class="block">
              <span class="label">Long description</span>
              <textarea v-model="form.long_description" rows="4" :disabled="generatingAI" />
            </label>

            <div class="grid two">
              <label class="block">
                <span class="label">Allow NULL values</span>
                <label class="switch">
                  <input v-model="form.allow_null" type="checkbox" />
                  <span class="switch-slider" />
                </label>
                <small class="muted inline">
                  {{ form.allow_null ? "nullable" : "not nullable" }}
                </small>
              </label>
              <label class="block">
                <span class="label">Ignore field</span>
                <label class="switch">
                  <input v-model="form.ignored" type="checkbox" />
                  <span class="switch-slider" />
                </label>
                <small class="muted inline">
                  {{ form.ignored ? "ignored" : "active" }}
                </small>
              </label>
            </div>

            <label class="block">
              <span class="label">Data type</span>
              <div class="data-type-select">
                <select v-model="form.data_type">
                  <option v-for="type in dataTypes" :key="type" :value="type || ''">
                    {{ type || "Select data type" }}
                  </option>
                </select>
                <svg class="data-type-select__icon" width="12" height="8" viewBox="0 0 12 8" fill="none">
                  <path d="M10.5 1.5L6 6 1.5 1.5" stroke="#9A6432" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </div>
            </label>

            <div class="block">
              <div class="label-row">
                <span class="label">Allowed values</span>
                <div class="button-group">
                  <button type="button" class="secondary-button" @click="addValue">Add value</button>
                  <button type="button" class="secondary-button" @click="toggleValuesPanel">
                    {{ showValuesPanel ? "Hide values" : "Show values" }}
                  </button>
                </div>
              </div>
              <div v-if="form.values.length" class="kv-list">
                <div v-for="(pair, idx) in form.values" :key="idx" class="kv-row">
                  <input v-model="pair.key" placeholder="Key" />
                  <input v-model="pair.value" placeholder="Description" />
                  <button type="button" class="icon-button small" @click="removeValue(idx)" aria-label="Remove value">&times;</button>
                </div>
              </div>
              <p v-else class="muted">No allowed values defined.</p>
            </div>

            <div class="block">
              <div class="label-row">
                <span class="label">Relationships</span>
                <button type="button" class="secondary-button" @click="addRelationship">Add relationship</button>
              </div>

              <div v-if="form.relationships.length" class="relationship-list">
                <div v-for="(rel, idx) in form.relationships" :key="idx" class="relationship-row">
                  <div class="input-wrapper">
                    <input v-model="rel.related_table" placeholder="Related table" list="table-suggestions" />
                    <button v-if="rel.related_table" type="button" class="clear-btn" @click="rel.related_table = ''" title="Clear table">×</button>
                  </div>
                  <div class="input-wrapper">
                    <input v-model="rel.related_field" placeholder="Related field" :list="'field-suggestions-' + idx" />
                    <button v-if="rel.related_field" type="button" class="clear-btn" @click="rel.related_field = ''" title="Clear field">×</button>
                  </div>
                  
                  <button 
                    type="button" 
                    class="icon-button small" 
                    title="Test relationship coverage"
                    @click="verifyRelationship(idx)"
                    :disabled="rel.verifying || !rel.related_table || !rel.related_field"
                  >
                    <span v-if="rel.verifying" class="spinner small"></span>
                    <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M8.5 2h7" />
                      <path d="M12 2v4" />
                      <path d="M18.42 20.22 12 6 5.58 20.22a2.2 2.2 0 0 0 2 1.78h8.84a2.2 2.2 0 0 0 2-1.78Z" />
                    </svg>
                  </button>

                  <button 
                    v-if="rel.coverage !== undefined" 
                    type="button"
                    class="coverage-badge" 
                    :class="[getCoverageClass(rel.coverage), { clickable: rel.coverage < 100 }]"
                    :title="rel.coverage < 100 ? 'Click to see unmatched values' : 'Full coverage'"
                    @click="showUnmatched(rel)"
                    :disabled="rel.coverage === 100"
                  >
                    {{ rel.coverage }}%
                  </button>

                  <span 
                    v-if="rel.error" 
                    class="error-badge" 
                    :title="rel.error"
                  >
                    {{ rel.error }}
                  </span>

                  <button type="button" class="icon-button small" @click="removeRelationship(idx)" aria-label="Remove relationship">&times;</button>
                </div>
              </div>
              <p v-else class="muted">No relationships recorded.</p>

              <div v-if="relationshipSuggestions.length" class="suggestion-chips">
                <span>Suggestions:</span>
                <button
                  v-for="suggestion in relationshipSuggestions"
                  :key="suggestionKey(suggestion)"
                  type="button"
                  class="chip"
                  @click="applySuggestion(suggestion)"
                >
                  {{ suggestion.related_table }} → {{ suggestion.related_field }}
                </button>
              </div>
            </div>
          </div>

          <div v-if="showValuesPanel" class="values-sidebar">
            <div class="sidebar-header">
              <h4>Distinct Values</h4>
              <button type="button" class="icon-button small" title="Refresh values" @click="fetchDistinctValues">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M11.5 7a4.5 4.5 0 1 1-1.318-3.182L11.5 5" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M11.5 2.5v2.5h-2.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </button>
            </div>
            
            <div v-if="!loadingValues && (nullCount !== null || emptyCount !== null || nonNullCount !== null)" class="stats-row">
              <div class="stat-item" v-if="nonNullCount !== null">
                <span class="stat-label">Non-NULL:</span>
                <span class="stat-value">{{ nonNullCount }}</span>
              </div>
              <div class="stat-item" v-if="nullCount !== null">
                <span class="stat-label">NULLs:</span>
                <span class="stat-value">{{ nullCount }}</span>
              </div>
              <div class="stat-item" v-if="emptyCount !== null">
                <span class="stat-label">Empty:</span>
                <span class="stat-value">{{ emptyCount }}</span>
              </div>
            </div>
            
            <div v-if="loadingValues" class="loading-state">
              <span class="spinner"></span> Loading...
            </div>
            
            <div v-else-if="distinctValues.length === 0" class="empty-state">
              No values found.
            </div>
            
            <div v-else class="values-grid">
              <div v-for="item in distinctValues" :key="item.value" class="value-item">
                <div class="value-content">
                  <span class="value-text" :title="item.value">{{ item.value }}</span>
                  <span class="value-count" title="Count">{{ item.count }}</span>
                </div>
                <button 
                  type="button" 
                  class="icon-button small add-btn" 
                  title="Add to allowed values"
                  @click="addValueFromGrid(item.value)"
                  :disabled="form.values.some(v => v.key === item.value)"
                >
                  +
                </button>
              </div>
            </div>
          </div>
        </div>

        <footer class="dialog-footer">
          <button type="button" class="secondary-button ai-button" :disabled="generatingAI" @click="handleAIAssist">
            <span>{{ generatingAI ? "Generating..." : "✨ AI Assist" }}</span>
          </button>
          <button v-if="generatingAI" type="button" class="secondary-button danger" @click="handleCancelAI">
            Stop
          </button>
          <button type="button" class="secondary-button danger" :disabled="saving || generatingAI" @click="handleDelete">Delete from schema</button>
          <div style="flex: 1;"></div>
          <button type="button" class="secondary-button" @click="handleClose">Cancel</button>
          <button type="button" class="secondary-button" :disabled="saving" @click="handleSave">
            {{ saving ? "Saving..." : "Save" }}
          </button>
        </footer>
      </div>

      <datalist id="table-suggestions">
        <option v-for="name in tableNames" :key="name" :value="name" />
      </datalist>
      <datalist v-for="(rel, idx) in form.relationships" :key="idx" :id="'field-suggestions-' + idx">
        <option v-for="fieldName in getFieldsForTable(rel.related_table)" :key="fieldName" :value="fieldName" />
      </datalist>

      <UnmatchedValuesDialog
        :visible="showUnmatchedDialog"
        :loading="unmatchedLoading"
        :values="unmatchedValues"
        :source-table="unmatchedSourceTable"
        :source-field="unmatchedSourceField"
        :target-table="unmatchedTargetTable"
        :target-field="unmatchedTargetField"
        @close="showUnmatchedDialog = false"
      />
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import { aiAssistField, cancelAIAssist, deleteField, runQuery, updateFieldMetadata } from "../api/client";
import { useSessionStore } from "../stores/session";
import type { AIAssistFieldRequest, FieldUpdateRequest, RelationshipPayload } from "../types/api";
import UnmatchedValuesDialog from "./UnmatchedValuesDialog.vue";

interface ValuePair {
  key: string;
  value: string;
}

interface RelationshipForm extends RelationshipPayload {
  coverage?: number;
  verifying?: boolean;
  error?: string;
}

interface FieldMetadata {
  name?: string;
  short_description?: string;
  long_description?: string;
  nullability?: string;
  data_type?: string;
  values?: Record<string, string>;
  relationships?: RelationshipPayload[];
  ignored?: boolean;
}

interface RelationshipSuggestion {
  related_table: string;
  related_field: string;
}

interface DistinctValue {
  value: string;
  count: number;
}

const props = defineProps<{
  visible: boolean;
  table: string;
  field: string;
  metadata: FieldMetadata | null;
  suggestions: RelationshipSuggestion[];
  tableNames: string[];
  fieldNames: string[];
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "saved"): void;
}>();

const sessionStore = useSessionStore();

  const form = reactive({
    field_name: "",
    short_description: "",
    long_description: "",
    data_type: "",
    values: [] as ValuePair[],
    relationships: [] as RelationshipForm[],
  allow_null: true,
  ignored: false,
});

const saving = ref(false);
const generatingAI = ref(false);
const showValuesPanel = ref(false);
const distinctValues = ref<DistinctValue[]>([]);
const loadingValues = ref(false);
const nullCount = ref<number | null>(null);
const emptyCount = ref<number | null>(null);
const nonNullCount = ref<number | null>(null);

const showUnmatchedDialog = ref(false);
const unmatchedValues = ref<{ value: string; count: number }[]>([]);
const unmatchedLoading = ref(false);
const unmatchedSourceTable = ref("");
const unmatchedSourceField = ref("");
const unmatchedTargetTable = ref("");
const unmatchedTargetField = ref("");

const relationshipSuggestions = computed(() => props.suggestions || []);

function getFieldsForTable(tableName: string): string[] {
  if (!tableName || !tableName.trim()) {
    return [];
  }
  const schema = sessionStore.schema;
  if (!schema || !schema.tables) {
    return [];
  }
  const tables = schema.tables as Record<string, any>;
  const table = tables[tableName];
  if (!table || !table.fields) {
    return [];
  }
  return Object.keys(table.fields).sort();
}

function getCoverageClass(coverage: number): string {
  if (coverage >= 90) return 'coverage-high';
  if (coverage >= 50) return 'coverage-medium';
  return 'coverage-low';
}

async function verifyRelationship(idx: number) {
  const rel = form.relationships[idx];
  if (!rel.related_table || !rel.related_field) return;

  rel.verifying = true;
  rel.coverage = undefined;
  rel.error = undefined;

  const sourceTable = props.table;
  const sourceField = props.field;
  const targetTable = rel.related_table;
  const targetField = rel.related_field;

// Construct SQL to check coverage
  // We want to know what % of total non-null/non-empty rows in source exist in target
  // We cast both sides to VARCHAR to avoid type mismatch errors (e.g. BIGINT vs VARCHAR)
  const sql = `
    SELECT 
      COUNT(*) as total_rows,
      COUNT(CASE WHEN CAST("${sourceField}" AS VARCHAR) IN (
        SELECT CAST("${targetField}" AS VARCHAR) FROM "${targetTable}" WHERE "${targetField}" IS NOT NULL
      ) THEN 1 END) as matched_count
    FROM "${sourceTable}"
    WHERE "${sourceField}" IS NOT NULL AND CAST("${sourceField}" AS VARCHAR) != ''
  `;  try {
    const result = await runQuery({
      sql,
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase
    });

    if (result.rows && result.rows.length > 0) {
      const total = Number(result.rows[0][0]);
      const matched = Number(result.rows[0][1]);
      
      if (total > 0) {
        if (matched === total) {
          rel.coverage = 100;
        } else {
          // Calculate percentage with 1 decimal place, ensuring we don't round up to 100
          // if there are any mismatches (e.g. 99.99% should show as 99.9%)
          const pct = (matched / total) * 100;
          rel.coverage = Math.floor(pct * 10) / 10;
        }
      } else {
        rel.coverage = 0;
      }
    }
  } catch (e: any) {
    console.error("Verification failed", e);
    const errorMessage = e.response?.data?.detail || e.message || String(e);
    if (errorMessage.includes("Binder Error: Cannot compare values")) {
      rel.error = "Incompatible fields";
    }
  } finally {
    rel.verifying = false;
  }
}

async function showUnmatched(rel: RelationshipForm) {
  if (!rel.related_table || !rel.related_field || rel.coverage === undefined || rel.coverage === 100) return;

  unmatchedSourceTable.value = props.table;
  unmatchedSourceField.value = props.field;
  unmatchedTargetTable.value = rel.related_table;
  unmatchedTargetField.value = rel.related_field;
  unmatchedValues.value = [];
  showUnmatchedDialog.value = true;
  unmatchedLoading.value = true;

  try {
    const sql = `
      SELECT "${props.field}", COUNT(*) as count
      FROM "${props.table}"
      WHERE "${props.field}" IS NOT NULL 
        AND CAST("${props.field}" AS VARCHAR) != ''
        AND CAST("${props.field}" AS VARCHAR) NOT IN (
          SELECT CAST("${rel.related_field}" AS VARCHAR)
          FROM "${rel.related_table}"
          WHERE "${rel.related_field}" IS NOT NULL
        )
      GROUP BY "${props.field}"
      ORDER BY count DESC
      LIMIT 100
    `;    const result = await runQuery({
      sql,
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase
    });

    if (result.rows) {
      unmatchedValues.value = result.rows.map(row => ({
        value: String(row[0]),
        count: Number(row[1])
      }));
    }
  } catch (e) {
    console.error("Failed to fetch unmatched values", e);
  } finally {
    unmatchedLoading.value = false;
  }
}

const DATA_TYPES = [
  "",
  "BOOLEAN",
  "TINYINT",
  "SMALLINT",
  "INTEGER",
  "BIGINT",
  "HUGEINT",
  "UTINYINT",
  "USMALLINT",
  "UINTEGER",
  "UBIGINT",
  "FLOAT",
  "DOUBLE",
  "DECIMAL",
  "VARCHAR",
  "BLOB",
  "DATE",
  "TIME",
  "TIMESTAMP",
  "TIMESTAMP_TZ",
  "TIMESTAMP_S",
  "TIMESTAMP_MS",
  "TIMESTAMP_NS",
  "UUID",
  "JSON",
  "LIST",
  "STRUCT",
  "MAP",
];
const dataTypes = DATA_TYPES;

watch(
  () => props.metadata,
  (metadata) => {
    form.field_name = props.field;
    form.short_description = metadata?.short_description ?? "";
    form.long_description = metadata?.long_description ?? "";
    form.data_type = metadata?.data_type ?? "";
    form.values =
      metadata && metadata.values
        ? Object.entries(metadata.values).map(([key, value]) => ({ key, value }))
        : [];
    form.relationships =
      metadata && metadata.relationships
        ? metadata.relationships.map((rel) => ({
            related_table: rel.related_table,
            related_field: rel.related_field,
            type: rel.type ?? null,
          }))
        : [];
    form.allow_null = inferAllowNull(metadata?.nullability);
    form.ignored = metadata?.ignored ?? false;
    
    // Reset values panel state when field changes
    showValuesPanel.value = false;
    distinctValues.value = [];
  },
  { immediate: true },
);

function inferAllowNull(value: string | undefined): boolean {
  if (!value) {
    return true;
  }
  const text = value.toLowerCase();
  if (text.includes("not") && text.includes("nullable")) {
    return false;
  }
  if (text.includes("no") && text.includes("null")) {
    return false;
  }
  return true;
}

function addValue() {
  form.values.push({ key: "", value: "" });
}

async function toggleValuesPanel() {
  showValuesPanel.value = !showValuesPanel.value;
  if (showValuesPanel.value && distinctValues.value.length === 0) {
    await fetchDistinctValues();
  }
}

async function fetchDistinctValues() {
  if (!props.table || !props.field) return;
  loadingValues.value = true;
  nullCount.value = null;
  emptyCount.value = null;
  nonNullCount.value = null;

  try {
    const sqlDistinct = `
      SELECT "${props.field}", COUNT(*) as count 
      FROM "${props.table}" 
      GROUP BY "${props.field}" 
      ORDER BY count DESC 
      LIMIT 100
    `;
    const sqlCounts = `
      SELECT 
        SUM(CASE WHEN "${props.field}" IS NOT NULL THEN 1 ELSE 0 END) as non_null_count,
        SUM(CASE WHEN "${props.field}" IS NULL THEN 1 ELSE 0 END) as null_count,
        SUM(CASE WHEN CAST("${props.field}" AS VARCHAR) = '' THEN 1 ELSE 0 END) as empty_count
      FROM "${props.table}"
    `;

    const [distinctRes, countsRes] = await Promise.all([
      runQuery({
        project: sessionStore.activeProject,
        database: sessionStore.activeDatabase,
        sql: sqlDistinct,
      }),
      runQuery({
        project: sessionStore.activeProject,
        database: sessionStore.activeDatabase,
        sql: sqlCounts,
      })
    ]);

    if (distinctRes.rows) {
      distinctValues.value = distinctRes.rows.map((row) => ({
        value: String(row[0] ?? "NULL"),
        count: Number(row[1] ?? 0)
      }));
    }

    if (countsRes.rows && countsRes.rows.length > 0) {
      nonNullCount.value = Number(countsRes.rows[0][0]);
      nullCount.value = Number(countsRes.rows[0][1]);
      emptyCount.value = Number(countsRes.rows[0][2]);
    }
  } catch (e) {
    console.error("Failed to fetch values", e);
  } finally {
    loadingValues.value = false;
  }
}

function addValueFromGrid(val: string) {
  if (!form.values.some((v) => v.key === val)) {
    form.values.push({ key: val, value: "" });
  }
}

function removeValue(index: number) {
  form.values.splice(index, 1);
}

function addRelationship() {
  form.relationships.push({
    related_table: "",
    related_field: "",
    type: null,
  });
}

function removeRelationship(index: number) {
  form.relationships.splice(index, 1);
}

function applySuggestion(suggestion: RelationshipSuggestion) {
  form.relationships.push({
    related_table: suggestion.related_table,
    related_field: suggestion.related_field,
    type: null,
  });
}

function suggestionKey(suggestion: RelationshipSuggestion): string {
  return `${suggestion.related_table}.${suggestion.related_field}`;
}

async function handleSave() {
  if (!props.table || !props.field) {
    return;
  }
  saving.value = true;
  const valuesObject: Record<string, string> | undefined =
    form.values.length > 0
      ? form.values
          .filter((pair) => pair.key.trim())
          .reduce<Record<string, string>>((acc, pair) => {
            acc[pair.key.trim()] = pair.value.trim();
            return acc;
          }, {})
      : undefined;

  const payload: FieldUpdateRequest = {
    project: sessionStore.activeProject,
    database: sessionStore.activeDatabase,
    table: props.table,
    field: props.field,
    new_field_name: form.field_name?.trim() || undefined,
    short_description: form.short_description ?? undefined,
    long_description: form.long_description ?? undefined,
    nullability: form.allow_null ? "nullable" : "not nullable",
    allow_null: form.allow_null,
    data_type: form.data_type || undefined,
    values: valuesObject,
    relationships: form.relationships.map((rel) => ({
      related_table: rel.related_table,
      related_field: rel.related_field,
      type: rel.type || undefined,
    })),
    ignored: form.ignored,
  };

  try {
    await updateFieldMetadata(payload);
    emit("saved");
  } finally {
    saving.value = false;
  }
}

async function handleAIAssist() {
  if (!props.table || !props.field) {
    return;
  }
  
  generatingAI.value = true;
  try {
    const payload: AIAssistFieldRequest = {
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
      table: props.table,
      field: form.field_name || props.field,
    };
    const response = await aiAssistField(payload);
    
    // Update all fields
    if (response.short_description) {
      form.short_description = response.short_description;
    }
    if (response.long_description) {
      form.long_description = response.long_description;
    }
    if (response.data_type) {
      form.data_type = response.data_type;
    }
    if (response.nullable !== undefined) {
      form.allow_null = response.nullable;
    }
  } catch (error) {
    console.error("Failed to generate AI assist:", error);
    alert("Failed to generate AI assist. Please try again.");
  } finally {
    generatingAI.value = false;
  }
}

async function handleCancelAI() {
  try {
    await cancelAIAssist();
    console.log("AI assist cancelled");
  } catch (error) {
    console.error("Failed to cancel AI assist:", error);
  }
}

async function handleDelete() {
  if (!props.table || !props.field) return;
  if (!window.confirm(`Are you sure you want to delete the field "${props.field}" from the schema documentation for table "${props.table}"? This will NOT remove the column from the database, only from the documentation.`)) {
    return;
  }
  saving.value = true;
  try {
    await deleteField(props.table, props.field, {
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
    });
    emit("saved");
    emit("close");
  } catch (error) {
    console.error("Failed to delete field:", error);
    alert("Failed to delete field. Please try again.");
  } finally {
    saving.value = false;
  }
}

function handleClose() {
  emit("close");
}
</script>

<style scoped>
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
  transition: width 0.3s ease;
}

.dialog-panel.wide {
  width: min(960px, 100%);
}

.dialog-content {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.dialog-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
  flex: 1;
}

.values-sidebar {
  width: 380px;
  border-left: 1px solid rgba(178, 106, 69, 0.2);
  background: rgba(253, 248, 241, 0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(178, 106, 69, 0.15);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-header h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #4f4035;
}

.values-grid {
  padding: 0.75rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.value-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.4rem 0.6rem;
  background: #fff;
  border: 1px solid rgba(178, 106, 69, 0.15);
  border-radius: 8px;
  font-size: 0.85rem;
}

.value-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #5c4b3f;
}

.add-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  font-size: 1.1rem;
  line-height: 1;
  padding: 0;
}

.loading-state, .empty-state {
  padding: 2rem;
  text-align: center;
  color: #8a7b6f;
  font-size: 0.9rem;
}

.button-group {
  display: flex;
  gap: 0.5rem;
}

.dialog-footer {
  padding: 0.9rem 1.25rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  border-top: 1px solid rgba(178, 106, 69, 0.18);
  background: rgba(253, 248, 241, 0.9);
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

.label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.data-type-select {
  position: relative;
  display: flex;
  align-items: center;
  background: #fdf8f1;
  border-radius: 18px;
  border: 1px solid #dfd2c6;
  padding: 0.25rem 0.6rem;
}

.data-type-select select {
  border: none;
  background: transparent;
  color: #4f4035;
  font-weight: 600;
  font-size: 0.95rem;
  flex: 1;
  padding: 0;
  appearance: none;
}

.data-type-select select:focus {
  outline: none;
}

.data-type-select__icon {
  position: absolute;
  right: 0.8rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}

input,
textarea {
  border: 1px solid rgba(178, 106, 69, 0.3);
  border-radius: 10px;
  padding: 0.5rem 0.65rem;
  font-size: 0.9rem;
  background: #fefbf6;
  color: #3d3129;
}

textarea {
  resize: vertical;
}

.grid.two {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.switch {
  position: relative;
  display: inline-flex;
  width: 44px;
  height: 22px;
  margin-top: 0.35rem;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.switch-slider {
  position: absolute;
  inset: 0;
  background-color: rgba(178, 106, 69, 0.35);
  border-radius: 999px;
  transition: background-color 0.2s ease;
}

.switch-slider::before {
  content: "";
  position: absolute;
  left: 3px;
  top: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 2px 4px rgba(47, 38, 32, 0.2);
  transition: transform 0.2s ease;
}

.switch input:checked + .switch-slider {
  background: linear-gradient(135deg, #b26a45, #d89b6c);
}

.switch input:checked + .switch-slider::before {
  transform: translateX(22px);
}

.muted.inline {
  display: block;
}

.kv-list,
.relationship-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.kv-row,
.relationship-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.35rem;
  align-items: center;
}

.relationship-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto auto auto;
  gap: 0.35rem;
  align-items: center;
}

.coverage-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  margin-left: 4px;
  min-width: 32px;
  height: 24px;
  border-style: solid;
  border-width: 1px;
  cursor: default;
}

.coverage-badge.clickable {
  cursor: pointer;
  text-decoration: underline;
}

.coverage-badge.clickable:hover {
  opacity: 0.8;
}

.coverage-high {
  background-color: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.coverage-medium {
  background-color: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
}

.coverage-low {
  background-color: #fee2e2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}

.error-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  margin-left: 4px;
  height: 24px;
  border: 1px solid #fecaca;
  background-color: #fee2e2;
  color: #b91c1c;
  cursor: help;
}

.muted {
  color: #8a7b6f;
  font-size: 0.85rem;
}

.icon-button {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(178, 106, 69, 0.28);
  background: rgba(253, 248, 241, 0.92);
  color: #b26a45;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}

.icon-button.small {
  width: 28px;
  height: 28px;
  font-size: 1rem;
}

.icon-button:hover {
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 4px 12px rgba(178, 106, 69, 0.18);
}

.icon-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  box-shadow: none;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(178, 106, 69, 0.3);
  border-top-color: #b26a45;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
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
  color: #dc2626;
  border-color: #fca5a5;
}

.secondary-button.danger:hover {
  background-color: #dc2626;
  border-color: #dc2626;
  color: #ffffff;
}

.secondary-button.full-width {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
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

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #7a6a5d;
}

.chip {
  border: 1px solid rgba(178, 106, 69, 0.3);
  border-radius: 999px;
  padding: 0.2rem 0.6rem;
  background: rgba(253, 248, 241, 0.9);
  color: #a05736;
  cursor: pointer;
  font-size: 0.8rem;
}

.chip:hover {
  background: rgba(255, 255, 255, 0.98);
}

.stats-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.75rem;
  padding: 0.5rem;
  background: rgba(178, 106, 69, 0.05);
  border-radius: 6px;
  font-size: 0.85rem;
}

.stat-item {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

.stat-label {
  color: #8a7b6f;
  font-weight: 500;
}

.stat-value {
  color: #4f4035;
  font-weight: 600;
  font-family: monospace;
}

.value-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 1;
  min-width: 0;
  gap: 0.5rem;
}

.value-count {
  color: #8a7b6f;
  font-size: 0.75rem;
  background: rgba(178, 106, 69, 0.1);
  padding: 1px 6px;
  border-radius: 99px;
  flex-shrink: 0;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-wrapper input {
  width: 100%;
  padding-right: 24px;
}

.clear-btn {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #8a7b6f;
  font-size: 1.2rem;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.clear-btn:hover {
  color: #b26a45;
  background-color: rgba(178, 106, 69, 0.1);
}
</style>
