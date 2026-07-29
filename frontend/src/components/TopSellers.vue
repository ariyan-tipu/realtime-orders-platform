<script setup lang="ts">
import { computed } from "vue";

import { formatMoney } from "../config";
import { useDashboardStore } from "../stores/dashboard";
import type { TopSellerRow } from "../types";

const store = useDashboardStore();

const byWarehouse = computed(() => {
  const groups = new Map<string, TopSellerRow[]>();
  for (const row of store.topSellers) {
    const list = groups.get(row.warehouse) ?? [];
    list.push(row);
    groups.set(row.warehouse, list);
  }
  return groups;
});
</script>

<template>
  <section class="panel" aria-label="Top sellers, last 24 hours">
    <h2>Top sellers · 24h</h2>
    <p v-if="store.topSellers.length === 0" class="muted">No sales in the last 24 hours yet.</p>
    <div v-for="[warehouse, rows] in byWarehouse" :key="warehouse" class="group">
      <h3>{{ warehouse }}</h3>
      <table>
        <tbody>
          <tr v-for="row in rows" :key="`${warehouse}:${row.product}`">
            <td class="num rank muted">{{ row.sales_rank }}</td>
            <td class="product">{{ row.product }}</td>
            <td class="num secondary">{{ row.units_sold }} u</td>
            <td class="num muted">{{ formatMoney(row.revenue_pence) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.group h3 {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-muted);
  margin: 10px 0 2px;
}

.rank {
  width: 20px;
}

.product {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
}

td {
  font-size: 13px;
  padding: 3px 6px;
}
</style>
