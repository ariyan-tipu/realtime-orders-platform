export type OrderStatus =
  | "PENDING"
  | "CONFIRMED"
  | "PICKING"
  | "PACKED"
  | "SHIPPED"
  | "DELIVERED"
  | "CANCELLED";

// --- WebSocket events (shapes defined by orders/events.py in the core service)

export interface OrderEvent {
  type: "order";
  order_id: string;
  status: OrderStatus;
  previous: OrderStatus | null;
  warehouse: string;
  total_pence: number;
  currency: string;
  items_count: number;
  created_at: string;
}

export interface StockChange {
  sku: string;
  product: string;
  quantity: number;
  bin: [number, number];
}

export interface StockEvent {
  type: "stock";
  warehouse: string;
  changes: StockChange[];
}

export interface HelloEvent {
  type: "hello";
  filter: string | null;
  server_time: string;
}

export interface HeartbeatEvent {
  type: "heartbeat";
}

export type WsEvent = OrderEvent | StockEvent | HelloEvent | HeartbeatEvent;

// --- REST API payloads (snapshot; the socket then applies deltas)

export interface ApiOrderItem {
  sku: string;
  name: string;
  quantity: number;
  unit_price_pence: number;
  line_total_pence: number;
}

export interface ApiOrder {
  public_id: string;
  status: OrderStatus;
  warehouse: string;
  total_pence: number;
  currency: string;
  created_at: string;
  updated_at: string;
  items: ApiOrderItem[];
}

export interface ApiStockRow {
  sku: string;
  product: string;
  warehouse: string;
  quantity: number;
  bin_x: number;
  bin_y: number;
  updated_at: string;
}

export interface TopSellerRow {
  warehouse: string;
  product: string;
  units_sold: number;
  revenue_pence: number;
  order_count: number;
  sales_rank: number;
}

export interface TopSellersResponse {
  generated_at: string;
  window_hours: number;
  top_n: number;
  rows: TopSellerRow[];
  cache_hit: boolean;
}

export interface PickPathStop {
  seq: number;
  x: number;
  y: number;
  items: { sku: string; quantity: number }[];
}

export interface PickPathResponse {
  order: string;
  warehouse: { code: string; grid_width: number; grid_height: number };
  depot: [number, number];
  engine: string;
  total_distance: number;
  computed_ms: number;
  stops: PickPathStop[];
  unlocated_skus: string[];
}

// --- Dashboard view models

export interface OrderRow {
  orderId: string;
  status: OrderStatus;
  warehouse: string;
  totalPence: number;
  itemsCount: number;
  createdAt: string;
  /** Bumped on every update so the UI can replay its flash animation. */
  version: number;
}

export interface StockRow {
  sku: string;
  product: string;
  warehouse: string;
  quantity: number;
  version: number;
}
