-- Top-selling products per warehouse over a time window.
-- Parameters (positional): [0] window start timestamp, [1] top-N cutoff.
--
-- Index support: order_active_created_idx, a partial index on
-- orders_order(created_at) WHERE status <> 'CANCELLED', INCLUDE (warehouse_id, id),
-- lets the planner serve the time/status filter, the warehouse grouping key
-- and the join key without touching the orders heap. See
-- docs/query-optimisation.md for the measured EXPLAIN ANALYZE plans.
WITH per_product AS (
    SELECT
        o.warehouse_id,
        v.product_id,
        SUM(oi.quantity)                       AS units_sold,
        SUM(oi.quantity * oi.unit_price_pence) AS revenue_pence,
        COUNT(DISTINCT o.id)                   AS order_count
    FROM orders_orderitem oi
    JOIN orders_order o           ON o.id = oi.order_id
    JOIN catalog_productvariant v ON v.id = oi.variant_id
    WHERE o.created_at >= %s
      AND o.status <> 'CANCELLED'
    GROUP BY o.warehouse_id, v.product_id
),
ranked AS (
    SELECT
        per_product.*,
        RANK() OVER (
            PARTITION BY warehouse_id
            ORDER BY units_sold DESC, revenue_pence DESC, product_id
        ) AS sales_rank
    FROM per_product
)
SELECT
    w.code          AS warehouse,
    p.name          AS product,
    r.units_sold,
    r.revenue_pence,
    r.order_count,
    r.sales_rank
FROM ranked r
JOIN inventory_warehouse w ON w.id = r.warehouse_id
JOIN catalog_product p     ON p.id = r.product_id
WHERE r.sales_rank <= %s
ORDER BY w.code, r.sales_rank, p.name;
