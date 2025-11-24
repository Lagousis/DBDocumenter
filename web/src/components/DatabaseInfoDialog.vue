<template>
  <transition name="fade">
    <div v-if="visible" class="dialog-backdrop">
      <div class="dialog-panel" role="dialog" aria-modal="true">
        <header class="dialog-header">
          <div>
            <h3>Database Info</h3>
            <p>Overview of tables and their statistics</p>
          </div>
          <button type="button" class="icon-button" @click="handleClose" aria-label="Close dialog">
            &times;
          </button>
        </header>

        <div class="dialog-body">
          <div v-if="loading" class="loading-state">
            <span class="spinner"></span> Loading database statistics...
          </div>
          <div v-else-if="error" class="error-state">
            {{ error }}
          </div>
          <div v-else class="stats-content">
            <div class="stats-header" v-if="totalSizePretty">
              <div class="stat-item">
                <span class="stat-label">Total Size:</span>
                <span class="stat-value">{{ totalSizePretty }}</span>
              </div>
              <button 
                type="button" 
                class="secondary-button reclaim-button" 
                @click="handleReclaimSpace"
                :disabled="reclaiming"
                title="Run VACUUM to reclaim unused space"
              >
                <span v-if="reclaiming" class="spinner small"></span>
                {{ reclaiming ? 'Reclaiming...' : 'Reclaim Space' }}
              </button>
            </div>

            <div v-if="stats.length === 0" class="empty-state">
              No tables found in the database.
            </div>
            <div v-else class="table-container">
              <table>
                <thead>
                  <tr>
                    <th @click="sortBy('name')" :class="{ active: sortKey === 'name' }">
                      Table Name
                      <span class="sort-icon">{{ sortKey === 'name' ? (sortOrder === 'asc' ? '↑' : '↓') : '' }}</span>
                    </th>
                    <th @click="sortBy('rowCount')" :class="{ active: sortKey === 'rowCount' }">
                      Row Count
                      <span class="sort-icon">{{ sortKey === 'rowCount' ? (sortOrder === 'asc' ? '↑' : '↓') : '' }}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="stat in sortedStats" :key="stat.name">
                    <td>{{ stat.name }}</td>
                    <td class="numeric">{{ formatNumber(stat.rowCount) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <footer class="dialog-actions">
          <button type="button" class="secondary-button" @click="handleClose">Close</button>
        </footer>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { fetchDatabaseStats, reclaimSpace } from "../api/client";
import { useSessionStore } from "../stores/session";

interface TableStat {
  name: string;
  rowCount: number;
}

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

const sessionStore = useSessionStore();
const loading = ref(false);
const error = ref("");
const stats = ref<TableStat[]>([]);
const sortKey = ref<keyof TableStat>("name");
const sortOrder = ref<"asc" | "desc">("asc");
const totalSizePretty = ref<string | null>(null);
const reclaiming = ref(false);

watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      await loadStats();
    }
  }
);

async function loadStats() {
  loading.value = true;
  error.value = "";
  stats.value = [];
  totalSizePretty.value = null;

  try {
    const project = sessionStore.activeProject;
    const database = sessionStore.activeDatabase;
    
    const response = await fetchDatabaseStats({ project, database });
    
    stats.value = response.tables.map((t) => ({
      name: t.name,
      rowCount: t.row_count,
    }));
    totalSizePretty.value = response.total_size_pretty || null;
  } catch (e: any) {
    console.error("Failed to load database stats", e);
    error.value = e.response?.data?.detail || e.message || "Failed to load database statistics.";
  } finally {
    loading.value = false;
  }
}

async function handleReclaimSpace() {
  if (reclaiming.value) return;
  
  reclaiming.value = true;
  try {
    const project = sessionStore.activeProject;
    const database = sessionStore.activeDatabase;
    
    const response = await reclaimSpace({ project, database });
    
    if (response.success) {
      await loadStats();
    }
  } catch (e: any) {
    console.error("Failed to reclaim space", e);
    error.value = e.response?.data?.detail || e.message || "Failed to reclaim space.";
  } finally {
    reclaiming.value = false;
  }
}

const sortedStats = computed(() => {
  return [...stats.value].sort((a, b) => {
    const modifier = sortOrder.value === "asc" ? 1 : -1;
    
    const aVal = a[sortKey.value];
    const bVal = b[sortKey.value];
    
    if (aVal === bVal) return 0;
    
    if (typeof aVal === "string" && typeof bVal === "string") {
      return aVal.localeCompare(bVal) * modifier;
    }
    // Handle potential undefined/null for other numeric fields if any (rowCount is number)
    return ((Number(aVal) || 0) - (Number(bVal) || 0)) * modifier;
  });
});

function sortBy(key: keyof TableStat) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === "asc" ? "desc" : "asc";
  } else {
    sortKey.value = key;
    sortOrder.value = "asc";
  }
}

function formatNumber(num: number): string {
  return new Intl.NumberFormat().format(num);
}

function handleClose() {
  emit("close");
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
  z-index: 1100; /* Higher than project editor if needed, but usually replaces it or sits on top */
  padding: 1rem;
}

.dialog-panel {
  width: min(700px, 100%);
  max-height: 85vh;
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
  padding: 0;
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  min-height: 300px;
}

.stats-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.table-container {
  flex: 1;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

th {
  position: sticky;
  top: 0;
  background: #f6f0e6;
  padding: 0.75rem 1rem;
  text-align: left;
  font-weight: 600;
  color: #5c4b3f;
  border-bottom: 1px solid rgba(178, 106, 69, 0.2);
  cursor: pointer;
  user-select: none;
}

th:hover {
  background: #efe6d9;
}

th.active {
  color: #b26a45;
}

td {
  padding: 0.6rem 1rem;
  border-bottom: 1px solid rgba(178, 106, 69, 0.1);
  color: #3d3129;
}

td.numeric {
  text-align: right;
  font-family: "SF Mono", "Monaco", monospace;
}

th:nth-child(2) {
  text-align: right;
}

tr:hover td {
  background: rgba(178, 106, 69, 0.05);
}

.loading-state, .error-state, .empty-state {
  padding: 3rem;
  text-align: center;
  color: #8a7b6f;
}

.error-state {
  color: #b91c1c;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(178, 106, 69, 0.3);
  border-top-color: #b26a45;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 0.5rem;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.dialog-actions {
  padding: 0.9rem 1.25rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  border-top: 1px solid rgba(178, 106, 69, 0.18);
  background: rgba(253, 248, 241, 0.9);
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
  font-size: 1.2rem;
  line-height: 1;
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

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  background: #fff;
  border-bottom: 1px solid rgba(178, 106, 69, 0.1);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.95rem;
  color: #5c4b3f;
}

.stat-label {
  font-weight: 600;
}

.stat-value {
  font-family: "SF Mono", "Monaco", monospace;
  color: #b26a45;
}

.reclaim-button {
  font-size: 0.85rem;
  padding: 0.35rem 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.reclaim-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spinner.small {
  width: 12px;
  height: 12px;
  border-width: 1.5px;
  margin-right: 0;
}
</style>
