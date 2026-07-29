import { API_BASE, IS_REPLAY } from "./config";
import { getDemoEngine } from "./demo/engine";
import type {
  ApiOrder,
  ApiStockRow,
  PickPathResponse,
  TopSellersResponse,
} from "./types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`GET ${path} -> ${response.status}`);
  }
  return (await response.json()) as T;
}

interface Paginated<T> {
  results: T[];
}

// Each function below returns the replay engine's answer in the Pages build
// and hits the real service everywhere else. Branching here rather than in
// the components is what lets every component stay unaware that the demo
// exists.

export async function fetchRecentOrders(limit = 30): Promise<ApiOrder[]> {
  if (IS_REPLAY) {
    return getDemoEngine().recentOrders(limit);
  }
  const page = await getJson<Paginated<ApiOrder>>(`/api/orders/?limit=${limit}`);
  return page.results;
}

export async function fetchStock(): Promise<ApiStockRow[]> {
  if (IS_REPLAY) {
    return getDemoEngine().stockRows();
  }
  const page = await getJson<Paginated<ApiStockRow>>("/api/stock/?limit=200");
  return page.results;
}

export function fetchTopSellers(): Promise<TopSellersResponse> {
  if (IS_REPLAY) {
    return Promise.resolve(getDemoEngine().topSellers());
  }
  return getJson<TopSellersResponse>("/api/analytics/top-sellers/");
}

export function fetchPickPath(orderId: string, engine?: string): Promise<PickPathResponse> {
  if (IS_REPLAY) {
    // The replay has one engine, so an explicit choice cannot be honoured.
    if (engine === "native") {
      return Promise.reject(new Error("native engine unavailable in the replay"));
    }
    return Promise.resolve(getDemoEngine().pickPath(orderId));
  }
  const suffix = engine ? `?engine=${engine}` : "";
  return getJson<PickPathResponse>(`/api/orders/${orderId}/pick-path/${suffix}`);
}

export async function placeDemoOrder(): Promise<void> {
  if (IS_REPLAY) {
    if (getDemoEngine().placeOrder() === null) {
      throw new Error("no sellable stock available");
    }
    return;
  }
  const response = await fetch(`${API_BASE}/api/demo/orders/`, { method: "POST" });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `demo order failed (${response.status})`);
  }
}
