-- GOLD · tablas del contrato de datos (mismos nombres y columnas que espera el motor y el conector de Databricks).
CREATE OR REPLACE TABLE gold.asset_reference AS
SELECT asset_id, issuer_id, name, sector, country, market, currency FROM silver.asset_reference ORDER BY asset_id;

CREATE OR REPLACE TABLE gold.client_profiles AS
SELECT client_id, profile_name, base_currency, horizon_months, risk_tolerance, max_drawdown_tolerance_pct, liquidity_need, priority, "constraint"
FROM silver.client_profiles ORDER BY client_id;

-- Los precios diarios se acotan a las fechas con macro (el archivo diario y el macro cubren el mismo periodo).
CREATE OR REPLACE TABLE gold.precios_diarios AS
SELECT day, asset_id, close, open, high, low, volume, currency
FROM silver.market_daily
WHERE day BETWEEN (SELECT min(date) FROM silver.macro) AND (SELECT max(date) FROM silver.macro)
ORDER BY asset_id, day;

-- Cierre diario del intradía. El tramo desde el primer día del archivo diario contradice al diario y al macro: se conserva
-- pero queda marcado como no confiable; el motor solo usa el tramo confiable (historial para el escenario de estrés).
CREATE OR REPLACE TABLE gold.precios_intradia_cierre AS
SELECT day, asset_id, arg_max(close, ts) AS close,
       day < (SELECT min(day) FROM silver.market_daily) AS tramo_confiable
FROM silver.market_intraday
GROUP BY day, asset_id
ORDER BY asset_id, day;

CREATE OR REPLACE TABLE gold.macro AS SELECT * EXCLUDE (_row_id) FROM silver.macro ORDER BY date;

CREATE OR REPLACE TABLE gold.fundamentales AS
SELECT issuer_id, period_end, revenue_usd_m, ebitda_usd_m, net_income_usd_m, debt_usd_m, cash_usd_m
FROM silver.fundamentals ORDER BY issuer_id, period_end;

CREATE OR REPLACE TABLE gold.events AS
SELECT event_date, scope, event_type, headline, severity, scope_tipo FROM silver.events ORDER BY event_date;

-- Restricciones del cliente en columnas numéricas (el texto libre de 'constraint' se interpreta una sola vez, aquí).
CREATE OR REPLACE TABLE gold.restricciones_cliente AS
SELECT client_id,
       CASE base_currency WHEN 'COP' THEN 'usd_cop' WHEN 'PEN' THEN 'usd_pen' END AS fx_col,
       TRY_CAST(NULLIF(regexp_extract("constraint", 'Máx\. (\d+)% en un solo sector', 1), '') AS DOUBLE) / 100 AS tope_por_sector,
       TRY_CAST(NULLIF(regexp_extract("constraint", 'Máx\. (\d+)% en activos de alta volatilidad', 1), '') AS DOUBLE) / 100 AS tope_alta_volatilidad,
       TRY_CAST(NULLIF(regexp_extract("constraint", 'Al menos (\d+) países', 1), '') AS INTEGER) AS min_paises,
       TRY_CAST(NULLIF(regexp_extract("constraint", '(\d+) sectores', 1), '') AS INTEGER) AS min_sectores,
       max_drawdown_tolerance_pct / 100.0 AS tolerancia_caida,
       CASE risk_tolerance WHEN 'Alta' THEN 0.25 WHEN 'Media' THEN 0.20 WHEN 'Media-Baja' THEN 0.15 END AS presupuesto_riesgo_supuesto
FROM silver.client_profiles ORDER BY client_id;
