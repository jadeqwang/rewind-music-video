// tree: the search-tree HUD as hero. The engine expands the game tree breadth-first; every leaf of the attempt that
// just died is pruned in red; the surviving line is faintly lit (not yet found). ATTEMPT flips to the next.
// params: {seed, depth, labels:[{node,text,color}], dead (first-level node index of the failed attempt),
//          grow (s), attempt, flipAt (local s), lines (subtitle), eval}
import { DW, DH, PAL, clamp, lerp, smooth, easeOutCubic, rgba } from '../core.js';
import { buildTree, searchTree, cross, evalBar, attempt } from '../hud.js';
import { subtitle, setFont, F } from '../type.js';
import { fillInk } from '../fx.js';

const cache = new Map();
export function draw(ctx, lt, t, shot, { T }) {
  const { g, ty } = ctx, p = shot.params, dur = shot.t1 - shot.t0;
  fillInk(g);
  const key = `${p.seed}:${p.depth}`;
  if (!cache.has(key)) cache.set(key, buildTree(p.seed ?? 3, p.depth ?? 6, 3));
  const TR = cache.get(key);
  const prog = easeOutCubic(clamp(lt / (p.grow ?? 1.2)));
  const geo = { x: 330, y: 540, w: 1320, h: 800 };
  // pruned subtree of the failed attempt, in red, under the main tree
  const { P } = searchTree(g, TR, { ...geo, progress: prog, lit: 0.35 * smooth(0.8, 1.4, lt), labels: p.labels, labelSize: p.labelSize, alpha: 1 });
  if (p.dead != null) {
    const dn = TR.nodes[p.dead], a = P(TR.nodes[0]), b = P(dn);
    const u = smooth(0.25, 0.5, lt);
    g.save(); g.strokeStyle = rgba(PAL.red, 0.9 * u); g.lineWidth = 3;
    g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(lerp(a[0], b[0], u), lerp(a[1], b[1], u)); g.stroke(); g.restore();
    const st = smooth(0.45, 0.62, lt);
    if (st > 0) cross(g, b[0], b[1], 22 * (1 + 0.5 * (1 - st)), PAL.red, 6, st);
  }
  // the header line of the engine: mono, small
  setFont(ty, F.mono(15), 2.5); ty.fillStyle = rgba(PAL.boneDim, 0.9);
  const nodes = Math.floor(TR.nodes.length * prog * 37.3);
  ty.fillText(`SEARCH  depth ${p.depth ?? 6}   nodes ${nodes.toLocaleString('en-US')}   pruned ${Math.floor(nodes * 0.93).toLocaleString('en-US')}`, 330, 96);
  if (p.eval) evalBar(ty, { value: lt < (p.flipAt ?? dur) ? -9.9 : p.eval[1], mate: lt < (p.flipAt ?? dur) ? -1 : null });
  const flipped = lt >= (p.flipAt ?? dur);
  attempt(ty, { n: flipped ? (p.attempt ?? 1) + 1 : (p.attempt ?? 1), failed: flipped ? 0 : 1, sub: flipped ? 'RELOADING' : 'TERMINATED' });
  if (p.lines) subtitle(ty, [].concat(...p.lines.map(i => T.lineWords(i))), t, { y: 1010, size: 26 });
  ctx.post.bloom = 0.6; ctx.post.ca = 0.8; if (flipped && lt - (p.flipAt ?? dur) < 2 / 30) ctx.post.flash = 0.25;
}
