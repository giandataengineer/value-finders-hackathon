import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Metric, MetricGrid, Panel } from "./Blocks";
import { pct, pctS } from "../lib/vf";

const COLORES = ["#d3222e", "#2b62d9", "#141414", "#158a5c", "#7c3aed", "#d98a1e", "#6b6b6b", "#0f9cb0"];
const fmtC = (v) => Number(v).toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/* Find the signal: la correlación cambia de régimen, hay un episodio de estrés y los eventos mueven a los activos. */
export function Senal({ payload }) {
  const s = payload?.senal;
  if (!s) return null;
  const serie = s.serie;
  const activos = Object.keys(serie.indice);
  const datos = serie.fechas.map((f, i) => ({ f, ...Object.fromEntries(activos.map((a) => [a, serie.indice[a][i]])) }));
  const stress = (s.regimenes ?? []).filter((r) => r.regimen === "Stress");
  const corr = Object.fromEntries((s.correlacion_por_fuente ?? []).map((c) => [c.fuente, c]));
  const c12 = corr.diario_12m?.correlacion_media, ch = corr.historial_intradia?.correlacion_media;

  return (
    <div className="nu-stack">
      <Panel eyebrow="La señal" title="La correlación entre activos cambia de régimen">
        <div className="nu-grande">
          <span>{fmtC(c12)}</span><span className="nu-flecha">→</span><span>{fmtC(ch)}</span>
          <small>correlación media entre los 8 activos: último año contra el historial 2020 a jul-2025</small>
        </div>
        <p className="nu-sub">
          Con correlación baja, repartir entre países y sectores sí reduce el riesgo. Con la del historial, todo cae junto y la diversificación protege mucho menos. Por eso la simulación
          incluye un escenario de estrés con esa estructura y por eso hay una recomendación defensiva. Cuál de los dos regímenes es el real no se sabe: lo tratamos como supuesto.
        </p>
      </Panel>

      <Panel eyebrow="Mercado" title="Precios de los 8 activos, base 100, últimos 12 meses">
        <div className="nu-chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={datos} margin={{ left: 4, right: 8, top: 8, bottom: 22 }}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="f" tick={{ fontSize: 11 }} minTickGap={48} tickFormatter={(d) => d.slice(0, 7)}
                label={{ value: "Fecha (año-mes)", position: "insideBottom", offset: -14, fontSize: 11, fill: "var(--muted)" }} />
              <YAxis tick={{ fontSize: 11 }} domain={["auto", "auto"]} width={40}
                label={{ value: "Precio indexado (base 100)", angle: -90, position: "insideLeft", offset: 6, fontSize: 11, fill: "var(--muted)" }} />
              <Tooltip labelFormatter={(d) => d} formatter={(v) => fmtC(v)} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {stress.map((r) => <ReferenceArea key={r.desde} x1={r.desde} x2={r.hasta} fill="#d3222e" fillOpacity={0.12} label={{ value: "Stress", fontSize: 11, fill: "#a3151f" }} />)}
              {activos.map((a, i) => <Line key={a} type="monotone" dataKey={a} stroke={COLORES[i % 8]} dot={false} strokeWidth={1.5} />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="nu-sub">La franja roja es el único episodio de estrés del macro ({stress.map((r) => `${r.desde} a ${r.hasta}, ${r.dias} días`).join("; ") || "sin episodios"}). Es corto: sirve como escenario, no para estimar un régimen completo.</p>
      </Panel>

      <Panel eyebrow="Activos" title="Riesgo y retorno por activo">
        <div className="table-wrap">
          <table className="data-table nu-tabla">
            <thead><tr><th>Activo</th><th>País</th><th>Sector</th><th className="nu-num">Retorno 12m</th><th className="nu-num">Vol. 12m</th><th className="nu-num">Caída máx. 12m</th><th className="nu-num">Vol. historial</th></tr></thead>
            <tbody>
              {(s.estadisticas_activo ?? []).map((a) => (
                <tr key={a.asset_id}>
                  <td>{a.name} <span className="label">{a.asset_id}</span></td><td>{a.pais}</td><td>{a.sector}</td>
                  <td className={`nu-num ${a.ret_12m < 0 ? "neg" : ""}`}>{pctS(a.ret_12m)}</td><td className="nu-num">{pct(a.vol_anual_12m)}</td>
                  <td className="nu-num neg">{pctS(a.caida_maxima_12m)}</td><td className="nu-num">{pct(a.vol_anual_historial)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="nu-grid">
        <Panel eyebrow="Eventos" title="Cómo reaccionó cada activo a los 5 eventos">
          <div className="table-wrap">
            <table className="data-table nu-tabla">
              <thead><tr><th>Fecha</th><th>Alcance</th><th>Activo</th><th className="nu-num">3 días</th><th className="nu-num">z</th></tr></thead>
              <tbody>
                {(s.eventos ?? []).map((e) => (
                  <tr key={e.event_date + e.asset_id}>
                    <td>{String(e.event_date).slice(0, 10)}</td><td>{e.event_type} · {e.severity}</td><td>{e.asset_id}</td>
                    <td className={`nu-num ${e.ret_3d < 0 ? "neg" : ""}`}>{pctS(e.ret_3d)}</td><td className="nu-num">{fmtC(e.z_3d)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="nu-sub">Son pocos eventos: los usamos como biblioteca de shocks, no para calibrar saltos.</p>
        </Panel>

        <Panel eyebrow="Validación" title="¿El método está bien calibrado?">
          <div className="table-wrap">
            <table className="data-table nu-tabla">
              <thead><tr><th>Método</th><th className="nu-num">Cobertura 90 %</th><th className="nu-num">Caída real sobre P95</th></tr></thead>
              <tbody>
                {(s.backtest ?? []).map((b) => (
                  <tr key={b.metodo}><td>{b.metodo}</td><td className="nu-num">{pct(b.cobertura_90_retorno, 0)}</td><td className="nu-num">{pct(b.caida_real_sobre_p95_simulado)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="nu-sub">Se entrena con 250 días y se compara con los 63 siguientes sobre el historial. Ningún método domina: la caída real supera el P95 simulado cerca del 5 % esperado.</p>
        </Panel>
      </div>
    </div>
  );
}
