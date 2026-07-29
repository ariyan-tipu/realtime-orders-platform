<script setup lang="ts">
import { computed } from "vue";

import { useDashboardStore } from "../stores/dashboard";

const store = useDashboardStore();

const view = computed(() => {
  switch (store.connection) {
    case "online":
      return { label: "Live", colour: "var(--status-good)" };
    case "connecting":
      return { label: "Connecting…", colour: "var(--status-warning)" };
    default:
      return { label: "Reconnecting…", colour: "var(--status-critical)" };
  }
});
</script>

<template>
  <span class="badge" role="status">
    <span class="dot" :style="{ background: view.colour }" aria-hidden="true"></span>
    {{ view.label }}
    <span v-if="store.eventsSeen > 0" class="muted">· {{ store.eventsSeen }} events</span>
  </span>
</template>
