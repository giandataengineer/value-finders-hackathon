-- SILVER · precios diarios (01_market_prices_raw): un dato limpio por (activo, día) y todo lo descartado a cuarentena.
-- Reglas: id de activo normalizado, fecha a ISO (MM/DD/YYYY confirmado por el orden del archivo), volumen sin sufijo K,
-- currency imputada desde la referencia, precio con punto decimal corrido corregido SOLO si el valor /100 cae dentro de [low, high].
CREATE OR REPLACE TABLE silver._market_daily_n AS
WITH n AS (
    SELECT _row_id,
           printf('VF_A%02d', TRY_CAST(NULLIF(regexp_extract(asset_id, '(\d+)$', 1), '') AS INTEGER)) AS asset_id,
           asset_id AS asset_id_original,
           COALESCE(try_strptime(date, '%Y-%m-%d'), try_strptime(date, '%m/%d/%Y'))::DATE AS day,
           date AS date_original, market, currency AS currency_original,
           TRY_CAST(open AS DOUBLE) AS o, TRY_CAST(high AS DOUBLE) AS h, TRY_CAST(low AS DOUBLE) AS l, TRY_CAST(close AS DOUBLE) AS c,
           CASE WHEN volume LIKE '%K' THEN TRY_CAST(replace(volume, 'K', '') AS DOUBLE) * 1000 ELSE TRY_CAST(volume AS DOUBLE) END AS volume
    FROM bronze.market_daily
), f AS (
    SELECT n.*, (c > 1000 AND c / 100 BETWEEN l AND h) AS precio_corregido FROM n
), g AS (
    SELECT f.*, CASE WHEN precio_corregido THEN c / 100 ELSE c END AS close_ok,
           row_number() OVER (PARTITION BY asset_id, day ORDER BY _row_id) AS rn
    FROM f
)
SELECT g.*, (a.asset_id IS NOT NULL) AS id_valido, a.currency AS currency_ref
FROM g LEFT JOIN silver.asset_reference a USING (asset_id);

CREATE OR REPLACE TABLE silver.market_daily AS
SELECT _row_id, asset_id, day, market, COALESCE(currency_original, currency_ref) AS currency,
       o AS open, h AS high, l AS low, close_ok AS close, CAST(volume AS BIGINT) AS volume,
       (asset_id_original <> asset_id) AS id_corregido, (date_original NOT LIKE '____-__-__') AS fecha_corregida,
       precio_corregido, (currency_original IS NULL) AS currency_imputada
FROM silver._market_daily_n
WHERE rn = 1 AND id_valido AND day IS NOT NULL AND close_ok > 0 AND close_ok <= 1000 AND l <= h;

INSERT INTO silver.cuarentena
SELECT 'market_daily', _row_id,
       CASE WHEN rn > 1 THEN 'duplicado (activo, día)' WHEN NOT id_valido THEN 'activo fuera de la referencia'
            WHEN day IS NULL THEN 'fecha no interpretable' ELSE 'precio inválido' END,
       asset_id || ' ' || CAST(day AS VARCHAR) || ' close=' || CAST(c AS VARCHAR)
FROM silver._market_daily_n
WHERE NOT (rn = 1 AND id_valido AND day IS NOT NULL AND close_ok > 0 AND close_ok <= 1000 AND l <= h);
