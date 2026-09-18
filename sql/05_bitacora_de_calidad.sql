-- Bitácora de limpieza: cuántas reglas y cuántas filas afectó cada una por tabla (trazabilidad del dato crudo al dato usado).
SELECT tabla, COUNT(*) AS reglas_aplicadas, SUM(filas_afectadas) AS filas_afectadas
FROM dq
GROUP BY tabla
ORDER BY filas_afectadas DESC;
