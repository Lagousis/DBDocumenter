<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel" role="dialog" aria-modal="true">
        <header class="dialog-header">
          <div>
            <h3>Chat History</h3>
            <p>View and restore past conversations for this project.</p>
          </div>
          <div class="header-actions">
            <button type="button" class="icon-button" :disabled="loading" @click="emitRefresh" aria-label="Refresh history">
              &#8635;
            </button>
            <button type="button" class="icon-button" @click="emitClose" aria-label="Close dialog">
              &times;
            </button>
          </div>
        </header>
        
        <div class="dialog-controls">
            <input 
                v-model="searchQuery" 
                type="text" 
                placeholder="Search history..." 
                class="search-input"
            />
            <select v-model="sortBy" class="sort-select">
                <option value="date_desc">Newest First</option>
                <option value="date_asc">Oldest First</option>
                <option value="count_desc">Most Messages</option>
                <option value="count_asc">Fewest Messages</option>
            </select>
        </div>

        <div class="dialog-body split-view">
          <div class="session-list-pane">
            <p v-if="error" class="error">{{ error }}</p>
            <p v-else-if="loading" class="status">Loading history...</p>
            <p v-else-if="!filteredSessions.length" class="status">No chat history found.</p>
            <div v-else class="table-container">
              <table class="history-table">
                <thead>
                  <tr>
                    <th>Description</th>
                    <th>Date</th>
                    <th>Msgs</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr 
                    v-for="session in filteredSessions" 
                    :key="session.id"
                    :class="{ selected: selectedSessionId === session.id }"
                    @click="selectSession(session.id)"
                  >
                    <td class="col-desc">
                      <div class="desc-text">{{ formatDescription(session.description) }}</div>
                    </td>
                    <td class="col-date">{{ formatDateTime(session.created_at) }}</td>
                    <td class="col-count">{{ session.message_count }}</td>
                    <td class="col-actions">
                      <button type="button" class="action-btn delete-btn" @click.stop="emitDelete(session.id)" title="Delete Session">
                        &times;
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          
          <div class="session-preview-pane">
            <div v-if="loadingPreview" class="preview-status">Loading preview...</div>
            <div v-else-if="previewSession" class="preview-content">
                <div class="preview-header">
                    <h4>Preview</h4>
                    <button type="button" class="primary-button small" @click="emitSelect(previewSession.id)">
                        Open Session
                    </button>
                </div>
                <div class="preview-messages">
                    <div 
                        v-for="(msg, idx) in previewSession.messages" 
                        :key="idx" 
                        class="preview-message"
                        :class="msg.role"
                    >
                        <div class="message-role">{{ msg.role }}</div>
                        <div class="message-text">{{ msg.content }}</div>
                    </div>
                </div>
            </div>
            <div v-else class="preview-placeholder">
                <p>Select a session to view preview</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { fetchChatSession } from "../api/client";
import { useSessionStore } from "../stores/session";
import type { ChatSession, ChatSessionSummary } from "../types/api";

interface Props {
  visible: boolean;
  sessions: ChatSessionSummary[];
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

const sessionStore = useSessionStore();
const searchQuery = ref("");
const sortBy = ref("date_desc");
const selectedSessionId = ref<string | null>(null);
const previewSession = ref<ChatSession | null>(null);
const loadingPreview = ref(false);

// Reset state when dialog opens
watch(() => props.visible, (newVal) => {
    if (newVal) {
        selectedSessionId.value = null;
        previewSession.value = null;
        searchQuery.value = "";
    }
});

// Clear selection if the selected session is removed from the list
watch(() => props.sessions, (newSessions) => {
    if (selectedSessionId.value && !newSessions.find(s => s.id === selectedSessionId.value)) {
        selectedSessionId.value = null;
        previewSession.value = null;
    }
});

const filteredSessions = computed(() => {
    let result = [...props.sessions];
    
    if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase();
        result = result.filter(s => 
            (s.description || "").toLowerCase().includes(query) ||
            s.id.includes(query)
        );
    }
    
    result.sort((a, b) => {
        switch (sortBy.value) {
            case "date_asc": return a.created_at - b.created_at;
            case "date_desc": return b.created_at - a.created_at;
            case "count_asc": return a.message_count - b.message_count;
            case "count_desc": return b.message_count - a.message_count;
            default: return 0;
        }
    });
    
    return result;
});

async function selectSession(id: string) {
    if (selectedSessionId.value === id) return;
    
    selectedSessionId.value = id;
    loadingPreview.value = true;
    previewSession.value = null;
    
    try {
        if (sessionStore.activeProject) {
            const session = await fetchChatSession(id, sessionStore.activeProject);
            // Filter out system messages and empty content for preview
            session.messages = session.messages.filter(msg => 
                (msg.role === 'user' || msg.role === 'assistant') && 
                msg.content && 
                msg.content.trim().length > 0
            );
            previewSession.value = session;
        }
    } catch (e) {
        console.error("Failed to load preview", e);
    } finally {
        loadingPreview.value = false;
    }
}

function formatDescription(desc: string): string {
    if (!desc) return "Untitled Session";
    // Remove common prefixes that LLMs might add
    return desc.replace(/^(Conversation title:|Chat title:|Title:)\s*/i, "").trim();
}

function formatDateTime(timestamp: number): string {
    if (!timestamp) return "";
    return new Date(timestamp * 1000).toLocaleString(undefined, {
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

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
  if (selectedSessionId.value === id) {
      selectedSessionId.value = null;
      previewSession.value = null;
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
  width: min(1000px, 95%);
  height: 85vh;
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

.dialog-controls {
    padding: 0.75rem 1.25rem;
    display: flex;
    gap: 0.75rem;
    border-bottom: 1px solid rgba(178, 106, 69, 0.1);
    background: rgba(255, 255, 255, 0.5);
}

.search-input {
    flex: 1;
    padding: 0.5rem;
    border: 1px solid rgba(178, 106, 69, 0.2);
    border-radius: 8px;
    font-size: 0.9rem;
}

.sort-select {
    padding: 0.5rem;
    border: 1px solid rgba(178, 106, 69, 0.2);
    border-radius: 8px;
    font-size: 0.9rem;
    background: white;
}

.dialog-body {
  padding: 0;
  overflow: hidden;
  flex: 1;
  display: flex;
}

.table-container {
  width: 100%;
  overflow-x: auto;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.history-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  text-align: left;
  padding: 0.75rem 1rem;
  background: rgba(178, 106, 69, 0.08);
  color: #5c4b3f;
  font-weight: 600;
  border-bottom: 1px solid rgba(178, 106, 69, 0.15);
  white-space: nowrap;
}

.history-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(178, 106, 69, 0.1);
  color: #4f4035;
}

.history-table tr:last-child td {
  border-bottom: none;
}

.history-table tr:hover {
  background: rgba(255, 255, 255, 0.6);
}

.col-desc {
  width: 60%;
}

.desc-text {
  font-weight: 500;
  color: #2c2420;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 350px;
}

.col-date {
  white-space: nowrap;
  color: #7a6a5d;
  font-size: 0.85rem;
}

.col-count {
  text-align: center;
  color: #7a6a5d;
}

.col-actions {
  white-space: nowrap;
  text-align: right;
}

.action-btn {
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  transition: all 0.2s;
  margin-left: 0.5rem;
}

.open-btn {
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  font-weight: 600;
}

.open-btn:hover {
  background: rgba(37, 99, 235, 0.2);
}

.delete-btn {
  background: transparent;
  color: #b91c1c;
  font-size: 1.1rem;
  line-height: 1;
  padding: 0.2rem 0.5rem;
}

.delete-btn:hover {
  background: rgba(185, 28, 28, 0.1);
  border-radius: 4px;
}

.status {
  padding: 2rem;
  text-align: center;
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
  padding: 1rem;
  color: #b91c1c;
  font-size: 0.85rem;
  text-align: center;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.split-view {
    display: flex;
    height: 100%;
}

.session-list-pane {
    width: 55%;
    border-right: 1px solid rgba(178, 106, 69, 0.15);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    background: rgba(255, 255, 255, 0.3);
}

.session-preview-pane {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: white;
}

.history-table th {
  position: sticky;
  top: 0;
  z-index: 1;
}

.history-table tr {
    cursor: pointer;
    transition: background-color 0.15s;
}

.history-table tr.selected {
    background: rgba(37, 99, 235, 0.08);
    border-left: 3px solid #2563eb;
}

.col-desc .desc-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.preview-status, .preview-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #7a6a5d;
    font-size: 0.95rem;
    background: #fdfdfd;
}

.preview-content {
    display: flex;
    flex-direction: column;
    height: 100%;
}

.preview-header {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid rgba(178, 106, 69, 0.1);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #fcfcfc;
}

.preview-header h4 {
    margin: 0;
    color: #5c4b3f;
    font-size: 0.95rem;
}

.preview-messages {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.preview-message {
    max-width: 85%;
    padding: 0.75rem 1rem;
    border-radius: 12px;
    font-size: 0.9rem;
    line-height: 1.5;
}

.preview-message.user {
    align-self: flex-end;
    background: #e0f2fe;
    color: #0c4a6e;
    border-bottom-right-radius: 2px;
}

.preview-message.assistant {
    align-self: flex-start;
    background: #f3f4f6;
    color: #374151;
    border-bottom-left-radius: 2px;
}

.message-role {
    font-size: 0.7rem;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
    opacity: 0.7;
    font-weight: 600;
}

.message-text {
    white-space: pre-wrap;
}

.primary-button.small {
    padding: 0.3rem 0.8rem;
    font-size: 0.85rem;
}
</style>
