-- SILVER · macro, fundamentales y eventos tipados y conformados.
CREATE OR REPLACE TABLE silver.macro AS
SELECT _row_id, CAST(date AS DATE) AS date,
       CAST(us_10y_yield AS DOUBLE) AS us_10y_yield,
       TRY_CAST(us_inflation_yoy AS DOUBLE) AS us_inflation_yoy,
       last_value(TRY_CAST(us_inflation_yoy AS DOUBLE) IGNORE NULLS) OVER (ORDER BY CAST(date AS DATE) ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS us_inflation_yoy_ffill,
       CAST(usd_cop AS DOUBLE) AS usd_cop, CAST(usd_pen AS DOUBLE) AS usd_pen, CAST(usd_mxn AS DOUBLE) AS usd_mxn, CAST(usd_clp AS DOUBLE) AS usd_clp,
       CAST(market_factor AS DOUBLE) AS market_factor, risk_regime
FROM bronze.macro
WHERE risk_regime IN ('Normal', 'Stress', 'Recovery');

INSERT INTO silver.cuarentena
SELECT 'macro', _row_id, 'régimen fuera del dominio (Normal, Stress, Recovery)', date FROM bronze.macro
WHERE risk_regime NOT IN ('Normal', 'Stress', 'Recovery') OR risk_regime IS NULL;

-- Fundamentales: emisor normalizado (ISS04 a ISS_04), miles con coma y trimestres con etiqueta 'Qn-AAAA'.
-- Una etiqueta de trimestre puede engañar: 'Q4-2024' de ISS_02 choca con el 2024-12-31 que ya existe y su posición en el archivo
-- (entre 2025-03-31 y 2025-09-30) y sus cifras corresponden al trimestre que falta, 2025-06-30. Si la fecha de la etiqueta choca con
-- un trimestre existente del mismo emisor, la fila se reasigna al trimestre siguiente al de la fila anterior; si no choca, se usa la etiqueta.
CREATE OR REPLACE TABLE silver._fund_n AS
WITH b AS (
    SELECT _row_id, issuer_id AS issuer_original, period_end AS period_original,
           printf('ISS_%02d', TRY_CAST(NULLIF(regexp_extract(issuer_id, '(\d+)$', 1), '') AS INTEGER)) AS issuer_id,
           CASE WHEN NOT regexp_matches(period_end, '^Q[1-4]-\d{4}$') THEN TRY_CAST(period_end AS DATE) END AS fecha_iso,
           CASE WHEN regexp_matches(period_end, '^Q[1-4]-\d{4}$')
                THEN last_day(make_date(CAST(right(period_end, 4) AS INTEGER), CAST(substr(period_end, 2, 1) AS INTEGER) * 3, 1)) END AS fecha_etiqueta,
           revenue_usd_m AS revenue_original,
           TRY_CAST(replace(revenue_usd_m, ',', '') AS DOUBLE) AS revenue_usd_m,
           TRY_CAST(ebitda_usd_m AS DOUBLE) AS ebitda_usd_m, TRY_CAST(net_income_usd_m AS DOUBLE) AS net_income_usd_m,
           TRY_CAST(debt_usd_m AS DOUBLE) AS debt_usd_m, TRY_CAST(cash_usd_m AS DOUBLE) AS cash_usd_m
    FROM bronze.fundamentals
), c AS (
    SELECT b.*, lag(fecha_iso) OVER (PARTITION BY issuer_id ORDER BY _row_id) AS fecha_fila_anterior,
           (fecha_etiqueta IS NOT NULL AND EXISTS (SELECT 1 FROM b b2 WHERE b2.issuer_id = b.issuer_id AND b2.fecha_iso = b.fecha_etiqueta)) AS etiqueta_choca
    FROM b
)
SELECT _row_id, issuer_original, period_original, issuer_id,
       CASE WHEN fecha_etiqueta IS NULL THEN fecha_iso
            WHEN etiqueta_choca THEN last_day(fecha_fila_anterior + INTERVAL 3 MONTH)
            ELSE fecha_etiqueta END AS period_end,
       (fecha_etiqueta IS NOT NULL) AS periodo_desde_etiqueta, etiqueta_choca AS periodo_reasignado,
       revenue_original, revenue_usd_m, ebitda_usd_m, net_income_usd_m, debt_usd_m, cash_usd_m
FROM c;

CREATE OR REPLACE TABLE silver.fundamentals AS
SELECT * EXCLUDE (issuer_original, period_original, revenue_original, periodo_desde_etiqueta, periodo_reasignado, rn) FROM (
    SELECT *, row_number() OVER (PARTITION BY issuer_id, period_end ORDER BY _row_id) AS rn FROM silver._fund_n
) WHERE rn = 1;

INSERT INTO silver.cuarentena
SELECT 'fundamentals', _row_id, 'duplicado (emisor, periodo)', issuer_id || ' ' || CAST(period_end AS VARCHAR)
FROM (SELECT *, row_number() OVER (PARTITION BY issuer_id, period_end ORDER BY _row_id) AS rn FROM silver._fund_n) WHERE rn > 1;

-- Eventos: se resuelve si el alcance es un activo o un sector.
CREATE OR REPLACE TABLE silver.events AS
SELECT e._row_id, CAST(e.event_date AS DATE) AS event_date, e.scope, e.event_type, e.headline, e.severity,
       CASE WHEN e.scope IN (SELECT asset_id FROM silver.asset_reference) THEN 'activo'
            WHEN e.scope IN (SELECT DISTINCT sector FROM silver.asset_reference) THEN 'sector' ELSE 'desconocido' END AS scope_tipo
FROM bronze.events e;
