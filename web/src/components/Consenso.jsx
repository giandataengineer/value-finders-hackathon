import { Panel } from "./Blocks";
import { IconAlert, IconCheck, IconLayers } from "./Icons";
import { ETIQUETA } from "../lib/vf";
import "../styles/dashboard.css";

const ROL = { gestor: "Gestor", riesgo: "Riesgo", asesor: "Asesor" };

/* El desacuerdo entre roles es un hallazgo: la elección depende de qué prioriza quien decide, no solo de los números. */
export function Consenso({ payload, cid }) {
  const m = payload?.clientes?.[cid]?.lecturas_multirol;
  if (!m?.agregacion) return null;
  const { agregacion, lecturas = [] } = m;
  const conLlm = lecturas.filter((l) => l.fuente === "llm");
  const sin = lecturas.filter((l) => l.fuente !== "llm");
  const estado = agregacion.modo === "determinista" ? "neutro" : agregacion.consenso ? "acuerdo" : "desacuerdo";
  const Icono = estado === "desacuerdo" ? IconAlert : estado === "acuerdo" ? IconCheck : IconLayers;
  const retiradas = lecturas.reduce((s, l) => s + (l.coherencia?.frases_retiradas ?? 0), 0);

  return (
    <Panel eyebrow="Tres lecturas · modelos de IA independientes" title={estado === "desacuerdo" ? "Los roles no coinciden: ese es el hallazgo" : estado === "acuerdo" ? "Los tres roles coinciden" : "Lecturas por reglas"} className={`consenso consenso--${estado}`}>
      <p className="panel__copy">{agregacion.veredicto}</p>
      <div className="consenso__grid">
        {lecturas.map((l) => (
          <article className="voto" key={l.rol}>
            <div className="voto__head">
              <span className="label">{ROL[l.rol] ?? l.rol}</span>
              <span className="voto__modelo">{l.fuente === "llm" ? `${(l.modelo || "").replace(/:free$/, "")} · ${l.proveedor}` : "reglas sobre las cifras"}</span>
            </div>
            <p className="voto__eleccion"><Icono style={{ width: 15, height: 15 }} />{ETIQUETA[l.decision_elegida] ?? l.decision_elegida}</p>
            {l.headline && <p className="voto__headline">{l.headline}</p>}
            {l.summary && <p className="cc-voto-texto">{l.summary}</p>}
            {l.coherencia?.frases_retiradas > 0 && (
              <p className="voto__aviso"><IconAlert style={{ width: 13, height: 13 }} />{l.coherencia.frases_retiradas} frase{l.coherencia.frases_retiradas === 1 ? "" : "s"} retirada{l.coherencia.frases_retiradas === 1 ? "" : "s"} por contradecir las cifras</p>
            )}
          </article>
        ))}
      </div>
      {sin.length > 0 && conLlm.length > 0 && (
        <div className="consenso__fallos"><span className="label">Roles sin modelo disponible</span><ul>{sin.map((l) => <li key={l.rol}><b>{ROL[l.rol] ?? l.rol}</b>: {l.motivo}</li>)}</ul></div>
      )}
      <span className="card__foot label">
        {m.desde_cache && "Lecturas reutilizadas de la última ejecución · "}
        {`Guardarraíl de coherencia: ${retiradas} frase${retiradas === 1 ? "" : "s"} retirada${retiradas === 1 ? "" : "s"} en total · `}
        {m.proveedores_configurados?.length ? `Proveedores: ${m.proveedores_configurados.join(", ")}` : "Sin claves de IA: solo reglas"}
      </span>
    </Panel>
  );
}
