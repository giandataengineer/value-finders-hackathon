import numpy as np
import pandas as pd
import pytest

from config import RAIZ, RAW, TABLAS_GOLD
from datos import cargar_insumos, cargar_insumos_pandas
from etl import FUENTES, asegurar_gold, leer_parquet


def g(capa, tabla):
    return leer_parquet(capa, tabla)


@pytest.fixture(scope="module", autouse=True)
def medallon():
    asegurar_gold()


def test_bronce_conserva_el_crudo_y_lo_marca():
    for tabla, (archivo, lote, *_r) in FUENTES.items():
        b = g("bronze", tabla)
        assert len(b) == len(pd.read_csv(RAW / archivo))
        assert {"_row_id", "_source_file", "_source_sha256", "_batch", "_ingested_at"} <= set(b.columns)
        assert (b["_batch"] == lote).all() and b["_row_id"].is_unique


def test_ninguna_fila_se_pierde_en_silencio():
    for r in g("gold", "linaje").itertuples():
        assert r.filas_bronze == r.filas_silver + r.filas_cuarentena, r.dataset


def test_la_cuarentena_explica_cada_descarte():
    c = g("silver", "cuarentena").groupby(["tabla", "motivo"]).size()
    assert c[("market_daily", "duplicado (activo, día)")] == 7
    assert c[("market_intraday", "close nulo")] == 24 and c[("market_intraday", "duplicado (activo, timestamp)")] == 12
    assert c[("fundamentals", "duplicado (emisor, periodo)")] == 1


def test_silver_de_precios_sin_duplicados_ni_ids_raros():
    ref = set(g("silver", "asset_reference").asset_id)
    for tabla, clave in (("market_daily", "day"), ("market_intraday", "ts")):
        s = g("silver", tabla)
        assert set(s.asset_id) <= ref and not s.duplicated(["asset_id", clave]).any()
        assert s.close.max() < 1000 and (s.low <= s.high).all()
    d = g("silver", "market_daily")
    assert d[(d.asset_id == "VF_A06") & (pd.to_datetime(d.day) == pd.Timestamp("2026-03-23"))].close.iloc[0] == pytest.approx(35.89)


def test_trimestre_mal_etiquetado_se_reasigna_al_que_falta():
    f = g("silver", "fundamentals")
    assert (f.groupby("issuer_id").size() == 8).all()
    fila = f[(f.issuer_id == "ISS_02") & (pd.to_datetime(f.period_end) == "2025-06-30")]
    assert len(fila) == 1 and fila.revenue_usd_m.iloc[0] == pytest.approx(2928.4)


def test_giros_se_convierten_en_parametros():
    x = g("gold", "giros").set_index("giro_id")
    assert x.loc["TW_01", "valor_parametro"] == pytest.approx(0.0065) and x.loc["TW_01", "parametro_modelo"] == "rendimiento_de_la_caja"
    assert x.loc["TW_02", "valor_parametro"] == pytest.approx(0.30) and x.loc["TW_02", "horizonte_meses"] == 6 and x.loc["TW_02", "clientes_afectados"] == "CL_02"
    assert x.loc["TW_03", "valor_parametro"] == pytest.approx(0.08) and x.loc["TW_03", "clientes_afectados"] == "CL_02"
    assert x.loc["TW_01", "clientes_afectados"] == "CL_01,CL_02,CL_03"


def test_restricciones_del_cliente_salen_del_texto():
    r = g("gold", "restricciones_cliente").set_index("client_id")
    assert r.loc["CL_01", "tope_por_sector"] == pytest.approx(0.45) and r.loc["CL_02", "tope_alta_volatilidad"] == pytest.approx(0.25)
    assert r.loc["CL_03", "min_paises"] == 3 and r.loc["CL_03", "min_sectores"] == 3 and r.loc["CL_02", "fx_col"] == "usd_cop"


def test_la_senal_de_correlacion_se_ve_en_el_gold():
    s = g("gold", "senal_correlacion").set_index("fuente").correlacion_media
    assert s["diario_12m"] == pytest.approx(0.157, abs=0.01) and s["historial_intradia"] == pytest.approx(0.798, abs=0.01)


def test_el_gold_cumple_el_contrato_de_databricks():
    for tabla in TABLAS_GOLD.values():
        assert (RAIZ / "data" / "gold" / f"{tabla}.parquet").exists(), tabla
    assert {"day", "asset_id", "close"} <= set(g("gold", "precios_diarios").columns)
    assert {"day", "asset_id", "close"} <= set(g("gold", "precios_intradia_cierre").columns)


def test_sql_y_pandas_limpian_igual():
    a, b = cargar_insumos(), cargar_insumos_pandas()
    pd.testing.assert_frame_equal(a["P"], b["P"], check_freq=False, check_dtype=False)
    pd.testing.assert_frame_equal(a["Rh"], b["Rh"], check_freq=False, check_dtype=False)
    cols = ["us_10y_yield", "us_inflation_yoy", "usd_cop", "usd_pen", "usd_mxn", "usd_clp", "market_factor", "risk_regime"]
    pd.testing.assert_frame_equal(a["macro"][cols], b["macro"][cols], check_freq=False, check_dtype=False)
    num = ["revenue_usd_m", "ebitda_usd_m", "net_income_usd_m", "debt_usd_m", "cash_usd_m"]
    pd.testing.assert_frame_equal(a["fund"][["issuer_id", "period_end"] + num], b["fund"][["issuer_id", "period_end"] + num], check_dtype=False)
    pd.testing.assert_frame_equal(a["ref"], b["ref"], check_dtype=False)
    pd.testing.assert_frame_equal(a["clientes"], b["clientes"], check_dtype=False)
    assert list(a["eventos"].scope) == list(b["eventos"].scope)
