// slam: drop typography. Each hit picks a designed variant (slams.js) or the restrained centred slam (type.js, keep it
// for the single biggest moment). params: {hits:[{t, text, variant: 'center'|'behind'|'mirror'|'bars'|'stack',
// style ('ink'|'flood' for center), code}], roto (subject for 'behind')}
import { DW, DH, PAL, clamp, smooth, hash, hsig } from '../core.js';
import { slam } from '../type.js';
import * as V from '../slams.js';
import { fillInk, sirens, headlights } from '../fx.js';

export function draw(ctx, lt, t, shot, { T, roto }) {
  const { g, ty } = ctx, p = shot.params;
  const hits = p.hits.filter(h => h.t <= t + 1e-6);
  const h = hits[hits.length - 1] || p.hits[0], k = Math.max(0, hits.length - 1);
  const dt = Math.max(0, t - h.t), v = h.variant || 'center';
  const kk = T.kick(t, 0.07), kb = T.beatPhase(t);
  const P = ctx.post;
  P.bloom = 0.15; P.bloomThr = 0.75; P.grain = 0.05; P.ca = 1.2;
  if (v === 'behind') {
    fillInk(g);
    sirens(g, T, t, { amount: 1, peak: 0.55, side: 'pair', base: 0.5, decay: 1.6 });
    headlights(g, DW / 2, 480, 1100, 0.35);
    V.behind(g, { t, t0: h.t, text: h.text, y: 600, color: PAL.bone }, gg => {
      const r = p.roto || 'ld_suits', m = roto.meta(r);
      roto.suits(gg, r, (m ? (m.frames - 1) / m.fps : 3) - 0.6 + Math.min(dt, 0.6) * 0.5, { boil: ctx.seed, rimL: PAL.red, rimR: PAL.blue, rimAmt: 1, glint: Math.exp(-dt / 0.2), glintSeed: k });
    });
  } else if (v === 'mirror') {
    fillInk(g); V.mirror(g, { t, t0: h.t, text: h.text, color: PAL.bone, mirrorColor: PAL.cyan });
    P.bloom = 0.35; P.bloomThr = 0.5;
  } else if (v === 'bars') {
    fillInk(g, PAL.bone); V.bars(g, { t, t0: h.t, text: h.text, code: h.code });
    P.vignette = 0.12; P.bloom = 0;
  } else if (v === 'stack') {
    fillInk(g); V.stack(g, { t, t0: h.t, text: h.text, color: PAL.bone });
  } else {
    fillInk(g, h.style === 'flood' ? PAL.red : PAL.ink);
    if (h.style !== 'flood' && kk > 0.05) { g.fillStyle = kb.i % 2 ? `rgba(47,91,255,${0.22 * kk})` : `rgba(255,42,42,${0.22 * kk})`; g.fillRect(0, 0, DW, DH); }
    g.fillStyle = h.style === 'flood' ? 'rgba(7,8,10,0.6)' : 'rgba(236,230,216,0.18)'; g.fillRect(0, 846, DW, 2);
    const kickFrame = kk > 0.62 && dt > 0.2;
    slam(g, { t, t0: kickFrame ? t : h.t, creepFrom: h.t, text: h.text, color: h.style === 'flood' ? PAL.ink : PAL.bone, stutter: kickFrame ? 0.35 : 1,
      seed: k + 1 + kb.i * 7, maxW: 1780, maxH: 700, y: 830, font: p.font, ...(kickFrame ? { plates: false } : { plates: h.style === 'flood' ? [PAL.ink, PAL.ink] : [PAL.red, PAL.blue] }) });
    if (h.style === 'flood') P.bloom = 0;
  }
  const kick = Math.max(Math.exp(-dt / 0.09), kk * 0.45);
  P.zoom = 1 + 0.04 * kick; P.shakeX = hsig(k, Math.floor(dt * 30)) * 9 * kick; P.shakeY = hsig(k, Math.floor(dt * 30), 2) * 5 * kick;
  P.ca += 4 * kick;
}
