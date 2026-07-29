<script setup lang="ts">
import type { OrderStatus } from "../types";

defineProps<{ status: OrderStatus }>();

// Terminal states wear reserved status colours; the in-progress ladder wears a
// validated ordinal blue ramp (identity is carried by the text, never colour alone).
const DOT: Record<OrderStatus, string> = {
  PENDING: "var(--status-warning)",
  CONFIRMED: "var(--ordinal-1)",
  PICKING: "var(--ordinal-2)",
  PACKED: "var(--ordinal-3)",
  SHIPPED: "var(--ordinal-4)",
  DELIVERED: "var(--status-good)",
  CANCELLED: "var(--status-critical)",
};
</script>

<template>
  <span class="badge">
    <span class="dot" :style="{ background: DOT[status] }" aria-hidden="true"></span>
    {{ status }}
  </span>
</template>
