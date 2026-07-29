<script setup lang="ts">
import { ref } from "vue";

import { placeDemoOrder } from "../api";

const busy = ref(false);
const error = ref("");

async function simulate(): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    await placeDemoOrder();
    // No local state change needed: the order arrives via the WebSocket.
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : "demo order failed";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <span class="wrap">
    <button class="primary" :disabled="busy" @click="simulate">
      {{ busy ? "Placing…" : "Simulate order" }}
    </button>
    <span v-if="error" class="muted err">{{ error }}</span>
  </span>
</template>

<style scoped>
.wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.err {
  font-size: 12px;
  max-width: 260px;
}
</style>
