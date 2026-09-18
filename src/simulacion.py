"""Motor Monte Carlo de carteras: bootstrap de bloques circulares, conversion a moneda base,
restricciones por cliente y optimizacion robusta. Los 8 activos van en las columnas 0-7 y la caja en la 8."""
from typing import NamedTuple, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from config import (ALFA_POR_TOLERANCIA, BLOQUE_POR_MODO, DIAS, ENCOGER, ERP, FX_COL, LOTE, N_CAND, POS_MIN, SIMS_BUSQUEDA, SIMS_FINAL, VOL_ALTA)


class Fuente(NamedTuple):
    """Un estado del mundo: retornos base para remuestrear, deriva diaria, tipo de cambio, caja diaria y largo de bloque."""
    Rm: np.ndarray
    drift: np.ndarray
    fx: Optional[np.ndarray]
    caja: float
    bloque: int


def generar(f, H, sims, rng, bloque=None, choque=0.0):
    b = bloque or f.bloque
    n = -(-H // b)
    starts = rng.integers(0, len(f.Rm), size=(sims, n))
    idx = ((starts[:, :, None] + np.arange(b)) % len(f.Rm)).reshape(sims, -1)[:, :H]   # circular: cada dia entra por igual
    ret = np.expm1(f.Rm[idx] + f.drift).astype(np.float32)
    if choque:
        ret[:, 0, :] = (1 + ret[:, 0, :]) * (1 + choque) - 1   # repricing instantaneo de las acciones el dia 1
    fxc = np.cumsum(f.fx[idx], axis=1).astype(np.float32) if f.fx is not None else None
    return ret, fxc


def trayectoria(w, ret, fxc, caja):
    S, H, _ = ret.shape
    rp = ret.reshape(-1, 8) @ w[:, :8].T.astype(np.float32) + w[:, 8].astype(np.float32) * caja
    V = np.cumprod(1 + rp.reshape(S, H, -1), axis=1)
    return V * np.exp(fxc)[:, :, None] if fxc is not None else V


def evaluar(W, ret, fxc, caja, chunk=25):
    S = ret.shape[0]
    term = np.empty((S, len(W)), np.float32)
    mdd = np.empty_like(term)
    for a in range(0, len(W), chunk):
        V = trayectoria(W[a:a + chunk], ret, fxc, caja)
        peak = np.maximum(np.maximum.accumulate(V, axis=1), 1.0)
        mdd[:, a:a + chunk] = (1 - V / peak).max(axis=1)
        term[:, a:a + chunk] = V[:, -1]
    return term, mdd


class Cliente:
    def __init__(self, cid, fila, ref, sig):
        self.id, self.f, self.ref = cid, fila, ref
        self.H = int(fila.horizon_months * 21)
        self.tol = fila.max_drawdown_tolerance_pct / 100
        self.moneda = fila.base_currency
        self.alfa = ALFA_POR_TOLERANCIA[fila.risk_tolerance]
        self.M_sec = pd.get_dummies(ref.sector).T.reindex(columns=ref.index).values.astype(float)
        self.M_pais = pd.get_dummies(ref.country).T.reindex(columns=ref.index).values.astype(float)
        self.alta = (sig.reindex(ref.index) > VOL_ALTA).values
        self.caja_min = 0.0   # liquidez exigida (giro TW_02)

    def cumple(self, W):
        ok = self._cumple(W)
        return ok & (W[:, 8] >= self.caja_min - 1e-9) if self.caja_min else ok

    def _cumple(self, W):
        A = W[:, :8]
        if self.id == "CL_01":
            return (A @ self.M_sec.T).max(axis=1) <= 0.45 + 1e-9
        if self.id == "CL_02":
            return A[:, self.alta].sum(axis=1) <= 0.25 + 1e-9
        pos = (A >= POS_MIN - 1e-9).astype(float)
        paises = ((pos @ self.M_pais.T) > 0).sum(1)
        sectores = ((pos @ self.M_sec.T) > 0).sum(1)
        return (pos.sum(1) >= 3) & (paises >= 3) & (sectores >= 3)


def muestrear(rng, n):
    W = np.zeros((n, 9))
    caja = np.where(rng.random(n) < 0.3, 0.0, rng.random(n) * 0.95)
    for i in range(n):
        m = rng.integers(2, 9)
        idx = rng.choice(8, m, replace=False)
        W[i, idx] = rng.dirichlet(np.ones(m)) * (1 - caja[i])
    W[:, 8] = caja
    return W


def perturbar(rng, base, n, esc):
    W = np.clip(base[rng.integers(0, len(base), n)] + rng.normal(0, esc, (n, 9)), 0, None)
    W[W < 0.02] = 0
    s = W.sum(1, keepdims=True)
    return np.where(s > 0, W / np.maximum(s, 1e-9), 0)


def optimizar(cl, fuentes_, rng, rondas, mezcla=None):
    """Busqueda por muestreo y refinamiento. Sin 'mezcla': exige P(caida > tolerancia) <= alfa en TODAS las fuentes y
    maximiza el retorno mediano promedio (robusto). Con 'mezcla': lo exige sobre la probabilidad ponderada de los estados."""
    caja = fuentes_[0].caja
    sims = [generar(f, cl.H, SIMS_BUSQUEDA, rng) for f in fuentes_]
    W = np.empty((0, 9))
    for _ in range(25):
        c = muestrear(rng, 4000)
        W = np.vstack([W, c[cl.cumple(c)]])
        if len(W) >= N_CAND:
            break
    if len(W) == 0:
        raise RuntimeError(f"{cl.id}: no hay carteras que cumplan las restricciones")
    W = W[:N_CAND]
    escala = [0.10, 0.06, 0.03, 0.015]
    todo_W, todo_med, todo_p = [], [], []
    for r in range(rondas):
        res = [evaluar(W, ret, fxc, caja) for ret, fxc in sims]
        meds = np.array([np.median(t, 0) - 1 for t, _ in res])
        ps = np.array([(m > cl.tol).mean(0) for _, m in res])
        if mezcla is None:
            med, p = meds.mean(0), ps.max(0)
        else:
            w = np.asarray(mezcla)[:, None]
            med, p = (w * meds).sum(0), (w * ps).sum(0)
        todo_W.append(W), todo_med.append(med), todo_p.append(p)
        AW, AMED, AP = np.vstack(todo_W), np.concatenate(todo_med), np.concatenate(todo_p)
        score = np.where(AP <= cl.alfa, AMED, -1 - AP)
        if r < rondas - 1:
            c = perturbar(rng, AW[np.argsort(-score)[:8]], 3000, escala[r])
            W = c[cl.cumple(c)][:N_CAND]
            if len(W) == 0:
                break
    j = int(np.argmax(score))
    return AW[j], bool(AP[j] <= cl.alfa)


def mv_sharpe(R, rf):
    """Comparador clasico: Markowitz de maximo Sharpe con media y covarianza muestrales, tope 45% por activo."""
    mu, cov = np.expm1(R.mean().values * DIAS), R.cov().values * DIAS
    r = minimize(lambda w: -(w @ mu - rf) / np.sqrt(w @ cov @ w), np.full(8, 1 / 8), bounds=[(0, 0.45)] * 8,
                 constraints={"type": "eq", "fun": lambda w: w.sum() - 1}, method="SLSQP")
    return np.append(r.x, 0.0)


def fuentes(ins, cl, erp=ERP, escala_vol=1.0, escala_fx=1.0, rf_caja=None):
    P, macro = ins["P"], ins["macro"]
    R = np.log(P).diff().dropna()
    rf = macro.us_10y_yield.mean() / 100
    caja = (1 + (rf if rf_caja is None else rf_caja)) ** (1 / DIAS) - 1   # rf_caja cambia solo lo que rinde la caja
    sig = R.std() * np.sqrt(DIAS) * escala_vol
    Rc = (R - R.mean()).values * escala_vol
    col = FX_COL[cl.moneda]
    fx = None
    if col:
        x = np.log(macro[col]).diff().reindex(R.index)
        fx = (x - x.mean()).values * escala_fx
    ret12 = (P.iloc[-1] / P.iloc[0]) ** (365 / (P.index[-1] - P.index[0]).days) - 1
    d = lambda mu: ((np.log1p(mu) - 0.5 * sig ** 2) / DIAS).values
    b = BLOQUE_POR_MODO
    return {
        "base_neutral": Fuente(Rc, d(pd.Series(rf + erp, index=sig.index)), fx, caja, b["base_neutral"]),
        "base_realizado": Fuente(Rc, d(rf + ENCOGER * (ret12 - rf)), fx, caja, b["base_realizado"]),
        "estres_historial_2020_2025": Fuente(ins["Rh"].values * escala_vol, np.zeros(8), None, caja, b["estres_historial_2020_2025"]),
    }


def resumen(term, mdd, tol, H):
    r = term - 1
    q = np.quantile(r, [0.05, 0.5, 0.95])
    p = float((mdd > tol).mean())
    return dict(ret_mediano=float(q[1]), p5=float(q[0]), p95=float(q[2]), prob_perdida=float((r < 0).mean()),
                cvar5=float(r[r <= q[0]].mean()), mdd_mediano=float(np.median(mdd)), p_mdd_sobre_tol=p,
                error_estandar_p_mdd=float(np.sqrt(p * (1 - p) / len(mdd))), ret_anual_mediano=float((1 + q[1]) ** (DIAS / H) - 1))


def simular_final(cl, W, fuente, rng, sims=SIMS_FINAL, bloque=None, meses_abanico=0, choque=0.0):
    """Evalua las carteras W (K,9) con simulaciones nuevas (fuera de la muestra de busqueda)."""
    T, M, fan = [], [], []
    for _ in range(max(1, sims // LOTE)):
        ret, fxc = generar(fuente, cl.H, min(LOTE, sims), rng, bloque, choque)
        t, m = evaluar(W, ret, fxc, fuente.caja)
        T.append(t)
        M.append(m)
        if meses_abanico:
            V = trayectoria(W[:1], ret, fxc, fuente.caja)[:, :, 0]
            fan.append(V[:, [21 * k - 1 for k in range(1, meses_abanico + 1)]])
    q = np.quantile(np.vstack(fan), [0.05, 0.25, 0.5, 0.75, 0.95], axis=0) if fan else None
    return np.vstack(T), np.vstack(M), q
