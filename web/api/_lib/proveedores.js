// Cadena de modelos de IA gratuitos, con respaldo. Portada de scripts/agente_multirol.py (Nordika).
// Todos hablan el protocolo de OpenAI: cambian la clave, la base_url y el modelo. Las claves viven solo en el servidor.
const P = {
  mistral:    { env: "MISTRAL_API_KEY",    url: "https://api.mistral.ai/v1" },
  gemini:     { env: "GEMINI_API_KEY",     url: "https://generativelanguage.googleapis.com/v1beta/openai" },
  groq:       { env: "GROQ_API_KEY",       url: "https://api.groq.com/openai/v1" },
  openrouter: { env: "OPENROUTER_API_KEY", url: "https://openrouter.ai/api/v1" },
  nvidia:     { env: "NVIDIA_API_KEY",     url: "https://integrate.api.nvidia.com/v1" },
  cerebras:   { env: "CEREBRAS_API_KEY",   url: "https://api.cerebras.ai/v1" },
  zai:        { env: "ZAI_API_KEY",        url: "https://api.z.ai/api/paas/v4" },
};

// De más capaz a más ligero dentro de cada proveedor; solo variantes gratuitas en OpenRouter.
const CATALOGO = {
  mistral: ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest", "ministral-14b-latest"],
  gemini: ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"],
  groq: ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "openai/gpt-oss-20b"],
  openrouter: ["nvidia/nemotron-3-super-120b-a12b:free", "z-ai/glm-5.2:free", "google/gemma-4-31b-it:free", "openai/gpt-oss-20b:free"],
  nvidia: ["nvidia/nemotron-3-super-120b-a12b", "meta/llama-3.1-70b-instruct", "deepseek-ai/deepseek-v4-flash-0731"],
  cerebras: ["gpt-oss-120b", "gemma-4-31b"],
  zai: ["glm-4.5-flash", "glm-4.7-flash"],
};

// Para el chat se prioriza a quien da más tokens gratis (Mistral y Gemini) y luego a quien responde más rápido.
export const ORDEN_CHAT = ["mistral", "gemini", "groq", "openrouter", "nvidia", "cerebras", "zai"];
// Para clasificar, tres familias distintas: si dos votos salieran del mismo modelo no serían dos opiniones.
export const ORDEN_VOTOS = ["gemini", "mistral", "groq", "openrouter", "nvidia", "cerebras", "zai"];

const enfriando = new Map();          // "prov/modelo" -> instante hasta el que se aparta tras un 429
const ESPERA_429 = 90_000;

const disponible = (prov) => Boolean(process.env[P[prov].env]);
export const proveedoresActivos = () => Object.keys(P).filter(disponible);
export const CLAVES = Object.values(P).map((x) => x.env);   // nombres de variables permitidas al cargar .env en desarrollo

export function candidatos(orden, excluir = new Set()) {
  const ahora = Date.now();
  const lista = [];
  for (const prov of orden) {
    if (!disponible(prov)) continue;
    for (const modelo of CATALOGO[prov]) {
      const clave = `${prov}/${modelo}`;
      if ((enfriando.get(clave) ?? 0) > ahora) continue;
      lista.push({ prov, modelo, repetido: excluir.has(modelo) });
    }
  }
  return [...lista.filter((c) => !c.repetido), ...lista.filter((c) => c.repetido)];
}

function sinVallas(t) {
  if (t.includes("<think>") && !t.includes("</think>")) throw new Error("respuesta truncada");
  let s = t.replace(/<think>[\s\S]*?<\/think>/g, "").trim();
  if (s.includes("```")) { const b = s.split("```"); if (b.length > 1) { s = b[1].replace(/^json\s*/i, ""); } }
  return s.trim();
}

async function una({ prov, modelo }, mensajes, { json, temperatura, maxTokens, timeoutMs }) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const cuerpo = { model: modelo, messages: mensajes, temperature: temperatura, max_tokens: maxTokens };
    if (json) cuerpo.response_format = { type: "json_object" };
    let r = await fetch(`${P[prov].url}/chat/completions`, {
      method: "POST", signal: ctl.signal,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${process.env[P[prov].env]}` },
      body: JSON.stringify(cuerpo),
    });
    if (json && r.status === 400) {   // no todos admiten JSON forzado
      delete cuerpo.response_format;
      r = await fetch(`${P[prov].url}/chat/completions`, { method: "POST", signal: ctl.signal, headers: { "Content-Type": "application/json", Authorization: `Bearer ${process.env[P[prov].env]}` }, body: JSON.stringify(cuerpo) });
    }
    if (r.status === 429) { enfriando.set(`${prov}/${modelo}`, Date.now() + ESPERA_429); throw new Error("429"); }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    const texto = d.choices?.[0]?.message?.content ?? "";
    if (!texto.trim()) throw new Error("vacío");
    return json ? JSON.parse(sinVallas(texto)) : sinVallas(texto);
  } finally { clearTimeout(t); }
}

/** Recorre la cadena hasta que un modelo responda. Devuelve { salida, proveedor, modelo, intentos } o lanza si ninguno pudo. */
export async function llamar(mensajes, { orden = ORDEN_CHAT, json = false, temperatura = 0.4, maxTokens = 1400, timeoutMs = 25_000, excluir = new Set(), maxIntentos = 8 } = {}) {
  const intentos = [];
  for (const c of candidatos(orden, excluir).slice(0, maxIntentos)) {
    try {
      const salida = await una(c, mensajes, { json, temperatura, maxTokens, timeoutMs });
      return { salida, proveedor: c.prov, modelo: c.modelo, intentos: intentos.length };
    } catch (e) { intentos.push(`${c.prov}/${c.modelo}: ${e.message}`); }
  }
  const err = new Error(intentos.length ? "ningún modelo respondió" : "sin claves de IA configuradas");
  err.intentos = intentos;
  throw err;
}
