import { useEffect, useRef, useState } from "react";
import { Panel } from "./Blocks";
import { IconAlert } from "./Icons";
import "../styles/asistente.css";

const SALUDO = "Hola, soy el asistente de Value Finders. Puedo explicar las cifras de tu simulación, hablarte de un sector o resolver dudas sobre tu perfil. Nada de esto es asesoría financiera.";

const SUGERENCIAS = ["¿En qué sector me conviene invertir?", "¿Por qué mi cartera tiene ese riesgo?", "¿Qué pasa si pongo todos mis ahorros aquí?"];

function nombreModelo(m) {
  return (m || "").replace(/:free$/, "");
}

export function Asistente({ payload, cid, setCid }) {
  const clientes = payload?.caso?.clientes ?? [];
  const cliente = clientes.find((c) => c.id === cid) ?? clientes[0];
  const [mensajes, setMensajes] = useState([{ role: "assistant", content: SALUDO }]);
  const [texto, setTexto] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);
  const simulacion = useRef(null);
  const listaRef = useRef(null);

  useEffect(() => {
    const oir = (e) => { simulacion.current = e.detail; };
    window.addEventListener("vf:simulacion", oir);
    return () => window.removeEventListener("vf:simulacion", oir);
  }, []);

  useEffect(() => {
    listaRef.current?.scrollTo({ top: listaRef.current.scrollHeight, behavior: "smooth" });
  }, [mensajes, cargando]);

  async function enviar(contenido) {
    const limpio = contenido.trim();
    if (!limpio || cargando) return;
    setError(null);
    setTexto("");
    const historial = [...mensajes, { role: "user", content: limpio }];
    setMensajes(historial);
    setCargando(true);
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mensajes: historial.slice(-10).map(({ role, content }) => ({ role, content })),
          cliente: cid ?? null,
          simulacion: simulacion.current,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.error || `HTTP ${r.status}`);
      setMensajes((m) => [...m, { role: "assistant", content: d.respuesta, modelo: d.modelo, proveedor: d.proveedor, determinista: d.determinista }]);
    } catch (err) {
      setError("No se pudo obtener respuesta. Intenta de nuevo en un momento.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="asistente" id="asistente">
      <Panel eyebrow="Asistente · Value Finders" title="Pregúntale a los datos">
        <p className="panel__copy">
          Responde con las cifras de tu simulación y, si preguntas por un sector, investiga en los datos del proyecto y en una fuente de mercado externa antes de contestar.
        </p>

        {clientes.length > 0 && (
          <div className="role-tabs" role="tablist">
            {clientes.map((c) => (
              <button key={c.id} role="tab" aria-selected={c.id === cliente?.id} className={`role-tab ${c.id === cliente?.id ? "is-on" : ""}`} onClick={() => setCid?.(c.id)}>
                {c.id.replace("_", " ")} · {c.nombre}
              </button>
            ))}
          </div>
        )}

        <div className="asis__ventana" ref={listaRef}>
          {mensajes.map((m, i) => (
            <div key={i} className={`asis__msg asis__msg--${m.role}`}>
              <p>{m.content}</p>
              {m.role === "assistant" && (m.modelo || m.determinista) && (
                <span className={`asis__firma ${m.determinista ? "asis__firma--reglas" : ""}`}>
                  {m.determinista ? <><IconAlert style={{ width: 12, height: 12 }} />solo reglas, sin modelo de IA disponible</> : `${nombreModelo(m.modelo)} · ${m.proveedor}`}
                </span>
              )}
            </div>
          ))}
          {cargando && <div className="asis__msg asis__msg--assistant asis__msg--cargando"><span /><span /><span /></div>}
        </div>

        {error && <p className="asis__error"><IconAlert style={{ width: 14, height: 14 }} />{error}</p>}

        {mensajes.length < 3 && (
          <div className="asis__sugerencias">
            {SUGERENCIAS.map((s) => <button key={s} type="button" onClick={() => enviar(s)} disabled={cargando}>{s}</button>)}
          </div>
        )}

        <form className="asis__form" onSubmit={(e) => { e.preventDefault(); enviar(texto); }}>
          <input type="text" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Escribe tu pregunta" disabled={cargando} maxLength={1500} />
          <button type="submit" disabled={cargando || !texto.trim()}>Enviar</button>
        </form>
        <p className="asis__nota">Genera insights sobre un caso sintético; no es asesoría financiera. Las decisiones las toman las personas.</p>
      </Panel>
    </div>
  );
}
