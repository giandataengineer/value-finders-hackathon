"""Validacion de la simulacion: calibracion del metodo, sensibilidad a los supuestos y estabilidad entre semillas."""
import numpy as np
import pandas as pd
from scipy import stats

from config import SEED
from simulacion import Fuente, fuentes, generar, resumen, simular_final


def _mdd(V):
    peak = np.maximum(np.maximum.accumulate(V, axis=-1), 1.0)
    return (1 - V / peak).max(axis=-1)


def backtest_calibracion(Rh, ventana=250, horizonte=63, paso=21, sims=2000):
    """Pone a prueba el METODO (no la deriva): entrena con 250 dias, simula los 63 siguientes de una cartera igual
    ponderada y mira en que percentil de la simulacion cayo lo que realmente paso, tanto en retorno como en caida maxima
    (que es lo que usan las decisiones). Bien calibrado = ~90% entre P5 y P95 y ~5% de exceso sobre P95 en la caida."""
    rng = np.random.default_rng(SEED)
    X = Rh.values
    metodos = ["normal multivariada", "bootstrap iid", "bloques de 5 dias", "bloques de 21 dias"]
    pit_r = {m: [] for m in metodos}
    pit_d = {m: [] for m in metodos}
    ancho = {m: [] for m in metodos}
    for t in range(ventana, len(X) - horizonte, paso):
        tr = X[t - ventana:t] - X[t - ventana:t].mean(0)
        r_real = np.expm1(X[t:t + horizonte]).mean(1)
        real_ret, real_dd = np.prod(1 + r_real) - 1, _mdd(np.cumprod(1 + r_real))
        z = np.zeros(8)
        sim = {metodos[0]: np.expm1(rng.multivariate_normal(z, np.cov(tr.T), size=(sims, horizonte)))}
        for m, b in zip(metodos[1:], (1, 5, 21)):
            sim[m] = generar(Fuente(tr, z, None, 0.0, b), horizonte, sims, rng)[0]
        for m in metodos:
            e = sim[m].mean(axis=2)
            V = np.cumprod(1 + e, axis=1)
            r, dd = V[:, -1] - 1, _mdd(V)
            pit_r[m].append(float((r <= real_ret).mean()))
            pit_d[m].append(float((dd <= real_dd).mean()))
            ancho[m].append(float(np.quantile(r, 0.95) - np.quantile(r, 0.05)))
    filas = []
    for m in metodos:
        p, d = np.array(pit_r[m]), np.array(pit_d[m])
        filas.append(dict(metodo=m, origenes=len(p), cobertura_90_retorno=float(((p >= 0.05) & (p <= 0.95)).mean()),
                          ancho_medio_intervalo_90=float(np.mean(ancho[m])), p_ks_retorno=float(stats.kstest(p, "uniform").pvalue),
                          caida_real_sobre_p95_simulado=float((d > 0.95).mean()), caida_real_bajo_p05_simulado=float((d < 0.05).mean()),
                          p_ks_caida=float(stats.kstest(d, "uniform").pvalue)))
    return pd.DataFrame(filas)


def sensibilidad(cl, w, ins, sims=5000):
    """La cartera evaluada con otros supuestos: largo de bloque y prima de riesgo (caso base neutral)."""
    filas = []
    for bloque in (1, 5, 10, 21):
        for erp in (0.02, 0.04, 0.06):
            F = fuentes(ins, cl, erp)["base_neutral"]
            T, M, _ = simular_final(cl, w[None, :], F, np.random.default_rng([SEED, 77, bloque, int(erp * 100)]), sims, bloque)
            r = resumen(T[:, 0], M[:, 0], cl.tol, cl.H)
            filas.append(dict(bloque=bloque, prima_riesgo=erp, ret_anual_mediano=r["ret_anual_mediano"], p_mdd_sobre_tol=r["p_mdd_sobre_tol"]))
    return filas


def estabilidad_semillas(cl, w, ins, semillas=5, sims=5000):
    """Mismo caso con 5 semillas distintas: cuanto se mueven las metricas por puro azar del Monte Carlo."""
    F = fuentes(ins, cl)["base_neutral"]
    p, r = [], []
    for s in range(semillas):
        T, M, _ = simular_final(cl, w[None, :], F, np.random.default_rng([SEED, 88, s]), sims)
        x = resumen(T[:, 0], M[:, 0], cl.tol, cl.H)
        p.append(x["p_mdd_sobre_tol"])
        r.append(x["ret_anual_mediano"])
    return dict(semillas=semillas, p_mdd_media=float(np.mean(p)), p_mdd_desv=float(np.std(p)), ret_anual_media=float(np.mean(r)), ret_anual_desv=float(np.std(r)))
