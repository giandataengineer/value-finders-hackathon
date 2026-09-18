"""Capa SQL (DuckDB): analitica sobre los datos limpios y sobre los resultados, con funciones de ventana.
Cuando el gold del equipo de ETL este listo, las vistas 'precios' y 'activos' se leen de ahi y el SQL no cambia."""
import duckdb
import pandas as pd

from config import RAIZ, SALIDAS


def ejecutar_sql(ins):
    con = duckdb.connect()
    precios = ins["P"].reset_index().melt(id_vars="day", var_name="asset_id", value_name="close").rename(columns={"day": "fecha"})
    con.register("precios", precios)
    con.register("activos", ins["ref"].reset_index())
    con.register("dq", pd.DataFrame(ins["dq"]))
    resultados = SALIDAS / "resultados_carteras.csv"
    if resultados.exists():
        con.execute(f"CREATE VIEW resultados AS SELECT * FROM read_csv_auto('{resultados}')")
    (SALIDAS / "sql").mkdir(exist_ok=True)
    filas = {}
    for f in sorted((RAIZ / "sql").glob("*.sql")):
        if "resultados" in f.read_text() and not resultados.exists():
            continue
        df = con.execute(f.read_text()).df()
        df.to_csv(SALIDAS / "sql" / f"{f.stem}.csv", index=False)
        filas[f.stem] = len(df)
    return filas
