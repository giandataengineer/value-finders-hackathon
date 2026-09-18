import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import BlurText from "../reactbits/BlurText";
import LogoLoop from "../reactbits/LogoLoop";
import CountUp from "../reactbits/CountUp";
import Magnet from "../reactbits/Magnet";
import Dock from "../reactbits/Dock";
import Strands from "../reactbits/Strands";
import SpecularButton from "../reactbits/SpecularButton";
import StarBorder from "../reactbits/StarBorder";
import { Console } from "./Console";
import { IconArrowDown, IconBriefing, IconDecide, IconLoad, IconModel, IconSimulate } from "./Icons";

const STATES = [
  { key: "briefing", verb: "Presenta", tailKey: "caso", Icon: IconBriefing, coords: ["4.7110° N", "74.0721° O"] },
  { key: "ingesta", verb: "Valida", tailKey: "rows", Icon: IconLoad, coords: ["4.7110° N", "74.0721° O"] },
  { key: "uplift", verb: "Detecta", tailKey: "senal", Icon: IconModel, coords: ["12.0464° S", "77.0428° O"] },
  { key: "montecarlo", verb: "Simula", tailKey: "sims", Icon: IconSimulate, coords: ["33.4489° S", "70.6693° O"] },
  { key: "reporte", verb: "Recomienda", tailKey: "clientes", Icon: IconDecide, coords: ["19.4326° N", "99.1332° O"] },
];

const STACK = ["Python 3.14", "DuckDB", "SQL medallón", "Bronze · Silver · Gold", "pandas", "NumPy", "SciPy", "Monte Carlo", "Bootstrap por bloques",
  "Cuarentena de datos", "Linaje por fila", "EVPI", "Guardarraíl de coherencia", "Mistral", "Gemini", "Groq", "OpenRouter", "NVIDIA NIM", "Databricks",
  "React 19", "Vite 6", "Recharts", "Motion", "OGL / WebGL"];

const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

export function Hero({ meta, cliente, metricas, onPhaseChange }) {
  const [i, setI] = useState(0);
  const [cycle, setCycle] = useState(0);
  useEffect(() => { const id = setInterval(() => setI((n) => (n + 1) % STATES.length), 3600); return () => clearInterval(id); }, [cycle]);
  const pick = (idx) => { setI(idx); setCycle((c) => c + 1); };
  useEffect(() => { onPhaseChange(STATES[i].key); }, [i, onPhaseChange]);

  const state = STATES[i];
  const Icon = state.Icon;
  const tail = { caso: "tres clientes, una pregunta", rows: "538.836 filas crudas", senal: "correlación 0,16 → 0,80", sims: "10.000 futuros por cliente", clientes: "para que decida una persona" }[state.tailKey];

  return (
    <section className="hero" id="top">
      <div className="hero__strands" aria-hidden="true">
        <Strands colors={["#d3222e", "#2b62d9", "#141414", "#158a5c"]} count={4} speed={0.22} amplitude={0.75} waviness={1.3} thickness={0.45} glow={1.6}
          intensity={0.28} saturation={1.1} opacity={0.5} scale={1.9} />
      </div>

      <div className="shell hero__inner">
        <div className="hero__coords">
          <AnimatePresence mode="wait"><motion.span key={state.coords[0]} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }}>{state.coords[0]}</motion.span></AnimatePresence>
          <AnimatePresence mode="wait"><motion.span key={state.coords[1]} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }}>{state.coords[1]}</motion.span></AnimatePresence>
        </div>

        <h1 className="display hero__title"><BlurText text="Insights con evidencia." animateBy="words" delay={120} stepDuration={0.4} /></h1>

        <div className="hero__rotator">
          <AnimatePresence mode="wait">
            <motion.span key={state.key} className="hero__rotator-icon" initial={{ opacity: 0, scale: 0.6, rotate: -35 }} animate={{ opacity: 1, scale: 1, rotate: 0 }}
              exit={{ opacity: 0, scale: 0.6, rotate: 35 }} transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}><Icon /></motion.span>
          </AnimatePresence>
          <AnimatePresence mode="wait">
            <motion.span key={`${state.key}-w`} className="hero__rotator-word" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -18 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}>{state.verb}</motion.span>
          </AnimatePresence>
          <AnimatePresence mode="wait">
            <motion.span key={`${state.key}-t`} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -18 }}
              transition={{ duration: 0.45, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}>{tail}</motion.span>
          </AnimatePresence>
        </div>

        <div className="hero__cta">
          <SpecularButton size="lg" radius={999} tint="#141414" tintOpacity={1} baseColor="#141414" textColor="#ffffff" lineColor="#ffffff" intensity={1.2} shineSize={14}
            onClick={() => scrollTo("fase-00")}>Recorrer las 5 fases</SpecularButton>
          <StarBorder as="button" color="#d3222e" speed="5s" onClick={() => scrollTo("fase-04")}>Ir al Decision Dashboard</StarBorder>
        </div>

        <div className="phase-dock">
          <Dock items={STATES.map((s, idx) => ({ icon: <s.Icon />, label: s.verb, className: `ph-${s.key}${idx === i ? " is-on" : ""}`, onClick: () => pick(idx) }))}
            panelHeight={76} baseItemSize={52} magnification={68} dockHeight={76} distance={150} />
        </div>

        <div className="hero__body">
          <div>
            <p className="hero__lead">
              Convertimos los datos crudos de mercado en una recomendación que se puede defender: qué está pasando, qué señales lo explican, qué significa para cada
              cliente y qué haría cambiar la respuesta. Generamos insights; las decisiones las toman las personas.
            </p>
            <Magnet padding={70} magnetStrength={5}>
              <button className="hero__explore" type="button" onClick={() => scrollTo("fase-00")}><span><IconArrowDown /></span>Explorar</button>
            </Magnet>
            {meta && (
              <p className="label" style={{ marginTop: 34, display: "block" }}>
                <CountUp to={538836} separator="." duration={2.2} /> registros de mercado · {meta.activos} activos · {meta.dias_analizados} días alineados con el macro
              </p>
            )}
          </div>
          <Console cliente={cliente} metricas={metricas} phase={state.key} />
          <div className="hero__loop">
            <LogoLoop logos={STACK.map((name) => ({ node: <span className="label" style={{ letterSpacing: "0.08em" }}>{name}</span>, title: name }))}
              speed={38} gap={44} logoHeight={18} fadeOut fadeOutColor="#ededed" scaleOnHover ariaLabel="Stack técnico del proyecto" />
          </div>
        </div>
      </div>
    </section>
  );
}
