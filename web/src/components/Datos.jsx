import { BarRow, Chips, MetricGrid, Metric, Panel } from "./Blocks";
import { num } from "../lib/vf";

const tipoPill = (d = "") => (/^usar/i.test(d) ? "usar" : /descartar|no aporta/i.test(d) ? "no" : "escenario");

function CapaBloque({ clase, titulo, texto, n, filas }) {
  return (
    <div className={`cc-capa cc-capa--${clase}`}>
      <span className="label">{titulo}</span>
      <b>{num(filas)}</b>
      <span>{n} tablas · {texto}</span>
    </div>
  );
}

/* Find the truth: medallón, calidad y qué datos entran a la simulación. */
export function Datos({ payload }) {
  const d = payload?.datos;
  if (!d) return null;
  const tablas = Object.entries(d.capas ?? {});
  const capa = (c) => tablas.filter(([k]) => k.startsWith(c + ".") && !/dq_log|cuarentena|linaje|calidad/.test(k));
  const suma = (c) => capa(c).reduce((a, [, v]) => a + v, 0);
  const cuarentena = (d.cuarentena ?? []).reduce((a, x) => a + x.filas, 0);
  const calidad = [...(d.calidad ?? [])].sort((a, b) => b.filas_afectadas - a.filas_afectadas);
  const max = Math.max(1, ...calidad.map((x) => x.filas_afectadas));
  const twist = (d.linaje ?? []).find((l) => l.lote?.startsWith("twist"));
  const conserva = (l) => l.filas_bronze === l.filas_silver + l.filas_cuarentena;

  return (
    <div className="nu-stack">
      <div className="cc-capas">
        <CapaBloque clase="bronze" titulo="Bronce" texto="el archivo tal cual, todo texto, con huella por fila" n={capa("bronze").length} filas={suma("bronze")} />
        <CapaBloque clase="silver" titulo="Silver" texto={`tipado y validado; ${num(cuarentena)} filas a cuarentena`} n={capa("silver").length} filas={suma("silver")} />
        <CapaBloque clase="gold" titulo="Gold" texto="listas para el motor, el dashboard y Databricks" n={capa("gold").length} filas={suma("gold")} />
      </div>

      <Panel eyebrow="Linaje" title="Ninguna fila se pierde en silencio">
        <p className="panel__copy">
          En cada tabla, lo que entra al bronce es igual a lo que sale a silver más lo que queda en cuarentena con su motivo.
          {twist && <> El segundo dataset, <code>dataset_twist.csv</code> (lote <code>{twist.lote}</code>), pasa por las mismas tres capas y sus textos se convierten en parámetros del motor.</>}
        </p>
        <div className="table-wrap">
          <table className="data-table nu-tabla">
            <thead><tr><th>Dataset</th><th>Lote</th><th className="nu-num">Bronce</th><th className="nu-num">Silver</th><th className="nu-num">Cuarentena</th><th className="nu-num">Gold</th><th>Conserva</th></tr></thead>
            <tbody>
              {(d.linaje ?? []).map((l) => (
                <tr key={l.dataset}>
                  <td>{l.dataset}</td><td>{l.lote}</td>
                  <td className="nu-num">{num(l.filas_bronce ?? l.filas_bronze)}</td><td className="nu-num">{num(l.filas_silver)}</td>
                  <td className="nu-num">{num(l.filas_cuarentena)}</td><td className="nu-num">{num(l.filas_gold)}</td>
                  <td className={conserva(l) ? "nu-ok" : "nu-mal"}>{conserva(l) ? "Sí" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="nu-grid">
        <Panel eyebrow="Calidad" title="Lo que encontramos en los datos crudos">
          {calidad.map((x) => (
            <BarRow key={x.tabla + x.regla} label={x.regla} gloss={x.tabla} value={x.filas_afectadas} max={max} count={num(x.filas_afectadas)} />
          ))}
        </Panel>
        <Panel eyebrow="Cuarentena" title="Por qué se descartó cada fila">
          <MetricGrid cols={2}>
            {(d.cuarentena ?? []).map((c) => <Metric key={c.tabla + c.motivo} label={c.tabla} value={num(c.filas)} gloss={c.motivo} />)}
          </MetricGrid>
        </Panel>
      </div>

      <Panel eyebrow="Valor de los datos" title="Qué entra a la simulación y qué no">
        <p className="panel__copy">Cada tabla se probó contra los datos. Si una fuente contradice al macro o a las demás, no entra al caso base; si aporta un escenario, se usa solo como escenario.</p>
        <div className="table-wrap">
          <table className="data-table nu-tabla">
            <thead><tr><th>Dato</th><th>Prueba y resultado</th><th>Decisión</th><th>Motivo</th></tr></thead>
            <tbody>
              {(d.valor ?? []).map((v) => (
                <tr key={v.dato}>
                  <td>{v.dato}</td><td>{v.prueba}: <b>{v.resultado}</b></td>
                  <td><span className={`cc-pill cc-pill--${tipoPill(v.decision)}`}>{v.decision}</span></td><td>{v.motivo}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Chips items={["Bronce", "Silver", "Gold", "Cuarentena", "Linaje por fila"]} />
      </Panel>
    </div>
  );
}
