// Guardarraíl de coherencia: ninguna frase del chat puede contradecir las cifras del cliente.
// Mismas reglas que src/robustez.py (portadas de analitica_avanzada.py de Nordika), más un par de promesas que un chat no debe hacer.
const norm = (t) => t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

export const REGLAS = [
  [/sin riesgo de perdida|riesgo de perdida (nulo|minimo)|capital (protegido|garantizado|asegurado)|inversion (segura|sin riesgo)/, (m) => m.prob_perdida > 0.05, "la probabilidad de pérdida supera el 5%"],
  [/cumple (siempre |en todos los escenarios )?(con )?la tolerancia|respeta (siempre )?la caida maxima|dentro de la tolerancia/, (m) => m.p_mdd_mezcla > m.alfa, "en la mezcla de estados la caída supera la tolerancia más veces que el presupuesto de riesgo"],
  [/resiste (una |la )?crisis|robust[ao] ante (una |la )?crisis|aguanta (el |un )?estres|inmune/, (m) => m.p_mdd_estres > m.alfa, "en estrés la caída supera la tolerancia más veces que el presupuesto"],
  [/protege(n)? (el )?capital|preserva(cion)? (del )?capital|proteccion del capital/, (m) => m.p5 < -0.10, "el percentil 5 pierde más de 10%"],
  [/supera (a |al )?(la )?(cartera )?(clasica|markowitz|tradicional)/, (m) => m.ret_anual <= m.ret_anual_mv, "en el caso base no rinde más que la cartera clásica"],
  [/garantiz|asegur(a|ado) (una )?(ganancia|rentabilidad|retorno)|ganancia segura|rentabilidad asegurada/, () => true, "ninguna ganancia está garantizada"],
  [/(deberias|debes|te recomiendo) (invertir|poner|meter) todo|invierte todo|todos tus ahorros (aqui|en esto) es (buena|una buena)/, () => true, "no recomendamos concentrar todos los ahorros"],
];

// Una negación justo antes de la expresión ("no garantizamos", "no es capital protegido") la vuelve una advertencia, no una promesa.
const NEGACION = /\b(no|ni|nunca|tampoco|ningun[ao]?|jamas)\b[^.!?]{0,30}$/;

/** Devuelve { texto, retiradas:[{frase, motivo}] } sin las frases que las cifras contradicen. Sin métricas, cualquier afirmación de las reglas se retira. */
export function revisar(texto, metricas) {
  const partes = String(texto ?? "").split(/(?<=[.!?])\s+|\n+/).map((s) => s.trim()).filter(Boolean);
  const retiradas = [];
  const ok = partes.filter((f) => {
    const plano = norm(f);
    for (const [re, falla, motivo] of REGLAS) {
      const m = re.exec(plano);
      if (!m) continue;
      if (NEGACION.test(plano.slice(0, m.index))) continue;
      if (!metricas || falla(metricas)) { retiradas.push({ frase: f, motivo }); return false; }
    }
    return true;
  });
  return { texto: ok.join(" "), retiradas };
}
