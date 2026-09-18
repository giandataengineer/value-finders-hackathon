-- Caída máxima de cada activo en los últimos 12 meses, con funciones de ventana (máximo acumulado hasta cada día).
WITH pico AS (
    SELECT asset_id, fecha, close,
           MAX(close) OVER (PARTITION BY asset_id ORDER BY fecha ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS maximo_previo
    FROM precios
), caida AS (
    SELECT asset_id, fecha, close / maximo_previo - 1 AS caida FROM pico
)
SELECT c.asset_id, a.country AS pais, a.sector, MIN(c.caida) AS caida_maxima, arg_min(c.fecha, c.caida) AS fecha_del_minimo
FROM caida c
JOIN activos a USING (asset_id)
GROUP BY c.asset_id, a.country, a.sector
ORDER BY caida_maxima;
