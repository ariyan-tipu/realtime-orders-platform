<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";

import { fetchRecentOrders, fetchStock, fetchTopSellers } from "./api";
import ConnectionBadge from "./components/ConnectionBadge.vue";
import DemoButton from "./components/DemoButton.vue";
import LiveOrders from "./components/LiveOrders.vue";
import PickPathViz from "./components/PickPathViz.vue";
import StockPanel from "./components/StockPanel.vue";
import TopSellers from "./components/TopSellers.vue";
import { useDemoReplay } from "./composables/useDemoReplay";
import { useDashboardSocket } from "./composables/useWebSocket";
import { IS_REPLAY } from "./config";
import { useDashboardStore } from "./stores/dashboard";

const store = useDashboardStore();

// The only difference between the published demo and a real deployment:
// where the events come from. Everything below this line is identical.
if (IS_REPLAY) {
  useDemoReplay();
} else {
  useDashboardSocket();
}

let topSellersTimer: ReturnType<typeof setInterval> | null = null;

async function refreshTopSellers(): Promise<void> {
  try {
    const payload = await fetchTopSellers();
    store.setTopSellers(payload.rows, payload.generated_at);
  } catch {
    /* transient API failure; next tick retries */
  }
}

onMounted(async () => {
  // Snapshot over REST, then live deltas over the WebSocket.
  try {
    const [orders, stock] = await Promise.all([fetchRecentOrders(), fetchStock()]);
    store.hydrateOrders(orders);
    store.hydrateStock(stock);
  } catch {
    /* services still starting; the socket will fill the screen as events flow */
  }
  await refreshTopSellers();
  topSellersTimer = setInterval(refreshTopSellers, 30_000);
});

onBeforeUnmount(() => {
  if (topSellersTimer !== null) {
    clearInterval(topSellersTimer);
  }
});
</script>

<template>
  <header>
    <div>
      <h1>Realtime Orders - Operations Dashboard</h1>
      <p class="muted sub">Django core · FastAPI realtime · Postgres LISTEN/NOTIFY · C++ pick-path</p>
    </div>
    <div class="actions">
      <ConnectionBadge />
      <DemoButton />
    </div>
  </header>

  <p v-if="IS_REPLAY" class="replay-banner">
    <strong>Interactive demo, not a live deployment.</strong>
    This page is the production dashboard build with its event source swapped
    for an in-browser simulation, so there is no server behind it. The real
    stack (Django, FastAPI, PostgreSQL <code>LISTEN/NOTIFY</code>, the C++
    pick-path engine) runs locally with one
    <code>docker compose up</code>:
    <a href="https://github.com/ariyan-tipu/realtime-orders-platform#quickstart">see the quickstart</a>.
    The concurrency and locking guarantees are proven by the test suite
    against a real PostgreSQL, not by this page.
  </p>

  <main>
    <div class="orders"><LiveOrders /></div>
    <div class="stock"><StockPanel /></div>
    <div class="top"><TopSellers /></div>
    <div class="path"><PickPathViz /></div>
  </main>
</template>

<style scoped>
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.sub {
  margin: 2px 0 0;
  font-size: 12px;
}

.replay-banner {
  margin: 0 0 14px;
  padding: 10px 12px;
  border: 1px solid #b7791f;
  border-left-width: 4px;
  border-radius: 6px;
  background: rgba(183, 121, 31, 0.12);
  font-size: 12.5px;
  line-height: 1.5;
}

.replay-banner code {
  font-size: 11.5px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

main {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  grid-template-areas:
    "orders stock"
    "orders top"
    "path path";
  gap: 14px;
}

.orders {
  grid-area: orders;
}

.stock {
  grid-area: stock;
}

.top {
  grid-area: top;
}

.path {
  grid-area: path;
}

@media (max-width: 900px) {
  main {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "orders"
      "stock"
      "top"
      "path";
  }
}
</style>
