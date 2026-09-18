"""Congela el contexto por cliente para el asistente del chat: web/api/_data/contexto.json.
Uso: python src/exportar_contexto.py   (despues de src/run.py y src/twists.py)
"""
import datetime
import json

from config import RAIZ, SALIDAS
from datos import cargar_insumos
from twists import FINAL

DEST = RAIZ / "web" / "api" / "_data"


def _pct(v, d=0):
    return f"{v * 100:.{d}f}%"


def construir():
    ins = cargar_insumos()
    mc = json.loads((SALIDAS / "mc_resultados.json").read_text())
    clientes = {}
    for cid, f in ins["clientes"].iterrows():
        c = mc["clientes"][cid]
        e = c["superposicion_estados"][FINAL]
        metricas = dict(ret_anual=e["ret_anual_mediano"], p5=e["p5"], p95=e["p95"], prob_perdida=e["prob_perdida"],
                        cvar5=e["cvar5"], mdd_mediano=e["mdd_mediano"], p_mdd_sobre_tol=e["p_mdd_sobre_tol"])
        perfil = dict(nombre=f.profile_name, moneda=f.base_currency, horizonte_meses=int(f.horizon_months),
                     tolerancia_caida=int(f.max_drawdown_tolerance_pct) / 100, liquidez=f.liquidity_need,
                     prioridad=f.priority, riesgo=f.risk_tolerance, restriccion=f["constraint"],
                     presupuesto_riesgo=c["presupuesto_riesgo"])
        cartera = {a: round(w, 4) for a, w in c["carteras"][FINAL].items() if w >= 0.005}
        texto = (
            f"Cliente {cid} ({perfil['nombre']}), perfil {perfil['prioridad']}, moneda base {perfil['moneda']}, "
            f"horizonte {perfil['horizonte_meses']} meses, tolerancia de caída {_pct(perfil['tolerancia_caida'])}, "
            f"restricción: {perfil['restriccion']}. "
            f"Cartera recomendada ({FINAL}): " + ", ".join(f"{a} {_pct(w)}" for a, w in cartera.items()) + ". "
            f"Simulación de 10.000 futuros: retorno anual mediano {_pct(metricas['ret_anual'], 1)}, "
            f"percentil 5 al final del horizonte {_pct(metricas['p5'])}, probabilidad de pérdida {_pct(metricas['prob_perdida'])}, "
            f"caída máxima mediana {_pct(metricas['mdd_mediano'])} contra un presupuesto de riesgo de {_pct(perfil['presupuesto_riesgo'])}."
        )
        clientes[cid] = dict(perfil=perfil, metricas=metricas, cartera=cartera, texto=texto)
    return dict(generado=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), cartera_final=FINAL, clientes=clientes)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    ruta = DEST / "contexto.json"
    ruta.write_text(json.dumps(construir(), ensure_ascii=False, indent=1, allow_nan=False))
    print(f"contexto.json listo: {ruta}")


if __name__ == "__main__":
    main()
