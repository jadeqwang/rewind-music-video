// suits: the approach. Siren floods alternate red/blue on the beat; the world is luminous contour lines;
// the agents are REDACTION — black cut-outs with a one-sided siren rim, redaction face bars, a sunglasses glint.
// params: {roto, lines:[idx] (subtitle), eval:[v0,v1], mate (at end), attempt, move:{n,move,nag,at}, banner, freezeAt}
import { DW, DH, PAL, clamp, lerp, smooth, hash } from '../core.js';
import { subtitle } from '../type.js';
import { evalBar, attempt, annotation, agencyBanner } from '../hud.js';
import { sirens, fillInk, headlights } from '../fx.js';

export function draw(ctx, lt, t, shot, { T, roto }) {
  const { g, ty } = ctx, p = shot.params, dur = shot.t1 - shot.t0;
  // a frozen shot passes freezeAt (local seconds): everything stops, including the boil
  const fl = p.freezeAt != null ? Math.min(lt, p.freezeAt) : lt;
  const ft = shot.t0 + fl;
  const clipT = fl + (p.rotoOffset || 0);
  if (ctx.mode === 'print') {
    // the file photo: bone stock, ink contours, black redactions (used by the freeze)
    fillInk(g, PAL.bone);
    roto.contours(g, p.roto, clipT, { color: PAL.ink, alpha: 0.85, boil: null, boilAmp: 0, exclude: p.roto, comp: 'source-over' });
    roto.suits(g, p.roto, clipT, { boil: null, glint: 0, barLabel: null });
    return;
  }
  fillInk(g);
  // contrast rule: the black cut-outs always sit against light (siren pair + headlight bloom behind the heads)
  const sr = sirens(g, T, ft, { amount: p.siren ?? 1, peak: 0.5, side: 'pair', base: 0.42, decay: 1.6 });
  headlights(g, DW / 2, 470, 1100, 0.3 + 0.08 * T.pulse(ft, 0.12), PAL.bone);
  roto.contours(g, p.roto, clipT, { color: PAL.ink, alpha: 0.5, boil: ctx.seed, exclude: p.roto, comp: 'source-over' });
  const glintBeat = T.beatPhase(ft);
  const glint = (glintBeat.i % 4 === 1) ? Math.exp(-glintBeat.phase * 5) : 0;
  roto.suits(g, p.roto, clipT, { boil: ctx.seed, rimL: PAL.red, rimR: PAL.blue, rimAmt: 1,
    glint: p.glint ?? glint, glintSeed: glintBeat.i, barLabel: null });
  if (ctx.rewinding) return;   // the rewind owns the HUD and the subtitle
  // HUD
  const u = smooth(0, dur, fl);
  if (p.eval) evalBar(ty, p.mate != null && fl >= dur - 0.05 ? { mate: p.mate } : { value: lerp(p.eval[0], p.eval[1], u * u) });
  if (p.attempt) attempt(ty, { n: p.attempt });
  if (p.move && t >= shot.t0 + (p.move.at ?? 0)) annotation(ty, { ...p.move, x: 110, y: 1010, alpha: smooth(p.move.at ?? 0, (p.move.at ?? 0) + 0.2, lt) });
  subtitle(ty, [].concat(...(p.lines || []).map(i => T.lineWords(i))).filter(w => w.start < shot.t1 + 0.01), ft, { y: 1010, x: 1180 });
  ctx.post.bloom = 0.45; ctx.post.bloomThr = 0.6; ctx.post.ca = 1.0 + sr.k * 2; ctx.post.zoom = 1 + 0.006 * T.pulse(ft, 0.1);
}
