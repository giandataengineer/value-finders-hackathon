"""Interfaz de datos del motor.

cargar_insumos()         lee el GOLD del medallon (data/gold/*.parquet, generado por src/etl.py con SQL). Es lo que usa el motor.
cargar_insumos_pandas()  limpia directamente el crudo con pandas, sin pasar por el medallon: implementacion INDEPENDIENTE de las mismas
                         reglas. Sirve para contrastar el SQL (tests/test_etl.py exige que ambas coincidan).
Ambas devuelven el mismo diccionario, que tambien produce databricks_io.cargar_insumos() al leer el gold de Databricks.
"""
import hashlib

import numpy as np
import pandas as pd

from config import IDS, RAIZ, RAW

ISO = r"^\d{4}-\d{2}-\d{2}"
ETIQUETA_TRIMESTRE = r"^Q[1-4]-\d{4}$"


def _g(tabla):
    from etl import leer_parquet
    return leer_parquet("gold", tabla)


def _ancho(largo):
    return largo.assign(day=pd.to_datetime(largo["day"])).pivot(index="day", columns="asset_id", values="close").sort_index()


def cargar_insumos(reconstruir=False):
    from etl import asegurar_gold
    manifiesto = asegurar_gold(reconstruir)
    macro = _g("macro").assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date").sort_index()
    intra_largo = _g("precios_intradia_cierre")
    intra = _ancho(intra_largo)
    P = _ancho(_g("precios_diarios")).loc[macro.index.min():macro.index.max()].ffill(limit=2).dropna()
    Rh = np.log(_ancho(intra_largo[intra_largo["tramo_confiable"]])).diff().dropna(how="any")   # historial para el escenario de estres
    dq = [dict(tabla=r.tabla, regla=r.regla, filas_afectadas=int(r.filas_afectadas)) for r in _g("calidad_datos").itertuples()]
    eventos = _g("events").assign(event_date=lambda d: pd.to_datetime(d["event_date"]))
    fund = _g("fundamentales").assign(period_end=lambda d: pd.to_datetime(d["period_end"])).sort_values(["issuer_id", "period_end"]).reset_index(drop=True)
    return dict(ref=_g("asset_reference").set_index("asset_id"), clientes=_g("client_profiles").set_index("client_id"), macro=macro, eventos=eventos,
                P=P, intra=intra, Rh=Rh, fund=fund, dq=dq, entradas=manifiesto["entradas"], linaje=_g("linaje").to_dict("records"),
                giros=_g("giros"), restricciones=_g("restricciones_cliente").set_index("client_id"), senal=_g("senal_correlacion"))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _fecha(s):
    return pd.to_datetime(s, format="mixed")


def cargar_insumos_pandas():
    dq, entradas = [], {}

    def log(tabla, regla, n):
        if int(n):
            dq.append(dict(tabla=tabla, regla=regla, filas_afectadas=int(n)))

    def leer(nombre, **kw):
        df = pd.read_csv(RAW / nombre, **kw)
        entradas[nombre] = dict(sha256=_sha256(RAW / nombre), filas=len(df), columnas=list(df.columns))
        return df

    ref = leer("04_asset_reference.csv").set_index("asset_id")
    clientes = leer("05_client_profiles.csv").set_index("client_id")
    macro = leer("02_macro_raw.csv", parse_dates=["date"]).set_index("date")
    eventos = leer("06_events.csv", parse_dates=["event_date"])

    t = "01_market_prices_raw"
    d = leer(t + ".csv")
    log(t, "asset_id mal escrito, corregido", d.asset_id.isin(IDS).sum())
    d["asset_id"] = d.asset_id.replace(IDS)
    log(t, "fecha MM/DD/YYYY convertida a ISO", (~d.date.str.match(ISO)).sum())
    d["day"] = _fecha(d.date)
    log(t, "filas duplicadas eliminadas", d.duplicated(["day", "asset_id"]).sum())
    d = d.drop_duplicates(["day", "asset_id"])
    malo = (d.close > 1000) & (d.close / 100).between(d.low, d.high)
    log(t, "precio con punto decimal corrido, dividido por 100", malo.sum())
    d.loc[malo, "close"] /= 100
    P = d.pivot(index="day", columns="asset_id", values="close").sort_index()
    P = P.loc[macro.index.min():macro.index.max()].ffill(limit=2).dropna()

    t = "01_market_prices_raw_expanded"
    e = leer(t + ".csv")
    e["asset_id"] = e.asset_id.replace(IDS)
    e["day"] = _fecha(e.date).dt.normalize()
    e = e.dropna(subset=["close"]).drop_duplicates(["date", "asset_id"])
    intra = e.groupby(["day", "asset_id"]).close.last().unstack("asset_id").sort_index()
    Rh = np.log(intra.loc[:P.index.min() - pd.Timedelta(days=1)]).diff().dropna(how="any")

    f = leer("03_fundamentals_raw.csv")
    f["issuer_id"] = f.issuer_id.replace({"ISS04": "ISS_04"})
    etiqueta = f.period_end.str.match(ETIQUETA_TRIMESTRE)
    iso = pd.to_datetime(f.period_end.where(~etiqueta), errors="coerce")
    lab = pd.to_datetime([pd.Period(f"{p[3:]}Q{p[1]}").end_time.normalize() if m else pd.NaT for p, m in zip(f.period_end, etiqueta)])
    choca = pd.Series([bool(m) and ((iso[f.issuer_id == i] == l).any()) for m, i, l in zip(etiqueta, f.issuer_id, lab)], index=f.index)
    # una etiqueta que choca con un trimestre existente se reasigna al trimestre siguiente al de la fila anterior del mismo emisor
    siguiente = iso.groupby(f.issuer_id).shift(1) + pd.offsets.MonthEnd(3)
    f["period_end"] = iso.where(~etiqueta, lab.to_series(index=f.index).where(~choca, siguiente))
    f["revenue_usd_m"] = pd.to_numeric(f.revenue_usd_m.astype(str).str.replace(",", ""))
    f = f.drop_duplicates(["issuer_id", "period_end"]).sort_values(["issuer_id", "period_end"]).reset_index(drop=True)
    return dict(ref=ref, clientes=clientes, macro=macro, eventos=eventos, P=P, intra=intra, Rh=Rh, fund=f, dq=dq, entradas=entradas)
