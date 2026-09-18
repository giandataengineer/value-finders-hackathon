"""Orquesta todo el flujo. Uso: python src/run.py [--sin-llm] [--databricks [--publicar]]   (desde la raiz del proyecto; --databricks lee el gold, --publicar ademas sube las salidas como tablas Delta)"""
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from config import DIAS, MODOS, PROB_ESTADOS, RONDAS_MODO, RONDAS_ROBUSTA, SALIDAS, SEED
from consultas import ejecutar_sql
from cuantico import grover_carteras, sensibilidad_estres, superposicion_estados
from datos import cargar_insumos
from lectura_multirol import lecturas_cliente
from robustez import estabilidad_ranking, sensibilidad_ruidos, valor_informacion_estados
from simulacion import Cliente, fuentes, mv_sharpe, optimizar, resumen, simular_final
from trazabilidad import manifiesto
from valor_datos import evaluar_valor
from validacion import backtest_calibracion, estabilidad_semillas, sensibilidad

MV, FINAL, BASE = "clasica Markowitz (max Sharpe)", "recomendada defensiva (con estres)", "recomendada base (robusta)"
JSON_DEF = lambda o: o.item() if hasattr(o, "item") else str(o)


def graficos(cid, cl, fan, M_rec, M_mv, gr):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    m, q = fan["meses"], np.array(fan["p5_p25_p50_p75_p95"])
    ax[0].fill_between(m, q[0], q[4], alpha=0.18, label="P5 a P95")
    ax[0].fill_between(m, q[1], q[3], alpha=0.32, label="P25 a P75")
    ax[0].plot(m, q[2], lw=2, label="mediana")
    ax[0].axhline(1, color="gray", lw=0.8)
    ax[0].set(title=f"{cid}: valor de 1 unidad invertida ({cl.moneda}), cartera recomendada", xlabel="meses")
    ax[0].legend()
    ax[1].hist(M_rec * 100, bins=40, alpha=0.6, label="recomendada")
    ax[1].hist(M_mv * 100, bins=40, alpha=0.5, label="Markowitz clasico")
    ax[1].axvline(cl.tol * 100, color="red", lw=2, label=f"tolerancia {cl.tol:.0%}")
    ax[1].set(title="Caida maxima en el horizonte (%)", xlabel="% de caida maxima")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(SALIDAS / "figuras" / f"{cid}_abanico_y_caida.png", dpi=130)
    plt.close(fig)
    if gr.get("top"):
        fig, ax = plt.subplots(figsize=(9, 4))
        top = gr["top"]
        ax.bar(range(len(top)), [t["prob_despues"] for t in top])
        ax.axhline(1 / gr["estados"], color="red", ls="--", label="probabilidad inicial (superposicion uniforme)")
        ax.set_xticks(range(len(top)))
        ax.set_xticklabels(["+".join(a.replace("VF_A", "A") for a in t["activos"]) for t in top], rotation=60, ha="right", fontsize=7)
        ax.set(title=f"{cid}: probabilidad de medir cada combinacion tras {gr['iteraciones']} pasos de Grover")
        ax.legend()
        fig.tight_layout()
        fig.savefig(SALIDAS / "figuras" / f"{cid}_grover.png", dpi=130)
        plt.close(fig)


def procesar_cliente(cid, ins):
    ref, clientes, macro, P = ins["ref"], ins["clientes"], ins["macro"], ins["P"]
    ci, fila = list(clientes.index).index(cid), clientes.loc[cid]
    R = np.log(P).diff().dropna()
    rf = macro.us_10y_yield.mean() / 100
    cl = Cliente(cid, fila, ref, R.std() * np.sqrt(DIAS))
    F = fuentes(ins, cl)
    rng = lambda *k: np.random.default_rng([SEED, ci, *k])
    opt = {m: optimizar(cl, [F[m]], rng(mi, 0), RONDAS_MODO) for mi, m in enumerate(MODOS)}
    opt["robusta"] = optimizar(cl, [F["base_neutral"], F["base_realizado"]], rng(9, 0), RONDAS_ROBUSTA)
    opt["defensiva"] = optimizar(cl, [F[m] for m in MODOS], rng(9, 1), RONDAS_ROBUSTA, mezcla=[PROB_ESTADOS[m] for m in MODOS])
    cols = list(ref.index) + ["CAJA"]
    carteras = {FINAL: opt["defensiva"][0], BASE: opt["robusta"][0], "optima solo neutral": opt["base_neutral"][0],
                "optima solo realizado": opt["base_realizado"][0], "igual ponderada": np.append(np.full(8, 1 / 8), 0.0),
                "solo caja": np.array([0.0] * 8 + [1.0]), MV: mv_sharpe(R, rf)}
    nombres, W = list(carteras), np.array(list(carteras.values()))
    cump = cl.cumple(W)
    salida = dict(perfil={k: (v.item() if hasattr(v, "item") else v) for k, v in fila.to_dict().items()},
                  presupuesto_riesgo=cl.alfa, alta_volatilidad=[a for a, v in zip(ref.index, cl.alta) if v],
                  carteras={n: dict(zip(cols, map(float, w))) for n, w in carteras.items()},
                  pesos_por_modo={m: dict(zip(cols, map(float, opt[m][0]))) for m in opt},
                  cumple_tolerancia_por_modo={m: opt[m][1] for m in opt}, metricas={})
    Tm, Mm, filas = {}, {}, []
    for mi, modo in enumerate(MODOS):
        T, M, q = simular_final(cl, W, F[modo], rng(mi, 1), meses_abanico=int(fila.horizon_months) if modo == "base_neutral" else 0)
        Tm[modo], Mm[modo] = T, M
        if q is not None:
            fan = dict(meses=list(range(1, int(fila.horizon_months) + 1)), p5_p25_p50_p75_p95=q.tolist())
        salida["metricas"][modo] = {n: dict(resumen(T[:, k], M[:, k], cl.tol, cl.H), cumple_restricciones_cliente=bool(cump[k])) for k, n in enumerate(nombres)}
    mezcla = {n: superposicion_estados({m: Tm[m][:, k] for m in MODOS}, {m: Mm[m][:, k] for m in MODOS}, cl, rng(5, k)) for k, n in enumerate(nombres)}
    salida["superposicion_estados"] = mezcla
    salida["sensibilidad_prob_estres"] = sensibilidad_estres({m: Tm[m][:, 0] for m in MODOS}, {m: Mm[m][:, 0] for m in MODOS}, cl, rng(5, 99))
    for modo in MODOS:
        for n in nombres:
            filas.append(dict(cliente=cid, perfil=fila.profile_name, modo=modo, cartera=n, **salida["metricas"][modo][n],
                              pesos="; ".join(f"{a}:{w:.0%}" for a, w in zip(cols, carteras[n]) if w >= 0.005)))
    for n in nombres:
        x = mezcla[n]
        filas.append(dict(cliente=cid, perfil=fila.profile_name, modo="mezcla_55_30_15", cartera=n,
                          **{k: x[k] for k in salida["metricas"]["base_neutral"][n] if k in x}, cumple_restricciones_cliente=bool(cump[nombres.index(n)]),
                          pesos="; ".join(f"{a}:{w:.0%}" for a, w in zip(cols, carteras[n]) if w >= 0.005)))
    salida["abanico"] = fan
    salida["grover"] = grover_carteras(cl, [F["base_neutral"], F["base_realizado"]], ref, rng(6, 0))
    pares = [F["base_neutral"], F["base_realizado"]]
    salida["robustez"] = dict(estabilidad_ranking=estabilidad_ranking(cl, W, nombres, pares),
                              sensibilidad_ruidos=sensibilidad_ruidos(cl, W, nombres, ins),
                              valor_informacion=valor_informacion_estados(nombres, Tm))
    w_fin = W[0]
    salida["validacion"] = dict(estabilidad_semillas=estabilidad_semillas(cl, w_fin, ins), sensibilidad=sensibilidad(cl, w_fin, ins))
    graficos(cid, cl, fan, Mm["base_neutral"][:, 0], Mm["base_neutral"][:, nombres.index(MV)], salida["grover"])
    return cid, filas, salida


def armar_ranking(s):
    mets, mez = s["metricas"], s["superposicion_estados"]
    mv = mets["base_neutral"][MV]["ret_anual_mediano"]
    out = []
    for n, w in s["carteras"].items():
        a, b, e = mets["base_neutral"][n], mets["base_realizado"][n], mets["estres_historial_2020_2025"][n]
        out.append(dict(decision=n, pesos={k: round(v, 3) for k, v in w.items() if v >= 0.005}, ret_anual_neutral=a["ret_anual_mediano"], p5=a["p5"],
                        cvar5=a["cvar5"], prob_perdida=a["prob_perdida"], p_mdd_neutral=a["p_mdd_sobre_tol"], p_mdd_realizado=b["p_mdd_sobre_tol"],
                        p_mdd_estres=e["p_mdd_sobre_tol"], p_mdd_mezcla=mez[n]["p_mdd_sobre_tol"], ret_anual_mezcla=mez[n]["ret_anual_mediano"],
                        cumple_restricciones=a["cumple_restricciones_cliente"], alfa=s["presupuesto_riesgo"], ret_anual_markowitz=mv))
    return out


def main():
    t0 = time.time()
    SALIDAS.mkdir(exist_ok=True)
    (SALIDAS / "figuras").mkdir(exist_ok=True)
    usar_dbx = "--databricks" in sys.argv
    if usar_dbx:
        import databricks_io
        spark = databricks_io.sesion()
        ins = databricks_io.cargar_insumos(spark)
    else:
        ins = cargar_insumos()
    valor = evaluar_valor(ins)
    valor.to_csv(SALIDAS / "valor_de_los_datos.csv", index=False)
    bt = backtest_calibracion(ins["Rh"])
    bt.to_csv(SALIDAS / "backtest_calibracion.csv", index=False)
    print(valor[["dato", "decision"]].to_string(index=False))
    print(bt.round(3).to_string(index=False), flush=True)
    ids = list(ins["clientes"].index)
    bruto = SALIDAS / "mc_clientes_bruto.json"
    if "--desde-cache" in sys.argv and bruto.exists():
        cache = json.loads(bruto.read_text())
        res = [(cid, cache["filas"][cid], cache["clientes"][cid]) for cid in ids]
    else:
        with ProcessPoolExecutor(max_workers=len(ids)) as ex:
            res = list(ex.map(procesar_cliente, ids, [ins] * len(ids)))
        bruto.write_text(json.dumps(dict(filas={c: f for c, f, _ in res}, clientes={c: s for c, _, s in res}), ensure_ascii=False, default=JSON_DEF))
    clientes = {cid: s for cid, _, s in res}
    pd.DataFrame([f for _, fs, _ in res for f in fs]).to_csv(SALIDAS / "resultados_carteras.csv", index=False)
    pd.DataFrame([dict(cliente=cid, **x) for cid, s in clientes.items() for x in s["validacion"]["sensibilidad"]]).to_csv(SALIDAS / "sensibilidad.csv", index=False)
    (SALIDAS / "mc_resultados.json").write_text(json.dumps(dict(clientes=clientes, backtest_calibracion=bt.to_dict("records")), ensure_ascii=False, indent=1, default=JSON_DEF))
    print("simulacion guardada (sin lecturas de IA todavia)", flush=True)
    usar_llm = "--sin-llm" not in sys.argv
    for cid, s in clientes.items():
        p = s["perfil"]
        perfil = {k: p[k] for k in ("profile_name", "base_currency", "horizon_months", "risk_tolerance", "max_drawdown_tolerance_pct", "liquidity_need", "priority", "constraint")}
        r = s["robustez"]
        evid = {"presupuesto de riesgo": f"{s['presupuesto_riesgo']:.0%} de probabilidad de superar la tolerancia de caida",
                "estabilidad del ranking": r["estabilidad_ranking"]["veredicto"], "sensibilidad a los supuestos": r["sensibilidad_ruidos"]["veredicto"],
                "valor de la informacion": r["valor_informacion"]["lectura"],
                "correlacion media entre activos": "0.16 en el ultimo anio, 0.80 en el historial de estres"}
        try:
            s["lecturas_multirol"] = lecturas_cliente(cid, perfil, armar_ranking(s), evid, usar_llm=usar_llm)
        except Exception as exc:   # la IA es un refuerzo: si falla, el cliente queda con lecturas deterministas y el error queda a la vista
            import traceback
            traceback.print_exc()
            s["lecturas_multirol"] = lecturas_cliente(cid, perfil, armar_ranking(s), evid, usar_llm=False)
            s["lecturas_multirol"]["error_llm"] = f"{type(exc).__name__}: {exc}"
        print(cid, s["lecturas_multirol"]["agregacion"]["veredicto"], flush=True)
    (SALIDAS / "mc_resultados.json").write_text(json.dumps(dict(clientes=clientes, backtest_calibracion=bt.to_dict("records")),
                                                            ensure_ascii=False, indent=1, default=JSON_DEF))
    print("SQL:", ejecutar_sql(ins))
    archivos = [SALIDAS / n for n in ("resultados_carteras.csv", "mc_resultados.json", "valor_de_los_datos.csv", "backtest_calibracion.csv", "sensibilidad.csv")]
    archivos += sorted((SALIDAS / "sql").glob("*.csv")) + [a for a in [SALIDAS / "lecturas_multirol.json"] if a.exists()]
    (SALIDAS / "trazabilidad.json").write_text(json.dumps(manifiesto(ins, valor, clientes, archivos), ensure_ascii=False, indent=1, default=JSON_DEF))
    if usar_dbx and "--publicar" in sys.argv:
        print("Databricks:", databricks_io.publicar(spark, SALIDAS))
    print(f"listo en {time.time() - t0:.0f}s: {SALIDAS}")


if __name__ == "__main__":
    main()
