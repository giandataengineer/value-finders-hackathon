import pandas as pd

import databricks_io as dbx
from config import TABLAS_GOLD
from datos import cargar_insumos


class SparkFalso:
    """Devuelve las tablas del gold desde memoria: prueba el mapeo sin conectarse a Databricks."""
    def __init__(self, tablas):
        self.tablas = tablas

    def table(self, completo):
        df = self.tablas[completo.split(".")[-1]]
        return type("T", (), {"toPandas": lambda s: df.copy()})()


def test_leer_el_gold_reproduce_el_diccionario_local():
    local = cargar_insumos()
    falso = SparkFalso({TABLAS_GOLD[k]: df for k, df in dbx.tablas_gold(local).items()})
    gold = dbx.cargar_insumos(falso)
    for clave in ("P", "Rh", "macro", "ref", "clientes"):
        pd.testing.assert_frame_equal(gold[clave], local[clave], check_freq=False, check_dtype=False)
    assert {d["tabla"] for d in gold["dq"]} == set(gold["entradas"])
