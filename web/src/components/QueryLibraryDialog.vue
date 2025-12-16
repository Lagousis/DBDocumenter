<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel" role="dialog" aria-modal="true">
        <header class="dialog-header">
          <div>
            <h3>Saved queries</h3>
            <p>Reopen, inspect, or delete SQL saved for this project.</p>
          </div>
          <div class="header-actions">
            <button type="button" class="icon-button" :disabled="loading" @click="emitRefresh" aria-label="Refresh queries">
              &#8635;
            </button>
            <button type="button" class="icon-button" @click="emitClose" aria-label="Close dialog">
              &times;
            </button>
          </div>
        </header>
        <div class="dialog-body">
          <p v-if="error" class="error">{{ error }}</p>
          <p v-else-if="loading" class="status">Loading queries...</p>
          <p v-else-if="!queries.length" class="status">No queries saved yet.</p>
          <ul v-else class="query-list">
            <li v-for="query in queries" :key="query.id" class="query-card">
              <div class="query-card__header">
                <div class="query-card__title-group">
                  <h4>{{ query.name || "Untitled query" }}</h4>
                  <span v-if="query.updated_at" class="meta date">Updated: {{ formatDate(query.updated_at) }}</span>
                </div>
                <div class="query-card__actions">
                  <button type="button" class="primary-button" @click="emitSelect(query.id)">Open</button>
                  <button type="button" class="secondary-button" @click="handleEdit(query)">Edit</button>
                  <button type="button" class="link-button" @click="emitDelete(query.id)">Delete</button>
                </div>
              </div>
              <div class="query-card__content">
                <p>{{ query.description || "No description provided." }}</p>
                <pre>{{ query.sql }}</pre>
                <div class="meta-row">
                  <span class="meta">{{ query.limit ? `Limit ${query.limit}` : "No limit saved" }}</span>
                </div>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </transition>

  <QuerySaveDialog
    :visible="showEditDialog"
    :loading="editLoading"
    :error="editError"
    :default-name="editingQuery?.name"
    :default-description="editingQuery?.description || ''"
    @close="closeEditDialog"
    @submit="handleSaveEdit"
  />
</template>

<script setup lang="ts">
import { ref } from "vue";
import type { QueryRecord } from "../types/api";
import QuerySaveDialog from "./QuerySaveDialog.vue";

interface Props {
  visible: boolean;
  queries: QueryRecord[];
  loading?: boolean;
  error?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "refresh"): void;
  (e: "select", id: string): void;
  (e: "delete", id: string): void;
  (e: "update", payload: { id: string; name: string; description: string }): void;
}>();

const showEditDialog = ref(false);
const editingQuery = ref<QueryRecord | null>(null);
const editLoading = ref(false);
const editError = ref("");

function emitClose(): void {
  emit("close");
}

function emitRefresh(): void {
  emit("refresh");
}

function emitSelect(id: string): void {
  emit("select", id);
}

function emitDelete(id: string): void {
  emit("delete", id);
}

function handleEdit(query: QueryRecord): void {
  editingQuery.value = query;
  editError.value = "";
  showEditDialog.value = true;
}

function closeEditDialog(): void {
  showEditDialog.value = false;
  editingQuery.value = null;
}

function handleSaveEdit(payload: { name: string; description: string }): void {
  if (!editingQuery.value) return;
  
  emit("update", {
    id: editingQuery.value.id,
    name: payload.name,
    description: payload.description
  });
  
  closeEditDialog();
}

function formatDate(isoString: string): string {
  try {
    return new Date(isoString).toLocaleString();
  } catch (e) {
    return isoString;
  }
}
</script>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.dialog-panel {
  width: min(720px, 100%);
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
  background: rgba(253, 248, 241, 0.94);
}

.dialog-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #5c4b3f;
}

.dialog-header p {
  margin: 0.35rem 0 0;
  color: #7a6a5d;
  font-size: 0.85rem;
}

.header-actions {
  display: inline-flex;
  gap: 0.35rem;
}

.dialog-body {
  padding: 1rem 1.25rem;
  overflow-y: auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.query-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.query-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  border: 1px solid rgba(178, 106, 69, 0.18);
  border-radius: 14px;
  padding: 0.85rem 1rem;
  background: rgba(255, 255, 255, 0.85);
}

.query-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.query-card__title-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.query-card__title-group h4 {
  margin: 0;
  color: #4f4035;
  font-size: 1rem;
}

.query-card__content p {
  margin: 0.35rem 0 0.4rem;
  color: #7a6a5d;
  font-size: 0.88rem;
}

.query-card__content pre {
  margin: 0.25rem 0;
  padding: 0.5rem;
  background: #f8fafc;
  border-radius: 8px;
  max-height: 6rem;
  overflow: auto;
  font-size: 0.8rem;
  white-space: pre-wrap;
}

.meta {
  font-size: 0.78rem;
  color: #b26a45;
  font-weight: 600;
}

.query-card__actions {
  display: flex;
  flex-direction: row;
  gap: 0.5rem;
  align-items: center;
}

.primary-button {
  border: none;
  border-radius: 6px;
  padding: 0.35rem 0.85rem;
  background: #007bff;
  color: #ffffff;
  font-weight: 500;
  cursor: pointer;
  font-size: 0.85rem;
}

.primary-button:hover {
  background: #0056b3;
}

.secondary-button {
  border: 1px solid #ccc;
  border-radius: 6px;
  padding: 0.35rem 0.85rem;
  background: #fff;
  color: #333;
  font-weight: 500;
  cursor: pointer;
  font-size: 0.85rem;
}

.secondary-button:hover {
  background: #f8f9fa;
  border-color: #bbb;
}

.link-button {
  border: none;
  background: transparent;
  color: #dc3545;
  font-weight: 500;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.35rem 0.85rem;
}

.link-button:hover {
  text-decoration: underline;
}

.meta-row {
  display: flex;
  gap: 1rem;
  align-items: center;
  margin-top: 0.25rem;
}

.date {
  color: #6c757d;
  font-weight: normal;
  font-size: 0.75rem;
}

.status {
  margin: 0;
  color: #7a6a5d;
  font-size: 0.9rem;
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
}

.icon-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.icon-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 4px 12px rgba(178, 106, 69, 0.18);
}

.error {
  margin: 0;
  color: #b91c1c;
  font-size: 0.85rem;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
