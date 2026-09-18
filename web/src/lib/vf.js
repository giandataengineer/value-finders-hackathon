export const FINAL = "recomendada defensiva (con estres)";
export const BASE = "recomendada base (robusta)";
export const MV = "clasica Markowitz (max Sharpe)";
export const MODOS = { base_neutral: "Neutral", base_realizado: "Con lo realizado", estres_historial_2020_2025: "Estrés 2020-2025" };
export const ETIQUETA = {
  [FINAL]: "Recomendada defensiva", [BASE]: "Recomendada base", "optima solo neutral": "Óptima solo neutral", "optima solo realizado": "Óptima con lo realizado",
  "igual ponderada": "Igual ponderada", "solo caja": "Solo caja (USD)", [MV]: "Clásica Markowitz",
};
const f = (v, d) => Number(v ?? 0).toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });
export const pct = (v, d = 1) => `${f(v * 100, d)} %`;
export const pctS = (v, d = 1) => `${v >= 0 ? "+" : "-"}${f(Math.abs(v) * 100, d)} %`;
export const num = (v, d = 0) => f(v, d);
export const nombreActivo = (payload, id) => payload?.caso?.activos?.find((a) => a.asset_id === id)?.name ?? id;
export const pesosVisibles = (w) => Object.entries(w ?? {}).filter(([, v]) => v >= 0.005).sort((a, b) => b[1] - a[1]);
