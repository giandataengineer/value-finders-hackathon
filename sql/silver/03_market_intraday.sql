-- SILVER · precios intradía (01_market_prices_raw_expanded, barras de 10 minutos 2020 a 2026): mismas reglas que el diario.
-- El close nulo se descarta a cuarentena ANTES de buscar duplicados, para que cada duplicado se cuente una sola vez.
CREATE OR REPLACE TABLE silver._market_intraday_n AS
WITH n AS (
    SELECT _row_id,
           printf('VF_A%02d', TRY_CAST(NULLIF(regexp_extract(asset_id, '(\d+)$', 1), '') AS INTEGER)) AS asset_id,
           asset_id AS asset_id_original,
           COALESCE(try_strptime(date, '%Y-%m-%d %H:%M:%S'), try_strptime(date, '%m/%d/%Y %H:%M:%S')) AS ts,
           date AS date_original, market, currency AS currency_original,
           TRY_CAST(open AS DOUBLE) AS o, TRY_CAST(high AS DOUBLE) AS h, TRY_CAST(low AS DOUBLE) AS l, TRY_CAST(close AS DOUBLE) AS c,
           CASE WHEN volume LIKE '%K' THEN TRY_CAST(replace(volume, 'K', '') AS DOUBLE) * 1000 ELSE TRY_CAST(volume AS DOUBLE) END AS volume
    FROM bronze.market_intraday
), f AS (
    SELECT n.*, (c > 1000 AND c / 100 BETWEEN l AND h) AS precio_corregido FROM n
)
SELECT f.*, CASE WHEN precio_corregido THEN c / 100 ELSE c END AS close_ok,
       CASE WHEN c IS NOT NULL THEN row_number() OVER (PARTITION BY asset_id, ts, (c IS NOT NULL) ORDER BY f._row_id) END AS rn,
       (a.asset_id IS NOT NULL) AS id_valido, a.currency AS currency_ref
FROM f LEFT JOIN silver.asset_reference a USING (asset_id);

CREATE OR REPLACE TABLE silver.market_intraday AS
SELECT _row_id, asset_id, ts, CAST(ts AS DATE) AS day, market, COALESCE(currency_original, currency_ref) AS currency,
       o AS open, h AS high, l AS low, close_ok AS close, CAST(volume AS BIGINT) AS volume,
       (asset_id_original <> asset_id) AS id_corregido, (date_original NOT LIKE '____-__-__ %') AS fecha_corregida,
       precio_corregido, (currency_original IS NULL) AS currency_imputada
FROM silver._market_intraday_n
WHERE c IS NOT NULL AND rn = 1 AND id_valido AND ts IS NOT NULL AND close_ok > 0 AND close_ok <= 1000 AND l <= h;

INSERT INTO silver.cuarentena
SELECT 'market_intraday', _row_id,
       CASE WHEN c IS NULL THEN 'close nulo' WHEN rn > 1 THEN 'duplicado (activo, timestamp)' WHEN NOT id_valido THEN 'activo fuera de la referencia'
            WHEN ts IS NULL THEN 'fecha no interpretable' ELSE 'precio inválido' END,
       asset_id || ' ' || COALESCE(CAST(ts AS VARCHAR), date_original)
FROM silver._market_intraday_n
WHERE NOT (c IS NOT NULL AND rn = 1 AND id_valido AND ts IS NOT NULL AND close_ok > 0 AND close_ok <= 1000 AND l <= h);
