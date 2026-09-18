"""ETL medallon (bronze, silver, gold) en DuckDB con SQL, para el data pack y el dataset del giro de la trama.

    bronze : el archivo tal cual (todo texto) + trazabilidad por fila (_source_file, _source_sha256, _batch, _ingested_at, _row_id)
    silver : tipado, normalizado y validado. Lo que no pasa va a silver.cuarentena con su motivo; nada se pierde en silencio
    gold   : tablas listas para el motor y el dashboard (contrato de datos en docs/medallion.md), en Parquet y en medallion.duckdb

Uso: python src/etl.py           reconstruye las tres capas y muestra el resumen
Las transformaciones estan en sql/silver y sql/gold; aqui solo se ordenan, se cuentan y se exportan.
"""
import datetime
import hashlib
import json
import sys

import duckdb
import pandas as pd

from config import RAIZ, RAW

DB = RAIZ / "data" / "medallion.duckdb"
CAPAS = ("bronze", "silver", "gold")
# tabla bronze: (archivo, lote, etiqueta en la bitacora, tabla silver, tabla gold)
FUENTES = {
    "market_daily": ("01_market_prices_raw.csv", "start", "01_market_prices_raw", "silver.market_daily", "gold.precios_diarios"),
    "market_intraday": ("01_market_prices_raw_expanded.csv", "start", "01_market_prices_raw_expanded", "silver.market_intraday", "gold.precios_intradia_cierre"),
    "macro": ("02_macro_raw.csv", "start", "02_macro_raw", "silver.macro", "gold.macro"),
    "fundamentals": ("03_fundamentals_raw.csv", "start", "03_fundamentals_raw", "silver.fundamentals", "gold.fundamentales"),
    "asset_reference": ("04_asset_reference.csv", "start", "04_asset_reference", "silver.asset_reference", "gold.asset_reference"),
    "client_profiles": ("05_client_profiles.csv", "start", "05_client_profiles", "silver.client_profiles", "gold.client_profiles"),
    "events": ("06_events.csv", "start", "06_events", "silver.events", "gold.events"),
    "twist": ("dataset_twist.csv", "twist_2026-08-17", "dataset_twist", "silver.giros", "gold.giros"),
}

# (etiqueta, regla, SQL que cuenta las filas afectadas). Los textos son estables: los usa la trazabilidad y las pruebas.
_M = "01_market_prices_raw"
_I = "01_market_prices_raw_expanded"
_F = "03_fundamentals_raw"
REGLAS = [
    (_M, "asset_id mal escrito, corregido", "SELECT count(*) FROM silver._market_daily_n WHERE asset_id_original <> asset_id"),
    (_M, "fecha MM/DD/YYYY convertida a ISO", "SELECT count(*) FROM silver._market_daily_n WHERE date_original NOT LIKE '____-__-__'"),
    (_M, "volumen con sufijo K (no se usa en la simulacion)", "SELECT count(*) FROM bronze.market_daily WHERE volume LIKE '%K'"),
    (_M, "volumen nulo (no se usa en la simulacion)", "SELECT count(*) FROM bronze.market_daily WHERE volume IS NULL"),
    (_M, "currency nula (USD segun tabla 04)", "SELECT count(*) FROM bronze.market_daily WHERE currency IS NULL"),
    (_M, "filas duplicadas eliminadas", "SELECT count(*) FROM silver.cuarentena WHERE tabla = 'market_daily' AND motivo LIKE 'duplicado%'"),
    (_M, "precio con punto decimal corrido, dividido por 100", "SELECT count(*) FROM silver._market_daily_n WHERE precio_corregido"),
    (_I, "asset_id mal escrito, corregido", "SELECT count(*) FROM silver._market_intraday_n WHERE asset_id_original <> asset_id"),
    (_I, "fecha MM/DD/YYYY convertida a ISO", "SELECT count(*) FROM silver._market_intraday_n WHERE date_original NOT LIKE '____-__-__ %'"),
    (_I, "volumen con sufijo K (no se usa en la simulacion)", "SELECT count(*) FROM bronze.market_intraday WHERE volume LIKE '%K'"),
    (_I, "volumen nulo (no se usa en la simulacion)", "SELECT count(*) FROM bronze.market_intraday WHERE volume IS NULL"),
    (_I, "currency nula (USD segun tabla 04)", "SELECT count(*) FROM bronze.market_intraday WHERE currency IS NULL"),
    (_I, "close nulo, fila descartada", "SELECT count(*) FROM silver.cuarentena WHERE tabla = 'market_intraday' AND motivo = 'close nulo'"),
    (_I, "filas duplicadas eliminadas", "SELECT count(*) FROM silver.cuarentena WHERE tabla = 'market_intraday' AND motivo LIKE 'duplicado%'"),
    (_I, "tramo desde 2025-08-01 marcado no confiable (contradice al diario y al macro)", "SELECT count(*) FROM gold.precios_intradia_cierre WHERE NOT tramo_confiable"),
    ("02_macro_raw", "inflacion mensual propagada a diario en columna aparte (no se usa)", "SELECT count(*) FROM silver.macro WHERE us_inflation_yoy IS NULL"),
    (_F, "issuer_id mal escrito (ISS04)", "SELECT count(*) FROM silver._fund_n WHERE issuer_original <> issuer_id"),
    (_F, "period_end como texto (Q4-2024), convertido", "SELECT count(*) FROM silver._fund_n WHERE periodo_desde_etiqueta"),
    (_F, "trimestre mal etiquetado: Q4-2024 choca con 2024-12-31 y se reasigna al trimestre faltante (2025-06-30) por posicion", "SELECT count(*) FROM silver._fund_n WHERE periodo_reasignado"),
    (_F, "revenue con coma de miles, convertido", "SELECT count(*) FROM silver._fund_n WHERE revenue_original LIKE '%,%'"),
    (_F, "filas duplicadas eliminadas", "SELECT count(*) FROM silver.cuarentena WHERE tabla = 'fundamentals'"),
    (_F, "cash nulo (se deja nulo, no se usa)", "SELECT count(*) FROM silver.fundamentals WHERE cash_usd_m IS NULL"),
    ("dataset_twist", "cifras extraidas del texto libre (pb, %, meses) con expresiones regulares", "SELECT count(*) FROM silver.giros WHERE magnitud_pb IS NOT NULL OR magnitud_pct IS NOT NULL"),
]


def leer_parquet(capa, tabla):
    """Lee una tabla del medallon exportada a Parquet (con DuckDB, sin depender de pyarrow)."""
    return duckdb.sql(f"SELECT * FROM read_parquet('{RAIZ / 'data' / capa / (tabla + '.parquet')}')").df()


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _correr(con, carpeta):
    for f in sorted((RAIZ / "sql" / carpeta).glob("*.sql")):
        con.execute(f.read_text())


def _bronce(con, ahora):
    entradas = {}
    for tabla, (archivo, lote, *_r) in FUENTES.items():
        ruta = RAW / archivo
        huella = sha256(ruta)
        con.execute(f"""CREATE OR REPLACE TABLE bronze.{tabla} AS
            SELECT row_number() OVER () AS _row_id, '{archivo}' AS _source_file, '{huella}' AS _source_sha256, '{lote}' AS _batch,
                   TIMESTAMP '{ahora}' AS _ingested_at, *
            FROM read_csv('{ruta}', header = true, all_varchar = true, parallel = false)""")
        cols = [c[0] for c in con.execute(f"DESCRIBE bronze.{tabla}").fetchall() if not c[0].startswith("_")]
        entradas[archivo] = dict(sha256=huella, filas=con.execute(f"SELECT count(*) FROM bronze.{tabla}").fetchone()[0], columnas=cols, lote=lote)
    return entradas


def _bitacora_y_linaje(con, entradas):
    dq = pd.DataFrame([dict(tabla=t, regla=r, filas_afectadas=int(con.execute(q).fetchone()[0])) for t, r, q in REGLAS])
    dq = dq[dq.filas_afectadas > 0].reset_index(drop=True)
    con.register("_dq", dq)
    con.execute("CREATE OR REPLACE TABLE silver.dq_log AS SELECT * FROM _dq")
    con.execute("CREATE OR REPLACE TABLE gold.calidad_datos AS SELECT tabla, regla, filas_afectadas FROM silver.dq_log ORDER BY tabla, filas_afectadas DESC")
    filas = []
    for tabla, (archivo, lote, etiqueta, silver, gold) in FUENTES.items():
        n = lambda t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        cuarentena = con.execute(f"SELECT count(*) FROM silver.cuarentena WHERE tabla = '{tabla}'").fetchone()[0]
        filas.append(dict(dataset=etiqueta, archivo=archivo, lote=lote, sha256=entradas[archivo]["sha256"], tabla_bronze=f"bronze.{tabla}",
                          tabla_silver=silver, tabla_gold=gold, filas_bronze=n(f"bronze.{tabla}"), filas_silver=n(silver),
                          filas_cuarentena=int(cuarentena), filas_gold=n(gold)))
    con.register("_linaje", pd.DataFrame(filas))
    con.execute("CREATE OR REPLACE TABLE gold.linaje AS SELECT * FROM _linaje")


def ejecutar_etl(verbose=True):
    ahora = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    for c in CAPAS:
        con.execute(f"CREATE SCHEMA {c}")
    entradas = _bronce(con, ahora)
    _correr(con, "silver")
    _correr(con, "gold")
    _bitacora_y_linaje(con, entradas)
    for s in ("silver", "gold"):   # tablas de trabajo
        for (t,) in con.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{s}' AND table_name LIKE '\\_%' ESCAPE '\\'").fetchall():
            con.execute(f"DROP TABLE {s}.{t}")
    conteos = {}
    for capa in CAPAS:
        (RAIZ / "data" / capa).mkdir(parents=True, exist_ok=True)
        for (t,) in con.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{capa}' ORDER BY 1").fetchall():
            con.execute(f"COPY {capa}.{t} TO '{RAIZ / 'data' / capa / (t + '.parquet')}' (FORMAT PARQUET)")
            conteos[f"{capa}.{t}"] = con.execute(f"SELECT count(*) FROM {capa}.{t}").fetchone()[0]
    manifiesto = dict(generado_utc=ahora, entradas=entradas, tablas=conteos)
    (RAIZ / "data" / "gold" / "_manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1))
    con.close()
    if verbose:
        print(pd.DataFrame(json.loads(json.dumps([dict(tabla=k, filas=v) for k, v in conteos.items()]))).to_string(index=False))
    return manifiesto


def asegurar_gold(reconstruir=False):
    """Devuelve el manifiesto del gold; reconstruye el medallon si falta o si algun archivo crudo cambio (huella distinta)."""
    ruta = RAIZ / "data" / "gold" / "_manifiesto.json"
    if not reconstruir and ruta.exists():
        m = json.loads(ruta.read_text())
        if all((RAW / a).exists() and sha256(RAW / a) == e["sha256"] for a, e in m["entradas"].items()) and len(m["entradas"]) == len(FUENTES):
            return m
    return ejecutar_etl(verbose=False)


if __name__ == "__main__":
    ejecutar_etl(verbose="--silencio" not in sys.argv)
