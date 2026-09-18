import numpy as np
import pytest

from config import MODOS, PROB_ESTADOS
from consultas import ejecutar_sql
from cuantico import amplitudes, grover_carteras
from datos import cargar_insumos
from lectura_multirol import agregar, lectura_determinista
from robustez import coherencia_informe, valor_informacion_estados
from simulacion import Cliente, Fuente, evaluar, fuentes, generar, trayectoria


@pytest.fixture(scope="session")
def ins():
    return cargar_insumos()


@pytest.fixture(scope="session")
def clientes(ins):
    R = np.log(ins["P"]).diff().dropna()
    sig = R.std() * np.sqrt(252)
    return {cid: Cliente(cid, f, ins["ref"], sig) for cid, f in ins["clientes"].iterrows()}


def test_bootstrap_circular_no_sesga_la_deriva():
    rng = np.random.default_rng(0)
    R = rng.normal(0, 0.01, (270, 8))
    R[:9] += 0.02
    R[-9:] -= 0.02
    R -= R.mean(0)
    ret, _ = generar(Fuente(R, np.zeros(8), None, 0.0, 10), 252, 20000, rng)
    assert abs(np.log1p(ret.astype(np.float64)).mean() * 252) < 0.01


def test_caja_pura_crece_a_la_tasa_y_no_cae():
    caja = 0.0002
    ret = np.zeros((50, 100, 8), np.float32)
    term, mdd = evaluar(np.array([[0.0] * 8 + [1.0]]), ret, None, caja)
    assert np.allclose(term, (1 + caja) ** 100, rtol=1e-4)
    assert mdd.max() < 1e-6


def test_conversion_a_moneda_base_multiplica_por_el_tipo_de_cambio():
    ret = np.full((10, 20, 8), 0.001, np.float32)
    fxc = np.cumsum(np.full((10, 20), 0.005, np.float32), axis=1)
    w = np.array([[1 / 8] * 8 + [0.0]])
    sin_fx = trayectoria(w, ret, None, 0.0)[:, -1, 0]
    con_fx = trayectoria(w, ret, fxc, 0.0)[:, -1, 0]
    assert np.allclose(con_fx, sin_fx * np.exp(fxc[:, -1]), rtol=1e-5)


def test_limpieza_deja_8_activos_sin_errores(ins):
    P = ins["P"]
    assert list(P.columns) == [f"VF_A0{i}" for i in range(1, 9)]
    assert P.max().max() < 200 and P.isna().sum().sum() == 0 and P.index.is_unique
    assert ins["Rh"].shape[1] == 8 and ins["Rh"].isna().sum().sum() == 0
    reglas = {d["regla"]: d["filas_afectadas"] for d in ins["dq"] if d["tabla"] == "01_market_prices_raw"}
    assert reglas["precio con punto decimal corrido, dividido por 100"] == 1


def test_restricciones_de_cada_cliente(clientes):
    igual = np.append(np.full(8, 1 / 8), 0.0)[None, :]
    caja = np.array([[0.0] * 8 + [1.0]])
    concentrada = np.array([[0.5, 0.5, 0, 0, 0, 0, 0, 0, 0.0]])
    buena_cl1 = np.array([[0, 0, 0, 0.45, 0.45, 0, 0, 0, 0.10]])
    assert not clientes["CL_01"].cumple(concentrada)[0] and clientes["CL_01"].cumple(buena_cl1)[0]
    assert not clientes["CL_02"].cumple(igual)[0] and clientes["CL_02"].cumple(caja)[0]
    assert not clientes["CL_03"].cumple(caja)[0] and clientes["CL_03"].cumple(igual)[0]


def test_amplitudes_dan_las_probabilidades_de_los_estados():
    p = np.abs(amplitudes(PROB_ESTADOS)) ** 2
    assert np.isclose(p.sum(), 1) and np.allclose(p, [PROB_ESTADOS[m] for m in MODOS])


def test_grover_amplifica_las_carteras_buenas(ins, clientes):
    cl = clientes["CL_01"]
    F = fuentes(ins, cl)
    g = grover_carteras(cl, [F["base_neutral"], F["base_realizado"]], ins["ref"], np.random.default_rng(1), sims=300)
    assert g["factibles"] > 0
    assert g["prob_marcados_despues"] > g["prob_marcados_antes"] and g["prob_marcados_despues"] <= 1 + 1e-9


def test_guardarrail_retira_lo_que_las_cifras_contradicen():
    m = dict(prob_perdida=0.30, p5=-0.20, p_mdd=0.24, p_mdd_estres=0.65, p_mdd_mezcla=0.27, alfa=0.25, ret_anual=0.06, ret_anual_mv=0.07)
    informe = dict(headline="Es una cartera sin riesgo de perdida", summary="Resiste una crisis como la de 2020.",
                   reasons=["Cumple la tolerancia en todos los escenarios", "Supera a la cartera clasica de Markowitz", "Concentra el 45% en VF_A05"])
    r = coherencia_informe(informe, m, "cartera X")
    assert r["frases_retiradas"] == 4
    assert r["informe"]["reasons"] == ["Concentra el 45% en VF_A05"]
    assert "6.0%" in r["informe"]["headline"] and "65%" in r["informe"]["headline"]


def test_guardarrail_deja_pasar_lo_verdadero():
    m = dict(prob_perdida=0.02, p5=0.01, p_mdd=0.01, p_mdd_estres=0.0, p_mdd_mezcla=0.01, alfa=0.15, ret_anual=0.05, ret_anual_mv=0.04)
    informe = dict(headline="Sin riesgo de perdida practico", reasons=["Resiste una crisis", "Supera a la cartera clasica"])
    assert coherencia_informe(informe, m)["frases_retiradas"] == 0


def test_evpi_de_estados_con_ejemplo_conocido():
    T = {"a": np.array([[1.20, 1.00]] * 50), "b": np.array([[0.90, 1.05]] * 50)}   # estado a: A rinde +20%, B 0%; estado b: A -10%, B +5%
    r = valor_informacion_estados(["A", "B"], T, {"a": 0.5, "b": 0.5})
    assert r["decision_sin_informacion"] == "A" and np.isclose(r["evpi"], 0.075)
    assert r["mejor_por_estado"] == {"a": "A", "b": "B"}
    assert r["cartera_minimo_arrepentimiento"] == "A" and np.isclose(r["arrepentimiento_maximo"], 0.15)


def test_agregador_distingue_consenso_desacuerdo_y_modelos_repetidos():
    mismo = [dict(rol="gestor", fuente="llm", modelo="m", decision_elegida="X"), dict(rol="riesgo", fuente="llm", modelo="m", decision_elegida="X")]
    dist = [dict(rol="gestor", fuente="llm", modelo="m1", decision_elegida="X"), dict(rol="riesgo", fuente="llm", modelo="m2", decision_elegida="X")]
    disc = [dict(rol="gestor", fuente="llm", modelo="m1", decision_elegida="X"), dict(rol="riesgo", fuente="llm", modelo="m2", decision_elegida="Y")]
    assert agregar(mismo)["consenso"] and not agregar(mismo)["modelos_independientes"]
    assert agregar(dist)["consenso"] and agregar(dist)["modelos_independientes"]
    assert not agregar(disc)["consenso"] and "No hay consenso" in agregar(disc)["veredicto"]


def test_lectura_determinista_respeta_restricciones_y_cada_rol_usa_su_criterio():
    base = dict(cumple_restricciones=True, alfa=0.2, ret_anual_neutral=0.05, p5=-0.05, prob_perdida=0.1, p_mdd_neutral=0.1, p_mdd_realizado=0.1,
                ret_anual_markowitz=0.04)
    rank = [dict(base, decision="recomendada A", ret_anual_mezcla=0.08, p_mdd_mezcla=0.18, p_mdd_estres=0.60),
            dict(base, decision="solo caja", ret_anual_mezcla=0.04, p_mdd_mezcla=0.0, p_mdd_estres=0.0),
            dict(base, decision="prohibida", ret_anual_mezcla=0.20, p_mdd_mezcla=0.05, p_mdd_estres=0.1, cumple_restricciones=False)]
    assert lectura_determinista("gestor", rank)["decision_elegida"] == "recomendada A"
    assert lectura_determinista("riesgo", rank)["decision_elegida"] == "solo caja"
    assert lectura_determinista("asesor", rank)["decision_elegida"] == "recomendada A"


def test_capa_sql_devuelve_lo_esperado(ins):
    filas = ejecutar_sql(ins)
    assert filas["01_retorno_mensual_por_activo"] == 8 * 13
    assert filas["03_correlaciones_12m"] == 28 and filas["02_caida_maxima_por_activo"] == 8
    assert filas["05_bitacora_de_calidad"] >= 3
    import pandas as pd
    from config import SALIDAS
    dd = pd.read_csv(SALIDAS / "sql" / "02_caida_maxima_por_activo.csv").set_index("asset_id").caida_maxima
    assert -0.45 < dd["VF_A06"] < -0.30
