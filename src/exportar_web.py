"""Congela los resultados para la web: web/public/payload.json (lo que se muestra) y web/public/motor.json (lo que necesita
el navegador para simular en vivo). Uso: python src/exportar_web.py   (despues de src/run.py y src/twists.py)"""
import datetime
import json
import re

import numpy as np
import pandas as pd

from config import BLOQUE_POR_MODO, DIAS, ENCOGER, ERP, FX_COL, PROB_ESTADOS, RAIZ, SALIDAS
from datos import cargar_insumos
from etl import leer_parquet

WEB = RAIZ / "web" / "public"
JSON_DEF = lambda o: o.item() if hasattr(o, "item") else (str(o) if not isinstance(o, (pd.Timestamp, datetime.date)) else str(o)[:10])

STAGES = [
    dict(key="briefing", eyebrow="Fase 00", title="El caso", tagline="Qué decisión se recomienda hoy, para quién y con qué evidencia."),
    dict(key="ingesta", eyebrow="Fase 01", title="Find the truth", tagline="Los datos crudos pasan por un medallón: qué sirve, qué no y por qué."),
    dict(key="uplift", eyebrow="Fase 02", title="Find the signal", tagline="La señal: el riesgo cambia de régimen y llegan tres giros de la trama."),
    dict(key="montecarlo", eyebrow="Fase 03", title="Find the value", tagline="Diez mil futuros por cliente, dentro de sus propias restricciones."),
    dict(key="reporte", eyebrow="Fase 04", title="Make it matter", tagline="Una vista para decidir: qué pasa, por qué, qué hacer y qué lo cambiaría."),
]


def _sql_consultas():
    out = []
    metas = {"02_caida_maxima_por_activo": "Riesgo por activo", "03_correlaciones_12m": "Correlaciones entre activos",
             "04_ranking_de_carteras": "Ranking de carteras por cliente", "05_bitacora_de_calidad": "Bitácora de calidad del ETL"}
    for f in sorted((RAIZ / "sql").glob("0*.sql")):
        csv = SALIDAS / "sql" / f"{f.stem}.csv"
        if f.stem not in metas or not csv.exists():
            continue
        texto = f.read_text()
        df = pd.read_csv(csv).head(12)
        out.append(dict(archivo=f"sql/{f.name}", titulo=metas[f.stem], proposito=texto.splitlines()[0].lstrip("- ").strip(), sql=texto,
                        columnas=list(df.columns), filas=json.loads(df.to_json(orient="records"))))
    return out


def _regimenes(macro):
    r = macro.risk_regime
    bloque = (r != r.shift()).cumsum()
    return [dict(regimen=g.risk_regime.iloc[0], desde=str(g.index[0].date()), hasta=str(g.index[-1].date()), dias=len(g)) for _, g in macro.groupby(bloque)]


def construir():
    ins = cargar_insumos()
    P, macro, ref = ins["P"], ins["macro"], ins["ref"]
    mc = json.loads((SALIDAS / "mc_resultados.json").read_text())
    traz = json.loads((SALIDAS / "trazabilidad.json").read_text())
    tw_ruta = SALIDAS / "twists.json"
    twists = json.loads(tw_ruta.read_text()) if tw_ruta.exists() else None
    valor = pd.read_csv(SALIDAS / "valor_de_los_datos.csv")
    manifiesto = json.loads((RAIZ / "data" / "gold" / "_manifiesto.json").read_text())
    cuarentena = leer_parquet("silver", "cuarentena").groupby(["tabla", "motivo"]).size().reset_index(name="filas")
    indice = (P / P.iloc[0] * 100).round(2)
    R = np.log(P).diff().dropna()

    clientes_perfil = [dict(id=cid, nombre=f.profile_name, moneda=f.base_currency, horizonte_meses=int(f.horizon_months), tolerancia_caida=int(f.max_drawdown_tolerance_pct) / 100,
                            liquidez=f.liquidity_need, prioridad=f.priority, riesgo=f.risk_tolerance, restriccion=f["constraint"],
                            presupuesto_riesgo=mc["clientes"][cid]["presupuesto_riesgo"]) for cid, f in ins["clientes"].iterrows()]
    payload = dict(
        meta=dict(proyecto="Value Finders", empresa="Credicorp Capital", generado=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  solo_insights=True, simulaciones=10000, activos=len(ref), dias_analizados=len(P),
                  aviso="Dataset sintético del reto Value Finders. Generamos insights y recomendaciones; las decisiones las toman las personas. No es asesoría financiera."),
        stages=STAGES,
        caso=dict(pregunta="¿Qué decisión de inversión recomendarían a este cliente hoy, a partir de la información disponible, y qué evidencia les permite defenderla?",
                  clientes=clientes_perfil, activos=json.loads(ref.reset_index().to_json(orient="records"))),
        datos=dict(capas=manifiesto["tablas"], linaje=ins["linaje"], calidad=ins["dq"], cuarentena=json.loads(cuarentena.to_json(orient="records")),
                   valor=json.loads(valor.to_json(orient="records")), entradas={k: dict(filas=v["filas"], lote=v.get("lote")) for k, v in ins["entradas"].items()}),
        senal=dict(estadisticas_activo=json.loads(leer_parquet("gold", "estadisticas_activo").to_json(orient="records")),
                   correlacion_por_fuente=json.loads(leer_parquet("gold", "senal_correlacion").to_json(orient="records")),
                   correlaciones=json.loads(leer_parquet("gold", "correlaciones").to_json(orient="records")),
                   eventos=json.loads(leer_parquet("gold", "eventos_reaccion").to_json(orient="records", date_format="iso")),
                   regimenes=_regimenes(macro), backtest=mc["backtest_calibracion"],
                   serie=dict(fechas=[str(d.date()) for d in P.index], indice={c: indice[c].tolist() for c in indice},
                              us10y=macro.us_10y_yield.reindex(P.index).tolist(), usd_cop=macro.usd_cop.reindex(P.index).tolist(),
                              usd_pen=macro.usd_pen.reindex(P.index).tolist(), regimen=macro.risk_regime.reindex(P.index).tolist())),
        clientes=mc["clientes"], giros=twists, sql=dict(consultas=_sql_consultas()),
        trazabilidad=dict(generado=traz["generado_utc"], entorno=traz["entorno"], entradas=traz["entradas"], linaje=traz.get("linaje_medallon"),
                          limpieza=traz["limpieza_aplicada"], parametros=traz["parametros"], asunciones=traz["asunciones"], salidas=traz["salidas"],
                          cadena=traz["cadena_de_evidencia"]),
    )
    # motor para el navegador: mismos retornos remuestreados, mismas deriva por estado y mismas carteras que el Monte Carlo de Python
    rf = macro.us_10y_yield.mean() / 100
    ret12 = ((P.iloc[-1] / P.iloc[0]) ** (365 / (P.index[-1] - P.index[0]).days) - 1)
    fx = {}
    for cur, col in FX_COL.items():
        if col:
            x = np.log(macro[col]).diff().reindex(R.index)
            fx[cur] = np.round((x - x.mean()).values, 6).tolist()
    motor = dict(
        semilla=42, dias=DIAS, activos=list(ref.index), rf=float(rf), erp=ERP, encoger=ENCOGER, prob_estados=PROB_ESTADOS, bloque=BLOQUE_POR_MODO,
        sigma_anual=(R.std() * np.sqrt(DIAS)).round(6).tolist(), ret12=ret12.round(6).tolist(),
        base=np.round((R - R.mean()).values, 6).tolist(), fx=fx, estres=np.round(ins["Rh"].values, 6).tolist(),
        clientes={cid: dict(H=int(f.horizon_months) * 21, meses=int(f.horizon_months), tolerancia=float(f.max_drawdown_tolerance_pct) / 100, moneda=f.base_currency,
                            carteras={n: [float(w[a]) for a in list(ref.index) + ["CAJA"]] for n, w in mc["clientes"][cid]["carteras"].items()})
                  for cid, f in ins["clientes"].iterrows()})
    return payload, motor


def main():
    WEB.mkdir(parents=True, exist_ok=True)
    payload, motor = construir()
    (WEB / "payload.json").write_text(json.dumps(payload, ensure_ascii=False, default=JSON_DEF, separators=(",", ":"), allow_nan=False))
    (WEB / "motor.json").write_text(json.dumps(motor, ensure_ascii=False, default=JSON_DEF, separators=(",", ":"), allow_nan=False))
    print("payload.json", (WEB / "payload.json").stat().st_size // 1024, "KB | motor.json", (WEB / "motor.json").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
