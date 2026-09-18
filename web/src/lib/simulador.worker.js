import { simular } from "./simulador.js";

let motor = null;

self.onmessage = (e) => {
  if (e.data.motor) motor = e.data.motor;
  try {
    const r = simular(motor, e.data.opciones, (p) => self.postMessage({ tipo: "progreso", p }));
    self.postMessage({ tipo: "listo", r });
  } catch (err) {
    self.postMessage({ tipo: "error", mensaje: String(err) });
  }
};
