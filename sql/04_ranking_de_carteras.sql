-- Ranking de carteras por cliente y estado del mercado, por retorno y por riesgo (funciones de ventana RANK).
SELECT cliente, modo, cartera, ret_anual_mediano, p_mdd_sobre_tol, cumple_restricciones_cliente,
       RANK() OVER (PARTITION BY cliente, modo ORDER BY ret_anual_mediano DESC) AS puesto_por_retorno,
       RANK() OVER (PARTITION BY cliente, modo ORDER BY p_mdd_sobre_tol ASC)    AS puesto_por_riesgo
FROM resultados
ORDER BY cliente, modo, puesto_por_retorno;
