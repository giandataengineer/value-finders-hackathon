"""Parametros y supuestos del proyecto. Todo lo que aqui se define queda registrado en outputs/trazabilidad.json."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
SALIDAS = RAIZ / "outputs"

SEED, DIAS = 42, 252
SIMS_BUSQUEDA, SIMS_FINAL, LOTE, N_CAND = 1500, 10_000, 2500, 600
RONDAS_ROBUSTA, RONDAS_MODO = 4, 2
ERP = 0.04        # prima de riesgo sobre la tasa libre en el escenario neutral
ENCOGER = 0.5     # parte del retorno realizado 12m que se conserva en base_realizado
VOL_ALTA = 0.30   # vol anual desde la cual un activo es "alta volatilidad" (restriccion de CL_02)
POS_MIN = 0.10    # peso minimo para contar una posicion como presente (restriccion de CL_03)
ALFA_POR_TOLERANCIA = {"Alta": 0.25, "Media": 0.20, "Media-Baja": 0.15}   # P(caida maxima > tolerancia) permitida
PROB_ESTADOS = {"base_neutral": 0.55, "base_realizado": 0.30, "estres_historial_2020_2025": 0.15}

IDS = {"VF-A1": "VF_A01", "VF-A4": "VF_A04", "VF-A6": "VF_A06", "VFA03": "VF_A03", "VF_A6": "VF_A06"}
FX_COL = {"USD": None, "COP": "usd_cop", "PEN": "usd_pen"}
MODOS = ["base_neutral", "base_realizado", "estres_historial_2020_2025"]
# Largo del bloque elegido con la razon de varianzas: los ultimos 12m se comportan como paseo aleatorio (ratio ~1, autocorr ~0),
# el historial 2020-2025 tiene dependencia (ratio hasta 1.47, autocorr de |r| 0.16).
BLOQUE_POR_MODO = {"base_neutral": 5, "base_realizado": 5, "estres_historial_2020_2025": 21}

ASUNCIONES = [
    "Retornos diarios conjuntos por bootstrap de bloques circulares: 5 dias en el caso base (12m sin dependencia medible) y 21 en el estres (historial con dependencia). Conserva correlacion entre activos, colas y agrupacion de volatilidad.",
    "Caso base calibrado con los ultimos 12 meses del archivo diario, el unico tramo coherente con macro y eventos.",
    "base_neutral: todos los activos rinden tasa libre + 4% (sin ventaja de ninguno). base_realizado: 50% del retorno realizado en 12m.",
    "estres_historial_2020_2025: retornos intradia 2020 a jul-2025 tal cual (correlacion media 0.80); es un escenario, no el caso base.",
    "La caja rinde el promedio del us_10y_yield (4.24%) en USD. No hay tasas en COP ni PEN en los datos.",
    "Tipo de cambio sin deriva (random walk): USD/COP y USD/PEN se remuestrean junto con los retornos para el cliente en esa moneda.",
    "Cartera de pesos constantes, rebalanceada a diario, sin costos de transaccion ni impuestos.",
    "Presupuesto de riesgo: P(caida maxima > tolerancia del cliente) <= 25% (tolerancia Alta), 20% (Media), 15% (Media-Baja).",
    "Recomendacion base (robusta): cumple el presupuesto en base_neutral Y en base_realizado; se maximiza el retorno mediano promedio.",
    "Recomendacion defensiva: optimiza sobre la mezcla de los tres estados (55/30/15); el retorno mediano que cede frente a la base es el costo de protegerse del estres.",
    "Alta volatilidad (CL_02) = vol anual 12m > 30%. Posicion presente (CL_03) = peso >= 10%. Un activo por sector, asi que 45% por sector = 45% por activo.",
    "Pesos por estado de mercado (superposicion): 55% neutral, 30% realizado, 15% estres. Es un supuesto, con sensibilidad en la salida.",
]

# Databricks (solo con --databricks). Ajustar a los nombres reales del gold del equipo de ETL: python src/databricks_io.py los lista.
CATALOGO, ESQUEMA_GOLD, ESQUEMA_SIM = "hackathon", "gold", "simulacion"   # las salidas del Monte Carlo van a ESQUEMA_SIM, nunca al gold de ETL
TABLAS_GOLD = dict(precios_diarios="precios_diarios", precios_intradia="precios_intradia_cierre", macro="macro", fundamentales="fundamentales",
                   activos="asset_reference", clientes="client_profiles", eventos="events")

ENV_FALLBACK =Path("/Users/gian.social/Downloads/Simulaciones Montecarlo/.env")   # claves de LLM del proyecto Nordika si no hay .env propio
