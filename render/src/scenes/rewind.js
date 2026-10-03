// rewind: THE signature effect. freeze → negative/cyan grade → the previous seconds play backwards (re-rendered:
// every frame is a pure function of t) with motion-echo ghosts, ripple/warp, tape warble + tracking band,
// timecode running backwards, ◀◀ ×2 ×4 ×8 badge.
// params: {from (source time to start from, default shot.t0), to (earliest source time), source (shot id | null = any),
//          speeds [2,4,8], segs [fractions of the rewind time], hold (s of frozen negative before it moves), lines (subtitle)}
import { DW, DH, PAL, clamp, lerp, smooth, hash, easeInCubic, layer, clearLayer, resetCtx } from '../core.js';
import { drawLayers } from '../layers.js';
import { rewindHud } from '../hud.js';
import { subtitle, setFont, F } from '../type.js';

const LOCAL0 = 23 * 3600 + 41 * 60 + 7;   // 23:41:07 local (the incident, COPY_v9)
export const noRewind = true;
const hexRGB = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];

// map local time → source-progress with stepped speeds (each segment plays at its nominal speed, scaled to land on `to`)
export function schedule(lt, dur, p) {
  const speeds = p.speeds || [2, 4, 8], segs = p.segs || [0.3, 0.33, 0.37], hold = p.hold ?? 0.1;
  const run = Math.max(1e-3, dur - hold), u = clamp((lt - hold) / run);
  let acc = 0, total = 0, at = 0, sp = speeds[0];
  for (let i = 0; i < speeds.length; i++) total += segs[i] * speeds[i];
  for (let i = 0; i < speeds.length; i++) {
    const a = segs.slice(0, i).reduce((x, y) => x + y, 0), b = a + segs[i];
    if (u >= b) acc += segs[i] * speeds[i]; else if (u > a) { acc += (u - a) * speeds[i]; sp = speeds[i]; break; } else break;
    sp = speeds[Math.min(i + 1, speeds.length - 1)];
  }
  return { progress: acc / total, speed: lt < hold ? 1 : sp, moving: lt >= hold };
}

function speedChangeFrames(dur, p) {
  const segs = p.segs || [0.3, 0.33, 0.37], hold = p.hold ?? 0.1, run = dur - hold; let a = 0; const r = [];
  for (let i = 0; i < segs.length - 1; i++) { a += segs[i]; r.push(Math.floor((hold + a * run) * 30 + 1e-3)); }
  return r;
}

export async function draw(ctx, lt, t, shot, data) {
  const { T, rewindOf } = data;
  const { g, ty } = ctx, p = shot.params, dur = shot.t1 - shot.t0;
  const from = p.from ?? shot.t0, to = p.to;
  // kickStep: the rewind stutter-jumps one step per kick (time only advances on the four-on-the-floor)
  let lts = lt;
  if (p.kickStep) { const k = T.kicks.filter(x => x > shot.t0 - 1e-3 && x <= t + 1e-6); lts = k.length ? k[k.length - 1] - shot.t0 + 0.08 * k.length : 0; }
  const s = schedule(lts, dur, p);
  g.fillStyle = PAL.ink; g.fillRect(0, 0, DW, DH);
  const echo = p.echo ?? (s.moving ? 3 : 0);
  const ts = await rewindOf(ctx, p.source ?? null, from, to, s.progress, { echo, echoDt: 0.07 * s.speed, echoAlpha: 0.5, noType: true });
  if (p.overlay) {   // a second attempt rewinding at the same time, in its own colour (kept crisp on the type layer)
    const O = layer('rw_overlay', g.canvas.width, g.canvas.height), og = clearLayer(O); og.setTransform(ctx.S, 0, 0, ctx.S, 0, 0);
    await rewindOf({ ...ctx, g: og }, null, p.overlay.from, p.overlay.to, s.progress, { echo: 0, noType: true });
    resetCtx(og);
    // luminance → alpha at quarter res, tinted: only the overlay's lines/lights survive, in their own colour
    const Q = layer('rw_overlay_q', 480, 270), qg = clearLayer(Q); qg.drawImage(O, 0, 0, 480, 270);
    const id = qg.getImageData(0, 0, 480, 270), d = id.data, [cr, cg, cb] = hexRGB(p.overlay.color || PAL.red);
    for (let i = 0; i < d.length; i += 4) { const l = (d[i] * 0.3 + d[i + 1] * 0.59 + d[i + 2] * 0.11) / 255; d[i] = cr; d[i + 1] = cg; d[i + 2] = cb; d[i + 3] = Math.min(255, Math.max(0, (l - 0.12) * 1.6) * 255); }
    qg.putImageData(id, 0, 0);
    ty.save(); ty.setTransform(1, 0, 0, 1, 0, 0); ty.globalAlpha = p.overlay.alpha ?? 0.6; ty.drawImage(Q, 0, 0, ty.canvas.width, ty.canvas.height); ty.restore();
  }
  rewindHud(ty, { speed: p.badge ?? s.speed, tc: LOCAL0 + ts, alpha: 1 });   // local clock base: never near 00:00
  // a thin progress rail along the bottom: the scrub position over the rewound span
  ty.fillStyle = 'rgba(61,242,230,0.35)'; ty.fillRect(90, 1052, DW - 180, 4);
  ty.fillStyle = PAL.cyan; ty.fillRect(90 + (DW - 180) * (1 - s.progress) - 4, 1040, 8, 28);
  if (p.lines) subtitle(ty, [].concat(...p.lines.map(i => T.lineWords(i))).filter(w => w.start < shot.t1), t, { y: 1000, lit: PAL.cyan, color: PAL.cyan });
  if (p.layers) await drawLayers(ctx, p.layers, { lt, t, dur, u: clamp(lt / dur), T, k: T.kick(t, 0.08), b: T.beatPhase(t), shot, ctx }, data);
  const P = ctx.post;
  // cyan positive grade throughout; true negative on the freeze-break and on every speed change (2 frames)
  const f = Math.floor(lt * 30 + 1e-3), sc = speedChangeFrames(dur, p);
  P.cyanGrade = 1;
  P.neg = (f < 3 || sc.some(c => f >= c && f < c + 2)) ? 1 : 0;
  P.flash = lt < 1 / 30 ? 0.6 : 0; P.flashC = [0.24, 0.95, 0.9];
  P.warble = 0.6 + 0.6 * (s.speed / 8); P.warbleSeed = Math.floor(lt * 30); P.tracking = 0.5 + 0.5 * hash(Math.floor(lt * 30), 5);
  P.scan = 0.55; P.ripple = lerp(1.0, 0.25, smooth(0, 0.6, lt)); P.ripplePhase = lt * 14;
  P.ca = 2.5 + s.speed * 0.3; P.bloom = 0.6; P.bloomThr = 0.5; P.grain = 0.06; P.vignette = 0.45;
}
