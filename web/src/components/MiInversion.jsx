import { useEffect, useMemo, useRef, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Metric, MetricGrid, Panel } from "./Blocks";
import { AbanicoMonteCarlo } from "./AbanicoMonteCarlo";
import { aDinero } from "../lib/simulador";
import { BASE, ETIQUETA, FINAL, MV, MODOS, pct } from "../lib/vf";
import "../styles/simulador.css";

const CARTERAS = [FINAL, BASE, "igual ponderada", MV, "solo caja"];
const MONTO_INICIAL = { USD: 10000, COP: 40000000, PEN: 40000 };
let motorEnCache = null;

const cargarMotor = () => (motorEnCache ? Promise.resolve(motorEnCache) : fetch("motor.json").then((r) => r.json()).then((m) => (motorEnCache = m)));

/* Reglas visibles: no se esconde por qué se marca una alerta. */
const REGLAS = [
  { desde: 50, nivel: "alerta", texto: "50 % o más de los ahorros en una sola inversión: alerta de concentración." },
  { desde: 30, nivel: "atencion", texto: "Entre 30 % y 49 %: atención, una mala racha pesa mucho en el patrimonio total." },
  { desde: 0, nivel: "ok", texto: "Menos de 30 %: la inversión no domina el patrimonio." },
];

export function MiInversion({ payload, cid, setCid }) {
  const clientes = payload?.caso?.clientes ?? [];
  const cliente = clientes.find((c) => c.id === cid) ?? clientes[0];
  const [monto, setMonto] = useState(10000);
  const [porc, setPorc] = useState(20);
  const [meses, setMeses] = useState(18);
  const [cartera, setCartera] = useState(FINAL);
  const [estado, setEstado] = useState("mezcla");
  const [res, setRes] = useState(null);
  const [avance, setAvance] = useState(0);
  const [error, setError] = useState(null);
  const [corrida, setCorrida] = useState(0);
  const worker = useRef(null);

  useEffect(() => {
    if (!cliente) return;
    setMonto(MONTO_INICIAL[cliente.moneda] ?? 10000);
    setMeses(cliente.horizonte_meses);
  }, [cliente?.id]);

  useEffect(() => {
    if (!cliente) return undefined;
    setError(null);
    const t = setTimeout(async () => {
      worker.current?.terminate();
      try {
        const motor = await cargarMotor();
        const w = new Worker(new URL("../lib/simulador.worker.js", import.meta.url), { type: "module" });
        worker.current = w;
        setAvance(0);
        w.onmessage = (e) => {
          if (e.data.tipo === "progreso") setAvance(e.data.p);
          if (e.data.tipo === "listo") { setRes(e.data.r); setAvance(1); w.terminate(); }
          if (e.data.tipo === "error") { setError(e.data.mensaje); w.terminate(); }
        };
        w.postMessage({ motor, opciones: { cid: cliente.id, cartera, meses, estado, sims: 10000 } });
      } catch (err) { setError(String(err)); }
    }, 350);
    return () => clearTimeout(t);
  }, [cliente?.id, cartera, meses, estado, corrida]);

  useEffect(() => () => worker.current?.terminate(), []);

  const dinero = useMemo(() => (res ? aDinero(res, monto) : null), [res, monto]);
  useEffect(() => {
    if (!res || !dinero) return;
    window.dispatchEvent(new CustomEvent("vf:simulacion", { detail: {
      cid: cliente.id, monto, porcentaje_ahorros: porc, horizonte: meses, cartera, estado, moneda: cliente.moneda,
      percentiles: res.percentiles, en_dinero: dinero, prob_perdida: res.prob_perdida, p_caida: res.p_caida, cvar5: res.cvar5,
    } }));
  }, [res, monto, porc, cliente?.id]);

  if (!cliente) return null;
  const fmt = (v) => new Intl.NumberFormat("es-CO", { style: "currency", currency: cliente.moneda, maximumFractionDigits: 0 }).format(v);
  const ahorros = monto / (porc / 100);
  const regla = REGLAS.find((r) => porc >= r.desde);
  const peorSobreAhorros = dinero ? (dinero.peor5 / ahorros) : 0;
  const presupuesto = cliente.presupuesto_riesgo;

  const datos = res ? res.abanico.meses.map((m, i) => ({
    mes: m, banda90: [monto * res.abanico.p5[i], monto * res.abanico.p95[i]], banda50: [monto * res.abanico.p25[i], monto * res.abanico.p75[i]], mediana: monto * res.abanico.p50[i],
  })) : [];

  const lectura = res && dinero ? (
    `Con ${fmt(monto)} en la cartera "${ETIQUETA[cartera]}" durante ${meses} meses, la mitad de los futuros simulados termina por encima de ${fmt(dinero.final_p50)} `
    + `(${dinero.mediana >= 0 ? "ganancia" : "pérdida"} de ${fmt(Math.abs(dinero.mediana))}). En el 5 % de los casos más favorables pasa de ${fmt(monto + dinero.techo)}, `
    + `y en el 5 % de los más adversos queda por debajo de ${fmt(monto + dinero.piso)}. Se pierde dinero en ${pct(res.prob_perdida, 0)} de los futuros.`
  ) : "";

  const recomendaciones = [
    "Un fondo de emergencia de unos 6 meses de gastos, fuera de esta inversión, evita vender en un mal momento.",
    `Conviene invertir solo lo que no se necesitará antes de ${meses} meses: el resultado se ve claro en el horizonte, no en el camino.`,
    "Entrar por tramos (por ejemplo en 3 o 4 aportes) reduce el riesgo de comprar justo antes de una caída.",
    `La tolerancia de caída de este perfil es ${pct(cliente.tolerancia_caida, 0)}; en ${pct(res?.p_caida ?? 0, 0)} de los futuros la caída máxima la supera (presupuesto de riesgo: ${pct(presupuesto, 0)}). Vale la pena que la persona revise si la tolera de verdad.`,
    ...(cliente.moneda !== "USD" ? [`Los activos cotizan en USD y el cliente piensa en ${cliente.moneda}: el tipo de cambio suma riesgo propio, y un monto que se necesitará en ${cliente.moneda} a corto plazo puede convenir en esa moneda.`] : []),
  ];

  return (
    <div className="mi-inv" id="mi-inversion">
      <Panel eyebrow="Mi inversión" title="¿Cuánto podría ganar o perder?">
        <p className="panel__copy">
          Elige el perfil, el monto y cuánto de tus ahorros representa. Corremos 10.000 futuros en tu navegador con el mismo motor que la simulación de Python y te mostramos el rango en dinero, no una cifra única.
        </p>

        <div className="role-tabs" role="tablist">
          {clientes.map((c) => (
            <button key={c.id} role="tab" aria-selected={c.id === cliente.id} className={`role-tab ${c.id === cliente.id ? "is-on" : ""}`} onClick={() => setCid?.(c.id)}>
              {c.id.replace("_", " ")} · {c.nombre}
            </button>
          ))}
        </div>

        <div className="mi-inv__form">
          <label>Monto a invertir ({cliente.moneda})
            <input type="number" min="0" step={cliente.moneda === "COP" ? 1000000 : 1000} value={monto} onChange={(e) => setMonto(Math.max(0, Number(e.target.value) || 0))} />
          </label>
          <label>Porcentaje de mis ahorros totales: <b>{porc} %</b>
            <input type="range" min="5" max="100" step="5" value={porc} onChange={(e) => setPorc(Number(e.target.value))} />
          </label>
          <label>Horizonte: <b>{meses} meses</b>
            <input type="range" min="6" max="36" step="1" value={meses} onChange={(e) => setMeses(Number(e.target.value))} />
          </label>
          <label>Cartera
            <select value={cartera} onChange={(e) => setCartera(e.target.value)}>{CARTERAS.map((c) => <option key={c} value={c}>{ETIQUETA[c]}</option>)}</select>
          </label>
          <label>Estado del mercado
            <select value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="mezcla">Mezcla 55/30/15 (recomendado)</option>
              {Object.entries(MODOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        </div>

        <button type="button" className="mi-inv__boton-simular" disabled={avance < 1} onClick={() => setCorrida((n) => n + 1)}>
          Simular 10.000 futuros
        </button>

        <div className="mi-inv__estado" aria-live="polite">
          {error ? `No se pudo simular: ${error}` : avance < 1 ? `Simulando ${Math.round(avance * 100)} %` : `${res?.sims.toLocaleString("es-CO")} futuros evaluados`}
          <i style={{ width: `${Math.round(avance * 100)}%` }} />
        </div>
      </Panel>

      {res && dinero && (
        <>
          <MetricGrid cols={3}>
            <Metric label="Podrías ganar (mediana)" value={`${dinero.mediana >= 0 ? "+" : "-"}${fmt(Math.abs(dinero.mediana))}`} gloss="La mitad de los futuros termina mejor que esto." accent />
            <Metric label="Techo razonable (P95)" value={`${dinero.techo >= 0 ? "+" : "-"}${fmt(Math.abs(dinero.techo))}`} gloss="Solo 1 de cada 20 futuros lo supera." />
            <Metric label="Podrías perder (P5)" value={`${dinero.piso >= 0 ? "+" : "-"}${fmt(Math.abs(dinero.piso))}`} gloss="En 1 de cada 20 futuros el resultado es peor que esto." />
            <Metric label="Peor 5 % promedio" value={fmt(dinero.peor5)} gloss="Promedio de los futuros más adversos (CVaR 5 %)." />
            <Metric label="Probabilidad de perder" value={pct(res.prob_perdida, 0)} gloss="Futuros que terminan por debajo de lo invertido." />
            <Metric label="Cae más que tu tolerancia" value={pct(res.p_caida, 0)} gloss={`Tolerancia ${pct(res.tolerancia, 0)}; presupuesto ${pct(presupuesto, 0)}.`} />
          </MetricGrid>

          <Panel eyebrow="Abanico de futuros" title={`Valor de tu inversión en ${cliente.moneda}`}>
            <p className="panel__copy">{lectura}</p>
            <AbanicoMonteCarlo res={res} monto={monto} />
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={datos} margin={{ left: 8, right: 8, top: 8 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="mes" tickFormatter={(m) => `${m} m`} />
                <YAxis width={82} tickFormatter={(v) => new Intl.NumberFormat("es-CO", { notation: "compact", maximumFractionDigits: 1 }).format(v)} domain={["auto", "auto"]} />
                <Tooltip formatter={(v) => (Array.isArray(v) ? `${fmt(v[0])} a ${fmt(v[1])}` : fmt(v))} labelFormatter={(m) => `Mes ${m}`} />
                <Area dataKey="banda90" name="P5 a P95" stroke="none" fill="#2b62d9" fillOpacity={0.16} isAnimationActive={false} />
                <Area dataKey="banda50" name="P25 a P75" stroke="none" fill="#2b62d9" fillOpacity={0.3} isAnimationActive={false} />
                <Line dataKey="mediana" name="Mediana" stroke="#d3222e" strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </Panel>

          <Panel eyebrow="Si pongo todos mis ahorros" title="Qué mirar antes de concentrar">
            <div className={`mi-inv__alerta mi-inv__alerta--${regla.nivel}`}>
              <b>{porc} % de tus ahorros</b> ({fmt(ahorros)} en total). En el peor 5 % de los casos perderías en promedio <b>{pct(Math.abs(peorSobreAhorros), 1)}</b> de todo tu patrimonio, no solo de esta inversión.
              {regla.nivel === "alerta" && " Es una concentración alta."}
            </div>
            <p className="label" style={{ marginTop: 18 }}>Reglas que aplicamos</p>
            <ul className="mi-inv__reglas">
              {REGLAS.map((r) => <li key={r.desde} className={r.nivel === regla.nivel ? "es-activa" : ""}>{r.texto}</li>)}
            </ul>
            <p className="label" style={{ marginTop: 18 }}>Qué podrían considerar las personas</p>
            <ul className="mi-inv__reglas">{recomendaciones.map((t) => <li key={t}>{t}</li>)}</ul>
            <p className="mi-inv__nota">Las decisiones las toman las personas; esto es un insight sobre un caso sintético y no es asesoría financiera.</p>
          </Panel>
        </>
      )}
    </div>
  );
}
