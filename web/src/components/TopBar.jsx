import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconArrowRight } from "./Icons";
import { MarcaCredicorp } from "./MarcaCredicorp";

export function TopBar({ stats, error, fases = [] }) {
  const [rotando, setRotando] = useState(0);
  const [activa, setActiva] = useState(null);
  const [arriba, setArriba] = useState(true);

  /* Arriba del todo la pastilla rota por las fases, a modo de índice; al hacer scroll indica en qué fase estás. */
  useEffect(() => {
    if (fases.length === 0) return undefined;
    let frame = 0;
    const medir = () => {
      frame = 0;
      const y = window.scrollY;
      setArriba(y < 80);
      const corte = y + window.innerHeight * 0.35;
      let actual = fases[0];
      for (const f of fases) {
        const el = document.getElementById(f.id);
        if (el && el.getBoundingClientRect().top + y <= corte) actual = f;
      }
      setActiva(actual);
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(medir); };
    medir();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [fases]);

  useEffect(() => {
    if (!arriba || fases.length === 0) return undefined;
    const id = setInterval(() => setRotando((n) => (n + 1) % fases.length), 3200);
    return () => clearInterval(id);
  }, [arriba, fases.length]);

  const fase = arriba ? fases[rotando % Math.max(fases.length, 1)] : activa;

  return (
    <header className="topbar">
      <a className="topbar__mark" href="#top" aria-label="Credicorp Capital, Value Finders">
        <MarcaCredicorp />
      </a>

      <div className="topbar__pill">
        <span className="status-dot" aria-hidden="true" />
        <span className="topbar__stats">{error ? `No se pudieron cargar los resultados (${error})` : stats}</span>
        {fase && (
          <AnimatePresence mode="wait">
            <motion.a
              key={fase.id + (arriba ? "-rota" : "-activa")}
              href={`#${fase.id}`}
              className={arriba ? "" : "is-activa"}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              {!arriba && <i className="topbar__aqui" aria-hidden="true" />}
              {fase.eyebrow} · {fase.title}
              {arriba && <IconArrowRight style={{ width: 12, height: 12, verticalAlign: "-1px", marginLeft: 6 }} />}
            </motion.a>
          </AnimatePresence>
        )}
      </div>

      <span className="topbar__right label">Value Finders</span>
    </header>
  );
}
