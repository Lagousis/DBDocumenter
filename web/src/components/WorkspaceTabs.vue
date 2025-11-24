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
      <div v-else-if="activeTab && activeTab.type === 'markdown'" class="markdown-viewer">
        <div class="markdown-content" v-html="renderMarkdown(activeTab.content)"></div>
      </div>
      <div v-else class="empty-state">Use the controls above to open a SQL query or ER diagram.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
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
  // Handle code blocks first (before escaping HTML)
  const codeBlocks: string[] = [];
  let processedText = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
    const placeholder = `___CODE_BLOCK_${codeBlocks.length}___`;
    const language = lang || 'text';
    const escapedCode = escapeHtml(code.trim());
    codeBlocks.push(`<pre class="code-block ${language}"><code>${escapedCode}</code></pre>`);
    return placeholder;
  });
  
  // Now escape the rest of the text (but preserve placeholders)
  const parts = processedText.split(/(___CODE_BLOCK_\d+___)/);
  let html = parts.map((part, index) => {
    // Don't escape placeholders
    if (part.startsWith('___CODE_BLOCK_')) {
      return part;
    }
    return escapeHtml(part);
  }).join('');
  
  // Restore code blocks BEFORE processing other markdown
  codeBlocks.forEach((block, index) => {
    html = html.replace(`___CODE_BLOCK_${index}___`, `\n${block}\n`);
  });
  
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  
  // Bold: **text** or __text__
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
  
  // Italic: *text* or _text_ (but not inside words)
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/\b_(.+?)_\b/g, '<em>$1</em>');
  
  // Inline code: `text`
  html = html.replace(/`(.+?)`/g, '<code class="inline-code">$1</code>');
  
  // Lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
  html = html.replace(/^• (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*?<\/li>\n?)+/g, '<ul>$&</ul>');
  
  // Protect code blocks from paragraph wrapping
  const protectedBlocks: string[] = [];
  html = html.replace(/(<pre class="code-block[^>]*>[\s\S]*?<\/pre>)/g, (match) => {
    const id = `___PROTECTED_${protectedBlocks.length}___`;
    protectedBlocks.push(match);
    return id;
  });
  
  // Line breaks (convert double newlines to paragraphs, single to <br>)
  html = html.replace(/\n\n/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');
  html = '<p>' + html + '</p>';
  
  // Remove empty paragraphs
  html = html.replace(/<p><\/p>/g, '');
  html = html.replace(/<p><br><\/p>/g, '');
  
  // Restore protected blocks
  protectedBlocks.forEach((block, index) => {
    html = html.replace(`___PROTECTED_${index}___`, block);
  });
  
  return html;
}

function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
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
</style>
