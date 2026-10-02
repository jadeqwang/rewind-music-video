// Canvas2D -> texture -> rtScene. For scenes that are easiest to draw as vector/2D graphics
// (data displays, printouts, diagrams). Drawn in 1920x1080 design pixels.
import * as THREE from 'three';

export class C2D {
  constructor(engine) {
    this.e = engine;
    this.canvas = document.createElement('canvas');
    this.canvas.width = engine.W; this.canvas.height = engine.H;
    this.ctx = this.canvas.getContext('2d');
    this.tex = new THREE.CanvasTexture(this.canvas);
    this.tex.colorSpace = THREE.NoColorSpace;
    this.tex.generateMipmaps = false;
    this.tex.minFilter = THREE.LinearFilter;
    this.mat = engine.shader(/* glsl */`
      uniform sampler2D tSrc; uniform float halftoneAmt; uniform vec2 res; uniform float S; uniform vec3 paperC;
      void main(){
        vec4 c = texture(tSrc, vUv);
        vec3 col = c.rgb;
        if (halftoneAmt > 0.) {
          vec2 px = vUv * res / S;
          // print texture: re-screen mid-tones (keeps flat inks flat, adds dots in gradients)
          float l = luma(col);
          float cov = halftone(px, 1. - l, 5.5, .26);
          col = mix(col, overprint(paperC, col / max(l, .05) * .5, cov), halftoneAmt * smoothstep(.05, .25, l) * (1. - smoothstep(.8, .95, l)));
        }
        fragColor = vec4(col, c.a);
      }`, { tSrc: { value: this.tex }, halftoneAmt: { value: 0 }, res: { value: new THREE.Vector2(engine.W, engine.H) }, S: { value: engine.S },
      paperC: { value: new THREE.Color(0.953, 0.937, 0.902) } });
  }
  begin(clear = null) {
    const c = this.ctx;
    c.setTransform(1, 0, 0, 1, 0, 0);
    if (clear) { c.fillStyle = clear; c.fillRect(0, 0, this.e.W, this.e.H); } else c.clearRect(0, 0, this.e.W, this.e.H);
    c.setTransform(this.e.S, 0, 0, this.e.S, 0, 0);
    c.globalAlpha = 1; c.globalCompositeOperation = 'source-over';
    return c;
  }
  end({ over = false, halftone = 0 } = {}) {
    this.tex.needsUpdate = true;
    this.mat.uniforms.halftoneAmt.value = halftone;
    if (over) this.e.passOver(this.mat, this.e.rtScene); else this.e.pass(this.mat, this.e.rtScene);
  }
}

export function font(c, family, px, weight = 400, stretch = 'normal', style = 'normal') {
  c.font = `${style} ${weight} ${px}px ${family}`;
  try { c.fontStretch = stretch; } catch (e) { /* noop */ }
}
