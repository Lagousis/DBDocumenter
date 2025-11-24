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
              <div class="label-row">
                <span class="label">Short description</span>
                <button type="button" class="icon-button small" :disabled="generatingAI" title="Generate description with AI" @click="handleAutoDescribeShort">
                  <svg v-if="!generatingAI" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2">
                    <path d="M4 8.5h3.5L6 12.5l6-5h-3.5L10 3.5 4 8.5z" stroke-linejoin="round" />
                  </svg>
                  <span v-else class="spinner"></span>
                </button>
              </div>
              <input v-model="form.short_description" type="text" :disabled="generatingAI" />
            </label>

            <label class="block">
              <div class="label-row">
                <span class="label">Long description</span>
                <button type="button" class="icon-button small" :disabled="generatingAI" title="Generate description with AI" @click="handleAutoDescribe">
                  <svg v-if="!generatingAI" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2">
                    <path d="M4 8.5h3.5L6 12.5l6-5h-3.5L10 3.5 4 8.5z" stroke-linejoin="round" />
                  </svg>
                  <span v-else class="spinner"></span>
                </button>
              </div>
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
            </div>

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
                  <input v-model="rel.related_table" placeholder="Related table" list="table-suggestions" />
                  <input v-model="rel.related_field" placeholder="Related field" :list="'field-suggestions-' + idx" />
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
            
            <div v-if="loadingValues" class="loading-state">
              <span class="spinner"></span> Loading...
            </div>
            
            <div v-else-if="distinctValues.length === 0" class="empty-state">
              No values found.
            </div>
            
            <div v-else class="values-grid">
              <div v-for="val in distinctValues" :key="val" class="value-item">
                <span class="value-text" :title="val">{{ val }}</span>
                <button 
                  type="button" 
                  class="icon-button small add-btn" 
                  title="Add to allowed values"
                  @click="addValueFromGrid(val)"
                  :disabled="form.values.some(v => v.key === val)"
                >
                  +
                </button>
              </div>
            </div>
          </div>
        </div>

        <footer class="dialog-footer">
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
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import { autoDescribeField, runQuery, updateFieldMetadata } from "../api/client";
import { useSessionStore } from "../stores/session";
import type { AutoDescribeRequest, FieldUpdateRequest, RelationshipPayload } from "../types/api";

interface ValuePair {
  key: string;
  value: string;
}

interface RelationshipForm extends RelationshipPayload {}

interface FieldMetadata {
  name?: string;
  short_description?: string;
  long_description?: string;
  nullability?: string;
  data_type?: string;
  values?: Record<string, string>;
  relationships?: RelationshipPayload[];
}

interface RelationshipSuggestion {
  related_table: string;
  related_field: string;
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
});

const saving = ref(false);
const generatingAI = ref(false);
const showValuesPanel = ref(false);
const distinctValues = ref<string[]>([]);
const loadingValues = ref(false);

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
  try {
    const sql = `SELECT DISTINCT "${props.field}" FROM "${props.table}" LIMIT 100`;
    const response = await runQuery({
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
      sql,
    });
    if (response.rows) {
      distinctValues.value = response.rows.map((row) => String(row[0] ?? "NULL"));
    }
  } catch (e) {
    console.error("Failed to fetch distinct values", e);
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
  };

  try {
    await updateFieldMetadata(payload);
    emit("saved");
  } finally {
    saving.value = false;
  }
}

async function handleAutoDescribe() {
  if (!props.table || !props.field) {
    return;
  }
  if (form.long_description && form.long_description.trim()) {
    const confirmed = window.confirm("Replace the existing long description with an AI-generated one?");
    if (!confirmed) {
      return;
    }
  }
  generatingAI.value = true;
  try {
    const payload: AutoDescribeRequest = {
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
      table: props.table,
      field: form.field_name || props.field,
      current_short_description: form.short_description,
      current_long_description: form.long_description,
      data_type: form.data_type,
      description_type: 'long',
    };
    const response = await autoDescribeField(payload);
    if (response.description) {
      form.long_description = response.description;
    }
  } catch (error) {
    console.error("Failed to generate AI description:", error);
    alert("Failed to generate AI description. Please try again.");
  } finally {
    generatingAI.value = false;
  }
}

async function handleAutoDescribeShort() {
  if (!props.table || !props.field) {
    return;
  }
  if (form.short_description && form.short_description.trim()) {
    const confirmed = window.confirm("Replace the existing short description with an AI-generated one?");
    if (!confirmed) {
      return;
    }
  }
  generatingAI.value = true;
  try {
    const payload: AutoDescribeRequest = {
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
      table: props.table,
      field: form.field_name || props.field,
      current_short_description: form.short_description,
      current_long_description: form.long_description,
      data_type: form.data_type,
      description_type: 'short',
    };
    const response = await autoDescribeField(payload);
    if (response.description) {
      form.short_description = response.description;
    }
  } catch (error) {
    console.error("Failed to generate AI description:", error);
    alert("Failed to generate AI description. Please try again.");
  } finally {
    generatingAI.value = false;
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
  width: 300px;
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
</style>
