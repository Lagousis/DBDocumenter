<template>
  <div class="er-diagram">
    <div class="diagram-header">
      <h2 class="section-title">{{ tab.title }}</h2>
      <div class="header-actions">
        <button
          type="button"
          class="edit-button"
          title="Edit diagram name and description"
          @click="openEditDiagramDialog"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.2">
            <path d="M11 2l3 3-8 8H3v-3l8-8z" />
            <path d="M10 3l3 3" />
          </svg>
          <span>Edit</span>
        </button>
        <button
          type="button"
          class="save-button"
          title="Save this layout for later"
          :disabled="!diagramData"
          @click="openSaveDiagramDialog"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.2">
            <path d="M4 2h7l3 3v9a1 1 0 01-1 1H3a1 1 0 01-1-1V3a1 1 0 011-1z" />
            <path d="M5 2v4h6V2" />
            <rect x="6" y="10" width="4" height="3" rx="0.6" />
          </svg>
          <span>Save</span>
        </button>
        <button
          type="button"
          class="export-button"
          :disabled="exporting"
          :aria-busy="exporting"
          @click="exportDiagram"
        >
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path
              d="M10 2a.75.75 0 01.75.75v7.19l2.22-2.22a.75.75 0 111.06 1.06l-3.5 3.5a.75.75 0 01-1.06 0l-3.5-3.5a.75.75 0 011.06-1.06l2.22 2.22V2.75A.75.75 0 0110 2zm-6 11.5a1.5 1.5 0 011.5-1.5h9a1.5 1.5 0 011.5 1.5v2a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 014 15.5v-2z"
              fill="currentColor"
            />
          </svg>
          <span>{{ exporting ? "Exporting…" : "Export" }}</span>
        </button>
      </div>
    </div>
    <div v-if="!tables.length" class="diagram-body">
      <p class="empty-state">
        Diagram has no tables to render yet. Open a diagram from the schema panel to get started.
      </p>
    </div>
    <div v-else class="diagram-body populated">
      <div class="diagram-view full-width">
        <div v-if="!diagramData" class="diagram-placeholder">
          No schema metadata available for the selected tables yet.
        </div>
        <div v-else ref="diagramElement" class="diagram-svg"></div>
        <p v-if="renderError" class="diagram-error" role="alert">
          Unable to render diagram: {{ renderError }}
        </p>
      </div>
    </div>
    <DiagramSaveDialog
      :visible="showSaveDialog"
      :loading="saveDialogLoading"
      :error="saveDialogError"
      :default-name="tab.title"
      :default-description="tab.diagramDescription ?? ''"
      @close="closeSaveDiagramDialog"
      @submit="handleSaveDiagram"
    />
    <DiagramEditorDialog
      :visible="showEditDialog"
      :current-name="tab.title"
      :current-description="tab.diagramDescription ?? ''"
      @close="closeEditDiagramDialog"
      @submit="handleEditDiagram"
    />
  </div>
</template>

<script setup lang="ts">
import * as d3 from "d3";
import { saveAs } from "file-saver";
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { useSessionStore, type DiagramTabState } from "../stores/session";
import type { DiagramTablePosition } from "../types/api";
import DiagramEditorDialog from "./DiagramEditorDialog.vue";
import DiagramSaveDialog from "./DiagramSaveDialog.vue";

interface SchemaFieldMetadata {
  data_type?: string;
  [key: string]: unknown;
}

interface SchemaTable {
  fields?: Record<string, SchemaFieldMetadata>;
  relationships?: Array<Record<string, any>>;
}

type SchemaMap = Record<string, SchemaTable>;

interface DiagramField {
  name: string;
  type: string;
  isForeignKey: boolean;
  tooltip?: string;
}

interface DiagramTable {
  name: string;
  fields: DiagramField[];
}

interface DiagramRelationship {
  source: string;
  target: string;
  label?: string;
}

interface DiagramData {
  tables: DiagramTable[];
  relationships: DiagramRelationship[];
}

interface LinkDatum {
  key: string;
  sx: number;
  sy: number;
  tx: number;
  ty: number;
  label?: string;
}

type DiagramDragEvent = d3.D3DragEvent<SVGGElement, DiagramTable, DiagramTable>;
type DiagramZoomEvent = d3.D3ZoomEvent<SVGSVGElement, unknown>;

interface Point {
  x: number;
  y: number;
}

const NODE_WIDTH = 240;
const HEADER_HEIGHT = 36;
const ROW_HEIGHT = 24;
const FONT_FAMILY = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif";

const COLORS = {
  nodeFill: "#f8fafc",
  nodeBorder: "rgba(37, 99, 235, 0.35)",
  headerFill: "rgba(37, 99, 235, 0.12)",
  divider: "#bfdbfe",
  title: "#1e3a8a",
  field: "#1f2937",
  fieldType: "#475569",
  link: "#94a3b8",
  labelBg: "#ffffff",
};

const LINK_ARROW_MARKER_BOX = {
  viewBox: "0 -5 10 10",
  refX: 10,
  refY: 0,
  width: 6,
  height: 6,
};
const LINK_START_PADDING = 12;
const LINK_END_PADDING = 8;

const props = defineProps<{
  tab: DiagramTabState;
}>();

const sessionStore = useSessionStore();
const { schema, diagramSavePromptTabId, diagramCloseRequestTabId } = storeToRefs(sessionStore);
const arrowMarkerId = `diagram-link-arrow-${props.tab.id}`;

const tables = computed(() => props.tab.tables ?? []);
const primaryTable = computed(() => props.tab.primaryTable ?? tables.value[0] ?? "");
const relatedTables = computed(() =>
  tables.value.filter((table) => table && table !== primaryTable.value),
);

const diagramElement = ref<HTMLDivElement | null>(null);
const renderError = ref("");
const exporting = ref(false);
const showSaveDialog = ref(false);
const saveDialogError = ref("");
const saveDialogLoading = ref(false);
const showEditDialog = ref(false);

const nodePositions = new Map<string, { x: number; y: number }>();
const nodeDimensions = new Map<string, { width: number; height: number }>();
const dragOffsets = new Map<string, { dx: number; dy: number }>();
let currentData: DiagramData | null = null;

let svgSelection: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null;
let rootGroup: d3.Selection<SVGGElement, unknown, null, undefined> | null = null;
let linkGroup: d3.Selection<SVGGElement, unknown, null, undefined> | null = null;
let labelGroup: d3.Selection<SVGGElement, unknown, null, undefined> | null = null;
let nodeGroup: d3.Selection<SVGGElement, unknown, null, undefined> | null = null;
let resizeObserver: ResizeObserver | null = null;
let exportInProgress = false;

function handleRemoveTable(name: string): void {
  sessionStore.removeTableFromDiagram(props.tab.id, name);
  sessionStore.markDiagramDirty(props.tab.id, true);
}

function handleSelectTable(name: string): void {
  sessionStore.selectDiagramTable(props.tab.id, name);
}

function openSaveDiagramDialog(): void {
  if (!diagramData.value) {
    return;
  }
  saveDialogError.value = "";
  showSaveDialog.value = true;
}

function closeSaveDiagramDialog(): void {
  if (saveDialogLoading.value) {
    return;
  }
  saveDialogError.value = "";
  showSaveDialog.value = false;
  sessionStore.clearDiagramSavePrompt(props.tab.id);
}

function openEditDiagramDialog(): void {
  showEditDialog.value = true;
}

function closeEditDiagramDialog(): void {
  showEditDialog.value = false;
}

function handleEditDiagram(payload: { name: string; description: string }): void {
  sessionStore.updateDiagramMetadata(props.tab.id, payload.name, payload.description);
  showEditDialog.value = false;
}

function collectDiagramLayout(): DiagramTablePosition[] {
  const layout: DiagramTablePosition[] = [];
  for (const name of tables.value) {
    if (!name) {
      continue;
    }
    const position = nodePositions.get(name);
    const dims = nodeDimensions.get(name);
    if (!position) {
      continue;
    }
    layout.push({
      name,
      x: position.x,
      y: position.y,
      width: dims?.width,
    });
  }
  return layout;
}

async function handleSaveDiagram(payload: { name: string; description: string }): Promise<void> {
  if (saveDialogLoading.value) {
    return;
  }
  const layout = collectDiagramLayout();
  if (!layout.length) {
    saveDialogError.value = "Add at least one table before saving a diagram.";
    return;
  }
  let targetDiagramId = props.tab.diagramId;
  if (props.tab.diagramId) {
    const overwrite = window.confirm(
      "This diagram already exists. Select OK to overwrite it, or Cancel to save as a new diagram.",
    );
    if (!overwrite) {
      targetDiagramId = undefined;
    }
  }
  saveDialogLoading.value = true;
  saveDialogError.value = "";
  try {
    const record = await sessionStore.saveDiagramLayout({
      name: payload.name,
      description: payload.description,
      tables: layout,
      diagramId: targetDiagramId,
    });
    showSaveDialog.value = false;
    props.tab.diagramId = record.id;
    props.tab.diagramDescription = record.description ?? "";
    const nextLayout: Record<string, { x: number; y: number; width?: number }> = {};
    for (const table of record.tables) {
      nextLayout[table.name] = { x: table.x, y: table.y, width: table.width };
    }
    props.tab.layout = nextLayout;
    sessionStore.markDiagramDirty(props.tab.id, false);
    props.tab.hasUnsavedChanges = false;
    const shouldCloseAfterSave = diagramCloseRequestTabId.value === props.tab.id;
    sessionStore.clearDiagramSavePrompt(props.tab.id);
    if (shouldCloseAfterSave) {
      sessionStore.closeWorkspaceTab(props.tab.id);
    }
  } catch (error) {
    saveDialogError.value =
      error instanceof Error ? error.message : "Failed to save diagram layout.";
  } finally {
    saveDialogLoading.value = false;
  }
}

const diagramData = computed<DiagramData | null>(() => {
  if (!tables.value.length) {
    return null;
  }

  const rawSchema = (schema.value ?? null) as { tables?: SchemaMap } | null;
  const schemaTables = rawSchema?.tables ?? {};
  if (!schemaTables || Object.keys(schemaTables).length === 0) {
    return null;
  }

  const nameLookup = new Map<string, string>();
  for (const tableName of Object.keys(schemaTables)) {
    nameLookup.set(tableName.toLowerCase(), tableName);
  }

  const included = new Set<string>();
  const tableRecords: Array<[string, SchemaTable]> = [];
  for (const rawName of tables.value) {
    const resolvedName = nameLookup.get(rawName.toLowerCase()) ?? rawName;
    if (included.has(resolvedName)) {
      continue;
    }
    const tableData = schemaTables[resolvedName];
    if (!tableData) {
      continue;
    }
    included.add(resolvedName);
    tableRecords.push([resolvedName, tableData]);
  }

  if (!tableRecords.length) {
    return null;
  }

  const fieldTargets = new Map<string, Array<{ table: string; field?: string }>>();
  for (const [tableName, tableData] of tableRecords) {
    const relations = Array.isArray(tableData.relationships) ? tableData.relationships : [];
    for (const rel of relations) {
      const sourceField = typeof rel?.field === "string" ? rel.field : "";
      const relatedRaw = typeof rel?.related_table === "string" ? rel.related_table : "";
      if (!sourceField || !relatedRaw) {
        continue;
      }
      const relatedName = nameLookup.get(relatedRaw.toLowerCase()) ?? relatedRaw;
      if (!included.has(relatedName)) {
        continue;
      }
      const relatedField =
        typeof rel?.related_field === "string" ? rel.related_field : undefined;
      const key = `${tableName.toLowerCase()}::${sourceField.toLowerCase()}`;
      const entries = fieldTargets.get(key) ?? [];
      entries.push({ table: relatedName, field: relatedField });
      fieldTargets.set(key, entries);
    }
  }

  const tablesPayload: DiagramTable[] = tableRecords.map(([tableName, tableData]) => {
    const fieldsMeta = tableData.fields ?? {};
    const entries = Object.entries(fieldsMeta);
    const fields: DiagramField[] = entries.map(([fieldName, details]) => {
      const dataType =
        typeof details?.data_type === "string" && details.data_type
          ? details.data_type
          : "string";
      const key = `${tableName.toLowerCase()}::${fieldName.toLowerCase()}`;
      const relatedTargets = fieldTargets.get(key) ?? [];
      const isForeignKey = relatedTargets.length > 0;
      const destinations = relatedTargets
        .map((entry) => (entry.field ? `${entry.table}.${entry.field}` : entry.table))
        .join(", ");
      return {
        name: fieldName,
        type: dataType,
        isForeignKey,
        tooltip: isForeignKey ? `References ${destinations}` : undefined,
      };
    });
    return { name: tableName, fields };
  });

  const relationships: DiagramRelationship[] = [];
  const seen = new Set<string>();
  for (const [tableName, tableData] of tableRecords) {
    const relations = Array.isArray(tableData.relationships) ? tableData.relationships : [];
    for (const rel of relations) {
      const relatedRaw = typeof rel?.related_table === "string" ? rel.related_table : "";
      if (!relatedRaw) {
        continue;
      }
      const targetName = nameLookup.get(relatedRaw.toLowerCase()) ?? relatedRaw;
      if (!included.has(targetName)) {
        continue;
      }
      const key = `${tableName.toLowerCase()}|${targetName.toLowerCase()}|${String(
        rel.field ?? "",
      )}|${String(rel.related_field ?? "")}`;
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      const labelParts: string[] = [];
      if (typeof rel.field === "string" && rel.field) {
        labelParts.push(rel.field);
      }
      if (typeof rel.related_field === "string" && rel.related_field) {
        labelParts.push(`→ ${rel.related_field}`);
      }
      if (!labelParts.length && typeof rel.type === "string" && rel.type) {
        labelParts.push(rel.type);
      }
      relationships.push({
        source: tableName,
        target: targetName,
        label: labelParts.length ? labelParts.join(" ") : undefined,
      });
    }
  }

  return {
    tables: tablesPayload,
    relationships,
  };
});

function computeDimensions(table: DiagramTable): { width: number; height: number } {
  const rows = Math.max(table.fields.length, 1);
  const savedLayout = props.tab.layout?.[table.name];
  const width = savedLayout?.width ?? NODE_WIDTH;
  return {
    width,
    height: HEADER_HEIGHT + rows * ROW_HEIGHT,
  };
}

function getNodeCenter(position: { x: number; y: number }, dims: { width: number; height: number }): Point {
  return {
    x: position.x + dims.width / 2,
    y: position.y + dims.height / 2,
  };
}

function projectPointTowards(reference: Point, nodeCenter: Point, dims: { width: number; height: number }, padding = 0): Point {
  const dx = reference.x - nodeCenter.x;
  const dy = reference.y - nodeCenter.y;
  if (Math.abs(dx) < 0.0001 && Math.abs(dy) < 0.0001) {
    return { ...nodeCenter };
  }
  const halfWidth = dims.width / 2;
  const halfHeight = dims.height / 2;
  let scale = Number.POSITIVE_INFINITY;
  if (Math.abs(dx) > 0.0001) {
    scale = Math.min(scale, halfWidth / Math.abs(dx));
  }
  if (Math.abs(dy) > 0.0001) {
    scale = Math.min(scale, halfHeight / Math.abs(dy));
  }
  if (!Number.isFinite(scale)) {
    scale = 0;
  }
  const boundary = {
    x: nodeCenter.x + dx * scale,
    y: nodeCenter.y + dy * scale,
  };
  if (!padding) {
    return boundary;
  }
  const length = Math.hypot(dx, dy) || 1;
  return {
    x: boundary.x + (dx / length) * padding,
    y: boundary.y + (dy / length) * padding,
  };
}

function handleResize(): void {
  if (!diagramElement.value || !svgSelection) {
    return;
  }
  const width = diagramElement.value.clientWidth || 900;
  const height = diagramElement.value.clientHeight || 600;
  svgSelection.attr("viewBox", `0 0 ${width} ${height}`);
  if (currentData) {
    renderDiagram(currentData);
  }
}

function setupCanvas(): void {
  if (!diagramElement.value) {
    return;
  }

  d3.select(diagramElement.value).selectAll("*").remove();

  const width = diagramElement.value.clientWidth || 900;
  const height = diagramElement.value.clientHeight || 600;

  svgSelection = d3
    .select(diagramElement.value)
    .append("svg")
    .attr("class", "diagram-canvas")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("preserveAspectRatio", "xMidYMid meet");

  const defs = svgSelection.append("defs");
  defs
    .append("marker")
    .attr("id", arrowMarkerId)
    .attr("viewBox", LINK_ARROW_MARKER_BOX.viewBox)
    .attr("refX", LINK_ARROW_MARKER_BOX.refX)
    .attr("refY", LINK_ARROW_MARKER_BOX.refY)
    .attr("markerWidth", LINK_ARROW_MARKER_BOX.width)
    .attr("markerHeight", LINK_ARROW_MARKER_BOX.height)
    .attr("orient", "auto")
    .attr("fill", COLORS.link)
    .append("path")
    .attr("d", "M0,-5L10,0L0,5Z");

  rootGroup = svgSelection.append("g").attr("class", "diagram-root");
  linkGroup = rootGroup.append("g").attr("class", "diagram-links");
  labelGroup = rootGroup.append("g").attr("class", "diagram-link-labels");
  nodeGroup = rootGroup.append("g").attr("class", "diagram-nodes");

  const zoomBehavior = d3
    .zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.4, 3])
    .on("zoom", (event: DiagramZoomEvent) => {
      rootGroup?.attr("transform", event.transform.toString());
    });

  svgSelection.call(zoomBehavior as any);
}

function clearDiagram(): void {
  linkGroup?.selectAll("*").remove();
  labelGroup?.selectAll("*").remove();
  nodeGroup?.selectAll("*").remove();
  dragOffsets.clear();
}

function updateLinks(): void {
  if (!currentData || !linkGroup || !labelGroup) {
    return;
  }

  const linkData: LinkDatum[] = currentData.relationships
    .map((rel) => {
      const sourcePos = nodePositions.get(rel.source);
      const targetPos = nodePositions.get(rel.target);
      const sourceDims = nodeDimensions.get(rel.source);
      const targetDims = nodeDimensions.get(rel.target);
      if (!sourcePos || !targetPos || !sourceDims || !targetDims) {
        return null;
      }
      const sourceCenter = getNodeCenter(sourcePos, sourceDims);
      const targetCenter = getNodeCenter(targetPos, targetDims);
      const startPoint = projectPointTowards(targetCenter, sourceCenter, sourceDims, LINK_START_PADDING);
      const endPoint = projectPointTowards(sourceCenter, targetCenter, targetDims, LINK_END_PADDING);
      return {
        key: `${rel.source}->${rel.target}:${rel.label ?? ""}`,
        sx: startPoint.x,
        sy: startPoint.y,
        tx: endPoint.x,
        ty: endPoint.y,
        label: rel.label,
      } as LinkDatum;
    })
    .filter((item): item is LinkDatum => Boolean(item));

  const path = (d: LinkDatum) => {
    const curvature = 0.3;
    const dx = d.tx - d.sx;
    const dy = d.ty - d.sy;
    const mx = d.sx + dx * 0.5;
    const control1Y = d.sy + dy * curvature;
    const control2Y = d.ty - dy * curvature;
    return `M${d.sx},${d.sy} C${mx},${control1Y} ${mx},${control2Y} ${d.tx},${d.ty}`;
  };

  const linkSelection = linkGroup
    .selectAll<SVGPathElement, LinkDatum>("path.relationship")
    .data(linkData, (d: LinkDatum) => d.key);

  linkSelection.exit().remove();

  linkSelection
    .enter()
    .append("path")
    .attr("class", "relationship")
    .attr("fill", "none")
    .merge(linkSelection)
    .attr("stroke", COLORS.link)
    .attr("stroke-width", 1.4)
    .attr("marker-end", `url(#${arrowMarkerId})`)
    .attr("d", path);

  const labeledLinks = linkData.filter((item): item is LinkDatum & { label: string } => Boolean(item.label));

  const labelSelection = labelGroup
    .selectAll<SVGTextElement, LinkDatum>("text.relationship-label")
    .data(labeledLinks, (d: LinkDatum) => d.key);

  labelSelection.exit().remove();

  labelSelection
    .enter()
    .append("text")
    .attr("class", "relationship-label")
    .merge(labelSelection)
    .attr("font-family", FONT_FAMILY)
    .attr("fill", COLORS.field)
    .attr("font-size", "0.75rem")
    .attr("font-weight", "500")
  .attr("text-anchor", "middle")
  .attr("x", (d: LinkDatum) => (d.sx + d.tx) / 2)
  .attr("y", (d: LinkDatum) => (d.sy + d.ty) / 2 - 8)
  .text((d: LinkDatum) => d.label ?? "");
}

function updateNodes(): void {
  if (!currentData || !nodeGroup) {
    return;
  }

  const nodeSelection = nodeGroup
    .selectAll<SVGGElement, DiagramTable>("g.diagram-node")
    .data(currentData.tables, (d) => d.name) as d3.Selection<
    SVGGElement,
    DiagramTable,
    SVGGElement,
    DiagramTable
  >;

  nodeSelection
    .exit()
    .each((d) => {
      const datum = d as DiagramTable;
      nodePositions.delete(datum.name);
      nodeDimensions.delete(datum.name);
      dragOffsets.delete(datum.name);
    })
    .remove();

  const nodeEnter = nodeSelection
    .enter()
    .append("g")
    .attr("class", "diagram-node")
    .style("cursor", "grab")
    .call(
      d3
        .drag<SVGGElement, DiagramTable>()
        .on("start", function (this: SVGGElement, event: DiagramDragEvent, datum: DiagramTable) {
          event.sourceEvent?.stopPropagation();
          d3.select<SVGGElement, DiagramTable>(this).style("cursor", "grabbing");
          const dims = nodeDimensions.get(datum.name);
          const position = nodePositions.get(datum.name);
          if (position) {
            dragOffsets.set(datum.name, {
              dx: event.x - position.x,
              dy: event.y - position.y,
            });
          } else if (dims) {
            dragOffsets.set(datum.name, { dx: dims.width / 2, dy: dims.height / 2 });
          } else {
            dragOffsets.delete(datum.name);
          }
        })
        .on("drag", function (this: SVGGElement, event: DiagramDragEvent, datum: DiagramTable) {
          const dims = nodeDimensions.get(datum.name);
          if (!dims) {
            return;
          }
          const offset = dragOffsets.get(datum.name);
          const dx = offset?.dx ?? dims.width / 2;
          const dy = offset?.dy ?? dims.height / 2;
          const x = event.x - dx;
          const y = event.y - dy;
          nodePositions.set(datum.name, { x, y });
          d3.select<SVGGElement, DiagramTable>(this).attr("transform", `translate(${x}, ${y})`);
          updateLinks();
        })
        .on("end", function (this: SVGGElement, _event: DiagramDragEvent, datum: DiagramTable) {
          dragOffsets.delete(datum.name);
          d3.select<SVGGElement, DiagramTable>(this).style("cursor", "grab");
          sessionStore.markDiagramDirty(props.tab.id, true);
        }),
    );

  nodeEnter
    .append("rect")
    .attr("class", "node-outline")
    .attr("rx", 10)
    .attr("ry", 10)
    .attr("fill", COLORS.nodeFill)
    .attr("stroke", COLORS.nodeBorder)
    .attr("stroke-width", 1.2);
  nodeEnter
    .append("rect")
    .attr("class", "node-header")
    .attr("fill", COLORS.headerFill);
  nodeEnter
    .append("line")
    .attr("class", "node-divider")
    .attr("stroke", COLORS.divider)
    .attr("stroke-width", 1);
  const actionsGroup = nodeEnter.append("g").attr("class", "node-actions");
  const selectGroup = actionsGroup.append("g").attr("class", "node-action action-select");
  selectGroup.append("rect").attr("width", 22).attr("height", 22).attr("rx", 6).attr("ry", 6);
  selectGroup.append("text").attr("text-anchor", "middle").attr("dominant-baseline", "middle").attr("x", 11).attr("y", 11).text("↗");
  selectGroup.append("title").text("Highlight and scroll to this table");

  const removeGroup = actionsGroup.append("g").attr("class", "node-action action-remove");
  removeGroup.append("rect").attr("width", 22).attr("height", 22).attr("rx", 6).attr("ry", 6);
  removeGroup.append("text").attr("text-anchor", "middle").attr("dominant-baseline", "middle").attr("x", 11).attr("y", 11).text("✕");
  removeGroup.append("title").text("Remove this table from the diagram");

  nodeEnter
    .append("text")
    .attr("class", "node-title")
    .attr("font-family", FONT_FAMILY)
    .attr("fill", COLORS.title)
    .attr("font-size", "0.95rem")
    .attr("font-weight", "600")
    .attr("text-anchor", "middle");
  nodeEnter.append("g").attr("class", "node-fields");

  const resizeHandle = nodeEnter
    .append("g")
    .attr("class", "resize-handle")
    .style("cursor", "ew-resize")
    .call(
      d3
        .drag<SVGGElement, DiagramTable>()
        .on("start", function (event) {
          event.sourceEvent.stopPropagation();
        })
        .on("drag", function (this: SVGGElement, event: DiagramDragEvent, d: DiagramTable) {
          const currentDims = nodeDimensions.get(d.name);
          if (!currentDims) return;

          const newWidth = Math.max(NODE_WIDTH, currentDims.width + event.dx);
          const newDims = { ...currentDims, width: newWidth };
          nodeDimensions.set(d.name, newDims);

          const pos = nodePositions.get(d.name);
          if (pos) {
            sessionStore.updateDiagramLayout(props.tab.id, d.name, {
              x: pos.x,
              y: pos.y,
              width: newWidth,
            });
          }

          const node = d3.select(this.parentNode as SVGGElement);

          node.select<SVGRectElement>("rect.node-outline").attr("width", newDims.width);
          node.select<SVGRectElement>("rect.node-header").attr("width", newDims.width);
          node.select<SVGLineElement>("line.node-divider").attr("x2", newDims.width);
          node.select<SVGTextElement>("text.node-title").attr("x", newDims.width / 2);
          node.selectAll("text.field-type").attr("x", newDims.width - 12);
          node
            .select<SVGGElement>("g.node-actions")
            .attr("transform", `translate(${Math.max(newDims.width - 48, 8)}, 7)`);
          node
            .select<SVGGElement>("g.resize-handle")
            .attr("transform", `translate(${newDims.width}, 0)`);
          
          node
            .select<SVGRectElement>("rect.resize-hit-area")
            .attr("height", newDims.height);

          node
            .select<SVGLineElement>("line.resize-visual")
            .attr("y1", newDims.height / 2 - 8)
            .attr("y2", newDims.height / 2 + 8);

          updateLinks();
        })
        .on("end", function () {
          sessionStore.markDiagramDirty(props.tab.id, true);
        }),
    );

  resizeHandle
    .append("rect")
    .attr("class", "resize-hit-area")
    .attr("width", 16)
    .attr("x", -8)
    .attr("fill", "#fff")
    .attr("fill-opacity", "0")
    .attr("stroke", "none");

  resizeHandle
    .append("line")
    .attr("class", "resize-visual")
    .attr("x1", 0)
    .attr("x2", 0)
    .attr("stroke", COLORS.nodeBorder)
    .attr("stroke-width", 2);

  const mergedNodes = nodeEnter.merge(nodeSelection);

  mergedNodes.each(function (this: SVGGElement, table: DiagramTable) {
    const dims = computeDimensions(table);
    nodeDimensions.set(table.name, dims);
    const existing = nodePositions.get(table.name);
    if (!existing) {
      nodePositions.set(table.name, { x: 0, y: 0 });
    }
    const position = nodePositions.get(table.name)!;

    const group = d3.select<SVGGElement, DiagramTable>(this);
    group.attr("transform", `translate(${position.x}, ${position.y})`);

    group
      .select<SVGRectElement>("rect.node-outline")
      .attr("width", dims.width)
      .attr("height", dims.height);

    group
      .select<SVGRectElement>("rect.node-header")
      .attr("width", dims.width)
      .attr("height", HEADER_HEIGHT);

    group
      .select<SVGLineElement>("line.node-divider")
      .attr("x1", 0)
      .attr("y1", HEADER_HEIGHT)
      .attr("x2", dims.width)
      .attr("y2", HEADER_HEIGHT);

    group
      .select<SVGTextElement>("text.node-title")
      .attr("x", dims.width / 2)
      .attr("y", HEADER_HEIGHT / 2 + 6)
      .text(table.name);

    const actions = group.select<SVGGElement>("g.node-actions");
    actions.attr("transform", `translate(${Math.max(dims.width - 48, 8)}, 7)`);

    const resize = group.select<SVGGElement>("g.resize-handle");
    resize.attr("transform", `translate(${dims.width}, 0)`);

    resize
      .select<SVGRectElement>("rect.resize-hit-area")
      .attr("height", dims.height)
      .attr("y", 0);

    resize
      .select<SVGLineElement>("line.resize-visual")
      .attr("y1", dims.height / 2 - 8)
      .attr("y2", dims.height / 2 + 8);

    const selectAction = actions.select<SVGGElement>("g.action-select");
    selectAction
      .attr("transform", "translate(0, 0)")
      .on("click", (event: MouseEvent) => {
        event.stopPropagation();
        handleSelectTable(table.name);
      });

    const removeAction = actions.select<SVGGElement>("g.action-remove");
    removeAction
      .attr("transform", "translate(26, 0)")
      .on("click", (event: MouseEvent) => {
        event.stopPropagation();
        const confirmed = window.confirm(`Remove ${table.name} from this diagram?`);
        if (!confirmed) {
          return;
        }
        handleRemoveTable(table.name);
      });

    const fieldsContainer = group.select<SVGGElement>("g.node-fields");
    const fieldSelection = fieldsContainer
      .selectAll<SVGGElement, DiagramField>("g.field-row")
  .data(table.fields, (field: DiagramField) => field.name);

    fieldSelection.exit().remove();

    const fieldEnter = fieldSelection.enter().append("g").attr("class", "field-row");
    fieldEnter.append("text").attr("class", "field-name");
    fieldEnter.append("text").attr("class", "field-type");
    fieldEnter.append("title");

    const fieldMerge = fieldEnter.merge(fieldSelection);

    fieldMerge.attr(
      "transform",
      (_field: DiagramField, index: number) => `translate(0, ${HEADER_HEIGHT + index * ROW_HEIGHT})`,
    );

    fieldMerge
      .select<SVGTextElement>("text.field-name")
      .attr("x", 12)
      .attr("y", ROW_HEIGHT / 2 + 5)
      .attr("font-family", FONT_FAMILY)
      .attr("fill", COLORS.field)
      .attr("font-size", "0.82rem")
      .text((field: DiagramField) => (field.isForeignKey ? "⛓ " : "") + field.name);

    fieldMerge
      .select<SVGTextElement>("text.field-type")
      .attr("x", dims.width - 12)
      .attr("y", ROW_HEIGHT / 2 + 5)
      .attr("text-anchor", "end")
      .attr("font-family", FONT_FAMILY)
      .attr("fill", COLORS.fieldType)
      .attr("font-size", "0.78rem")
      .text((field: DiagramField) => field.type);

    fieldMerge
      .select("title")
      .text((field: DiagramField) => (field.tooltip ? field.tooltip : ""));
  });
}

function renderDiagram(data: DiagramData): void {
  currentData = data;

  if (!diagramElement.value || !svgSelection || !rootGroup) {
    setupCanvas();
  }

  if (!diagramElement.value) {
    return;
  }

  applySavedLayout(data);

  const width = diagramElement.value.clientWidth || 900;
  const height = diagramElement.value.clientHeight || 600;
  svgSelection?.attr("viewBox", `0 0 ${width} ${height}`);

  const radius = Math.min(width, height) * 0.35 + data.tables.length * 12;

  const activeNames = new Set(data.tables.map((table) => table.name));
  for (const key of Array.from(nodePositions.keys())) {
    if (!activeNames.has(key)) {
      nodePositions.delete(key);
      nodeDimensions.delete(key);
      dragOffsets.delete(key);
    }
  }

  data.tables.forEach((table, index) => {
    const dims = computeDimensions(table);
    nodeDimensions.set(table.name, dims);
    if (!nodePositions.has(table.name)) {
      const angle = (2 * Math.PI * index) / data.tables.length;
      const x = width / 2 + radius * Math.cos(angle) - dims.width / 2;
      const y = height / 2 + radius * Math.sin(angle) - dims.height / 2;
      nodePositions.set(table.name, { x, y });
    }
  });

  updateNodes();
  updateLinks();
}

function applySavedLayout(data: DiagramData): void {
  const layout = props.tab.layout;
  if (!layout) {
    return;
  }
  for (const table of data.tables) {
    const saved = layout[table.name];
    if (saved && typeof saved.x === "number" && typeof saved.y === "number" && !nodePositions.has(table.name)) {
      nodePositions.set(table.name, { x: saved.x, y: saved.y });
    }
  }
}

watch(
  diagramData,
  (data) => {
    if (!diagramElement.value) {
      return;
    }
    if (!svgSelection) {
      setupCanvas();
    }
    if (!data) {
      clearDiagram();
      renderError.value = tables.value.length
        ? "No schema metadata available for the selected tables yet."
        : "";
      currentData = null;
      return;
    }
    renderError.value = "";
    renderDiagram(data);
  },
  { immediate: true },
);

// Removed showSummary watcher


watch(
  () => ({ requestedTab: diagramSavePromptTabId.value, dataReady: diagramData.value }),
  ({ requestedTab, dataReady }) => {
    if (requestedTab === props.tab.id && dataReady && !showSaveDialog.value) {
      openSaveDiagramDialog();
    }
  },
  { immediate: true },
);

onMounted(() => {
  setupCanvas();
  window.addEventListener("resize", handleResize);
  if (diagramElement.value) {
    resizeObserver = new ResizeObserver(() => handleResize());
    resizeObserver.observe(diagramElement.value);
  }
  if (diagramData.value) {
    renderDiagram(diagramData.value);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  resizeObserver?.disconnect();
  resizeObserver = null;
  svgSelection?.on(".zoom", null);
  svgSelection = null;
  rootGroup = null;
  nodeGroup = null;
  linkGroup = null;
  labelGroup = null;
  nodePositions.clear();
  nodeDimensions.clear();
  dragOffsets.clear();
  currentData = null;
});

async function exportDiagram(): Promise<void> {
  if (exporting.value || !svgSelection) {
    return;
  }
  exporting.value = true;
  try {
    if ("fonts" in document && typeof (document.fonts as any).ready === "object") {
      try {
        await (document.fonts as FontFaceSet).ready;
      } catch {
        /* ignore font loading errors */
      }
    }
    const serializer = new XMLSerializer();
    const svgNode = svgSelection.node();
    if (!svgNode) {
      throw new Error("Unable to locate diagram SVG.");
    }
    
    // Calculate bounding box of all diagram elements
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    
    nodePositions.forEach((pos, name) => {
      const dims = nodeDimensions.get(name);
      if (dims) {
        minX = Math.min(minX, pos.x);
        minY = Math.min(minY, pos.y);
        maxX = Math.max(maxX, pos.x + dims.width);
        maxY = Math.max(maxY, pos.y + dims.height);
      }
    });
    
    // Fallback if no nodes found
    if (!isFinite(minX) || !isFinite(minY)) {
      minX = 0;
      minY = 0;
      maxX = 1200;
      maxY = 800;
    }
    
    // Add padding
    const padding = 40;
    minX = minX - padding;
    minY = minY - padding;
    maxX = maxX + padding;
    maxY = maxY + padding;
    
    const width = maxX - minX;
    const height = maxY - minY;
    
    const svgClone = svgNode.cloneNode(true) as SVGSVGElement;
    svgClone.removeAttribute("style");
    
    // Remove action buttons (black boxes) from the export
    const actionGroups = svgClone.querySelectorAll('.node-actions');
    actionGroups.forEach(group => group.remove());
    
    svgClone.setAttribute("width", `${width}`);
    svgClone.setAttribute("height", `${height}`);
    svgClone.setAttribute("viewBox", `${minX} ${minY} ${width} ${height}`);
    svgClone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    const svgString = serializer.serializeToString(svgClone);
    const blob = new Blob([`<?xml version="1.0" encoding="UTF-8"?>\n${svgString}`], {
      type: "image/svg+xml;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = reject;
      image.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      throw new Error("Failed to obtain drawing context.");
    }
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(image, 0, 0, width, height);
    URL.revokeObjectURL(url);
    const blobPromise = new Promise<Blob | null>((resolve) =>
      canvas.toBlob((result) => resolve(result), "image/jpeg", 0.92),
    );
    const jpegBlob = await blobPromise;
    if (!jpegBlob) {
      throw new Error("Could not generate JPEG image.");
    }
    const filename =
      tables.value.length === 1
        ? `${tables.value[0]}-diagram.jpg`
        : `diagram-${Date.now()}.jpg`;
    saveAs(jpegBlob, filename);
  } catch (error) {
    console.error("Failed to export ER diagram:", error);
    renderError.value =
      error instanceof Error ? `Export failed: ${error.message}` : "Export failed.";
  } finally {
    exporting.value = false;
  }
}
</script>

<style scoped>
.er-diagram {
  display: flex;
  flex-direction: column;
  flex: 1;
  gap: 0.5rem;
}

.diagram-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.edit-button {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.85rem;
  border-radius: 9999px;
  border: 1px solid rgba(178, 106, 69, 0.3);
  background: rgba(253, 248, 241, 0.9);
  color: #b26a45;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}

.edit-button svg {
  width: 16px;
  height: 16px;
}

.edit-button:hover {
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 4px 10px rgba(178, 106, 69, 0.18);
}

.save-button {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.85rem;
  border-radius: 9999px;
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #1e3a8a;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}

.save-button svg {
  width: 16px;
  height: 16px;
}

.save-button:not(:disabled):hover {
  background: #e0e7ff;
  box-shadow: 0 4px 10px rgba(79, 70, 229, 0.18);
}

.save-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.export-button {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.95rem;
  border-radius: 9999px;
  border: none;
  background: linear-gradient(135deg, #1d4ed8, #3b82f6);
  color: #ffffff;
  font-size: 0.82rem;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.2s ease;
}

.export-button svg {
  width: 16px;
  height: 16px;
}

.export-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.25);
  filter: brightness(1.05);
}

.export-button:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.2);
}

.export-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
  box-shadow: none;
}

.summary-toggle {
  border: 1px solid #bfdbfe;
  background-color: #ffffff;
  color: #1d4ed8;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.35rem 0.75rem;
  border-radius: 9999px;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.summary-toggle:hover {
  background-color: #e0ecff;
  color: #1e40af;
}

.diagram-body {
  flex: 1;
  border: 1px dashed #cbd5f5;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  text-align: center;
  background-color: #f8fbff;
  width: 100%;
  box-sizing: border-box;
  max-width: 100%;
  overflow: hidden;
}

.diagram-body.populated {
  display: flex;
  align-items: stretch;
  column-gap: 1.5rem;
  text-align: left;
  width: 100%;
  box-sizing: border-box;
}

.diagram-body.populated.no-summary {
  justify-content: stretch;
  column-gap: 0;
}

.diagram-body.populated .diagram-view {
  flex: 1 1 auto;
  min-width: 0;
}

.diagram-view {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 100%;
  box-sizing: border-box;
}

.diagram-view.full-width {
  width: 100%;
  max-width: 100%;
}

.diagram-svg {
  width: 100%;
  min-height: 420px;
  height: 100%;
  max-width: 100%;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background-color: #ffffff;
  overflow: hidden;
  position: relative;
  box-sizing: border-box;
}

.diagram-svg :deep(.diagram-canvas) {
  width: 100%;
  height: 100%;
  cursor: grab;
  touch-action: none;
}

.diagram-svg :deep(.diagram-canvas:active) {
  cursor: grabbing;
}

:deep(.node-actions) {
  pointer-events: auto;
}

:deep(.node-action) {
  cursor: pointer;
}

:deep(.node-action rect) {
  fill: rgba(37, 99, 235, 0.12);
  stroke: rgba(37, 99, 235, 0.32);
  stroke-width: 1px;
}

:deep(.node-action text) {
  fill: #1e3a8a;
  font-size: 0.78rem;
  font-family: "Segoe UI", "Inter", sans-serif;
  pointer-events: none;
}

:deep(.node-action:hover rect) {
  fill: rgba(37, 99, 235, 0.22);
}

.diagram-placeholder {
  margin: 0;
  padding: 1.2rem;
  border-radius: 8px;
  background-color: #eef2ff;
  color: #4338ca;
  font-size: 0.9rem;
}

.diagram-loading {
  margin: 0;
  font-size: 0.85rem;
  color: #334155;
}

.diagram-error {
  margin: 0;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  background-color: rgba(248, 113, 113, 0.15);
  color: #b91c1c;
  font-size: 0.85rem;
}

.diagram-summary {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  min-width: 200px;
  max-width: 260px;
}

.diagram-summary h3 {
  margin: 0;
  color: #1d4ed8;
}

.diagram-text {
  margin: 0;
  color: #334155;
  font-size: 0.9rem;
}

.diagram-summary ul {
  margin: 0;
  padding-left: 1.2rem;
  color: #475569;
  font-size: 0.9rem;
}

.diagram-note {
  margin: 0;
  font-size: 0.8rem;
  color: #64748b;
}

.empty-state {
  margin: 0;
  color: #1e3a8a;
  font-weight: 500;
}
</style>
