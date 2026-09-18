-- GOLD · giros de la trama listos para el motor: a qué parámetro afectan y a qué clientes.
CREATE OR REPLACE TABLE gold.giros AS
SELECT g.giro_id, g.fecha_efectiva, g.tipo, g.campo, g.informacion, g.accion_requerida, g.variable, g.verbo,
       g.magnitud_pb, g.magnitud_pct, g.horizonte_meses,
       CASE WHEN g.tipo = 'Macro' AND g.variable = 'us_10y_yield' THEN 'rendimiento_de_la_caja'
            WHEN g.tipo = 'Client' AND g.variable = 'liquidity' THEN 'liquidez_requerida'
            WHEN g.tipo = 'FX' THEN 'choque_cambiario' END AS parametro_modelo,
       CASE WHEN g.magnitud_pb IS NOT NULL THEN g.magnitud_pb / 10000.0 ELSE g.magnitud_pct END AS valor_parametro,
       CASE WHEN g.verbo IN ('sube', 'aumenta', 'se deprecia') THEN 1 WHEN g.verbo IN ('baja', 'cae', 'se aprecia') THEN -1 END AS signo_en_variable,
       CASE WHEN g.tipo = 'Client' THEN g.cliente_afectado
            WHEN g.tipo = 'FX' THEN (SELECT string_agg(client_id, ',') FROM gold.restricciones_cliente WHERE fx_col = g.variable)
            ELSE (SELECT string_agg(client_id, ',') FROM gold.client_profiles) END AS clientes_afectados,
       CASE WHEN g.tipo = 'Client' THEN 'client_profiles.' || g.cliente_afectado || '.' || g.variable ELSE 'macro.' || g.variable END AS destino_en_gold
FROM silver.giros g ORDER BY g.giro_id;
