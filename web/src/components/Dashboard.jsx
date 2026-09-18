import { PestanasCliente } from "./Valor";
import { Robustez } from "./Robustez";
import { Consenso } from "./Consenso";
import { Trazabilidad } from "./Trazabilidad";
import { BASE, ETIQUETA, FINAL, nombreActivo, pct, pctS, pesosVisibles } from "../lib/vf";
import "../styles/dashboard.css";

const Resp = ({ n, titulo, children, destacar }) => (
  <article className={destacar ? "cc-resp cc-resp--reco" : "cc-resp"}>
    <span className="cc-n">{n}</span>
    {destacar && <span className="cc-badge-reco">LA RECOMENDACIÓN</span>}
    <h4>{titulo}</h4>
    {children}
  </article>
);

/* Decision Dashboard: una vista principal que responde las 5 preguntas del reto. Todo el texto sale de las cifras del cliente elegido. */
export function Dashboard({ payload, cid, setCid }) {
  const c = payload?.clientes?.[cid];
  const perfil = payload?.caso?.clientes?.find((x) => x.id === cid);
  if (!c || !perfil) return null;

  const s = payload.senal ?? {};
  const corr = Object.fromEntries((s.correlacion_por_fuente ?? []).map((x) => [x.fuente, x.correlacion_media]));
  const stress = (s.regimenes ?? []).find((r) => r.regimen === "Stress");
  const eventosFuertes = (s.eventos ?? []).filter((e) => Math.abs(e.z_3d) >= 1.5);
  const giros = (payload.giros?.insights ?? []).filter((g) => g.cliente === "todos" || g.cliente === cid);
  const fin = c.metricas.base_neutral[FINAL];
  const est = c.metricas.estres_historial_2020_2025[FINAL];
  const mez = c.superposicion_estados?.[FINAL];
  const mezBase = c.superposicion_estados?.[BASE];
  const costo = mez && mezBase ? mezBase.ret_anual_mediano - mez.ret_anual_mediano : null;
  const pesos = pesosVisibles(c.carteras[FINAL]);
  const caja = c.carteras[FINAL].CAJA ?? 0;
  const estres = c.sensibilidad_prob_estres ?? [];
  const cruza = estres.find((x) => x.p_mdd_sobre_tol > perfil.presupuesto_riesgo);
  const quiebres = (c.robustez?.sensibilidad_ruidos?.resultados ?? []).filter((r) => r.punto_de_quiebre != null);
  const valor = payload.datos?.valor ?? [];
  const usados = valor.filter((v) => /^Usar/.test(v.decision)).length;
  const descartados = valor.filter((v) => /Descartar|No aporta/.test(v.decision)).length;
  const supuestos = (payload.trazabilidad?.asunciones ?? []).slice(0, 3);
  const cumple = mez ? mez.p_mdd_sobre_tol <= perfil.presupuesto_riesgo : false;   // se recalcula con las simulaciones finales

  return (
    <div className="cc-seccion">
      <PestanasCliente payload={payload} cid={cid} setCid={setCid} />
      <p className="cc-aviso">Este panel entrega insights y recomendaciones basados en un dataset sintético. Las decisiones las toman las personas; no es asesoría financiera.</p>

      <div className="cc-dec">
        <Resp n="1" titulo="¿Qué está ocurriendo?">
          <p>El riesgo cambió de régimen: la correlación media entre los 8 activos es {corr.diario_12m?.toFixed(2).replace(".", ",")} en el último año y {corr.historial_intradia?.toFixed(2).replace(".", ",")} en el historial 2020-2025. Cuando todo se mueve junto, diversificar protege menos.</p>
          {stress && <p>El macro marcó un episodio de estrés de {stress.dias} días ({stress.desde} a {stress.hasta}).</p>}
          {giros.length > 0 && <ul className="cc-lista">{giros.slice(0, 2).map((g) => <li key={g.giro + g.cliente}><b>{g.titulo}</b>: llegó un giro de la trama que revisamos más abajo.</li>)}</ul>}
        </Resp>

        <Resp n="2" titulo="¿Qué datos o señales lo explican?">
          <ul className="cc-lista">
            <li>De {valor.length} fuentes evaluadas, {usados} entran a la simulación y {descartados} se descartan con evidencia.</li>
            <li>El archivo intradía posterior a agosto 2025 contradice al diario y al macro, así que solo sirve como escenario de estrés.</li>
            <li>{eventosFuertes.length} de {(s.eventos ?? []).length} reacciones a eventos superan 1,5 desviaciones típicas: son pocas para calibrar saltos y se usan como escenarios.</li>
            <li>Los fundamentales de 8 emisores no predicen el retorno de forma significativa: sirven como contexto.</li>
          </ul>
        </Resp>

        <Resp n="3" titulo="¿Qué significa para el cliente elegido?">
          <p>{perfil.nombre} invierte en {perfil.moneda} a {perfil.horizonte_meses} meses y tolera caer {pct(perfil.tolerancia_caida, 0)}. Con la cartera recomendada, el retorno anual mediano es {pctS(fin.ret_anual_mediano)}, el peor 5 % termina en {pctS(fin.p5)} y hay {pct(fin.prob_perdida, 0)} de probabilidad de terminar en pérdida.</p>
          <p>En un estrés como el de 2020-2025, la probabilidad de superar la tolerancia sube a {pct(est.p_mdd_sobre_tol, 0)}.</p>
        </Resp>

        <Resp n="4" titulo="¿Qué debería hacer?" destacar>
          <p>Sugerimos evaluar esta asignación: {pesos.map(([k, v]) => `${k === "CAJA" ? "caja" : nombreActivo(payload, k)} ${pct(v, 0)}`).join(", ")}.</p>
          <p>{caja >= 0.5 ? `Casi todo queda en caja (${pct(caja, 0)}): con esta tolerancia de caída el universo de 8 acciones deja poco espacio para riesgo. ` : ""}Mezcla de estados: {pct(mez?.p_mdd_sobre_tol, 0)} de probabilidad de superar la tolerancia frente a un presupuesto de {pct(perfil.presupuesto_riesgo, 0)}{cumple ? ", dentro del presupuesto" : ", por encima del presupuesto"}.</p>
          {costo != null && <p>La alternativa base ({pesosVisibles(c.carteras[BASE]).map(([k, v]) => `${k === "CAJA" ? "caja" : nombreActivo(payload, k)} ${pct(v, 0)}`).join(", ")}) {costo > 0.005 ? `rinde ${pctS(costo)} más de retorno anual mediano en la mezcla: ese es el costo de protegerse del estrés.` : "rinde prácticamente lo mismo en la mezcla: protegerse del estrés casi no cuesta retorno."} La decisión es de la persona.</p>}
        </Resp>

        <Resp n="5" titulo="¿Qué riesgo, supuesto o cambio podría modificar la recomendación?">
          <ul className="cc-lista">
            {cruza && <li>Si la probabilidad de un estado de crisis sube a {pct(cruza.prob_estres, 0)} o más, la cartera supera su presupuesto de riesgo.</li>}
            {quiebres.length > 0 ? quiebres.map((q) => <li key={q.ruido}>Deja de cumplir o cambia si {q.ruido} llega a {q.punto_de_quiebre}x del valor supuesto.</li>) : <li>Aguanta todas las variaciones probadas de volatilidad, prima de riesgo y tipo de cambio.</li>}
            {supuestos.map((a) => <li key={a}>Supuesto: {a}</li>)}
            {giros.filter((g) => g.cliente === cid).slice(0, 2).map((g) => <li key={g.giro}><b>{g.titulo}</b>: {g.texto}</li>)}
          </ul>
        </Resp>
      </div>

      <Robustez payload={payload} cid={cid} />
      <Consenso payload={payload} cid={cid} />
      <Trazabilidad payload={payload} cid={cid} />
    </div>
  );
}
