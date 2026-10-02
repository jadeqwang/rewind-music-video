// slam: drop typography — a massive condensed word re-slammed on each sung hit, with stutter plates.
// params: {hits:[{t, text, style: 'ink'|'flood'|'outline', color}], font}
import { DW, DH, PAL, clamp, smooth, hash, hsig } from '../core.js';
import { slam } from '../type.js';
import { fillInk } from '../fx.js';

export function draw(ctx, lt, t, shot, { T }) {
  const { g, ty } = ctx, p = shot.params;
  const hits = p.hits.filter(h => h.t <= t + 1e-6);
  const h = hits[hits.length - 1] || p.hits[0], k = Math.max(0, hits.length - 1);
  const dt = Math.max(0, t - h.t);
  fillInk(g, h.style === 'flood' ? PAL.red : PAL.ink);
  // a single hairline horizon under the word anchors it to the road
  g.fillStyle = h.style === 'flood' ? 'rgba(7,8,10,0.6)' : 'rgba(236,230,216,0.18)'; g.fillRect(0, 846, DW, 2);
  const col = h.style === 'flood' ? PAL.ink : (h.color || PAL.bone);
  // the type is part of the scene here (so it gets bloom + CA with the frame)
  slam(g, { t, t0: h.t, text: h.text, color: col, stutter: 1, seed: k + 1, maxW: 1780, maxH: 700, y: 830, font: p.font,
    plates: h.style === 'flood' ? [PAL.blue, PAL.bone] : [PAL.red, PAL.blue] });
  const kick = Math.exp(-dt / 0.09);
  const P = ctx.post;
  P.zoom = 1 + 0.045 * kick; P.shakeX = hsig(k, Math.floor(dt * 30)) * 10 * kick; P.shakeY = hsig(k, Math.floor(dt * 30), 2) * 6 * kick;
  P.ca = 1.5 + 5 * kick; P.bloom = h.style === 'flood' ? 0 : 0.22; P.bloomThr = 0.7; P.invert = (h.style === 'outline' && dt < 2 / 30) ? 1 : 0; P.grain = 0.05;
}
