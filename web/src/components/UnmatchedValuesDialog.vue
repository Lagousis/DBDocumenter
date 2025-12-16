<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel">
        <header class="dialog-header">
          <div class="header-content">
            <h3>Unmatched Values</h3>
            <p>
              Values in <strong>{{ sourceTable }}.{{ sourceField }}</strong> 
              not found in <strong>{{ targetTable }}.{{ targetField }}</strong>
            </p>
          </div>
          <button type="button" class="icon-button" @click="handleClose" aria-label="Close dialog">
            ×
          </button>
        </header>

        <div class="dialog-content">
          <div class="dialog-body">
            <div v-if="loading" class="loading-state">
              <span class="spinner"></span> Loading...
            </div>
            <div v-else-if="values.length === 0" class="empty-state">
              No unmatched values found.
            </div>
            <div v-else class="values-list">
              <div v-for="(item, idx) in values" :key="idx" class="value-item">
                <span class="value-text">{{ item.value }}</span>
                <span class="value-count">{{ item.count }} rows</span>
              </div>
            </div>
            <p v-if="values.length >= 100" class="limit-notice">
              Showing first 100 unmatched values.
            </p>
          </div>
        </div>

        <footer class="dialog-footer">
          <button type="button" class="secondary-button" @click="handleClose">Close</button>
        </footer>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean;
  loading: boolean;
  values: { value: string; count: number }[];
  sourceTable: string;
  sourceField: string;
  targetTable: string;
  targetField: string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
}>();

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
  z-index: 1100;
}

.dialog-panel {
  width: min(500px, 100%);
  max-height: 80vh;
  background: #fdf9f3;
  border-radius: 20px;
  box-shadow: 0 24px 50px rgba(47, 38, 32, 0.22);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dialog-header {
  padding: 1.25rem;
  border-bottom: 1px solid rgba(178, 106, 69, 0.15);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: #fff;
}

.dialog-header h3 {
  margin: 0 0 0.25rem;
  font-size: 1.1rem;
  color: #4f4035;
}

.dialog-header p {
  margin: 0;
  font-size: 0.85rem;
  color: #7a6a5d;
}

.header-content {
  flex: 1;
  min-width: 0;
  margin-right: 1rem;
}

.dialog-content {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.dialog-body {
  padding: 1.25rem;
}

.dialog-footer {
  padding: 1rem 1.25rem;
  border-top: 1px solid rgba(178, 106, 69, 0.15);
  background: #fff;
  display: flex;
  justify-content: flex-end;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 2rem;
  color: #7a6a5d;
}

.values-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.value-item {
  padding: 0.5rem 0.75rem;
  background: #fff;
  border: 1px solid rgba(178, 106, 69, 0.15);
  border-radius: 6px;
  font-family: monospace;
  font-size: 0.9rem;
  color: #4f4035;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.value-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.value-count {
  font-size: 0.8rem;
  color: #7a6a5d;
  background: rgba(178, 106, 69, 0.1);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  white-space: nowrap;
  margin-left: 0.5rem;
}

.limit-notice {
  margin-top: 1rem;
  text-align: center;
  font-size: 0.8rem;
  color: #7a6a5d;
  font-style: italic;
}

.icon-button {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 10px;
  border: 1px solid rgba(178, 106, 69, 0.28);
  background: rgba(253, 248, 241, 0.92);
  color: #b26a45;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s ease;
  font-size: 1.2rem;
}

.icon-button:hover {
  background: rgba(255, 255, 255, 0.98);
}

.secondary-button {
  background: #fff;
  border: 1px solid #d4c5b9;
  color: #4f4035;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.secondary-button:hover {
  background: #fdf9f3;
  border-color: #b26a45;
  color: #b26a45;
}

.spinner {
  display: inline-block;
  width: 1rem;
  height: 1rem;
  border: 2px solid rgba(178, 106, 69, 0.3);
  border-top-color: #b26a45;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 0.5rem;
  vertical-align: middle;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

