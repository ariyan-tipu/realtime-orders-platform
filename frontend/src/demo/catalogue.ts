/** Seed data for the browser-only replay build.
 *
 * These are the same shapes the Django service returns, filled with the same
 * kind of catalogue `manage.py seed_data` creates. Nothing here is fetched,
 * so the published demo has no backend to be down.
 */

export interface DemoProduct {
  sku: string;
  product: string;
  pricePence: number;
  /** Bin coordinates per warehouse, as the Stock rows carry them. */
  bin: Record<string, [number, number]>;
}

export const WAREHOUSES = ["LDN", "MAN"] as const;

export const GRID = { width: 40, height: 15 } as const;

export const PRODUCTS: DemoProduct[] = [
  { sku: "MUG-01", product: "Enamel Mug", pricePence: 799, bin: { LDN: [3, 2], MAN: [6, 4] } },
  { sku: "BAG-01", product: "Canvas Tote", pricePence: 4500, bin: { LDN: [8, 1], MAN: [11, 9] } },
  { sku: "TEE-01", product: "Cotton T-Shirt", pricePence: 1899, bin: { LDN: [14, 7], MAN: [3, 12] } },
  { sku: "CAP-01", product: "Wool Cap", pricePence: 2250, bin: { LDN: [21, 3], MAN: [17, 2] } },
  { sku: "BTL-01", product: "Steel Bottle", pricePence: 1650, bin: { LDN: [27, 11], MAN: [24, 6] } },
  { sku: "NTB-01", product: "Pocket Notebook", pricePence: 650, bin: { LDN: [33, 5], MAN: [29, 13] } },
  { sku: "SCK-01", product: "Merino Socks", pricePence: 1200, bin: { LDN: [36, 13], MAN: [35, 8] } },
  { sku: "PEN-01", product: "Rollerball Pen", pricePence: 950, bin: { LDN: [18, 12], MAN: [8, 1] } },
];

export const INITIAL_QUANTITY: Record<string, number> = {
  "MUG-01": 64,
  "BAG-01": 22,
  "TEE-01": 48,
  "CAP-01": 31,
  "BTL-01": 40,
  "NTB-01": 75,
  "SCK-01": 27,
  "PEN-01": 58,
};

/** Small, fast, seedable PRNG so the replay is reproducible and testable. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
