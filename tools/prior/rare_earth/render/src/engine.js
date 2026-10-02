// Rendering engine: three.js WebGL2 context, render targets, fullscreen passes, bloom and the final
// SIGNAL PRINT compositor. Scenes draw into engine.rtScene; the type system draws into engine.typeCanvas.
import * as THREE from 'three';

export const GLSL_LIB = /* glsl */`
float hash12(vec2 p){ vec3 p3=fract(vec3(p.xyx)*.1031); p3+=dot(p3,p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }
vec2 hash22(vec2 p){ vec3 p3=fract(vec3(p.xyx)*vec3(.1031,.1030,.0973)); p3+=dot(p3,p3.yzx+33.33); return fract((p3.xx+p3.yz)*p3.zy); }
float vnoise(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.-2.*f);
  return mix(mix(hash12(i),hash12(i+vec2(1,0)),u.x),mix(hash12(i+vec2(0,1)),hash12(i+vec2(1,1)),u.x),u.y); }
float fbm(vec2 p){ float v=0., a=.5; for(int i=0;i<5;i++){ v+=a*vnoise(p); p=p*2.03+vec2(17.1,9.2); a*=.5; } return v; }
float fbm3(vec2 p){ float v=0., a=.5; for(int i=0;i<3;i++){ v+=a*vnoise(p); p=p*2.03+vec2(17.1,9.2); a*=.5; } return v; }
mat2 rot(float a){ float c=cos(a), s=sin(a); return mat2(c,-s,s,c); }
// amplitude-modulated halftone: coverage (0..1) for tone v (0..1) at pixel px; cell size in px
float halftone(vec2 px, float v, float cell, float ang){
  v = clamp(v, 0., 1.);
  vec2 q = rot(ang) * px / cell;
  vec2 f = fract(q) - .5;
  float d = length(f);
  float r = sqrt(v) * .7071;
  float aa = 0.75 / cell;
  float dots = 1. - smoothstep(r - aa, r + aa, d);
  // above ~78% the dots merge: switch to inverted (paper) dots
  float rinv = sqrt(max(0., 1. - v)) * .7071;
  float holes = smoothstep(rinv - aa, rinv + aa, length(fract(q + .5) - .5));
  return v > .5 ? max(dots, holes) : dots;
}
// line/stipple screen for alternate textures
float linescreen(vec2 px, float v, float cell, float ang){
  vec2 q = rot(ang) * px / cell; float f = abs(fract(q.y) - .5);
  float w = clamp(v, 0., 1.) * .5; float aa = .75 / cell;
  return 1. - smoothstep(w - aa, w + aa, f);
}
vec3 overprint(vec3 base, vec3 ink, float cov){ return base * mix(vec3(1.), ink, clamp(cov, 0., 1.)); }
float luma(vec3 c){ return dot(c, vec3(.299,.587,.114)); }
// Bayer 4x4 ordered dither threshold
float bayer4(vec2 px){ ivec2 p = ivec2(mod(px, 4.));
  int i = p.x + p.y*4;
  float m[16] = float[16](0.,8.,2.,10.,12.,4.,14.,6.,3.,11.,1.,9.,15.,7.,13.,5.);
  return (m[i] + .5) / 16.; }
`;

const FS_VERT = /* glsl */`
out vec2 vUv;
void main(){ vUv = position.xy * .5 + .5; gl_Position = vec4(position.xy, 0., 1.); }
`;

export class Engine {
  constructor(canvas, W, H) {
    this.W = W; this.H = H;
    this.S = H / 1080; // design-pixel scale (author everything at 1920x1080)
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(W, H, false);
    this.renderer.autoClear = true;
    this.renderer.outputColorSpace = THREE.LinearSRGBColorSpace; // we author colors directly
    const rtOpts = { type: THREE.HalfFloatType, depthBuffer: true, stencilBuffer: false, magFilter: THREE.LinearFilter, minFilter: THREE.LinearFilter };
    this.rtScene = new THREE.WebGLRenderTarget(W, H, rtOpts);
    this.rtTmp = new THREE.WebGLRenderTarget(W, H, rtOpts);
    this.rtTmp2 = new THREE.WebGLRenderTarget(W, H, rtOpts);
    this.bloomRTs = [];
    let w = W, h = H;
    for (let i = 0; i < 5; i++) { w = Math.max(1, w >> 1); h = Math.max(1, h >> 1); this.bloomRTs.push(new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, depthBuffer: false })); }
    this.quadGeo = new THREE.PlaneGeometry(2, 2);
    this.quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    this.quadScene = new THREE.Scene();
    this.quadMesh = new THREE.Mesh(this.quadGeo, null);
    this.quadMesh.frustumCulled = false;
    this.quadScene.add(this.quadMesh);

    this.typeCanvas = document.createElement('canvas');
    this.typeCanvas.width = W; this.typeCanvas.height = H;
    this.typeCtx = this.typeCanvas.getContext('2d');
    this.typeTex = new THREE.CanvasTexture(this.typeCanvas);
    this.typeTex.colorSpace = THREE.NoColorSpace;
    this.typeTex.premultiplyAlpha = false;
    this.typeTex.generateMipmaps = false;
    this.typeTex.minFilter = THREE.LinearFilter;

    this.materials = {};
    this._mkPost();
    this._bakePaper();
  }

  // Create a fullscreen shader material (glsl3)
  shader(fragBody, uniforms = {}) {
    return new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3, vertexShader: FS_VERT,
      fragmentShader: `precision highp float;\nin vec2 vUv;\nout vec4 fragColor;\n${GLSL_LIB}\n${fragBody}`,
      uniforms, depthTest: false, depthWrite: false,
    });
  }

  pass(material, target) {
    this.quadMesh.material = material;
    this.renderer.setRenderTarget(target || null);
    this.renderer.render(this.quadScene, this.quadCam);
  }

  // draw over the existing contents of target (alpha blended, no clear)
  passOver(material, target) {
    material.transparent = true;
    material.blending = THREE.NormalBlending;
    this.renderer.autoClear = false;
    this.quadMesh.material = material;
    this.renderer.setRenderTarget(target || null);
    this.renderer.render(this.quadScene, this.quadCam);
    this.renderer.autoClear = true;
  }

  _mkPost() {
    this.matDown = this.shader(/* glsl */`
      uniform sampler2D tSrc; uniform vec2 texel; uniform float threshold; uniform float first;
      void main(){
        vec4 s = texture(tSrc, vUv) * 4.;
        s += texture(tSrc, vUv + vec2(-texel.x, -texel.y));
        s += texture(tSrc, vUv + vec2( texel.x,  texel.y));
        s += texture(tSrc, vUv + vec2( texel.x, -texel.y));
        s += texture(tSrc, vUv + vec2(-texel.x,  texel.y));
        vec3 c = s.rgb / 8.;
        if (any(isnan(c)) || any(isinf(c))) c = vec3(0.);
        c = min(c, vec3(8.));
        if (first > .5) { float l = max(c.r, max(c.g, c.b)); c *= smoothstep(threshold, threshold + .35, l); }
        fragColor = vec4(c, 1.);
      }`, { tSrc: { value: null }, texel: { value: new THREE.Vector2() }, threshold: { value: 0.6 }, first: { value: 0 } });
    this.matUp = this.shader(/* glsl */`
      uniform sampler2D tSrc; uniform sampler2D tBase; uniform vec2 texel;
      void main(){
        vec3 s = texture(tSrc, vUv + vec2(-texel.x*2., 0.)).rgb;
        s += texture(tSrc, vUv + vec2(-texel.x, texel.y)).rgb * 2.;
        s += texture(tSrc, vUv + vec2(0., texel.y*2.)).rgb;
        s += texture(tSrc, vUv + vec2(texel.x, texel.y)).rgb * 2.;
        s += texture(tSrc, vUv + vec2(texel.x*2., 0.)).rgb;
        s += texture(tSrc, vUv + vec2(texel.x, -texel.y)).rgb * 2.;
        s += texture(tSrc, vUv + vec2(0., -texel.y*2.)).rgb;
        s += texture(tSrc, vUv + vec2(-texel.x, -texel.y)).rgb * 2.;
        fragColor = vec4(s / 12. + texture(tBase, vUv).rgb, 1.);
      }`, { tSrc: { value: null }, tBase: { value: null }, texel: { value: new THREE.Vector2() } });

    this.matFinal = this.shader(/* glsl */`
      uniform sampler2D tScene; uniform sampler2D tType; uniform sampler2D tBloom;
      uniform vec2 res; uniform float time; uniform float S;
      uniform float paper;      // 0..1 paper stock texture (print look)
      uniform float grain;      // film/riso grain amount
      uniform float grainSeed;  // per-shot grain seed
      uniform float bloom;      // bloom mix (light look)
      uniform float misreg;     // plate misregistration in design px
      uniform float flash;      // + white flash, - ink flash
      uniform float invert;     // impact frame (hard 2-tone inversion)
      uniform vec3 invertInk;   // ink used for impact frames
      uniform float vignette;
      uniform vec2 shake;       // design px
      uniform float scan;       // CRT scanline amount
      uniform float ca;         // chromatic aberration (design px)
      uniform float fade;       // 0 = black, 1 = image
      uniform float zoom;       // global zoom punch
      uniform float spin;       // tiny roll
      uniform vec3 paperCol; uniform sampler2D tPaper;
      void main(){
        vec2 uv = (rot(spin) * ((vUv - .5) * vec2(res.x / res.y, 1.)) / vec2(res.x / res.y, 1.)) / zoom + .5 + shake * S / res;
        vec2 o = vec2(misreg * S) / res;
        vec2 c2 = vec2(ca * S) / res * (uv - .5) * 2.;
        vec3 col;
        col.r = texture(tScene, uv + o + c2).r;
        col.g = texture(tScene, uv).g;
        col.b = texture(tScene, uv - o*.6 - c2).b;
        if (any(isnan(col))) col = vec3(0.);
        if (bloom > 0.) { vec3 bl = texture(tBloom, uv).rgb; if (!any(isnan(bl))) col += bl * bloom; }
        // typography (straight alpha), with its own tiny misregistration of the color plate
        vec4 ty = texture(tType, uv);
        col = mix(col, ty.rgb, ty.a);
        // paper stock: fibres + mottling (multiplied, strongest in the light areas)
        if (paper > 0.) {
          float st = texture(tPaper, vUv).r;          // baked fibres + mottling (0.89..1)
          col = mix(col, col * st, paper * .9);
        }
        // grain
        // 2-design-px grain cells, seeded per shot and static within it: reads as the print's paper tooth,
        // and costs almost nothing to encode (per-frame noise would eat most of a 6 Mbit/s budget)
        float g = hash12(floor(vUv * res / (2. * S)) + fract(grainSeed * .1371) * 1000.) - .5;
        col += g * grain * .7 * (0.35 + .65 * (1. - luma(col)));
        // scanlines
        if (scan > 0.) { float sl = .5 + .5 * sin(vUv.y * res.y * 3.14159); col *= 1. - scan * .35 * sl; }
        // impact frame: hard two-tone
        if (invert > 0.) {
          float l = luma(col);
          vec3 hard = mix(invertInk, vec3(.98), step(.5, 1. - l));
          col = mix(col, hard, invert);
        }
        // flashes
        col = flash >= 0. ? mix(col, vec3(1.), flash) : mix(col, invertInk, -flash);
        // vignette
        vec2 vq = vUv - .5; col *= 1. - vignette * dot(vq, vq) * 1.6;
        col *= fade;
        fragColor = vec4(clamp(col, 0., 1.), 1.);
      }`, {
      tScene: { value: null }, tType: { value: this.typeTex }, tBloom: { value: null },
      res: { value: new THREE.Vector2(this.W, this.H) }, time: { value: 0 }, S: { value: this.S },
      paper: { value: 0 }, grain: { value: 0.05 }, grainSeed: { value: 0 }, bloom: { value: 0 }, misreg: { value: 0 }, flash: { value: 0 },
      invert: { value: 0 }, invertInk: { value: new THREE.Color(0.043, 0.043, 0.078) }, vignette: { value: 0.3 },
      shake: { value: new THREE.Vector2() }, scan: { value: 0 }, ca: { value: 0 }, fade: { value: 1 },
      paperCol: { value: new THREE.Color(0.953, 0.937, 0.902) }, zoom: { value: 1 }, spin: { value: 0 }, tPaper: { value: null },
    });
  }

  _bakePaper() {
    this.rtPaper = new THREE.WebGLRenderTarget(this.W, this.H, { type: THREE.UnsignedByteType, depthBuffer: false });
    const m = this.shader(/* glsl */`
      uniform vec2 res; uniform float S;
      void main(){
        vec2 px = vUv * res / S;
        float fib = fbm(px * vec2(.018, .06)) * .6 + vnoise(px * .9) * .4;
        float mott = fbm(px * .004 + 3.);
        float st = (0.93 + .07 * fib) * (0.96 + .06 * mott);
        fragColor = vec4(vec3(st), 1.);
      }`, { res: { value: new THREE.Vector2(this.W, this.H) }, S: { value: this.S } });
    this.pass(m, this.rtPaper);
    this.matFinal.uniforms.tPaper.value = this.rtPaper.texture;
  }

  bloomChain(src, threshold = 0.6) {
    let prev = src;
    for (let i = 0; i < this.bloomRTs.length; i++) {
      const rt = this.bloomRTs[i];
      this.matDown.uniforms.tSrc.value = prev.texture;
      this.matDown.uniforms.texel.value.set(1 / prev.width, 1 / prev.height);
      this.matDown.uniforms.threshold.value = threshold;
      this.matDown.uniforms.first.value = i === 0 ? 1 : 0;
      this.pass(this.matDown, rt);
      prev = rt;
    }
    // upsample back (accumulate into the next-larger level); reuse a temp per level via ping (in-place add)
    for (let i = this.bloomRTs.length - 1; i > 0; i--) {
      const small = this.bloomRTs[i], big = this.bloomRTs[i - 1];
      if (!big.__acc) big.__acc = new THREE.WebGLRenderTarget(big.width, big.height, { type: THREE.HalfFloatType, depthBuffer: false });
      this.matUp.uniforms.tSrc.value = (small.__acc && i < this.bloomRTs.length - 1) ? small.__acc.texture : small.texture;
      this.matUp.uniforms.tBase.value = big.texture;
      this.matUp.uniforms.texel.value.set(0.5 / small.width, 0.5 / small.height);
      this.pass(this.matUp, big.__acc);
    }
    return this.bloomRTs[0].__acc.texture;
  }

  composite(post, time) {
    const u = this.matFinal.uniforms;
    u.tScene.value = this.rtScene.texture;
    u.time.value = time;
    this.typeTex.needsUpdate = true;
    u.bloom.value = post.bloom || 0;
    if (u.bloom.value > 0) u.tBloom.value = this.bloomChain(this.rtScene, post.bloomThreshold ?? 0.55);
    u.paper.value = post.paper || 0;
    u.grain.value = post.grain ?? 0.05;
    u.grainSeed.value = post.grainSeed ?? 0;
    u.misreg.value = post.misreg || 0;
    u.flash.value = post.flash || 0;
    u.invert.value = post.invert || 0;
    if (post.invertInk) u.invertInk.value.setRGB(...post.invertInk);
    u.vignette.value = post.vignette ?? 0.3;
    u.shake.value.set(post.shakeX || 0, post.shakeY || 0);
    u.scan.value = post.scan || 0;
    u.ca.value = post.ca || 0;
    u.fade.value = post.fade ?? 1;
    u.zoom.value = post.zoom ?? 1;
    u.spin.value = post.spin ?? 0;
    this.pass(this.matFinal, null);
  }
}
