-- ============================================================
-- Sample queries for the te-lake Gold views.
-- Run these from the Athena console with workgroup
--   te-lake-<uid>-analytics-wg selected (see `terraform output athena_workgroup`).
-- ============================================================

-- ---------- Smoke tests (verify each layer is alive) ----------

-- 1. Silver row count (should match producer output within 1%)
SELECT count(*) AS silver_rows
FROM te_lake_silver.instantaneous_measurements;

-- 2. Latest record per device
SELECT device_id, max(measured_at) AS last_seen
FROM te_lake_silver.instantaneous_measurements
GROUP BY device_id
ORDER BY device_id;

-- 3. Iceberg snapshot inspection (Iceberg metadata table)
SELECT committed_at, snapshot_id, operation, summary
FROM te_lake_silver."instantaneous_measurements$snapshots"
ORDER BY committed_at DESC
LIMIT 10;


-- ---------- Gold view: G1 — hourly energy per device ----------

SELECT *
FROM te_lake_gold.v_hourly_energy
WHERE measured_date = current_date
ORDER BY device_id, hour_of_day
LIMIT 100;

-- Which device consumed the most yesterday?
SELECT device_id, sum(kwh) AS kwh_total
FROM te_lake_gold.v_hourly_energy
WHERE measured_date = date_add('day', -1, current_date)
GROUP BY device_id
ORDER BY kwh_total DESC;


-- ---------- Gold view: G2 — daily device summary ----------

SELECT *
FROM te_lake_gold.v_daily_device_summary
ORDER BY measured_date DESC, device_id
LIMIT 50;

-- Voltage out-of-spec days (ANSI ±5% on a 220 V nominal device)
SELECT device_id, measured_date, min_voltage, max_voltage
FROM te_lake_gold.v_daily_device_summary
WHERE min_voltage < 209 OR max_voltage > 231
ORDER BY measured_date DESC;


-- ---------- Gold view: G3 — fleet daily rollup ----------

SELECT *
FROM te_lake_gold.v_fleet_daily_rollup
ORDER BY measured_date DESC;

-- 7-day fleet trend
SELECT measured_date, fleet_total_kwh, fleet_peak_power_w
FROM te_lake_gold.v_fleet_daily_rollup
WHERE measured_date >= date_add('day', -7, current_date)
ORDER BY measured_date;
