<script setup lang="ts">
import { computed, ref } from "vue";

import { useDashboardStore } from "../stores/dashboard";

const VISIBLE_ROWS = 30;
const LOW_THRESHOLD = 10;

const store = useDashboardStore();
const warehouseFilter = ref<string>("all");

const filtered = computed(() => {
  const rows = store.stockRows;
  if (warehouseFilter.value === "all") {
    return rows;
  }
  return rows.filter((row) => row.warehouse === warehouseFilter.value);
});

const visible = computed(() => filtered.value.slice(0, VISIBLE_ROWS));

function barWidth(quantity: number): string {
  return `${Math.max(1.5, (quantity / store.maxStockQuantity) * 100)}%`;
}
</script>

<template>
  <section class="panel" aria-label="Stock levels">
    <div class="head">
      <h2>Stock levels</h2>
      <label class="muted">
        Warehouse
        <select v-model="warehouseFilter">
          <option value="all">All</option>
          <option v-for="code in store.warehouses" :key="code" :value="code">{{ code }}</option>
        </select>
      </label>
    </div>

    <p v-if="visible.length === 0" class="muted">No stock rows yet. Seed the database first.</p>
    <ul v-else class="rows">
      <li
        v-for="row in visible"
        :key="`${row.warehouse}::${row.sku}:${row.version}`"
        :class="{ flash: row.version > 0 }"
      >
        <span class="sku"><code>{{ row.sku }}</code> <span class="secondary">{{ row.product }}</span></span>
        <span class="wh muted">{{ row.warehouse }}</span>
        <span class="bar-track" aria-hidden="true">
          <span class="bar" :style="{ width: barWidth(row.quantity) }"></span>
        </span>
        <span class="qty num">{{ row.quantity }}</span>
        <span v-if="row.quantity === 0" class="badge chip">
          <span class="dot" style="background: var(--status-critical)" aria-hidden="true"></span>OUT
        </span>
        <span v-else-if="row.quantity < LOW_THRESHOLD" class="badge chip">
          <span class="dot" style="background: var(--status-warning)" aria-hidden="true"></span>LOW
        </span>
      </li>
    </ul>
    <p v-if="filtered.length > VISIBLE_ROWS" class="muted hint">
      Showing {{ VISIBLE_ROWS }} of {{ filtered.length }} SKUs.
    </p>
  </section>
</template>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.head label {
  font-size: 12px;
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.rows {
  list-style: none;
  margin: 0;
  padding: 0;
}

.rows li {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) 34px minmax(60px, 1fr) 44px auto;
  gap: 10px;
  align-items: center;
  padding: 5px 0;
  border-bottom: 1px solid var(--hairline);
}

.rows li:last-child {
  border-bottom: none;
}

.sku {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sku code {
  font-size: 12px;
}

.wh {
  font-size: 12px;
}

.bar-track {
  display: block;
  height: 8px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--hairline) 55%, transparent);
  overflow: hidden;
}

.bar {
  display: block;
  height: 100%;
  border-radius: 4px;
  background: var(--seq-bar);
  transition: width 0.4s ease;
}

.qty {
  font-size: 13px;
}

.chip {
  font-size: 11px;
}

.hint {
  font-size: 12px;
  margin: 10px 0 0;
}
</style>
