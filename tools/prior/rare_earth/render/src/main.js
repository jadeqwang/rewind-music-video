// RARE EARTH renderer entry point.
// URL params: ?w=1920&h=1080 (render size), ?t=12.3 (render one frame), ?play=1 (live preview with audio)
import { Engine } from './engine.js';
import { AudioMap } from './audio.js';
import { TypeLayer, loadFonts } from './type.js';
import { buildTimeline, buildGlobalPost } from './timeline.js';
import { SCENES } from './scenes/index.js';

const qs = new URLSearchParams(location.search);
const W = Number(qs.get('w') || 1920), H = Number(qs.get('h') || 1080);
const canvas = document.getElementById('view');
canvas.width = W; canvas.height = H;
canvas.style.width = qs.get('fit') ? '100vw' : `${W}px`;

const state = {};

async function boot() {
  const data = await (await fetch('data/audio.json')).json();
  await loadFonts();
  const engine = new Engine(canvas, W, H);
  const audio = new AudioMap(data);
  const type = new TypeLayer(engine, audio);
  const shots = buildTimeline(audio);
  const ctx = { engine, audio, type, W, H, S: engine.S, state: {} };
  for (const s of Object.values(SCENES)) if (s.init) await s.init(ctx);
  Object.assign(state, { engine, audio, type, shots, ctx, globalPost: buildGlobalPost(audio) });
  window.__shots = shots.map((s) => ({ id: s.id, t0: s.t0, t1: s.t1, scene: s.scene }));
}

function shotAt(t) {
  const { shots } = state;
  for (let i = shots.length - 1; i >= 0; i--) if (t >= shots[i].t0 && t < shots[i].t1) return shots[i];
  return shots[shots.length - 1];
}

let busy = Promise.resolve();
async function renderAt(t) {
  const run = async () => {
    const { engine, type, ctx } = state;
    const shot = shotAt(t);
    const lt = t - shot.t0;
    const scene = SCENES[shot.scene];
    if (!scene) throw new Error('no scene ' + shot.scene);
    ctx.t = t; ctx.lt = lt; ctx.shot = shot;
    await scene.draw(ctx, shot, t, lt);
    type.begin();
    if (shot.type) shot.type(type, t, lt, shot, ctx);
    const look = typeof shot.look === 'function' ? shot.look(t, lt, ctx) : (shot.look || {});
    const g = state.globalPost ? state.globalPost(t, shot) : {};
    const post = { ...look };
    // global rhythm layer composes with the shot's look (additive where it makes sense)
    post.zoom = (look.zoom ?? 1) * (g.zoom ?? 1);
    post.misreg = (look.misreg ?? 0) + (g.misreg ?? 0);
    post.ca = (look.ca ?? 0) + (g.ca ?? 0);
    post.flash = look.flash ? look.flash : (g.flash ?? 0);
    post.invert = Math.max(look.invert ?? 0, g.invert ?? 0);
    post.shakeX = (look.shakeX ?? 0) + (g.shakeX ?? 0); post.shakeY = (look.shakeY ?? 0) + (g.shakeY ?? 0);
    post.grainSeed = shot.t0;          // grain is re-seeded per shot, static within it (print texture, and cheap to encode)
    if (shot.post) Object.assign(post, shot.post(t, lt, ctx, post));
    engine.composite(post, t);
    const hud = document.getElementById('hud');
    if (hud && qs.get('debug')) hud.textContent = `${t.toFixed(3)}s  ${shot.id}  beat ${ctx.audio.beat(t).i}`;
  };
  busy = busy.then(run, run);
  return busy;
}

window.renderAt = renderAt;
window.__ready = boot().then(async () => {
  if (qs.get('t')) await renderAt(Number(qs.get('t')));
  if (qs.get('play')) {
    const el = new Audio('audio/Rare_Earth_DDR.mp3');
    document.body.addEventListener('click', () => el.play(), { once: true });
    const loop = async () => { await renderAt(el.currentTime || 0); requestAnimationFrame(loop); };
    loop();
  }
  return true;
}).catch((e) => { console.error(e); window.__error = String(e && e.stack || e); throw e; });
