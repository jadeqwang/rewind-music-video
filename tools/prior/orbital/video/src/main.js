// main.js: boot, renderAt(t), renderSheet(), and the interactive scrubber.

const Q = new URLSearchParams(location.search);
window.ready = false;

async function renderFrame(t) {
  G.setTransform(1, 0, 0, 1, 0, 0); G.globalAlpha = 1; G.globalCompositeOperation = 'source-over';
  const sh = shotAt(t);
  if (!sh) { paper(G, 'night'); return; }
  // The film is drawn on twos: everything (camera punches, type, pulses) changes on a 12-per-second
  // clock that restarts at each cut, so cuts stay frame-exact. Impact and panic shots opt into ones.
  if (!(sh.opts && sh.opts.ones) && !Q.has('ones')) t = sh.t0 + Math.floor((t - sh.t0) * 12 + 1e-6) / 12;
  const lt = t - sh.t0;
  await sh.fn(t, lt, sh.t1 - sh.t0, sh);
  G.setTransform(1, 0, 0, 1, 0, 0); G.globalAlpha = 1; G.globalCompositeOperation = 'source-over';
  finish(t, sh);
}

// global finishing: a whisper of film-grain flicker and the paper vignette (shots may disable)
function finish(t, sh) {
  if (sh.opts && sh.opts.noFinish) return;
}

window.renderAt = async (t, type = 'image/jpeg', q = .92) => {
  await renderFrame(t);
  return OUT.toDataURL(type, q);
};

// Making-of: the reference plate(s) behind frame t, placed exactly where the renderer read them (never part of the film)
window.renderSource = async (t, type = 'image/jpeg', q = .9) => {
  window._rec = []; await renderFrame(t); const rec = window._rec; window._rec = null;
  const S = makeCanvas(W, H), g = S.getContext('2d');
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  for (const r of rec) { const im = await plateImage(r.id, r.tp); g.setTransform(r.m); g.drawImage(im, 0, 0); }
  return { url: S.toDataURL(type, q), plates: rec.map(r => [r.id, +r.tp.toFixed(3)]) };
};

window.renderSheet = async (times, cols = 3, w = 640) => {
  const h = Math.round(w * 9 / 16), rows = Math.ceil(times.length / cols);
  const S = makeCanvas(cols * w, rows * (h + 26)), g = S.getContext('2d');
  g.fillStyle = '#222'; g.fillRect(0, 0, S.width, S.height);
  const ms = [];
  for (let i = 0; i < times.length; i++) {
    const t0 = performance.now(); await renderFrame(times[i]); ms.push(performance.now() - t0);
    const x = (i % cols) * w, y = Math.floor(i / cols) * (h + 26);
    g.drawImage(OUT, x, y, w, h);
    g.fillStyle = '#ddd'; g.font = '16px monospace'; const sh = shotAt(times[i]);
    g.fillText(`${times[i].toFixed(2)}s  ${sh ? sh.name : '-'}  ${ms[i].toFixed(0)}ms`, x + 6, y + h + 18);
  }
  return { url: S.toDataURL('image/jpeg', .9), ms };
};

(async function boot() {
  const tm = await loadJSON('data/timing.json');
  Object.assign(TM, { bpm: tm.bpm, beat: tm.beat, t0: tm.t0, beats: tm.beats, sections: tm.sections, lines: tm.lines, dur: tm.dur, durExt: tm.durExt });
  try { PLATES = await loadJSON('plates/index.json'); } catch (e) { console.warn('no plates index'); }
  try { TM.mouth = await loadJSON('data/mouth.json'); } catch (e) { TM.mouth = null; }
  buildTooth(); buildPaper('night'); buildPaper('snow');
  await Promise.all([FONT.impact(40), FONT.cyr(40), FONT.serif(40), FONT.mono(20), FONT.mono(20, 700), FONT.mono(20, 800), FONT.serifR(40), FONT.cyr(40, 500)].map(f => document.fonts.load(f, 'AБ')));
  if (typeof initShots === 'function') await initShots();
  window.ready = true;
  if (!Q.has('render')) {
    const scrub = document.getElementById('scrub'), tt = document.getElementById('tt');
    let busy = false, want = +(Q.get('t') || 0);
    const go = async () => { if (busy) return; busy = true; const t = want; const t0 = performance.now(); await renderFrame(t); const sh = shotAt(t); tt.textContent = `${t.toFixed(2)}s  ${sh ? sh.name : ''}  ${(performance.now() - t0).toFixed(0)}ms`; busy = false; if (t !== want) go(); };
    scrub.value = want; scrub.oninput = () => { want = +scrub.value; go(); }; go();
  }
})();
