// engine.js: boot, shot dispatch, deterministic renderAt(t), rewindOf(), contact sheets.
//
//   scene module: export function draw(ctx, localT, globalT, shot, data)  (may be async)
//     ctx  = { g (scene Canvas2D, design px), ty (type/HUD Canvas2D), post (object the scene fills), boil (drawing index,
//              15/s, restarts per shot), seed (boil seed), W, H, rewinding (bool: drawn inside a rewind), engine }
//     data = { T (TimeMap), roto (roto.js module), shots, SCENES }
//   shot = { id, t0, t1, scene, params }  — times come from the TimeMap (see shots.js)
import { DW, DH, PAL, FPS, BOIL_FPS, clamp, fin, hash, layer, clearLayer, resetCtx, rgb } from './core.js';
import { TimeMap } from './timing.js';
import { Post } from './post.js';
import * as roto from './roto.js';
import { loadFonts } from './type.js';
import { SCENES } from './scenes/index.js';
import { applyRhythm, skipAt } from './rhythm.js';
import { hudOverlay } from './hud.js';
import { drawLayers } from './layers.js';
import * as CAR from './car.js';

const Q = new URLSearchParams(location.search);
export const W = +(Q.get('w') || 1920), H = +(Q.get('h') || 1080), S = H / DH;

const E = { T: null, shots: [], post: null, scene: null, type: null, out: null, ready: false };
window.E = E;

function mkCanvas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }

export function shotAt(t, exclude = null) {
  let r = null;
  for (const s of E.shots) if (t >= s.t0 - 1e-9 && t < s.t1 - 1e-9 && s !== exclude) r = s;
  if (!r && E.shots.length) { const last = E.shots[E.shots.length - 1]; if (t >= last.t1) r = last; else if (t < E.shots[0].t0) r = E.shots[0]; }
  return r;
}
export const shotById = id => E.shots.find(s => s.id === id);

function defaultPost(shot) {
  return { bloom: 0.3, bloomThr: 0.8, grain: 0.045, grainSeed: hash(shot.id) * 1000, vignette: 0.3, ca: 0.6, typeCA: 0.35,
    inkC: rgb(PAL.ink), boneC: rgb(PAL.bone), cyanC: rgb(PAL.cyan), flashC: rgb(PAL.bone), ...(shot.post || {}) };
}

// Draw one shot at global time t into the given layers. Used for the main pass and for rewind re-renders.
export async function drawShot(shot, t, g, ty, post, opts = {}) {
  const tReal = t;
  t = t + skipAt(shot.fx, t);           // microsleep: dropped time after a blink
  const lt = t - shot.t0;
  const boil = Math.floor(Math.max(0, lt) * BOIL_FPS + 1e-6);
  const ctx = { g, ty, post, boil, seed: hash(shot.id, boil), W: DW, H: DH, rewinding: !!opts.rewinding, mode: opts.mode || null, engine: E, S, shot };
  const sc = SCENES[shot.scene];
  if (!sc) throw new Error(`unknown scene ${shot.scene} (shot ${shot.id})`);
  g.save(); ty.save();
  const data = { T: E.T, roto, shots: E.shots, SCENES, shotById, shotAt, drawShot, rewindOf };
  await sc.draw(ctx, lt, t, shot, data);
  g.restore(); ty.restore();
  // params.over: extra layers drawn over any scene (comp-style)
  if (shot.params.over && !(opts.rewinding && shot.params.overNoRewind)) {
    resetCtx(g); resetCtx(ty); g.setTransform(S, 0, 0, S, 0, 0); ty.setTransform(S, 0, 0, S, 0, 0);
    const dur = shot.t1 - shot.t0;
    await drawLayers(ctx, shot.params.over, { lt, t, dur, u: clamp(lt / dur), T: E.T, k: E.T.kick(t, 0.08), b: E.T.beatPhase(t), shot, ctx }, data);
  }
  resetCtx(ty); ty.setTransform(S, 0, 0, S, 0, 0);
  if (shot.hud && !opts.rewinding && !opts.noHud) hudOverlay(ty, tReal, shot, E.T);
  if (!opts.rewinding && post && post !== true && !opts.noRhythm) applyRhythm(post, tReal, shot, E.T);
  resetCtx(g); resetCtx(ty); g.setTransform(S, 0, 0, S, 0, 0); ty.setTransform(S, 0, 0, S, 0, 0);
}

function beginLayer(c) { const g = c.getContext('2d'); resetCtx(g); g.clearRect(0, 0, c.width, c.height); g.setTransform(S, 0, 0, S, 0, 0); return g; }

// rewindOf(shotId, fromT, toT, progress): the earlier shot re-rendered at reversed time
//   ts = fromT + (toT - fromT) * progress   (fromT > toT; progress may already be eased by the caller)
// drawn with motion-echo ghosts (the frames it just came from, i.e. later source times) into ctx.g.
// If shotId is null the shot covering each source time is used, so a rewind can cross several earlier shots.
// opts: {echo: n ghosts, echoDt: source seconds between ghosts, echoAlpha}
export async function rewindOf(ctx, shotId, fromT, toT, progress, opts = {}) {
  const ts = fromT + (toT - fromT) * clamp(progress);
  const n = opts.echo ?? 3, dt = opts.echoDt ?? 0.18, a0 = opts.echoAlpha ?? 0.42;
  const pick = tt => {
    if (shotId) return shotById(shotId);
    let sh = shotAt(tt, ctx.shot), guard = 0;
    while (sh && (SCENES[sh.scene]?.noRewind || sh.params.isRewind) && guard++ < 12) sh = shotAt(sh.t0 - 1e-3, ctx.shot);   // skip other rewinds
    return sh;
  };
  const L = layer('rw_scene', W, H), LT = layer('rw_type', W, H);
  const dummy = {};
  // current frame first (opaque), then the motion-echo ghosts screened over it (they must not wash the frame out)
  const order = [0]; for (let k = 1; k <= n; k++) order.push(k);
  for (const k of order) {
    let tk = Math.min(fromT - 1e-4, ts + k * dt * Math.sign(fromT - toT || 1));
    const sh = pick(tk); if (!sh || SCENES[sh.scene]?.noRewind || sh.params.isRewind) continue;
    if (tk >= sh.t1) tk = sh.t1 - 1 / 30;
    const g = beginLayer(L), ty = beginLayer(LT);
    await drawShot(sh, tk, g, ty, dummy, { rewinding: true });
    resetCtx(g); g.drawImage(LT, 0, 0);
    const c = ctx.g; c.save(); c.setTransform(1, 0, 0, 1, 0, 0);
    c.globalAlpha = k === 0 ? 1 : a0 * 0.6 * (1 - (k - 1) / n);
    c.globalCompositeOperation = k === 0 ? 'source-over' : 'screen';
    c.drawImage(L, 0, 0); c.restore();
  }
  return ts;
}
E.rewindOf = rewindOf;

async function frame(t) {
  t = fin(t);
  const shot = shotAt(t);
  const g = beginLayer(E.scene), ty = beginLayer(E.type);
  if (!shot) { g.fillStyle = PAL.ink; g.fillRect(0, 0, DW, DH); E.post.render(E.scene, E.type, { bloom: 0 }, t); return null; }
  const post = defaultPost(shot);
  await drawShot(shot, t, g, ty, post);
  return { shot, post };
}

export async function renderFrame(t) {
  // miss-driven roto loading: draw, and if any roto frame wasn't cached, load the misses and draw again
  let r;
  for (let pass = 0; pass < 4; pass++) {
    r = await frame(t);
    if (!roto.misses.size) break;
    await roto.resolveMisses();
  }
  if (r) {
    E.post.render(E.scene, E.type, r.post, t);
    // background warm-up for the next frames of this shot (does not affect this frame's pixels)
    for (const id of (r.shot._rotos || [])) roto.prefetch(id, t - r.shot.t0 + (r.shot.params.rotoOffset || 0));
  }
  return r;
}

let chain = Promise.resolve();
const serial = fn => (chain = chain.then(fn, fn));
window.renderAt = (t, type = 'image/jpeg', q = 0.93) => serial(async () => { await renderFrame(t); return type ? E.out.toDataURL(type, q) : null; });
window.renderTimed = (t, type = 'image/jpeg', q = 0.93) => serial(async () => { const a = performance.now(); await renderFrame(t); const b = performance.now(); const url = E.out.toDataURL(type, q); return { url, ms: b - a, msEnc: performance.now() - b }; });
window.listShots = () => E.shots.map(s => ({ id: s.id, t0: s.t0, t1: s.t1, scene: s.scene }));
window.renderSheet = (times, cols = 4, w = 480) => serial(async () => {
  const h = Math.round(w * 9 / 16), rows = Math.ceil(times.length / cols), lab = 22;
  const C = mkCanvas(cols * w, rows * (h + lab)), g = C.getContext('2d');
  g.fillStyle = '#111'; g.fillRect(0, 0, C.width, C.height);
  const ms = [];
  for (let i = 0; i < times.length; i++) {
    const a = performance.now(); const r = await renderFrame(times[i]); ms.push(performance.now() - a);
    const x = (i % cols) * w, y = Math.floor(i / cols) * (h + lab);
    g.drawImage(E.out, x, y, w, h);
    g.fillStyle = '#bbb'; g.font = '13px monospace';
    g.fillText(`${times[i].toFixed(2)}s  ${r ? r.shot.id : '-'}  ${ms[i].toFixed(0)}ms`, x + 6, y + h + 15);
  }
  return { url: C.toDataURL('image/png'), ms };
});

// roto references: any value under a key named `roto`/`jade`/`world`/`matte` may be 'A|B|C' = first sequence that exists
// (e.g. 'B3|_auto/S1|ld_suits': the roto agent's shot, else the interim auto-roto of the base clip, else the stand-in).
const ROTO_KEYS = new Set(['roto', 'jade', 'world', 'subject']);
async function resolveRef(v) {
  for (const c of String(v).split('|')) if (await roto.loadMeta(c)) return c;
  return String(v).split('|').pop();
}
async function resolveRotos(o, acc = new Set()) {
  if (!o || typeof o !== 'object') return [...acc];
  for (const k of Object.keys(o)) {
    const v = o[k];
    if (ROTO_KEYS.has(k) && (typeof v === 'string' || Array.isArray(v))) {
      if (Array.isArray(v)) { for (let i = 0; i < v.length; i++) { v[i] = await resolveRef(v[i]); acc.add(v[i]); } }
      else { o[k] = await resolveRef(v); acc.add(o[k]); }
    } else if (typeof v === 'object') await resolveRotos(v, acc);
  }
  return [...acc];
}

export async function boot() {
  const which = Q.get('shots') || 'main';
  E.T = await TimeMap.load('..');
  await loadFonts();
  await CAR.load();
  const mod = await import(which === 'main' ? './shots.js' : `./shots.${which}.js`);
  E.shots = mod.buildShots(E.T).map(s => ({ params: {}, ...s, t0: fin(s.t0), t1: fin(s.t1) })).sort((a, b) => a.t0 - b.t0);
  const ids = new Set();
  for (const s of E.shots) {
    if (ids.has(s.id)) throw new Error('duplicate shot id ' + s.id); ids.add(s.id);
    if (!(s.t1 > s.t0)) throw new Error(`shot ${s.id} has t1 <= t0 (${s.t0}, ${s.t1})`);
    s._rotos = await resolveRotos(s.params);
  }
  E.scene = mkCanvas(W, H); E.type = mkCanvas(W, H);
  E.out = document.getElementById('out'); E.out.width = W; E.out.height = H;
  E.post = new Post(E.out, W, H);
  E.range = [E.shots[0]?.t0 ?? 0, E.shots[E.shots.length - 1]?.t1 ?? 0];
  window.timingInfo = { sources: E.T.sources, range: E.range, gl: E.post.info, shots: E.shots.length };
  E.ready = true; window.ready = true;
  return E;
}
