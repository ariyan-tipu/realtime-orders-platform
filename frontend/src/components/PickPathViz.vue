<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { fetchPickPath } from "../api";
import { useDashboardStore } from "../stores/dashboard";
import type { PickPathResponse, PickPathStop } from "../types";

const store = useDashboardStore();
const path = ref<PickPathResponse | null>(null);
const error = ref("");
const engineOverride = ref<string | undefined>(undefined);
const hovered = ref<PickPathStop | null>(null);
const tooltipPos = ref({ x: 0, y: 0 });

async function load(): Promise<void> {
  if (!store.selectedOrderId) {
    return;
  }
  error.value = "";
  hovered.value = null;
  try {
    path.value = await fetchPickPath(store.selectedOrderId, engineOverride.value);
  } catch {
    error.value = engineOverride.value
      ? `${engineOverride.value} engine unavailable here`
      : "could not compute pick path";
    if (engineOverride.value) {
      engineOverride.value = undefined; // fall back to best available
    }
  }
}

watch(() => store.selectedOrderId, load, { immediate: true });
watch(engineOverride, load);

const grid = computed(() => path.value?.warehouse ?? { code: "", grid_width: 40, grid_height: 15 });

const viewBox = computed(
  () => `-1.2 -1.2 ${grid.value.grid_width + 2.4} ${grid.value.grid_height + 2.4}`,
);

const polylinePoints = computed(() => {
  if (!path.value) {
    return "";
  }
  const points = [
    "0,0",
    ...path.value.stops.map((stop) => `${stop.x},${stop.y}`),
    "0,0",
  ];
  return points.join(" ");
});

function onHover(stop: PickPathStop, event: MouseEvent): void {
  hovered.value = stop;
  const bounds = (event.currentTarget as SVGElement).closest("figure")?.getBoundingClientRect();
  tooltipPos.value = {
    x: event.clientX - (bounds?.left ?? 0) + 12,
    y: event.clientY - (bounds?.top ?? 0) + 12,
  };
}
</script>

<template>
  <section class="panel" aria-label="Warehouse pick path">
    <div class="head">
      <h2>
        Pick path
        <span v-if="path" class="secondary normal">
          · order <code>{{ path.order.slice(0, 8) }}</code> · {{ grid.code }}
        </span>
      </h2>
      <div class="controls" role="group" aria-label="Optimiser engine">
        <button
          class="ghost"
          :aria-pressed="engineOverride === undefined"
          @click="engineOverride = undefined"
        >
          auto
        </button>
        <button
          class="ghost"
          :aria-pressed="engineOverride === 'python'"
          @click="engineOverride = 'python'"
        >
          python
        </button>
        <button
          class="ghost"
          :aria-pressed="engineOverride === 'native'"
          @click="engineOverride = 'native'"
        >
          C++
        </button>
      </div>
    </div>

    <p v-if="!store.selectedOrderId" class="muted">Select an order above to compute its route.</p>
    <p v-if="error" class="muted">{{ error }}</p>

    <template v-if="path">
      <p class="stats secondary">
        engine <strong>{{ path.engine }}</strong>
        · distance <strong class="num">{{ path.total_distance }}</strong> cells
        · computed in <strong class="num">{{ path.computed_ms }}</strong> ms
        · {{ path.stops.length }} stops
        <span v-if="path.unlocated_skus.length > 0" class="muted">
          · unlocated: {{ path.unlocated_skus.join(", ") }}
        </span>
      </p>

      <figure>
        <svg :viewBox="viewBox" role="img" aria-label="Route through warehouse grid">
          <defs>
            <pattern id="cells" width="1" height="1" patternUnits="userSpaceOnUse">
              <path d="M 1 0 L 0 0 0 1" fill="none" stroke="var(--hairline)" stroke-width="0.03" />
            </pattern>
          </defs>
          <rect
            x="0"
            y="0"
            :width="grid.grid_width"
            :height="grid.grid_height"
            fill="url(#cells)"
            stroke="var(--hairline)"
            stroke-width="0.05"
          />
          <polyline
            :points="polylinePoints"
            fill="none"
            stroke="var(--series-blue)"
            stroke-width="0.14"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          <g>
            <rect x="-0.45" y="-0.45" width="0.9" height="0.9" rx="0.15" class="depot" />
            <text x="0" y="0.02" class="depot-label">D</text>
          </g>
          <g v-for="stop in path.stops" :key="stop.seq">
            <circle
              :cx="stop.x"
              :cy="stop.y"
              r="0.8"
              fill="transparent"
              @mousemove="onHover(stop, $event)"
              @mouseleave="hovered = null"
            />
            <circle :cx="stop.x" :cy="stop.y" r="0.34" class="stop" />
            <text :x="stop.x" :y="stop.y + 0.02" class="stop-label">{{ stop.seq + 1 }}</text>
          </g>
        </svg>
        <div
          v-if="hovered"
          class="tooltip"
          :style="{ left: `${tooltipPos.x}px`, top: `${tooltipPos.y}px` }"
        >
          <div class="secondary">bin ({{ hovered.x }}, {{ hovered.y }})</div>
          <div v-for="item in hovered.items" :key="item.sku">
            <code>{{ item.sku }}</code> × {{ item.quantity }}
          </div>
        </div>
      </figure>
    </template>
  </section>
</template>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}

.normal {
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
}

.controls {
  display: flex;
  gap: 6px;
}

.stats {
  font-size: 12px;
  margin: 4px 0 10px;
}

figure {
  margin: 0;
  position: relative;
}

svg {
  width: 100%;
  height: auto;
  display: block;
}

.depot {
  fill: var(--surface);
  stroke: var(--ink-secondary);
  stroke-width: 0.08;
}

.depot-label,
.stop-label {
  font-size: 0.45px;
  text-anchor: middle;
  dominant-baseline: middle;
  fill: var(--ink);
  pointer-events: none;
}

.stop {
  fill: var(--surface);
  stroke: var(--series-blue);
  stroke-width: 0.1;
}

.tooltip {
  position: absolute;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 7px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
  padding: 8px 10px;
  font-size: 12px;
  pointer-events: none;
  max-width: 240px;
  z-index: 2;
}
</style>
