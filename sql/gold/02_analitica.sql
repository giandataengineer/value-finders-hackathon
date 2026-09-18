-- GOLD · tablas analíticas: retornos, riesgo por activo, correlaciones, señal de régimen, fundamentales y reacción a eventos.
CREATE OR REPLACE TABLE gold.retornos_diarios AS
WITH base AS (
    SELECT 'diario_12m' AS fuente, day, asset_id, close FROM gold.precios_diarios
    UNION ALL
    SELECT 'historial_intradia', day, asset_id, close FROM gold.precios_intradia_cierre WHERE tramo_confiable
)
SELECT fuente, day, asset_id, ln(close / lag(close) OVER (PARTITION BY fuente, asset_id ORDER BY day)) AS ret_log
FROM base QUALIFY ret_log IS NOT NULL ORDER BY fuente, asset_id, day;

CREATE OR REPLACE TABLE gold.estadisticas_activo AS
WITH pico AS (
    SELECT asset_id, close / max(close) OVER (PARTITION BY asset_id ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - 1 AS caida
    FROM gold.precios_diarios
), dd AS (SELECT asset_id, min(caida) AS caida_maxima_12m FROM pico GROUP BY asset_id),
r AS (SELECT asset_id, exp(sum(ret_log)) - 1 AS ret_12m, stddev_samp(ret_log) * sqrt(252) AS vol_anual_12m FROM gold.retornos_diarios WHERE fuente = 'diario_12m' GROUP BY asset_id),
h AS (SELECT asset_id, stddev_samp(ret_log) * sqrt(252) AS vol_anual_historial FROM gold.retornos_diarios WHERE fuente = 'historial_intradia' GROUP BY asset_id)
SELECT a.asset_id, a.name, a.country AS pais, a.sector, a.currency, r.ret_12m, r.vol_anual_12m, dd.caida_maxima_12m, h.vol_anual_historial
FROM gold.asset_reference a JOIN r USING (asset_id) JOIN dd USING (asset_id) JOIN h USING (asset_id) ORDER BY a.asset_id;

CREATE OR REPLACE TABLE gold.correlaciones AS
SELECT x.fuente, x.asset_id AS activo_a, y.asset_id AS activo_b, corr(x.ret_log, y.ret_log) AS correlacion
FROM gold.retornos_diarios x JOIN gold.retornos_diarios y ON x.fuente = y.fuente AND x.day = y.day AND x.asset_id < y.asset_id
GROUP BY x.fuente, x.asset_id, y.asset_id ORDER BY x.fuente, correlacion DESC;

-- La señal central: la correlación media entre activos cambia de 0.16 (último año) a 0.80 (historial 2020 a jul-2025).
CREATE OR REPLACE TABLE gold.senal_correlacion AS
SELECT c.fuente, round(avg(c.correlacion), 3) AS correlacion_media, count(*) AS pares,
       round(any_value(v.vol_media), 3) AS vol_anual_media
FROM gold.correlaciones c
JOIN (SELECT fuente, avg(stddev_samp_ret * sqrt(252)) AS vol_media FROM
        (SELECT fuente, asset_id, stddev_samp(ret_log) AS stddev_samp_ret FROM gold.retornos_diarios GROUP BY fuente, asset_id) GROUP BY fuente) v USING (fuente)
GROUP BY c.fuente;

CREATE OR REPLACE TABLE gold.fundamentales_ratios AS
SELECT issuer_id, period_end, revenue_usd_m, ebitda_usd_m / revenue_usd_m AS margen_ebitda, net_income_usd_m / revenue_usd_m AS margen_neto,
       debt_usd_m / (4 * ebitda_usd_m) AS deuda_sobre_ebitda_anualizada, debt_usd_m - cash_usd_m AS deuda_neta_usd_m,
       revenue_usd_m / lag(revenue_usd_m, 4) OVER (PARTITION BY issuer_id ORDER BY period_end) - 1 AS crecimiento_interanual
FROM gold.fundamentales ORDER BY issuer_id, period_end;

-- Reacción de cada activo en los 3 días desde cada evento, medida en desviaciones típicas de su propio movimiento de 3 días.
CREATE OR REPLACE TABLE gold.eventos_reaccion AS
WITH s3 AS (
    SELECT asset_id, day, sum(ret_log) OVER w AS ret_3d, count(*) OVER w AS n
    FROM gold.retornos_diarios WHERE fuente = 'diario_12m'
    WINDOW w AS (PARTITION BY asset_id ORDER BY day ROWS BETWEEN CURRENT ROW AND 2 FOLLOWING)
), sd AS (SELECT asset_id, stddev_samp(ret_3d) AS sd3 FROM s3 WHERE n = 3 GROUP BY asset_id),
ea AS (
    SELECT e.event_date, e.scope, e.event_type, e.severity, a.asset_id
    FROM gold.events e JOIN gold.asset_reference a ON (e.scope_tipo = 'activo' AND a.asset_id = e.scope) OR (e.scope_tipo = 'sector' AND a.sector = e.scope)
)
SELECT ea.event_date, ea.scope, ea.event_type, ea.severity, ea.asset_id, s.day AS primer_dia_habil, s.ret_3d, s.ret_3d / sd.sd3 AS z_3d
FROM ea JOIN LATERAL (SELECT * FROM s3 WHERE s3.asset_id = ea.asset_id AND s3.day >= ea.event_date AND s3.n = 3 ORDER BY s3.day LIMIT 1) s ON true
JOIN sd ON sd.asset_id = ea.asset_id ORDER BY ea.event_date;
