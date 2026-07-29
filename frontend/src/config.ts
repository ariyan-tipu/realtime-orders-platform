/** In dev, Vite env vars point at the two services directly; in production
 * they are left empty and everything is same-origin behind nginx. */
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";

/** The GitHub Pages build sets this: no backend exists, so the dashboard
 * runs against an in-browser replay instead of the REST and WebSocket
 * services. Every other build leaves it unset and talks to the real stack. */
export const IS_REPLAY = import.meta.env.VITE_REPLAY === "1";

export function wsUrl(path: string): string {
  const base = import.meta.env.VITE_WS_BASE;
  if (base) {
    return `${base}${path}`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}

export function formatMoney(pence: number, currency = "GBP"): string {
  return new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(pence / 100);
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", { hour12: false });
}
