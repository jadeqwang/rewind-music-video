// car.js: her car, a white 2001 Acura TL, drawn from the assets/car kit (6 views of unit-box polylines + clip tracks).
// The Seedance car is erased (dilated track bbox filled with ink) and ours is drawn on top: steady body silhouette,
// lighter boil on detail strokes, siren-red tail lights with glow, cold-white headlights.
import { DW, DH, PAL, clamp, hash, hsig, rgba } from './core.js';

const ROOT = '../assets/car';
const VIEWS = ['chase', 'rear34', 'rear', 'side', 'front34', 'top'];
const K = { views: {}, tracks: {} };

export async function load() {
  await Promise.all(VIEWS.map(async v => { try { const r = await fetch(`${ROOT}/${v}/contours.json`); if (r.ok) K.views[v] = await r.json(); } catch (e) { /* kit missing */ } }));
  await Promise.all(['E1', 'Epull'].map(async c => { try { const r = await fetch(`${ROOT}/tracks/${c}.json`); if (r.ok) K.tracks[c] = await r.json(); } catch (e) { /* none */ } }));
  return K;
}
export const has = v => !!K.views[v];
export function trackFor(rotoId) { const base = String(rotoId || '').replace(/^_auto\//, '').replace(/^plate_.*/, ''); return K.tracks[base] || null; }

// bbox (design px) of the tracked car at clip time ct, mapped through the world's camera rect (source 1280x720)
export function trackBox(track, ct, rect) {
  const fr = track.frames, f = Math.max(0, Math.min(fr.length - 1, Math.round(ct * (track.fps || 24))));
  let e = fr[f]; if (!e || !e.visible) return null;
  const [sw, sh] = track.size || [1280, 720], b = e.bbox.slice();
  if (track === K.tracks.Epull && f <= 20) { b[1] -= 40; b[3] -= 40; }   // known lock on the wet-road reflection
  return { x0: rect.x + b[0] / sw * rect.w, y0: rect.y + b[1] / sh * rect.h, x1: rect.x + b[2] / sw * rect.w, y1: rect.y + b[3] / sh * rect.h };
}

// draw a view so its extent fits width w, bottom-centre at (cx, by). o: {color, alpha, seed, outline (ghost), lights:'tail'|'head'|'brake'|null, rot, minimal, fill}
export function drawView(g, view, cx, by, w, o = {}) {
  const V = K.views[view]; if (!V) return false;
  const s = w / V.extent[0], ax = V.anchor_ground_center[0], ay = V.anchor_ground_center[1];
  const col = o.color || PAL.bone, a = o.alpha ?? 1, seed = o.seed ?? 0, minimal = o.minimal ?? (w < 90);
  g.save(); g.translate(cx, by); if (o.rot) g.rotate(o.rot); g.translate(-ax * s, -ay * s);
  g.lineJoin = 'round'; g.lineCap = 'round';
  const path = (pts, jit, k) => { g.beginPath(); pts.forEach((p, i) => { const jx = jit ? hsig(seed, k, i) * jit : 0, jy = jit ? hsig(seed, k, i, 7) * jit : 0; const x = p[0] * s + jx, y = p[1] * s + jy; i ? g.lineTo(x, y) : g.moveTo(x, y); }); };
  const F = V.features;
  // faint white-paint fill so the car reads as WHITE against the ink
  const body = F.find(f => f.type === 'body');
  if (body && o.erase) {   // erase the Seedance car under ours: the body silhouette, enlarged, filled with ink
    const cxu = V.extent[0] / 2 * s, cyu = V.extent[1] / 2 * s;
    g.save(); g.translate(cxu, cyu); g.scale(1.3, 1.35); g.translate(-cxu, -cyu); path(body.pts, 0, 0); g.closePath(); g.fillStyle = PAL.ink; g.shadowColor = PAL.ink; g.shadowBlur = w * 0.15; g.fill(); g.restore();
  }
  if (body && !o.outline) { path(body.pts, 0, 0); g.closePath(); g.fillStyle = rgba(col, (o.fill ?? 0.18) * a); g.fill(); }
  F.forEach((f, k) => {
    const t = f.type;
    if (minimal && !(t === 'body' || t === 'taillight' || t === 'window')) return;
    if (t === 'taillight' || t === 'headlight') {
      const lit = (t === 'taillight' && (o.lights === 'tail' || o.lights === 'brake')) || (t === 'headlight' && o.lights === 'head');
      path(f.pts, 0, k); if (f.closed) g.closePath();
      if (lit && !o.outline) {
        g.save(); g.fillStyle = t === 'taillight' ? PAL.red : '#F4F1EA'; g.shadowColor = g.fillStyle; g.shadowBlur = Math.max(6, w * 0.06) * (o.lights === 'brake' ? 1.6 : 1) * (w < 260 ? 2 : 1); g.globalAlpha = a; g.fill(); if (w < 260) { g.globalCompositeOperation = 'lighter'; g.globalAlpha = a * 0.6; g.fill(); } g.restore();
      } else { g.strokeStyle = rgba(o.outline ? col : (t === 'taillight' ? PAL.red : col), a); g.lineWidth = Math.max(1.5, w * 0.006); g.stroke(); }
      return;
    }
    const isDetail = t === 'detail' || t === 'lower_dark';
    path(f.pts, isDetail ? 0.6 : 0.15, k); if (f.closed) g.closePath();
    g.strokeStyle = rgba(col, a * (isDetail ? 0.5 : 1)); g.lineWidth = Math.max(2, w * (t === 'body' ? 0.014 : 0.008)) * (o.outline ? 1.2 : 1);
    g.stroke();
  });
  g.restore();
  return true;
}
