/** An in-browser stand-in for the Django core and the realtime gateway.
 *
 * It emits exactly the frames `orders/events.py` publishes and answers the
 * same REST shapes `api.ts` fetches, so the dashboard, the Pinia store and
 * every component run unmodified. Only the transport is replaced: instead
 * of Postgres NOTIFY reaching a FastAPI socket, a timer walks orders along
 * the same lifecycle and hands the frames to the same `applyEvent`.
 *
 * The order lifecycle, the status flow and the all-or-nothing stock rule
 * mirror `orders/services.py`. What it deliberately does not reproduce is
 * the part that matters most in the real system: there is one thread here,
 * so there is no contention, no row locking and nothing for `SELECT ...
 * FOR UPDATE` to protect against. The concurrency guarantees are proven by
 * the test suite against a real PostgreSQL, not by this.
 */

import type {
  ApiOrder,
  ApiStockRow,
  OrderStatus,
  PickPathResponse,
  TopSellerRow,
  TopSellersResponse,
  WsEvent,
} from "../types";
import { GRID, INITIAL_QUANTITY, PRODUCTS, WAREHOUSES, mulberry32 } from "./catalogue";
import { optimiseRoute, type Point } from "./pickpath";

const NEXT_STATUS: Record<OrderStatus, OrderStatus | null> = {
  PENDING: "CONFIRMED",
  CONFIRMED: "PICKING",
  PICKING: "PACKED",
  PACKED: "SHIPPED",
  SHIPPED: "DELIVERED",
  DELIVERED: null,
  CANCELLED: null,
};

interface DemoLine {
  sku: string;
  product: string;
  quantity: number;
  unitPricePence: number;
}

interface DemoOrder {
  publicId: string;
  status: OrderStatus;
  warehouse: string;
  lines: DemoLine[];
  totalPence: number;
  createdAt: string;
}

type Listener = (event: WsEvent) => void;

function stockKey(warehouse: string, sku: string): string {
  return `${warehouse}::${sku}`;
}

export class DemoEngine {
  private readonly random: () => number;
  private readonly stock = new Map<string, number>();
  private readonly orders: DemoOrder[] = [];
  private readonly listeners = new Set<Listener>();
  private readonly unitsSold = new Map<string, { units: number; revenue: number; orders: number }>();
  private timer: ReturnType<typeof setInterval> | null = null;
  private counter = 0;

  constructor(seed = 20260728) {
    this.random = mulberry32(seed);
    for (const warehouse of WAREHOUSES) {
      for (const product of PRODUCTS) {
        this.stock.set(stockKey(warehouse, product.sku), INITIAL_QUANTITY[product.sku]);
      }
    }
    // Backdate a little history so the first paint is a working dashboard
    // rather than an empty one waiting for the first tick.
    for (let i = 0; i < 14; i += 1) {
      this.placeOrder(-((14 - i) * 45_000));
    }
    for (const order of this.orders) {
      const steps = Math.floor(this.random() * 4);
      for (let s = 0; s < steps; s += 1) {
        this.advance(order);
      }
    }
  }

  // --- transport -----------------------------------------------------

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(event: WsEvent): void {
    for (const listener of this.listeners) {
      listener(event);
    }
  }

  start(intervalMs = 2600): void {
    if (this.timer !== null) {
      return;
    }
    this.timer = setInterval(() => this.tick(), intervalMs);
  }

  stop(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  private tick(): void {
    if (this.random() < 0.72) {
      this.placeOrder();
    }
    const movable = this.orders.filter((order) => NEXT_STATUS[order.status] !== null);
    if (movable.length > 0) {
      this.advance(movable[Math.floor(this.random() * movable.length)]);
    }
  }

  // --- domain --------------------------------------------------------

  /** Place a randomised order, decrementing stock all-or-nothing. */
  placeOrder(createdOffsetMs = 0): DemoOrder | null {
    const warehouse = WAREHOUSES[Math.floor(this.random() * WAREHOUSES.length)];
    const lineCount = 1 + Math.floor(this.random() * 4);
    const chosen = new Set<string>();
    const lines: DemoLine[] = [];

    for (let i = 0; i < lineCount; i += 1) {
      const product = PRODUCTS[Math.floor(this.random() * PRODUCTS.length)];
      if (chosen.has(product.sku)) {
        continue; // duplicate lines are merged upstream; skip rather than double
      }
      const quantity = 1 + Math.floor(this.random() * 3);
      const available = this.stock.get(stockKey(warehouse, product.sku)) ?? 0;
      if (available < quantity) {
        continue; // this line cannot be satisfied
      }
      chosen.add(product.sku);
      lines.push({
        sku: product.sku,
        product: product.product,
        quantity,
        unitPricePence: product.pricePence,
      });
    }
    if (lines.length === 0) {
      this.replenish(warehouse);
      return null;
    }

    for (const line of lines) {
      const key = stockKey(warehouse, line.sku);
      this.stock.set(key, (this.stock.get(key) ?? 0) - line.quantity);
    }

    this.counter += 1;
    const order: DemoOrder = {
      publicId: this.uuid(),
      status: "PENDING",
      warehouse,
      lines,
      totalPence: lines.reduce((sum, l) => sum + l.quantity * l.unitPricePence, 0),
      createdAt: new Date(Date.now() + createdOffsetMs).toISOString(),
    };
    this.orders.unshift(order);
    this.orders.splice(80);

    for (const line of lines) {
      // Keyed by warehouse as well as SKU: the real query ranks within each
      // warehouse with a RANK() window, so a global tally would show both
      // warehouses the same figures and give the game away immediately.
      const key = stockKey(warehouse, line.sku);
      const entry = this.unitsSold.get(key) ?? { units: 0, revenue: 0, orders: 0 };
      entry.units += line.quantity;
      entry.revenue += line.quantity * line.unitPricePence;
      entry.orders += 1;
      this.unitsSold.set(key, entry);
    }

    this.emitOrder(order, null);
    this.emitStock(warehouse, lines.map((l) => l.sku));
    this.replenish(warehouse);
    return order;
  }

  private advance(order: DemoOrder): void {
    const previous = order.status;
    // A small share of orders are cancelled instead of progressing, which is
    // what makes the restock path visible in the stock panel.
    const next =
      (previous === "PENDING" || previous === "CONFIRMED") && this.random() < 0.12
        ? "CANCELLED"
        : NEXT_STATUS[previous];
    if (next === null) {
      return;
    }
    order.status = next;

    if (next === "CANCELLED") {
      for (const line of order.lines) {
        const key = stockKey(order.warehouse, line.sku);
        this.stock.set(key, (this.stock.get(key) ?? 0) + line.quantity);
      }
      this.emitOrder(order, previous);
      this.emitStock(order.warehouse, order.lines.map((l) => l.sku));
      return;
    }
    this.emitOrder(order, previous);
  }

  /** Keep the demo from running dry without making stock look infinite. */
  private replenish(warehouse: string): void {
    const low = PRODUCTS.filter(
      (product) => (this.stock.get(stockKey(warehouse, product.sku)) ?? 0) <= 4,
    );
    if (low.length === 0) {
      return;
    }
    for (const product of low) {
      this.stock.set(stockKey(warehouse, product.sku), INITIAL_QUANTITY[product.sku]);
    }
    this.emitStock(warehouse, low.map((p) => p.sku));
  }

  private emitOrder(order: DemoOrder, previous: OrderStatus | null): void {
    this.emit({
      type: "order",
      order_id: order.publicId,
      status: order.status,
      previous,
      warehouse: order.warehouse,
      total_pence: order.totalPence,
      currency: "GBP",
      items_count: order.lines.length,
      created_at: order.createdAt,
    });
  }

  private emitStock(warehouse: string, skus: string[]): void {
    this.emit({
      type: "stock",
      warehouse,
      changes: skus.map((sku) => {
        const product = PRODUCTS.find((p) => p.sku === sku)!;
        return {
          sku,
          product: product.product,
          quantity: this.stock.get(stockKey(warehouse, sku)) ?? 0,
          bin: product.bin[warehouse],
        };
      }),
    });
  }

  private uuid(): string {
    const hex = "0123456789abcdef";
    let out = "";
    for (let i = 0; i < 32; i += 1) {
      out += hex[Math.floor(this.random() * 16)];
      if (i === 7 || i === 11 || i === 15 || i === 19) {
        out += "-";
      }
    }
    return out;
  }

  // --- the REST surface api.ts mirrors --------------------------------

  recentOrders(limit = 30): ApiOrder[] {
    return this.orders.slice(0, limit).map((order) => ({
      public_id: order.publicId,
      status: order.status,
      warehouse: order.warehouse,
      total_pence: order.totalPence,
      currency: "GBP",
      created_at: order.createdAt,
      updated_at: order.createdAt,
      items: order.lines.map((line) => ({
        sku: line.sku,
        name: line.product,
        quantity: line.quantity,
        unit_price_pence: line.unitPricePence,
        line_total_pence: line.quantity * line.unitPricePence,
      })),
    }));
  }

  stockRows(): ApiStockRow[] {
    const rows: ApiStockRow[] = [];
    for (const warehouse of WAREHOUSES) {
      for (const product of PRODUCTS) {
        rows.push({
          sku: product.sku,
          product: product.product,
          warehouse,
          quantity: this.stock.get(stockKey(warehouse, product.sku)) ?? 0,
          bin_x: product.bin[warehouse][0],
          bin_y: product.bin[warehouse][1],
          updated_at: new Date().toISOString(),
        });
      }
    }
    return rows;
  }

  topSellers(topN = 5): TopSellersResponse {
    const rows: TopSellerRow[] = [];
    for (const warehouse of WAREHOUSES) {
      const ranked = PRODUCTS.flatMap((product) => {
        const entry = this.unitsSold.get(stockKey(warehouse, product.sku));
        return entry === undefined
          ? []
          : [
              {
                warehouse,
                product: product.product,
                units_sold: entry.units,
                revenue_pence: entry.revenue,
                order_count: entry.orders,
                sales_rank: 0,
              },
            ];
      })
        .sort((a, b) => b.units_sold - a.units_sold || a.product.localeCompare(b.product))
        .slice(0, topN);
      ranked.forEach((row, index) => {
        row.sales_rank = index + 1;
      });
      rows.push(...ranked);
    }
    return {
      generated_at: new Date().toISOString(),
      window_hours: 24,
      top_n: topN,
      rows,
      cache_hit: false,
    };
  }

  pickPath(orderId: string): PickPathResponse {
    const order = this.orders.find((candidate) => candidate.publicId === orderId);
    if (!order) {
      throw new Error("unknown order");
    }
    const byBin = new Map<string, { point: Point; items: { sku: string; quantity: number }[] }>();
    for (const line of order.lines) {
      const point = PRODUCTS.find((p) => p.sku === line.sku)!.bin[order.warehouse];
      const key = `${point[0]},${point[1]}`;
      const entry = byBin.get(key) ?? { point, items: [] };
      entry.items.push({ sku: line.sku, quantity: line.quantity });
      byBin.set(key, entry);
    }
    // Sorted so the bin order fed to the solver is deterministic, exactly as
    // the Django view sorts before calling the engine.
    const bins = [...byBin.values()].sort(
      (a, b) => a.point[0] - b.point[0] || a.point[1] - b.point[1],
    );
    const started = performance.now();
    const result = optimiseRoute(bins.map((b) => b.point));
    const elapsed = performance.now() - started;

    return {
      order: orderId,
      warehouse: { code: order.warehouse, grid_width: GRID.width, grid_height: GRID.height },
      depot: [0, 0],
      engine: "typescript-replay",
      total_distance: result.totalDistance,
      computed_ms: Number(elapsed.toFixed(3)),
      stops: result.sequence.map((binIndex, position) => ({
        seq: position,
        x: bins[binIndex].point[0],
        y: bins[binIndex].point[1],
        items: bins[binIndex].items,
      })),
      unlocated_skus: [],
    };
  }
}

let instance: DemoEngine | null = null;

/** The single engine the replay build talks to.
 *
 * Constructed on first use rather than at import time, deliberately. A
 * module-level `new DemoEngine()` is a side effect, which stops Rollup
 * dropping this module from builds that never call it, and the result was
 * the simulator being shipped inside the real production image. With the
 * construction deferred, `IS_REPLAY` folds to false in a normal build and
 * the whole of src/demo falls out of the bundle.
 */
export function getDemoEngine(): DemoEngine {
  instance ??= new DemoEngine();
  return instance;
}
