import { Panel } from "./Blocks";
import { FINAL, nombreActivo, num, pct, pesosVisibles } from "../lib/vf";
import "../styles/dashboard.css";

/* De cada archivo crudo a la recomendación, con huellas y conteos que se pueden verificar. */
export function Trazabilidad({ payload, cid }) {
  const t = payload?.trazabilidad;
  const c = payload?.clientes?.[cid];
  if (!t || !c) return null;
  const lin = t.linaje ?? payload?.datos?.linaje ?? [];
  const suma = (k) => lin.reduce((s, x) => s + (x[k] ?? 0), 0);
  const corto = (h) => (h ? h.slice(0, 10) : "");
  const gold = Object.keys(payload?.datos?.capas ?? {}).filter((k) => k.startsWith("gold.")).length;
  const conserva = lin.length > 0 && lin.every((x) => x.filas_bronze === x.filas_silver + x.filas_cuarentena);
  const p = t.parametros ?? {};
  const pesos = pesosVisibles(c.carteras[FINAL]).map(([k, v]) => `${k === "CAJA" ? "Caja" : nombreActivo(payload, k)} ${pct(v, 0)}`).join(", ");
  const salida = t.salidas?.["mc_resultados.json"];

  return (
    <Panel eyebrow="Trazabilidad" title="Del archivo crudo a la recomendación, paso a paso">
      <ol className="cc-cadena">
        <li><div><b>Crudo</b>: {lin.length} archivos con huella SHA-256. {lin.slice(0, 3).map((x) => <span key={x.archivo}><code>{x.archivo}</code> <code>{corto(x.sha256)}</code>; </span>)}
          <span className="cc-nota">Si un archivo cambia, la huella cambia y el medallón se reconstruye.</span></div></li>
        <li><div><b>Bronce</b>: {num(suma("filas_bronze"))} filas tal cual, todo texto, con archivo de origen, lote y número de fila.</div></li>
        <li><div><b>Silver</b>: {num(suma("filas_silver"))} filas limpias y {num(suma("filas_cuarentena"))} en cuarentena con su motivo. {conserva ? "En todas las tablas, bronce = silver + cuarentena: no se pierde nada en silencio." : ""}
          <span className="cc-nota">{(t.limpieza ?? []).length} reglas de limpieza registradas con sus conteos.</span></div></li>
        <li><div><b>Gold</b>: {gold} tablas listas para el motor, con el contrato de datos que también lee Databricks.</div></li>
        <li><div><b>Parámetros</b>: semilla {p.SEED ?? 42}, {num(p.SIMS_FINAL ?? 10000)} futuros por cartera, prima de riesgo neutral {pct(p.ERP ?? 0.04, 0)}, {(t.asunciones ?? []).length} supuestos escritos en el manifiesto.</div></li>
        <li><div><b>Simulación</b>: bootstrap de bloques circulares, retornos y tipo de cambio remuestreados juntos, conversión a {payload.caso.clientes.find((x) => x.id === cid)?.moneda}.</div></li>
        <li><div><b>Recomendación</b> para {cid}: {pesos}. {salida && <span>Resultados con huella <code>{corto(salida)}</code>.</span>} <span className="cc-nota">Generado {t.generado} con Python {t.entorno?.python}, numpy {t.entorno?.numpy}, pandas {t.entorno?.pandas}.</span></div></li>
      </ol>
    </Panel>
  );
}
