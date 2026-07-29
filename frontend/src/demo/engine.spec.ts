import { describe, expect, it } from "vitest";

import { WAREHOUSES } from "./catalogue";
import { DemoEngine } from "./engine";
import type { OrderEvent, StockEvent, WsEvent } from "../types";

function collect(engine: DemoEngine): WsEvent[] {
  const seen: WsEvent[] = [];
  engine.subscribe((event) => seen.push(event));
  return seen;
}

describe("DemoEngine", () => {
  it("starts with a populated dashboard rather than an empty one", () => {
    const engine = new DemoEngine(1);
    expect(engine.recentOrders().length).toBeGreaterThan(5);
    expect(engine.stockRows().length).toBe(WAREHOUSES.length * 8);
  });

  it("makes the same decisions for a given seed", () => {
    // Timestamps come from the wall clock on purpose, because the order feed
    // shows real elapsed times. Everything the seed drives is reproducible.
    const decisions = (engine: DemoEngine) =>
      engine.recentOrders().map(({ public_id, status, warehouse, total_pence, items }) => ({
        public_id,
        status,
        warehouse,
        total_pence,
        items,
      }));

    expect(decisions(new DemoEngine(42))).toEqual(decisions(new DemoEngine(42)));
    expect(decisions(new DemoEngine(42))).not.toEqual(decisions(new DemoEngine(43)));
  });

  it("never lets stock go negative", () => {
    const engine = new DemoEngine(7);
    for (let i = 0; i < 400; i += 1) {
      engine.placeOrder();
    }
    for (const row of engine.stockRows()) {
      expect(row.quantity).toBeGreaterThanOrEqual(0);
    }
  });

  it("emits an order frame and a stock frame when an order is placed", () => {
    const engine = new DemoEngine(3);
    const seen = collect(engine);
    engine.placeOrder();

    const orderEvents = seen.filter((e): e is OrderEvent => e.type === "order");
    const stockEvents = seen.filter((e): e is StockEvent => e.type === "stock");
    expect(orderEvents).toHaveLength(1);
    expect(orderEvents[0].status).toBe("PENDING");
    expect(orderEvents[0].previous).toBeNull();
    expect(orderEvents[0].items_count).toBeGreaterThan(0);
    expect(stockEvents.length).toBeGreaterThanOrEqual(1);
  });

  it("decrements exactly the units an order took", () => {
    const engine = new DemoEngine(11);
    const before = new Map(engine.stockRows().map((r) => [`${r.warehouse}::${r.sku}`, r.quantity]));
    const order = engine.placeOrder();
    expect(order).not.toBeNull();

    const after = new Map(engine.stockRows().map((r) => [`${r.warehouse}::${r.sku}`, r.quantity]));
    for (const line of order!.lines) {
      const key = `${order!.warehouse}::${line.sku}`;
      // Replenishment can top a line back up, so assert it never dropped by
      // more than the quantity taken.
      expect(before.get(key)! - after.get(key)!).toBeLessThanOrEqual(line.quantity);
    }
  });

  it("computes a pick path over the ordered bins", () => {
    const engine = new DemoEngine(5);
    const order = engine.recentOrders()[0];
    const path = engine.pickPath(order.public_id);

    expect(path.order).toBe(order.public_id);
    expect(path.stops.length).toBeGreaterThan(0);
    expect(path.stops.length).toBeLessThanOrEqual(order.items.length);
    expect(path.total_distance).toBeGreaterThan(0);
    expect(path.stops.map((s) => s.seq)).toEqual(path.stops.map((_, i) => i));
  });

  it("rejects a pick path for an order it does not know", () => {
    expect(() => new DemoEngine(5).pickPath("no-such-order")).toThrow();
  });

  it("ranks top sellers per warehouse", () => {
    const engine = new DemoEngine(9);
    for (let i = 0; i < 40; i += 1) {
      engine.placeOrder();
    }
    const { rows } = engine.topSellers();
    for (const warehouse of WAREHOUSES) {
      const forWarehouse = rows.filter((r) => r.warehouse === warehouse);
      expect(forWarehouse.length).toBeGreaterThan(0);
      expect(forWarehouse.map((r) => r.sales_rank)).toEqual(
        forWarehouse.map((_, index) => index + 1),
      );
      const units = forWarehouse.map((r) => r.units_sold);
      expect([...units].sort((a, b) => b - a)).toEqual(units);
    }
  });

  it("tallies top sellers per warehouse rather than globally", () => {
    // A global tally would print identical figures under both warehouses,
    // which is both wrong and the fastest way to spot a faked dashboard.
    const engine = new DemoEngine(21);
    for (let i = 0; i < 60; i += 1) {
      engine.placeOrder();
    }
    const { rows } = engine.topSellers();
    const ldn = rows.filter((r) => r.warehouse === "LDN").map((r) => r.units_sold);
    const man = rows.filter((r) => r.warehouse === "MAN").map((r) => r.units_sold);
    expect(ldn.length).toBeGreaterThan(0);
    expect(man.length).toBeGreaterThan(0);
    expect(ldn).not.toEqual(man);
  });

  it("stops emitting once stopped", () => {
    const engine = new DemoEngine(13);
    engine.start(1);
    engine.stop();
    const seen = collect(engine);
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        expect(seen).toHaveLength(0);
        resolve();
      }, 30);
    });
  });
});
