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
  // ×1 always returns the text exactly as written
  ["0.8 US cup", 1, "0.8 US cup"],
];

let fail = 0;
for (const [input, k, want] of CASES) {
  const got = scaleQty(input, k);
  if (got !== want) { fail++; console.log(`FAIL  ${JSON.stringify(input)} ×${k}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); }
}
// (The zero-amount check over all recipe data is added with the B2 fix.)
console.log(fail ? `${fail} failure(s)` : `All ${CASES.length} cases passed.`);
process.exit(fail ? 1 : 0);
