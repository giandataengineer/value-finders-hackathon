import { useCallback, useEffect, useState } from "react";
import { fases as leerFases } from "./lib/fases";
import { FINAL } from "./lib/vf";
import { TopBar } from "./components/TopBar";
import { Hero } from "./components/Hero";
import { Feature } from "./components/Feature";
import { Accordion } from "./components/Accordion";
import { Footer } from "./components/Footer";
import { SqlSection } from "./components/SqlSection";
import { Caso } from "./components/Caso";
import { Datos } from "./components/Datos";
import { Senal } from "./components/Senal";
import { Giros } from "./components/Giros";
import { Valor } from "./components/Valor";
import { Dashboard } from "./components/Dashboard";
import { MiInversion } from "./components/MiInversion";
import { Asistente } from "./components/Asistente";
import { Comparativa } from "./components/Comparativa";
import "./styles/global.css";
import "./styles/vf.css";
import "./styles/nucleo.css";

const FAQ = [
  { q: "¿Por qué simular y no predecir?", a: "Una predicción sola no dice cuánto puedes perder. Con diez mil futuros por cliente sale la distribución entera: el suelo, la mediana, el techo y cada cuántas veces la caída supera lo que el cliente tolera. La decisión se firma una vez, no cien." },
  { q: "¿Qué es la mezcla de estados?", a: "Un mismo mercado puede comportarse de tres maneras: neutral (ningún activo tiene ventaja), con lo realizado el último año y en estrés, con la correlación del historial 2020 a jul-2025. La mezcla pondera los tres (55, 30 y 15 %) como un vector de estados: al simular, cada futuro colapsa a uno de ellos. Es un supuesto y la página muestra cuánto cambia el riesgo al mover la probabilidad de estrés." },
  { q: "¿Por qué hay dos recomendaciones?", a: "La base cumple el presupuesto de riesgo en los estados neutral y realizado. La defensiva lo cumple sobre la mezcla que incluye el estrés. La diferencia de retorno entre las dos es el costo de protegerse de una crisis: la persona decide cuánto está dispuesta a pagar." },
  { q: "¿Esto es asesoría financiera?", a: "No. Es un caso sintético del reto Value Finders. Generamos insights y recomendaciones para apoyar una conversación; ninguna cifra es una promesa de rentabilidad y las decisiones de inversión las toman las personas, idealmente con un asesor." },
];

export default function App() {
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState(null);
  const [cid, setCid] = useState("CL_01");
  const [phase, setPhase] = useState("briefing");

  useEffect(() => {
    fetch("payload.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setPayload)
      .catch((e) => setError(e.message));
  }, []);

  const handlePhase = useCallback((p) => setPhase(p), []);
  const listaFases = leerFases(payload);
  const f = (k) => listaFases.find((x) => x.key === k);
  const cliente = payload?.caso?.clientes?.find((c) => c.id === cid);
  const metricas = payload?.clientes?.[cid]?.metricas?.base_neutral?.[FINAL];
  const meta = payload?.meta;

  return (
    <div className="page" data-phase={phase}>
      <TopBar error={error} stats={meta ? `${meta.activos} activos · ${meta.dias_analizados} días · ${Number(meta.simulaciones).toLocaleString("es-CO")} futuros por cliente` : "Cargando resultados"} fases={listaFases} />

      <Hero meta={meta} cliente={cliente} metricas={metricas} onPhaseChange={handlePhase} />

      <Caso payload={payload} cid={cid} setCid={setCid} />

      <Feature id="fase-01" index={1} eyebrow={f("ingesta")?.eyebrow} faseTitulo={f("ingesta")?.title} solid="Los datos crudos" ghost="pasan por un medallón." wide
        echo="Antes de usar un dato, hay que saber si se puede confiar en él."
        copy="Bronce guarda cada archivo tal cual, con su huella. Silver tipa, corrige y manda a cuarentena lo que no pasa. Gold entrega tablas listas. Los dos datasets, el data pack y el giro de la trama, siguen el mismo camino y cada descarte tiene su motivo."
        media={<Datos payload={payload} />} />

      <SqlSection payload={payload} />

      <Feature id="fase-02" index={2} eyebrow={f("uplift")?.eyebrow} faseTitulo={f("uplift")?.title} solid="La señal" ghost="es el cambio de régimen." wide
        echo="Lo que cambia entre un año y otro no es el precio: es cuánto se mueven juntos."
        copy="Los últimos 12 meses y el historial 2020 a jul-2025 cuentan riesgos distintos. Esa diferencia, más un episodio de estrés y cinco eventos, es lo que define las carteras. Luego llegan tres giros de la trama."
        media={<Senal payload={payload} />} />
      <Giros payload={payload} cid={cid} />

      <Feature id="fase-03" index={3} eyebrow={f("montecarlo")?.eyebrow} faseTitulo={f("montecarlo")?.title} solid="Diez mil futuros" ghost="dentro de las reglas de cada cliente." wide
        echo="Cada cliente tiene su moneda, su horizonte y cuánta caída tolera."
        copy="Se remuestrean días completos del mercado para conservar la correlación y las colas, se convierte a la moneda del cliente y se buscan carteras que respeten sus restricciones. Todo se evalúa con simulaciones nuevas, no con las que sirvieron para buscar."
        media={<Valor payload={payload} cid={cid} setCid={setCid} />} />

      <Feature id="fase-04" index={4} eyebrow={f("reporte")?.eyebrow} faseTitulo={f("reporte")?.title} solid="Una vista" ghost="para decidir." wide
        echo="Qué pasa, por qué, qué significa, qué hacer y qué lo cambiaría."
        copy="El Decision Dashboard responde las cinco preguntas del reto para el cliente elegido, con su robustez, tres lecturas de modelos de IA independientes y el linaje de cada cifra."
        media={<Dashboard payload={payload} cid={cid} setCid={setCid} />} />

      <MiInversion payload={payload} cid={cid} setCid={setCid} />
      <Asistente payload={payload} cid={cid} setCid={setCid} />
      <Comparativa />

      <section className="section" id="faq">
        <div className="shell section__inner faq__grid">
          <div>
            <span className="label" style={{ display: "block", marginBottom: 24 }}>FAQ</span>
            <h2 className="display faq__title">Cómo leer<br />estos números.</h2>
          </div>
          <Accordion items={FAQ} />
        </div>
      </section>

      <Footer fases={listaFases} meta={meta ? `Generado ${meta.generado?.slice(0, 10)} · ${meta.empresa}` : "Value Finders"} />
    </div>
  );
}
