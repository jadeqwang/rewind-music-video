// plates.js: access to reference frames (Seedance plates extracted to plates/<id>/f0001.jpg at 24 fps).
// Plates are only ever *read*: analyzePlate() turns a frame into fields for the pencil engine.

let PLATES = {};             // id -> { n, fps, w, h, gain }
const GAIN_POW = new URLSearchParams(location.search).has('gainPow') ? +new URLSearchParams(location.search).get('gainPow') : .75;   // soften the per-plate exposure lift
const _img = new Map(), _ana = new Map();
const IMG_MAX = 24, ANA_MAX = 16;

function lruGet(m, k) { if (!m.has(k)) return undefined; const v = m.get(k); m.delete(k); m.set(k, v); return v; }
function lruSet(m, k, v, max) { m.set(k, v); while (m.size > max) m.delete(m.keys().next().value); }

function plateIndex(id, tp) { // plate-local time → 1-based frame index (clamped)
  const P0 = PLATES[id]; if (!P0) throw new Error('no plate ' + id);
  return clamp(Math.round(tp * P0.fps) + 1, 1, P0.n);
}
async function plateImage(id, tp) {
  const f = plateIndex(id, tp), key = id + '#' + f;
  let im = lruGet(_img, key);
  if (!im) { im = await loadImage(`plates/${id}/f${String(f).padStart(4, '0')}.jpg`); lruSet(_img, key, im, IMG_MAX); }
  return im;
}
// Fields for plate `id` at plate time tp (seconds). aw/ah = analysis resolution.
async function plateF(id, tp, aw = 640, ah = 360, opt = {}) {
  const f = plateIndex(id, tp), key = `${id}#${f}#${aw}x${ah}#${opt.s1 ?? ''}${opt.sT ?? ''}#${opt.gain ?? ''}`;
  let F = lruGet(_ana, key);
  if (!F) { F = analyzePlate(await plateImage(id, tp), aw, ah, { gain: Math.pow(PLATES[id].gain ?? 1, GAIN_POW), ...opt }); F.id = id; F.frame = f; lruSet(_ana, key, F, ANA_MAX); }
  return F;
}
function plateDur(id) { const P0 = PLATES[id]; return P0 ? P0.n / P0.fps : 0; }

// Subject matte (rembg) for plate time tp: an Image, or null if the plate has none. Mattes exist for odd frames.
const _mat = new Map();
async function plateMatte(id, tp) {
  let f = plateIndex(id, tp); if (f % 2 === 0) f = Math.min(f + 1, PLATES[id].n % 2 ? PLATES[id].n : PLATES[id].n - 1);
  const key = id + '#m' + f;
  if (_mat.has(key)) return lruGet(_mat, key);
  let im = null;
  if (PLATES[id] && PLATES[id].mattes) { try { im = await loadImage(`plates/${id}/m${String(f).padStart(4, '0')}.png`); } catch (e) { im = null; } }
  lruSet(_mat, key, im, 16);
  return im;
}
// Resample a matte image into a Float32 field at the analysis resolution of F (stored as F.M)
const _mc = makeCanvas(8, 8), _mg = _mc.getContext('2d', { willReadFrequently: true });
function attachMatte(F, im) {
  if (!im) { F.M = null; return F; }
  _mc.width = F.aw; _mc.height = F.ah; _mg.clearRect(0, 0, F.aw, F.ah); _mg.drawImage(im, 0, 0, F.aw, F.ah);
  const d = _mg.getImageData(0, 0, F.aw, F.ah).data, M = new Float32Array(F.aw * F.ah);
  for (let i = 0; i < M.length; i++) M[i] = d[i * 4] / 255;
  F.M = M; F.matteImg = im; return F;
}
