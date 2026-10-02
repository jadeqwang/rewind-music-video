// rhythm.js: the global energy/dream layer applied on top of every shot's post settings.
// shot.fx = { heart (vignette pulse amount, default .18), kick (zoom/CA punch on kicks, drops), strobe (flash on kicks),
//             soft (soft-focus that snaps sharp on each beat), blinks: [{t, skip}] (microsleep eyelid wipes; skip = seconds of
//             dropped time after reopening), jerks: [t] (hypnagogic 1-frame vertical jolt + flash), speed (speed-line amount) }
import { clamp, hash, hsig } from './core.js';

export function blinkAt(fx, t) {
  let b = 0;
  for (const k of fx.blinks || []) {
    const d = t - k.t, f = 1 / 30;
    if (d > -2 * f && d < 0) b = Math.max(b, (d + 2 * f) / (2 * f));
    else if (d >= 0 && d < f * (k.hold ?? 1)) b = 1;
    else if (d >= f * (k.hold ?? 1) && d < f * ((k.hold ?? 1) + 2)) b = Math.max(b, 1 - (d - f * (k.hold ?? 1)) / (2 * f));
  }
  return b;
}
// dropped time: after a blink the shot resumes `skip` seconds later
export function skipAt(fx, t) { let s = 0; for (const k of fx?.blinks || []) if (k.skip && t >= k.t + 1 / 30) s += k.skip; return s; }

export function applyRhythm(P, t, shot, T) {
  const fx = shot.fx || {};
  const b = T.beatPhase(t);
  const heart = fx.heart ?? 0.18;
  if (heart > 0) { const hp = Math.exp(-(t - b.t0) / 0.13) + 0.6 * Math.exp(-Math.max(0, t - b.t0 - 0.16) / 0.1) * (t - b.t0 > 0.16 ? 1 : 0); P.vignette = (P.vignette ?? 0.3) + heart * hp; }
  if (fx.kick) { const k = T.kick(t, 0.08); P.zoom = (P.zoom ?? 1) * (1 + 0.03 * fx.kick * k); P.ca = (P.ca ?? 0) + 3 * fx.kick * k; }
  if (fx.strobe) { const k = T.kick(t, 0.05); P.flash = Math.max(P.flash ?? 0, fx.strobe * 0.18 * k); if (fx.strobeColor) P.flashC = fx.strobeColor; }
  if (fx.soft) P.soft = Math.max(P.soft ?? 0, fx.soft * Math.pow(b.phase, 1.5));
  // bone-paper inversion on downbeats (every n-th): two frames of the hard two-tone print
  if (fx.downInvert) { const k = T.downbeatIndex(t); const d0 = T.downbeats[k]; if (k >= 0 && k % fx.downInvert === 0 && t - d0 < 2 / 30) P.invert = 1; }
  const bl = blinkAt(fx, t); if (bl > 0) P.blink = Math.max(P.blink ?? 0, bl);
  for (const j of fx.jerks || []) if (t >= j && t < j + 1 / 30) { P.shakeY = (P.shakeY ?? 0) + 46; P.flash = Math.max(P.flash ?? 0, 0.45); P.zoom = (P.zoom ?? 1) * 1.03; }
  return P;
}
