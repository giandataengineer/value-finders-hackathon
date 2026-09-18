import { useEffect, useRef } from "react";
import { gsap } from "gsap";

/* Degradado azul -> teal -> dorado -> rojo Credicorp: sigue el orden de resultado final de cada ruta, no es decorativo al azar. */
const PARADAS = ["#2b62d9", "#3f9bd6", "#1d9a8f", "#c98a00", "#d3222e"];
const rgb = (hex) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
const PARADAS_RGB = PARADAS.map(rgb);

function color(t) {
  const n = PARADAS_RGB.length - 1;
  const f = Math.min(0.999999, Math.max(0, t)) * n;
  const i = Math.floor(f);
  const l = f - i;
  const [r1, g1, b1] = PARADAS_RGB[i];
  const [r2, g2, b2] = PARADAS_RGB[Math.min(i + 1, n)];
  return `rgb(${Math.round(r1 + (r2 - r1) * l)}, ${Math.round(g1 + (g2 - g1) * l)}, ${Math.round(b1 + (b2 - b1) * l)})`;
}

/* Abanico animado de trayectorias individuales del Monte Carlo (imagen "viva" para el pitch).
   La lectura precisa con ejes, tooltip y bandas de percentil sigue disponible en el gráfico de abajo;
   este canvas es la pieza visual de impacto, por eso va marcado aria-hidden. */
export function AbanicoMonteCarlo({ res, monto }) {
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    const rutas = res?.trayectorias?.rutas;
    const meses = res?.trayectorias?.meses;
    if (!wrap || !canvas || !rutas?.length || !meses?.length) return undefined;

    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const n = rutas.length;
    const rutasDinero = rutas.map(({ ruta }) => ruta.map((v) => v * monto));
    const medianaDinero = res.abanico ? [monto, ...res.abanico.p50.map((v) => v * monto)] : null;

    let vmin = Infinity;
    let vmax = -Infinity;
    for (const r of rutasDinero) for (const v of r) { if (v < vmin) vmin = v; if (v > vmax) vmax = v; }
    const pad = (vmax - vmin) * 0.06 || Math.abs(vmax || monto) * 0.06 || 1;
    vmin -= pad; vmax += pad;

    const M = { l: 6, r: 6, t: 14, b: 8 };
    let pActual = 0;

    function medidas() {
      const rect = wrap.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    }
    const ejeX = (i) => M.l * dpr + (i / (meses.length - 1)) * (canvas.width - (M.l + M.r) * dpr);
    const ejeY = (v) => canvas.height - M.b * dpr - ((v - vmin) / (vmax - vmin)) * (canvas.height - (M.t + M.b) * dpr);

    function trazarParcial(pts, frac) {
      const totalTramos = pts.length - 1;
      const avance = frac * totalTramos;
      const completos = Math.floor(avance);
      ctx.beginPath();
      ctx.moveTo(ejeX(0), ejeY(pts[0]));
      for (let i = 1; i <= completos; i += 1) ctx.lineTo(ejeX(i), ejeY(pts[i]));
      if (completos < totalTramos) {
        const resto = avance - completos;
        const a = pts[completos];
        const b = pts[completos + 1];
        ctx.lineTo(ejeX(completos + resto), ejeY(a + (b - a) * resto));
      }
      ctx.stroke();
    }

    function dibujar(p) {
      pActual = p;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.lineJoin = "round";
      ctx.lineCap = "round";

      ctx.save();
      ctx.setLineDash([4 * dpr, 5 * dpr]);
      ctx.strokeStyle = "rgba(20,20,20,.18)";
      ctx.lineWidth = dpr;
      ctx.beginPath();
      ctx.moveTo(ejeX(0), ejeY(monto));
      ctx.lineTo(ejeX(meses.length - 1), ejeY(monto));
      ctx.stroke();
      ctx.restore();

      const dur = n > 40 ? 0.5 : 0.65;
      rutasDinero.forEach((ruta, i) => {
        const t = n > 1 ? i / (n - 1) : 0.5;
        const inicio = n > 1 ? (i / n) * (1 - dur) : 0;
        const local = Math.min(1, Math.max(0, (p - inicio) / dur));
        if (local <= 0) return;
        ctx.globalAlpha = 0.32 + 0.32 * (1 - Math.abs(t - 0.5) * 2);
        ctx.strokeStyle = color(t);
        ctx.lineWidth = 1.1 * dpr;
        trazarParcial(ruta, local);
      });
      ctx.globalAlpha = 1;

      if (medianaDinero) {
        const local = Math.min(1, Math.max(0, (p - 0.22) / 0.78));
        if (local > 0) {
          ctx.strokeStyle = "#d3222e";
          ctx.lineWidth = 2.6 * dpr;
          ctx.shadowColor = "rgba(211,34,46,.35)";
          ctx.shadowBlur = 6 * dpr;
          trazarParcial(medianaDinero, local);
          ctx.shadowBlur = 0;
        }
      }
    }

    medidas();
    const ro = new ResizeObserver(() => { medidas(); dibujar(pActual); });
    ro.observe(wrap);

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let tween = null;
    if (reduceMotion) {
      dibujar(1);
    } else {
      dibujar(0);
      const estado = { p: 0 };
      tween = gsap.to(estado, { p: 1, duration: 2.6, ease: "power2.out", onUpdate: () => dibujar(estado.p) });
    }

    return () => { ro.disconnect(); tween?.kill(); };
  }, [res, monto]);

  if (!res?.trayectorias?.rutas?.length) return null;

  return (
    <div className="abanico-mc" ref={wrapRef}>
      <canvas ref={canvasRef} aria-hidden="true" />
      <span className="abanico-mc__etq">{res.sims.toLocaleString("es-CO")} futuros · {res.trayectorias.rutas.length} rutas mostradas</span>
    </div>
  );
}
