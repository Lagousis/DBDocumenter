<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel" role="dialog" aria-modal="true">
        <header class="dialog-header">
          <div>
            <h3>{{ title }}</h3>
            <p>{{ subtitle }}</p>
          </div>
          <button type="button" class="icon-button" @click="handleClose" aria-label="Close dialog">
            &times;
          </button>
        </header>

        <form class="dialog-body" @submit.prevent="handleSubmit">
          <label class="block">
            <span class="label">Project name</span>
            <input v-model.trim="form.name" type="text" :maxlength="80" required />
          </label>

          <label class="block">
            <span class="label">Description</span>
            <textarea v-model="form.description" rows="4" placeholder="Describe the focus and purpose of this project." />
          </label>

          <label class="block">
            <span class="label">Query Instructions</span>
            <textarea
              v-model="form.query_instructions"
              rows="4"
              placeholder="Specific instructions for the LLM when generating queries (e.g., 'Always use CTEs', 'Prefer specific naming conventions')."
            />
          </label>

          <label class="block">
            <span class="label">Version</span>
            <input v-model.trim="form.version" type="text" placeholder="e.g., 1.0.0" />
          </label>

          <p v-if="error" class="error">{{ error }}</p>

          <footer class="dialog-actions">
            <div class="left-actions">
              <button v-if="mode === 'edit'" type="button" class="secondary-button" @click="openDbInfo">DB info</button>
            </div>
            <div class="right-actions">
              <button type="button" class="secondary-button" @click="handleClose">Cancel</button>
              <button type="submit" class="secondary-button" :disabled="disabled">
                {{ loading ? "Saving..." : mode === "create" ? "Create project" : "Save changes" }}
              </button>
            </div>
          </footer>
        </form>
      </div>
    </div>
  </transition>

  <DatabaseInfoDialog :visible="dbInfoVisible" @close="closeDbInfo" />
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import DatabaseInfoDialog from "./DatabaseInfoDialog.vue";

interface Props {
  visible: boolean;
  mode: "edit" | "create";
  initialName: string;
  initialDescription: string;
  initialVersion?: string;
  initialQueryInstructions?: string;
  loading?: boolean;
  error?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: "close"): void;
  (
    e: "submit",
    payload: { name: string; description: string; version: string; query_instructions: string },
  ): void;
}>();

const form = reactive({
  name: props.initialName,
  description: props.initialDescription ?? "",
  version: props.initialVersion ?? "",
  query_instructions: props.initialQueryInstructions ?? "",
});

const dbInfoVisible = ref(false);

watch(
  () =>
    [
      props.initialName,
      props.initialDescription,
      props.initialVersion,
      props.initialQueryInstructions,
      props.visible,
    ] as const,
  ([name, description, version, query_instructions, visible]) => {
    if (visible) {
      form.name = name;
      form.description = description ?? "";
      form.version = version ?? "";
      form.query_instructions = query_instructions ?? "";
    }
  },
);

const title = computed(() => (props.mode === "create" ? "Create new project" : "Edit project"));
const subtitle = computed(() =>
  props.mode === "create"
    ? "Set up a fresh DuckDB project with a name and description."
    : "Update the project name, description, and version shown across the workspace.",
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
    version: form.version.trim(),
    query_instructions: form.query_instructions,
  });
}

function openDbInfo() {
  dbInfoVisible.value = true;
}

function closeDbInfo() {
  dbInfoVisible.value = false;
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
  width: min(540px, 100%);
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
  align-items: flex-start;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(178, 106, 69, 0.2);
  background: rgba(253, 248, 241, 0.94);
  flex-wrap: nowrap;
  gap: 1rem;
}

.dialog-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #4f4035;
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
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid rgba(178, 106, 69, 0.18);
  background: rgba(253, 248, 241, 0.9);
}

.left-actions {
  display: flex;
  gap: 0.75rem;
}

.right-actions {
  display: flex;
  gap: 0.75rem;
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

.icon-button {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
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
