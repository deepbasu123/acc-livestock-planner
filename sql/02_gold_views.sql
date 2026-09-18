-- ============================================================================
-- ACC Livestock Planner - GOLD layer
-- Unified, analytics-ready views over the booking model. Consumed by the
-- AI/BI dashboard, the Genie space and the app.
-- ============================================================================

-- THE expanded booking view: resolves every FK to a name, excludes
-- soft-deleted rows, extracts a numeric price where the free-text
-- price_per_kg field parses (it does not always - that is by design).
CREATE OR REPLACE VIEW project_command_centre.acc_gold.booking_expanded AS
SELECT
  b.id, b.property, f.feedlot_name, f.total_capacity_head, b.status,
  b.week_number, b.week_commencing, b.head_count, b.delivery_day,
  b.agent_id, ag.name AS agent_name,
  b.vendor_id, v.name AS vendor_name,
  b.payee_id, p.name AS payee_name,
  b.grid_text, b.program, b.price_per_kg,
  TRY_CAST(regexp_extract(b.price_per_kg, '([0-9]+\\.?[0-9]*)', 1) AS DOUBLE) AS price_per_kg_numeric,
  b.price_variation,
  b.weigh_point_id, wp.name AS weigh_point_name,
  b.origin_id, o.name AS origin_name,
  b.buyer_id, by.name AS buyer_name,
  b.buyer_payee_details, b.notes,
  b.created_by, b.created_by_email, b.created_at,
  b.modified_by, b.modified_by_email, b.updated_at, b.deleted_at
FROM project_command_centre.acc_booking.cattle_bookings b
LEFT JOIN project_command_centre.acc_feedlot.feedlots f ON b.property = f.property
LEFT JOIN project_command_centre.acc_counterparty.agents ag ON b.agent_id = ag.id
LEFT JOIN project_command_centre.acc_counterparty.vendors v ON b.vendor_id = v.id
LEFT JOIN project_command_centre.acc_counterparty.payees p ON b.payee_id = p.id
LEFT JOIN project_command_centre.acc_reference.weigh_points wp ON b.weigh_point_id = wp.id
LEFT JOIN project_command_centre.acc_reference.origins o ON b.origin_id = o.id
LEFT JOIN project_command_centre.acc_counterparty.buyers by ON b.buyer_id = by.id
WHERE b.deleted_at IS NULL;

-- Weekly booked head per feedlot (actuals through today, forward bookings
-- beyond it), for the Capacity Forecast tab. Cancelled bookings excluded.
CREATE OR REPLACE VIEW project_command_centre.acc_gold.feedlot_weekly_bookings AS
SELECT property, feedlot_name, total_capacity_head,
  week_commencing AS week_start,
  SUM(head_count) AS head_booked,
  COUNT(*) AS bookings_count
FROM project_command_centre.acc_gold.booking_expanded
WHERE status <> 'Cancelled' AND week_commencing IS NOT NULL
GROUP BY property, feedlot_name, total_capacity_head, week_commencing;

-- Estimated on-feed inventory: trailing 14-week rolling sum of booked head
-- against total pen capacity (an estimate - the real app does not track
-- receival/turnoff, only bookings).
CREATE OR REPLACE VIEW project_command_centre.acc_gold.feedlot_capacity_weekly AS
SELECT *,
  SUM(head_booked) OVER (PARTITION BY property ORDER BY week_start
      ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS head_on_feed_est,
  ROUND(100.0 * SUM(head_booked) OVER (PARTITION BY property ORDER BY week_start
      ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) / NULLIF(total_capacity_head, 0), 1) AS utilization_pct
FROM project_command_centre.acc_gold.feedlot_weekly_bookings;

-- Vendor scorecard - booking volume + cancellation rate + avg parsed price.
CREATE OR REPLACE VIEW project_command_centre.acc_gold.vendor_scorecard AS
SELECT
  v.id AS vendor_id, v.name AS vendor_name, v.active,
  COUNT(b.id) AS total_bookings,
  SUM(CASE WHEN b.status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_bookings,
  ROUND(100.0 * SUM(CASE WHEN b.status = 'Cancelled' THEN 1 ELSE 0 END) / NULLIF(COUNT(b.id), 0), 1) AS cancellation_rate_pct,
  SUM(CASE WHEN b.status <> 'Cancelled' THEN b.head_count ELSE 0 END) AS total_head_booked,
  ROUND(AVG(b.price_per_kg_numeric), 2) AS avg_price_per_kg
FROM project_command_centre.acc_counterparty.vendors v
LEFT JOIN project_command_centre.acc_gold.booking_expanded b ON v.id = b.vendor_id
GROUP BY v.id, v.name, v.active;

-- Agent performance - booking volume handled per agent.
CREATE OR REPLACE VIEW project_command_centre.acc_gold.agent_performance AS
SELECT
  ag.id AS agent_id, ag.name AS agent_name, ag.active,
  COUNT(b.id) AS total_bookings,
  SUM(CASE WHEN b.status <> 'Cancelled' THEN b.head_count ELSE 0 END) AS total_head_booked,
  COUNT(DISTINCT b.vendor_id) AS distinct_vendors
FROM project_command_centre.acc_counterparty.agents ag
LEFT JOIN project_command_centre.acc_gold.booking_expanded b ON ag.id = b.agent_id
GROUP BY ag.id, ag.name, ag.active;

-- Weekly average price trend (parsed numeric) by feedlot, for the market view.
CREATE OR REPLACE VIEW project_command_centre.acc_gold.price_trend_weekly AS
SELECT property, feedlot_name, week_commencing AS week_start,
  ROUND(AVG(price_per_kg_numeric), 2) AS avg_price_per_kg
FROM project_command_centre.acc_gold.booking_expanded
WHERE price_per_kg_numeric IS NOT NULL AND week_commencing IS NOT NULL
GROUP BY property, feedlot_name, week_commencing;
