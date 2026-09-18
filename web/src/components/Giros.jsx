import { BarRow, Panel } from "./Blocks";
import { pct } from "../lib/vf";

/* Giros de la trama (dataset_twist.csv): qué cambia con cada novedad. Insights para que decida una persona. */
export function Giros({ payload, cid }) {
  const g = payload?.giros;
  return (
    <section className="nu-giros-sec" id="giros">
      <div className="shell">
        <span className="label">Giros de la trama · dataset_twist</span>
        <h3 className="display" style={{ fontSize: "var(--display-md)", margin: "14px 0 18px" }}>Tres novedades del 17 de agosto.</h3>
        {!g?.insights ? (
          <p className="nu-aviso">El análisis de los giros todavía no está disponible en esta versión.</p>
        ) : (
          <div className="nu-stack">
            <div className="nu-giros">
              {(g.giros ?? []).map((x) => (
                <article className="nu-giro" key={x.giro_id}>
                  <span className="nu-giro__n">{x.giro_id} · {x.tipo}</span>
                  <h4>{x.informacion}</h4>
                  <p className="nu-sub">{x.accion_requerida}</p>
                  <span className="nu-giro__cli">Afecta a {x.clientes_afectados}</span>
                </article>
              ))}
            </div>
            <div className="nu-giros">
              {g.insights.filter((i) => i.cliente === "todos" || i.cliente === cid || i.giro !== "TW_01").map((i) => (
                <article className="nu-giro" key={i.giro + i.cliente}>
                  <span className="nu-giro__n">{i.giro} · {i.cliente === "todos" ? "todos los clientes" : i.cliente}</span>
                  <h4>{i.titulo}</h4>
                  <p>{i.texto}</p>
                </article>
              ))}
            </div>
            {g.clientes?.[cid]?.TW_01?.malla_choque_valoracion && (
              <Panel eyebrow={`Tasa +65 pb · ${cid}`} title="Hasta dónde aguanta la cartera si las acciones se reprecian">
                <p className="panel__copy">Probabilidad de superar la tolerancia de caída, con la mezcla de estados, contra el presupuesto de riesgo del cliente ({pct(g.clientes[cid].TW_01.presupuesto, 0)}).</p>
                {g.clientes[cid].TW_01.malla_choque_valoracion.map((m) => (
                  <BarRow key={m.choque} label={m.choque === 0 ? "Sin repricing" : `Repricing de ${pct(m.choque, 0)}`} gloss={m.p_mdd > g.clientes[cid].TW_01.presupuesto ? "fuera del presupuesto" : "dentro del presupuesto"}
                    value={m.p_mdd} max={1} count={pct(m.p_mdd, 0)} tone={m.p_mdd > g.clientes[cid].TW_01.presupuesto ? "var(--cc-red)" : "var(--green)"} />
                ))}
              </Panel>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
