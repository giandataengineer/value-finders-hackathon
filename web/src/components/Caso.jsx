import { pct } from "../lib/vf";

const PREGUNTAS = [
  ["01", "¿Qué está ocurriendo en el mercado?"],
  ["02", "¿Qué datos o señales lo explican?"],
  ["03", "¿Qué significa para el cliente elegido?"],
  ["04", "¿Qué debería hacer? Nuestra recomendación."],
  ["05", "¿Qué riesgo, supuesto o cambio podría modificarla?"],
];

/* Fase 00: la pregunta del reto y los tres clientes. Elegir cliente cambia toda la página. */
export function Caso({ payload, cid, setCid }) {
  const clientes = payload?.caso?.clientes ?? [];
  return (
    <section className="section nu-caso" id="fase-00">
      <div className="shell section__inner">
        <span className="label">Fase 00 · El caso</span>
        <h2 className="display faq__title" style={{ marginTop: 16 }}>Una pregunta,<br />tres clientes.</h2>
        <p className="nu-pregunta">{payload?.caso?.pregunta ?? "¿Qué decisión de inversión recomendarían a este cliente hoy, y qué evidencia les permite defenderla?"}</p>

        <div className="cc-clientes" role="group" aria-label="Elige un cliente">
          {clientes.map((c) => (
            <button key={c.id} type="button" className="cc-cliente" aria-pressed={c.id === cid} onClick={() => setCid(c.id)}>
              <span className="cc-cliente__cuadros" aria-hidden="true"><i /><i /></span>
              <span className="label">{c.id.replace("CL_", "Cliente ")}</span>
              <h3>{c.nombre}</h3>
              <dl>
                <dt>Prioridad</dt><dd>{c.prioridad}</dd>
                <dt>Moneda base</dt><dd>{c.moneda}</dd>
                <dt>Horizonte</dt><dd>{c.horizonte_meses} meses</dd>
                <dt>Caída tolerada</dt><dd>{pct(c.tolerancia_caida, 0)}</dd>
                <dt>Liquidez</dt><dd>{c.liquidez}</dd>
                <dt>Restricción</dt><dd>{c.restriccion}</dd>
              </dl>
            </button>
          ))}
        </div>

        <p className="cc-aviso">
          <b>Solo generamos insights y recomendaciones.</b> Las decisiones de inversión las toman las personas. Los datos son sintéticos del reto Value Finders y nada de esto es asesoría financiera.
        </p>

        <div className="nu-preguntas">
          {PREGUNTAS.map(([n, q]) => <div className="nu-preg" key={n}><b>{n}</b>{q}</div>)}
        </div>
      </div>
    </section>
  );
}
