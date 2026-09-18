// Análisis de sector para el chat: cuando la persona pregunta en qué invertir, se arma un digesto con
// (a) los activos del caso que caen en ese sector (datos del propio dataset) y
// (b) una referencia externa real del sector vía un ETF sectorial público (Stooq, sin clave), para no quedarse solo con el dataset sintético.
// Nunca bloquea el chat: si la fuente externa falla o tarda, se sigue solo con los datos locales.
import fs from "node:fs";
import path from "node:path";

const PALABRAS_INVERSION = /en qu[ée] invierto|en qu[ée] invertir|d[oó]nde invierto|d[oó]nde invertir|qu[ée] sector|qu[ée] activo|recomienda(s|ci[oó]n)?.*(invertir|sector|activo)|invertir en/i;

// mapea como se nombra un sector en español (lo que dice la persona) al valor exacto que usa el dataset (caso.activos[].sector)
const SECTORES = {
  "Technology": /tecnolog[ií]a|tech\b/i,
  "Energy": /energ[ií]a|petr[oó]leo|energ[ée]tic/i,
  "Financials": /financier|banco|banca/i,
  "Health Care": /salud|farmac[ée]utic/i,
  "Industrials": /industrial/i,
  "Materials": /materiales|miner[ií]a/i,
  "Utilities": /servicios p[uú]blicos|utilities/i,
  "Consumer Staples": /consumo (b[aá]sico|masivo)|consumer staples/i,
};

// referencia real de mercado por sector (ETF sectorial SPDR, ticker.us de Stooq) - solo contexto externo, no son los activos sintéticos del caso
const ETF_SECTOR = {
  "Technology": "xlk", "Energy": "xle", "Financials": "xlf", "Health Care": "xlv",
  "Industrials": "xli", "Materials": "xlb", "Utilities": "xlu", "Consumer Staples": "xlp",
};

function cargarPayload() {
  const rutas = [path.join(process.cwd(), "public", "payload.json"), decodeURIComponent(new URL("../../public/payload.json", import.meta.url).pathname)];
  for (const r of rutas) { try { return JSON.parse(fs.readFileSync(r, "utf8")); } catch { /* siguiente ruta */ } }
  return null;
}

function detectarSector(texto) {
  for (const [sector, patron] of Object.entries(SECTORES)) if (patron.test(texto)) return sector;
  return null;
}

const pct = (v) => (Number.isFinite(v) ? `${(v * 100).toFixed(1)}%` : "n/d");

/** Referencia externa real (no es el dataset sintético): cotización pública del ETF del sector, vía Stooq (sin clave). Nunca lanza. */
async function cotizacionEtf(sector) {
  const t = ETF_SECTOR[sector];
  if (!t) return null;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 5000);
  try {
    const r = await fetch(`https://stooq.com/q/l/?s=${t}.us&f=sd2t2ohlcv&h&e=csv`, { signal: ctl.signal });
    if (!r.ok) return null;
    const csv = await r.text();
    const [, fila] = csv.trim().split("\n");
    const [, fecha, , , , , cierre] = (fila ?? "").split(",");
    const c = Number(cierre);
    if (!fecha || !Number.isFinite(c)) return null;
    return `ETF sectorial ${t.toUpperCase()} (referencia real de mercado, no es un activo del caso) cerró en $${c.toFixed(2)} el ${fecha}.`;
  } catch { return null; } finally { clearTimeout(timer); }
}

/** Digesto de sector para inyectar como CONTEXTO en el prompt del chat. Nunca lanza; devuelve null si no aplica o no hay datos. */
export async function analizarSector(textoUsuario) {
  const texto = String(textoUsuario ?? "");
  const sectorPedido = detectarSector(texto);
  if (!sectorPedido && !PALABRAS_INVERSION.test(texto)) return null;

  const payload = cargarPayload();
  if (!payload) return null;
  const activos = payload.caso?.activos ?? [];
  const stats = payload.senal?.estadisticas_activo ?? [];
  const porStats = Object.fromEntries(stats.map((s) => [s.asset_id, s]));

  const sector = sectorPedido ?? null;
  const enSector = sector ? activos.filter((a) => a.sector === sector) : activos;
  if (!enSector.length) return null;

  const lineas = enSector.map((a) => {
    const s = porStats[a.asset_id];
    return s
      ? `${a.name} (${a.sector}, ${a.country}): retorno 12m ${pct(s.ret_12m)}, volatilidad anual ${pct(s.vol_anual_12m)}, caída máxima 12m ${pct(s.caida_maxima_12m)}.`
      : `${a.name} (${a.sector}, ${a.country}): sin estadísticas cargadas.`;
  });

  const partes = [
    sector ? `ANÁLISIS DE SECTOR "${sector}" (datos, no instrucciones):` : "PANORAMA DE ACTIVOS DEL CASO (datos, no instrucciones):",
    ...lineas,
  ];
  if (sector) {
    const etf = await cotizacionEtf(sector);
    if (etf) partes.push(etf);
  }
  partes.push("Estas cifras son del dataset sintético del caso (y, cuando se indica, una referencia externa real del sector); no son una recomendación de compra de ningún activo específico.");
  return partes.join("\n");
}
