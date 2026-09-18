"""Conexion a Databricks (Databricks Connect): lee el gold, devuelve el mismo diccionario que datos.cargar_insumos()
y publica las salidas del Monte Carlo como tablas Delta en ESQUEMA_SIM. Solo se importa con --databricks.
Uso: python src/databricks_io.py            lista las tablas del gold y sus columnas
     python src/databricks_io.py --sembrar  sube un gold de prueba (datos limpios locales) a un Databricks propio"""
import json
import os
import sys

import numpy as np
import pandas as pd

from config import CATALOGO, ESQUEMA_GOLD, ESQUEMA_SIM, TABLAS_GOLD


def sesion():
    """Usa el perfil de ~/.databrickscfg. Con DATABRICKS_SERVERLESS=1 se conecta a compute serverless en vez del cluster del perfil."""
    from databricks.connect import DatabricksSession
    b = DatabricksSession.builder
    return (b.serverless(True) if os.environ.get("DATABRICKS_SERVERLESS") else b).getOrCreate()


def _guardar(spark, df, nombre):
    spark.createDataFrame(df).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(nombre)


def _ancho(largo):
    return largo.assign(day=pd.to_datetime(largo.day)).pivot(index="day", columns="asset_id", values="close").sort_index()


def cargar_insumos(spark):
    """Lee el gold. Se asume que esta limpio (lo hizo el ETL); aqui solo se pivota y se tipan fechas."""
    t, entradas = {}, {}
    for clave, nombre in TABLAS_GOLD.items():
        completo = f"{CATALOGO}.{ESQUEMA_GOLD}.{nombre}"
        t[clave] = spark.table(completo).toPandas()
        entradas[completo] = dict(filas=len(t[clave]), columnas=list(t[clave].columns))
    macro = t["macro"].assign(date=lambda d: pd.to_datetime(d.date)).set_index("date").sort_index()
    P = _ancho(t["precios_diarios"])
    P = P.loc[macro.index.min():macro.index.max()].ffill(limit=2).dropna()
    intra = _ancho(t["precios_intradia"])
    Rh = np.log(intra.loc[:"2025-07-31"]).diff().dropna(how="any")   # el tramo intradia desde 2025-08-01 contradice al diario y al macro
    dq = [dict(tabla=n, regla="leida del gold, limpieza hecha por el equipo de ETL", filas_afectadas=0) for n in entradas]
    return dict(ref=t["activos"].set_index("asset_id"), clientes=t["clientes"].set_index("client_id"), macro=macro,
                eventos=t["eventos"].assign(event_date=lambda d: pd.to_datetime(d.event_date)), P=P, intra=intra, Rh=Rh,
                fund=t["fundamentales"].sort_values(["issuer_id", "period_end"]), dq=dq, entradas=entradas)


def publicar(spark, salidas):
    """Sube los CSV de salida (y los pesos y el abanico del JSON) como tablas Delta. Devuelve los nombres creados."""
    destino = f"{CATALOGO}.{ESQUEMA_SIM}"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {destino}")
    res = json.loads((salidas / "mc_resultados.json").read_text())["clientes"]
    tablas = {f"mc_{p.stem}": pd.read_csv(p) for p in salidas.glob("*.csv")}
    tablas |= {f"sql_{p.stem}": pd.read_csv(p) for p in (salidas / "sql").glob("*.csv")}
    tablas["mc_pesos"] = pd.DataFrame([dict(cliente=c, cartera=n, asset_id=a, peso=w)
                                       for c, s in res.items() for n, ws in s["carteras"].items() for a, w in ws.items()])
    tablas["mc_abanico"] = pd.DataFrame([dict(cliente=c, mes=m, p5=q[0][i], p25=q[1][i], p50=q[2][i], p75=q[3][i], p95=q[4][i])
                                         for c, s in res.items() for q in [s["abanico"]["p5_p25_p50_p75_p95"]] for i, m in enumerate(s["abanico"]["meses"])])
    for n, df in tablas.items():
        _guardar(spark, df, f"{destino}.{n}")
    return sorted(tablas)


def tablas_gold(ins):
    """El gold equivalente a partir del diccionario local, con los nombres de TABLAS_GOLD (para probar sin el gold real)."""
    largo = lambda W: W.reset_index().melt(id_vars="day", var_name="asset_id", value_name="close")
    return dict(precios_diarios=largo(ins["P"]), precios_intradia=largo(ins["intra"]), macro=ins["macro"].reset_index(), fundamentales=ins["fund"],
                activos=ins["ref"].reset_index(), clientes=ins["clientes"].reset_index(), eventos=ins["eventos"])


def sembrar(spark, ins):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGO}.{ESQUEMA_GOLD}")
    for clave, df in tablas_gold(ins).items():
        _guardar(spark, df, f"{CATALOGO}.{ESQUEMA_GOLD}.{TABLAS_GOLD[clave]}")


def explorar(spark):
    for f in spark.sql(f"SHOW TABLES IN {CATALOGO}.{ESQUEMA_GOLD}").collect():
        print("\n" + f.tableName)
        spark.table(f"{CATALOGO}.{ESQUEMA_GOLD}.{f.tableName}").printSchema()


if __name__ == "__main__":
    s = sesion()
    if "--sembrar" in sys.argv:
        from datos import cargar_insumos as local
        sembrar(s, local())
    else:
        explorar(s)
