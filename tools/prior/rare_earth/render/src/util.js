// Deterministic helpers shared by every scene.
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
export const smoother = (t) => { t = clamp(t); return t * t * t * (t * (t * 6 - 15) + 10); };
export const easeOutCubic = (t) => 1 - Math.pow(1 - clamp(t), 3);
export const easeInCubic = (t) => Math.pow(clamp(t), 3);
export const easeOutExpo = (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * clamp(t)));
export const easeInOutCubic = (t) => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
export const easeOutBack = (t, s = 1.70158) => { t = clamp(t) - 1; return 1 + t * t * ((s + 1) * t + s); };
export const easeOutElastic = (t) => {
  t = clamp(t);
  if (t === 0 || t === 1) return t;
  return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * (2 * Math.PI) / 3) + 1;
};
export const range = (x, a, b) => clamp((x - a) / (b - a));
export const pulse = (x, w) => Math.exp(-(x * x) / (w * w));

// hash-based randomness: same inputs -> same numbers, every render
export function hash1(n) { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); }
export function hash2(a, b) { const s = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return s - Math.floor(s); }
export function rng(seed) {
  let s = (seed >>> 0) || 1;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
}
export function noise1(x) {
  const i = Math.floor(x), f = x - i; const u = f * f * (3 - 2 * f);
  return lerp(hash1(i), hash1(i + 1), u);
}

export const INK = {
  klein: [0x1f / 255, 0x2b / 255, 0xd1 / 255],
  orange: [1.0, 0x5a / 255, 0x1f / 255],
  pale: [0x9c / 255, 0xcb / 255, 1.0],
  pink: [1.0, 0x48 / 255, 0xb0 / 255],
  mint: [0x3f / 255, 0xe0 / 255, 0xc5 / 255],
  yellow: [1.0, 0xe1 / 255, 0x4d / 255],
  ink: [0x0b / 255, 0x0b / 255, 0x14 / 255],
  paper: [0xf3 / 255, 0xef / 255, 0xe6 / 255],
  violet: [0x2a / 255, 0x10 / 255, 0x5a / 255],
  red: [0xff / 255, 0x2a / 255, 0x2a / 255],
};
export const css = (c, a = 1) => `rgba(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)},${a})`;
