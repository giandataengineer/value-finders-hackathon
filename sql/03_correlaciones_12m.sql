-- Correlación de retornos diarios entre cada par de activos (últimos 12 meses alineados con macro y eventos).
WITH r AS (
    SELECT asset_id, fecha, close / LAG(close) OVER (PARTITION BY asset_id ORDER BY fecha) - 1 AS ret
    FROM precios
)
SELECT x.asset_id AS activo_a, y.asset_id AS activo_b, corr(x.ret, y.ret) AS correlacion
FROM r x
JOIN r y ON x.fecha = y.fecha AND x.asset_id < y.asset_id
WHERE x.ret IS NOT NULL AND y.ret IS NOT NULL
GROUP BY x.asset_id, y.asset_id
ORDER BY correlacion DESC;
