import { useMemo, useState } from "react";
import CountUp from "../reactbits/CountUp";
import { IconTrendUp } from "./Icons";

const RANGES = ["P5", "P50", "P95"];

/* Histograma decorativo estable: la misma semilla da siempre la misma forma. Las cifras que lo rodean salen del payload. */
function bars(seed, n = 34) {
  return Array.from({ length: n }, (_, i) => {
    const x = (i / (n - 1)) * 2 - 1;
    return Math.max(0.05, Math.min(1, Math.exp(-(x * x) / 0.24) + Math.sin(seed + i * 1.7) * 0.08));
  });
}
const SEEDS = { ingesta: 1.2, uplift: 3.4, montecarlo: 5.6, reporte: 7.8, briefing: 0.4 };

export function Console({ cliente, metricas, phase }) {
  const [range, setRange] = useState("P50");
  const data = useMemo(() => bars(SEEDS[phase] ?? 1.2), [phase]);
  const peak = data.indexOf(Math.max(...data));
  const m = metricas;
  const shown = m ? { P5: m.p5, P50: m.ret_mediano, P95: m.p95 }[range] : 0;

  return (
    <article className="console">
      <div className="console__head">
        <h3>{cliente ? `${cliente.nombre}` : "Cartera recomendada"}</h3>
        <span className="label">10.000 futuros</span>
      </div>

      <div className="console__odo">
        {m ? (
          <>
            <span className="console__odo-unit">{shown < 0 ? "-" : "+"}</span>
            <span style={{ fontSize: 40, fontWeight: 500 }} key={range}><CountUp to={Math.round(Math.abs(shown || 0) * 1000) / 10} duration={1.2} startWhen /></span>
            <span className="console__odo-unit" style={{ marginLeft: 4 }}>%</span>
          </>
        ) : <span className="console__odo-empty">-</span>}
      </div>

      <span className="console__delta">
        <IconTrendUp />
        {m ? `Retorno total al horizonte · pérdida ${(m.prob_perdida * 100).toFixed(0)} % de las veces` : "Cargando resultados"}
      </span>

      <div className="console__bars">
        {data.map((h, i) => <i key={i} data-hot={i === peak} style={{ height: `${h * 100}%`, animationDelay: `${i * 0.018}s` }} />)}
      </div>

      <div className="console__range">
        {RANGES.map((r) => <button key={r} type="button" aria-pressed={r === range} onClick={() => setRange(r)}>{r}</button>)}
      </div>

      {m && (
        <div className="console__block">
          <div className="console__block-row"><span className="label">Retorno anual mediano</span><b>{(m.ret_anual_mediano * 100).toFixed(1)} %</b></div>
        </div>
      )}
      {m && (
        <div className="console__block">
          <div className="console__block-row"><span className="label">Cae más que su tolerancia</span><b>{(m.p_mdd_sobre_tol * 100).toFixed(0)} % de las veces</b></div>
          <div className="console__meter"><i style={{ width: `${Math.min(100, m.p_mdd_sobre_tol * 100 * 3)}%` }} /></div>
        </div>
      )}
      {cliente && <p className="label" style={{ display: "block", marginTop: 16 }}>{cliente.moneda} · {cliente.horizonte_meses} meses · solo insights, decide una persona</p>}
    </article>
  );
}
