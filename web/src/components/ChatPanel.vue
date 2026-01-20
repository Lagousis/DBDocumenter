<template>
  <div class="chat-panel">
    <div class="chat-header">
      <h2 class="section-title">Assistant</h2>
      <div class="header-actions">
        <button 
          v-if="activeProject"
          type="button" 
          class="icon-btn" 
          @click="openHistory"
          title="Chat History"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M8 3.5v4.5l3 3" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="8" cy="8" r="6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <button 
          v-if="chatHistory.length > 0" 
          type="button" 
          class="icon-btn" 
          @click="clearChat"
          title="Start new chat"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 8v5a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M10 3h3m0 0v3m0-3L7 9" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
    <div v-if="!activeProject" class="warning-banner">
      Please select a project to start chatting with the assistant.
    </div>
    <div class="transcript" ref="transcriptContainer">
      <div v-if="chatHistory.length === 0 && !loadingChat" class="empty-state">
        Ask a question about your DuckDB projects to start a conversation.
      </div>
      <div
        v-for="entry in chatHistory"
        v-show="entry.text.trim() !== ''"
        :key="entry.id"
        class="message"
        :class="entry.role"
      >
        <div class="message-header">
          <span class="label">{{ entry.role === "user" ? "You" : "Assistant" }}</span>
          <span class="timestamp">{{ formatTimestamp(entry.timestamp) }}</span>
          <button
            v-if="entry.role === 'assistant' && entry.metadata"
            type="button"
            class="info-btn"
            @click="showExecutionInfo(entry)"
            title="Show execution details"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="8" cy="8" r="6" stroke-linecap="round" stroke-linejoin="round" />
              <path d="M8 7v4M8 5v.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </div>
        <div class="message-content">
          <template v-for="(block, idx) in parseMessage(entry.text)" :key="idx">
            <div v-if="block.type === 'text'" class="text-block" v-html="block.content"></div>
            <div v-else-if="block.type === 'table'" class="table-container">
              <div class="table-header">
                <span class="table-label">Results</span>
                <button type="button" class="export-csv-btn" @click="exportTableToCsv(block)" title="Export to CSV">
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M2.5 8h11M8 2.5v11" stroke-linecap="round" stroke-linejoin="round" transform="rotate(45 8 8)"/>
                    <path d="M14 9v4.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 13.5v-9A1.5 1.5 0 0 1 3.5 3H8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  Export CSV
                </button>
              </div>
              <table class="data-table">
                <thead>
                  <tr>
                    <th v-for="(header, i) in block.headers" :key="i">{{ header }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, i) in block.rows" :key="i">
                    <td v-for="(cell, j) in row" :key="j">{{ cell }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else-if="block.type === 'chart'" class="chart-block">
              <div v-if="block.chartData?.sql" class="chart-sql-section">
                <div class="sql-header">
                  <span class="sql-label">SQL Query</span>
                  <div class="sql-actions">
                    <button type="button" class="expand-sql-btn" @click="toggleSqlExpanded(entry.id, idx)" :title="isSqlExpanded(entry.id, idx) ? 'Collapse SQL' : 'Expand SQL'">
                      <svg v-if="!isSqlExpanded(entry.id, idx)" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M4 6l4 4 4-4" stroke-linecap="round" stroke-linejoin="round" />
                      </svg>
                      <svg v-else width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M4 10l4-4 4 4" stroke-linecap="round" stroke-linejoin="round" />
                      </svg>
                      {{ isSqlExpanded(entry.id, idx) ? 'Collapse' : 'Expand' }}
                    </button>
                    <button type="button" class="open-sql-btn" @click="openSqlInTab(block.chartData.sql)" title="Open in SQL tab">
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M14 9v4.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 13.5v-9A1.5 1.5 0 0 1 3.5 3H8m3-1h4v4m-5 0L15 1" stroke-linecap="round" stroke-linejoin="round" />
                      </svg>
                      Open in SQL tab
                    </button>
                  </div>
                </div>
                <pre v-show="isSqlExpanded(entry.id, idx)" class="chart-sql-pre"><code>{{ block.chartData.sql }}</code></pre>
              </div>
              <div class="chart-preview">
                <div class="chart-preview-header">
                  <span class="chart-label">{{ block.chartData?.title || 'Chart' }}</span>
                  <button type="button" class="open-chart-btn" @click="openChartInTab(block.chartData!)" title="Open in Chart tab">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M14 9v4.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 13.5v-9A1.5 1.5 0 0 1 3.5 3H8m3-1h4v4m-5 0L15 1" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    Open in Chart tab
                  </button>
                </div>
                <svg 
                  :ref="(el) => setChartRef(entry.id, idx, el as SVGSVGElement)"
                  class="inline-chart-svg"
                  style="width: 100%; height: 250px; margin: 12px 0;"
                ></svg>
                <div class="chart-preview-info">
                  <span><strong>Type:</strong> {{ block.chartData?.chartType }}</span>
                  <span v-if="block.chartData?.xLabel"><strong>X-Axis:</strong> {{ block.chartData.xLabel }}</span>
                  <span v-if="block.chartData?.yLabel"><strong>Y-Axis:</strong> {{ block.chartData.yLabel }}</span>
                </div>
              </div>
            </div>
            <div v-else-if="block.type === 'sql'" class="sql-block">
              <div class="sql-header">
                <span class="sql-label">SQL</span>
                <div class="sql-actions">
                  <button type="button" class="expand-sql-btn" @click="toggleSqlExpanded(entry.id, idx)" :title="isSqlExpanded(entry.id, idx) ? 'Collapse SQL' : 'Expand SQL'">
                    <svg v-if="!isSqlExpanded(entry.id, idx)" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M4 6l4 4 4-4" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <svg v-else width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M4 10l4-4 4 4" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    {{ isSqlExpanded(entry.id, idx) ? 'Collapse' : 'Expand' }}
                  </button>
                  <button 
                    v-if="findPlanForSql(entry.text, idx)" 
                    type="button" 
                    class="show-plan-btn" 
                    @click="openPlanInTab(entry.text, idx, block.content)" 
                    title="Show implementation plan"
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M2 5h12M2 8h12M2 11h12" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    Show Plan
                  </button>
                  <button type="button" class="open-sql-btn" @click="openSqlInTab(block.content)" title="Open in SQL tab">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M14 9v4.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 13.5v-9A1.5 1.5 0 0 1 3.5 3H8m3-1h4v4m-5 0L15 1" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    Open in SQL tab
                  </button>
                </div>
              </div>
              <pre v-show="isSqlExpanded(entry.id, idx)"><code>{{ block.content }}</code></pre>
            </div>
          </template>
        </div>
      </div>
      <div v-if="loadingChat" class="message assistant loading-message">
        <span class="label">Assistant</span>
        <div class="loading-animation">
          <div class="loading-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
          <span class="loading-text">{{ chatStatusMessage }}</span>
        </div>
      </div>
    </div>
    <form class="composer" @submit.prevent="send">
      <div v-if="pastedImages.length > 0" class="pasted-images">
        <div v-for="(img, index) in pastedImages" :key="index" class="image-preview">
          <img :src="img.data" alt="Pasted image" />
          <button type="button" class="remove-image-btn" @click="removeImage(index)" title="Remove image">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M12 4l-8 8M4 4l8 8" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
      <div v-if="selectedFile" class="file-preview">
        <span class="file-name">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" class="file-icon">
            <path d="M3 3.5a.5.5 0 0 1 .5-.5h9a.5.5 0 0 1 .5.5v9a.5.5 0 0 1-.5.5h-9a.5.5 0 0 1-.5-.5v-9z" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M3 6h10" stroke-linecap="round"/>
          </svg>
          {{ selectedFile.name }}
        </span>
        <button type="button" class="remove-file-btn" @click="removeFile" title="Remove file">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 4l-8 8M4 4l8 8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <div class="input-area">
        <textarea
          v-model="draft"
          :disabled="loadingChat || !activeProject"
          :placeholder="activeProject ? 'Ask about schemas, generate SQL, or request ER diagrams... (Paste images to analyze)' : 'Select a project to start chatting...'"
          @keydown.enter="handleEnterKey"
          @paste="handlePaste"
        ></textarea>
        <div class="composer-actions">
          <input
            type="file"
            ref="fileInput"
            class="hidden-file-input"
            @change="handleFileSelect"
            accept=".csv,.xlsx,.xls,.txt,.json,.md"
            style="display: none"
          />
          <button 
            type="button" 
            class="attach-btn" 
            @click="triggerFileSelect"
            :disabled="loadingChat || !activeProject"
            title="Attach file"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
            </svg>
          </button>
          <button v-if="!loadingChat" type="submit" :disabled="!activeProject">
            Send
          </button>
          <button v-else type="button" class="stop-btn" @click="stopChat">
            Stop
          </button>
        </div>
      </div>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    </form>
    <ChatHistoryDialog 
        :visible="historyVisible"
        :sessions="chatSessions"
        :loading="chatSessionsLoading"
        :error="chatSessionsError"
        @close="historyVisible = false"
        @refresh="loadHistory"
        @select="loadSession"
        @delete="deleteSession"
    />
  </div>
</template>

<script setup lang="ts">
import * as d3 from "d3";
import { storeToRefs } from "pinia";
import { nextTick, onMounted, onUpdated, ref, watch } from "vue";

import { useSessionStore } from "../stores/session";
import ChatHistoryDialog from "./ChatHistoryDialog.vue";

const sessionStore = useSessionStore();
const { chatHistory, loadingChat, activeProject, chatSessions, chatSessionsLoading, chatSessionsError, chatStatusMessage } = storeToRefs(sessionStore);
const draft = ref("");
const errorMessage = ref("");
const expandedSqlBlocks = ref<Set<string>>(new Set());
const chartRefs = ref<Map<string, SVGSVGElement>>(new Map());
const historyVisible = ref(false);
const transcriptContainer = ref<HTMLElement | null>(null);

// File Upload State
const selectedFile = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const pastedImages = ref<Array<{ data: string; name: string }>>([])

const colorPalette = [
  "#3b82f6", // blue
  "#10b981", // green
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // purple
  "#ec4899", // pink
  "#14b8a6", // teal
  "#f97316", // orange
];

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    selectedFile.value = input.files[0];
  }
  // Reset input so same file can be selected again if needed
  input.value = "";
}

function triggerFileSelect() {
  fileInput.value?.click();
}

function removeFile() {
  selectedFile.value = null;
}

function stopChat(): void {
  sessionStore.stopChat();
}

async function handlePaste(event: ClipboardEvent) {
  const items = event.clipboardData?.items;
  if (!items) return;

  for (const item of Array.from(items)) {
    if (item.type.startsWith('image/')) {
      event.preventDefault();
      const file = item.getAsFile();
      if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const base64 = e.target?.result as string;
          pastedImages.value.push({
            data: base64,
            name: `pasted-image-${Date.now()}.${item.type.split('/')[1]}`
          });
        };
        reader.readAsDataURL(file);
      }
    }
  }
}

function removeImage(index: number) {
  pastedImages.value.splice(index, 1);
}

interface MessageBlock {
  type: "text" | "table" | "sql" | "plan" | "chart";
  content?: string;
  headers?: string[];
  rows?: string[][];
  chartData?: {
    chartType: string;
    title: string;
    xLabel: string;
    yLabel: string;
    labels: string[];
    datasets: Array<{ label: string; data: number[]; color?: string }>;
    sql?: string;
    plan?: string;
  };
}

function parseMessage(text: string): MessageBlock[] {
  const blocks: MessageBlock[] = [];
  let currentPos = 0;
  
  // First, extract and remove [PLAN:...] markers
  const planMarkerPattern = /\[PLAN:(.*?)\]\n?/g;
  const planMatches: Array<{ content: string; start: number; end: number }> = [];
  let planMatch;
  while ((planMatch = planMarkerPattern.exec(text)) !== null) {
    planMatches.push({
      content: planMatch[1],
      start: planMatch.index,
      end: planMatch.index + planMatch[0].length
    });
  }
  
  // Remove plan markers from text
  let cleanedText = text;
  for (let i = planMatches.length - 1; i >= 0; i--) {
    const pm = planMatches[i];
    cleanedText = cleanedText.substring(0, pm.start) + cleanedText.substring(pm.end);
  }

  // Match SQL code blocks (```sql ... ```)
  const sqlPattern = /```sql\n([\s\S]*?)```/g;
  // Match chart JSON blocks (```chart ... ``` or CHART: {...})
  const chartPattern = /```chart\n([\s\S]*?)```|CHART:\s*(\{[\s\S]*?\})/g;
  // Match table-like structures - properly match consecutive lines with pipes
  // This regex matches one or more consecutive lines that contain pipes
  const tablePattern = /((?:^|\n)(?:[^\n]*\|[^\n]*\n?)+)/gm;

  const matches: Array<{ type: "sql" | "table" | "chart"; start: number; end: number; match: RegExpMatchArray }> = [];

  // Find all SQL blocks
  let match;
  while ((match = sqlPattern.exec(cleanedText)) !== null) {
    matches.push({ type: "sql", start: match.index, end: match.index + match[0].length, match });
  }

  // Find all chart blocks
  while ((match = chartPattern.exec(cleanedText)) !== null) {
    matches.push({ type: "chart", start: match.index, end: match.index + match[0].length, match });
  }

  // Find all table blocks
  while ((match = tablePattern.exec(cleanedText)) !== null) {
    matches.push({ type: "table", start: match.index, end: match.index + match[0].length, match });
  }

  // Sort by position
  matches.sort((a, b) => a.start - b.start);
  
  // Track which SQL block we're on for plan association
  let sqlBlockIndex = 0;

  for (const m of matches) {
    // Add text before this match
    if (currentPos < m.start) {
      const textContent = cleanedText.substring(currentPos, m.start).trim();
      if (textContent) {
        blocks.push({
          type: "text",
          content: markdownToHtml(textContent),
        });
      }
    }

    if (m.type === "sql") {
      // Add plan block before SQL if we have one
      if (sqlBlockIndex < planMatches.length && planMatches[sqlBlockIndex]) {
        blocks.push({
          type: "plan",
          content: planMatches[sqlBlockIndex].content,
        });
      }
      
      blocks.push({
        type: "sql",
        content: m.match[1].trim(),
      });
      sqlBlockIndex++;
    } else if (m.type === "chart") {
      const chartJson = m.match[1] || m.match[2]; // From ```chart or CHART:
      console.log("ChatPanel - Found chart block, raw JSON:", chartJson);
      try {
        const chartData = JSON.parse(chartJson);
        console.log("ChatPanel - Parsed chart data:", chartData);
        blocks.push({
          type: "chart",
          chartData,
        });
      } catch (e) {
        // If JSON parsing fails, treat as text
        console.warn("Failed to parse chart JSON:", e);
        blocks.push({
          type: "text",
          content: markdownToHtml(m.match[0]),
        });
      }
    } else if (m.type === "table") {
      const tableData = parseTable(m.match[1]);
      if (tableData) {
        blocks.push(tableData);
      } else {
        // If parsing failed, treat as text
        blocks.push({
          type: "text",
          content: markdownToHtml(m.match[1]),
        });
      }
    }

    currentPos = m.end;
  }

  // Add remaining text
  if (currentPos < cleanedText.length) {
    const textContent = cleanedText.substring(currentPos).trim();
    if (textContent) {
      blocks.push({
        type: "text",
        content: markdownToHtml(textContent),
      });
    }
  }

  // If no blocks were created, return the whole text as one block
  if (blocks.length === 0) {
    blocks.push({
      type: "text",
      content: markdownToHtml(text),
    });
  }

  return blocks;
}

function parseTable(tableText: string): MessageBlock | null {
  // Filter out lines that are just borders (start with +) unless they contain |
  const lines = tableText.trim().split("\n").filter(line => line.includes("|"));
  
  if (lines.length < 2) return null;

  const rows = lines.map(line => {
    // Split by pipe and remove first/last empty elements from outer pipes
    const cells = line.split("|");
    // Remove leading empty cell if line starts with |
    if (cells[0].trim() === "") cells.shift();
    // Remove trailing empty cell if line ends with |
    if (cells.length > 0 && cells[cells.length - 1].trim() === "") cells.pop();
    // Trim each cell but preserve empty cells
    return cells.map(cell => cell.trim());
  });

  // Check if second line is a separator (contains mostly - and |)
  // Note: rows[1] is the parsed cells of the second line
  const isSeparatorLine = (line: string[]) => 
    line.every(cell => /^[-:|\s]*$/.test(cell));

  if (rows.length >= 2 && isSeparatorLine(rows[1])) {
    // Markdown-style table with header separator
    return {
      type: "table",
      headers: rows[0],
      rows: rows.slice(2),
    };
  } 
  
  // For loose tables (no separator), check column consistency to avoid false positives
  const colCounts = rows.map(r => r.length);
  const isConsistent = new Set(colCounts).size === 1;

  if (rows.length >= 1 && isConsistent) {
    // Simple table without separator
    return {
      type: "table",
      headers: rows[0],
      rows: rows.slice(1),
    };
  }

  return null;
}

function exportTableToCsv(block: MessageBlock): void {
  if (block.type !== "table" || !block.headers || !block.rows) {
    return;
  }

  const csvEscape = (value: unknown): string => {
    const text = value === null || value === undefined ? "" : String(value);
    if (/[",\n\r]/.test(text)) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  };

  const lines: string[] = [];
  lines.push(block.headers.map(csvEscape).join(","));
  for (const row of block.rows) {
    lines.push(row.map(csvEscape).join(","));
  }

  const csv = lines.join("\r\n") + "\r\n";
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const date = new Date();
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const filename = `query_results_${yyyy}-${mm}-${dd}.csv`;

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function markdownToHtml(text: string): string {
  let html = escapeHtml(text);
  
  // Bold: **text** or __text__
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
  
  // Italic: *text* only (removed single underscore support to preserve table names with underscores)
  html = html.replace(/\*([^\s*][^\*]*?)\*/g, '<em>$1</em>');
  
  // Inline code: `text`
  html = html.replace(/`(.+?)`/g, '<code>$1</code>');
  
  // Lists with bullets (• character)
  html = html.replace(/^•\s+(.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
  
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  
  return html;
}

function openSqlInTab(sql: string | undefined): void {
  if (!sql) return;
  sessionStore.createQueryTab({ sql, makeActive: true });
}

function openChartInTab(chartData: NonNullable<MessageBlock['chartData']>): void {
  sessionStore.createChartTab({
    chartType: chartData.chartType as "bar" | "horizontal-bar" | "line" | "pie" | "scatter" | "area",
    data: {
      labels: chartData.labels,
      datasets: chartData.datasets,
    },
    title: chartData.title || "Chart",
    xLabel: chartData.xLabel || "",
    yLabel: chartData.yLabel || "",
    sql: chartData.sql,
    plan: chartData.plan,
    makeActive: true,
  });
}

function findPlanForSql(messageText: string, blockIndex: number): string | null {
  // Parse the message to find blocks
  const blocks = parseMessage(messageText);
  
  // Check if the block at blockIndex is SQL and if there's a plan right before it
  if (blockIndex > 0 && 
      blocks[blockIndex] && 
      blocks[blockIndex].type === 'sql' &&
      blocks[blockIndex - 1] && 
      blocks[blockIndex - 1].type === 'plan') {
    return blocks[blockIndex - 1].content || null;
  }
  return null;
}

function openPlanInTab(messageText: string, blockIndex: number, sql: string | undefined): void {
  if (!sql) return;
  const planContent = findPlanForSql(messageText, blockIndex);
  if (planContent) {
    // Count existing plan tabs to generate sequential name
    const existingPlanTabs = sessionStore.workspaceTabs.filter(
      tab => tab.type === 'markdown' && tab.title.startsWith('Plan ')
    );
    const planNumber = existingPlanTabs.length + 1;
    const title = `Plan ${planNumber}`;
    
    // Format the plan content with the SQL included
    const lines: string[] = [];
    lines.push("# Implementation Plan");
    lines.push("");
    lines.push(planContent);
    lines.push("");
    lines.push("## SQL Query");
    lines.push("");
    lines.push("```sql");
    lines.push(sql);
    lines.push("```");
    
    const content = lines.join("\n");
    
    sessionStore.createMarkdownTab({ 
      content, 
      title,
      makeActive: true 
    });
  }
}

function toggleSqlExpanded(messageId: string, blockIndex: number): void {
  const key = `${messageId}-${blockIndex}`;
  if (expandedSqlBlocks.value.has(key)) {
    expandedSqlBlocks.value.delete(key);
  } else {
    expandedSqlBlocks.value.add(key);
  }
}

function isSqlExpanded(messageId: string, blockIndex: number): boolean {
  const key = `${messageId}-${blockIndex}`;
  return expandedSqlBlocks.value.has(key);
}

function clearChat(): void {
  // Clear the chat history in the store
  sessionStore.clearChatHistory();
  // Clear the expanded SQL blocks
  expandedSqlBlocks.value.clear();
}

function formatTimestamp(timestamp: number): string {
  if (!timestamp) return '';
  const date = new Date(timestamp); // timestamp is already in milliseconds
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const messageDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  
  const timeStr = date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit',
    hour12: false 
  });
  
  if (messageDate.getTime() === today.getTime()) {
    return timeStr;
  } else {
    const dateStr = date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric' 
    });
    return `${dateStr} ${timeStr}`;
  }
}

function openHistory() {
    historyVisible.value = true;
    loadHistory();
}

async function loadHistory() {
    await sessionStore.loadChatHistory();
}

async function loadSession(id: string) {
    await sessionStore.loadChatSession(id);
    historyVisible.value = false;
}

async function deleteSession(id: string) {
    if (confirm("Are you sure you want to delete this chat session?")) {
        await sessionStore.deleteChatSession(id);
    }
}

function handleEnterKey(event: KeyboardEvent): void {
  // If Shift+Enter, allow default behavior (new line)
  if (event.shiftKey) {
    return;
  }
  
  // Otherwise, prevent default and send the message
  event.preventDefault();
  send();
}

async function send(): Promise<void> {
  if (!activeProject.value) {
    errorMessage.value = "Please select a project first.";
    return;
  }
  if (!draft.value.trim() && !selectedFile.value && pastedImages.value.length === 0) {
    errorMessage.value = "Enter a question, attach a file, or paste an image.";
    return;
  }
  errorMessage.value = "";
  const content = draft.value;
  const file = selectedFile.value;
  const images = [...pastedImages.value];
  
  draft.value = "";
  selectedFile.value = null;
  pastedImages.value = [];
  
  try {
    let fileData = undefined;
    if (file) {
      let content = "";
      // Check for binary file types (Excel)
      const isBinary = /\.(xlsx|xls)$/i.test(file.name);
      
      if (isBinary) {
        // Read as base64 for binary files
        content = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result as string);
          reader.onerror = reject;
          reader.readAsDataURL(file);
        });
      } else {
        // Read as text for others
        content = await file.text();
      }
      
      fileData = { name: file.name, content };
    }
    
    await sessionStore.sendMessage(content, fileData, images.length > 0 ? images : undefined);
  } catch (error) {
    // Don't show error message if the operation was cancelled by the user
    const isCancelled = error instanceof Error && (error.name === 'AbortError' || error.message.includes('cancelled'));
    if (!isCancelled) {
      errorMessage.value = error instanceof Error ? error.message : "Chat request failed.";
      draft.value = content;
      selectedFile.value = file; // Restore file on error
      pastedImages.value = images; // Restore images on error
    }
  }
}

function showExecutionInfo(entry: any): void {
  const metadata = entry.metadata;
  if (!metadata) return;

  // Format the execution details as markdown
  const lines: string[] = [];
  lines.push("# Agent Execution Details");
  lines.push("");
  
  // Summary section
  lines.push("## Summary");
  lines.push("");
  if (metadata.model) {
    lines.push(`- **Model:** ${metadata.model}`);
  }
  if (metadata.execution_time_seconds !== undefined) {
    lines.push(`- **Execution Time:** ${metadata.execution_time_seconds.toFixed(2)}s`);
  }
  if (metadata.iterations !== undefined) {
    lines.push(`- **Iterations:** ${metadata.iterations} (each iteration = 1 API call to the model)`);
  }
  if (metadata.api_calls !== undefined) {
    lines.push(`- **Total API Calls:** ${metadata.api_calls}`);
  }
  
  lines.push("");
  
  // Token usage
  lines.push("## Token Usage");
  lines.push("");
  lines.push("*Tokens are units of text processed by the AI model. More tokens = higher cost.*");
  lines.push("");
  if (metadata.total_tokens !== undefined) {
    lines.push(`- **Total Tokens:** ${metadata.total_tokens}`);
  }
  if (metadata.prompt_tokens !== undefined) {
    lines.push(`- **Prompt Tokens:** ${metadata.prompt_tokens} (input to model)`);
  }
  if (metadata.completion_tokens !== undefined) {
    lines.push(`- **Completion Tokens:** ${metadata.completion_tokens} (generated by model)`);
  }
  
  lines.push("");
  
  // Tools execution flow
  if (metadata.tools_used && metadata.tools_used.length > 0) {
    lines.push("## Tool Execution Flow");
    lines.push("");
    lines.push("*The agent called the following tools in sequence to complete your request:*");
    lines.push("");
    
    metadata.tools_used.forEach((tool: any, index: number) => {
      lines.push(`### Step ${index + 1}: \`${tool.name}\``);
      lines.push("");
      
      // Add description based on tool name
      if (tool.name === "duckdb_schema") {
        lines.push("**Purpose:** Retrieve database schema information");
      } else if (tool.name === "duckdb_query") {
        lines.push("**Purpose:** Execute SQL query against the database");
      }
      lines.push("");
      
      if (tool.arguments && Object.keys(tool.arguments).length > 0) {
        // Show SQL in nice code block if present
        if (tool.arguments.sql) {
          lines.push("**SQL Query:**");
          lines.push("");
          lines.push("```sql");
          lines.push(tool.arguments.sql);
          lines.push("```");
          lines.push("");
        }
        
        // Show implementation plan if present
        if (tool.arguments.plan) {
          lines.push("**Implementation Plan:**");
          lines.push("");
          lines.push(tool.arguments.plan);
          lines.push("");
        }
        
        // Show other parameters
        lines.push("**Input Parameters:**");
        lines.push("");
        
        // Format arguments with descriptions
        Object.entries(tool.arguments).forEach(([key, value]) => {
          // Skip sql and plan as they're shown above
          if (key === "sql" || key === "plan") {
            return;
          }
          
          if (key === "action") {
            lines.push(`- **${key}:** \`${value}\` - Schema operation to perform`);
          } else if (key === "table_name") {
            lines.push(`- **${key}:** \`${value}\` - Target table`);
          } else {
            lines.push(`- **${key}:** \`${JSON.stringify(value)}\``);
          }
        });
        lines.push("");
        
        // Add detailed JSON for reference
        lines.push("<details>");
        lines.push("<summary>View full JSON</summary>");
        lines.push("");
        lines.push("```json");
        lines.push(JSON.stringify(tool.arguments, null, 2));
        lines.push("```");
        lines.push("</details>");
        lines.push("");
      }
      
      // Add separator between steps
      if (index < metadata.tools_used.length - 1) {
        lines.push("---");
        lines.push("");
      }
    });
  } else {
    lines.push("## Tool Execution Flow");
    lines.push("");
    lines.push("*No tools were called. The agent responded directly without executing any operations.*");
  }

  const content = lines.join("\n");
  
  // Create a markdown tab with execution info
  sessionStore.createMarkdownTab({
    content,
    title: "Execution Info",
    makeActive: true
  });
}

function setChartRef(entryId: string, blockIndex: number, el: SVGSVGElement | null): void {
  const key = `${entryId}-${blockIndex}`;
  if (el) {
    chartRefs.value.set(key, el);
  } else {
    chartRefs.value.delete(key);
  }
}

function renderInlineCharts(): void {
  chatHistory.value.forEach((entry) => {
    const blocks = parseMessage(entry.text);
    blocks.forEach((block, idx) => {
      if (block.type === "chart" && block.chartData) {
        const key = `${entry.id}-${idx}`;
        const svgElement = chartRefs.value.get(key);
        if (svgElement && block.chartData.labels && block.chartData.datasets) {
          renderInlineChart(svgElement, block.chartData);
        }
      }
    });
  });
}

function renderInlineChart(
  svgElement: SVGSVGElement,
  chartData: NonNullable<MessageBlock["chartData"]>
): void {
  const svg = d3.select(svgElement);
  svg.selectAll("*").remove();

  const containerWidth = svgElement.clientWidth || 600;
  const containerHeight = 250;
  const margin = { top: 20, right: 80, bottom: 60, left: 50 };
  const width = containerWidth - margin.left - margin.right;
  const height = containerHeight - margin.top - margin.bottom;

  svg.attr("width", containerWidth).attr("height", containerHeight);

  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  const labels = chartData.labels;
  const datasets = chartData.datasets;

  if (!datasets || datasets.length === 0 || !labels || labels.length === 0) return;

  // Render based on chart type
  if (chartData.chartType === "bar") {
    // X scale
    const x0 = d3.scaleBand().domain(labels).rangeRound([0, width]).paddingInner(0.1);
    const x1 = d3
      .scaleBand()
      .domain(datasets.map((d) => d.label))
      .rangeRound([0, x0.bandwidth()])
      .padding(0.05);

    // Y scale
    const maxValue = d3.max(datasets.flatMap((d) => d.data)) ?? 0;
    const y = d3.scaleLinear().domain([0, maxValue * 1.1]).range([height, 0]);

    // X axis
    g.append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(x0))
      .selectAll("text")
      .attr("transform", "rotate(-45)")
      .style("text-anchor", "end")
      .style("font-size", "10px");

    // Y axis
    g.append("g").call(d3.axisLeft(y).ticks(5));

    // Bars
    const labelGroups = g
      .selectAll(".label-group")
      .data(labels)
      .enter()
      .append("g")
      .attr("class", "label-group")
      .attr("transform", (d) => `translate(${x0(d)},0)`);

    datasets.forEach((dataset, i) => {
      labelGroups
        .append("rect")
        .attr("x", x1(dataset.label) ?? 0)
        .attr("y", (d, idx) => y(dataset.data[idx]))
        .attr("width", x1.bandwidth())
        .attr("height", (d, idx) => height - y(dataset.data[idx]))
        .attr("fill", dataset.color || colorPalette[i % colorPalette.length]);
    });

    // Legend
    const legend = g
      .append("g")
      .attr("class", "legend")
      .attr("transform", `translate(${width + 10}, 0)`);

    datasets.forEach((dataset, i) => {
      const legendRow = legend.append("g").attr("transform", `translate(0, ${i * 20})`);
      legendRow
        .append("rect")
        .attr("width", 12)
        .attr("height", 12)
        .attr("fill", dataset.color || colorPalette[i % colorPalette.length]);
      legendRow
        .append("text")
        .attr("x", 16)
        .attr("y", 10)
        .style("font-size", "11px")
        .text(dataset.label);
    });
  } else if (chartData.chartType === "horizontal-bar") {
    // Y scale (for labels/categories)
    const y0 = d3.scaleBand().domain(labels).rangeRound([0, height]).paddingInner(0.1);
    const y1 = d3
      .scaleBand()
      .domain(datasets.map((d) => d.label))
      .rangeRound([0, y0.bandwidth()])
      .padding(0.05);

    // X scale (for values)
    const maxValue = d3.max(datasets.flatMap((d) => d.data)) ?? 0;
    const x = d3.scaleLinear().domain([0, maxValue * 1.1]).range([0, width]);

    // Y axis (categories)
    g.append("g").call(d3.axisLeft(y0)).selectAll("text").style("font-size", "10px");

    // X axis (values)
    g.append("g").attr("transform", `translate(0,${height})`).call(d3.axisBottom(x).ticks(5));

    // Bars
    const labelGroups = g
      .selectAll(".label-group")
      .data(labels)
      .enter()
      .append("g")
      .attr("class", "label-group")
      .attr("transform", (d) => `translate(0,${y0(d)})`);

    datasets.forEach((dataset, i) => {
      labelGroups
        .append("rect")
        .attr("y", y1(dataset.label) ?? 0)
        .attr("x", 0)
        .attr("height", y1.bandwidth())
        .attr("width", (d, idx) => x(dataset.data[idx]))
        .attr("fill", dataset.color || colorPalette[i % colorPalette.length]);
    });

    // Legend
    const legend = g
      .append("g")
      .attr("class", "legend")
      .attr("transform", `translate(${width + 10}, 0)`);

    datasets.forEach((dataset, i) => {
      const legendRow = legend.append("g").attr("transform", `translate(0, ${i * 20})`);
      legendRow
        .append("rect")
        .attr("width", 12)
        .attr("height", 12)
        .attr("fill", dataset.color || colorPalette[i % colorPalette.length]);
      legendRow
        .append("text")
        .attr("x", 16)
        .attr("y", 10)
        .style("font-size", "11px")
        .text(dataset.label);
    });
  } else if (chartData.chartType === "line") {
    // X scale
    const x = d3.scalePoint().domain(labels).range([0, width]).padding(0.5);

    // Y scale
    const maxValue = d3.max(datasets.flatMap((d) => d.data)) ?? 0;
    const y = d3.scaleLinear().domain([0, maxValue * 1.1]).range([height, 0]);

    // X axis
    g.append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .attr("transform", "rotate(-45)")
      .style("text-anchor", "end")
      .style("font-size", "10px");

    // Y axis
    g.append("g").call(d3.axisLeft(y).ticks(5));

    // Line generator
    const line = d3
      .line<number>()
      .x((d, i) => x(labels[i]) ?? 0)
      .y((d) => y(d));

    // Draw lines
    datasets.forEach((dataset, i) => {
      g.append("path")
        .datum(dataset.data)
        .attr("fill", "none")
        .attr("stroke", dataset.color || colorPalette[i % colorPalette.length])
        .attr("stroke-width", 2)
        .attr("d", line);

      // Add points
      g.selectAll(`.point-${i}`)
        .data(dataset.data)
        .enter()
        .append("circle")
        .attr("class", `point-${i}`)
        .attr("cx", (d, idx) => x(labels[idx]) ?? 0)
        .attr("cy", (d) => y(d))
        .attr("r", 3)
        .attr("fill", dataset.color || colorPalette[i % colorPalette.length]);
    });

    // Legend
    const legend = g
      .append("g")
      .attr("class", "legend")
      .attr("transform", `translate(${width + 10}, 0)`);

    datasets.forEach((dataset, i) => {
      const legendRow = legend.append("g").attr("transform", `translate(0, ${i * 20})`);
      legendRow
        .append("rect")
        .attr("width", 12)
        .attr("height", 12)
        .attr("fill", dataset.color || colorPalette[i % colorPalette.length]);
      legendRow
        .append("text")
        .attr("x", 16)
        .attr("y", 10)
        .style("font-size", "11px")
        .text(dataset.label);
    });
  } else if (chartData.chartType === "pie") {
    // For pie chart, use first dataset's data
    const dataset = datasets[0];
    const pieData = labels.map((label, i) => ({
      label,
      value: dataset.data[i],
      color: colorPalette[i % colorPalette.length]
    }));

    const radius = Math.min(width, height) / 2;
    const centerX = width / 2;
    const centerY = height / 2;

    const pie = d3.pie<{ label: string; value: number; color: string }>().value(d => d.value);
    const arc = d3.arc<d3.PieArcDatum<{ label: string; value: number; color: string }>>()
      .innerRadius(0)
      .outerRadius(radius);

    const pieGroup = g.append("g")
      .attr("transform", `translate(${centerX}, ${centerY})`);

    const arcs = pieGroup.selectAll(".arc")
      .data(pie(pieData))
      .enter()
      .append("g")
      .attr("class", "arc");

    arcs.append("path")
      .attr("d", arc)
      .attr("fill", d => d.data.color)
      .attr("stroke", "#fff")
      .attr("stroke-width", 2);

    // Add labels with values
    arcs.append("text")
      .attr("transform", d => `translate(${arc.centroid(d)})`)
      .attr("text-anchor", "middle")
      .attr("font-size", "11px")
      .attr("fill", "#fff")
      .attr("font-weight", "600")
      .text(d => {
        const percent = ((d.data.value / d3.sum(pieData, p => p.value)!) * 100).toFixed(1);
        return `${percent}%`;
      });

    // Legend
    const legend = g
      .append("g")
      .attr("class", "legend")
      .attr("transform", `translate(${width + 10}, 0)`);

    pieData.forEach((d, i) => {
      const legendRow = legend.append("g").attr("transform", `translate(0, ${i * 20})`);
      legendRow
        .append("rect")
        .attr("width", 12)
        .attr("height", 12)
        .attr("fill", d.color);
      legendRow
        .append("text")
        .attr("x", 16)
        .attr("y", 10)
        .style("font-size", "11px")
        .text(d.label);
    });
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (transcriptContainer.value) {
      transcriptContainer.value.scrollTop = transcriptContainer.value.scrollHeight;
    }
  });
}

watch(
  [chatHistory, loadingChat],
  () => {
    scrollToBottom();
  },
  { deep: true }
);

onMounted(() => {
  renderInlineCharts();
  scrollToBottom();
});

onUpdated(() => {
  nextTick(() => {
    renderInlineCharts();
  });
});
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 0.75rem;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.section-title {
  margin: 0;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  color: #64748b;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn:hover {
  background: #f1f5f9;
  color: #334155;
}

.icon-btn.danger {
    color: #ef4444;
    border-color: #ef4444;
}

.icon-btn.danger:hover {
    background: #ef4444;
    color: white;
}

.clear-chat-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: transparent;
  color: #ef4444;
  border: 1px solid #ef4444;
  border-radius: 6px;
  padding: 0.35rem 0.7rem;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-chat-btn:hover {
  background: #ef4444;
  color: white;
}

.warning-banner {
  background-color: #fef3c7;
  border: 1px solid #fbbf24;
  color: #92400e;
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
  text-align: center;
}

.transcript {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.message {
  padding: 0.6rem 0.75rem;
  border-radius: 10px;
  background-color: #eff6ff;
  color: #0f172a;
}

.message.assistant {
  background-color: #e2e8f0;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.label {
  font-weight: 600;
  font-size: 0.75rem;
  color: #1e3a8a;
  text-transform: uppercase;
}

.timestamp {
  font-size: 0.7rem;
  color: #64748b;
  margin-left: auto;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.text-block {
  line-height: 1.5;
}

.text-block strong {
  font-weight: 600;
  color: #1e293b;
}

.text-block em {
  font-style: italic;
}

.text-block code {
  background-color: #f1f5f9;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-family: "Consolas", "Monaco", "Courier New", monospace;
  font-size: 0.9em;
  color: #be123c;
}

.text-block ul {
  margin: 0.5rem 0;
  padding-left: 0;
  list-style: none;
}

.text-block li {
  padding-left: 1.5rem;
  position: relative;
  margin: 0.25rem 0;
}

.text-block li::before {
  content: "•";
  position: absolute;
  left: 0.5rem;
  color: #64748b;
}

.table-container {
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  padding: 0 0.25rem;
}

.table-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #475569;
}

.export-csv-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: transparent;
  color: #10b981;
  border: 1px solid #10b981;
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.export-csv-btn:hover {
  background: #10b981;
  color: white;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  background: white;
}

.data-table thead {
  background-color: #f1f5f9;
  border-bottom: 2px solid #cbd5e1;
}

.data-table th {
  padding: 0.5rem 0.75rem;
  text-align: left;
  font-weight: 600;
  color: #334155;
}

.data-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #e2e8f0;
  color: #1e293b;
}

.data-table tbody tr:hover {
  background-color: #f8fafc;
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.sql-block {
  background-color: #1e293b;
  border-radius: 6px;
  overflow: hidden;
}

.sql-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
}

.sql-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
}

.sql-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.expand-sql-btn,
.show-plan-btn,
.open-sql-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: transparent;
  color: #60a5fa;
  border: 1px solid #3b82f6;
  border-radius: 4px;
  padding: 0.3rem 0.6rem;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.expand-sql-btn:hover,
.show-plan-btn:hover,
.open-sql-btn:hover {
  background: #1e40af;
  color: #93c5fd;
  border-color: #60a5fa;
}

.expand-sql-btn:disabled,
.show-plan-btn:disabled,
.open-sql-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sql-block pre {
  margin: 0;
  padding: 0.75rem;
  overflow-x: auto;
}

.sql-block code {
  color: #e2e8f0;
  font-family: "Consolas", "Monaco", "Courier New", monospace;
  font-size: 0.85rem;
  line-height: 1.5;
}

.chart-block {
  background-color: #f8fafc;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.chart-sql-section {
  border-bottom: 1px solid #cbd5e1;
}

.chart-sql-pre {
  margin: 0;
  padding: 0.75rem;
  overflow-x: auto;
  background-color: #1e293b;
  color: #e2e8f0;
  font-family: "Consolas", "Monaco", "Courier New", monospace;
  font-size: 0.85rem;
  line-height: 1.5;
}

.chart-preview {
  padding: 0.75rem;
}

.chart-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.chart-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: #334155;
}

.chart-preview-info {
  display: flex;
  gap: 1rem;
  font-size: 0.8rem;
  color: #64748b;
}

.open-chart-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: transparent;
  color: #3b82f6;
  border: 1px solid #3b82f6;
  border-radius: 4px;
  padding: 0.3rem 0.6rem;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.open-chart-btn:hover {
  background: #3b82f6;
  color: white;
}

.composer {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  background: white;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0.5rem;
}

.file-preview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #f1f5f9;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  font-size: 0.85rem;
  color: #334155;
  border: 1px solid #e2e8f0;
}

.pasted-images {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.image-preview {
  position: relative;
  width: 120px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid #e2e8f0;
  background: #f8fafc;
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.remove-image-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background: rgba(0, 0, 0, 0.6);
  border: none;
  color: white;
  cursor: pointer;
  padding: 0.3rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
}

.remove-image-btn:hover {
  background: rgba(239, 68, 68, 0.9);
  transform: scale(1.1);
}

.file-name {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-icon {
  color: #64748b;
  flex-shrink: 0;
}

.remove-file-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 0.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.remove-file-btn:hover {
  background-color: #e2e8f0;
  color: #ef4444;
}

.input-area {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

textarea {
  min-height: 60px;
  border: none;
  padding: 0.25rem;
  resize: vertical;
  font-family: "Inter", "Segoe UI", sans-serif;
  outline: none;
  width: 100%;
}

.composer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 0.25rem;
  border-top: 1px solid #f1f5f9;
}

.attach-btn {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.attach-btn:hover {
  background-color: #f1f5f9;
  color: #3b82f6;
}

.attach-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

button[type="submit"] {
  background-color: #1d4ed8;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  padding: 0.4rem 0.9rem;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: background-color 0.2s;
}

button[type="submit"]:hover {
  background-color: #1e40af;
}

button[type="submit"]:disabled {
  background-color: #94a3b8;
  cursor: not-allowed;
}

.stop-btn {
  background-color: #ef4444;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  padding: 0.4rem 0.9rem;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: background-color 0.2s;
}

.stop-btn:hover {
  background-color: #dc2626;
}

.error {
  color: #b91c1c;
  font-size: 0.8rem;
  margin: 0;
}

.empty-state {
  color: #64748b;
  text-align: center;
  padding: 2rem;
  font-style: italic;
}

.loading-message {
  opacity: 0.9;
}

.loading-animation {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.loading-dots {
  display: flex;
  gap: 0.4rem;
}

.loading-dots .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #60a5fa;
  animation: pulse 1.4s infinite ease-in-out;
}

.loading-dots .dot:nth-child(1) {
  animation-delay: 0s;
}

.loading-dots .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes pulse {
  0%, 60%, 100% {
    transform: scale(1);
    opacity: 0.5;
  }
  30% {
    transform: scale(1.3);
    opacity: 1;
  }
}

.loading-text {
  color: #64748b;
  font-size: 0.9rem;
  font-style: italic;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.info-btn {
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.25rem;
  transition: all 0.2s ease;
  opacity: 0.6;
}

.info-btn:hover {
  color: #3b82f6;
  background-color: rgba(59, 130, 246, 0.1);
  opacity: 1;
}

.info-btn svg {
  width: 16px;
  height: 16px;
}
</style>
