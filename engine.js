/* AetherGit engine: pure logic, no DOM. Works in browser (window.Aether) and Node (tests). */
(function (root) {
  const STOP = new Set("a an the and or of to in on for with is are was were be been it its this that these those from by as at we they them their our into than then so but not no pr".split(" "));
  const norm = s => s.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
  const words = s => norm(s).split(" ").filter(Boolean);
  const stem = w => w.replace(/(ing|ed|es|s)$/, "");
  const keywords = s => words(s).filter(w => w.length > 2 && !STOP.has(w)).map(stem);

  /* ---------- 1. Decision extraction + quote verification ---------- */
  const DECIDE = /\b(consensus|decided|decision|agreed|resolved|concluded|keep|keeping|chose|adopt|settled|standardi[sz]e)\b/i;
  const REJECT = /\b(reject(ed|ing)?|revert(ed|ing)?|veto(ed)?|dropped|declined|abandon(ed)?|won'?t|scrapped|ruled out)\b/gi;
  const WHY = /\b(because|since|due to|slower|faster|bugs?|unpredictabl\w*|breaks?|regress\w*|too (slow|complex)|caused?|creates?|leads? to|compared to)\b/gi;
  const count = (re, s) => (s.match(re) || []).length;

  function sentences(t) {
    return t.replace(/\r/g, "").split(/(?<=[.!?])\s+|\n+/)
      .map(s => s.replace(/^\s*\**@[\w.-]+:?\**\s*/, "").replace(/^["“”\s]+|["“”\s]+$/g, "").trim()).filter(s => s.length > 8);
  }
  const stripLabel = s => s.replace(/^[^.:]{1,30}:\s+/, "").replace(/["“”]/g, "").trim();
  const isRef = s => /^(pr|pull request|issue|commit)?\s*#?\d+$/i.test(s.trim());
  function cleanRejected(s) {
    return s.replace(/\b(was|were|is|are|been)?\s*(reject(ed)?|revert(ed|ing)?|vetoed|dropped|abandoned|scrapped)\b/i, "")
      .replace(/^(core\s+)?(developers|maintainers|reviewers|team|we|they)\s+/i, "")
      .replace(/["“”]/g, "").replace(/\s+/g, " ").trim();
  }
  function candidate(s) {
    const b = s.match(/^(.*?)\s*\b(?:because|since|due to)\b\s+(.*?)[.!?]?$/i);
    if (b) { const r = stripLabel(cleanRejected(b[1])); if (r && !isRef(r)) return { rejected: r, why: b[2].replace(/["“”]/g, "").trim() }; }
    const p = s.match(/^(.*?)\s+(?:was|is|are|were|would be)\s+(.*?)[.!?]?$/i);
    if (p && !isRef(stripLabel(p[1]))) return { rejected: stripLabel(p[1]).replace(/\*+/g, "").trim(), why: p[2].replace(/\*+/g, "").trim() };
    return null;
  }

  function extractHeuristic(text) {
    const ss = sentences(text);
    const decidedS = [...ss].reverse().find(s => DECIDE.test(s) && !count(REJECT, s)) || ss.find(s => DECIDE.test(s));
    const decided = decidedS && decidedS
      .replace(/^(the\s+)?(consensus|core developers|maintainers?)?\s*(decided|agreed|resolved|concluded)(\s+that)?\s*/i, "")
      .replace(/^(consensus( reached)?|decision)\s*:\s*/i, "").replace(/[.!?]$/, "");
    const ranked = [...ss].sort((x, y) => count(WHY, y) - count(WHY, x));
    let c = null;
    for (const s of ranked) { if (count(WHY, s) && (c = candidate(s))) break; }
    if (!c) { const rs = ss.find(s => count(REJECT, s)); if (rs) c = { rejected: cleanRejected(rs), why: ranked[0] || "" }; }
    if (!decided && !c) return null;
    const refs = [...new Set(text.match(/#\d+/g) || [])];
    return { decided: decided || "", rejected: c ? c.rejected : "", why: c ? c.why : "", evidence: c ? c.why : "", refs, engine: "heuristic" };
  }

  function verifyQuote(quote, source) {
    const nq = norm(quote), ns = norm(source), qw = words(quote), sw = new Set(words(source));
    return { contiguous: !!nq && ns.includes(nq), overlap: qw.length ? qw.filter(w => sw.has(w)).length / qw.length : 0 };
  }

  function extract(text) {
    const out = extractHeuristic(text);
    return out && { ...out, engine: "local rule engine", verify: verifyQuote(out.evidence, text) };
  }
  function suggestAnchor(text) {
    const file = (text.match(/diff --git a\/(\S+)/) || [])[1] || "";
    const h = text.match(/@@ -(\d+),(\d+) \+\d+(?:,\d+)? @@[^\n]*?(\w+)\s*\(/);
    return h ? { file, start: +h[1], end: +h[1] + +h[2] - 1, symbol: h[3] } : { file, start: "", end: "", symbol: "" };
  }

  /* ---------- 2. PR firewall ---------- */
  function checkPR({ title, file, line }, decisions) {
    const t = new Set(keywords(title)), hits = [];
    for (const d of decisions) {
      const same = d.file && file && (file === d.file || file.endsWith("/" + d.file) || d.file.endsWith("/" + file));
      if (!same) continue;
      const inRange = Number(line) >= d.start && Number(line) <= d.end;
      if (!inRange) continue;
      const dec = new Set(keywords(d.decided));
      const matched = keywords(d.rejected).filter(k => t.has(k) && !dec.has(k));
      hits.push({ d, matched, level: matched.length ? "block" : "warn" });
    }
    const block = hits.find(h => h.level === "block");
    return { status: block ? "block" : hits.length ? "warn" : "safe", hits };
  }

  /* ---------- 3. Rename-resilient relinker (AST-lite + SequenceMatcher-style ratio) ---------- */
  const NOT_FN = new Set(["if", "while", "for", "switch", "catch", "else", "return", "sizeof"]);
  const C_RE = /^[ \t]*(?:[\w*]+[\s*]+)*?(\w+)\s*\(([^;)]*)\)\s*\{/gm;
  const PY_RE = /^[ \t]*(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)[^:\n]*:/gm;
  function findFns(code) {
    const out = [];
    for (const re of [C_RE, PY_RE]) {
      re.lastIndex = 0; let m;
      while ((m = re.exec(code))) if (!NOT_FN.has(m[1])) out.push({ name: m[1], params: m[2], index: m.index });
    }
    out.sort((a, b) => a.index - b.index);
    const lineOf = i => code.slice(0, i).split("\n").length;
    return out.map((f, i) => {
      const end = i + 1 < out.length ? out[i + 1].index : code.length;
      const body = code.slice(f.index, end).replace(/\s+$/, "");
      return { ...f, body, startLine: lineOf(f.index), endLine: lineOf(f.index) + body.split("\n").length - 1 };
    });
  }
  const tokens = s => s.match(/[A-Za-z_]\w*|\d+|\S/g) || [];
  function matchCount(a, b) {
    if (!a.length || !b.length) return 0;
    let best = 0, ai = 0, bi = 0, prev = new Uint16Array(b.length + 1);
    for (let i = 1; i <= a.length; i++) {
      const cur = new Uint16Array(b.length + 1);
      for (let j = 1; j <= b.length; j++) if (a[i - 1] === b[j - 1]) {
        cur[j] = prev[j - 1] + 1;
        if (cur[j] > best) { best = cur[j]; ai = i - best; bi = j - best; }
      }
      prev = cur;
    }
    return best ? best + matchCount(a.slice(0, ai), b.slice(0, bi)) + matchCount(a.slice(ai + best), b.slice(bi + best)) : 0;
  }
  const ratio = (a, b) => (a.length + b.length) ? 2 * matchCount(a, b) / (a.length + b.length) : 1;
  const paramKeys = p => p.split(",").map(x => x.trim()).filter(Boolean).map(x => { const t = x.split(/[\s*&]+/).filter(Boolean); return t.length > 1 ? t.slice(0, -1).join("") : t[0]; });
  function sigScore(a, b) {
    const n = a.name === b.name ? 1 : ratio(a.name.split("_"), b.name.split("_"));
    const pa = new Set(paramKeys(a.params)), pb = new Set(paramKeys(b.params));
    const uni = new Set([...pa, ...pb]), inter = [...pa].filter(x => pb.has(x)).length;
    return 0.6 * n + 0.4 * (uni.size ? inter / uni.size : 1);
  }
  function relink(original, newFile, threshold = 0.6) {
    const o = findFns(original)[0];
    if (!o) return { error: "No function signature found in the original snippet." };
    const cands = findFns(newFile).map(c => {
      const sig = sigScore(o, c), seq = ratio(tokens(o.body), tokens(c.body));
      return { name: c.name, startLine: c.startLine, endLine: c.endLine, sig, seq, confidence: 0.5 * sig + 0.5 * seq };
    }).sort((a, b) => b.confidence - a.confidence);
    if (!cands.length) return { error: "No functions found in the new file." };
    return { original: o.name, best: cands[0], ok: cands[0].confidence >= threshold, others: cands.slice(1, 4), threshold };
  }

  /* ---------- 4. Contributor identity graph ---------- */
  function resolveIdentities(text) {
    const recs = text.split("\n").map(l => l.trim()).filter(Boolean).map(l => {
      const f = l.split("|").map(x => x.trim()), r = { src: f[0], name: "", handle: "", email: "", raw: [] };
      f.slice(1).forEach(x => {
        if (/^\S+@\S+\.\S+$/.test(x)) r.email = x.toLowerCase();
        else if (/^@[\w-]+$/.test(x)) r.handle = x.toLowerCase();
        else if (x) r.name = x;
      });
      return r;
    });
    const alnum = s => s.toLowerCase().replace(/[^a-z0-9]/g, "");
    const parent = recs.map((_, i) => i), find = i => parent[i] === i ? i : (parent[i] = find(parent[i]));
    const seen = new Map();
    recs.forEach((r, i) => {
      const nt = words(r.name), keys = [];
      if (r.email) keys.push("e:" + r.email, "h:" + alnum(r.email.split("@")[0]));
      if (r.handle) keys.push("h:" + alnum(r.handle));
      if (nt.length) keys.push("n:" + [...nt].sort().join(" "), "h:" + nt.join(""));
      keys.forEach(k => { if (seen.has(k)) parent[find(i)] = find(seen.get(k)); else seen.set(k, i); });
    });
    const groups = {};
    recs.forEach((r, i) => (groups[find(i)] = groups[find(i)] || []).push(r));
    return Object.values(groups).map(g => ({
      name: g.map(r => r.name).find(Boolean) || g[0].handle || g[0].email,
      handles: [...new Set(g.map(r => r.handle).filter(Boolean))], emails: [...new Set(g.map(r => r.email).filter(Boolean))],
      aliases: g.map(r => [r.handle, r.email, r.name && `${r.name} (${r.src})`].filter(Boolean)).flat().filter((v, i, a) => a.indexOf(v) === i)
    }));
  }

  const api = { extract, extractHeuristic, verifyQuote, suggestAnchor, checkPR, relink, resolveIdentities };
  if (typeof module !== "undefined") module.exports = api; else root.Aether = api;
})(typeof window !== "undefined" ? window : globalThis);
