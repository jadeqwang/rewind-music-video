// suits: the approach. Siren floods alternate red/blue on the beat; the world is luminous contour lines;
// the agents are REDACTION — black cut-outs with a one-sided siren rim, FOIA face bars, a sunglasses glint.
// params: {roto, lines:[idx] (subtitle), eval:[v0,v1], mate (at end), attempt, move:{n,move,nag,at}, banner, freezeAt}
import { DW, DH, PAL, clamp, lerp, smooth, hash } from '../core.js';
import { subtitle } from '../type.js';
import { evalBar, attempt, annotation, foiaBanner } from '../hud.js';
import { sirens, fillInk } from '../fx.js';

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
    roto.suits(g, p.roto, clipT, { boil: null, glint: 0, barLabel: p.barLabel ?? '(b)(6)', labelColor: PAL.ink });
    return;
  }
  fillInk(g);
  const sr = sirens(g, T, ft, { amount: p.siren ?? 1, peak: 0.42 });
  roto.contours(g, p.roto, clipT, { color: PAL.bone, alpha: 0.55, boil: ctx.seed, exclude: p.roto, fog: { y0: 120, y1: 700, min: 0.25 } });
  const glintBeat = T.beatPhase(ft);
  const glint = (glintBeat.i % 4 === 1) ? Math.exp(-glintBeat.phase * 5) : 0;
  roto.suits(g, p.roto, clipT, { boil: ctx.seed, rimL: sr.red ? PAL.red : null, rimR: sr.red ? null : PAL.blue, rimAmt: clamp(0.35 + sr.k * 1.6),
    glint: p.glint ?? glint, glintSeed: glintBeat.i, barLabel: p.barLabel ?? '(b)(6)' });
  if (ctx.rewinding) return;   // the rewind owns the HUD and the subtitle
  // HUD
  const u = smooth(0, dur, fl);
  if (p.eval) evalBar(ty, p.mate != null && fl >= dur - 0.05 ? { mate: p.mate } : { value: lerp(p.eval[0], p.eval[1], u * u) });
  if (p.attempt) attempt(ty, { n: p.attempt });
  if (p.move && t >= shot.t0 + (p.move.at ?? 0)) annotation(ty, { ...p.move, x: 96, y: 1000, alpha: smooth(p.move.at ?? 0, (p.move.at ?? 0) + 0.2, lt) });
  if (p.banner) foiaBanner(ty, { text: p.banner, case: p.caseNo, page: p.pageNo, alpha: 0.9 });
  subtitle(ty, [].concat(...(p.lines || []).map(i => T.lineWords(i))), ft, { y: 1000, size: 28 });
  ctx.post.bloom = 0.75; ctx.post.ca = 1.0 + sr.k * 2; ctx.post.zoom = 1 + 0.006 * T.pulse(ft, 0.1);
}
