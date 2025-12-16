<template>
  <div class="schema-sidebar">
    <div class="sidebar-header">
      <h2 class="section-title">
        Schema
        <span v-if="tables.length" class="count-badge">({{ tables.length }} tables)</span>
      </h2>
    </div>

    <p v-if="!hasSelection" class="empty-state">Select a project to browse its tables and documentation.</p>
    <p v-else-if="tables.length === 0" class="empty-state">
      No documented tables yet. Use the CLI or chat assistant to document your schema.
    </p>

    <div v-else class="schema-content">
      <div class="table-picker">
        <div class="picker-input">
          <input
            ref="searchInput"
            v-model="searchTerm"
            type="text"
            placeholder="Search table..."
            @focus="openDropdown"
            @input="openDropdown"
            @blur="scheduleClose"
          />
          <button
            v-if="searchTerm"
            type="button"
            class="picker-clear"
            @mousedown.prevent="clearSelection"
            aria-label="Clear table selection"
          >
            &times;
          </button>
          <button type="button" class="picker-toggle" @mousedown.prevent="toggleDropdown">
            <span v-if="showDropdown">&#9650;</span>
            <span v-else>&#9660;</span>
          </button>
        </div>
        <ul v-if="showDropdown" class="picker-options">
          <li v-for="table in filteredTables" :key="table" :class="{ active: isSelected(table) }">
            <button type="button" @mousedown.prevent="handleSelect(table)">
              {{ table }}
            </button>
          </li>
          <li v-if="filteredTables.length === 0" class="empty">No matches found.</li>
        </ul>
      </div>

      <div v-if="selectedDetails" class="table-details">
        <div class="table-header">
          <h3>
            {{ selectedDetails.name }}
            <span class="coverage-chip" :class="getCoverageClass(documentationCoverage)" title="Documentation Coverage">
              {{ documentationCoverage }}%
            </span>
          </h3>
          <div class="table-header-actions">
            <button
              type="button"
              class="icon-button small"
              title="Edit table name and description"
              @click="openTableEditor"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 18 18"
                fill="none"
                stroke="currentColor"
                stroke-width="1.4"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M12.5 3.5l2 2-7 7H5.5v-2l7-7z" />
                <path d="M11.5 4.5l2 2" />
              </svg>
            </button>
            <button
              type="button"
              class="icon-button small"
              title="Open a new ER diagram for this table"
              @click="showDiagramForTable"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 18 18"
                fill="none"
                stroke="currentColor"
                stroke-width="1.4"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <rect x="3" y="5" width="12" height="8" rx="1.8" />
                <line x1="6" y1="8.5" x2="12" y2="8.5" />
                <line x1="6" y1="10.8" x2="9.5" y2="10.8" />
                <line x1="9" y1="2.5" x2="9" y2="6.5" />
                <line x1="7" y1="4.5" x2="11" y2="4.5" />
              </svg>
            </button>
            <button
              type="button"
              class="icon-button small"
              :title="
                canAddToCurrentDiagram
                  ? 'Add this table to the current diagram tab'
                  : 'Open a diagram tab to add this table'
              "
              :disabled="!canAddToCurrentDiagram"
              @click="addTableToCurrentDiagram"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 18 18"
                fill="none"
                stroke="currentColor"
                stroke-width="1.4"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <rect x="3.2" y="4.2" width="5.8" height="5.8" rx="1.2" />
                <rect x="9" y="9.2" width="5.8" height="5.8" rx="1.2" />
                <path d="M9 9.2l-2-2" />
                <path d="M11.5 3.5v3.5" />
                <path d="M9.8 5.25h3.5" />
              </svg>
            </button>
          </div>
        </div>
        <p v-if="diagramActionError" class="diagram-action-error" role="alert">
          {{ diagramActionError }}
        </p>
        <p v-if="selectedDetails.data?.short_description" class="summary">
          {{ selectedDetails.data.short_description }}
        </p>
        <p v-if="selectedDetails.data?.long_description" class="description">
          {{ selectedDetails.data.long_description }}
        </p>

        <section class="fields">
          <div class="fields-header">
            <h4>Fields</h4>
            <div class="field-search">
              <input
                v-model="fieldSearchTerm"
                type="text"
                placeholder="Search field..."
                aria-label="Search fields"
              />
              <button
                v-if="fieldSearchTerm"
                type="button"
                class="field-search-clear"
                @click="fieldSearchTerm = ''"
                aria-label="Clear field search"
              >
                &times;
              </button>
            </div>
            <div class="fields-actions">
              <button
                type="button"
                class="icon-button small"
                title="Refresh fields"
                @click="refreshFields"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M23 4v6h-6" />
                  <path d="M1 20v-6h6" />
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                </svg>
              </button>
              <button
                type="button"
                class="icon-button small"
                title="Generate sample query (key columns)"
                @click="generateQuery(false)"
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.4">
                  <rect x="3.5" y="4" width="11" height="10" rx="1.5" />
                  <line x1="6.5" y1="4" x2="6.5" y2="14" />
                  <line x1="11.5" y1="8" x2="11.5" y2="14" />
                </svg>
              </button>
              <button
                type="button"
                class="icon-button small"
                title="Generate full query (all columns)"
                @click="generateQuery(true)"
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.4">
                  <rect x="3.5" y="4" width="11" height="10" rx="1.5" />
                  <line x="6.5" y1="4" x2="6.5" y2="14" />
                  <line x1="9" y1="4" x2="9" y2="14" />
                  <line x1="11.5" y1="4" x2="11.5" y2="14" />
                </svg>
              </button>
            </div>
          </div>

          <div v-if="undocumentedFields.length" class="undocumented">
            <span class="undocumented-label">Undocumented fields in database</span>
              <div class="undocumented-chips">
                <button
                v-for="field in filteredUndocumentedFields"
                  :key="`undoc-${field.name}`"
                  type="button"
                  class="undocumented-chip"
                  @click="openEditor(field.name, field.data_type)"
                >
                {{ field.name }}
              </button>
            </div>
          </div>

          <div v-if="fields.length > 0" class="field-list">
            <article v-for="field in fields" :key="field.name" class="field-card">
              <header>
                <span class="field-name">{{ field.name }}</span>
                <span class="field-type">{{ field.type || "UNKNOWN" }}</span>
                <button
                  type="button"
                  class="icon-button small"
                  title="Edit field metadata"
                  @click="openEditor(field.name, field.type)"
                >
                  &#9998;
                </button>
              </header>
              <p v-if="field.short" class="field-short">{{ field.short }}</p>
              <p v-if="field.long" class="field-long">{{ field.long }}</p>
              <ul v-if="field.values" class="field-values">
                <li v-for="(label, key) in field.values" :key="`${field.name}-${key}`">
                  <strong>{{ key }}:</strong> {{ label }}
                </li>
              </ul>
              <div v-if="field.relationships.length" class="field-relationships">
                <span class="field-rel-label">Relationships</span>
                <div class="field-rel-list">
                  <span v-for="rel in field.relationships" :key="rel.key" class="field-rel-chip">
                    {{ rel.target }}
                  </span>
                </div>
              </div>
              <footer>
                <span>{{ field.nullability || "nullable" }}</span>
              </footer>
            </article>
          </div>

          <div v-if="ignoredFields.length > 0" class="undocumented">
            <span class="undocumented-label">Ignored Fields</span>
            <div class="undocumented-chips">
              <button
                v-for="field in ignoredFields"
                :key="`ignored-${field.name}`"
                type="button"
                class="undocumented-chip ignored"
                @click="openEditor(field.name, field.type)"
              >
                {{ field.name }}
              </button>
            </div>
          </div>

          <p v-if="fields.length === 0 && ignoredFields.length === 0" class="empty-state subtle">No documented fields yet.</p>
        </section>
      </div>
      <div v-else class="empty-state secondary">Select a table to view its fields.</div>
    </div>

    <FieldEditorDialog
      :visible="isEditorOpen"
      :table="selectedDetails?.name ?? ''"
      :field="editorField ?? ''"
      :metadata="editorMetadata"
      :suggestions="relationshipSuggestionsForEditor"
      :table-names="tableNames"
      :field-names="fieldNames"
      @close="handleEditorClose"
      @saved="handleEditorSaved"
    />

    <TableEditorDialog
      :visible="isTableEditorOpen"
      :table="selectedDetails?.name ?? ''"
      @update:visible="isTableEditorOpen = $event"
      @saved="handleTableEditorSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, nextTick, ref, watch } from "vue";

import { fetchUndocumentedFields } from "../api/client";
import { useSessionStore, type DiagramTabState } from "../stores/session";
import type { RelationshipPayload, UndocumentedField } from "../types/api";
import FieldEditorDialog from "./FieldEditorDialog.vue";
import TableEditorDialog from "./TableEditorDialog.vue";

interface FieldMetadata {
  short_description?: string;
  long_description?: string;
  nullability?: string;
  data_type?: string;
  values?: Record<string, string>;
  relationships?: RelationshipPayload[];
  ignored?: boolean;
}

const sessionStore = useSessionStore();
const {
  tables,
  activeProject,
  selectedTable,
  selectedTableDetails,
} = storeToRefs(sessionStore);

const hasSelection = computed(() => Boolean(activeProject.value));
const selectedDetails = computed(() => selectedTableDetails.value);
const searchTerm = ref("");
const showDropdown = ref(false);
const searchInput = ref<HTMLInputElement | null>(null);
let closeTimer: number | undefined;

const isEditorOpen = ref(false);
const editorField = ref<string | null>(null);
const editorMetadata = ref<FieldMetadata | null>(null);
const undocumentedFields = ref<UndocumentedField[]>([]);
const fieldSearchTerm = ref("");

const isTableEditorOpen = ref(false);

const fields = computed(() => {
  const details = selectedDetails.value?.data;
  if (!details || !details.fields) {
    return [];
  }
  const tableRelationships = Array.isArray(details.relationships) ? details.relationships : [];
  const allFields = Object.entries(details.fields as Record<string, any>).map(([name, meta]) => ({
    name,
    short: meta?.short_description ?? "",
    long: meta?.long_description ?? "",
    type: meta?.data_type ?? "",
    nullability: meta?.nullability ?? "",
    ignored: meta?.ignored ?? false,
    values: Object.keys(meta?.values ?? {}).length ? meta?.values : null,
    relationships: tableRelationships
      .filter((rel: Record<string, any>) => (rel.field ?? "").toLowerCase() === name.toLowerCase())
      .map((rel: Record<string, any>, idx: number) => ({
        key: `${name}-${rel.related_table}-${rel.related_field}-${idx}`,
        target: `${rel.related_table ?? ""}.${rel.related_field ?? ""}`,
      })),
  }));

  const needle = fieldSearchTerm.value.trim().toLowerCase();
  if (!needle) {
    return allFields.filter(f => !f.ignored);
  }
  return allFields.filter((field) => !field.ignored && field.name.toLowerCase().includes(needle));
});

const ignoredFields = computed(() => {
  const details = selectedDetails.value?.data;
  if (!details || !details.fields) {
    return [];
  }
  const allFields = Object.entries(details.fields as Record<string, any>).map(([name, meta]) => ({
    name,
    short: meta?.short_description ?? "",
    long: meta?.long_description ?? "",
    type: meta?.data_type ?? "",
    nullability: meta?.nullability ?? "",
    ignored: meta?.ignored ?? false,
  }));

  const needle = fieldSearchTerm.value.trim().toLowerCase();
  if (!needle) {
    return allFields.filter(f => f.ignored);
  }
  return allFields.filter((field) => field.ignored && field.name.toLowerCase().includes(needle));
});

const filteredUndocumentedFields = computed(() => {
  if (!fieldSearchTerm.value.trim()) {
    return undocumentedFields.value;
  }
  const needle = fieldSearchTerm.value.trim().toLowerCase();
  return undocumentedFields.value.filter((field) => field.name.toLowerCase().includes(needle));
});

const filteredTables = computed(() => {
  if (!searchTerm.value.trim()) {
    return tables.value;
  }
  const needle = searchTerm.value.toLowerCase();
  return tables.value.filter((item) => item.toLowerCase().includes(needle));
});

const documentationCoverage = computed(() => {
  const details = selectedDetails.value?.data;
  if (!details) return 0;

  const documentedCount = Object.keys(details.fields || {}).length;
  const undocumentedCount = undocumentedFields.value.length;
  const totalCount = documentedCount + undocumentedCount;

  if (totalCount === 0) return 0;
  return Math.round((documentedCount / totalCount) * 100);
});

const schemaTables = computed(() => (sessionStore.schema?.tables as Record<string, any>) || {});
const tableNames = computed(() => Object.keys(schemaTables.value || {}).sort());
const fieldNames = computed(() => {
  const names = new Set<string>();
  Object.values(schemaTables.value).forEach((table: any) => {
    Object.keys(table.fields || {}).forEach((field) => names.add(field));
  });
  return Array.from(names).sort();
});
const diagramActionError = ref("");
const activeDiagramTab = computed<DiagramTabState | null>(() => {
  const activeTab = sessionStore.activeWorkspaceTab;
  return activeTab && activeTab.type === "diagram" ? activeTab : null;
});
const canAddToCurrentDiagram = computed(() => Boolean(activeDiagramTab.value));

async function loadUndocumented(tableName?: string | null) {
  if (!tableName) {
    undocumentedFields.value = [];
    return;
  }
  try {
    undocumentedFields.value = await fetchUndocumentedFields({
      table: tableName,
      project: sessionStore.activeProject,
      database: sessionStore.activeDatabase,
    });
  } catch (error) {
    console.error("Failed to load undocumented fields", error);
    undocumentedFields.value = [];
  }
}

const relationshipSuggestionsForEditor = computed(() => {
  if (!editorField.value) {
    return [];
  }
  const suggestions: { related_table: string; related_field: string }[] = [];
  const target = editorField.value.toLowerCase();
  for (const [tableName, tableData] of Object.entries(schemaTables.value)) {
    if (tableName === selectedDetails.value?.name) {
      continue;
    }
    Object.keys(tableData.fields || {}).forEach((fieldName) => {
      if (fieldName.toLowerCase() === target) {
        suggestions.push({ related_table: tableName, related_field: fieldName });
      }
    });
  }
  return suggestions.sort((a, b) => 
    a.related_table.localeCompare(b.related_table) || 
    a.related_field.localeCompare(b.related_field)
  );
});

watch(
  selectedTable,
  (value) => {
    searchTerm.value = value ?? "";
  },
  { immediate: true },
);

watch(
  selectedDetails,
  (newDetails, oldDetails) => {
    if (newDetails?.name !== oldDetails?.name) {
      fieldSearchTerm.value = "";
      diagramActionError.value = "";
    }
    loadUndocumented(newDetails?.name);
  },
  { immediate: true },
);

watch(
  () => activeDiagramTab.value?.id,
  () => {
    diagramActionError.value = "";
  },
);

function resolveTableName(name?: string | null): string | undefined {
  if (!name) {
    return undefined;
  }
  const lower = name.toLowerCase();
  const match = tableNames.value.find((entry) => entry.toLowerCase() === lower);
  return match ?? name;
}

function getCoverageClass(percentage: number): string {
  if (percentage >= 100) return "high";
  if (percentage >= 50) return "medium";
  return "low";
}

function selectTable(name: string | undefined) {
  sessionStore.selectTable(name);
}

function isSelected(name: string): boolean {
  if (!selectedTable.value) {
    return false;
  }
  return selectedTable.value.toLowerCase() === name.toLowerCase();
}

function handleSelect(name: string) {
  selectTable(name);
  searchTerm.value = name;
  closeDropdown();
}

function openDropdown() {
  if (closeTimer) {
    window.clearTimeout(closeTimer);
    closeTimer = undefined;
  }
  showDropdown.value = true;
}

function scheduleClose() {
  closeTimer = window.setTimeout(() => {
    closeDropdown();
  }, 120);
}

function closeDropdown() {
  if (closeTimer) {
    window.clearTimeout(closeTimer);
    closeTimer = undefined;
  }
  showDropdown.value = false;
}

function toggleDropdown() {
  if (showDropdown.value) {
    closeDropdown();
    return;
  }
  openDropdown();
  nextTick(() => {
    searchInput.value?.focus();
  });
}

function clearSelection() {
  searchTerm.value = "";
  fieldSearchTerm.value = "";
  selectTable(undefined);
  openDropdown();
  undocumentedFields.value = [];
}

function openEditor(fieldName: string, fieldType?: string | null) {
  editorField.value = fieldName;
  const fieldsRecord = (selectedDetails.value?.data?.fields ?? {}) as Record<string, FieldMetadata>;
  const tableRelationships = (selectedDetails.value?.data?.relationships ?? []) as Array<Record<string, any>>;
  const existing = fieldsRecord[fieldName];
  const fieldLower = fieldName.toLowerCase();

  const relatedRelationships = tableRelationships
    .filter((rel) => typeof rel?.field === "string" && rel.field.toLowerCase() === fieldLower)
    .map((rel) => ({
      related_table: rel.related_table ?? "",
      related_field: rel.related_field ?? "",
      type: rel.type ?? null,
    }));

  let metadata: FieldMetadata | null = existing ? { ...existing } : null;

  const normalisedType = fieldType?.trim();
  if (metadata) {
    if (!metadata.data_type && normalisedType) {
      metadata = { ...metadata, data_type: normalisedType };
    }
    if (relatedRelationships.length) {
      metadata = { ...metadata, relationships: relatedRelationships };
    }
  } else {
    const baseMetadata: FieldMetadata = {};
    if (normalisedType) {
      baseMetadata.data_type = normalisedType;
    }
    if (relatedRelationships.length) {
      baseMetadata.relationships = relatedRelationships;
    }
    metadata = Object.keys(baseMetadata).length ? baseMetadata : null;
  }

  editorMetadata.value = metadata;
  isEditorOpen.value = true;
}

function showDiagramForTable() {
  const tableName = selectedDetails.value?.name;
  if (!tableName) {
    return;
  }
  sessionStore.createDiagramTabForTable(tableName);
}

function addTableToCurrentDiagram() {
  diagramActionError.value = "";
  const tableName = resolveTableName(selectedDetails.value?.name);
  const diagramTab = activeDiagramTab.value;
  if (!tableName || !diagramTab) {
    return;
  }
  const added = sessionStore.addTableToDiagram(diagramTab.id, tableName);
  if (!added) {
    diagramActionError.value = `${tableName} is already part of the current diagram.`;
    return;
  }
  sessionStore.selectDiagramTable(diagramTab.id, tableName);
}

function handleEditorClose() {
  isEditorOpen.value = false;
  editorField.value = null;
  editorMetadata.value = null;
}

async function handleEditorSaved() {
  await sessionStore.refreshMetadata();
  handleEditorClose();
  await loadUndocumented(selectedDetails.value?.name);
}

function openTableEditor() {
  isTableEditorOpen.value = true;
}

async function handleTableEditorSaved() {
  await sessionStore.refreshMetadata();
}

async function refreshFields() {
  if (!selectedDetails.value?.name) return;
  await sessionStore.refreshMetadata();
  await loadUndocumented(selectedDetails.value.name);
}

function generateQuery(includeAll: boolean) {
  if (!selectedDetails.value) {
    return;
  }
  const tableName = selectedDetails.value.name;
  if (!tableName) {
    return;
  }
  const documentedFields = fields.value.map((field) => field.name).filter(Boolean);
  const undocumented = (undocumentedFields.value ?? [])
    .map((item) => item.name)
    .filter((name): name is string => Boolean(name));

  const combined = Array.from(
    new Set<string>([...documentedFields, ...undocumented].map((name) => name.trim()).filter(Boolean)),
  );

  // If no fields at all (documented or undocumented), use SELECT *
  if (combined.length === 0) {
    const query = `SELECT * FROM "${tableName}" LIMIT 10;`;
    sessionStore.createQueryTab({
      sql: query,
      title: `SQL: ${tableName}`,
      makeActive: true,
    });
    return;
  }

  const selectedFields = includeAll
    ? combined
    : documentedFields.length > 0
      ? documentedFields.slice(0, Math.min(documentedFields.length, 4))
      : combined.slice(0, Math.min(combined.length, 4));
  const columnSegment = selectedFields.length
    ? selectedFields.map((name) => `"${name}"`).join(", ")
    : "*";
  const query =
    columnSegment === "*"
      ? `SELECT * FROM "${tableName}" LIMIT 10;`
      : `SELECT ${columnSegment} FROM "${tableName}" LIMIT 10;`;

  const descriptor = includeAll ? " (all columns)" : " (sample)";
  sessionStore.createQueryTab({
    sql: query,
    title: `SQL: ${tableName}${descriptor}`,
    makeActive: true,
  });
}
</script>

<style scoped>
.schema-sidebar {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  height: 100%;
  padding: 0.75rem;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.schema-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  flex: 1;
  min-height: 0;
}

.table-picker {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.picker-input {
  position: relative;
  display: flex;
  align-items: center;
  border: 1px solid rgba(178, 106, 69, 0.25);
  border-radius: 14px;
  background-color: #fdf8f1;
}

.picker-input input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 0.45rem 0.75rem;
  font-size: 0.88rem;
  color: #5b4a3f;
}

.picker-input input:focus {
  outline: none;
}

.picker-clear,
.picker-toggle {
  border: none;
  background: transparent;
  color: #b26a45;
  width: 34px;
  height: 100%;
  cursor: pointer;
  font-size: 0.85rem;
}

.picker-options {
  list-style: none;
  margin: 0;
  padding: 0.35rem 0;
  border: 1px solid rgba(178, 106, 69, 0.2);
  border-radius: 12px;
  background: #ffffff;
  max-height: 200px;
  overflow-y: auto;
  box-shadow: 0 16px 28px rgba(149, 128, 105, 0.14);
}

.picker-options li button {
  width: 100%;
  text-align: left;
  padding: 0.45rem 0.75rem;
  border: none;
  background: transparent;
  color: #4f4035;
  font-size: 0.85rem;
  cursor: pointer;
}

.picker-options li button:hover,
.picker-options li.active button {
  background: rgba(178, 106, 69, 0.12);
  color: #b26a45;
}

.table-details {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid rgba(178, 106, 69, 0.14);
  border-radius: 14px;
  background: linear-gradient(180deg, #fcfaf6, #ffffff);
  overflow-y: auto;
  flex: 1;
}

.table-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.table-header-actions {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.table-header h3 {
  margin: 0;
  font-size: 1rem;
  color: #4f4035;
}

.table-header-actions .icon-button {
  flex-shrink: 0;
}

.diagram-action-error {
  margin: 0;
  margin-top: -0.3rem;
  padding: 0.35rem 0.5rem;
  border-radius: 8px;
  background-color: rgba(248, 113, 113, 0.18);
  color: #b45309;
  font-size: 0.82rem;
}

.summary {
  margin: 0;
  font-weight: 500;
  font-size: 0.85rem;
  color: #5c4b3f;
}

.description {
  margin: 0;
  color: #7a6a5d;
  font-size: 0.8rem;
  line-height: 1.35;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.fields-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
}

.field-search {
  flex: 1 1 auto;
  position: relative;
}

.field-search input {
  width: 100%;
  border-radius: 999px;
  border: 1px solid rgba(178, 106, 69, 0.25);
  background-color: rgba(253, 248, 241, 0.9);
  padding: 0.35rem 0.9rem;
  padding-right: 2rem;
  font-size: 0.85rem;
  color: #5c4b3f;
}

.field-search input:focus {
  outline: none;
  border-color: #b26a45;
  box-shadow: 0 0 0 2px rgba(178, 106, 69, 0.15);
}

.field-search-clear {
  position: absolute;
  right: 0.25rem;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  color: #b26a45;
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 1.2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s ease;
}

.field-search-clear:hover {
  background-color: rgba(178, 106, 69, 0.1);
}

.fields-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

.undocumented {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-bottom: 0.3rem;
}

.undocumented-label {
  font-size: 0.82rem;
  color: #7a6a5d;
  font-weight: 600;
}

.undocumented-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.undocumented-chip {
  border: 1px solid rgba(178, 106, 69, 0.3);
  border-radius: 999px;
  padding: 0.2rem 0.6rem;
  background: rgba(253, 248, 241, 0.92);
  color: #a05736;
  font-size: 0.8rem;
  cursor: pointer;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}

.undocumented-chip:hover {
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 4px 12px rgba(178, 106, 69, 0.14);
}

.undocumented-chip.ignored {
  background: rgba(240, 240, 240, 0.92);
  color: #7a6a5d;
  border-color: rgba(122, 106, 93, 0.3);
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
  font-size: 0.9rem;
}

.icon-button:hover {
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 4px 12px rgba(178, 106, 69, 0.18);
}

.icon-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}

.field-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.6rem;
}

.field-card {
  background-color: #fdf7f1;
  border-radius: 12px;
  padding: 0.65rem;
  border: 1px solid rgba(178, 106, 69, 0.18);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
}

.field-card header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.field-card header .icon-button {
  margin-left: auto;
}

.field-name {
  font-weight: 600;
  color: #4f4035;
}

.field-type {
  font-size: 0.72rem;
  padding: 0.15rem 0.4rem;
  border-radius: 999px;
  background-color: rgba(178, 106, 69, 0.16);
  color: #a05736;
}

.field-short {
  margin: 0;
  color: #5c4b3f;
}

.field-long {
  margin: 0;
  color: #7a6859;
  font-size: 0.8rem;
}

.field-values {
  list-style: none;
  margin: 0;
  padding: 0.2rem 0 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.field-values li {
  font-size: 0.75rem;
  color: #a05736;
}

.field-relationships {
  margin-top: 0.45rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.field-rel-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #a05736;
  font-weight: 600;
}

.field-rel-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.field-rel-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  background-color: rgba(178, 106, 69, 0.14);
  color: #6f4d39;
  font-size: 0.76rem;
  font-weight: 600;
}

.field-card footer {
  margin-top: auto;
  font-size: 0.72rem;
  color: #8a7b6f;
}

.empty-state {
  padding: 1rem;
  text-align: center;
  color: #6d5b4d;
}

.empty-state.subtle {
  padding: 0.5rem;
}

.secondary {
  border: 1px dashed rgba(178, 106, 69, 0.24);
  border-radius: 10px;
  padding: 1rem;
  color: #6d5b4d;
  background: rgba(249, 246, 238, 0.8);
}

.count-badge {
  font-size: 0.85rem;
  color: #7a6a5d;
  font-weight: normal;
  margin-left: 0.5rem;
  background-color: rgba(178, 106, 69, 0.1);
  padding: 0.1rem 0.5rem;
  border-radius: 12px;
}

.coverage-chip {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 12px;
  margin-left: 0.5rem;
  vertical-align: middle;
}

.coverage-chip.high {
  background-color: rgba(34, 197, 94, 0.15);
  color: #15803d;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.coverage-chip.medium {
  background-color: rgba(234, 179, 8, 0.15);
  color: #a16207;
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.coverage-chip.low {
  background-color: rgba(239, 68, 68, 0.15);
  color: #b91c1c;
  border: 1px solid rgba(239, 68, 68, 0.3);
}
</style>
