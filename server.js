// Local API + static host. Zero dependencies: `node server.js` → http://127.0.0.1:3000
const http = require("http"), fs = require("fs"), path = require("path"), A = require("./engine.js");
const PORT = process.env.PORT || 3000, DB = path.join(__dirname, "data", "decisions.json");
const load = () => { try { return JSON.parse(fs.readFileSync(DB, "utf8")); } catch (e) { return []; } };
const save = d => { fs.mkdirSync(path.dirname(DB), { recursive: true }); fs.writeFileSync(DB, JSON.stringify(d, null, 2)); };
const STATIC = { "/": ["index.html", "text/html"], "/index.html": ["index.html", "text/html"], "/engine.js": ["engine.js", "text/javascript"] };
const readBody = req => new Promise(res => {
  let b = ""; req.on("data", c => { b += c; if (b.length > 1e6) req.destroy(); });
  req.on("end", () => { try { res(JSON.parse(b || "{}")); } catch (e) { res({}); } });
});
const send = (res, code, obj) => { res.writeHead(code, { "Content-Type": "application/json" }); res.end(JSON.stringify(obj)); };

http.createServer(async (req, res) => {
  const url = req.url.split("?")[0];
  if (STATIC[url] && req.method === "GET") {
    res.writeHead(200, { "Content-Type": STATIC[url][1] + "; charset=utf-8" });
    return res.end(fs.readFileSync(path.join(__dirname, STATIC[url][0])));
  }
  if (!url.startsWith("/api/")) return send(res, 404, { error: "not found" });
  const route = url.slice(5), b = req.method === "POST" ? await readBody(req) : {};
  try {
    if (route === "health") return send(res, 200, { ok: true });
    if (route === "extract" && req.method === "POST") {
      const text = String(b.text || "");
      return send(res, 200, { result: A.extract(text), anchor: A.suggestAnchor(text) });
    }
    if (route === "decisions" && req.method === "GET") return send(res, 200, load());
    if (route === "decisions" && req.method === "POST") {
      const d = { ...b, id: b.id || Date.now() }, all = load().filter(x => x.id !== d.id);
      all.push(d); save(all); return send(res, 200, d);
    }
    if (route.startsWith("decisions/") && req.method === "DELETE") {
      save(load().filter(x => String(x.id) !== route.split("/")[1])); return send(res, 200, { ok: true });
    }
    if (route === "check" && req.method === "POST") return send(res, 200, A.checkPR(b, load()));
    if (route === "relink" && req.method === "POST") return send(res, 200, A.relink(String(b.original || ""), String(b.newFile || "")));
    if (route === "identities" && req.method === "POST") return send(res, 200, A.resolveIdentities(String(b.text || "")));
    send(res, 404, { error: "no such route" });
  } catch (e) { send(res, 500, { error: e.message }); }
}).listen(PORT, "127.0.0.1", () => console.log("AetherGit local API → http://127.0.0.1:" + PORT));
