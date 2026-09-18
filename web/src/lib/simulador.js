/* Monte Carlo en el navegador. Replica src/simulacion.py: bootstrap de bloques circulares, deriva por estado,
   caja a rf, conversión a moneda base con el tipo de cambio acumulado y caída máxima con pico inicial 1.
   Es JS puro (sin DOM) para que corra igual en el Web Worker y en la prueba de Node. */

export function mulberry32(semilla) {
  let a = semilla >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const ESTADOS = ["base_neutral", "base_realizado", "estres_historial_2020_2025"];

function cuantil(ordenado, q) {
  const pos = (ordenado.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return ordenado[lo] + (ordenado[hi] - ordenado[lo]) * (pos - lo);
}

/* Tabla de un estado: retorno simple de la cartera por fila de historia (pesos constantes, rebalanceo diario), fx acumulable y bloque. */
function estado(motor, clave, w, fxMoneda) {
  const n = motor.activos.length;
  const cajaDia = (1 + motor.rf) ** (1 / motor.dias) - 1;
  const esEstres = clave === ESTADOS[2];
  const R = esEstres ? motor.estres : motor.base;
  const drift = new Float64Array(n);
  if (!esEstres) {
    for (let i = 0; i < n; i += 1) {
      const mu = clave === ESTADOS[0] ? motor.rf + motor.erp : motor.rf + motor.encoger * (motor.ret12[i] - motor.rf);
      drift[i] = (Math.log1p(mu) - 0.5 * motor.sigma_anual[i] ** 2) / motor.dias;
    }
  }
  const RP = new Float64Array(R.length);
  for (let t = 0; t < R.length; t += 1) {
    let s = w[n] * cajaDia;
    for (let i = 0; i < n; i += 1) s += w[i] * Math.expm1(R[t][i] + drift[i]);
    RP[t] = s;
  }
  return { T: R.length, RP, fx: esEstres ? null : fxMoneda, bloque: motor.bloque[clave] };
}

function trayectoria(E, H, meses, rng, abanico, off) {
  let V = 1;
  let fxc = 0;
  let pico = 1;
  let mdd = 0;
  let mes = 0;
  let t = 0;
  let vb = 1;
  while (t < H) {
    const ini = Math.floor(rng() * E.T);
    for (let k = 0; k < E.bloque && t < H; k += 1, t += 1) {
      const idx = (ini + k) % E.T;
      V *= 1 + E.RP[idx];
      if (E.fx) fxc += E.fx[idx];
      vb = E.fx ? V * Math.exp(fxc) : V;
      if (vb > pico) pico = vb;
      const dd = 1 - vb / pico;
      if (dd > mdd) mdd = dd;
      if ((t + 1) % 21 === 0 && mes < meses) {
        abanico[off + mes] = vb;
        mes += 1;
      }
    }
  }
  return { vb, mdd };
}

/* opciones: { cid, cartera, meses, sims, estado: "mezcla" | ESTADOS[i], semilla }
   Devuelve percentiles del valor final de 1 unidad invertida, probabilidades y el abanico mensual. */
export function simular(motor, opciones, alAvanzar) {
  const c = motor.clientes[opciones.cid];
  const w = c.carteras[opciones.cartera];
  if (!w) throw new Error(`cartera desconocida: ${opciones.cartera}`);
  const meses = opciones.meses ?? c.meses;
  const H = meses * 21;
  const sims = opciones.sims ?? 5000;
  const rng = mulberry32(opciones.semilla ?? motor.semilla);
  const fx = motor.fx[c.moneda] ?? null;
  const claves = opciones.estado && opciones.estado !== "mezcla" ? [opciones.estado] : ESTADOS;
  const tablas = claves.map((k) => estado(motor, k, w, fx));
  const pesos = claves.map((k) => motor.prob_estados[k]);
  const total = pesos.reduce((a, b) => a + b, 0);
  const acum = [];
  pesos.reduce((s, p, i) => { acum[i] = (s + p) / total; return s + p; }, 0);

  const term = new Float64Array(sims);
  const caidas = new Float64Array(sims);
  const fan = new Float64Array(sims * meses);
  for (let s = 0; s < sims; s += 1) {
    let k = 0;
    if (tablas.length > 1) {   // medir el estado: cada trayectoria colapsa a uno segun su probabilidad
      const u = rng();
      while (k < acum.length - 1 && u > acum[k]) k += 1;
    }
    const r = trayectoria(tablas[k], H, meses, rng, fan, s * meses);
    term[s] = r.vb;
    caidas[s] = r.mdd;
    if (alAvanzar && s % 250 === 0) alAvanzar(s / sims);
  }

  const ord = Float64Array.from(term).sort();
  const p = { p5: cuantil(ord, 0.05), p25: cuantil(ord, 0.25), p50: cuantil(ord, 0.5), p75: cuantil(ord, 0.75), p95: cuantil(ord, 0.95) };
  let suma = 0;
  let n5 = 0;
  let perdidas = 0;
  let sobre = 0;
  for (let s = 0; s < sims; s += 1) {
    if (term[s] - 1 <= p.p5 - 1) { suma += term[s] - 1; n5 += 1; }
    if (term[s] < 1) perdidas += 1;
    if (caidas[s] > c.tolerancia) sobre += 1;
  }
  const abanico = { meses: [], p5: [], p25: [], p50: [], p75: [], p95: [] };
  const col = new Float64Array(sims);
  for (let m = 0; m < meses; m += 1) {
    for (let s = 0; s < sims; s += 1) col[s] = fan[s * meses + m];
    const o = col.slice().sort();
    abanico.meses.push(m + 1);
    ["p5", "p25", "p50", "p75", "p95"].forEach((k, j) => abanico[k].push(cuantil(o, [0.05, 0.25, 0.5, 0.75, 0.95][j])));
  }

  // Muestra de trayectorias individuales para el abanico visual, ordenadas por resultado final
  // para que el degradado de color siga la distribución real (no un subconjunto arbitrario).
  const nMuestra = Math.min(220, sims);
  const ordenIdx = Array.from({ length: sims }, (_, i) => i).sort((a, b) => term[a] - term[b]);
  const rutas = [];
  for (let j = 0; j < nMuestra; j += 1) {
    const pos = nMuestra > 1 ? Math.round((j * (sims - 1)) / (nMuestra - 1)) : 0;
    const s = ordenIdx[pos];
    const ruta = new Array(meses + 1);
    ruta[0] = 1;
    for (let m = 0; m < meses; m += 1) ruta[m + 1] = fan[s * meses + m];
    rutas.push({ v: term[s], ruta });
  }

  return {
    percentiles: p, prob_perdida: perdidas / sims, p_caida: sobre / sims, cvar5: suma / n5,
    mdd_mediano: cuantil(Float64Array.from(caidas).sort(), 0.5),
    ret_anual_mediano: p.p50 ** (motor.dias / H) - 1,
    abanico, tolerancia: c.tolerancia, meses, sims, moneda: c.moneda,
    trayectorias: { meses: [0, ...abanico.meses], rutas },
  };
}

/* Traduce el resultado a dinero: el valor final es por unidad invertida. */
export function aDinero(r, monto) {
  const g = (v) => monto * (v - 1);
  return { mediana: g(r.percentiles.p50), techo: g(r.percentiles.p95), piso: g(r.percentiles.p5), peor5: monto * r.cvar5, final_p50: monto * r.percentiles.p50 };
}
