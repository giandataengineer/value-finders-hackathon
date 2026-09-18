// POST /api/chat  { mensajes:[{role,content}], cliente: "CL_01"|null, simulacion? }  ->  { respuesta, modelo, proveedor, frases_retiradas }
// GET  /api/chat  ->  { proveedores:[...] }  (nombres de proveedores con clave; nunca las claves)
import { llamar, ORDEN_CHAT, proveedoresActivos } from "./_lib/proveedores.js";
import { revisar } from "./_lib/coherencia.js";
import { cargarContexto, metricasCliente, promptSistema, respuestaDeterminista } from "./_lib/contexto.js";
import { analizarSector } from "./_lib/mercado.js";

const CLIENTES = new Set(["CL_01", "CL_02", "CL_03"]);
const visitas = new Map();   // ponytail: límite por IP en memoria de la instancia; usar un almacén compartido si el tráfico crece
function limitado(ip) {
  const ahora = Date.now();
  const v = (visitas.get(ip) ?? []).filter((t) => ahora - t < 10 * 60_000);
  v.push(ahora);
  visitas.set(ip, v);
  if (visitas.size > 2000) visitas.clear();
  return v.length > 40;
}

export async function procesar(body, ip = "local") {
  if (limitado(ip)) return { status: 429, json: { error: "demasiadas consultas, intenta en unos minutos" } };
  const cid = CLIENTES.has(body?.cliente) ? body.cliente : null;
  const mensajes = (Array.isArray(body?.mensajes) ? body.mensajes : []).slice(-10)
    .map((m) => ({ role: m?.role === "assistant" ? "assistant" : "user", content: String(m?.content ?? "").slice(0, 1500) }))
    .filter((m) => m.content.trim());
  if (!mensajes.length || mensajes[mensajes.length - 1].role !== "user") return { status: 400, json: { error: "falta el mensaje del usuario" } };

  const ctx = cargarContexto();
  const ultima = mensajes[mensajes.length - 1].content;
  const mercado = await analizarSector(ultima).catch(() => null);
  let salida;
  try {
    const r = await llamar([{ role: "system", content: promptSistema(cid, ctx, body?.simulacion, mercado) }, ...mensajes],
      { orden: ORDEN_CHAT, temperatura: 0.4, maxTokens: 900, timeoutMs: 22_000 });
    salida = { texto: String(r.salida), modelo: r.modelo, proveedor: r.proveedor };
  } catch (e) {
    const motivo = e.intentos?.length ? "los modelos de IA gratuitos no respondieron" : "no hay claves de IA configuradas";
    return { status: 200, json: { respuesta: respuestaDeterminista(cid, ctx, ultima, body?.simulacion, motivo), modelo: "reglas", proveedor: "determinista", determinista: true, frases_retiradas: [] } };
  }

  const rev = revisar(salida.texto, metricasCliente(cid, ctx));
  const respuesta = rev.texto.trim() || respuestaDeterminista(cid, ctx, ultima, body?.simulacion, "las frases del modelo contradecían las cifras");
  return { status: 200, json: { respuesta, modelo: salida.modelo, proveedor: salida.proveedor, frases_retiradas: rev.retiradas } };
}

export default async function handler(req, res) {
  if (req.method === "GET") return res.status(200).json({ proveedores: proveedoresActivos() });
  if (req.method !== "POST") return res.status(405).json({ error: "método no permitido" });
  const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body ?? {};
  const ip = String(req.headers?.["x-forwarded-for"] ?? req.socket?.remoteAddress ?? "local").split(",")[0].trim();
  const { status, json } = await procesar(body, ip);
  res.status(status).json(json);
}
