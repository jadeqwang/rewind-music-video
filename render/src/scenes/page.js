// page: a whispered-verse shot. The dissertation page is the frame: big CMU italic, word by word, in the left
// two-thirds; Jade (roto, bone cut-paper) in the right third at the wheel; sodium streetlights sweep across her;
// one or two quiet world contours. HUD: thin eval bar, ATTEMPT counter.
// params: {roto (jade id), world (roto id, optional), lines:[line idx] | words:[...], notes:{word: mark}, footnotes,
//          header, folio, eval:[v0,v1], attempt, worldAlpha}
import { DW, DH, PAL, clamp, lerp, inv, smooth } from '../core.js';
import { page as pageType } from '../type.js';
import { evalBar, attempt } from '../hud.js';
import { sodiumSweep, sodiumWash, fillInk, rain } from '../fx.js';

export function words(T, p) {
  let ws = p.words || [].concat(...(p.lines || []).map(i => T.lineWords(i)));
  return ws.map(w => ({ ...w, note: p.notes && p.notes[w.key] }));
}

export function draw(ctx, lt, t, shot, { T, roto }) {
  const { g, ty } = ctx, p = shot.params;
  fillInk(g);
  const dur = shot.t1 - shot.t0;
  // world: the lake horizon (one contour) and the road, very low, fogged to nothing at the horizon
  g.save(); g.globalCompositeOperation = 'lighter';
  g.fillStyle = 'rgba(236,230,216,0.10)'; g.fillRect(0, 610, DW, 1);
  g.restore();
  if (p.world) roto.contours(g, p.world, lt + (p.worldOffset || 0), { color: PAL.boneDim, alpha: p.worldAlpha ?? 0.22, boil: ctx.seed, fog: { y0: 560, y1: 1080, min: 0 } });
  rain(g, ctx.boil, t, { n: 70, alpha: 0.07 });
  const sw = sodiumSweep(t, { period: p.sweep ?? 1.1, amount: 0.32 });
  sodiumWash(g, sw, 0.07);
  // Jade
  const mouth = clamp((T.e('vocal', t) - 0.18) * 1.6);
  // in a rewind she is a past attempt: outline only (the Braid shadow)
  roto.jade(g, p.jade ?? [].concat(p.roto)[0], lt + (p.rotoOffset || 0), ctx.rewinding
    ? { boil: ctx.seed, ghost: true, ghostColor: PAL.bone }
    : { boil: ctx.seed, mouth, light: sw, rim: { color: PAL.bone, alpha: 0.55, w: 1.4 } });
  // type: the page
  const ws = words(T, p);
  const fns = (p.footnotes || []).map(f => ({ ...f, at: f.at ?? (ws.find(w => w.key === f.word)?.start ?? 0) }));
  pageType(ty, ws, t, { x: p.x ?? 150, y: p.y ?? 420, w: p.measure ?? 1060, size: p.size ?? 140, maxLines: p.maxLines ?? 3, header: p.header, folio: p.folio,
    footnotes: fns, furniture: smooth(0, 0.4, lt) });
  if (ctx.rewinding) return;   // the rewind owns the HUD
  // HUD (quiet)
  if (p.eval) evalBar(ty, { value: lerp(p.eval[0], p.eval[1], smooth(0, dur, lt)), alpha: 0.9 });
  ctx.post.bloom = 0.35; ctx.post.bloomThr = 0.8; ctx.post.ca = 0.5;
}
