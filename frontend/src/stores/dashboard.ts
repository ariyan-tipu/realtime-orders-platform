import { defineStore } from "pinia";

import type {
  ApiOrder,
  ApiStockRow,
  OrderRow,
  StockRow,
  TopSellerRow,
  WsEvent,
} from "../types";

export type ConnectionState = "connecting" | "online" | "offline";

const MAX_ORDER_ROWS = 40;

function stockKey(warehouse: string, sku: string): string {
  return `${warehouse}::${sku}`;
}

export const useDashboardStore = defineStore("dashboard", {
  state: () => ({
    connection: "connecting" as ConnectionState,
    orders: [] as OrderRow[],
    stock: {} as Record<string, StockRow>,
    topSellers: [] as TopSellerRow[],
    topSellersGeneratedAt: "",
    eventsSeen: 0,
    selectedOrderId: "" as string,
  }),

  getters: {
    stockRows(state): StockRow[] {
      return Object.values(state.stock).sort(
        (a, b) => a.warehouse.localeCompare(b.warehouse) || a.sku.localeCompare(b.sku),
      );
    },
    warehouses(state): string[] {
      return [...new Set(Object.values(state.stock).map((row) => row.warehouse))].sort();
    },
    maxStockQuantity(state): number {
      return Math.max(1, ...Object.values(state.stock).map((row) => row.quantity));
    },
  },

  actions: {
    setConnection(connectionState: ConnectionState) {
      this.connection = connectionState;
    },

    selectOrder(orderId: string) {
      this.selectedOrderId = orderId;
    },

    hydrateOrders(apiOrders: ApiOrder[]) {
      this.orders = apiOrders.slice(0, MAX_ORDER_ROWS).map((order) => ({
        orderId: order.public_id,
        status: order.status,
        warehouse: order.warehouse,
        totalPence: order.total_pence,
        itemsCount: order.items.length,
        createdAt: order.created_at,
        version: 0,
      }));
      if (!this.selectedOrderId && this.orders.length > 0) {
        this.selectedOrderId = this.orders[0].orderId;
      }
    },

    hydrateStock(apiRows: ApiStockRow[]) {
      this.stock = Object.fromEntries(
        apiRows.map((row) => [
          stockKey(row.warehouse, row.sku),
          {
            sku: row.sku,
            product: row.product,
            warehouse: row.warehouse,
            quantity: row.quantity,
            version: 0,
          },
        ]),
      );
    },

    setTopSellers(rows: TopSellerRow[], generatedAt: string) {
      this.topSellers = rows;
      this.topSellersGeneratedAt = generatedAt;
    },

    applyEvent(event: WsEvent) {
      if (event.type === "order") {
        this.eventsSeen += 1;
        const existing = this.orders.find((row) => row.orderId === event.order_id);
        if (existing) {
          existing.status = event.status;
          existing.version += 1;
        } else {
          this.orders.unshift({
            orderId: event.order_id,
            status: event.status,
            warehouse: event.warehouse,
            totalPence: event.total_pence,
            itemsCount: event.items_count,
            createdAt: event.created_at,
            version: 1,
          });
          this.orders.splice(MAX_ORDER_ROWS);
          if (!this.selectedOrderId) {
            this.selectedOrderId = event.order_id;
          }
        }
      } else if (event.type === "stock") {
        this.eventsSeen += 1;
        for (const change of event.changes) {
          const key = stockKey(event.warehouse, change.sku);
          const existing = this.stock[key];
          if (existing) {
            existing.quantity = change.quantity;
            existing.version += 1;
          } else {
            this.stock[key] = {
              sku: change.sku,
              product: change.product,
              warehouse: event.warehouse,
              quantity: change.quantity,
              version: 1,
            };
          }
        }
      }
      // hello/heartbeat frames carry no dashboard state
    },
  },
});
