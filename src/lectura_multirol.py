"""Tres lecturas independientes de cada recomendacion (Gestor, Riesgo, Asesor), cada una con su propio modelo de IA.

Portado de Nordika (scripts/agente_multirol.py): un proveedor y un modelo distintos por rol con anticolision, enfriamiento tras un
429, cadena de reemplazo completa, guardarrail de coherencia sobre lo que escribe cada modelo y camino determinista sin claves.
Un rol PUEDE elegir una cartera distinta a la de los otros: ese desacuerdo es lo que hace informativa la comparacion.
"""
import hashlib
import json
import os
import re
import time
from typing import Any

from config import ENV_FALLBACK, RAIZ, SALIDAS
from robustez import coherencia_informe

CACHE = SALIDAS / "lecturas_multirol.json"


def cargar_claves():
    from dotenv import load_dotenv
    for ruta in (RAIZ / ".env", ENV_FALLBACK):
        if ruta.exists():
            load_dotenv(ruta, override=False)


PROVEEDORES = {   # todos hablan el protocolo de OpenAI: cambian clave, base_url y modelo por defecto
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1", "qwen/qwen3.6-27b"),
    "cerebras": ("CEREBRAS_API_KEY", "https://api.cerebras.ai/v1", "gpt-oss-120b"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "z-ai/glm-5.2:free"),
    "gemini": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-3.6-flash"),
    "zai": ("ZAI_API_KEY", "https://api.z.ai/api/paas/v4", "glm-4.5-flash"),
    "nvidia": ("NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1", "deepseek-ai/deepseek-v3"),
    "mistral": ("MISTRAL_API_KEY", "https://api.mistral.ai/v1", "mistral-small-latest"),
}

CATALOGO = {   # de mas capaz a mas ligero; solo variantes gratuitas en OpenRouter
    "gemini": ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3-flash-preview", "gemini-3.5-flash-lite"],
    "groq": ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "openai/gpt-oss-20b", "groq/compound", "groq/compound-mini"],
    "openrouter": ["nvidia/nemotron-3-ultra-550b-a55b:free", "nvidia/nemotron-3-super-120b-a12b:free", "z-ai/glm-5.2:free",
                   "google/gemma-4-31b-it:free", "nvidia/nemotron-3.5-lightning:free", "openai/gpt-oss-20b:free"],
    "cerebras": ["gpt-oss-120b", "gemma-4-31b"],
    "mistral": ["mistral-large-latest", "mistral-medium-latest", "magistral-medium-latest", "mistral-small-latest", "ministral-14b-latest"],
    "zai": ["glm-4.5-flash", "glm-4.7-flash"],
    "nvidia": ["nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3-super-120b-a12b", "deepseek-ai/deepseek-v4-flash-0731",
               "meta/llama-3.1-70b-instruct", "nvidia/llama-3.3-nemotron-super-49b-v1.5"],
}

_ENFRIANDO, _ESPERA_429 = {}, 90.0


def _frio(clave):
    hasta = _ENFRIANDO.get(clave)
    if hasta is None:
        return False
    if time.time() >= hasta:
        _ENFRIANDO.pop(clave, None)
        return False
    return True


ROLES = {
    "gestor": dict(etiqueta="Gestor", proveedor="groq", modelo="qwen/qwen3.6-27b",
                   prioriza="retorno mediano dentro de las restricciones del cliente y una asignacion que se pueda defender ante un comite",
                   sistema=("Eres el gestor de portafolio de una firma de inversion. Decides la asignacion del cliente. Te importa el retorno "
                            "mediano dentro de las restricciones y del presupuesto de riesgo, y poder defender cada peso ante un comite. Sabes que "
                            "doce meses de datos son pocos y que el ganador reciente no es necesariamente el mejor. No eres el mas agresivo ni el "
                            "mas prudente: eres quien responde por la asignacion.")),
    "riesgo": dict(etiqueta="Riesgo", proveedor="gemini", modelo="gemini-3.6-flash",
                   prioriza="caida maxima, colas y comportamiento en estres",
                   sistema=("Eres el director de riesgos. No maximizas el retorno: evitas que el cliente sufra una caida que no puede tolerar. "
                            "Miras la probabilidad de superar la tolerancia de caida, el peor 5% y el escenario de estres antes que el retorno "
                            "mediano. Sabes que en crisis la correlacion entre activos sube y la diversificacion protege menos de lo que parece. "
                            "Discrepa abiertamente si la mejor cartera del caso base no es la mas defendible en estres.")),
    "asesor": dict(etiqueta="Asesor", proveedor="openrouter", modelo="nvidia/nemotron-3-super-120b-a12b:free",
                   prioriza="encaje con el perfil, la moneda base y el horizonte del cliente, y una explicacion que el cliente entienda",
                   sistema=("Eres el asesor que habla con el cliente. Te importa que la recomendacion encaje con su perfil, su moneda base, su "
                            "horizonte y su necesidad de liquidez, y que el cliente entienda por que se le propone. Desconfias de las carteras que "
                            "solo se explican con formulas. Estas dispuesto a discrepar de gestion o de riesgo si la opcion elegida no se le puede "
                            "explicar con claridad.")),
}

ESQUEMA = """Devuelve exclusivamente JSON valido, sin markdown ni bloques de codigo:
{
  "decision_elegida": "el nombre exacto de una de las carteras del ranking",
  "headline": "una frase con tu veredicto",
  "summary": "dos o tres frases justificando desde tu angulo",
  "reasons": ["tres razones"],
  "watchouts": ["tres cosas a vigilar"],
  "next_actions": ["tres siguientes pasos"],
  "switch_signals": ["tres senales que te harian cambiar de opinion"]
}

Reglas duras:
- decision_elegida DEBE ser una de las carteras del ranking, copiada literal.
- Puedes elegir una cartera distinta a la que lidera si tu criterio lo justifica.
- No afirmes que una cartera cumple la tolerancia si su probabilidad de superarla es mayor que el presupuesto de riesgo.
- No digas que resiste una crisis si en estres supera la tolerancia mas veces que el presupuesto.
- Cita cifras concretas del ranking cuando sustenten tu argumento.
- Escribe en espanol ejecutivo, sin markdown."""


def candidatos(rol, ya_usados):
    """Pares (proveedor, modelo) que el rol puede intentar. Cada rol arranca en un proveedor distinto; los modelos que otro rol
    ya uso bajan al final porque dos roles sobre el mismo modelo no son dos opiniones."""
    cfg = ROLES[rol]
    orden = list(PROVEEDORES)
    i = orden.index(cfg["proveedor"])
    orden = orden[i:] + orden[:i]
    pref, resto, repetidos = [], [], []
    for prov in orden:
        if not os.getenv(PROVEEDORES[prov][0]):
            continue
        for modelo in CATALOGO.get(prov, [PROVEEDORES[prov][2]]):
            if _frio(f"{prov}/{modelo}"):
                continue
            if modelo in ya_usados:
                repetidos.append((prov, modelo))
            elif prov == cfg["proveedor"] and modelo == cfg["modelo"]:
                pref.append((prov, modelo))
            else:
                resto.append((prov, modelo))
    return pref + resto + repetidos


def _sin_vallas(texto):
    if "<think>" in texto and "</think>" not in texto:
        raise ValueError("respuesta truncada: el modelo no cerro su razonamiento")
    limpio = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()
    if "```" in limpio and len(limpio.split("```")) > 1:
        limpio = limpio.split("```")[1]
        limpio = limpio.lstrip()[4:] if limpio.lstrip().startswith("json") else limpio
    limpio = limpio.strip()
    if not limpio.startswith("{"):
        i, j = limpio.find("{"), limpio.rfind("}")
        if i != -1 and j > i:
            limpio = limpio[i:j + 1]
    return limpio


def _una_llamada(prov, modelo, rol, prompt, timeout=45.0):
    from openai import OpenAI
    env, base_url, _ = PROVEEDORES[prov]
    cliente = OpenAI(api_key=os.getenv(env), base_url=base_url)
    kw = dict(model=modelo, temperature=0.4, timeout=timeout, max_tokens=2600,
              messages=[{"role": "system", "content": ROLES[rol]["sistema"]}, {"role": "user", "content": prompt}])
    try:
        r = cliente.chat.completions.create(**kw, response_format={"type": "json_object"})
    except Exception:
        r = cliente.chat.completions.create(**kw)   # no todos los proveedores admiten JSON forzado
    return json.loads(_sin_vallas(r.choices[0].message.content or ""))


def _contexto(perfil, ranking, evidencia):
    partes = ["Cliente:", json.dumps(perfil, ensure_ascii=False), "", "Carteras candidatas y resultados tras simular (retornos anualizados; p_mdd = probabilidad de que la caida maxima supere la tolerancia):",
              json.dumps(ranking, ensure_ascii=False, indent=1)]
    if evidencia:
        partes += ["", "Evidencia sobre la solidez del resultado:"] + [f"- {k}: {v}" for k, v in evidencia.items()]
    return "\n".join(partes)


def consultar_rol(rol, perfil, ranking, evidencia, ya_usados):
    prompt = f"{_contexto(perfil, ranking, evidencia)}\n\nPrioriza {ROLES[rol]['prioriza']}.\n\n{ESQUEMA}"
    validas = {r["decision"] for r in ranking}
    intentos = []
    for prov, modelo in candidatos(rol, ya_usados):
        try:
            datos = _una_llamada(prov, modelo, rol, prompt)
        except Exception as exc:
            if "RateLimit" in type(exc).__name__ or "429" in str(exc):
                _ENFRIANDO[f"{prov}/{modelo}"] = time.time() + _ESPERA_429
            intentos.append(f"{prov}/{modelo}: {type(exc).__name__}")
            continue
        if str(datos.get("decision_elegida", "")).strip() not in validas:
            intentos.append(f"{prov}/{modelo}: eligio {datos.get('decision_elegida')!r}, que no esta en el ranking")
            continue
        datos.update(rol=rol, fuente="llm", proveedor=prov, modelo=modelo, intentos_previos=len(intentos))
        return datos
    return dict(rol=rol, fuente="determinista", motivo=f"agotados {len(intentos)} modelos" if intentos else "sin claves de API", intentos=intentos[:6])


def lectura_determinista(rol, ranking):
    """Sin LLM: cada rol aplica su criterio a las cifras. Coinciden o no segun los numeros, no segun un modelo."""
    validas = [r for r in ranking if r["cumple_restricciones"]] or ranking
    if rol == "gestor":
        dentro = [r for r in validas if r["p_mdd_mezcla"] <= r["alfa"]] or validas
        r = max(dentro, key=lambda x: x["ret_anual_mezcla"])
        why = "mayor retorno mediano de la mezcla de estados entre las carteras que cumplen restricciones y presupuesto"
    elif rol == "riesgo":
        r = min(validas, key=lambda x: (x["p_mdd_estres"], -x["ret_anual_mezcla"]))
        why = "menor probabilidad de superar la tolerancia en el escenario de estres entre las carteras que cumplen restricciones"
    else:
        cand = [x for x in validas if x["decision"].startswith("recomendada")]
        r = max(cand, key=lambda x: x["ret_anual_mezcla"]) if cand else validas[0]
        why = "es la propuesta del modelo con sus restricciones cumplidas y la explicacion mas directa"
    return dict(rol=rol, fuente="determinista", decision_elegida=r["decision"],
                headline=f"{ROLES[rol]['etiqueta']}: {r['decision']}",
                summary=(f"Se elige por {why}. Retorno anual mediano de la mezcla {r['ret_anual_mezcla']:+.1%}, probabilidad de superar la tolerancia "
                         f"{r['p_mdd_mezcla']:.0%} en la mezcla y {r['p_mdd_estres']:.0%} en estres (presupuesto {r['alfa']:.0%})."))


def agregar(lecturas):
    """El desacuerdo es el dato: significa que la eleccion depende de que se prioriza y no solo de los numeros."""
    con_llm = [l for l in lecturas if l.get("fuente") == "llm"]
    elecciones = {l["rol"]: l["decision_elegida"] for l in lecturas if l.get("decision_elegida")}
    distintas = set(elecciones.values())
    indep = len({l["modelo"] for l in con_llm}) == len(con_llm) and len(con_llm) > 1
    if not con_llm:
        return dict(modo="determinista", consenso=len(distintas) == 1, elecciones=elecciones, roles_con_llm=0,
                    veredicto=("Sin modelos de IA disponibles: las tres lecturas salen de reglas deterministas sobre las cifras. "
                               + ("Coinciden en " + next(iter(distintas)) + "." if len(distintas) == 1 else
                                  "No coinciden: " + " · ".join(f"{ROLES[r]['etiqueta']} elige {d}" for r, d in elecciones.items()) + ".")))
    if len(distintas) == 1:
        v = f"Los {len(con_llm)} roles coinciden en {next(iter(distintas))}. " + (
            "Al correr en modelos independientes, la coincidencia es una senal real de robustez." if indep
            else "Varios roles comparten modelo, asi que la coincidencia vale menos de lo que parece.")
        return dict(modo="llm", consenso=True, decision_consenso=next(iter(distintas)), elecciones=elecciones, roles_con_llm=len(con_llm),
                    modelos_independientes=indep, veredicto=v)
    detalle = " · ".join(f"{ROLES[r]['etiqueta']} elige {d}" for r, d in elecciones.items())
    return dict(modo="llm", consenso=False, elecciones=elecciones, roles_con_llm=len(con_llm), modelos_independientes=indep,
                veredicto=f"No hay consenso: {detalle}. La eleccion depende de que se prioriza, no solo de los numeros. Esa discrepancia es el hallazgo.")


def lecturas_cliente(cid, perfil, ranking, evidencia, pausa=4.0, usar_llm=True):
    """Punto de entrada por cliente. Cache en disco con la huella del ranking: no se vuelve a llamar a los modelos por lo mismo."""
    if usar_llm:
        cargar_claves()
    huella = hashlib.sha256(json.dumps([perfil, ranking, evidencia], sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]
    try:
        cache = json.loads(CACHE.read_text())
    except Exception:
        cache = {}
    if usar_llm and cache.get(cid, {}).get("huella") == huella and any(l["fuente"] == "llm" for l in cache[cid]["resultado"]["lecturas"]):
        return dict(cache[cid]["resultado"], desde_cache=True)
    lecturas, usados = [], set()
    por_nombre = {r["decision"]: r for r in ranking}
    for i, rol in enumerate(ROLES):
        if i:
            time.sleep(pausa)   # los free tier limitan por minuto, no solo por dia
        s = consultar_rol(rol, perfil, ranking, evidencia, usados) if usar_llm else dict(rol=rol, fuente="determinista", motivo="modo sin LLM")
        if s.get("modelo"):
            usados.add(s["modelo"])
        if s["fuente"] == "determinista" and not s.get("decision_elegida"):
            s = dict(lectura_determinista(rol, ranking), motivo=s.get("motivo"))
        r = por_nombre[s["decision_elegida"]]
        metr = dict(prob_perdida=r["prob_perdida"], p5=r["p5"], p_mdd=r["p_mdd_neutral"], p_mdd_estres=r["p_mdd_estres"],
                    p_mdd_mezcla=r["p_mdd_mezcla"], alfa=r["alfa"], ret_anual=r["ret_anual_neutral"], ret_anual_mv=r["ret_anual_markowitz"])
        rev = coherencia_informe(s, metr, s["decision_elegida"])
        s = rev["informe"]
        s["coherencia"] = dict(frases_retiradas=rev["frases_retiradas"], incidencias=rev["incidencias"])
        lecturas.append(s)
    res = dict(lecturas=lecturas, agregacion=agregar(lecturas), proveedores_configurados=[p for p, v in PROVEEDORES.items() if os.getenv(v[0])],
               desde_cache=False)
    if usar_llm:
        cache[cid] = dict(huella=huella, resultado=res)
        try:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
        except Exception:
            pass
    return res
