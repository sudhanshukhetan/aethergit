const test = require("node:test"), assert = require("node:assert");
const A = require("../engine.js");
const THREAD = `**@bench_bot:** Benchmark completed: Rust rewrite was **2x slower on big files** compared to the C parser.
**@maintainer_lead:** Consensus reached: Keep the C parser. Reverting #1901.
"PR #1901 was reverted because the Rust rewrite was 2x slower on big files compared to the C parser."`;
test("extracts + verifies quote", async () => {
  const r = await A.extract(THREAD);
  assert.match(r.decided, /Keep the C parser/); assert.match(r.rejected, /Rust rewrite/);
  assert.ok(r.verify.contiguous); assert.equal(r.verify.overlap, 1);
});
test("firewall blocks regression, warns, passes", () => {
  const d = [{ decided: "Keep the C parser", rejected: "Rust rewrite", file: "parser/core.c", start: 40, end: 120 }];
  assert.equal(A.checkPR({ title: "Rewrite parser in Rust", file: "parser/core.c", line: 50 }, d).status, "block");
  assert.equal(A.checkPR({ title: "Fix typo", file: "parser/core.c", line: 50 }, d).status, "warn");
  assert.equal(A.checkPR({ title: "Rewrite in Rust", file: "parser/core.c", line: 10 }, d).status, "safe");
});
test("relinker survives rename + edit", () => {
  const o = "int parse_token_stream(TokenStream* ts) {\n  Token t = next_token(ts);\n  while (t.kind != EOF) { emit(t); t = next_token(ts); }\n  return 0;\n}";
  const n = "static void helper(int x) {\n  x++;\n}\n\nint parse_token_stream(TokenStream* ts) {\n  Token t = fast_next_token(ts);\n  while (t.kind != EOF) { emit(t); t = fast_next_token(ts); }\n  return 0;\n}";
  const r = A.relink(o, n); assert.equal(r.best.name, "parse_token_stream"); assert.ok(r.ok);
});
test("identity graph merges aliases", () => {
  const g = A.resolveIdentities("github | @demo_user | demo@example.com\ngit | Demo User | demo@example.com\ndiscuss | Demo User\nx | @other | o@x.io");
  assert.equal(g.length, 2);
});
