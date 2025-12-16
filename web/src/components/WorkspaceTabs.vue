<template>
  <div class="workspace-tabs">
    <div class="tab-bar" role="tablist">
      <template v-if="tabs.length">
        <div
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-button"
          :class="{ active: tab.id === activeId }"
          role="tab"
          :aria-selected="tab.id === activeId"
          :aria-label="tabLabel(tab)"
          tabindex="0"
          @click="activate(tab.id)"
          @keydown.enter.prevent="activate(tab.id)"
          @keydown.space.prevent="activate(tab.id)"
        >
          <span class="tab-title">
            <span class="tab-title-text">{{ tab.title }}</span>
            <span v-if="tabHasUnsavedChanges(tab)" class="tab-dirty-indicator" aria-hidden="true">*</span>
          </span>
          <span class="tab-type">{{ getTabType(tab) }}</span>
          <span
            class="tab-close"
            role="button"
            tabindex="0"
            aria-label="Close tab"
            @click.stop="close(tab.id)"
            @keydown.enter.prevent.stop="close(tab.id)"
            @keydown.space.prevent.stop="close(tab.id)"
          >
            ×
          </span>
        </div>
      </template>
      <div v-else class="tab-bar-empty">No open tabs</div>
    </div>
    <div class="tab-content">
      <QueryConsole v-if="activeTab && activeTab.type === 'query'" :tab="activeTab" />
      <ERDiagram v-else-if="activeTab && activeTab.type === 'diagram'" :tab="activeTab" />
      <ChartViewer v-else-if="activeTab && activeTab.type === 'chart'" :tab="activeTab" />
      <div v-else-if="activeTab && activeTab.type === 'markdown'" class="markdown-viewer-container">
        <div class="markdown-toolbar">
          <button class="toolbar-btn" @click="exportMarkdown(activeTab)" title="Download Markdown">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            Markdown
          </button>
          <button class="toolbar-btn" @click="exportHtml(activeTab)" title="Download HTML">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="16 18 22 12 16 6"></polyline>
              <polyline points="8 6 2 12 8 18"></polyline>
            </svg>
            HTML
          </button>
          <button class="toolbar-btn" @click="printMarkdown" title="Print / Save as PDF">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 6 2 18 2 18 9"></polyline>
              <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
              <rect x="6" y="14" width="12" height="8"></rect>
            </svg>
            Print / PDF
          </button>
        </div>
        <div class="markdown-viewer">
          <div class="markdown-content" v-html="renderMarkdown(activeTab.content)"></div>
        </div>
      </div>
      <div v-else class="empty-state">Use the controls above to open a SQL query or ER diagram.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import { storeToRefs } from "pinia";
import { computed, watch } from "vue";

import { useSessionStore, type WorkspaceTab } from "../stores/session";
import ChartViewer from "./ChartViewer.vue";
import ERDiagram from "./ERDiagram.vue";
import QueryConsole from "./QueryConsole.vue";

const sessionStore = useSessionStore();
const { workspaceTabs, activeWorkspaceTabId } = storeToRefs(sessionStore);

const tabs = computed(() => workspaceTabs.value);
const activeId = computed(() => activeWorkspaceTabId.value);
const activeTab = computed(() => tabs.value.find((tab) => tab.id === activeId.value));

watch(
  tabs,
  (collection) => {
    if (collection.length === 0) {
      sessionStore.ensureDefaultQueryTab();
      return;
    }
    if (!activeId.value) {
      sessionStore.setActiveWorkspaceTab(collection[0].id);
    }
  },
  { immediate: true },
);

function activate(id: string): void {
  sessionStore.setActiveWorkspaceTab(id);
}

function close(id: string): void {
  sessionStore.closeWorkspaceTab(id);
}

function tabHasUnsavedChanges(tab: WorkspaceTab): boolean {
  if (tab.type === "diagram" || tab.type === "query") {
    return Boolean(tab.hasUnsavedChanges);
  }
  return false;
}

function getTabType(tab: WorkspaceTab): string {
  if (tab.type === "diagram") return "Diagram";
  if (tab.type === "markdown") return "Markdown";
  if (tab.type === "chart") return "Chart";
  return "SQL";
}

function tabLabel(tab: WorkspaceTab): string {
  if (tab.type === "diagram") {
    const suffix = tabHasUnsavedChanges(tab) ? " (unsaved changes)" : "";
    return `${tab.title} — Diagram${suffix}`;
  }
  if (tab.type === "markdown") {
    return `${tab.title} — Markdown`;
  }
  if (tab.type === "chart") {
    return `${tab.title} — Chart`;
  }
  const suffix = tabHasUnsavedChanges(tab) ? " (unsaved changes)" : "";
  return `${tab.title} — SQL${suffix}`;
}

function renderMarkdown(text: string): string {
  try {
    return marked.parse(text) as string;
  } catch (e) {
    console.error("Markdown parsing failed", e);
    return text;
  }
}

function exportMarkdown(tab: WorkspaceTab) {
  if (tab.type !== "markdown") return;
  const blob = new Blob([tab.content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${tab.title.replace(/\s+/g, "_")}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function exportHtml(tab: WorkspaceTab) {
  if (tab.type !== "markdown") return;
  const htmlContent = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>${tab.title}</title>
<style>
body { font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 2rem; color: #333; }
h1, h2, h3 { color: #111; margin-top: 1.5em; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background-color: #f5f5f5; }
code { background: #f5f5f5; padding: 2px 5px; border-radius: 3px; font-family: monospace; font-size: 0.9em; }
pre { background: #f5f5f5; padding: 1rem; overflow-x: auto; border-radius: 5px; }
pre code { background: transparent; padding: 0; }
blockquote { border-left: 4px solid #ddd; margin: 0; padding-left: 1rem; color: #666; }
img { max-width: 100%; height: auto; }
</style>
</head>
<body>
${renderMarkdown(tab.content)}
</body>
</html>`;
  
  const blob = new Blob([htmlContent], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${tab.title.replace(/\s+/g, "_")}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function printMarkdown() {
  window.print();
}
</script>

<style scoped>
.workspace-tabs {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.tab-bar {
  display: flex;
  align-items: flex-end;
  gap: 0.4rem;
  padding: 0.4rem 0.4rem 0;
}

.tab-bar-empty {
  font-size: 0.85rem;
  color: #64748b;
  padding: 0.35rem 0.6rem;
}

.tab-button {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border: 1px solid #cbd5f5;
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  padding: 0.35rem 0.8rem;
  background: #f1f5ff;
  color: #1e293b;
  cursor: pointer;
  position: relative;
  min-width: 120px;
  justify-content: space-between;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.tab-button.active {
  background: #ffffff;
  color: #0f172a;
  border-color: #93c5fd;
  box-shadow: 0 -2px 8px rgba(148, 163, 184, 0.2);
}

.tab-button:hover {
  background: #e2e8ff;
}

.tab-title {
  font-weight: 600;
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
}

.tab-title-text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.tab-dirty-indicator {
  color: #dc2626;
  font-weight: 700;
}

.tab-type {
  font-size: 0.75rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.tab-close {
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0 0.2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tab-close:hover {
  color: #ef4444;
}

.tab-content {
  flex: 1;
  background: #ffffff;
  border: 1px solid #cbd5f5;
  border-radius: 0 12px 12px 12px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  text-align: center;
}

.markdown-viewer-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.markdown-toolbar {
  display: flex;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  flex-shrink: 0;
}

.toolbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.75rem;
  border: 1px solid #cbd5f5;
  background: #ffffff;
  border-radius: 4px;
  font-size: 0.85rem;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background: #f1f5f9;
  color: #0f172a;
  border-color: #94a3b8;
}

.markdown-viewer {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.markdown-content {
  max-width: 800px;
  margin: 0 auto;
  line-height: 1.6;
  color: #334155;
}

.markdown-content :deep(h1) {
  font-size: 1.875rem;
  font-weight: 700;
  margin: 1.5rem 0 1rem;
  color: #0f172a;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 0.5rem;
}

.markdown-content :deep(h2) {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 1.25rem 0 0.75rem;
  color: #1e293b;
}

.markdown-content :deep(h3) {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 1rem 0 0.5rem;
  color: #334155;
}

.markdown-content :deep(p) {
  margin: 0.75rem 0;
}

.markdown-content :deep(strong) {
  font-weight: 600;
  color: #1e293b;
}

.markdown-content :deep(em) {
  font-style: italic;
}

.markdown-content :deep(code.inline-code) {
  background: #f1f5f9;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-family: 'Courier New', monospace;
  font-size: 0.875em;
  color: #b26a45;
}

.markdown-content :deep(pre.code-block) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin: 1rem 0;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
}

.markdown-content :deep(pre.code-block code) {
  background: transparent;
  color: inherit;
  padding: 0;
  border-radius: 0;
  font-family: inherit;
  font-size: inherit;
}

.markdown-content :deep(ul) {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.markdown-content :deep(li) {
  margin: 0.25rem 0;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.9rem;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  padding: 0.5rem 0.75rem;
  border: 1px solid #e2e8f0;
  text-align: left;
}

.markdown-content :deep(th) {
  background-color: #f8fafc;
  font-weight: 600;
  color: #1e293b;
}

.markdown-content :deep(tr:nth-child(even)) {
  background-color: #fcfcfc;
}

.markdown-content :deep(code) {
  background: #f1f5f9;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-family: 'Courier New', monospace;
  font-size: 0.875em;
  color: #b26a45;
}

.markdown-content :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin: 1rem 0;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}
</style>
