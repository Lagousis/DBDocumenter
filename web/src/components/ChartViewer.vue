<template>
  <div class="chart-viewer">
    <div class="toolbar">
      <h2 class="section-title">{{ editableTitle }}</h2>
      <div class="toolbar-actions">
        <select v-model="selectedChartType" class="chart-type-selector">
          <option value="bar">Bar Chart</option>
          <option value="horizontal-bar">Horizontal Bar Chart</option>
          <option value="line">Line Chart</option>
          <option value="pie">Pie Chart</option>
          <option value="area">Area Chart</option>
          <option value="scatter">Scatter Plot</option>
        </select>
        <button type="button" @click="showControls = !showControls" class="secondary-button">
          {{ showControls ? 'Hide' : 'Show' }} Settings
        </button>
        <div class="save-dropdown">
          <button type="button" @click="saveAsImage" class="secondary-button save-main">
            Save as {{ exportFormat.toUpperCase() }}
          </button>
          <button type="button" @click="toggleExportMenu" class="secondary-button save-toggle">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4 6l4 4 4-4z" />
            </svg>
          </button>
          <div v-if="showExportMenu" class="export-menu">
            <button type="button" @click="selectFormat('svg')" class="menu-item">Save as SVG</button>
            <button type="button" @click="selectFormat('png')" class="menu-item">Save as PNG</button>
          </div>
        </div>
        <button v-if="tab.sql" type="button" @click="openSqlInTab" class="secondary-button">
          View SQL
        </button>
      </div>
    </div>

    <div v-if="showControls" class="chart-controls">
      <div class="control-group">
        <label>
          Chart Title:
          <input v-model="editableTitle" @input="onLabelChange" type="text" placeholder="Enter chart title" />
        </label>
      </div>
      <div class="control-group">
        <label>
          Value Labels:
          <select v-model="valueLabelMode" @change="onLabelChange" class="label-mode-selector">
            <option v-if="selectedChartType === 'bar' || selectedChartType === 'horizontal-bar'" value="none">None</option>
            <option value="value">Show Values</option>
            <option value="percent">Show Percentages</option>
            <option value="both">Show Both</option>
          </select>
        </label>
      </div>
      <div v-if="selectedChartType !== 'pie'" class="control-group">
        <label>
          X-Axis Label:
          <input v-model="editableXLabel" @input="onLabelChange" type="text" placeholder="X-axis label" />
        </label>
      </div>
      <div v-if="selectedChartType !== 'pie'" class="control-group">
        <label>
          Y-Axis Label:
          <input v-model="editableYLabel" @input="onLabelChange" type="text" placeholder="Y-axis label" />
        </label>
      </div>
      <div v-for="(dataset, idx) in editableDatasetLabels" :key="idx" class="control-group">
        <label>
          Series {{ idx + 1 }} Label:
          <input v-model="editableDatasetLabels[idx]" @input="onLabelChange" type="text" :placeholder="`Series ${idx + 1} name`" />
        </label>
      </div>
    </div>

    <div class="chart-container">
      <svg ref="chartSvg" class="chart-svg"></svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import * as d3 from "d3";
import { onMounted, ref, watch } from "vue";

import { useSessionStore, type ChartTabState } from "../stores/session";

const props = defineProps<{
  tab: ChartTabState;
}>();

const sessionStore = useSessionStore();

const chartSvg = ref<SVGSVGElement | null>(null);
const selectedChartType = ref(props.tab.chartType);
const editableTitle = ref(props.tab.title);
const editableXLabel = ref(props.tab.xLabel);
const editableYLabel = ref(props.tab.yLabel);
const editableDatasetLabels = ref<string[]>(props.tab.data.datasets.map(d => d.label));
const showControls = ref(false);
const exportFormat = ref<"svg" | "png">("svg");
const showExportMenu = ref(false);
const valueLabelMode = ref<"none" | "value" | "percent" | "both">("both");

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

// Watch for changes and re-render
watch([selectedChartType, editableTitle, editableXLabel, editableYLabel], () => {
  console.log("ChartViewer - Watch triggered, re-rendering chart");
  renderChart();
}, { deep: true });

function onLabelChange(): void {
  console.log("ChartViewer - Label changed, triggering re-render");
  renderChart();
}

function toggleExportMenu(): void {
  showExportMenu.value = !showExportMenu.value;
}

function selectFormat(format: "svg" | "png"): void {
  exportFormat.value = format;
  showExportMenu.value = false;
  saveAsImage();
}

function getUpdatedDatasets() {
  return props.tab.data.datasets.map((dataset, idx) => ({
    ...dataset,
    label: editableDatasetLabels.value[idx] || dataset.label
  }));
}

onMounted(() => {
  renderChart();
  // Re-render on window resize
  window.addEventListener("resize", renderChart);
});

function renderChart(): void {
  if (!chartSvg.value) return;

  console.log("ChartViewer - Rendering chart with data:", props.tab);
  console.log("ChartViewer - Data structure:", props.tab.data);
  console.log("ChartViewer - Labels:", props.tab.data?.labels);
  console.log("ChartViewer - Datasets:", props.tab.data?.datasets);

  const svg = d3.select(chartSvg.value);
  svg.selectAll("*").remove(); // Clear previous chart

  const containerWidth = chartSvg.value.parentElement?.clientWidth ?? 800;
  const containerHeight = 500;
  const margin = { top: 40, right: 200, bottom: 80, left: 150 };
  const width = containerWidth - margin.left - margin.right;
  const height = containerHeight - margin.top - margin.bottom;

  svg.attr("width", containerWidth).attr("height", containerHeight);

  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  // Render based on chart type
  switch (selectedChartType.value) {
    case "bar":
      renderBarChart(g, width, height);
      break;
    case "horizontal-bar":
      renderHorizontalBarChart(g, width, height);
      break;
    case "line":
      renderLineChart(g, width, height);
      break;
    case "pie":
      renderPieChart(g, width, height);
      break;
    case "area":
      renderAreaChart(g, width, height);
      break;
    case "scatter":
      renderScatterChart(g, width, height);
      break;
  }

  // Add title
  if (editableTitle.value) {
    svg
      .append("text")
      .attr("x", containerWidth / 2)
      .attr("y", 20)
      .attr("text-anchor", "middle")
      .style("font-size", "16px")
      .style("font-weight", "600")
      .text(editableTitle.value);
  }
}

function renderBarChart(g: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number): void {
  const data = props.tab.data;
  const labels = data.labels;
  const datasets = getUpdatedDatasets();

  if (datasets.length === 0) return;

  // X scale
  const x0 = d3
    .scaleBand()
    .domain(labels)
    .rangeRound([0, width])
    .paddingInner(0.1);

  const x1 = d3
    .scaleBand()
    .domain(datasets.map((d) => d.label))
    .rangeRound([0, x0.bandwidth()])
    .padding(0.05);

  // Y scale
  const maxValue = d3.max(datasets.flatMap((d) => d.data)) ?? 0;
  const y = d3
    .scaleLinear()
    .domain([0, maxValue * 1.1])
    .range([height, 0]);

  // X axis
  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x0))
    .selectAll("text")
    .attr("transform", "rotate(-45)")
    .style("text-anchor", "end");

  // Y axis
  g.append("g").call(d3.axisLeft(y));

  // Bars
  const labelGroups = g
    .selectAll(".label-group")
    .data(labels)
    .enter()
    .append("g")
    .attr("class", "label-group")
    .attr("transform", (d) => `translate(${x0(d)},0)`);

  const total = d3.sum(datasets.flatMap(d => d.data));
  
  datasets.forEach((dataset, i) => {
    const bars = labelGroups
      .append("rect")
      .attr("x", x1(dataset.label) ?? 0)
      .attr("y", (d, idx) => y(dataset.data[idx]))
      .attr("width", x1.bandwidth())
      .attr("height", (d, idx) => height - y(dataset.data[idx]))
      .attr("fill", dataset.color || colorPalette[i % colorPalette.length]);
    
    // Add value labels if enabled
    if (valueLabelMode.value !== "none") {
      labelGroups.each(function(d, idx) {
        const value = dataset.data[idx];
        const percent = ((value / total) * 100).toFixed(1);
        let labelText = "";
        
        if (valueLabelMode.value === "value") {
          labelText = `${value}`;
        } else if (valueLabelMode.value === "percent") {
          labelText = `${percent}%`;
        } else if (valueLabelMode.value === "both") {
          labelText = `${value} (${percent}%)`;
        }
        
        d3.select(this)
          .append("text")
          .attr("x", (x1(dataset.label) ?? 0) + x1.bandwidth() / 2)
          .attr("y", y(value) - 5)
          .attr("text-anchor", "middle")
          .style("font-size", "11px")
          .style("font-weight", "600")
          .style("fill", "#334155")
          .text(labelText);
      });
    }
  });

  // Add axis labels
  if (editableXLabel.value) {
    g.append("text")
      .attr("x", width / 2)
      .attr("y", height + 60)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableXLabel.value);
  }

  if (editableYLabel.value) {
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -height / 2)
      .attr("y", -60)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableYLabel.value);
  }

  // Legend
  addLegend(g, datasets, width);
}

function renderHorizontalBarChart(g: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number): void {
  const data = props.tab.data;
  const labels = data.labels;
  const datasets = getUpdatedDatasets();

  if (datasets.length === 0) return;

  // Y scale (for labels/categories)
  const y0 = d3
    .scaleBand()
    .domain(labels)
    .rangeRound([0, height])
    .paddingInner(0.1);

  const y1 = d3
    .scaleBand()
    .domain(datasets.map((d) => d.label))
    .rangeRound([0, y0.bandwidth()])
    .padding(0.05);

  // X scale (for values)
  const maxValue = d3.max(datasets.flatMap((d) => d.data)) ?? 0;
  const x = d3
    .scaleLinear()
    .domain([0, maxValue * 1.1])
    .range([0, width]);

  // Y axis (categories)
  g.append("g").call(d3.axisLeft(y0));

  // X axis (values)
  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x));

  // Bars
  const labelGroups = g
    .selectAll(".label-group")
    .data(labels)
    .enter()
    .append("g")
    .attr("class", "label-group")
    .attr("transform", (d) => `translate(0,${y0(d)})`);

  const total = d3.sum(datasets.flatMap(d => d.data));
  
  datasets.forEach((dataset, i) => {
    labelGroups
      .append("rect")
      .attr("y", y1(dataset.label) ?? 0)
      .attr("x", 0)
      .attr("height", y1.bandwidth())
      .attr("width", (d, idx) => x(dataset.data[idx]))
      .attr("fill", dataset.color || colorPalette[i % colorPalette.length]);
    
    // Add value labels if enabled
    if (valueLabelMode.value !== "none") {
      labelGroups.each(function(d, idx) {
        const value = dataset.data[idx];
        const percent = ((value / total) * 100).toFixed(1);
        let labelText = "";
        
        if (valueLabelMode.value === "value") {
          labelText = `${value}`;
        } else if (valueLabelMode.value === "percent") {
          labelText = `${percent}%`;
        } else if (valueLabelMode.value === "both") {
          labelText = `${value} (${percent}%)`;
        }
        
        d3.select(this)
          .append("text")
          .attr("x", x(value) + 5)
          .attr("y", (y1(dataset.label) ?? 0) + y1.bandwidth() / 2)
          .attr("dominant-baseline", "middle")
          .style("font-size", "11px")
          .style("font-weight", "600")
          .style("fill", "#334155")
          .text(labelText);
      });
    }
  });

  // Add axis labels
  if (editableXLabel.value) {
    g.append("text")
      .attr("x", width / 2)
      .attr("y", height + 40)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableXLabel.value);
  }

  if (editableYLabel.value) {
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -height / 2)
      .attr("y", -135)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableYLabel.value);
  }

  // Legend
  addLegend(g, datasets, width);
}

function renderLineChart(g: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number): void {
  const data = props.tab.data;
  const labels = data.labels;
  const datasets = getUpdatedDatasets();

  if (datasets.length === 0) return;

  // X scale
  const x = d3
    .scalePoint()
    .domain(labels)
    .range([0, width])
    .padding(0.5);

  // Y scale
  const maxValue = d3.max(datasets.flatMap((d) => d.data)) ?? 0;
  const y = d3
    .scaleLinear()
    .domain([0, maxValue * 1.1])
    .range([height, 0]);

  // X axis
  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x))
    .selectAll("text")
    .attr("transform", "rotate(-45)")
    .style("text-anchor", "end");

  // Y axis
  g.append("g").call(d3.axisLeft(y));

  // Line generator
  const line = d3
    .line<number>()
    .x((d, i) => x(labels[i]) ?? 0)
    .y((d) => y(d))
    .curve(d3.curveMonotoneX);

  // Draw lines
  const total = d3.sum(datasets.flatMap(d => d.data));
  
  datasets.forEach((dataset, i) => {
    g.append("path")
      .datum(dataset.data)
      .attr("fill", "none")
      .attr("stroke", dataset.color || colorPalette[i % colorPalette.length])
      .attr("stroke-width", 2)
      .attr("d", line);

    // Add dots
    g.selectAll(`.dot-${i}`)
      .data(dataset.data)
      .enter()
      .append("circle")
      .attr("class", `dot-${i}`)
      .attr("cx", (d, idx) => x(labels[idx]) ?? 0)
      .attr("cy", (d) => y(d))
      .attr("r", 4)
      .attr("fill", dataset.color || colorPalette[i % colorPalette.length]);
    
    // Add value labels if enabled
    if (valueLabelMode.value !== "none") {
      g.selectAll(`.label-${i}`)
        .data(dataset.data)
        .enter()
        .append("text")
        .attr("class", `label-${i}`)
        .attr("x", (d, idx) => x(labels[idx]) ?? 0)
        .attr("y", (d) => y(d) - 10)
        .attr("text-anchor", "middle")
        .style("font-size", "11px")
        .style("font-weight", "600")
        .style("fill", "#334155")
        .text((d) => {
          const percent = ((d / total) * 100).toFixed(1);
          if (valueLabelMode.value === "value") {
            return `${d}`;
          } else if (valueLabelMode.value === "percent") {
            return `${percent}%`;
          } else {
            return `${d} (${percent}%)`;
          }
        });
    }
  });

  // Add axis labels
  if (editableXLabel.value) {
    g.append("text")
      .attr("x", width / 2)
      .attr("y", height + 60)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableXLabel.value);
  }

  if (editableYLabel.value) {
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -height / 2)
      .attr("y", -60)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableYLabel.value);
  }

  // Legend
  addLegend(g, datasets, width);
}

function renderPieChart(g: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number): void {
  const data = props.tab.data;
  const labels = data.labels;
  const datasets = getUpdatedDatasets();
  const dataset = datasets[0]; // Pie charts use first dataset only

  if (!dataset) return;

  const radius = Math.min(width, height) / 2 - 40;
  g.attr("transform", `translate(${width / 2},${height / 2 + 20})`);

  const pie = d3.pie<number>().value((d) => d);
  const arc = d3
    .arc<d3.PieArcDatum<number>>()
    .innerRadius(0)
    .outerRadius(radius);

  const arcs = g
    .selectAll(".arc")
    .data(pie(dataset.data))
    .enter()
    .append("g")
    .attr("class", "arc");

  arcs
    .append("path")
    .attr("d", arc)
    .attr("fill", (d, i) => colorPalette[i % colorPalette.length])
    .attr("stroke", "white")
    .attr("stroke-width", 2);

  // Add labels based on mode
  if (valueLabelMode.value !== "none") {
    const total = d3.sum(dataset.data);
    arcs
      .append("text")
      .attr("transform", (d) => `translate(${arc.centroid(d)})`)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .style("fill", "white")
      .style("font-weight", "600")
      .text((d, i) => {
        const value = d.value;
        const percent = ((value / total) * 100).toFixed(1);
        
        if (valueLabelMode.value === "value") {
          return `${value}`;
        } else if (valueLabelMode.value === "percent") {
          return `${percent}%`;
        } else {
          return `${value} (${percent}%)`;
        }
      });
  }
}

function renderAreaChart(g: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number): void {
  const data = props.tab.data;
  const labels = data.labels;
  const datasets = getUpdatedDatasets();

  if (datasets.length === 0) return;

  // X scale
  const x = d3
    .scalePoint()
    .domain(labels)
    .range([0, width])
    .padding(0.5);

  // Y scale
  const maxValue = d3.max(datasets.flatMap((d) => d.data)) ?? 0;
  const y = d3
    .scaleLinear()
    .domain([0, maxValue * 1.1])
    .range([height, 0]);

  // X axis
  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x))
    .selectAll("text")
    .attr("transform", "rotate(-45)")
    .style("text-anchor", "end");

  // Y axis
  g.append("g").call(d3.axisLeft(y));

  // Area generator
  const area = d3
    .area<number>()
    .x((d, i) => x(labels[i]) ?? 0)
    .y0(height)
    .y1((d) => y(d))
    .curve(d3.curveMonotoneX);

  // Draw areas
  const total = d3.sum(datasets.flatMap(d => d.data));
  
  datasets.forEach((dataset, i) => {
    g.append("path")
      .datum(dataset.data)
      .attr("fill", dataset.color || colorPalette[i % colorPalette.length])
      .attr("opacity", 0.6)
      .attr("d", area);
    
    // Add value labels if enabled
    if (valueLabelMode.value !== "none") {
      g.selectAll(`.area-label-${i}`)
        .data(dataset.data)
        .enter()
        .append("text")
        .attr("class", `area-label-${i}`)
        .attr("x", (d, idx) => x(labels[idx]) ?? 0)
        .attr("y", (d) => y(d) - 10)
        .attr("text-anchor", "middle")
        .style("font-size", "11px")
        .style("font-weight", "600")
        .style("fill", "#334155")
        .text((d) => {
          const percent = ((d / total) * 100).toFixed(1);
          if (valueLabelMode.value === "value") {
            return `${d}`;
          } else if (valueLabelMode.value === "percent") {
            return `${percent}%`;
          } else {
            return `${d} (${percent}%)`;
          }
        });
    }
  });

  // Add axis labels
  if (editableXLabel.value) {
    g.append("text")
      .attr("x", width / 2)
      .attr("y", height + 60)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableXLabel.value);
  }

  if (editableYLabel.value) {
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -height / 2)
      .attr("y", -60)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableYLabel.value);
  }

  // Legend
  addLegend(g, datasets, width);
}

function renderScatterChart(g: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number): void {
  const data = props.tab.data;
  const labels = data.labels;
  const datasets = getUpdatedDatasets();

  if (datasets.length === 0) return;

  // X scale
  const x = d3
    .scalePoint()
    .domain(labels)
    .range([0, width])
    .padding(0.5);

  // Y scale
  const maxValue = d3.max(datasets.flatMap((d) => d.data)) ?? 0;
  const y = d3
    .scaleLinear()
    .domain([0, maxValue * 1.1])
    .range([height, 0]);

  // X axis
  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x))
    .selectAll("text")
    .attr("transform", "rotate(-45)")
    .style("text-anchor", "end");

  // Y axis
  g.append("g").call(d3.axisLeft(y));

  // Draw scatter points
  const total = d3.sum(datasets.flatMap(d => d.data));
  
  datasets.forEach((dataset, i) => {
    g.selectAll(`.scatter-${i}`)
      .data(dataset.data)
      .enter()
      .append("circle")
      .attr("class", `scatter-${i}`)
      .attr("cx", (d, idx) => x(labels[idx]) ?? 0)
      .attr("cy", (d) => y(d))
      .attr("r", 5)
      .attr("fill", dataset.color || colorPalette[i % colorPalette.length])
      .attr("opacity", 0.7);
    
    // Add value labels if enabled
    if (valueLabelMode.value !== "none") {
      g.selectAll(`.scatter-label-${i}`)
        .data(dataset.data)
        .enter()
        .append("text")
        .attr("class", `scatter-label-${i}`)
        .attr("x", (d, idx) => x(labels[idx]) ?? 0)
        .attr("y", (d) => y(d) - 10)
        .attr("text-anchor", "middle")
        .style("font-size", "11px")
        .style("font-weight", "600")
        .style("fill", "#334155")
        .text((d) => {
          const percent = ((d / total) * 100).toFixed(1);
          if (valueLabelMode.value === "value") {
            return `${d}`;
          } else if (valueLabelMode.value === "percent") {
            return `${percent}%`;
          } else {
            return `${d} (${percent}%)`;
          }
        });
    }
  });

  // Add axis labels
  if (editableXLabel.value) {
    g.append("text")
      .attr("x", width / 2)
      .attr("y", height + 60)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableXLabel.value);
  }

  if (editableYLabel.value) {
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -height / 2)
      .attr("y", -60)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(editableYLabel.value);
  }

  // Legend
  addLegend(g, datasets, width);
}

function addLegend(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  datasets: Array<{ label: string; data: number[]; color?: string }>,
  width: number
): void {
  const legend = g
    .selectAll(".legend")
    .data(datasets)
    .enter()
    .append("g")
    .attr("class", "legend")
    .attr("transform", (d, i) => `translate(${width + 10},${i * 20})`);

  legend
    .append("rect")
    .attr("width", 15)
    .attr("height", 15)
    .attr("fill", (d, i) => d.color || colorPalette[i % colorPalette.length]);

  legend
    .append("text")
    .attr("x", 20)
    .attr("y", 12)
    .style("font-size", "12px")
    .text((d) => d.label);
}

function saveAsImage(): void {
  if (!chartSvg.value) return;

  const svgElement = chartSvg.value;

  if (exportFormat.value === "svg") {
    // Save as SVG
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgElement);
    const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = `${editableTitle.value || "chart"}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  } else {
    // Save as PNG
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgElement);
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    
    if (!ctx) return;

    const img = new Image();
    const svgBlob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);

    img.onload = () => {
      canvas.width = svgElement.clientWidth * 2; // 2x for better quality
      canvas.height = svgElement.clientHeight * 2;
      ctx.fillStyle = "white";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      canvas.toBlob((blob) => {
        if (blob) {
          const pngUrl = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = pngUrl;
          link.download = `${editableTitle.value || "chart"}.png`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(pngUrl);
        }
        URL.revokeObjectURL(url);
      }, "image/png");
    };

    img.src = url;
  }
}

function openSqlInTab(): void {
  if (props.tab.sql) {
    sessionStore.createQueryTab({ sql: props.tab.sql, makeActive: true });
  }
}
</script>

<style scoped>
.chart-viewer {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: 100%;
  overflow: hidden;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chart-type-selector {
  padding: 0.45rem 0.75rem;
  border: 1px solid #cbd5f5;
  border-radius: 6px;
  font-size: 0.9rem;
  background: white;
  cursor: pointer;
}

.chart-type-selector:focus {
  outline: none;
  border-color: #b26a45;
}

.export-format-selector {
  padding: 0.45rem 0.75rem;
  border: 1px solid #cbd5f5;
  border-radius: 6px;
  font-size: 0.9rem;
  background: white;
  cursor: pointer;
  min-width: 70px;
}

.export-format-selector:focus {
  outline: none;
  border-color: #b26a45;
}

.save-dropdown {
  position: relative;
  display: inline-flex;
  align-items: stretch;
}

.save-main {
  border-top-right-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
  border-right: none !important;
  white-space: nowrap;
}

.save-toggle {
  border-top-left-radius: 0 !important;
  border-bottom-left-radius: 0 !important;
  padding: 0.45rem 0.5rem !important;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: auto;
}

.export-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.25rem;
  background: white;
  border: 1px solid #cbd5f5;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 100;
  min-width: 140px;
}

.menu-item {
  display: block;
  width: 100%;
  padding: 0.6rem 1rem;
  text-align: left;
  background: none;
  border: none;
  color: #334155;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.15s;
}

.menu-item:first-child {
  border-top-left-radius: 6px;
  border-top-right-radius: 6px;
}

.menu-item:last-child {
  border-bottom-left-radius: 6px;
  border-bottom-right-radius: 6px;
}

.menu-item:hover {
  background-color: #f1f5f9;
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

.chart-controls {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.control-group {
  flex: 1;
  min-width: 200px;
}

.control-group label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #475569;
}

.control-group input {
  padding: 0.45rem 0.75rem;
  border: 1px solid #cbd5f5;
  border-radius: 6px;
  font-size: 0.9rem;
}

.control-group input:focus {
  outline: none;
  border-color: #b26a45;
}

.label-mode-selector {
  padding: 0.45rem 0.75rem;
  border: 1px solid #cbd5f5;
  border-radius: 6px;
  font-size: 0.9rem;
  background: white;
  cursor: pointer;
}

.label-mode-selector:focus {
  outline: none;
  border-color: #b26a45;
}

.chart-container {
  flex: 1;
  min-height: 0;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: white;
  padding: 1rem;
}

.chart-svg {
  display: block;
  width: 100%;
}

.chart-info {
  padding: 1rem;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.chart-info h3 {
  margin: 0 0 0.5rem 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: #334155;
}

.chart-info p {
  margin: 0;
  font-size: 0.85rem;
  color: #64748b;
  line-height: 1.5;
}

.section-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
</style>
