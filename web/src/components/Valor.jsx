import { useMemo } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarRow, Metric, MetricGrid, Panel } from "./Blocks";
import { BASE, ETIQUETA, FINAL, MODOS, nombreActivo, num, pct, pctS, pesosVisibles } from "../lib/vf";
import "../styles/dashboard.css";

export function PestanasCliente({ payload, cid, setCid }) {
  const clientes = payload?.caso?.clientes ?? [];
  return (
    <div className="role-tabs" role="tablist">
      {clientes.map((c) => (
        <button key={c.id} role="tab" aria-selected={cid === c.id} className={`role-tab ${cid === c.id ? "is-on" : ""}`} onClick={() => setCid(c.id)}>
          {c.id.replace("CL_", "Cliente ")} · {c.nombre}
        </button>
      ))}
    </div>
  );
}

function Pesos({ payload, pesos }) {
  const filas = pesosVisibles(pesos);
  const max = Math.max(0.01, ...filas.map(([, v]) => v));
  return filas.map(([k, v]) => (
    <BarRow key={k} label={k === "CAJA" ? "Caja (USD, rinde la tasa a 10 años)" : nombreActivo(payload, k)} value={v} max={max} count={pct(v, 0)} tone={k === "CAJA" ? "var(--faint)" : "var(--cc-blue)"} />
  ));
}

export function Valor({ payload, cid, setCid }) {
  const c = payload?.clientes?.[cid];
  const perfil = payload?.caso?.clientes?.find((x) => x.id === cid);
  const fan = useMemo(() => {
    const a = c?.abanico;
    if (!a) return [];
    const q = a.p5_p25_p50_p75_p95;
    return a.meses.map((mes, i) => ({ mes, banda90: [(q[0][i] - 1) * 100, (q[4][i] - 1) * 100], banda50: [(q[1][i] - 1) * 100, (q[3][i] - 1) * 100], mediana: (q[2][i] - 1) * 100 }));
  }, [c]);
  if (!c || !perfil) return null;

  const m = c.metricas;
  const fin = m.base_neutral[FINAL];
  const mez = c.superposicion_estados?.[FINAL];
  const pm = (modo) => m[modo]?.[FINAL]?.p_mdd_sobre_tol;
  const nombres = Object.keys(c.carteras);

  return (
    <div className="cc-seccion">
      <PestanasCliente payload={payload} cid={cid} setCid={setCid} />
      <p className="panel__copy">
        {perfil.nombre}: {perfil.prioridad.toLowerCase()}, en {perfil.moneda}, horizonte de {perfil.horizonte_meses} meses, tolera una caída máxima de {pct(perfil.tolerancia_caida, 0)}
        y aceptamos superarla como máximo {pct(perfil.presupuesto_riesgo, 0)} de las veces. Restricción: {perfil.restriccion}. Son insights para que decida una persona.
      </p>

      <div className="cc-grid2">
        <Panel eyebrow="Recomendación defensiva" title="Optimizada sobre la mezcla de estados 55 / 30 / 15">
          <Pesos payload={payload} pesos={c.carteras[FINAL]} />
          <p className="cc-mini">Cumple el presupuesto de riesgo con un 15 % de probabilidad de estrés: {mez && mez.p_mdd_sobre_tol <= perfil.presupuesto_riesgo ? "sí" : "no"}.</p>
        </Panel>
        <Panel eyebrow="Alternativa sin estrés" title="Robusta a dos supuestos de retorno (neutral y con lo realizado)">
          <Pesos payload={payload} pesos={c.carteras[BASE]} />
          <p className="cc-mini">Rinde más si no llega una crisis y cede protección si llega.</p>
        </Panel>
      </div>

      <MetricGrid cols={4}>
        <Metric label="Retorno anual mediano" value={pctS(fin.ret_anual_mediano)} gloss="Escenario neutral, moneda base del cliente" accent />
        <Metric label="Peor 5 % (P5)" value={pctS(fin.p5)} gloss="Retorno total al horizonte" />
        <Metric label="Mejor 5 % (P95)" value={pctS(fin.p95)} gloss="Retorno total al horizonte" />
        <Metric label="Probabilidad de pérdida" value={pct(fin.prob_perdida, 0)} gloss="Terminar por debajo de lo invertido" />
        <Metric label={`Cae más que ${pct(perfil.tolerancia_caida, 0)}: neutral`} value={pct(pm("base_neutral"), 0)} gloss={MODOS.base_neutral} />
        <Metric label="Con lo realizado" value={pct(pm("base_realizado"), 0)} gloss="Retorno del último año a medias" />
        <Metric label="Estrés 2020-2025" value={pct(pm("estres_historial_2020_2025"), 0)} gloss="Correlación entre activos 0,80" />
        <Metric label="Mezcla 55 / 30 / 15" value={pct(mez?.p_mdd_sobre_tol, 0)} gloss={`Presupuesto: ${pct(perfil.presupuesto_riesgo, 0)}`} accent />
      </MetricGrid>

      <Panel eyebrow="Abanico de resultados" title={`Valor de la cartera recomendada mes a mes (${perfil.moneda}, variación %)`}>
        <div className="cc-fan">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={fan} margin={{ left: 4, right: 8, top: 8, bottom: 22 }}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="mes" tickLine={false} axisLine={false} unit=" m"
                label={{ value: "Mes del horizonte", position: "insideBottom", offset: -14, fontSize: 11, fill: "var(--muted)" }} />
              <YAxis tickLine={false} axisLine={false} unit="%" width={44}
                label={{ value: "Variación de la cartera (%)", angle: -90, position: "insideLeft", offset: 6, fontSize: 11, fill: "var(--muted)" }} />
              <Tooltip formatter={(v) => (Array.isArray(v) ? `${num(v[0], 1)} % a ${num(v[1], 1)} %` : `${num(v, 1)} %`)} labelFormatter={(l) => `Mes ${l}`} />
              <Area type="monotone" dataKey="banda90" name="P5 a P95" stroke="none" fill="var(--cc-blue)" fillOpacity={0.14} />
              <Area type="monotone" dataKey="banda50" name="P25 a P75" stroke="none" fill="var(--cc-blue)" fillOpacity={0.28} />
              <Area type="monotone" dataKey="mediana" name="Mediana" stroke="var(--cc-red)" strokeWidth={2} fill="none" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel eyebrow="Las 7 carteras comparadas" title="Qué gana y qué cuesta cada una, con las mismas 10.000 simulaciones">
        <div className="table-wrap">
          <table className="data-table cc-tabla">
            <thead>
              <tr><th>Cartera</th><th>Retorno anual mediano</th><th>P5</th><th>Prob. pérdida</th><th>Cae más que la tolerancia (mezcla)</th><th>En estrés</th><th>Restricciones</th></tr>
            </thead>
            <tbody>
              {nombres.map((n) => {
                const a = m.base_neutral[n];
                const z = c.superposicion_estados?.[n];
                const ok = a.cumple_restricciones_cliente;
                return (
                  <tr key={n} className={n === FINAL ? "cc-fila-final" : ok ? "" : "cc-fila-no"}>
                    <td>{ETIQUETA[n] ?? n}</td>
                    <td>{pctS(a.ret_anual_mediano)}</td>
                    <td className={a.p5 < 0 ? "cc-neg" : ""}>{pctS(a.p5)}</td>
                    <td>{pct(a.prob_perdida, 0)}</td>
                    <td className={z?.p_mdd_sobre_tol > perfil.presupuesto_riesgo ? "cc-neg" : ""}>{pct(z?.p_mdd_sobre_tol, 0)}</td>
                    <td>{pct(m.estres_historial_2020_2025[n].p_mdd_sobre_tol, 0)}</td>
                    <td><span className={`chip ${ok ? "cc-chip-ok" : "cc-chip-no"}`}>{ok ? "Cumple" : "No cumple las del cliente"}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="cc-mini">Rojo: supera el presupuesto de riesgo del cliente. La cartera clásica de Markowitz se calcula con media y covarianza muestrales, sin conocer la tolerancia de caída.</p>
      </Panel>
    </div>
  );
}
