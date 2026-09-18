-- SILVER · giros de la trama (dataset_twist.csv, lote twist_2026-08-17): el texto libre se convierte en parámetros numéricos.
-- Se extraen con expresiones regulares y quedan trazables a la frase original (columna 'informacion').
CREATE OR REPLACE TABLE silver.giros AS
SELECT _row_id, release_id AS giro_id, CAST(effective_date AS DATE) AS fecha_efectiva, type AS tipo, field AS campo,
       new_information AS informacion, required_action AS accion_requerida,
       CASE WHEN type = 'Client' THEN NULLIF(regexp_extract(field, '^(CL_\d+)', 1), '') END AS cliente_afectado,
       CASE WHEN type = 'Client' THEN NULLIF(regexp_extract(field, '^CL_\d+_(.*)$', 1), '') ELSE lower(field) END AS variable,
       NULLIF(regexp_extract(lower(new_information), '(sube|baja|cae|aumenta|se deprecia|se aprecia|necesitar)', 1), '') AS verbo,
       TRY_CAST(NULLIF(regexp_extract(new_information, '(\d+(?:[.,]\d+)?)\s*pb', 1), '') AS DOUBLE) AS magnitud_pb,
       TRY_CAST(replace(NULLIF(regexp_extract(new_information, '(\d+(?:[.,]\d+)?)\s*%', 1), ''), ',', '.') AS DOUBLE) / 100 AS magnitud_pct,
       TRY_CAST(NULLIF(regexp_extract(new_information, 'en (\d+) meses?', 1), '') AS INTEGER) AS horizonte_meses,
       CASE WHEN regexp_matches(lower(new_information), 'en una semana') THEN 1 END AS plazo_semanas
FROM bronze.twist;
