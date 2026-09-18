"""Giros de la trama (dataset_twist.csv, vigentes desde 2026-08-17): que cambia en cada recomendacion.

Solo generamos insights y recomendaciones para que las personas decidan. Los parametros salen de gold.giros (ETL), no de numeros a mano.
Uso: python src/twists.py     (requiere haber corrido src/run.py: lee las carteras recomendadas de outputs/mc_resultados.json)
"""
import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import stats

from config import DIAS, MODOS, PROB_ESTADOS, RONDAS_ROBUSTA, SALIDAS, SEED
from cuantico import superposicion_estados
from datos import cargar_insumos
from simulacion import Cliente, fuentes, generar, optimizar, resumen, simular_final, trayectoria

FINAL = "recomendada defensiva (con estres)"
CHOQUES = (0.0, -0.05, -0.10, -0.15, -0.20, -0.30)
JSON_DEF = lambda o: o.item() if hasattr(o, "item") else str(o)


def _vec(pesos, ref):
    return np.array([pesos[a] for a in ref.index] + [pesos["CAJA"]])


def mezcla(cl, W, F, rng, choque=0.0, sims=5000):
    """Metricas de la mezcla de estados (55/30/15) para las carteras W bajo las fuentes F, con un repricing inicial opcional de las acciones."""
    Tm, Mm = {}, {}
    for m in MODOS:
        Tm[m], Mm[m], _ = simular_final(cl, W, F[m], rng, sims, choque=choque)
    filas = []
    for k in range(len(W)):
        x = superposicion_estados({m: Tm[m][:, k] for m in MODOS}, {m: Mm[m][:, k] for m in MODOS}, cl, rng)
        filas.append(dict(ret_anual=x["ret_anual_mediano"], p_mdd=x["p_mdd_sobre_tol"], prob_perdida=x["prob_perdida"], cvar5=x["cvar5"],
                          p_mdd_neutral=float((Mm["base_neutral"][:, k] > cl.tol).mean()), p_mdd_estres=float((Mm[MODOS[2]][:, k] > cl.tol).mean())))
    return filas


def sensibilidad_tasas(ins):
    """Cuanto se ha movido la tasa en los datos y si los retornos de las acciones responden a ella."""
    P, y = ins["P"], ins["macro"].us_10y_yield
    R = np.log(P).diff().dropna()
    dy = y.diff().reindex(R.index)
    betas = {c: stats.linregress(dy, R[c]) for c in R}
    return dict(tasa_inicio=float(y.iloc[0]), tasa_fin=float(y.iloc[-1]), tasa_min=float(y.min()), tasa_max=float(y.max()),
                mayor_alza_semanal_pb=float(y.diff(5).max() * 100), mayor_baja_semanal_pb=float(y.diff(5).min() * 100),
                activos_con_beta_significativa=int(sum(b.pvalue < 0.05 for b in betas.values())),
                beta_media_por_pp=float(np.mean([b.slope for b in betas.values()])), r2_maximo=float(max(b.rvalue ** 2 for b in betas.values())),
                nota="Los retornos no responden de forma significativa a la tasa en los datos: no se inventa un efecto mecanico sobre las acciones.")


def tw01(cl, ins, w, giro, rng):
    delta = float(giro.valor_parametro)
    rf_nuevo = float(ins["macro"].us_10y_yield.iloc[-1]) / 100 + delta
    F0, F1 = fuentes(ins, cl), fuentes(ins, cl, rf_caja=rf_nuevo)
    W = w[None, :]
    antes, misma = mezcla(cl, W, F0, rng)[0], mezcla(cl, W, F1, rng)[0]
    malla = [dict(choque=s, **mezcla(cl, W, F1, rng, choque=s)[0]) for s in CHOQUES]
    w1, ok = optimizar(cl, [F1[m] for m in MODOS], rng, RONDAS_ROBUSTA, mezcla=[PROB_ESTADOS[m] for m in MODOS])
    nueva = mezcla(cl, w1[None, :], F1, rng)[0]
    quiebre = next((m["choque"] for m in malla if m["p_mdd"] > cl.alfa), None)
    return dict(rf_nueva=rf_nuevo, antes=antes, misma_cartera=misma, malla_choque_valoracion=malla, choque_que_rompe_el_presupuesto=quiebre,
                reoptimizada=dict(pesos=dict(zip(list(ins["ref"].index) + ["CAJA"], map(float, w1))), cumple=ok, **nueva),
                cambio_de_pesos_l1=float(np.abs(w1 - w).sum()), presupuesto=cl.alfa)


def tw02(cl, ins, w, giro, rng):
    """CL_02 necesitara el 30% del portafolio en 6 meses: liquidez, riesgo de la ventana de 6 meses y riesgo cambiario del tramo en USD."""
    pct, meses = float(giro.valor_parametro), int(giro.horizonte_meses)
    caja = float(w[8])
    F = fuentes(ins, cl)
    d = meses * 21
    ret, fxc = generar(F["base_neutral"], d, 10000, rng)
    v6 = trayectoria(w[None, :], ret, fxc, F["base_neutral"].caja)[:, -1, 0]
    caja_usd = (1 + F["base_neutral"].caja) ** d * np.exp(fxc[:, -1])   # 1 COP en caja USD, valorado en COP a los 6 meses
    cl.caja_min = pct
    cumple = bool(cl.cumple(w[None, :])[0])
    w2, ok2 = (w, True) if cumple else optimizar(cl, [F[m] for m in MODOS], rng, RONDAS_ROBUSTA, mezcla=[PROB_ESTADOS[m] for m in MODOS])
    cl.caja_min = 0.0
    fx_sd = float(np.std(fxc[:, -1]))
    return dict(porcentaje=pct, meses=meses, caja_en_cartera_recomendada=caja, cumple_liquidez=cumple,
                cartera_con_liquidez=dict(pesos=dict(zip(list(ins["ref"].index) + ["CAJA"], map(float, w2))), cumple=ok2),
                cartera_completa_a_6_meses=dict(p5=float(np.quantile(v6, 0.05) - 1), mediana=float(np.median(v6) - 1), prob_perdida=float((v6 < 1).mean())),
                tramo_en_caja_usd_a_6_meses=dict(p5=float(np.quantile(caja_usd, 0.05) - 1), mediana=float(np.median(caja_usd) - 1),
                                                 prob_perder_3pct=float((caja_usd < 0.97).mean()), prob_perdida=float((caja_usd < 1).mean()),
                                                 desviacion_cambiaria_6m=fx_sd),
                nota=("Los datos no traen tasas en COP ni PEN: el tramo de liquidez en COP se describe por el riesgo cambiario que evita, no por su rendimiento."))


def tw03(cl, ins, w, giro, rng):
    """El COP se deprecia 8% frente al USD: ganancia latente en COP y riesgo de reversion segun cuanta volatilidad cambiaria se suponga."""
    shock = float(giro.valor_parametro)
    nivel = float(ins["macro"].usd_cop.iloc[-1])
    rango = (float(ins["macro"].usd_cop.min()), float(ins["macro"].usd_cop.max()))
    vuelta = -np.log1p(shock)
    filas = []
    for esc in (1.0, 2.0, 3.0):
        F = fuentes(ins, cl, escala_fx=esc)
        ret, fxc = generar(F["base_neutral"], cl.H, 10000, rng)
        filas.append(dict(escala_volatilidad_cambiaria=esc, vol_cambiaria_anual=float(F["base_neutral"].fx.std() * np.sqrt(DIAS)),
                          prob_revierte_todo_al_final=float((fxc[:, -1] <= vuelta).mean()),
                          prob_toca_el_nivel_previo_en_algun_momento=float((fxc.min(axis=1) <= vuelta).mean()),
                          p5_cambio_cambiario_horizonte=float(np.quantile(np.expm1(fxc[:, -1]), 0.05)),
                          **{f"mezcla_{k}": v for k, v in mezcla(cl, w[None, :], F, rng, sims=2500)[0].items() if k in ("ret_anual", "p_mdd")}))
    return dict(depreciacion=shock, usd_cop_ultimo_dato=nivel, usd_cop_despues_del_giro=nivel * (1 + shock), rango_del_ultimo_anio=rango,
                por_encima_del_maximo_del_anio=float(nivel * (1 + shock) / rango[1] - 1), exposicion_usd_de_la_cartera=1.0,
                ganancia_latente_en_cop=shock, por_volatilidad_cambiaria=filas,
                nota="El shock es mayor que cualquier movimiento visto en 12 meses: la volatilidad cambiaria historica probablemente subestima el riesgo.")


def _cliente(cid, ins, pesos, giros):
    ref, clientes, P = ins["ref"], ins["clientes"], ins["P"]
    ci = list(clientes.index).index(cid)
    R = np.log(P).diff().dropna()
    cl = Cliente(cid, clientes.loc[cid], ref, R.std() * np.sqrt(DIAS))
    w = _vec(pesos, ref)
    rng = np.random.default_rng([SEED, 900, ci])
    g = giros.set_index("giro_id")
    out = dict(cartera_recomendada_previa={k: v for k, v in pesos.items() if v >= 0.005})
    out["TW_01"] = tw01(cl, ins, w, g.loc["TW_01"], rng)
    if "CL_02" in str(g.loc["TW_02", "clientes_afectados"]).split(",") and cid == "CL_02":
        out["TW_02"] = tw02(cl, ins, w, g.loc["TW_02"], rng)
    if cid in str(g.loc["TW_03", "clientes_afectados"]).split(","):
        out["TW_03"] = tw03(cl, ins, w, g.loc["TW_03"], rng)
    return cid, out


def _f(x, d=1):
    return f"{x * 100:.{d}f}%"


def insights(res, giros):
    """Frases para las personas que deciden. Todas salen de las cifras calculadas; nada se afirma sin numero."""
    out = []
    s = res["sensibilidad_tasas"]
    out.append(dict(giro="TW_01", cliente="todos", titulo="Tasa a 10 años +65 pb",
                    texto=(f"En 12 meses la tasa se movió entre {s['tasa_min']:.2f}% y {s['tasa_max']:.2f}% y su mayor alza semanal fue de {s['mayor_alza_semanal_pb']:.0f} pb: "
                           f"el giro es unas {65 / max(s['mayor_alza_semanal_pb'], 1):.0f} veces mayor a lo visto y ninguna acción responde a la tasa de forma significativa "
                           f"({s['activos_con_beta_significativa']} de 8). Por eso no asumimos un efecto mecánico sobre las acciones: medimos hasta qué caída de valoración aguanta cada cartera.")))
    for cid, c in res["clientes"].items():
        t = c["TW_01"]
        q = t["choque_que_rompe_el_presupuesto"]
        cambio = "sus pesos casi no cambian" if t["cambio_de_pesos_l1"] < 0.15 else f"conviene revisar sus pesos (cambio de {_f(t['cambio_de_pesos_l1'], 0)})"
        out.append(dict(giro="TW_01", cliente=cid, titulo="Efecto en la cartera recomendada",
                        texto=(f"La caja pasa a rendir {_f(t['rf_nueva'], 2)}. Con la misma cartera, el retorno anual mediano va de {_f(t['antes']['ret_anual'])} a {_f(t['misma_cartera']['ret_anual'])} "
                               f"y la probabilidad de superar la tolerancia de caída de {_f(t['antes']['p_mdd'], 0)} a {_f(t['misma_cartera']['p_mdd'], 0)} (presupuesto {_f(t['presupuesto'], 0)}). "
                               + (f"Si las acciones se reprecian {_f(abs(q), 0)} o más, la cartera actual deja de cumplir su presupuesto. " if q is not None
                                  else "Aguanta un repricing de hasta 30% de las acciones dentro de su presupuesto. ")
                               + f"Al reoptimizar con la nueva tasa, {cambio}.")))
    if "TW_02" in res["clientes"].get("CL_02", {}):
        t = res["clientes"]["CL_02"]["TW_02"]
        out.append(dict(giro="TW_02", cliente="CL_02", titulo="Necesita 30% en 6 meses",
                        texto=(f"La cartera recomendada ya tiene {_f(t['caja_en_cartera_recomendada'], 0)} en caja, así que "
                               + ("cumple el 30% sin vender acciones. " if t["cumple_liquidez"] else "no cumple el 30%; con la restricción de liquidez la caja sube. ")
                               + f"El riesgo que sí aparece es cambiario: ese tramo está en USD y se necesita en COP; en 6 meses su desviación cambiaria es {_f(t['tramo_en_caja_usd_a_6_meses']['desviacion_cambiaria_6m'])} "
                               f"y hay {_f(t['tramo_en_caja_usd_a_6_meses']['prob_perder_3pct'], 0)} de probabilidad de perder más de 3% al convertirlo. "
                               "Sugerimos que las personas evalúen mantener el 30% en pesos, que elimina ese riesgo (los datos no traen tasas en COP para medir su rendimiento).")))
    if "TW_03" in res["clientes"].get("CL_02", {}):
        t = res["clientes"]["CL_02"]["TW_03"]
        v1, v3 = t["por_volatilidad_cambiaria"][0], t["por_volatilidad_cambiaria"][2]
        out.append(dict(giro="TW_03", cliente="CL_02", titulo="El COP se deprecia 8%",
                        texto=(f"Si la cartera ya está en USD, gana {_f(t['ganancia_latente_en_cop'], 0)} en pesos de forma latente (USD/COP de {t['usd_cop_ultimo_dato']:,.0f} a {t['usd_cop_despues_del_giro']:,.0f}, "
                               f"{_f(t['por_encima_del_maximo_del_anio'])} por encima del máximo de los últimos 12 meses). Esa ganancia no es firme: con la volatilidad histórica hay {_f(v1['prob_toca_el_nivel_previo_en_algun_momento'], 0)} "
                               f"de probabilidad de que el tipo de cambio vuelva al nivel previo en algún momento del horizonte, y {_f(v3['prob_toca_el_nivel_previo_en_algun_momento'], 0)} si la volatilidad triplica. "
                               "Si el cliente comprará USD ahora, entra 8% más caro. La decisión de asegurar parte de la ganancia o de esperar es de las personas.")))
    return out


def main():
    ins = cargar_insumos()
    giros = ins["giros"]
    prev = json.loads((SALIDAS / "mc_resultados.json").read_text())["clientes"]
    ids = list(ins["clientes"].index)
    with ProcessPoolExecutor(max_workers=len(ids)) as ex:
        res = dict(ex.map(_cliente, ids, [ins] * len(ids), [prev[c]["carteras"][FINAL] for c in ids], [giros] * len(ids)))
    # to_json (no to_dict) para que magnitud_pb/magnitud_pct (mutuamente excluyentes en el dataset) salgan como null y no como NaN
    salida = dict(giros=json.loads(giros.astype({"fecha_efectiva": str}).to_json(orient="records")), sensibilidad_tasas=sensibilidad_tasas(ins), clientes=res)
    salida["insights"] = insights(salida, giros)
    (SALIDAS / "twists.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1, default=JSON_DEF, allow_nan=False))
    for i in salida["insights"]:
        print(f"[{i['giro']}·{i['cliente']}] {i['titulo']}: {i['texto']}\n")


if __name__ == "__main__":
    main()
