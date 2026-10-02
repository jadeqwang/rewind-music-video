// post.js: WebGL2 post compositor (ported from tools/prior/rare_earth engine.js, rewritten on raw WebGL2, no three.js).
// Inputs: the Canvas2D scene layer and the Canvas2D type/HUD layer (both 1920x1080 design, any pixel size).
// Passes: dual-filter bloom (5 levels) → final compositor: zoom punch / roll / shake / ripple / tape warble (uv),
// chromatic aberration, misregistration, bloom, type mix, rewind negative-cyan grade, per-shot static grain,
// scanlines, two-tone impact invert, ± flash, vignette, fade.
// Orientation: canvases are uploaded with UNPACK_FLIP_Y so uv (0,0) = bottom-left everywhere; "screen y" in shaders
// is (1 - uv.y) * H (top-down) whenever an effect is defined in design pixels.
// Works under SwiftShader (--use-gl=angle --use-angle=swiftshader); RGBA8 targets unless float targets are renderable.

const VS = `#version 300 es
in vec2 p; out vec2 vUv; void main(){ vUv = p * .5 + .5; gl_Position = vec4(p, 0., 1.); }`;

const LIB = `
float hash12(vec2 p){ vec3 p3=fract(vec3(p.xyx)*.1031); p3+=dot(p3,p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }
float vnoise(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.-2.*f);
  return mix(mix(hash12(i),hash12(i+vec2(1,0)),u.x),mix(hash12(i+vec2(0,1)),hash12(i+vec2(1,1)),u.x),u.y); }
float luma(vec3 c){ return dot(c, vec3(.299,.587,.114)); }
mat2 rot(float a){ float c=cos(a), s=sin(a); return mat2(c,-s,s,c); }
vec3 safe(vec3 c){ if (any(isnan(c)) || any(isinf(c))) return vec3(0.); return c; }
`;

const FS_DOWN = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; ${LIB}
uniform sampler2D tSrc; uniform sampler2D tType; uniform vec2 texel; uniform float thr; uniform float first; uniform float typeBloom;
vec3 S(vec2 uv){
  vec3 c = texture(tSrc, uv).rgb;
  if (first > .5) { vec4 ty = texture(tType, uv); c = mix(c, ty.rgb, ty.a * typeBloom); }
  return safe(c);
}
void main(){
  vec3 c = S(vUv) * 4.;
  c += S(vUv + vec2(-texel.x, -texel.y)); c += S(vUv + vec2(texel.x, texel.y));
  c += S(vUv + vec2(texel.x, -texel.y)); c += S(vUv + vec2(-texel.x, texel.y));
  c /= 8.;
  if (first > .5) { float l = max(c.r, max(c.g, c.b)); c *= smoothstep(thr, thr + .3, l); }
  o = vec4(safe(min(c, vec3(4.))), 1.);
}`;

const FS_UP = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; ${LIB}
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
  o = vec4(safe(s / 12. + texture(tBase, vUv).rgb), 1.);
}`;

const FS_FINAL = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; ${LIB}
uniform sampler2D tScene, tType, tBloom;
uniform vec2 res; uniform float S; uniform float time;
uniform float bloom, ca, misreg, grain, grainSeed, scan, invert, flash, vignette, fade, zoom, spin;
uniform vec2 shake; uniform float ripple, ripplePhase, warble, warbleSeed, tracking, neg, typeCA, typeDim, dither;
uniform vec3 inkC, boneC, cyanC, flashC;
vec2 distort(vec2 uv){
  vec2 a = vec2(res.x / res.y, 1.);
  vec2 q = (uv - .5) * a;
  q = rot(spin) * q / zoom;
  // ripple (rewind): concentric radial wave from the centre
  if (ripple > 0.) { float r = length(q); q += normalize(q + 1e-5) * sin(r * 26. - ripplePhase) * ripple * .012 * smoothstep(0., .3, r); }
  uv = q / a + .5;
  uv += shake * S / res;
  float sy = (1. - uv.y) * res.y / S;               // screen y in design px (top-down)
  // tape warble: banded horizontal displacement + a rolling tracking band
  if (warble > 0.) {
    float band = floor(sy / 6.);
    float n = vnoise(vec2(band * .37, warbleSeed * 3.1)) - .5;
    float slow = sin(sy * .011 + warbleSeed * 1.7) * .5;
    uv.x += (n * .6 + slow * .4) * warble * 7. * S / res.x;
  }
  if (tracking > 0.) {
    float by = fract(warbleSeed * .173) * 1080.;
    float d = abs(sy - by);
    float m = smoothstep(46., 0., d);
    uv.x += m * tracking * (vnoise(vec2(sy * .35, warbleSeed)) - .3) * 40. * S / res.x;
  }
  return uv;
}
void main(){
  vec2 uv = distort(vUv);
  vec2 o1 = vec2(misreg * S) / res;
  vec2 c2 = vec2(ca * S) / res * (uv - .5) * 2.;
  vec3 col;
  col.r = texture(tScene, uv + o1 + c2).r;
  col.g = texture(tScene, uv).g;
  col.b = texture(tScene, uv - o1 * .6 - c2).b;
  col = safe(col);
  if (bloom > 0.) col += safe(texture(tBloom, uv).rgb) * bloom;
  // type layer (straight alpha) with its own, smaller CA
  vec2 tc = c2 * typeCA;
  vec4 ty = texture(tType, uv);
  float tar = texture(tType, uv + tc).a, tab = texture(tType, uv - tc).a;
  vec3 tcol = vec3(texture(tType, uv + tc).r, ty.g, texture(tType, uv - tc).b);
  vec3 ta = vec3(tar, ty.a, tab);
  col = mix(col, tcol * typeDim, ta);
  col = safe(col);
  // rewind grade: negative, mapped into an ink→cyan→bone duotone
  if (neg > 0.) {
    float l = 1. - clamp(luma(col), 0., 1.);
    vec3 duo = l < .55 ? mix(inkC * .6, cyanC * .55, l / .55) : mix(cyanC * .55, mix(cyanC, boneC, .55), (l - .55) / .45);
    col = mix(col, duo, neg);
  }
  // per-shot static grain (2 design-px cells), weighted toward darks
  float g = hash12(floor(vUv * res / (2. * S)) + fract(grainSeed * .1371) * 1000.) - .5;
  col += g * grain * (.35 + .65 * (1. - luma(col)));
  if (scan > 0.) { float sl = .5 + .5 * sin((1. - vUv.y) * res.y / S * 3.14159 * .5); col *= 1. - scan * .4 * sl; }
  if (invert > 0.) { float l = luma(col); vec3 hard = mix(boneC, inkC, step(.42, l)); col = mix(col, hard, invert); }
  col = flash >= 0. ? mix(col, flashC, flash) : mix(col, inkC, -flash);
  vec2 vq = vUv - .5; col *= 1. - vignette * dot(vq, vq) * 1.6;
  col *= fade;
  col += (hash12(vUv * res + 7.) - .5) * dither / 255.;
  o = vec4(clamp(safe(col), 0., 1.), 1.);
}`;

export class Post {
  constructor(canvas, W, H) {
    this.W = W; this.H = H; this.S = H / 1080;
    const gl = canvas.getContext('webgl2', { antialias: false, alpha: false, preserveDrawingBuffer: true, premultipliedAlpha: false });
    if (!gl) throw new Error('WebGL2 unavailable');
    this.gl = gl;
    this.floatRT = !!gl.getExtension('EXT_color_buffer_float') && !!gl.getExtension('OES_texture_float_linear');
    this.info = { renderer: gl.getParameter(gl.RENDERER), floatRT: this.floatRT };
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    this.vao = gl.createVertexArray(); gl.bindVertexArray(this.vao);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    this.pDown = this._prog(FS_DOWN); this.pUp = this._prog(FS_UP); this.pFinal = this._prog(FS_FINAL);
    this.texScene = this._tex(W, H, false); this.texType = this._tex(W, H, false);
    this.levels = []; let w = W, h = H;
    for (let i = 0; i < 5; i++) { w = Math.max(1, w >> 1); h = Math.max(1, h >> 1); this.levels.push({ w, h, down: this._rt(w, h), up: this._rt(w, h) }); }
  }

  _sh(type, src) { const gl = this.gl, s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) + '\n' + src.split('\n').map((l, i) => i + 1 + ' ' + l).join('\n')); return s; }
  _prog(fs) {
    const gl = this.gl, p = gl.createProgram();
    gl.attachShader(p, this._sh(gl.VERTEX_SHADER, VS)); gl.attachShader(p, this._sh(gl.FRAGMENT_SHADER, fs));
    gl.bindAttribLocation(p, 0, 'p'); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    const u = {}; const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < n; i++) { const a = gl.getActiveUniform(p, i); u[a.name] = gl.getUniformLocation(p, a.name); }
    return { p, u };
  }
  _tex(w, h, float) {
    const gl = this.gl, t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    if (float) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null);
    else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  }
  _rt(w, h) { const gl = this.gl, tex = this._tex(w, h, this.floatRT), fb = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fb); gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0); gl.bindFramebuffer(gl.FRAMEBUFFER, null); return { tex, fb, w, h }; }
  _upload(tex, canvas) {
    const gl = this.gl; gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, canvas);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
  }
  _bind(prog, unit, name, tex) { const gl = this.gl; gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, tex); gl.uniform1i(prog.u[name], unit); }
  _draw(target, w, h) { const gl = this.gl; gl.bindFramebuffer(gl.FRAMEBUFFER, target); gl.viewport(0, 0, w, h); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); }

  render(sceneCanvas, typeCanvas, P, time = 0) {
    const gl = this.gl, n = (k, d) => (Number.isFinite(P[k]) ? P[k] : d);
    gl.bindVertexArray(this.vao); gl.disable(gl.BLEND);
    this._upload(this.texScene, sceneCanvas); this._upload(this.texType, typeCanvas);
    const bloom = n('bloom', 0.6);
    if (bloom > 0) {
      let src = this.texScene, sw = this.W, sh = this.H;
      gl.useProgram(this.pDown.p);
      for (let i = 0; i < this.levels.length; i++) {
        const L = this.levels[i];
        this._bind(this.pDown, 0, 'tSrc', src); this._bind(this.pDown, 1, 'tType', this.texType);
        gl.uniform2f(this.pDown.u.texel, 1 / sw, 1 / sh); gl.uniform1f(this.pDown.u.thr, n('bloomThr', 0.45));
        gl.uniform1f(this.pDown.u.first, i === 0 ? 1 : 0); gl.uniform1f(this.pDown.u.typeBloom, n('typeBloom', 0.5));
        this._draw(L.down.fb, L.w, L.h); src = L.down.tex; sw = L.w; sh = L.h;
      }
      gl.useProgram(this.pUp.p);
      let small = this.levels[this.levels.length - 1].down;
      for (let i = this.levels.length - 2; i >= 0; i--) {
        const L = this.levels[i];
        this._bind(this.pUp, 0, 'tSrc', small.tex); this._bind(this.pUp, 1, 'tBase', L.down.tex);
        gl.uniform2f(this.pUp.u.texel, 0.5 / small.w, 0.5 / small.h);
        this._draw(L.up.fb, L.w, L.h); small = L.up;
      }
    }
    const F = this.pFinal, u = F.u; gl.useProgram(F.p);
    this._bind(F, 0, 'tScene', this.texScene); this._bind(F, 1, 'tType', this.texType); this._bind(F, 2, 'tBloom', this.levels[0].up.tex);
    gl.uniform2f(u.res, this.W, this.H); gl.uniform1f(u.S, this.S); gl.uniform1f(u.time, time);
    const f1 = (k, d) => u[k] && gl.uniform1f(u[k], n(k, d));
    f1('bloom', 0.6); f1('ca', 0); f1('misreg', 0); f1('grain', 0.05); f1('grainSeed', 0); f1('scan', 0); f1('invert', 0); f1('flash', 0);
    f1('vignette', 0.25); f1('fade', 1); f1('zoom', 1); f1('spin', 0); f1('ripple', 0); f1('ripplePhase', 0); f1('warble', 0);
    f1('warbleSeed', 0); f1('tracking', 0); f1('neg', 0); f1('typeCA', 0.35); f1('typeDim', 1); f1('dither', 1.5);
    gl.uniform2f(u.shake, n('shakeX', 0), n('shakeY', 0));
    const c3 = (k, v) => gl.uniform3f(u[k], v[0], v[1], v[2]);
    c3('inkC', P.inkC || [0.027, 0.031, 0.039]); c3('boneC', P.boneC || [0.925, 0.902, 0.847]);
    c3('cyanC', P.cyanC || [0.239, 0.949, 0.902]); c3('flashC', P.flashC || [0.925, 0.902, 0.847]);
    this._draw(null, this.W, this.H);
  }
}
