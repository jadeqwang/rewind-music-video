// core.js: math, easing, deterministic hashing/RNG/noise, palette, pooled canvases.
// Contract: nothing in the renderer may call Math.random() or Date; every value is a function of t (and seeds).

export const DW = 1920, DH = 1080;           // design resolution (all drawing is authored in these units)
export const FPS = 30;
export const BOIL_FPS = 15;                   // line boil "on twos" at 30 fps

export const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
export const lerp = (a, b, u) => a + (b - a) * u;
export const inv = (a, b, x) => clamp((x - a) / (b - a || 1e-9));
export const smooth = (a, b, x) => { const u = inv(a, b, x); return u * u * (3 - 2 * u); };
export const fract = x => x - Math.floor(x);
export const easeOutCubic = u => 1 - Math.pow(1 - clamp(u), 3);
export const easeInCubic = u => Math.pow(clamp(u), 3);
export const easeInOutCubic = u => { u = clamp(u); return u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; };
export const easeOutExpo = u => (u >= 1 ? 1 : 1 - Math.pow(2, -10 * clamp(u)));
export const easeInExpo = u => (u <= 0 ? 0 : Math.pow(2, 10 * clamp(u) - 10));
export const easeOutBack = (u, s = 1.7) => { u = clamp(u) - 1; return 1 + u * u * ((s + 1) * u + s); };
export const fin = (x, d = 0) => (Number.isFinite(x) ? x : d);   // NaN guard for anything that reaches canvas/GL

// ---- hashing / RNG (integer hash → [0,1)) ----
export function hashStr(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
export function hashU(...xs) {
  let h = 0x9e3779b9 | 0;
  for (const x0 of xs) {
    let x = typeof x0 === 'string' ? hashStr(x0) : (Math.floor(x0 * 1000) | 0);
    x = Math.imul(x ^ (x >>> 16), 0x85ebca6b); x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35); x ^= x >>> 16;
    h = Math.imul(h ^ x, 0x27d4eb2d); h ^= h >>> 15;
  }
  return (h >>> 0) / 4294967296;
}
export const hash = hashU;
export const hsig = (...xs) => hashU(...xs) * 2 - 1;      // [-1,1)
export function rng(seed) {                                // mulberry32
  let a = (typeof seed === 'string' ? hashStr(seed) : Math.floor(seed * 4294967296)) >>> 0;
  return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
export function noise1(x, seed = 0) { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hsig(i, seed), hsig(i + 1, seed), u); }
export function noise2(x, y, seed = 0) {
  const i = Math.floor(x), j = Math.floor(y), fx = x - i, fy = y - j, ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
  return lerp(lerp(hsig(i, j, seed), hsig(i + 1, j, seed), ux), lerp(hsig(i, j + 1, seed), hsig(i + 1, j + 1, seed), ux), uy);
}

// ---- palette: REDACTED NOCTURNE ----
export const PAL = {
  ink: '#07080A', black: '#000000', bone: '#ECE6D8', red: '#FF2A2A', blue: '#2F5BFF', sodium: '#FF9F1C',
  cyan: '#3DF2E6',            // rewind-cyan: reversed time only
  boneDim: '#8E897F', graphite: '#1A1C20', rule: '#3A3C40',
};
export const rgb = hex => [parseInt(hex.slice(1, 3), 16) / 255, parseInt(hex.slice(3, 5), 16) / 255, parseInt(hex.slice(5, 7), 16) / 255];
export const rgba = (hex, a) => { const [r, g, b] = rgb(hex); return `rgba(${(r * 255) | 0},${(g * 255) | 0},${(b * 255) | 0},${clamp(fin(a))})`; };

// ---- pooled canvases (reuse to avoid GC churn; content is always cleared by the user) ----
const pool = new Map();
export function layer(name, w = DW, h = DH) {
  const key = `${name}:${w}x${h}`;
  let c = pool.get(key);
  if (!c) { c = document.createElement('canvas'); c.width = w; c.height = h; c.ctx = c.getContext('2d', { willReadFrequently: false }); pool.set(key, c); }
  return c;
}
export function resetCtx(g) { g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = 1; g.globalCompositeOperation = 'source-over'; g.filter = 'none'; g.shadowBlur = 0; g.shadowColor = 'transparent'; }
export function clearLayer(c) { resetCtx(c.ctx); c.ctx.clearRect(0, 0, c.width, c.height); return c.ctx; }

// timecode HH:MM:SS:FF at 30 fps
export function timecode(t) {
  t = Math.max(0, fin(t)); const f = Math.floor(t * FPS + 1e-3);
  const ff = f % FPS, s = Math.floor(f / FPS) % 60, m = Math.floor(f / FPS / 60) % 60, h = Math.floor(f / FPS / 3600);
  const p = n => String(n).padStart(2, '0');
  return `${p(h)}:${p(m)}:${p(s)}:${p(ff)}`;
}
