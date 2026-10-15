/**
 * RepDB API server — zero dependencies (Node http only), so it runs free
 * anywhere Node runs, and the same shapes are pre-generated as a static
 * tree in /api-static for serverless free hosting.
 *
 * Routes (ExerciseDB-style):
 *   GET /v1/exercises?limit=10&offset=0&search=bench
 *   GET /v1/exercises/:id
 *   GET /v1/exercises/bodyPart/:bodyPart
 *   GET /v1/exercises/target/:target
 *   GET /v1/exercises/equipment/:equipment
 *   GET /v1/bodyPartList | /v1/targetList | /v1/equipmentList
 *   GET /media/... (GIFs + photos), GET / (storefront), GET /docs
 */
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.dirname(__dirname);
const DATA = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "exercises.json"), "utf8"));
const PORT = process.env.PORT || 8787;

const MIME = { ".json": "application/json", ".gif": "image/gif", ".jpg": "image/jpeg",
               ".html": "text/html", ".md": "text/plain", ".txt": "text/plain" };

function send(res, code, body, type = "application/json") {
  const buf = Buffer.isBuffer(body) ? body : Buffer.from(body);
  res.writeHead(code, { "Content-Type": type, "Content-Length": buf.length,
                        "Access-Control-Allow-Origin": "*" });
  res.end(buf);
}
const json = (res, code, obj) => send(res, code, JSON.stringify(obj));

function paginate(req, list) {
  const u = new URL(req.url, "http://x");
  const limit = Math.min(parseInt(u.searchParams.get("limit") || "25", 10) || 25, 500);
  const offset = parseInt(u.searchParams.get("offset") || "0", 10) || 0;
  return list.slice(offset, offset + limit);
}

const server = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x");
  const p = decodeURIComponent(u.pathname);

  if (p === "/" || p === "/index.html")
    return send(res, 200, fs.readFileSync(path.join(ROOT, "site", "index.html")), "text/html");
  if (p === "/docs")
    return send(res, 200, fs.readFileSync(path.join(ROOT, "site", "docs.html")), "text/html");

  if (p.startsWith("/media/") || p.startsWith("/api-static/")) {
    const file = path.join(ROOT, p);
    if (!file.startsWith(ROOT) || !fs.existsSync(file)) return json(res, 404, { error: "not found" });
    return send(res, 200, fs.readFileSync(file), MIME[path.extname(file)] || "application/octet-stream");
  }

  if (p === "/v1/bodyPartList") return json(res, 200, [...new Set(DATA.map(e => e.bodyPart))].sort());
  if (p === "/v1/targetList") return json(res, 200, [...new Set(DATA.map(e => e.target))].sort());
  if (p === "/v1/equipmentList") return json(res, 200, [...new Set(DATA.map(e => e.equipment))].sort());

  if (p === "/v1/exercises") {
    let list = DATA;
    const q = (u.searchParams.get("search") || "").toLowerCase();
    if (q) list = list.filter(e => e.name.toLowerCase().includes(q));
    return json(res, 200, paginate(req, list));
  }
  let m = p.match(/^\/v1\/exercises\/(bodyPart|target|equipment)\/(.+)$/);
  if (m) {
    const [, field, val] = m;
    return json(res, 200, paginate(req, DATA.filter(e => e[field] === val)));
  }
  m = p.match(/^\/v1\/exercises\/(.+)$/);
  if (m) {
    const ex = DATA.find(e => e.id === m[1]);
    return ex ? json(res, 200, ex) : json(res, 404, { error: "exercise not found" });
  }
  return json(res, 404, { error: "not found" });
});

server.listen(PORT, () => console.log(`RepDB API on http://localhost:${PORT} — ${DATA.length} exercises`));
