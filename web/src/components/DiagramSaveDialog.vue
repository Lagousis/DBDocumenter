<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel" role="dialog" aria-modal="true">
        <header class="dialog-header">
          <div>
            <h3>Save diagram layout</h3>
            <p>Store this arrangement so you can reopen it later.</p>
          </div>
          <button type="button" class="icon-button" @click="handleClose" aria-label="Close dialog">
            &times;
          </button>
        </header>
        <form class="dialog-body" @submit.prevent="handleSubmit">
          <label class="block">
            <span class="label">Diagram name</span>
            <input v-model.trim="form.name" type="text" :maxlength="80" required />
          </label>
          <label class="block">
            <span class="label">Description</span>
            <textarea v-model="form.description" rows="4" placeholder="Explain the focus of this diagram." />
          </label>
          <p v-if="error" class="error">{{ error }}</p>
          <footer class="dialog-actions">
            <button type="button" class="link-button" @click="handleClose">Cancel</button>
            <button type="submit" class="primary-button" :disabled="disabled">
              {{ loading ? "Saving..." : "Save diagram" }}
            </button>
          </footer>
        </form>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue";

interface Props {
  visible: boolean;
  loading?: boolean;
  error?: string;
  defaultName?: string;
  defaultDescription?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: { name: string; description: string }): void;
}>();

const form = reactive({
  name: props.defaultName ?? "",
  description: props.defaultDescription ?? "",
});

watch(
  () => [props.visible, props.defaultName, props.defaultDescription] as const,
  ([visible, name, description]) => {
    if (visible) {
      form.name = name ?? "";
      form.description = description ?? "";
    }
  },
);

const disabled = computed(() => props.loading || !form.name.trim());

function handleClose(): void {
  if (!props.loading) {
    emit("close");
  }
}

function handleSubmit(): void {
  if (disabled.value) {
    return;
  }
  emit("submit", {
    name: form.name.trim(),
    description: form.description,
  });
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
  width: min(520px, 100%);
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

.dialog-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
}

.block {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #5c4b3f;
}

input,
textarea {
  border-radius: 10px;
  border: 1px solid #dfd2c6;
  padding: 0.65rem 0.75rem;
  font-size: 0.95rem;
  font-family: "Segoe UI", "Inter", sans-serif;
  resize: vertical;
  background: rgba(255, 255, 255, 0.95);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

input:focus,
textarea:focus {
  outline: none;
  border-color: rgba(178, 106, 69, 0.65);
  box-shadow: 0 0 0 3px rgba(178, 106, 69, 0.15);
}

.dialog-actions {
  padding: 0.9rem 1.25rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  border-top: 1px solid rgba(178, 106, 69, 0.18);
  background: rgba(253, 248, 241, 0.9);
}

.primary-button {
  border: none;
  border-radius: 12px;
  padding: 0.5rem 1.2rem;
  background: linear-gradient(135deg, #2563eb, #38bdf8);
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(59, 130, 246, 0.28);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.primary-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(59, 130, 246, 0.3);
}

.primary-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.link-button {
  border: none;
  background: transparent;
  color: #1d4ed8;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
}

.link-button:hover {
  background: rgba(255, 255, 255, 0.9);
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

.icon-button:hover {
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
