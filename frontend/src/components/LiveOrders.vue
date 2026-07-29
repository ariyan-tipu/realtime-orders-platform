<script setup lang="ts">
import { formatMoney, formatTime } from "../config";
import { useDashboardStore } from "../stores/dashboard";
import StatusBadge from "./StatusBadge.vue";

const store = useDashboardStore();

function shortId(orderId: string): string {
  return orderId.slice(0, 8);
}
</script>

<template>
  <section class="panel" aria-label="Live orders">
    <h2>Live orders</h2>
    <p v-if="store.orders.length === 0" class="muted">
      Waiting for orders. Run <code>manage.py demo_orders</code> or press "Simulate order".
    </p>
    <table v-else>
      <thead>
        <tr>
          <th scope="col">Time</th>
          <th scope="col">Order</th>
          <th scope="col">Warehouse</th>
          <th scope="col" class="num">Items</th>
          <th scope="col" class="num">Total</th>
          <th scope="col">Status</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in store.orders"
          :key="`${row.orderId}:${row.version}`"
          :class="{ flash: row.version > 0, selected: row.orderId === store.selectedOrderId }"
          tabindex="0"
          @click="store.selectOrder(row.orderId)"
          @keydown.enter="store.selectOrder(row.orderId)"
        >
          <td class="muted">{{ formatTime(row.createdAt) }}</td>
          <td><code>{{ shortId(row.orderId) }}</code></td>
          <td class="secondary">{{ row.warehouse }}</td>
          <td class="num">{{ row.itemsCount }}</td>
          <td class="num">{{ formatMoney(row.totalPence) }}</td>
          <td><StatusBadge :status="row.status" /></td>
        </tr>
      </tbody>
    </table>
    <p class="muted hint">Click an order to draw its warehouse pick path below.</p>
  </section>
</template>

<style scoped>
tbody tr {
  cursor: pointer;
}

tbody tr.selected td {
  background: color-mix(in srgb, var(--series-blue) 9%, transparent);
}

tbody tr:focus-visible {
  outline: 2px solid var(--series-blue);
  outline-offset: -2px;
}

code {
  font-size: 12px;
  color: var(--ink-secondary);
}

.hint {
  font-size: 12px;
  margin: 10px 0 0;
}
</style>
