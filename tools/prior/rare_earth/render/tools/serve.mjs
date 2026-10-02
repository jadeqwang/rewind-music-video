// Tiny static server for the renderer (preview in a browser, or capture with tools/render.mjs).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const REPO = path.resolve(ROOT, '..');
const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml',
  '.ttf': 'font/ttf', '.otf': 'font/otf', '.woff2': 'font/woff2', '.mp3': 'audio/mpeg', '.wav': 'audio/wav',
  '.glsl': 'text/plain', '.bin': 'application/octet-stream', '.geojson': 'application/json',
};

export function serve(port = 8765) {
  const server = http.createServer((req, res) => {
    let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (p === '/') p = '/index.html';
    // /audio/* is served from the repo's audio folder; /work/* from the scratch work dir (guide frames)
    let file;
    if (p.startsWith('/audio/')) file = path.join(REPO, p);
    else if (p.startsWith('/work/')) file = path.join(process.env.WORK_DIR || '/tmp/work', p.slice(6));
    else file = path.join(ROOT, p);
    if (!file.startsWith(REPO) && !file.startsWith(process.env.WORK_DIR || '/tmp/work')) { res.writeHead(403); return res.end(); }
    fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(404); return res.end('not found'); }
      res.writeHead(200, { 'Content-Type': TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream',
        'Cache-Control': 'no-store' });
      res.end(data);
    });
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve(server)));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const port = Number(process.env.PORT || 8765);
  serve(port).then(() => console.log(`serving ${ROOT} on http://127.0.0.1:${port}`));
}
