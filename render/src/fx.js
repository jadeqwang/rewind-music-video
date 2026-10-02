// fx.js: light and atmosphere — siren floods, sodium streetlight sweeps, the suspended bullet, rain, lane dashes.
// Light is the only colour: flat fills, composited additively onto ink.
import { DW, DH, PAL, clamp, lerp, inv, smooth, hash, hsig, rgba, fin } from './core.js';

// Siren floods: alternating red/blue half-frame washes on the beat (police light-bar logic), hard-edged with a
// soft falloff toward the centre. o: {amount, side ('split'|'full'), decay}
export function sirens(g, T, t, o = {}) {
  const b = T.beatPhase(t), amt = clamp(o.amount ?? 1);
  if (amt <= 0) return { color: null, k: 0 };
  const red = (b.i & 1) === 0, col = red ? PAL.red : PAL.blue;
  const k = amt * Math.exp(-b.phase * (o.decay ?? 2.2)) * (o.peak ?? 0.55);
  g.save(); g.globalCompositeOperation = 'lighter';
  if (o.side === 'full') { g.fillStyle = rgba(col, k); g.fillRect(0, 0, DW, DH); }
  else {
    const left = red, x0 = left ? 0 : DW, x1 = DW / 2;
    const gr = g.createLinearGradient(x0, 0, x1 + (left ? 260 : -260), 0);
    gr.addColorStop(0, rgba(col, k)); gr.addColorStop(0.55, rgba(col, k * 0.75)); gr.addColorStop(1, rgba(col, 0));
    g.fillStyle = gr; g.fillRect(0, 0, DW, DH);
    // the far side keeps a faint residue of the other colour
    g.fillStyle = rgba(red ? PAL.blue : PAL.red, k * 0.12); g.fillRect(left ? DW / 2 : 0, 0, DW / 2, DH);
  }
  g.restore();
  return { color: col, k, red };
}

// Sodium streetlights sweeping past the car: a diagonal band of orange light every `period` s.
// Returns the band for reuse on figures ({from:[x0,y0,x1,y1], amount, color}).
export function sodiumSweep(t, o = {}) {
  const period = o.period ?? 0.92, ph = ((t + (o.offset ?? 0)) / period) % 1;
  const cx = lerp(DW * 1.25, -DW * 0.35, ph), w = o.width ?? 520, slope = o.slope ?? 0.35;
  return { from: [cx - w, -w * slope, cx + w, w * slope], amount: (o.amount ?? 0.5) * smooth(0, 0.15, ph) * (1 - smooth(0.85, 1, ph)), color: PAL.sodium, cx, ph };
}
export function sodiumWash(g, sw, alpha = 0.12) {
  if (!sw || sw.amount <= 0) return;
  g.save(); g.globalCompositeOperation = 'lighter';
  const gr = g.createLinearGradient(...sw.from);
  gr.addColorStop(0, rgba(PAL.sodium, 0)); gr.addColorStop(0.5, rgba(PAL.sodium, sw.amount * alpha)); gr.addColorStop(1, rgba(PAL.sodium, 0));
  g.fillStyle = gr; g.fillRect(0, 0, DW, DH); g.restore();
}

// The bullet, suspended: a hairline with a bright head and a tapered trail. o: {x, y, len, angle, u (flight 0..1)}
export function bullet(g, o) {
  const x = o.x, y = o.y, len = o.len ?? 900, ang = o.angle ?? 0;
  const col = o.color || PAL.bone;
  g.save(); g.translate(x, y); g.rotate(ang); g.globalCompositeOperation = o.comp || 'lighter';
  const gr = g.createLinearGradient(-len, 0, 0, 0);
  gr.addColorStop(0, rgba(col, 0)); gr.addColorStop(0.85, rgba(col, 0.55)); gr.addColorStop(1, rgba(col, 1));
  g.fillStyle = gr; g.fillRect(-len, -1.5, len, 3);
  g.fillStyle = col; g.beginPath(); g.ellipse(0, 0, 16, 4.5, 0, 0, Math.PI * 2); g.fill();
  // pressure rings around the slug (time is stopped: they hold still)
  g.strokeStyle = rgba(col, 0.45); g.lineWidth = 1.2;
  for (let k = 1; k <= 4; k++) { g.beginPath(); g.ellipse(-k * 34, 0, 6 + k * 3, 12 + k * 11, 0, -Math.PI / 2, Math.PI / 2); g.stroke(); }
  g.restore();
}

// rain on the windshield as short falling line segments (drawn per boil drawing, so it boils too)
export function rain(g, seed, t, o = {}) {
  const n = o.n ?? 140, a = o.alpha ?? 0.22;
  g.save(); g.strokeStyle = rgba(PAL.bone, a); g.lineWidth = 1;
  g.beginPath();
  for (let i = 0; i < n; i++) {
    const sp = 900 + hash(i, 3) * 900, x = hash(i, 1) * DW + Math.sin(t * .3 + i) * 4, y = ((hash(i, 2) * DH + t * sp) % (DH + 80)) - 40, l = 10 + hash(i, 4) * 22;
    g.moveTo(x, y); g.lineTo(x - l * 0.12, y + l);
  }
  g.stroke(); g.restore();
}

export function fillInk(g, col = PAL.ink) { g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-over'; g.fillStyle = col; g.fillRect(0, 0, g.canvas.width, g.canvas.height); g.restore(); }
