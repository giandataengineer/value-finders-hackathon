// Clasificador determinista de los 3 tipos de cliente. Sin dependencias: lo usan el servidor (respaldo y desempate) y la interfaz (sin conexión).
export const PERFILES = {
  CL_01: { id: "CL_01", nombre: "Crecimiento Global", moneda: "USD", horizonte_meses: 18, caida: 22, liquidez: "baja", objetivo: "crecer",
    resumen: "Orientado al crecimiento: horizonte de 18 meses, tolera caídas de hasta 22% y no necesita liquidez inmediata.", restriccion: "Máx. 45% en un solo sector" },
  CL_02: { id: "CL_02", nombre: "Patrimonio Estable", moneda: "COP", horizonte_meses: 36, caida: 10, liquidez: "media", objetivo: "preservar",
    resumen: "Enfocado en la preservación patrimonial: horizonte de 36 meses, tolera caídas de hasta 10% y necesita liquidez media.", restriccion: "Máx. 25% en activos de alta volatilidad" },
  CL_03: { id: "CL_03", nombre: "Diversificación Regional", moneda: "PEN", horizonte_meses: 24, caida: 15, liquidez: "media", objetivo: "diversificar",
    resumen: "Busca diversificación geográfica: horizonte de 24 meses, tolera caídas de hasta 15% y necesita liquidez media.", restriccion: "Al menos 3 países y 3 sectores" },
};

const IDS = Object.keys(PERFILES);
const norm = (t) => String(t ?? "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
const PALABRAS = {
  CL_01: /crecer|crecimiento|rapido|agresiv|maximizar|multiplicar|arriesg|dinamic/,
  CL_02: /preserv|proteg|conserv|estable|patrimoni|no perder|seguridad|tranquil|cuidar/,
  CL_03: /diversific|region|paises|repartir|varios|internacional|geograf|no poner todo/,
};

/** Puntajes explícitos por señal. objetivo pesa 3, caída tolerada 2, texto libre 2 (una vez por perfil), horizonte, moneda y liquidez 1. */
export function clasificarPorReglas(r = {}, texto = "") {
  const p = { CL_01: 0, CL_02: 0, CL_03: 0 };
  const razones = [];
  const suma = (id, v, why) => { p[id] += v; razones.push(`${PERFILES[id].id}: ${why} (+${v})`); };

  const obj = { crecer: "CL_01", preservar: "CL_02", diversificar: "CL_03" }[r.objetivo];
  if (obj) suma(obj, 3, `objetivo "${r.objetivo}"`);

  const caida = Number(r.caida);
  if (Number.isFinite(caida) && caida > 0) {
    const id = IDS.reduce((a, b) => (Math.abs(PERFILES[b].caida - caida) < Math.abs(PERFILES[a].caida - caida) ? b : a));
    suma(id, 2, `tolera caídas de ${caida}%`);
  }

  const h = Number(r.horizonte);
  if (Number.isFinite(h) && h > 0) {
    const id = IDS.reduce((a, b) => (Math.abs(PERFILES[b].horizonte_meses - h) < Math.abs(PERFILES[a].horizonte_meses - h) ? b : a));
    suma(id, 1, `horizonte de ${h} meses`);
  }

  const m = { USD: "CL_01", COP: "CL_02", PEN: "CL_03" }[String(r.moneda).toUpperCase()];
  if (m) suma(m, 1, `moneda base ${String(r.moneda).toUpperCase()}`);

  if (r.liquidez === "baja") suma("CL_01", 1, "no necesita liquidez pronto");
  else if (r.liquidez === "media") { suma("CL_02", 0.5, "necesita liquidez media"); suma("CL_03", 0.5, "necesita liquidez media"); }

  const t = norm(texto);
  for (const id of IDS) if (t && PALABRAS[id].test(t)) suma(id, 2, "lo que escribió apunta a ese perfil");

  const orden = IDS.slice().sort((a, b) => p[b] - p[a] || (obj === b ? 1 : 0) - (obj === a ? 1 : 0));
  const total = IDS.reduce((s, id) => s + p[id], 0);
  return { cliente: orden[0], puntajes: p, confianza: total ? p[orden[0]] / total : 0, empate: p[orden[0]] === p[orden[1]], razones };
}
