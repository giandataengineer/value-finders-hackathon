import ParticleText from "../reactbits/ParticleText";
import { MarcaCredicorp } from "./MarcaCredicorp";

export function Footer({ meta, fases = [] }) {
  return (
    <footer className="site-footer">
      <div className="site-footer__fondo" aria-hidden="true">
        <span className="site-footer__glow" />
        <div className="site-footer__wordmark">
          <ParticleText text="VALUE FINDERS" particleSize={1.5} density={5} color="#332f2d" highlightColor="#a3151f" scatter={200} gatherDuration={1600}
            stagger={420} repelRadius={150} trigger="view" fontSize="clamp(3rem, 11vw, 10rem)" fontWeight={600} glow />
        </div>
      </div>

      <div className="shell site-footer__contenido">
        <div className="site-footer__links">
          <div>
            <h4>Recorrido</h4>
            <ul>{fases.map((f) => <li key={f.key}><a href={`#${f.id}`}>{f.eyebrow} · {f.title}</a></li>)}</ul>
          </div>
          <div>
            <h4>Método</h4>
            <ul>
              <li><a href="#giros">Giros de la trama</a></li>
              <li><a href="#faq">Preguntas frecuentes</a></li>
              <li>Medallón bronce, silver, gold</li>
              <li>Monte Carlo por bloques</li>
            </ul>
          </div>
          <div>
            <h4>Garantías</h4>
            <ul>
              <li>Ninguna fila se pierde en silencio</li>
              <li>Cada cifra tiene su linaje</li>
              <li>Guardarraíl de coherencia en texto e IA</li>
              <li>Semilla fija: reproducible</li>
            </ul>
          </div>
          <div>
            <h4>Stack</h4>
            <ul>
              <li>Python · DuckDB · SQL · NumPy · SciPy</li>
              <li>React 19 · Vite 6 · Recharts</li>
              <li>Modelos de IA gratuitos con respaldo</li>
              <li>Conector a Databricks</li>
            </ul>
          </div>
        </div>

        <div className="site-footer__meta">
          <span className="site-footer__firma">
            <MarcaCredicorp />
            <span style={{ marginLeft: 10 }}>Value Finders · datos sintéticos. Insights y recomendaciones: decide una persona.</span>
          </span>
          <span>{meta}</span>
        </div>
      </div>
    </footer>
  );
}
