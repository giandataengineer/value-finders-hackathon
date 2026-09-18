// node --test tests/simulador.test.mjs
// Contrasta el motor JS con el de Python (payload.clientes[cid].superposicion_estados de la cartera recomendada defensiva).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { simular } from "../src/lib/simulador.js";

const leer = (n) => JSON.parse(readFileSync(new URL(`../public/${n}`, import.meta.url), "utf8"));
const FINAL = "recomendada defensiva (con estres)";
const motor = leer("motor.json");
const payload = leer("payload.json");

for (const cid of ["CL_01", "CL_02", "CL_03"]) {
  test(`${cid}: el motor JS coincide con Python`, (t) => {
    const py = payload.clientes?.[cid]?.superposicion_estados?.[FINAL];
    if (!py || !motor.clientes?.[cid]?.carteras?.[FINAL]) return t.skip("motor.json o payload.json todavía no son los de Value Finders");
    const r = simular(motor, { cid, cartera: FINAL, estado: "mezcla", sims: 20000 });
    const dRet = Math.abs(r.ret_anual_mediano - py.ret_anual_mediano) * 100;
    const dCaida = Math.abs(r.p_caida - py.p_mdd_sobre_tol) * 100;
    console.log(`${cid}: retorno anual JS ${(r.ret_anual_mediano * 100).toFixed(2)}% vs Python ${(py.ret_anual_mediano * 100).toFixed(2)}% | P(caída>tol) JS ${(r.p_caida * 100).toFixed(1)}% vs Python ${(py.p_mdd_sobre_tol * 100).toFixed(1)}%`);
    assert.ok(dRet < 1.5, `retorno difiere ${dRet.toFixed(2)} puntos`);
    assert.ok(dCaida < 3, `P(caída>tol) difiere ${dCaida.toFixed(2)} puntos`);
  });
}

test("solo caja no pierde y crece a la tasa libre de riesgo (USD)", (t) => {
  if (!motor.clientes?.CL_01?.carteras?.["solo caja"]) return t.skip("motor.json antiguo");
  const r = simular(motor, { cid: "CL_01", cartera: "solo caja", estado: "base_neutral", sims: 500 });
  assert.equal(r.prob_perdida, 0);
  assert.ok(Math.abs(r.ret_anual_mediano - motor.rf) < 0.002);
});
