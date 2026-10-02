// roto.js: roto sequence loading (assets/roto/<id>/{lines,matte,face,features,hair}/NNNN.png + meta.json)
// and the REDACTED NOCTURNE figure components that redraw them: luminous contours, Jade (bone fill / ghost),
// REDACTION agents (black cut-out + face bar + sunglasses glint).
//
// Loading is miss-driven and deterministic: get() returns a cached ImageBitmap or records a miss and returns null.
// The engine redraws the frame after awaiting the misses, so the output never depends on cache state.
// prefetch() warms the current shot's frames ± a window in the background; an LRU caps memory.
import { DW, DH, PAL, clamp, fin, hash, hsig, layer, clearLayer, rgba, BOIL_FPS } from './core.js';

const ROOT = '../assets/roto';
const _Q = new URLSearchParams(location.search), FORCE_V1 = _Q.has('jadev1'), CELV = _Q.get('cel') || 'cel', NOFEAT = _Q.has('nofeat');
const MAX = 80;                  // cached bitmaps (1280x720 ≈ 3.7 MB each)
const cache = new Map();          // url -> {bmp, last}
const pending = new Map();        // url -> Promise
const metas = new Map();          // id -> meta | null
let clock = 0;
export const misses = new Set();

export async function loadMeta(id) {
  if (metas.has(id)) return metas.get(id);
  let m = null;
  try { const r = await fetch(`${ROOT}/${id}/meta.json`); if (r.ok) m = await r.json(); } catch (e) { /* none */ }
  if (m) { m.fps = fin(m.fps, 15); m.layers = m.layers || ['lines', 'matte']; }
  if (m && m.layers.includes('cel') && CELV !== 'cel' && !m.layers.includes(CELV)) m.layers.push(CELV);
  if (m && m.layers.includes('cel')) { try { const r = await fetch(`${ROOT}/${id}/cel.json`); if (r.ok) m.celData = (await r.json()).frames; } catch (e) { /* none */ } }
  if (m && m.layers.includes('face')) { try { const r = await fetch(`${ROOT}/${id}/face.json`); if (r.ok) m.faceData = await r.json(); } catch (e) { /* no template data */ } }
  metas.set(id, m);
  return m;
}
export const meta = id => metas.get(id) || null;

const url = (id, lay, i) => `${ROOT}/${id}/${lay}/${String(i).padStart(4, '0')}.png`;
export function frameIndex(m, clipT) { return Math.max(0, Math.min(m.frames - 1, Math.floor(fin(clipT) * m.fps + 1e-3))); }

function load(u) {
  if (cache.has(u)) return Promise.resolve();
  if (pending.has(u)) return pending.get(u);
  const p = fetch(u).then(r => (r.ok ? r.blob() : null)).then(b => (b ? createImageBitmap(b) : null)).then(bmp => {
    cache.set(u, { bmp, last: ++clock }); pending.delete(u);
    if (cache.size > MAX) {
      const old = [...cache.entries()].sort((a, b) => a[1].last - b[1].last).slice(0, cache.size - MAX + 20);
      for (const [k, v] of old) { if (v.bmp && v.bmp.close) v.bmp.close(); cache.delete(k); }
    }
  }).catch(() => { cache.set(u, { bmp: null, last: ++clock }); pending.delete(u); });
  pending.set(u, p);
  return p;
}
export function get(id, lay, clipT) {
  const m = meta(id); if (!m || !m.layers.includes(lay)) return null;
  const u = url(id, lay, frameIndex(m, clipT));
  const e = cache.get(u);
  if (e) { e.last = ++clock; return e.bmp; }
  misses.add(u); return null;
}
export async function resolveMisses() { const l = [...misses]; misses.clear(); await Promise.all(l.map(load)); return l.length; }
export function prefetch(id, clipT, ahead = 10, behind = 2) {
  const m = meta(id); if (!m) return;
  const f0 = frameIndex(m, clipT);
  for (let f = Math.max(0, f0 - behind); f <= Math.min(m.frames - 1, f0 + ahead); f++) for (const l of m.layers) load(url(id, l, f));
}
export function perFrame(id, clipT) { const m = meta(id); if (!m || !m.per_frame) return {}; return m.per_frame[frameIndex(m, clipT)] || {}; }

// ------------------------------------------------------------------------------------------------
// helpers working at roto resolution (scratch canvases match the roto frame size)

function scratch(name, m) { const c = layer('roto_' + name, m.w, m.h); if (!c.ctxR) { c.ctxR = true; c.ctx = c.getContext('2d', { willReadFrequently: true }); } return c; }
// tint a white-on-transparent bitmap into a scratch canvas
function tinted(name, m, bmp, color, alpha = 1, times = 1) {
  const c = scratch(name, m), g = clearLayer(c);
  g.globalAlpha = alpha; for (let k = 0; k < times; k++) g.drawImage(bmp, 0, 0, m.w, m.h); g.globalAlpha = 1;
  g.globalCompositeOperation = 'source-in'; g.fillStyle = color; g.fillRect(0, 0, m.w, m.h);
  g.globalCompositeOperation = 'source-over';
  return c;
}
// ring around a matte: dilate by r (8 taps) minus the matte, optionally one-sided (dir = [dx,dy] light direction)
function ring(name, m, bmp, r, color, dir = null) {
  const c = scratch(name, m), g = clearLayer(c);
  if (dir) g.drawImage(bmp, -dir[0] * r, -dir[1] * r, m.w, m.h);
  else if (false) {}
  else for (let k = 0; k < 8; k++) { const a = k * Math.PI / 4; g.drawImage(bmp, Math.cos(a) * r, Math.sin(a) * r, m.w, m.h); }
  hardAlpha(c); g.globalCompositeOperation = 'destination-out'; g.drawImage(bmp, 0, 0, m.w, m.h); g.drawImage(bmp, 0, 0, m.w, m.h);
  g.globalCompositeOperation = 'source-in'; g.fillStyle = color; g.fillRect(0, 0, m.w, m.h);
  g.globalCompositeOperation = 'source-over';
  hardAlpha(c);
  return c;
}

// placement: where a roto frame lands in design space ({x,y,w,h}; default full frame), with boil jitter
export function boilSeed(shotId, lt) { return Math.floor(fin(lt) * BOIL_FPS + 1e-6); }
function place(g, src, rect, jit) {
  const r = rect || { x: 0, y: 0, w: DW, h: DH };
  if (jit) {
    g.save(); g.translate(r.x + r.w / 2 + jit.dx, r.y + r.h / 2 + jit.dy); g.rotate(jit.rot); g.scale(1 + jit.s, 1 + jit.s);
    g.drawImage(src, -r.w / 2, -r.h / 2, r.w, r.h); g.restore();
  } else g.drawImage(src, r.x, r.y, r.w, r.h);
}
export function jitter(seed, amp = 1) {
  return { dx: hsig(seed, 1) * 1.6 * amp, dy: hsig(seed, 2) * 1.2 * amp, rot: hsig(seed, 3) * 0.0011 * amp, s: hsig(seed, 4) * 0.0018 * amp };
}

// ---- luminous contour lines -------------------------------------------------------------------
// opts: {color, alpha, rect, boil (seed), boilAmp, double (sketchy second pass), fog:{y0,y1,min} (design y; fades lines
//        toward the horizon), exclude (matte id to cut out), comp ('lighter' for additive)}
export function contours(g, id, clipT, o = {}) {
  const m = meta(id); const bmp = get(id, 'lines', clipT); if (!m || !bmp) return false;
  const c = tinted('lines', m, bmp, o.color || PAL.bone, 1);
  const cg = c.ctx;
  if (o.exclude) { const mt = get(o.exclude, 'matte', clipT); if (mt) { cg.globalCompositeOperation = 'destination-out'; cg.drawImage(mt, 0, 0, m.w, m.h); cg.globalCompositeOperation = 'source-over'; } }
  if (o.fog) {
    const r = o.rect || { y: 0, h: DH }, k = m.h / r.h;
    const gr = cg.createLinearGradient(0, (o.fog.y0 - r.y) * k, 0, (o.fog.y1 - r.y) * k);
    gr.addColorStop(0, `rgba(0,0,0,${o.fog.min ?? 0.12})`); gr.addColorStop(1, 'rgba(0,0,0,1)');
    cg.globalCompositeOperation = 'destination-in'; cg.fillStyle = gr; cg.fillRect(0, 0, m.w, m.h); cg.globalCompositeOperation = 'source-over';
  }
  g.save(); g.globalCompositeOperation = o.comp || 'lighter';
  const amp = o.boilAmp ?? 1, seed = o.boil ?? 0;
  g.globalAlpha = clamp(o.alpha ?? 1) * (o.double ? 0.75 : 1);
  place(g, c, o.rect, amp ? jitter(seed, amp) : null);
  if (o.double) { g.globalAlpha = clamp(o.alpha ?? 1) * 0.4; place(g, c, o.rect, jitter(seed + 0.5, amp * 1.8)); }
  g.restore();
  return true;
}

// ---- Jade: flat bone-white figure with sparse interior lines --------------------------------------
// LIKENESS RULES: inside the face mask only `features` (eyes at full size, brows, nose tip, jaw/hair contours) and the
// vocal-driven mouth are drawn; every other line is suppressed there. No texture, hatching or speckle on skin, ever.
// opts: {rect, boil, fill, lineColor, ghost (outline-only past attempt), ghostColor, light:{color, amount, from:[x0,y0,x1,y1]},
//        mouth (0..1 openness from the vocal envelope), alpha}
export function jade(g, id, clipT, o = {}) {
  const m0 = meta(id);
  if (m0 && m0.layers.includes('cel') && !o.v1 && !o.ghost && !FORCE_V1) return jade2(g, id, clipT, o);
  const m = m0; const mt = get(id, 'matte', clipT); if (!m || !mt) return false;
  const face = get(id, 'face', clipT), feat = get(id, 'features', clipT), hair = get(id, 'hair', clipT), lines = get(id, 'lines', clipT);
  const pf = perFrame(id, clipT);
  const A = scratch('jadeA', m), a = clearLayer(A);
  const lineCol = o.lineColor || PAL.ink;
  if (o.ghost) {
    // past attempt (Braid shadow): outline only, plus the features, in ghost colour
    const col = o.ghostColor || PAL.cyan;
    a.drawImage(ring('jring', m, mt, 2.2, col), 0, 0);
    if (feat) { a.globalAlpha = 0.8; a.drawImage(tinted('jfeat', m, feat, col), 0, 0); a.globalAlpha = 1; }
  } else {
    if (o.rim) { a.globalAlpha = clamp(o.rim.alpha ?? 0.6); a.drawImage(ring('jrim', m, mt, o.rim.w ?? 1.6, o.rim.color || PAL.bone), 0, 0); a.globalAlpha = 1; }
    const F0 = scratch('jadeF', m), f0 = clearLayer(F0);
    f0.drawImage(mt, 0, 0, m.w, m.h); hardAlpha(F0, 70, 150);
    f0.globalCompositeOperation = 'source-in'; f0.fillStyle = o.fill || PAL.bone; f0.fillRect(0, 0, m.w, m.h);
    f0.globalCompositeOperation = 'source-over';
    a.drawImage(F0, 0, 0);
    a.globalCompositeOperation = 'source-atop';
    if (o.light && o.light.amount > 0) {   // a flat wash of light across the figure (sodium sweep, siren spill)
      const L = o.light, k = m.w / DW, gr = a.createLinearGradient(L.from[0] * k, L.from[1] * k, L.from[2] * k, L.from[3] * k);
      gr.addColorStop(0, rgba(L.color, 0)); gr.addColorStop(0.5, rgba(L.color, L.amount)); gr.addColorStop(1, rgba(L.color, 0));
      a.fillStyle = gr; a.fillRect(0, 0, m.w, m.h);
    }
    if (hair) {
      const H = tinted('jhair', m, hair, o.hairColor || PAL.ink); hardAlpha(H, 60, 170);
      const fdh = m.faceData && m.faceData[frameIndex(m, clipT)];
      const pts = fdh ? [].concat(fdh.jaw || [], fdh.eye_L_upper || [], fdh.eye_R_upper || [], fdh.eye_near_upper || [], fdh.N ? [fdh.N] : []) : [];
      if (pts.length > 2) {
        const b = bboxOf(pts), fw = Math.max(b.w, 120), cx = b.cx;
        a.save(); a.beginPath(); a.rect(cx - fw * 2.4, 0, fw * 4.8, b.y1 + fw * 2.2); a.clip(); a.drawImage(H, 0, 0); a.restore();
      } else a.drawImage(H, 0, 0);
    }
    if (lines) {   // interior lines outside the face only
      const B = tinted('jlines', m, lines, lineCol), b = B.ctx;
      if (face) { b.globalCompositeOperation = 'destination-out'; b.drawImage(face, 0, 0, m.w, m.h); b.globalCompositeOperation = 'source-over'; }
      a.drawImage(B, 0, 0);
    }
    if (feat) a.drawImage(tinted('jfeat', m, feat, m.faceData ? (o.featColor || '#3A3230') : lineCol), 0, 0);   // softer warm-dark features on the real template (brows not heavy)
    if (pf.mouth) drawMouth(a, pf.mouth, pf.face_mode === 'profile' ? Math.min(0.06, o.mouth ?? 0) : clamp(o.mouth ?? 0) * 0.8, m.faceData ? '#4A3A38' : lineCol, pf.tilt || 0);
    if (m.faceData && o.glasses !== false) drawGlasses(a, m.faceData[frameIndex(m, clipT)], o);
    a.globalCompositeOperation = 'source-over';
  }
  g.save(); g.globalAlpha = clamp(o.alpha ?? 1);
  place(g, A, o.rect, o.boil != null ? jitter(o.boil, 0.6) : null);
  g.restore();
  return true;
}
// ---- glasses: her identity marker, always on. Thin rectangular frames (dark grey-teal), sized to her real frames
// (frame width ≈ 1.1 × outer-canthus distance), placed from the template eye anchors (face.json) and head yaw/roll.
const GL = '#1C2E31';
const bboxOf = pts => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const [x, y] of pts) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); } return { x0, y0, x1, y1, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: x1 - x0, h: y1 - y0 }; };
function lens(a, cx, cy, w, h, rot, lw) {
  a.save(); a.translate(cx, cy); a.rotate(rot);
  const r = h * 0.28; a.beginPath(); a.moveTo(-w / 2 + r, -h / 2); a.lineTo(w / 2 - r, -h / 2); a.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r); a.lineTo(w / 2, h / 2 - r); a.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2); a.lineTo(-w / 2 + r, h / 2); a.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r); a.lineTo(-w / 2, -h / 2 + r); a.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2); a.closePath();
  a.fillStyle = 'rgba(61,242,230,0.07)'; a.fill();
  a.strokeStyle = GL; a.lineWidth = lw; a.stroke();
  // faint lens glint: one short diagonal streak, top-left
  a.strokeStyle = 'rgba(255,255,255,0.75)'; a.lineWidth = lw * 0.7; a.beginPath(); a.moveTo(-w * 0.32, -h * 0.05); a.lineTo(-w * 0.18, -h * 0.32); a.stroke();
  a.restore();
}
function drawGlasses(a, fd, o) {
  if (!fd) return;
  a.save(); a.globalCompositeOperation = 'source-over'; a.lineCap = 'round'; a.lineJoin = 'round';
  if (fd.eye_L_upper && fd.eye_R_upper) {
    const L = bboxOf([...fd.eye_L_upper, ...(fd.eye_L_lower || [])]), Rr = bboxOf([...fd.eye_R_upper, ...(fd.eye_R_lower || [])]);
    const left = L.cx < Rr.cx ? L : Rr, right = L.cx < Rr.cx ? Rr : L;
    const outer = right.x1 - left.x0, Wf = outer * 1.14, rot = Math.atan2(right.cy - left.cy, right.cx - left.cx);
    const bridge = Wf * 0.11, lw0 = (Wf - bridge) / 2, hh = lw0 * 0.44, lwid = Math.max(3.5, Wf * 0.028);
    // foreshortening with yaw: each lens keeps its eye's share of the width
    const sL = left.w / (left.w + right.w) * 2, sR = 2 - sL;
    const cxm = (left.x0 + right.x1) / 2, cym = (left.cy + right.cy) / 2 + hh * 0.08, c = Math.cos(rot), s_ = Math.sin(rot);
    const off = d => [cxm + c * d, cym + s_ * d];
    const lL = lw0 * sL, lR = lw0 * sR, half = (lL + lR + bridge) / 2;
    const pL = off(-half + lL / 2), pR = off(half - lR / 2);
    lens(a, pL[0], pL[1], lL, hh, rot, lwid); lens(a, pR[0], pR[1], lR, hh, rot, lwid);
    const b0 = off(-half + lL), b1 = off(half - lR);
    a.strokeStyle = GL; a.lineWidth = lwid; a.beginPath(); a.moveTo(b0[0], b0[1] - hh * 0.2); a.quadraticCurveTo((b0[0] + b1[0]) / 2, (b0[1] + b1[1]) / 2 - hh * 0.38, b1[0], b1[1] - hh * 0.2); a.stroke();
    // temples: short arms back toward the ears
    const tl = off(-half), tr = off(half);
    a.beginPath(); a.moveTo(tl[0], tl[1] - hh * 0.3); a.lineTo(tl[0] - lw0 * 0.18, tl[1] - hh * 0.25); a.moveTo(tr[0], tr[1] - hh * 0.3); a.lineTo(tr[0] + lw0 * 0.18, tr[1] - hh * 0.25); a.stroke();
  } else if (fd.eye_near_upper) {
    // profile: the near lens side-on and the temple arm running back to the ear
    const E = bboxOf([...fd.eye_near_upper, ...(fd.eye_near_lower || [])]), N = fd.N || [E.cx - 40, E.cy + 40];
    const dir = N[0] < E.cx ? -1 : 1, w = E.w * 1.45, h = w * 0.62, lwid = Math.max(3.5, w * 0.07);
    const cx = E.cx + dir * w * 0.08, cy = E.cy + h * 0.05;
    lens(a, cx, cy, w, h, 0, lwid);
    a.strokeStyle = GL; a.lineWidth = lwid; a.beginPath(); const x0 = cx - dir * w / 2; a.moveTo(x0, cy - h * 0.3); a.lineTo(x0 - dir * w * 2.2, cy - h * 0.18); a.stroke();
  }
  a.restore();
}

// ---- Jade v2: 3-tone cel figure (tools/jade2/build.py) + template features drawn as vectors from face.json ----
const FEAT = '#5B4237', LIDC = '#1E1716', LIP = '#C99B94', LIPD = '#6A4440';
function poly(a, pts, close) { a.beginPath(); pts.forEach((p, i) => (i ? a.lineTo(p[0], p[1]) : a.moveTo(p[0], p[1]))); if (close) a.closePath(); }
function smoothPath(a, pts) {   // quadratic midpoint smoothing
  if (pts.length < 3) return poly(a, pts);
  a.beginPath(); a.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length - 1; i++) { const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2; a.quadraticCurveTo(pts[i][0], pts[i][1], mx, my); }
  const l = pts[pts.length - 1]; a.lineTo(l[0], l[1]);
}
// her real eye opening (opening / width) and iris size (iris diameter / face width) from the real-photo template
const EYE_OPEN = 0.39,   // drawn target; measures as her real mean 0.358 (MediaPipe reads the lid stroke inner edge)
  _EYE_REAL = 0.358, IRIS_FACE = 0.096, IOD_FW = 0.6578;
function fitEye(up, lo, closure) {
  const all = [...up, ...lo]; let x0 = 1e9, x1 = -1e9; for (const p of all) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); }
  const a = all.find(p => p[0] === x0), b = all.find(p => p[0] === x1), w = x1 - x0;
  const yl = x => a[1] + (b[1] - a[1]) * (x - x0) / (w || 1);
  let op = 0; for (const p of up) op = Math.max(op, yl(p[0]) - p[1]); let ol = 0; for (const p of lo) ol = Math.max(ol, p[1] - yl(p[0]));
  const cur = (op + ol) / (w || 1), k = (closure == null || closure > 0.5) && cur > 0.05 ? EYE_OPEN / cur : 1;
  const f = p => [p[0], yl(p[0]) + (p[1] - yl(p[0])) * k];
  return { up: up.map(f), lo: lo.map(f), k, cy: yl((x0 + x1) / 2) };
}
function eye(a, up, lo, crease, iris, closure, sc, fwPx) {
  if (!up) return;
  const open = closure == null ? 1 : clamp(closure);
  if (lo && lo.length) { const F = fitEye(up, lo, closure); up = F.up; lo = F.lo; if (crease) crease = crease.map(p => [p[0], F.cy + (p[1] - F.cy) * (1 + (F.k - 1) * 0.8)]); }
  if (iris && fwPx) iris = [iris[0], iris[1], fwPx * IRIS_FACE / 2];
  // white of the eye (bone) clipped by the lids, iris dark with a catchlight
  a.save();
  poly(a, [...up, ...(lo || []).slice().reverse()], true); a.fillStyle = '#F4EFE6'; a.fill(); a.clip();
  if (iris && open > 0.3) {
    const [ix, iy, ir] = iris.length >= 3 ? iris : [iris[0], iris[1], sc * 0.07];
    a.fillStyle = '#2A1F1C'; a.beginPath(); a.arc(ix, iy, ir, 0, Math.PI * 2); a.fill();
    a.fillStyle = '#0B0807'; a.beginPath(); a.arc(ix, iy, ir * 0.48, 0, Math.PI * 2); a.fill();
    a.fillStyle = '#FFFFFF'; a.beginPath(); a.arc(ix - ir * 0.32, iy - ir * 0.36, Math.max(1.4, ir * 0.2), 0, Math.PI * 2); a.fill();
  }
  a.restore();
  a.lineCap = 'round'; a.lineJoin = 'round';
  smoothPath(a, up); a.strokeStyle = LIDC; a.lineWidth = Math.max(3, sc * 0.04); a.stroke();   // the upper lid is the dominant stroke
  if (lo) { smoothPath(a, lo); a.strokeStyle = 'rgba(58,46,44,0.55)'; a.lineWidth = Math.max(1, sc * 0.009); a.stroke(); }
  if (crease) { smoothPath(a, crease); a.strokeStyle = 'rgba(58,46,44,0.6)'; a.lineWidth = Math.max(1, sc * 0.008); a.stroke(); }
}
// her brows: soft, medium-thin, tapered tails (keeps the template's per-side shape/asymmetry, only thins it)
function thinBrow(b, profile) {
  const n = b.length, h = Math.floor(n / 2), out = b.map(p => p.slice());
  // which end is lateral: the end farther from the face centre line is the tail (approx: larger |x - mean|)
  for (let i = 0; i < h; i++) {
    const j = n - 1 - i, u = i / Math.max(1, h - 1);
    const mx = (b[i][0] + b[j][0]) / 2, my = (b[i][1] + b[j][1]) / 2;
    const k = 0.74 * (1 - 0.45 * Math.pow(u, 1.8));   // thinner overall, tapering toward the tail
    out[i] = [mx + (b[i][0] - mx) * k, my + (b[i][1] - my) * k]; out[j] = [mx + (b[j][0] - mx) * k, my + (b[j][1] - my) * k];
  }
  return out;
}
export function jade2(g, id, clipT, o = {}) {
  const m = meta(id), fi = frameIndex(m, clipT), cel = get(id, CELV, clipT) || get(id, 'cel', clipT); if (!cel) return false;
  const fd = m.faceData && m.faceData[fi] || {}, cd = m.celData && (m.celData[fi] || m.celData[String(fi)]) || {}, pf = perFrame(id, clipT);
  const A = scratch('jade2', m), a = clearLayer(A);
  a.drawImage(cel, 0, 0, m.w, m.h);
  // scene light: a restrained wash on the figure only (keeps the 3 tones readable)
  if (o.light && o.light.amount > 0) {   // multiply: tints bone/mid, never lifts the ink
    const L = o.light, k = m.w / DW, gr = a.createLinearGradient(L.from[0] * k, L.from[1] * k, L.from[2] * k, L.from[3] * k);
    gr.addColorStop(0, rgba(L.color, 0)); gr.addColorStop(0.5, rgba(L.color, L.amount * 0.35)); gr.addColorStop(1, rgba(L.color, 0));
    a.globalCompositeOperation = 'multiply'; a.fillStyle = gr; a.fillRect(0, 0, m.w, m.h); a.globalCompositeOperation = 'destination-in'; a.drawImage(cel, 0, 0, m.w, m.h); a.globalCompositeOperation = 'source-over';
  }
  const lines = get(id, 'lines', clipT), faceM = get(id, 'face', clipT);
  if (lines && !o.noLines) {   // hands / sleeves / wheel: the roto agent's clean vector line art, in ink, on the figure only
    const Lc = tinted('jlines2', m, lines, PAL.ink); const lg = Lc.ctx;
    lg.globalCompositeOperation = 'destination-in'; lg.drawImage(cel, 0, 0, m.w, m.h);
    if (faceM) { lg.globalCompositeOperation = 'destination-out'; for (let k = 0; k < 2; k++) lg.drawImage(faceM, 0, 0, m.w, m.h); }
    lg.globalCompositeOperation = 'source-over';
    a.globalAlpha = 0.85; a.drawImage(Lc, 0, 0); a.globalAlpha = 1;
  }
  const sc = fd.template_scale_px || (cd.iod) || 150;
  if (NOFEAT) { if (o.glasses !== false) drawGlasses(a, fd, o); g.save(); g.globalAlpha = clamp(o.alpha ?? 1); place(g, A, o.rect, null); g.restore(); return true; }
  // brows: filled tapered polygons (her own asymmetric template)
  a.fillStyle = FEAT;
  for (const b of [fd.brow_R, fd.brow_L, fd.brow_near]) if (b && b.length > 2) { poly(a, thinBrow(b, fd.brow_near === b), true); a.fill(); }
  const fwPx = (fd.template_scale_px || sc) / IOD_FW;
  eye(a, fd.eye_R_upper, fd.eye_R_lower, fd.eye_R_crease, fd.eye_R_iris, fd.eye_R_closure, sc, fwPx);
  eye(a, fd.eye_L_upper, fd.eye_L_lower, fd.eye_L_crease, fd.eye_L_iris, fd.eye_L_closure, sc, fwPx);
  eye(a, fd.eye_near_upper, fd.eye_near_lower, fd.eye_near_crease, fd.eye_near_iris, 1, sc * 1.4, null);
  // nose: a small soft mid-tone shadow on the shadow side of the bridge/tip + nostril hints
  if (cd.nose) {
    const [nx, ny] = cd.nose, s_ = sc, side = (o.light && o.light.from && o.light.from[0] > nx) ? -1 : 1;
    a.fillStyle = 'rgba(150,140,132,0.75)';
    a.beginPath(); a.moveTo(nx + side * s_ * 0.05, ny - s_ * 0.26); a.quadraticCurveTo(nx + side * s_ * 0.11, ny - s_ * 0.1, nx + side * s_ * 0.09, ny + s_ * 0.02);
    a.quadraticCurveTo(nx + side * s_ * 0.04, ny + s_ * 0.05, nx + side * s_ * 0.02, ny - s_ * 0.05); a.quadraticCurveTo(nx + side * s_ * 0.05, ny - s_ * 0.14, nx + side * s_ * 0.04, ny - s_ * 0.26); a.closePath(); a.fill();
    a.fillStyle = 'rgba(90,70,66,0.7)';
    for (const sd of [-1, 1]) { a.beginPath(); a.ellipse(nx + sd * s_ * 0.075, ny + s_ * 0.045, s_ * 0.03, s_ * 0.014, sd * 0.4, 0, Math.PI * 2); a.fill(); }
    a.strokeStyle = 'rgba(90,70,66,0.55)'; a.lineWidth = Math.max(1.4, s_ * 0.012); a.beginPath(); a.moveTo(nx - s_ * 0.05, ny + s_ * 0.06); a.quadraticCurveTo(nx, ny + s_ * 0.085, nx + s_ * 0.05, ny + s_ * 0.06); a.stroke();
  } else if (cd.nostril) { const [nx, ny] = cd.nostril; a.fillStyle = 'rgba(90,70,66,0.75)'; a.beginPath(); a.ellipse(nx, ny, sc * 0.035, sc * 0.016, 0.3, 0, Math.PI * 2); a.fill(); }
  // lips: two soft tone shapes + the mouth line; openness from the vocal envelope
  const open = clamp(o.mouth ?? 0);
  if (cd.lips) {
    const cx = cd.lips.outer.reduce((s, p) => s + p[0], 0) / cd.lips.outer.length, cy = cd.lips.inner.reduce((s, p) => s + p[1], 0) / cd.lips.inner.length;
    const shr = p => [cx + (p[0] - cx) * 0.86, cy + (p[1] - cy) * 0.86];
    const lo = cd.lips.outer.map(shr), li = cd.lips.inner.map(shr), h = Math.max(3, sc * 0.07) * open;
    const mv = p => [p[0], p[1] > cy ? p[1] + h : p[1]];
    poly(a, lo.map(mv), true); a.fillStyle = LIP; a.fill();
    if (open > 0.12) { const xs = li.map(p => p[0]), w2 = (Math.max(...xs) - Math.min(...xs)) * 0.42; a.fillStyle = LIPD; a.beginPath(); a.ellipse(cx, cy + h * 0.4, w2, Math.max(1.5, h * 0.55), 0, 0, Math.PI * 2); a.fill(); }
    // mouth line (the meeting of the lips)
    const n = li.length, upperIn = li.slice(0, Math.ceil(n / 2) + 1);
    smoothPath(a, upperIn); a.strokeStyle = LIPD; a.lineWidth = Math.max(1.6, sc * 0.016); a.stroke();
  } else if ((cd.mouth_corner || pf.mouth) && cd.E) {
    const [mx, my] = cd.mouth_corner || pf.mouth, back = cd.back || 1, dd = Math.hypot(cd.N[0] - cd.E[0], cd.N[1] - cd.E[1]);
    a.fillStyle = LIP; a.beginPath(); a.ellipse(mx - back * dd * 0.18, my + 1, dd * 0.2, dd * 0.07 + open * dd * 0.06, 0, 0, Math.PI * 2); a.fill();
    a.strokeStyle = LIPD; a.lineWidth = Math.max(1.6, dd * 0.03); a.beginPath(); a.moveTo(mx, my); a.lineTo(mx - back * dd * 0.36, my - dd * 0.02); a.stroke();
  }
  // glasses: front = rectangular frames from the eye anchors; profile = foreshortened lens + temple arm to the ear
  if (o.glasses !== false) {
    if (cd.glasses && cd.glasses.kind === 'profile') {
      let q = cd.glasses.lens; const lw = Math.max(3.5, sc * 0.03);
      const ir = fd.eye_near_iris || cd.E;
      if (ir) {   // the lens sits over the eye (slightly forward of the iris)
        const cx0 = q.reduce((s, p) => s + p[0], 0) / 4, cy0 = q.reduce((s, p) => s + p[1], 0) / 4, back = cd.back || 1;
        const qw = Math.max(...q.map(p => p[0])) - Math.min(...q.map(p => p[0]));
        const dx = ir[0] - back * qw * 0.12 - cx0, dy = ir[1] - cy0; q = q.map(p => [p[0] + dx, p[1] + dy]);
        cd.glasses = { ...cd.glasses, arm: [[cd.glasses.arm[0][0] + dx, cd.glasses.arm[0][1] + dy], cd.glasses.arm[1]] };
      }
      poly(a, q, true); a.fillStyle = 'rgba(61,242,230,0.06)'; a.fill(); a.strokeStyle = GL; a.lineWidth = lw; a.lineJoin = 'round'; a.stroke();
      const [p0, p1] = cd.glasses.arm; a.beginPath(); a.moveTo(p0[0], p0[1]); a.lineTo(p1[0], p1[1]); a.stroke();
      a.strokeStyle = 'rgba(255,255,255,0.7)'; a.lineWidth = lw * 0.6; a.beginPath(); a.moveTo(q[0][0] * 0.7 + q[3][0] * 0.3, q[0][1] * 0.7 + q[3][1] * 0.3); a.lineTo(q[0][0] * 0.85 + q[1][0] * 0.15, q[0][1] * 0.85 + q[1][1] * 0.15); a.stroke();
    } else drawGlasses(a, fd, o);
  }
  g.save(); g.globalAlpha = clamp(o.alpha ?? 1);
  place(g, A, o.rect, null);   // no boil on her: the likeness stays steady
  g.restore();
  return true;
}

// lips from the vocal track: a closed mouth is one soft ink stroke; open = a small almond whose height follows the voice
function drawMouth(a, [x, y, w], open, col, tilt) {
  a.save(); a.translate(x, y); a.rotate(tilt); a.fillStyle = col; a.strokeStyle = col; a.lineCap = 'round';
  const hw = w / 2, h = 2 + open * 15;
  if (open < 0.08) { a.lineWidth = 2.4; a.beginPath(); a.moveTo(-hw * .8, 0); a.quadraticCurveTo(0, 2.5, hw * .8, 0); a.stroke(); }
  else { a.beginPath(); a.moveTo(-hw * .78, 0); a.quadraticCurveTo(0, -h * .55, hw * .78, 0); a.quadraticCurveTo(0, h, -hw * .78, 0); a.fill(); }
  a.restore();
}

// ---- REDACTION agents ----------------------------------------------------------------------------
// black cut-outs from the matte, a one-sided rim of siren light, FOIA face bars and a sunglasses glint.
// opts: {rect, boil, rimL (colour from the left), rimR, rimAmt, bars (true), barLabel ('(b)(6)'), glint (0..1), glintSeed}
export function suits(g, id, clipT, o = {}) {
  const m = meta(id); const mt = get(id, 'matte', clipT); if (!m || !mt) return false;
  const pf = perFrame(id, clipT);
  const A = scratch('suitA', m), a = clearLayer(A);
  if (o.rimL) { a.globalAlpha = clamp(o.rimAmt ?? 1); a.drawImage(ring('rimL', m, mt, 3.5, o.rimL, [-1, 0]), 0, 0); }
  if (o.rimR) { a.globalAlpha = clamp(o.rimAmt ?? 1); a.drawImage(ring('rimR', m, mt, 3.5, o.rimR, [1, 0]), 0, 0); }
  a.globalAlpha = 1;
  const B = tinted('suitB', m, mt, '#000000', 1, 1);
  hardAlpha(B);   // flat cut-out: no soft/partial matte lets the world show through as smudge
  a.drawImage(B, 0, 0);
  g.save();
  const r = o.rect || { x: 0, y: 0, w: DW, h: DH }, kx = r.w / m.w, ky = r.h / m.h;
  const jit = o.boil != null ? jitter(o.boil, 0.5) : null;
  place(g, A, r, jit);
  // face bars: wider than the head, so they cross into the light and read as redaction, not as hair
  if (o.bars !== false && pf.faces) {
    for (let i = 0; i < pf.faces.length; i++) {
      const [cx, cy, fw, fh] = pf.faces[i];
      if (!o.allFaces && cy > m.h * 0.5) continue;   // false 'heads' low in frame (wheels, hands)
      const x = r.x + cx * kx, y = r.y + cy * ky, w = fw * kx * (o.barW ?? 1.55), h = fh * ky * (o.barH ?? 1.0);
      const ox = hsig(i, o.boil ?? 0, 7) * 1.2;
      g.fillStyle = '#000'; g.fillRect(x - w / 2 + ox, y - h / 2, w, h);
      if (o.barLabel) { g.fillStyle = rgba(o.labelColor || PAL.boneDim, 0.85); g.font = `500 ${Math.round(12 * kx * 1.5)}px JBM`; g.textBaseline = 'top'; g.fillText(o.barLabel, x + w / 2 + 6, y - h / 2); }
    }
  }
  // sunglasses glint: a sharp four-point star that lives on top of the bar
  if (pf.glints && (o.glint ?? 0) > 0) {
    for (let i = 0; i < pf.glints.length; i++) {
      if (!o.allFaces && pf.glints[i][1] > m.h * 0.5) continue;
      const gi = clamp((o.glint) * (0.55 + 0.45 * hash(i, o.glintSeed ?? 0)));
      if (gi < 0.02) continue;
      const [gx, gy] = pf.glints[i];
      star(g, r.x + (gx + 18 * (i % 2 ? 1 : -1)) * kx, r.y + gy * ky, 16 + 44 * gi, gi, PAL.bone);
    }
  }
  g.restore();
  return true;
}
export function star(g, x, y, R, a, col) {
  g.save(); g.globalCompositeOperation = 'lighter'; g.fillStyle = rgba(col, clamp(a));
  g.beginPath();
  const w = Math.max(1.2, R * 0.06);
  g.moveTo(x - R, y); g.lineTo(x - w, y - w); g.lineTo(x, y - R * 0.8); g.lineTo(x + w, y - w); g.lineTo(x + R, y); g.lineTo(x + w, y + w); g.lineTo(x, y + R * 0.8); g.lineTo(x - w, y + w); g.closePath(); g.fill();
  g.beginPath(); g.arc(x, y, w * 1.8, 0, Math.PI * 2); g.fill();
  g.restore();
}

// threshold a scratch canvas' alpha (ramp 70..130) so mattes are FLAT shapes, never textured
export function hardAlpha(c, lo = 96, hi = 112) {
  const g = c.ctx, im = g.getImageData(0, 0, c.width, c.height), d = im.data, k = 255 / (hi - lo);
  for (let i = 3; i < d.length; i += 4) { const a = d[i]; d[i] = a < lo ? 0 : a > hi ? 255 : (a - lo) * k; }
  g.putImageData(im, 0, 0);
}
// ---- light layer (format addition): RGB = the light's own colour, alpha = brightness; drawn additively ----
// tools/roto atlas ('light', 960x270): left half R siren_red G sodium B siren_blue, right half R cold_white G ground B luma.
// Colourised once per frame into a 480x270 RGBA canvas (cached), then drawn additively like 'lights'.
const atlasCache = new Map();
const LCOL = { red: [255, 42, 42], sodium: [255, 159, 28], blue: [47, 91, 255], white: [236, 230, 216] };
function atlasLights(id, clipT) {
  const m = meta(id), bmp = get(id, 'light', clipT); if (!bmp) return null;
  const key = url(id, 'light', frameIndex(m, clipT));
  if (atlasCache.has(key)) return atlasCache.get(key);
  const c = document.createElement('canvas'); c.width = 480; c.height = 270; const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(bmp, 0, 0); const L = g.getImageData(0, 0, 480, 270).data; g.clearRect(0, 0, 480, 270); g.drawImage(bmp, -480, 0); const Rt = g.getImageData(0, 0, 480, 270).data;
  const out = g.createImageData(480, 270), d = out.data;
  for (let i = 0; i < d.length; i += 4) {
    const r = L[i] / 255, so = L[i + 1] / 255, b = L[i + 2] / 255, w = Rt[i] / 255;
    const a = Math.min(1, r + so + b + w); if (a < 0.02) continue;
    d[i] = Math.min(255, (LCOL.red[0] * r + LCOL.sodium[0] * so + LCOL.blue[0] * b + LCOL.white[0] * w) / a);
    d[i + 1] = Math.min(255, (LCOL.red[1] * r + LCOL.sodium[1] * so + LCOL.blue[1] * b + LCOL.white[1] * w) / a);
    d[i + 2] = Math.min(255, (LCOL.red[2] * r + LCOL.sodium[2] * so + LCOL.blue[2] * b + LCOL.white[2] * w) / a);
    d[i + 3] = clamp((a - 0.3) / 0.45) * 190;   // only real lights survive (flat, no photographic texture)
  }
  g.clearRect(0, 0, 480, 270); g.putImageData(out, 0, 0);
  const c2 = document.createElement('canvas'); c2.width = 160; c2.height = 90; { const g2 = c2.getContext('2d'); g2.filter = 'blur(3px)'; g2.drawImage(c, 0, 0, 160, 90); g2.filter = 'none';   // flat soft discs, no source pixels
    }
  atlasCache.set(key, c2); if (atlasCache.size > 60) atlasCache.delete(atlasCache.keys().next().value);
  return c2;
}
export function lights(g, id, clipT, o = {}) {
  const m = meta(id); if (!m) return false;
  let bmp = null;
  if (m.layers.includes('lights')) bmp = get(id, 'lights', clipT);
  else if (m.layers.includes('light')) bmp = atlasLights(id, clipT);
  if (!bmp) return false;
  g.save(); g.globalCompositeOperation = o.comp || 'lighter'; g.globalAlpha = clamp(o.alpha ?? 1);
  if (m.layers.includes('lights')) { g.filter = 'blur(3px)'; g.globalAlpha *= 0.8; }   // flat soft light shapes: no plate pixels
  place(g, bmp, o.rect, o.boil != null ? jitter(o.boil, 0.4) : null);
  g.restore(); return true;
}
// clip time for a shot-local time: speed, offset, loop / ping-pong / hold
export function clipTime(id, lt, o = {}) {
  const m = meta(id); if (!m) return 0;
  const dur = m.frames / m.fps; let x = lt * (o.speed ?? 1) + (o.offset ?? 0);
  if (o.loop === 'pingpong') { const p = x % (2 * dur); x = p < dur ? p : 2 * dur - p; }
  else if (o.loop) x = ((x % dur) + dur) % dur;
  return Math.max(0, Math.min(dur - 1e-3, x));
}
