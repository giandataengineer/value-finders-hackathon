"""Robustez de la recomendacion. Portado del proyecto Nordika (scripts/analitica_avanzada.py) y adaptado a carteras:

- coherencia_informe        : el texto (de una plantilla o de un LLM) no puede contradecir a sus propias cifras.
- estabilidad_ranking       : cuanto del ganador es senal y cuanto es la semilla (30 realizaciones).
- sensibilidad_ruidos       : que pasa si se calibro mal la volatilidad, la prima de riesgo o el tipo de cambio.
- valor_informacion_estados : cuanto vale saber en que estado del mercado estamos antes de decidir (EVPI) y matriz de arrepentimiento.
"""
import re

import numpy as np

from config import PROB_ESTADOS, SEED
from simulacion import fuentes, resumen, simular_final

_ACENTOS = str.maketrans("áéíóúüñ", "aeiouun")

# (patron que aparece en el texto sin acentos ni mayusculas, condicion que lo haria falso, por que se retira)
_REGLAS = [
    (r"sin riesgo de perdida|riesgo de perdida (nulo|minimo)|capital (protegido|garantizado|asegurado)",
     lambda m: m["prob_perdida"] > 0.05, "la probabilidad de perdida supera el 5%"),
    (r"cumple (siempre |en todos los escenarios )?(con )?la tolerancia|respeta (siempre )?la caida maxima|dentro de la tolerancia",
     lambda m: m["p_mdd_mezcla"] > m["alfa"], "en la mezcla de estados la caida supera la tolerancia mas veces que el presupuesto de riesgo"),
    (r"resiste (una |la )?crisis|robust[ao] ante (una |la )?crisis|aguanta (el |un )?estres|inmune",
     lambda m: m["p_mdd_estres"] > m["alfa"], "en el escenario de estres la caida supera la tolerancia mas veces que el presupuesto"),
    (r"protege(n)? (el )?capital|preserva(cion)? (del )?capital|proteccion del capital",
     lambda m: m["p5"] < -0.10, "el percentil 5 pierde mas de 10%, no es proteccion de capital"),
    (r"supera (a |al )?(la )?(cartera )?(clasica|markowitz|tradicional)",
     lambda m: m["ret_anual"] <= m["ret_anual_mv"], "en el caso base no rinde mas que la cartera clasica"),
    (r"la diversificacion (protege|elimina|reduce el riesgo en crisis)|diversificacion (real|efectiva) en crisis",
     lambda m: m["p_mdd_estres"] > m["alfa"], "en estres la correlacion sube a 0.80 y la diversificacion no evita superar la tolerancia"),
]
_OBLIGATORIOS = ("headline", "summary")


def _norm(t):
    return t.lower().translate(_ACENTOS)


def frase_factual(nombre, m):
    base = (f"{nombre}: retorno anual mediano {m['ret_anual']:+.1%} en el caso base y {m['p_mdd']:.0%} de probabilidad de superar "
            f"la tolerancia de caida (presupuesto {m['alfa']:.0%})")
    if m["p_mdd_estres"] > m["alfa"]:
        return base + f"; en estres esa probabilidad sube a {m['p_mdd_estres']:.0%}."
    return base + "."


def coherencia_informe(informe, metricas, nombre="la cartera elegida"):
    """Revisa cada frase contra las cifras. Las frases de lista que fallan se retiran; titular y resumen se sustituyen por una
    frase construida solo con cifras verificadas. Todo queda en 'incidencias': el fallo del generador no se oculta."""
    incidencias = []
    sustituta = frase_factual(nombre, metricas)

    def revisa(frase, ruta):
        plano = _norm(frase)
        for patron, falla, motivo in _REGLAS:
            if re.search(patron, plano) and falla(metricas):
                incidencias.append(dict(ubicacion=ruta, frase=frase, motivo=motivo))
                return False
        return True

    def limpia(nodo, ruta, clave=""):
        if isinstance(nodo, str):
            return nodo if revisa(nodo, ruta) else (sustituta if clave in _OBLIGATORIOS else None)
        if isinstance(nodo, list):
            return [v for v in (limpia(x, f"{ruta}[{i}]") for i, x in enumerate(nodo)) if v is not None]
        if isinstance(nodo, dict):
            return {k: limpia(v, f"{ruta}.{k}" if ruta else k, k) for k, v in nodo.items()}
        return nodo

    return dict(informe=limpia(informe, ""), incidencias=incidencias, frases_retiradas=len(incidencias), frase_sustituta=sustituta)


def _ganador(nombres, validas, med, p, alfa):
    """Mejor retorno entre las carteras validas que cumplen el presupuesto; si ninguna cumple, la de menor probabilidad."""
    idx = [i for i in range(len(nombres)) if validas[i]]
    ok = [i for i in idx if p[i] <= alfa]
    return max(ok, key=lambda i: med[i]) if ok else min(idx, key=lambda i: p[i])


def _evaluar_pares(cl, W, pares, rng, sims):
    med, p = [], []
    for F in pares:
        T, M, _ = simular_final(cl, W, F, rng, sims)
        med.append(np.median(T, 0) - 1)
        p.append((M > cl.tol).mean(0))
    return np.mean(med, axis=0), np.max(p, axis=0)


def estabilidad_ranking(cl, W, nombres, pares, semillas=30, sims=2000):
    """Repite solo la capa Monte Carlo con 30 semillas y cuenta cuantas veces gana cada cartera (validas y dentro del presupuesto)."""
    validas = cl.cumple(W)
    vic, pos, vals = {n: 0 for n in nombres}, {n: [] for n in nombres}, {n: [] for n in nombres}
    for s in range(semillas):
        med, p = _evaluar_pares(cl, W, pares, np.random.default_rng([SEED, 501, s]), sims)
        g = _ganador(nombres, validas, med, p, cl.alfa)
        vic[nombres[g]] += 1
        orden = np.argsort(-med)
        for r, i in enumerate(orden):
            pos[nombres[i]].append(r + 1)
            vals[nombres[i]].append(float(med[i]))
    detalle = [dict(cartera=n, victorias=vic[n], tasa_victoria=vic[n] / semillas, posicion_media=float(np.mean(pos[n])),
                    ret_mediano_medio=float(np.mean(vals[n])), ret_mediano_min=float(np.min(vals[n])), ret_mediano_max=float(np.max(vals[n])))
               for n in nombres]
    detalle.sort(key=lambda d: -d["tasa_victoria"])
    lider = detalle[0]
    return dict(realizaciones=semillas, detalle=detalle, ganador_estable=lider["tasa_victoria"] >= 0.80,
                veredicto=f"{lider['cartera']} gana en {lider['victorias']} de {semillas} realizaciones",
                alcance="varia la semilla del Monte Carlo; los datos y los supuestos se mantienen fijos")


def sensibilidad_ruidos(cl, W, nombres, ins, sims=1500):
    """Escala cada ruido por separado y mira si la cartera ganadora aguanta dentro del presupuesto de riesgo."""
    validas = cl.cumple(W)
    grillas = [("volatilidad de los activos", "escala_vol", (0.75, 1.0, 1.25, 1.5, 2.0), 1.0),
               ("prima de riesgo", "erp", (0.0, 0.02, 0.04, 0.06, 0.08), 0.04),
               ("volatilidad del tipo de cambio", "escala_fx", (0.5, 1.0, 2.0, 3.0), 1.0)]
    base = None
    resultados = []
    for etiqueta, param, factores, neutro in grillas:
        puntos = []
        for f in factores:
            F = fuentes(ins, cl, **{param: f})
            med, p = _evaluar_pares(cl, W, [F["base_neutral"], F["base_realizado"]], np.random.default_rng([SEED, 601, int(f * 100)]), sims)
            g = _ganador(nombres, validas, med, p, cl.alfa)
            if base is None and f == neutro:
                base = g
            puntos.append(dict(factor=f, ganador=nombres[g], p_mdd_del_ganador_base=None if base is None else float(p[base]), _g=g, _p=p))
        for pt in puntos:
            pt["cambia"] = base is not None and pt["_g"] != base
            pt["base_fuera_de_presupuesto"] = base is not None and bool(pt["_p"][base] > cl.alfa)
            pt["p_mdd_del_ganador_base"] = float(pt["_p"][base])
            del pt["_g"], pt["_p"]
        quiebre = next((pt["factor"] for pt in sorted(puntos, key=lambda x: abs(x["factor"] - neutro))
                        if pt["cambia"] or pt["base_fuera_de_presupuesto"]), None)
        resultados.append(dict(ruido=etiqueta, punto_de_quiebre=quiebre, puntos=puntos))
    frag = [r["ruido"] for r in resultados if r["punto_de_quiebre"] is not None]
    return dict(ganador_base=nombres[base], resultados=resultados, robusto=not frag,
                veredicto="La recomendacion aguanta todas las variaciones probadas" if not frag
                else "La recomendacion deja de cumplir o cambia al mover: " + ", ".join(frag))


def valor_informacion_estados(nombres, T_por_modo, probs=PROB_ESTADOS):
    """EVPI sobre los estados del mercado: cuanto vale saber si estamos en el escenario neutral, el realizado o el de estres
    antes de elegir cartera. Incluye la matriz de arrepentimiento y la cartera de minimo arrepentimiento maximo (minimax)."""
    modos = list(T_por_modo)
    E = np.array([[T_por_modo[m][:, k].mean() - 1 for m in modos] for k in range(len(nombres))])   # (carteras, estados)
    p = np.array([probs[m] for m in modos], float)
    p /= p.sum()
    esperado = E @ p
    i_sin = int(np.argmax(esperado))
    con = float((E.max(axis=0) * p).sum())
    arrep = E.max(axis=0) - E
    i_mm = int(np.argmin(arrep.max(axis=1)))
    return dict(estados=modos, probabilidades=p.tolist(), decision_sin_informacion=nombres[i_sin], retorno_esperado_sin_informacion=float(esperado[i_sin]),
                retorno_esperado_con_informacion_perfecta=con, evpi=con - float(esperado[i_sin]),
                mejor_por_estado={m: nombres[int(np.argmax(E[:, j]))] for j, m in enumerate(modos)},
                cartera_minimo_arrepentimiento=nombres[i_mm], arrepentimiento_maximo=float(arrep.max(axis=1)[i_mm]),
                matriz_retorno_esperado={n: dict(zip(modos, map(float, E[k]))) for k, n in enumerate(nombres)},
                lectura=(f"Saber de antemano en que estado estamos vale como maximo {con - float(esperado[i_sin]):+.1%} de retorno acumulado. "
                         f"Sin esa informacion la mejor apuesta es '{nombres[i_sin]}'; la de minimo arrepentimiento es '{nombres[i_mm]}'."))
