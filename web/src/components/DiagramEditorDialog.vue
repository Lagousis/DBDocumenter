<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel" role="dialog" aria-modal="true">
        <header class="dialog-header">
          <div>
            <h3>Edit diagram</h3>
            <p>Update the name and description of this diagram.</p>
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
          <footer class="dialog-actions">
            <button type="button" class="link-button" @click="handleClose">Cancel</button>
            <button type="submit" class="primary-button" :disabled="!form.name.trim()">
              Save changes
            </button>
          </footer>
        </form>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { reactive, watch } from "vue";

interface Props {
  visible: boolean;
  currentName: string;
  currentDescription?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: { name: string; description: string }): void;
}>();

const form = reactive({
  name: props.currentName ?? "",
  description: props.currentDescription ?? "",
});

watch(
  () => [props.visible, props.currentName, props.currentDescription] as const,
  ([visible, name, description]) => {
    if (visible) {
      form.name = name ?? "";
      form.description = description ?? "";
    }
  },
);

function handleClose(): void {
  emit("close");
}

function handleSubmit(): void {
  if (!form.name.trim()) {
    return;
  }
  emit("submit", {
    name: form.name.trim(),
    description: form.description,
  });
  emit("close");
}
</script>

<style scoped>
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

input,
textarea {
  border: 1px solid rgba(178, 106, 69, 0.3);
  border-radius: 10px;
  padding: 0.5rem 0.65rem;
  font-size: 0.9rem;
  background: #fefbf6;
  color: #3d3129;
  font-family: inherit;
  resize: vertical;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

input:focus,
textarea:focus {
  outline: none;
  border-color: rgba(178, 106, 69, 0.65);
  box-shadow: 0 0 0 3px rgba(178, 106, 69, 0.15);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 0.5rem;
  margin-top: 0.5rem;
  border-top: 1px solid rgba(178, 106, 69, 0.18);
}

.primary-button {
  border: none;
  border-radius: 12px;
  padding: 0.5rem 1.1rem;
  background: linear-gradient(135deg, #b26a45, #d89b6c);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(178, 106, 69, 0.28);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.primary-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(178, 106, 69, 0.3);
}

.primary-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.link-button {
  border: none;
  background: transparent;
  color: #b26a45;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  transition: background 0.2s ease;
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
  font-size: 1.5rem;
  padding: 0;
}

.icon-button:hover {
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 4px 12px rgba(178, 106, 69, 0.18);
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
