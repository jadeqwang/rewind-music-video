// Rotoscope layer: redraws a base clip frame from its guide maps (line / tone / matte / color class)
// as SIGNAL PRINT inks, or as LIGHT MODE neon linework. The base clip itself is never displayed.
import * as THREE from 'three';

const cache = new Map(); // url -> {tex, img, last}
let clock = 0;

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('load ' + url));
    img.src = url;
  });
}

export async function getTex(url) {
  clock++;
  let e = cache.get(url);
  if (e) { e.last = clock; return e.tex; }
  const img = await loadImage(url);
  const tex = new THREE.Texture(img);
  tex.colorSpace = THREE.NoColorSpace;
  tex.generateMipmaps = false;
  tex.minFilter = THREE.LinearFilter; tex.magFilter = THREE.LinearFilter;
  tex.flipY = true;
  tex.needsUpdate = true;
  e = { tex, last: clock };
  cache.set(url, e);
  if (cache.size > 90) { // evict least recently used
    const old = [...cache.entries()].sort((a, b) => a[1].last - b[1].last).slice(0, 30);
    for (const [k, v] of old) { v.tex.dispose(); cache.delete(k); }
  }
  return tex;
}

export const metaCache = new Map();
export async function clipMeta(name) {
  if (metaCache.has(name)) return metaCache.get(name);
  const r = await fetch(`/work/guides/${name}/meta.json`);
  if (!r.ok) throw new Error('no clip ' + name);
  const m = await r.json();
  metaCache.set(name, m);
  return m;
}

// Frame selection: drawings on twos (12 fps) by default; `offset` = seconds into the clip at local time 0.
export function frameIndex(meta, clipTime, twos = true) {
  let f = Math.floor(clipTime * meta.fps + 1e-3);   // lags are stored rounded to 6 decimals; 1e-3 frame keeps them on the intended frame
  if (twos) f -= f % 2;
  return Math.max(0, Math.min(meta.frames - 1, f));
}

export function makeRotoMaterial(engine) {
  return engine.shader(/* glsl */`
    uniform sampler2D tGuide; uniform sampler2D tColor;
    uniform vec2 res; uniform float S; uniform float time; uniform float kick;
    uniform float mode;          // 0 = print, 1 = light, 2 = data (dither)
    uniform vec3 inkA;           // shadow ink (halftone)
    uniform vec3 inkB;           // accent ink (flat)
    uniform vec3 inkC;           // hair/secondary accent
    uniform vec3 inkLine;        // line ink
    uniform vec3 paperC;         // stock (print) / background (light)
    uniform float cell;          // halftone cell (design px)
    uniform float boil;          // line boil amount
    uniform float drawSeed;      // changes every drawing (on twos)
    uniform vec4 frameRect;      // where the clip lands on screen: x,y,w,h in uv (0..1)
    uniform float bgKeep;        // keep background (context clips) 1, or only subject (keyed) 0
    uniform float lineGain;
    uniform float toneGamma;
    uniform vec3 glowCol; uniform vec3 glowCol2;
    uniform float alphaOut;      // write matte into alpha
    uniform float envFill;       // light mode: luminous areas of environment plates glow in the inks
    void main(){
      vec2 uv = (vUv - frameRect.xy) / frameRect.zw;
      if (uv.x < 0. || uv.y < 0. || uv.x > 1. || uv.y > 1.) { fragColor = vec4(paperC, 0.); return; }
      vec2 px = vUv * res / S;
      // line boil: tiny per-drawing displacement of the sampling position
      vec2 bo = (vec2(vnoise(px * .02 + drawSeed * 7.1), vnoise(px * .02 + drawSeed * 3.7 + 9.)) - .5) * boil / vec2(1280., 720.);
      vec4 g = texture(tGuide, uv + bo);
      vec3 col = texture(tColor, uv).rgb;
      float line = clamp(g.r * lineGain, 0., 1.);
      float tone = pow(g.g, toneGamma);
      float matte = g.b;
      // ink classification from the smoothed color
      float mx = max(col.r, max(col.g, col.b)), mn = min(col.r, min(col.g, col.b));
      float sat = (mx - mn) / max(mx, 1e-3);
      float hue = 0.;
      if (mx - mn > 1e-3) {
        if (mx == col.r) hue = mod((col.g - col.b) / (mx - mn), 6.);
        else if (mx == col.g) hue = (col.b - col.r) / (mx - mn) + 2.;
        else hue = (col.r - col.g) / (mx - mn) + 4.;
        hue /= 6.;
      }
      float orange = smoothstep(.42, .6, sat) * (1. - smoothstep(.06, .11, abs(hue - .06))) * step(.45, mx);
      float blueish = smoothstep(.2, .4, sat) * (1. - smoothstep(.06, .12, abs(hue - .58)));
      float skin = (1. - smoothstep(.05, .1, abs(hue - .06))) * smoothstep(.08, .2, sat) * (1. - smoothstep(.45, .6, sat)) * step(.55, mx);
      vec3 outc; float a = 1.;
      if (mode < .5) {
        // PRINT: paper, overprinted halftone shadow ink, flat accent inks, black ink line
        float shade = clamp(1. - tone * 1.08, 0., 1.);
        shade = shade * shade * .9 + shade * .1;
        float cov = halftone(px, shade, cell * (1. + kick * .12), .26);
        vec3 c = paperC;
        c = overprint(c, inkA, cov * mix(1., .55, skin));
        c = overprint(c, inkB, orange * .95);
        c = overprint(c, inkC, blueish * .8);
        // deep darks (hair, crop top) as solid ink
        float deep = smoothstep(.2, .1, tone);
        c = overprint(c, inkLine, deep * .9);
        c = overprint(c, inkLine, line);
        float m = mix(1., matte, 1. - bgKeep);
        outc = c; a = m;
      } else if (mode < 1.5) {
        // LIGHT: neon linework + faint fill on dark
        float dotsF = halftone(px, tone * .55, cell * .9, .5);
        vec3 c = paperC + glowCol * dotsF * matte * .22;
        vec3 lc = mix(glowCol, glowCol2, orange);
        c += lc * line * 1.6;
        c += glowCol * smoothstep(.75, 1., tone) * matte * .35;
        if (envFill > 0.) {
          float lum = smoothstep(.18, 1., tone);
          c += mix(glowCol2, glowCol, smoothstep(.35, .9, tone)) * lum * lum * envFill;
          c += glowCol * halftone(px, lum * .5, cell, .5) * envFill * .25;
        }
        outc = c; a = mix(1., matte, 1. - bgKeep);
      } else {
        // DATA: 1-bit ordered dither of tone, in glowCol
        float th = bayer4(floor(px / max(1., cell * .25)));
        float on = step(th, tone * 1.05);
        vec3 c = mix(paperC, glowCol, on);
        c = mix(c, glowCol2, line * .8);
        outc = c; a = mix(1., matte, 1. - bgKeep);
      }
      fragColor = vec4(outc, alphaOut > .5 ? a : 1.);
    }`, {
    tGuide: { value: null }, tColor: { value: null },
    res: { value: new THREE.Vector2(engine.W, engine.H) }, S: { value: engine.S }, time: { value: 0 }, kick: { value: 0 },
    mode: { value: 0 }, inkA: { value: new THREE.Color() }, inkB: { value: new THREE.Color() }, inkC: { value: new THREE.Color() },
    inkLine: { value: new THREE.Color(0.043, 0.043, 0.078) }, paperC: { value: new THREE.Color(0.953, 0.937, 0.902) },
    cell: { value: 7 }, boil: { value: 1.2 }, drawSeed: { value: 0 }, frameRect: { value: new THREE.Vector4(0, 0, 1, 1) },
    bgKeep: { value: 1 }, lineGain: { value: 1.3 }, toneGamma: { value: 1.0 },
    glowCol: { value: new THREE.Color() }, glowCol2: { value: new THREE.Color() }, alphaOut: { value: 0 }, envFill: { value: 0 },
  });
}
