// Acceptance tests for the amount scaling in index.html.
// Run from the repo root:  node test_scaling.js
// It loads the code between /* SCALING:START */ and /* SCALING:END */ in index.html.
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "index.html", "utf8");
const m = /\/\* SCALING:START \*\/([\s\S]*?)\/\* SCALING:END \*\//.exec(html);
if (!m) { console.error("SCALING:START / SCALING:END markers not found in index.html"); process.exit(1); }
const scaleQty = new Function(m[1] + "\nreturn scaleQty;")();

const CASES = [
  // [input, multiplier, expected]
  // Bug 1: "N × size" scales the count only
  ["4 × 4–6 oz", 3, "12 × 4–6 oz"],
  ["4 × 115–170 g", 0.5, "2 × 115–170 g"],
  ["6 (700–900 g)", 0.5, "3 (350–450 g)"],            // a total weight in brackets still scales
  ["6 portions (~120 g each)", 3, "18 portions (~120 g each)"],
  ["15 oz can", 1.5, "1½ × 15 oz can"],
  // Bug 2: small amounts, units and plurals
  ["⅛ tsp", 0.5, "1 pinch"],
  ["¼ tsp", 1.5, "⅜ tsp"],
  ["1 tbsp", 0.5, "1½ tsp"],
  ["¼ cup", 0.5, "2 tbsp"],
  ["⅓ cup", 0.5, "2 tbsp + 2 tsp"],
  ["¼ cup", 1.5, "6 tbsp"],
  ["2 tsp", 3, "2 tbsp"],
  ["4 tbsp", 3, "¾ cup"],
  ["6 tbsp", 3, "1 cup + 2 tbsp"],
  ["½ US cup", 3, "1½ US cups"],
  ["¾ US cup + 1 tbsp", 2, "1½ US cups + 2 tbsp"],
  ["about 1½ tsp", 1.5, "about 2¼ tsp"],
  ["3–4 tbsp", 0.5, "1½–2 tbsp"],                     // ranges keep their unit
  ["2 grinds", 0.5, "1 grind"],
  ["1 taza (cup)", 2, "2 tazas (cups)"],
  ["2 cucchiai (tbsp)", 0.5, "1 cucchiaio (tbsp)"],
  ["1 cucharada (tbsp)", 3, "3 cucharadas (tbsp)"],
  ["1 egg", 3, "3 eggs"],
  ["1 packet", 2, "2 packets"],
  ["1 cucchiaino raso (level tsp)", 2, "2 cucchiaini raso (level tsp)"],
  ["½ cucchiaino (tsp)", 2, "1 cucchiaino (tsp)"],
  ["½ cube", 4, "2 cubes"],
  ["2 packets", 0.5, "1 packet"],
  ["1.25 ml (≈ 1.5 g)", 0.5, "0.6 ml (≈ 0.8 g)"],
  ["0.5 g", 0.5, "0.3 g"],
  ["580 g", 3, "1.74 kg"],
  ["45–60 ml", 1.5, "68–90 ml"],
  ["¾ US cup + 1 tbsp", 1.5, "1¼ US cups"],            // just short of a cup measure (used to crash)
  // Lengths and temperatures never scale
  ["12-inch", 2, "12-inch"],
  ["10″", 0.5, "10″"],
  ["230 °C", 2, "230 °C"],
  // ×1 always returns the text exactly as written
  ["0.8 US cup", 1, "0.8 US cup"],
];

let fail = 0;
for (const [input, k, want] of CASES) {
  const got = scaleQty(input, k);
  if (got !== want) { fail++; console.log(`FAIL  ${JSON.stringify(input)} ×${k}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); }
}
// No scaled amount may ever display as zero
const data = JSON.parse(/<script type="application\/json" id="recipe-data">\n([\s\S]*?)\n<\/script>/.exec(html)[1]);
for (const r of data) for (const g of r.ingredients) for (const i of g.items) for (const q of [i.o, i.m]) {
  if (!q) continue;
  for (const k of [0.5, 1.5, 2, 3, 10]) {
    const got = scaleQty(q, k);
    if (/(^|[^\d.,½¼¾⅓⅔⅛⅜⅝⅞])0(?![.,]\d)/.test(got)) { fail++; console.log(`FAIL  zero amount: ${JSON.stringify(q)} ×${k} → ${JSON.stringify(got)}`); }
  }
}
// Every US volume from a pinch to 40 cups gives a sensible result (no crash, no zero, no NaN)
for (let tsp = 0.05; tsp < 2000; tsp += 0.05) {
  let got;
  try { got = scaleQty("1 tsp", tsp); } catch (e) { got = "CRASH " + e.message; }
  if (/CRASH|NaN|undefined|(^|[^\d½¼¾⅓⅔⅛⅜⅝⅞])0(?![.\d])/.test(got)) { fail++; console.log(`FAIL  1 tsp ×${tsp.toFixed(2)} → ${JSON.stringify(got)}`); if (fail > 20) break; }
}
console.log(fail ? `${fail} failure(s)` : `All ${CASES.length} cases passed, no zero amounts.`);
process.exit(fail ? 1 : 0);
