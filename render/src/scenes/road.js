// road: generic driving shot — luminous contours of a world roto, sodium sweeps, mono subtitle of the sung line(s).
// params: {roto (world id), lines:[idx], sirens (0..1), attempt}
import { PAL } from '../core.js';
import { subtitle } from '../type.js';
import { attempt } from '../hud.js';
import { sodiumSweep, sodiumWash, sirens, fillInk } from '../fx.js';
export function draw(ctx, lt, t, shot, { T, roto }) {
  const { g, ty } = ctx, p = shot.params;
  fillInk(g);
  if (p.sirens) sirens(g, T, t, { amount: p.sirens, peak: 0.3 });
  if (p.roto) roto.contours(g, p.roto, (lt + (p.rotoOffset || 0)) % 3.9, { color: PAL.bone, alpha: 0.75, boil: ctx.seed, fog: { y0: 380, y1: 900, min: 0.15 } });
  sodiumWash(g, sodiumSweep(t, { period: 0.8 }), 0.18);
  if (p.lines) subtitle(ty, [].concat(...p.lines.map(i => T.lineWords(i))), t, {});
  if (p.attempt) attempt(ty, { n: p.attempt, alpha: 0.8 });
}
