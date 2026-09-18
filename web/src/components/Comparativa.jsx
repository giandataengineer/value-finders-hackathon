import { Panel } from "./Blocks";
import "../styles/dashboard.css";

const SI = <span className="cc-si">Sí</span>;
const PA = <span className="cc-pa">Parcial</span>;
const NO = <span className="cc-no">No</span>;

const COLS = ["Hoja de cálculo con escenarios", "Markowitz open source", "Simuladores web de Monte Carlo", "Plataformas institucionales", "Value Finders"];
const FILAS = [
  ["Restricciones del cliente (tope por sector, alta volatilidad, países)", [NO, SI, NO, SI, SI]],
  ["Presupuesto de riesgo como probabilidad de caída máxima", [NO, PA, PA, SI, SI]],
  ["Moneda base del cliente (COP, PEN) con su tipo de cambio", [PA, NO, NO, SI, SI]],
  ["Valida y descarta datos con evidencia", [NO, NO, NO, PA, SI]],
  ["Trazabilidad del dato a la decisión", [NO, NO, NO, SI, SI]],
  ["Estrés con otro régimen de correlación", [NO, PA, PA, SI, SI]],
  ["Backtest de calibración, sensibilidad y 30 semillas", [NO, PA, NO, SI, SI]],
  ["Lecturas de IA independientes con guardarraíl de coherencia", [NO, NO, NO, PA, SI]],
  ["Supuestos explícitos y auditables", [PA, PA, PA, PA, SI]],
  ["Reproducible con semilla y huellas", [NO, PA, NO, PA, SI]],
];

export function Comparativa() {
  return (
    <section className="section" id="comparativa">
      <div className="shell section__inner cc-seccion">
        <span className="label">Soluciones similares</span>
        <h2 className="display faq__title">Por qué esta es la mejor opción<br />para este caso.</h2>
        <p className="panel__copy">Comparamos con cuatro formas habituales de resolver este problema. Las capacidades de las alternativas son generales y públicas, no una auditoría de un producto concreto.</p>

        <div className="cc-cmp-wrap">
          <table className="data-table cc-cmp">
            <thead><tr><th>Criterio</th>{COLS.map((c) => <th key={c} className={c === "Value Finders" ? "cc-ours" : ""}>{c}</th>)}</tr></thead>
            <tbody>
              {FILAS.map(([k, v]) => (
                <tr key={k}><td>{k}</td>{v.map((x, i) => <td key={i} className={i === 4 ? "cc-ours" : ""}>{x}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="cc-mini">Ejemplos: PyPortfolioOpt o Riskfolio-Lib (Markowitz open source); Portfolio Visualizer (simulador web); Bloomberg PORT, MSCI o Aladdin (plataformas institucionales).</p>

        <div className="cc-grid2">
          <div className="cc-caja cc-caja--aviso">
            <h4>Dónde otras herramientas nos superan</h4>
            <ul className="cc-lista">
              <li>Las plataformas institucionales cubren muchos más instrumentos, renta fija y derivados; nosotros solo 8 acciones y caja.</li>
              <li>Trabajan con datos de mercado licenciados y en tiempo real; aquí el dataset es sintético.</li>
              <li>Traen modelos de factores y equipos de soporte que no replicamos.</li>
              <li>No modelamos costos de transacción, impuestos ni tasas en COP o PEN, porque los datos no las traen.</li>
            </ul>
          </div>
          <div className="cc-caja cc-caja--azul">
            <h4>Por qué aun así es la mejor opción aquí</h4>
            <ul className="cc-lista">
              <li><b>Problem framing</b>: cada cliente tiene su tolerancia y sus restricciones dentro del motor, no un promedio.</li>
              <li><b>Criterio técnico</b>: elegimos el largo del bloque con la razón de varianzas y probamos el método con un backtest de calibración.</li>
              <li><b>Comunicación</b>: una vista responde las 5 preguntas y dice qué cambiaría la respuesta.</li>
              <li><b>Pensamiento crítico</b>: descartamos datos que se contradicen y el guardarraíl retira frases de la IA que las cifras desmienten.</li>
              <li><b>Colaboración</b>: ETL, simulación y web comparten un contrato de datos con 24 pruebas; en el medallón, bronce = silver + cuarentena.</li>
            </ul>
          </div>
        </div>
        <p className="cc-aviso">Generamos insights y recomendaciones. Decide una persona.</p>
      </div>
    </section>
  );
}
