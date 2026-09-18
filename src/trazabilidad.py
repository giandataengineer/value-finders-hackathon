"""Manifiesto de trazabilidad: de cada archivo crudo a cada recomendacion, con huellas, reglas aplicadas y parametros."""
import datetime
import hashlib
import platform

import numpy as np
import pandas as pd
import scipy

import config

TABLAS_POR_PASO = {
    "rendimientos y riesgo por activo": ["01_market_prices_raw (diario, ultimos 12m)", "04_asset_reference"],
    "moneda base del cliente": ["02_macro_raw.usd_cop", "02_macro_raw.usd_pen", "05_client_profiles.base_currency"],
    "rendimiento de la caja": ["02_macro_raw.us_10y_yield"],
    "restricciones del cliente": ["05_client_profiles", "04_asset_reference (pais, sector)"],
    "escenario de estres": ["01_market_prices_raw_expanded (2020 a 2025-07-31)"],
}


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def manifiesto(ins, valor, resultados, archivos_salida):
    parametros = {k: v for k, v in vars(config).items() if k.isupper() and k not in ("ASUNCIONES", "RAIZ", "RAW", "SALIDAS")}
    cadena = {}
    for cid, r in resultados.items():
        pesos = lambda m: {k: round(v, 4) for k, v in r["pesos_por_modo"][m].items() if v >= 0.005}
        cadena[cid] = dict(
            recomendacion_final=pesos("defensiva"), alternativa_sin_estres=pesos("robusta"),
            cumple_presupuesto_de_riesgo_mezcla=r["cumple_tolerancia_por_modo"]["defensiva"],
            restricciones_del_cliente=r["perfil"]["constraint"], tolerancia_caida_pct=r["perfil"]["max_drawdown_tolerance_pct"],
            moneda_base=r["perfil"]["base_currency"], horizonte_meses=r["perfil"]["horizon_months"],
            datos_usados=TABLAS_POR_PASO, decisiones_sobre_datos=valor[["dato", "decision"]].to_dict("records"))
    return dict(
        generado_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        entorno=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__),
        entradas=ins["entradas"], linaje_medallon=ins.get("linaje"), limpieza_aplicada=ins["dq"], parametros=parametros, asunciones=config.ASUNCIONES,
        cadena_de_evidencia=cadena, salidas={a.name: sha256(a) for a in archivos_salida})
