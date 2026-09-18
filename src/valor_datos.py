"""Decide con evidencia que datos entran a la simulacion y cuales no."""
import numpy as np
import pandas as pd
from scipy import stats

from config import DIAS


def evaluar_valor(ins):
    ref, macro, P, intra, f, ev, Rh = ins["ref"], ins["macro"], ins["P"], ins["intra"], ins["fund"], ins["eventos"], ins["Rh"]
    R = np.log(P).diff().dropna()
    post = np.log(intra.loc["2025-08-01":]).diff().dropna(how="all")
    ew = R.mean(axis=1)
    mf = macro.market_factor.reindex(R.index)
    filas = []

    def add(dato, prueba, resultado, decision, motivo):
        filas.append(dict(dato=dato, prueba=prueba, resultado=resultado, decision=decision, motivo=motivo))

    cmed = lambda X: X.corr().values[np.triu_indices(X.shape[1], 1)].mean()
    anual = lambda X: np.expm1(X.mean() * DIAS).mean()
    add("Precios diarios (01 raw), ultimos 12m", "Coherencia con macro: corr(retorno medio, market_factor)",
        f"{ew.corr(mf):.2f}", "Usar (base de la simulacion)", "Se mueve con el factor de mercado y reacciona a los eventos.")
    add("Precios intradia (01 expanded) desde 2025-08", "Coherencia con macro: corr(retorno medio, market_factor)",
        f"{post.mean(axis=1).reindex(mf.index).corr(mf):.2f}", "Descartar",
        "Mismo periodo que el diario pero no coincide con el macro ni con el diario (el dia 1 es igual, despues divergen).")
    add("Precios intradia (01 expanded) 2020 a jul-2025", "Estructura de riesgo vs ultimo anio alineado",
        f"corr media entre activos {cmed(Rh):.2f} vs {cmed(R):.2f}; retorno anual medio {anual(Rh):.0%} vs {anual(R):.0%}",
        "Solo escenario de estres",
        "La correlacion entre activos es mucho mayor que en el anio alineado con macro y eventos; sirve para probar una crisis, no para calibrar el caso base.")
    add("Granularidad de 10 minutos", "Horizonte de decision de 18 a 36 meses",
        "Toda la simulacion usa retornos diarios", "No aporta", "El detalle intradia no cambia la distribucion a 18-36 meses.")

    reg = macro.risk_regime.reindex(R.index)
    vol, mu, n = ew.groupby(reg).std(), ew.groupby(reg).mean(), ew.groupby(reg).size()
    add("risk_regime (02)", "Vol y retorno diario del portafolio por regimen",
        f"vol Normal {vol['Normal']:.2%} / Stress {vol['Stress']:.2%}; retorno Stress {mu['Stress']:.2%}/dia; dias Stress={n['Stress']}, Recovery={n['Recovery']}",
        "Solo escenario", "Stress cambia la deriva pero no la volatilidad y son solo 10 dias: no alcanza para estimar distribuciones por regimen.")
    r1, p1 = stats.pearsonr(mf.iloc[:-1], ew.iloc[1:])
    add("market_factor (02)", "Poder predictivo: corr(factor hoy, retorno manana)", f"{r1:.2f} (p={p1:.2f})", "Contexto",
        "Es contemporaneo (0.77) pero no predice; redundante con los precios.")
    infl = macro.us_inflation_yoy.dropna()
    add("us_inflation_yoy (02)", "Variacion en el periodo", f"{len(infl)} datos mensuales entre {infl.min():.2f} y {infl.max():.2f}",
        "Descartar", "Casi constante; no mueve la distribucion de retornos.")
    rf = macro.us_10y_yield.mean() / 100
    add("us_10y_yield (02)", "Uso directo", f"promedio {rf:.2%}", "Usar", "Rendimiento de la caja: no hay activos de renta fija en el universo.")
    fx = np.log(macro[["usd_cop", "usd_pen", "usd_mxn", "usd_clp"]]).diff().reindex(R.index)
    for c in ["usd_cop", "usd_pen"]:
        share = 1 - ew.var() / (ew + fx[c]).var()
        add(c + " (02)", "Parte de la varianza que agrega a una cartera en USD",
            f"{share:.0%} de la varianza; vol anual {fx[c].std() * np.sqrt(DIAS):.1%}; corr con acciones {ew.corr(fx[c]):.2f}",
            "Usar", "Moneda base de CL_02 (COP) y CL_03 (PEN): cambia el resultado que ve el cliente.")
    add("usd_mxn, usd_clp (02)", "Monedas de cotizacion de los activos", "todos cotizan en USD (04)", "Descartar", "Ningun activo se valora en MXN o CLP.")

    filas_f = []
    for k, x in f.groupby("issuer_id"):
        a, b = x.iloc[-1], x.iloc[-5]
        filas_f.append(dict(asset_id=k.replace("ISS_", "VF_A"), rev_yoy=a.revenue_usd_m / b.revenue_usd_m - 1,
                            d_margen=a.ebitda_usd_m / a.revenue_usd_m - b.ebitda_usd_m / b.revenue_usd_m,
                            apal=a.debt_usd_m / (4 * a.ebitda_usd_m)))
    F = pd.DataFrame(filas_f).set_index("asset_id")
    ret12 = P.iloc[-1] / P.iloc[0] - 1
    txt = []
    for c in F:
        r, p = stats.pearsonr(F[c], ret12.reindex(F.index))
        txt.append(f"{c} r={r:+.2f} (p={p:.2f})")
    add("Fundamentales (03)", "Correlacion con el retorno de los ultimos 12m (n=8)", "; ".join(txt), "Contexto (no entra a la deriva)",
        "Con 8 emisores nada es significativo. Sirve como filtro de calidad, no como prediccion. VF_A06 muestra ingresos +68% interanual: verificar.")

    filas_e, zs = [], []
    Rlog = np.log(P).diff()
    for _, x in ev.iterrows():
        cols = ref.index[ref.sector == x.scope] if x.scope in set(ref.sector) else [x.scope]
        for c in cols:
            r3 = Rlog[c].loc[x.event_date:].iloc[:3].sum()
            z = r3 / Rlog[c].rolling(3).sum().dropna().std()
            zs.append(abs(z))
            filas_e.append(f"{c} {x.severity}: {r3:+.1%} (z={z:+.1f})")
    add("Eventos (06)", "Reaccion acumulada a 3 dias vs su desviacion tipica", "; ".join(filas_e), "Solo escenario",
        f"{len(zs)} eventos, {sum(z >= 1.5 for z in zs)} con |z| >= 1.5: no alcanzan para calibrar saltos; se usan como biblioteca de shocks.")
    add("Referencia (04) y perfiles (05)", "Uso directo", "-", "Usar", "Definen pais, sector, moneda base, horizonte y restricciones de cada cliente.")
    return pd.DataFrame(filas)
