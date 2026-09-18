"""Superposicion de estados, al estilo de los qubits, simulada en clasico.

HONESTIDAD TECNICA: simular qubits en un computador normal NO da aceleracion. Aqui sirve para dos cosas reales:
1) superposicion_estados: el mercado como vector de estados (neutral, realizado, estres) con amplitudes; medir colapsa a uno
   (regla de Born, p = |amplitud|^2). Equivale a una mezcla de escenarios ponderada, y es util para comunicar y para la sensibilidad.
2) grover_carteras: 8 qubits = 256 combinaciones de activos en superposicion; un oraculo marca las combinaciones buenas y la
   amplificacion de amplitud (Grover) concentra la probabilidad en ellas. El oraculo se calcula con la propia Monte Carlo.
"""
import numpy as np

from config import MODOS, PROB_ESTADOS
from simulacion import evaluar, generar, resumen


def amplitudes(probs):
    a = np.sqrt([probs[m] for m in MODOS]).astype(complex)
    return a / np.linalg.norm(a)


def superposicion_estados(T_modo, M_modo, cl, rng, probs=PROB_ESTADOS):
    a = amplitudes(probs)
    p = np.abs(a) ** 2
    S = len(T_modo[MODOS[0]])
    estado = rng.choice(len(MODOS), size=S, p=p)           # medir: cada simulacion colapsa a un estado
    T, M = np.empty(S), np.empty(S)
    for k, m in enumerate(MODOS):
        sel = estado == k
        j = rng.integers(0, S, int(sel.sum()))
        T[sel], M[sel] = T_modo[m][j], M_modo[m][j]
    return dict(amplitudes=[float(x.real) for x in a], probabilidades=[float(x) for x in p], **resumen(T, M, cl.tol, cl.H))


def sensibilidad_estres(T_modo, M_modo, cl, rng, grilla=(0.0, 0.05, 0.10, 0.15, 0.20, 0.30)):
    filas = []
    for ps in grilla:
        resto = 1 - ps
        base = {"base_neutral": resto * 0.65, "base_realizado": resto * 0.35, "estres_historial_2020_2025": ps}
        x = superposicion_estados(T_modo, M_modo, cl, rng, base)
        filas.append(dict(prob_estres=ps, ret_anual_mediano=x["ret_anual_mediano"], p_mdd_sobre_tol=x["p_mdd_sobre_tol"], cvar5=x["cvar5"]))
    return filas


def grover_carteras(cl, fuentes_, ref, rng, sims=1000):
    caja = fuentes_[0].caja
    simul = [generar(f, cl.H, sims, rng) for f in fuentes_]
    N = 256
    filas = []
    for s in range(N):
        idx = [i for i in range(8) if s >> i & 1]
        for c in ([1.0] if not idx else [0.0, 0.25, 0.5, 0.75]):
            w = np.zeros(9)
            w[8] = c
            if idx:
                w[idx] = (1 - c) / len(idx)
            filas.append((s, c, w))
    W = np.array([f[2] for f in filas])
    res = [evaluar(W, ret, fxc, caja) for ret, fxc in simul]
    med = np.mean([np.median(t, 0) - 1 for t, _ in res], axis=0)
    p = np.max([(m > cl.tol).mean(0) for _, m in res], axis=0)
    ok = cl.cumple(W) & (p <= cl.alfa)
    mejor = np.full(N, -np.inf)
    donde = {}
    for k, (s, c, w) in enumerate(filas):
        if ok[k] and med[k] > mejor[s]:
            mejor[s], donde[s] = med[k], k
    factibles = np.isfinite(mejor)
    if not factibles.any():
        return dict(estados=N, factibles=0, nota="Ninguna combinacion de pesos iguales cumple las restricciones del cliente: hace falta ponderacion continua.")
    marcados = factibles & (mejor >= np.quantile(mejor[factibles], 0.90))
    M = int(marcados.sum())
    psi = np.full(N, 1 / np.sqrt(N), dtype=complex)         # superposicion uniforme de las 256 combinaciones
    iteraciones = max(1, int(np.floor(np.pi / 4 * np.sqrt(N / M))))
    for _ in range(iteraciones):
        psi[marcados] *= -1                                  # oraculo: invierte la fase de las buenas
        psi = 2 * psi.mean() - psi                           # difusion: inversion respecto al promedio
    prob = np.abs(psi) ** 2
    nombre = lambda s: [ref.index[i] for i in range(8) if s >> i & 1] or ["solo caja"]
    top = []
    for s in np.argsort(-prob)[:10]:
        k = donde.get(int(s))
        top.append(dict(activos=nombre(int(s)), prob_despues=float(prob[s]), caja=float(filas[k][1]) if k is not None else None,
                        ret_mediano=float(mejor[s]) if np.isfinite(mejor[s]) else None))
    s0 = int(np.argmax(mejor))
    return dict(estados=N, factibles=int(factibles.sum()), marcados=M, iteraciones=iteraciones,
                prob_marcados_antes=float(M / N), prob_marcados_despues=float(prob[marcados].sum()), top=top,
                mejor_clasico=dict(activos=nombre(s0), caja=float(filas[donde[s0]][1]), ret_mediano=float(mejor[s0]),
                                   prob_despues=float(prob[s0])),
                nota="Simulacion clasica de 8 qubits: sin aceleracion. El oraculo usa la propia Monte Carlo.")
