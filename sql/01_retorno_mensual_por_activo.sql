-- Retorno mensual por activo: cierre del último día hábil de cada mes contra el del mes anterior.
WITH mensual AS (
    SELECT asset_id, date_trunc('month', fecha) AS mes, arg_max(close, fecha) AS cierre
    FROM precios
    GROUP BY asset_id, date_trunc('month', fecha)
)
SELECT asset_id, mes, cierre,
       cierre / LAG(cierre) OVER (PARTITION BY asset_id ORDER BY mes) - 1 AS retorno_mensual
FROM mensual
ORDER BY asset_id, mes;
