import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import type { ApiOrder, ApiStockRow, OrderEvent, StockEvent } from "../types";
import { useDashboardStore } from "./dashboard";

function apiOrder(overrides: Partial<ApiOrder> = {}): ApiOrder {
  return {
    public_id: "order-1",
    status: "PENDING",
    warehouse: "LDN",
    total_pence: 1099,
    currency: "GBP",
    created_at: "2026-07-07T10:00:00Z",
    updated_at: "2026-07-07T10:00:00Z",
    items: [
      { sku: "MUG-1", name: "One Size", quantity: 1, unit_price_pence: 1099, line_total_pence: 1099 },
    ],
    ...overrides,
  };
}

function orderEvent(overrides: Partial<OrderEvent> = {}): OrderEvent {
  return {
    type: "order",
    order_id: "order-1",
    status: "CONFIRMED",
    previous: "PENDING",
    warehouse: "LDN",
    total_pence: 1099,
    currency: "GBP",
    items_count: 1,
    created_at: "2026-07-07T10:00:00Z",
    ...overrides,
  };
}

function stockEvent(overrides: Partial<StockEvent> = {}): StockEvent {
  return {
    type: "stock",
    warehouse: "LDN",
    changes: [{ sku: "MUG-1", product: "Azure Mug", quantity: 7, bin: [2, 3] }],
    ...overrides,
  };
}

function stockRow(overrides: Partial<ApiStockRow> = {}): ApiStockRow {
  return {
    sku: "MUG-1",
    product: "Azure Mug",
    warehouse: "LDN",
    quantity: 9,
    bin_x: 2,
    bin_y: 3,
    updated_at: "2026-07-07T10:00:00Z",
    ...overrides,
  };
}

describe("dashboard store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("hydrates orders and selects the newest for the pick-path panel", () => {
    const store = useDashboardStore();
    store.hydrateOrders([apiOrder(), apiOrder({ public_id: "order-2" })]);
    expect(store.orders).toHaveLength(2);
    expect(store.orders[0].itemsCount).toBe(1);
    expect(store.selectedOrderId).toBe("order-1");
  });

  it("prepends unseen order events and caps the feed at 40 rows", () => {
    const store = useDashboardStore();
    for (let index = 0; index < 45; index += 1) {
      store.applyEvent(orderEvent({ order_id: `order-${index}`, status: "PENDING" }));
    }
    expect(store.orders).toHaveLength(40);
    expect(store.orders[0].orderId).toBe("order-44"); // newest first
    expect(store.eventsSeen).toBe(45);
  });

  it("updates status and bumps version for orders already on screen", () => {
    const store = useDashboardStore();
    store.hydrateOrders([apiOrder()]);
    expect(store.orders[0].version).toBe(0);

    store.applyEvent(orderEvent({ status: "SHIPPED" }));

    expect(store.orders).toHaveLength(1);
    expect(store.orders[0].status).toBe("SHIPPED");
    expect(store.orders[0].version).toBe(1);
  });

  it("upserts stock rows from stock events", () => {
    const store = useDashboardStore();
    store.hydrateStock([stockRow()]);

    store.applyEvent(stockEvent()); // existing SKU: quantity 9 -> 7
    store.applyEvent(
      stockEvent({
        warehouse: "MCR",
        changes: [{ sku: "BAG-1", product: "Crimson Bag", quantity: 4, bin: [1, 1] }],
      }),
    );

    const rows = store.stockRows;
    expect(rows).toHaveLength(2);
    expect(rows.find((row) => row.sku === "MUG-1")?.quantity).toBe(7);
    expect(rows.find((row) => row.sku === "MUG-1")?.version).toBe(1);
    expect(rows.find((row) => row.sku === "BAG-1")?.warehouse).toBe("MCR");
  });

  it("ignores hello and heartbeat frames", () => {
    const store = useDashboardStore();
    store.applyEvent({ type: "hello", filter: null, server_time: "2026-07-07T10:00:00Z" });
    store.applyEvent({ type: "heartbeat" });
    expect(store.orders).toHaveLength(0);
    expect(store.eventsSeen).toBe(0);
  });

  it("derives warehouse list and max quantity for bar scaling", () => {
    const store = useDashboardStore();
    store.hydrateStock([
      stockRow(),
      stockRow({ sku: "BAG-1", warehouse: "MCR", quantity: 120 }),
    ]);
    expect(store.warehouses).toEqual(["LDN", "MCR"]);
    expect(store.maxStockQuantity).toBe(120);
  });
});
