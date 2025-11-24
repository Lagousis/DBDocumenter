<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel" role="dialog" aria-modal="true">
        <header class="dialog-header">
          <div>
            <h3>Saved diagrams</h3>
            <p>Reopen, inspect, or delete saved layouts for this project.</p>
          </div>
          <div class="header-actions">
            <button type="button" class="icon-button" :disabled="loading" @click="emitRefresh" aria-label="Refresh diagrams">
              &#8635;
            </button>
            <button type="button" class="icon-button" @click="emitClose" aria-label="Close dialog">
              &times;
            </button>
          </div>
        </header>
        <div class="dialog-body">
          <p v-if="error" class="error">{{ error }}</p>
          <p v-else-if="loading" class="status">Loading diagrams...</p>
          <p v-else-if="!diagrams.length" class="status">No diagrams saved yet.</p>
          <ul v-else class="diagram-list">
            <li v-for="diagram in diagrams" :key="diagram.id" class="diagram-card">
              <div class="diagram-card__info">
                <h4>{{ diagram.name || "Untitled diagram" }}</h4>
                <p>{{ diagram.description || "No description provided." }}</p>
                <span class="meta">{{ diagram.tables.length }} tables</span>
              </div>
              <div class="diagram-card__actions">
                <button type="button" class="primary-button" @click="emitSelect(diagram.id)">Open</button>
                <button type="button" class="link-button" @click="emitDelete(diagram.id)">Delete</button>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import type { DiagramRecord } from "../types/api";

interface Props {
  visible: boolean;
  diagrams: DiagramRecord[];
  loading?: boolean;
  error?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "refresh"): void;
  (e: "select", id: string): void;
  (e: "delete", id: string): void;
}>();

function emitClose(): void {
  emit("close");
}

function emitSelect(id: string): void {
  emit("select", id);
}

function emitDelete(id: string): void {
  emit("delete", id);
}

function emitRefresh(): void {
  emit("refresh");
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

.diagram-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.diagram-card {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  border: 1px solid rgba(178, 106, 69, 0.18);
  border-radius: 14px;
  padding: 0.85rem 1rem;
  background: rgba(255, 255, 255, 0.85);
}

.diagram-card__info h4 {
  margin: 0;
  color: #4f4035;
  font-size: 1rem;
}

.diagram-card__info p {
  margin: 0.35rem 0 0.4rem;
  color: #7a6a5d;
  font-size: 0.88rem;
}

.meta {
  font-size: 0.78rem;
  color: #b26a45;
  font-weight: 600;
}

.diagram-card__actions {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  align-items: flex-end;
}

.primary-button {
  border: none;
  border-radius: 10px;
  padding: 0.45rem 1rem;
  background: linear-gradient(135deg, #2563eb, #38bdf8);
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.primary-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(59, 130, 246, 0.28);
}

.link-button {
  border: none;
  background: transparent;
  color: #b91c1c;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.2rem 0.4rem;
  border-radius: 999px;
}

.link-button:hover {
  background: rgba(185, 28, 28, 0.08);
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
