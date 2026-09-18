import { BarRow, Panel } from "./Blocks";
import { ETIQUETA, MODOS, pct, pctS } from "../lib/vf";
import "../styles/dashboard.css";

/* Tres pruebas de que la recomendación no depende de la suerte ni de un supuesto puesto a mano. */
export function Robustez({ payload, cid }) {
  const r = payload?.clientes?.[cid]?.robustez;
  if (!r) return null;
  const { estabilidad_ranking: est, sensibilidad_ruidos: sens, valor_informacion: evpi } = r;
  const modos = evpi?.estados ?? [];
  const nombres = Object.keys(evpi?.matriz_retorno_esperado ?? {});
  const mejor = modos.map((m) => Math.max(...nombres.map((n) => evpi.matriz_retorno_esperado[n][m])));

  return (
    <div className="cc-grid2">
      {est && (
        <Panel eyebrow="Estabilidad del ranking" title={est.veredicto}>
          {est.detalle.slice(0, 5).map((d) => (
            <BarRow key={d.cartera} label={ETIQUETA[d.cartera] ?? d.cartera} gloss={`posición media ${d.posicion_media.toFixed(1)}`} value={d.tasa_victoria} max={1} count={`${d.victorias} de ${est.realizaciones}`} tone="var(--cc-blue)" />
          ))}
          <p className="cc-mini">{est.ganador_estable ? "El ganador se repite en al menos 80 % de las realizaciones." : "El ganador cambia con la semilla: la diferencia entre carteras es pequeña frente al azar."} {est.alcance}.</p>
        </Panel>
      )}

      {sens && (
        <Panel eyebrow="Sensibilidad a los supuestos" title={sens.veredicto}>
          {sens.resultados.map((s) => (
            <div key={s.ruido} style={{ marginBottom: 12 }}>
              <span className="label">{s.ruido}</span>
              <div className="cc-quiebre">
                {s.puntos.map((p) => (
                  <span key={p.factor} className={`cc-punto ${p.cambia || p.base_fuera_de_presupuesto ? "cc-punto--mal" : ""}`} title={`Probabilidad de superar la tolerancia: ${pct(p.p_mdd_del_ganador_base, 0)}`}>
                    {p.factor}x · {pct(p.p_mdd_del_ganador_base, 0)}
                  </span>
                ))}
              </div>
              <p className="cc-mini">{s.punto_de_quiebre == null ? "No se rompe en ningún punto probado." : `Deja de cumplir o cambia de ganadora desde ${s.punto_de_quiebre}x.`}</p>
            </div>
          ))}
          <p className="cc-mini">Cada chip es el valor probado y la probabilidad de superar la tolerancia de caída de la cartera ganadora base.</p>
        </Panel>
      )}

      {evpi && (
        <Panel eyebrow="Valor de saber en qué estado estamos (EVPI)" title={`Como máximo ${pctS(evpi.evpi)} de retorno acumulado`}>
          <p className="panel__copy">{evpi.lectura}</p>
          <div className="table-wrap">
            <table className="data-table cc-tabla">
              <thead><tr><th>Arrepentimiento</th>{modos.map((m) => <th key={m}>{MODOS[m] ?? m}</th>)}</tr></thead>
              <tbody>
                {nombres.map((n) => (
                  <tr key={n} className={n === evpi.cartera_minimo_arrepentimiento ? "cc-fila-final" : ""}>
                    <td>{ETIQUETA[n] ?? n}</td>
                    {modos.map((m, i) => <td key={m}>{pct(mejor[i] - evpi.matriz_retorno_esperado[n][m], 1)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="cc-mini">Arrepentimiento = retorno de la mejor cartera en ese estado menos el de esta. Mínimo arrepentimiento máximo: {ETIQUETA[evpi.cartera_minimo_arrepentimiento] ?? evpi.cartera_minimo_arrepentimiento} ({pct(evpi.arrepentimiento_maximo, 1)}).</p>
        </Panel>
      )}
    </div>
  );
}
