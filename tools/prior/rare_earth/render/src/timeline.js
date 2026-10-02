// THE EDIT. Every shot is placed on the song's own clock: lyric word onsets (A.W) and the tracked,
// accelerating beat grid (bars below). Shots never overlap; transitions are cuts, flashes and impact frames.
import { INK, css, clamp, range, smooth, easeOutCubic, easeInOutCubic, lerp, pulse } from './util.js';
import { SELECT } from './selects.js';

const P = css(INK.paper), PALE = css(INK.pale), ORANGE = css(INK.orange), MINT = css(INK.mint),
  PINK = css(INK.pink), YELLOW = css(INK.yellow), KLEIN = css(INK.klein), INKC = css(INK.ink);

// Earth print look / Echo print look / light look
const PRINT = { paper: 1, grain: 0.06, vignette: 0.25 };
const LIGHT = { bloom: 0.9, grain: 0.05, vignette: 0.35, bloomThreshold: 0.5 };
const LIGHT3D = { bloom: 0.55, grain: 0.05, vignette: 0.35, bloomThreshold: 0.72 };

export function buildTimeline(A) {
  const W = (i, j) => A.W(i, j), L = (i) => A.L(i);
  const bars = A.bars;
  const bar = (t) => bars.reduce((best, b) => (Math.abs(b - t) < Math.abs(best - t) ? b : best), bars[0]);
  // rotoscope shot helper: clip = shot id in SELECT (chosen take + measured lip-sync lag)
  const R = (clip, extra = {}) => {
    const s = SELECT[clip] || { start: 0, lag: 0 };
    return { clip, start: s.start, lag: s.lag || 0, mode: 'print', ...extra };
  };
  const skyL = (extra = {}) => ({ scene: 'sky', p: { mode: 'light', band: 1.0, density: 1.2, ...extra } });
  const burstBG = (extra = {}) => ({ scene: 'burst', p: { stars: true, ...extra } });
  const skyP = (extra = {}) => ({ scene: 'sky', p: { mode: 'print', band: 0.9, horizon: 0.1, ...extra } });

  const S = [];
  const add = (s) => { S.push(s); return s; };

  // ================================================================ COLD OPEN + V1 (Earth, asking)
  add({ id: 'poster', t0: 0, t1: 5.70, scene: 'roto',
    p: (t) => R('sd01', { rect: [-0.04 * smooth(t / 5.7), -0.03 * smooth(t / 5.7), 1 + 0.08 * smooth(t / 5.7), 1 + 0.08 * smooth(t / 5.7)] }),
    look: PRINT,
    type: (ty, t) => {
      const c = ty.ctx;
      // 1) the star she reaches for flares and blinks (foreshadows "the beating blinking of a star").
      //    Position tracked in the sd01 plate (clip px), mapped through the poster's slow push-in rect.
      const TRACK = [[1.5, 431, 89], [2.0, 429, 93], [2.5, 426, 99], [3.0, 423, 106], [3.5, 420, 114], [4.0, 417, 125],
        [4.5, 413, 135], [5.0, 409, 146], [5.5, 407, 156], [5.75, 405, 161]];
      let cx = TRACK[0][1], cy = TRACK[0][2];
      for (let i = 1; i < TRACK.length; i++) if (t >= TRACK[i - 1][0]) {
        const u = clamp((t - TRACK[i - 1][0]) / (TRACK[i][0] - TRACK[i - 1][0]));
        cx = lerp(TRACK[i - 1][1], TRACK[i][1], u); cy = lerp(TRACK[i - 1][2], TRACK[i][2], u);
      }
      const pk = smooth(t / 5.7), rr = [-0.04 * pk, -0.03 * pk, 1 + 0.08 * pk, 1 + 0.08 * pk];
      const starX = (rr[0] + (cx / 1280) * rr[2]) * 1920, starY = (1 - (rr[1] + (1 - cy / 720) * rr[3])) * 1080;
      const blinkT = [0.55, 1.35, 2.15, 2.75];
      let fl = 0.35;
      for (const bt of blinkT) fl = Math.max(fl, Math.exp(-Math.pow((t - bt) / 0.09, 2)) * 1.0);
      c.save(); c.globalCompositeOperation = 'lighter';
      const g = c.createRadialGradient(starX, starY, 0, starX, starY, 90 * fl + 20);
      g.addColorStop(0, `rgba(255,255,255,${0.9 * fl})`); g.addColorStop(0.3, `rgba(156,203,255,${0.35 * fl})`); g.addColorStop(1, 'rgba(0,0,0,0)');
      c.fillStyle = g; c.fillRect(starX - 200, starY - 200, 400, 400);
      c.fillStyle = `rgba(255,255,255,${0.85 * fl})`;
      c.fillRect(starX - 220 * fl, starY - 1.2, 440 * fl, 2.4); c.fillRect(starX - 1.2, starY - 140 * fl, 2.4, 280 * fl);
      c.restore();
      // 2) poster title: plates snap into register, then dissolve through a growing halftone erasure
      const reg = Math.max(0, 1 - t / 0.35);
      const dis = range(t, 2.45, 3.05);
      if (dis < 1) {
        c.save();
        const off = [7 + 26 * reg, 6 - 18 * reg];
        ty.font('NotoSerifDisplay', 250, 900, 'extra-condensed');
        ty.plateText('RARE', 90, 400, P, css(INK.orange, 0.9), off);
        ty.plateText('EARTH', 90, 640, P, css(INK.orange, 0.9), off);
        // translations on small ink labels, legible over the pale fog
        const label = (str, fam, size, wt, x, y) => {
          ty.font(fam, size, wt); const w = c.measureText(str).width;
          c.fillStyle = css(INK.ink, 0.88); c.fillRect(x - 12, y - size * 0.98, w + 24, size * 1.3);
          c.fillStyle = P; c.fillText(str, x, y);
        };
        label('稀有地球', 'NotoSansSC', 50, 900, 96, 726);
        label('Уникальная Земля', 'Unbounded', 34, 800, 96, 796);
        if (dis > 0) {
          c.globalCompositeOperation = 'destination-out';
          const cell = 18, rr = cell * 0.75 * dis;
          c.fillStyle = '#000';
          for (let y = 150; y < 820; y += cell) for (let x = 70; x < 820; x += cell) { c.beginPath(); c.arc(x + ((y / cell) % 2) * cell / 2, y, rr, 0, 7); c.fill(); }
        }
        c.restore();
      }
      // 3) HUD types itself
      const hudS = 'RX  1420.40575 MHz   ·   SUTRO / SF   ·   NIGHT 4,017';
      ty.hud(hudS.slice(0, Math.floor(Math.min(1, t / 1.1) * hudS.length)), 90, 70, { alpha: 0.85 });
      ty.hud('LISTENING  ' + (Math.floor(t * 2) % 2 ? '●' : '○'), 1830, 70, { align: 'right', alpha: 0.85 });
      ty.stack(t, [0], { x: 92, y: 360, size: 220, lineH: 205, maxW: 1150, accent: PALE, plate: css(INK.orange, 0.9) });
    } });

  add({ id: 'yearning', t0: 5.70, t1: 8.86, scene: 'roto', p: R('sd02'), look: PRINT,
    type: (ty, t) => ty.stack(t, [1], { x: 90, y: 250, size: 112, lineH: 122, maxW: 620, stretch: 'normal', accent: PALE }) });

  add({ id: 'searching', t0: 8.86, t1: 10.88, scene: 'array',
    p: { mode: 'print', choreo: 'sweep', cam: 'low' }, look: PRINT,
    type: (ty, t) => {
      ty.keyword(t, 'SEARCHING', W(2, 0), { size: 250, y: 330, plate: css(INK.orange, 0.9) });
      ty.keyword(t, 'FOR ME', W(2, 1), { size: 120, y: 470, stretch: 'normal' });
      ty.hud(`SCANNING  ${(1.4e9 + Math.floor((t - 8.86) * 3.1e8)).toLocaleString('en-US')}  CHANNELS`, 90, 1010);
    } });

  add({ id: 'listen', t0: 10.88, t1: 12.73, scene: 'roto', p: R('sd03', { rect: [0, -0.06, 1.12, 1.12] }), look: PRINT,
    type: (ty, t) => ty.stack(t, [3], { x: 70, y: 260, size: 128, lineH: 132, maxW: 540, accent: PALE, fromScale: 1.3 }) });

  add({ id: 'pullback', t0: 12.73, t1: 14.81, scene: 'roto', p: R('sd04'), look: PRINT,
    type: (ty, t) => {
      ty.keyword(t, 'A RARE EARTH', W(4, 0), { size: 200, y: 215, plate: css(INK.orange, 0.9) });
      ty.keyword(t, 'LOOKING FOR', W(4, 3), { size: 90, y: 335, stretch: 'normal' });
    } });

  add({ id: 'zoomout', t0: 14.81, t1: 18.04, scene: 'zoom', p: { from: 14.81, to: 18.04 }, look: PRINT,
    type: (ty, t) => {
      const k = range(t, 14.81, 17.2);
      ty.font('Archivo', 170, 900, 'expanded');
      const word = 'FRIEND';
      const sp = lerp(10, 90, easeOutCubic(k));
      let x = 960 - (ty.ctx.measureText(word).width + sp * (word.length - 1)) / 2;
      for (const ch of word) { ty.plateText(ch, x, 330, P, css(INK.orange, 0.85), [6, 5], 1 - range(t, 17.4, 18.0)); x += ty.ctx.measureText(ch).width + sp; }
    } });

  // ================================================================ V2 (Earth, the signal)
  add({ id: 'palebluedot', t0: 18.04, t1: 21.89, scene: 'dot', p: {}, look: { ...PRINT, paper: 0.3 },
    type: (ty, t) => {
      ty.stack(t, [5], { x: 110, y: 330, size: 92, lineH: 100, maxW: 620, accent: PALE, filter: (w) => w.t < W(5, 5) - 0.05, fromScale: 1.25 });
      ty.keyword(t, 'PALE BLUE DOT', W(5, 5), { size: 150, y: 240, color: PALE, stretch: 'expanded' });
      ty.hud('VOYAGER 1  ·  14 FEB 1990  ·  6.1 × 10⁹ km', 90, 1010, { alpha: 0.7 });            // 40.47 AU from Earth
      const c = ty.ctx, a = range(t, 18.3, 18.8) * (1 - range(t, 21.5, 21.89));
      if (a > 0) {
        c.globalAlpha = a; c.strokeStyle = PALE; c.lineWidth = 2.5;
        c.beginPath(); c.arc(1020, 540, 34 + 4 * Math.sin(t * 3), 0, Math.PI * 2); c.stroke();
        c.beginPath(); c.moveTo(1048, 516); c.lineTo(1150, 430); c.lineTo(1330, 430); c.stroke();
        ty.hud('YOU ARE HERE', 1160, 418, { size: 26, color: PALE });
        c.globalAlpha = 1;
      }
    } });

  add({ id: 'waterfall', t0: 21.89, t1: 23.17, scene: 'waterfall', p: { mode: 'print', signalAt: W(6, 1) }, look: PRINT,
    type: (ty, t) => {
      ty.keyword(t, 'SIGNAL', W(6, 1), { size: 260, y: 600, color: P, plate: css(INK.orange, 0.95) });
      ty.subtitle(t, 6, { y: 980, size: 44, text: 'Your signal here', end: 23.1 });
    } });

  add({ id: 'caught', t0: 23.17, t1: 24.79, scene: 'roto', p: R('sd05'), look: PRINT,
    type: (ty, t) => ty.subtitle(t, 6, { y: 990, size: 52, text: 'I think I’ve caught' }) });

  add({ id: 'wow', t0: 24.79, t1: 25.30, scene: 'wow', p: { circleAt: 24.85 }, look: { paper: 0.6, grain: 0.07 } });

  add({ id: 'blink', t0: 25.30, t1: 27.82, scene: 'roto', p: R('sd06'), look: PRINT,
    type: (ty, t) => {
      ty.keyword(t, 'BEATING', W(7, 1), { size: 132, y: 1030, x: 480, maxW: 780, kickAmt: 0.12 });
      ty.keyword(t, 'BLINKING', W(7, 2), { size: 132, y: 1030, x: 1440, maxW: 780, kickAmt: 0.12 });
    } });

  add({ id: 'star', t0: 27.82, t1: 28.64, scene: 'star', p: { mode: 'light' }, look: LIGHT,
    type: (ty, t) => ty.keyword(t, 'STAR', W(7, 5), { size: 300, y: 900, color: P }) });

  add({ id: 'transit', t0: 28.64, t1: 30.98, scene: 'transit', p: { mode: 'print', t0: 28.64, t1: 30.98 }, look: PRINT,
    type: (ty, t) => {
      ty.subtitle(t, 8, { y: 100, size: 46, text: 'A planet’s transit', end: 30.9 });
      ty.keyword(t, 'TRANSIT', W(8, 2), { size: 170, x: 1580, y: 300, maxW: 600, color: P, plate: css(INK.orange, 0.9) });
    } });

  add({ id: 'transit_eye', t0: 30.98, t1: 35.94, scene: 'roto', p: R('sd07'), look: PRINT,
    type: (ty, t) => ty.stack(t, [8], { x: 60, y: 180, size: 92, lineH: 100, maxW: 440, accent: PALE, fromScale: 1.3,
      filter: (w) => w.t >= 30.9 }) });

  add({ id: 'alone', t0: 35.94, t1: 39.95, scene: 'roto', p: R('sd08'), look: PRINT,
    type: (ty, t) => {
      ty.keyword(t, t < W(9, 3) ? 'HOW COULD WE' : 'HOW COULD WE BE', W(9, 0), { size: 84, y: 118, stretch: 'normal', inDur: t < W(9, 3) ? 0.22 : 0.001 });
      const k = range(t, W(9, 4), 39.9);
      ty.font('Archivo', 200, 900, 'expanded');
      const word = 'ALONE?'; const sp = lerp(0, 60, easeOutCubic(k));
      let x = 960 - (ty.ctx.measureText(word).width + sp * (word.length - 1)) / 2;
      if (t >= W(9, 3)) for (const ch of word) { ty.plateText(ch, x, 1010, P, css(INK.orange, 0.9), [7, 6]); x += ty.ctx.measureText(ch).width + sp; }
    } });

  // ================================================================ BUILD (the other world)
  add({ id: 'chapter', t0: 39.95, t1: 40.78, scene: 'solid', p: { color: [0.01, 0.008, 0.02] },
    look: (t) => ({ grain: 0.05, vignette: 0.2, flash: pulse(t - 39.95, 0.05) * 0.4 }),
    type: (ty, t) => {
      const c = ty.ctx;
      ty.font('NotoSerifDisplay', 210, 900, 'extra-condensed');
      // Echo is fictional. Its HUD cites the real science behind it: the Earth Transit Zone (Kaltenegger & Faherty, Nature 2021)
      const s1 = 'ECHO'; const w1 = c.measureText(s1).width;
      ty.plateText(s1, 960 - w1 / 2, 560, P, css(INK.pink, 0.9), [7, 6]);
      // "second Earth", the usual phrase for an Earth-like exoplanet in both languages
      const zh = '第二地球', ru = 'Вторая Земля';
      ty.font('NotoSansSC', 58, 900); const wz = c.measureText(zh).width;
      ty.font('Unbounded', 44, 800); const wr = c.measureText(ru).width;
      const x0 = 960 - (wz + 60 + wr) / 2;
      c.fillStyle = MINT;
      ty.font('NotoSansSC', 58, 900); c.fillText(zh, x0, 684);
      ty.font('Unbounded', 44, 800); c.fillText(ru, x0 + wz + 60, 680);
      ty.hud('217 LIGHT-YEARS  ·  INSIDE THE EARTH TRANSIT ZONE  ·  IT HAS SEEN US TOO', 960, 780, { align: 'center', size: 22 });
    } });

  add({ id: 'warp', t0: 40.78, t1: 43.94, scene: 'sky',
    p: (t) => ({ mode: 'light', band: 0.8, density: 1.4, warp: smooth(range(t, 40.78, 41.8)) * (1 - range(t, 43.2, 43.94)), zoom: 1 + range(t, 40.78, 43.94) * 0.6 }),
    look: LIGHT,
    type: (ty, t) => {
      const ly = Math.floor(217 * easeInOutCubic(range(t, 40.3, 43.5)));
      ty.hud(`DISTANCE  ${ly} LY`, 90, 1000, { size: 30 });
      ty.hud(`ONE-WAY LATENCY  ${ly} YEARS`, 1830, 1000, { size: 30, align: 'right' });
      ty.decode(t, 'ECHO', 42.3, { size: 120, y: 560 });
      const cap = 'EARTH TRANSIT ZONE  ·  1,715 STARS WITHIN 326 LY COULD HAVE SEEN EARTH CROSS THE SUN IN THE LAST 5,000 YEARS';
      ty.hud(cap.slice(0, Math.floor(clamp((t - 40.9) / 1.2) * cap.length)), 90, 70, { size: 22, plate: css(INK.ink, 0.96) });
      if (t > 42.1) ty.hud('KALTENEGGER & FAHERTY, NATURE 2021', 90, 106, { size: 18, alpha: 0.8 * smooth(range(t, 42.1, 42.5)), plate: css(INK.ink, 0.96 * smooth(range(t, 42.1, 42.5))) });
    } });

  add({ id: 'planet', t0: 43.94, t1: 47.55, scene: 'planet', p: (t, lt) => ({ mode: 'print', radius: 200, zoomRate: 0.32, spin0: 1.2 }), look: PRINT,
    type: (ty, t) => {
      ty.hud('ECHO   ·   SUPER-EARTH   ·   1.7 R⊕   ·   RINGED', 90, 70);
      ty.hud('INHABITED', 1830, 70, { align: 'right', color: css(INK.pink) });
      ty.glyphLine('WE ARE LISTENING', 90, 1010, 30, css(INK.pink));
    } });

  add({ id: 'theircity', t0: 47.55, t1: 49.36, scene: 'otherworld', p: { mode: 'print', view: 'city' }, look: PRINT });
  add({ id: 'theirfield', t0: 49.36, t1: 51.16, scene: 'roto', p: R('se05', { mode: 'print', inkA: INK.violet, inkB: INK.pink, inkC: INK.mint }), look: PRINT,
    type: (ty, t) => ty.decode(t, 'ARE YOU THERE?', 49.7, { size: 90, y: 200, latinColor: P }) });
  add({ id: 'theirtower', t0: 51.16, t1: 52.96, scene: 'otherworld', p: { mode: 'print', view: 'tower' }, look: PRINT });

  // "Before they launch or self-destruct": the whole line stays on screen from its first word to its last (the "or" is
  // easy to miss by ear), each word lighting up as it is sung; it runs under the flips, the title, the launch and the war
  const LINE10 = (ty, t) => ty.line(t, 10, { y: 1022, size: 56, accents: [PALE, PALE, YELLOW, YELLOW, css(INK.red)] });

  // one-beat alternation into the drop
  const bt = A.beats.filter((b) => b > 52.9 && b < 54.8);
  const flip = ['array', 'petals', 'array', 'petals'];
  for (let i = 0; i < bt.length - 1; i++) {
    const sc = flip[i % flip.length];
    add({ id: `flip${i}`, t0: i === 0 ? 52.96 : bt[i], t1: i === bt.length - 2 ? 54.76 : bt[i + 1], scene: sc,
      p: { mode: 'light', choreo: 'snap', cam: i % 2 ? 'high' : 'low' },
      look: (t) => ({ ...LIGHT3D, flash: pulse(t - bt[i], 0.04) * 0.6 }),
      type: (ty, t) => LINE10(ty, t) });
  }

  // ================================================================ DROP 1 / V3 (the filter, keep looking)
  add({ id: 'title', t0: 54.76, t1: 55.45, scene: 'galaxy', p: { mode: 'light', view: 'title' },
    look: (t) => ({ ...LIGHT, invert: t < 54.84 ? 1 : 0, flash: pulse(t - 54.76, 0.06) * 0.5 }),
    type: (ty, t) => { ty.title(t, 54.76, { t1: 55.45 }); LINE10(ty, t); } });

  add({ id: 'launch', t0: 55.45, t1: W(10, 3), scene: 'roto', p: R('se02', { mode: 'light', glow: INK.yellow, glow2: INK.orange, envFill: 1.1 }), look: LIGHT,
    type: (ty, t) => { ty.keyword(t, 'LAUNCH', W(10, 2), { size: 260, y: 330, color: P }); LINE10(ty, t); } });

  // "or": the same launch with a different payload. Missile tracks over the pole, the warheads landing on "self-destruct"
  // (scenes/war.js), the lights going out, and on to the Drake equation's L
  add({ id: 'war', t0: W(10, 3), t1: 57.59, scene: 'war', p: { t0: W(10, 3), tImpact: W(10, 4) },
    look: (t) => {
      const k = t >= W(10, 4) ? Math.exp(-(t - W(10, 4)) / 0.35) : 0;       // the first warheads land on "self-destruct"
      return { ...LIGHT, flash: t >= W(10, 4) ? Math.exp(-(t - W(10, 4)) / 0.07) * 0.5 : 0, ca: 6 * k,
        shakeX: Math.sin(t * 90) * 7 * k, shakeY: Math.cos(t * 77) * 5 * k };
    },
    // the big words sit over the far side of the pole, clear of the cities the warheads land on
    type: (ty, t) => {
      ty.keyword(t, 'OR', W(10, 3), { size: 260, y: 250, color: YELLOW, t1: W(10, 4) - 0.16 });
      ty.keyword(t, 'SELF-DESTRUCT', W(10, 4), { size: 170, y: 245, maxW: 1600, color: P, plate: css(INK.red, 0.95), kickAmt: 0.2 });
      LINE10(ty, t);
    } });

  add({ id: 'drake', t0: 57.59, t1: 61.03, scene: 'drake', p: {}, look: { paper: 0.9, grain: 0.07 },
    type: (ty, t) => {
      ty.terminal(t, [
        { t: W(11, 0), s: '> WEAPONS', color: css(INK.red) },
        { t: W(11, 1), s: '> WARS', color: css(INK.red) },
        { t: W(11, 2), s: '> AND NOW WE’RE', color: INKC },
      ], { x: 90, y: 860, size: 48, color: INKC });
    } });

  add({ id: 'blank', t0: 61.03, t1: 61.45, scene: 'solid', p: { color: [0, 0, 0] }, look: { grain: 0.02, vignette: 0 },
    type: (ty, t) => ty.censor(t, 61.03, 61.45) });

  add({ id: 'keep_array', t0: 61.45, t1: 62.42, scene: 'array', p: { mode: 'light', choreo: 'snapup', t0: 61.45 },
    look: (t) => ({ ...LIGHT3D, invert: t < 61.53 ? 1 : 0, flash: pulse(t - 61.45, 0.05) }),
    type: (ty, t) => ty.keyword(t, 'KEEP ON', W(12, 0), { size: 230, y: 330, color: P }) });

  add({ id: 'keep_yagi', t0: 62.42, t1: 63.23, scene: 'roto', p: R('sd09', { mode: 'light', bg: burstBG({ c1: INK.pale, c2: INK.yellow }) }), look: LIGHT,
    type: (ty, t) => ty.keyword(t, 'LOOKING', W(12, 2), { size: 260, y: 1000, color: P }) });

  add({ id: 'faith', t0: 63.23, t1: 64.89, scene: 'petals', p: { mode: 'light', choreo: 'bloom' }, look: LIGHT3D,
    type: (ty, t) => ty.keyword(t, 'KEEP THE FAITH', W(12, 3), { size: 170, y: 300, maxW: 1500, color: P }) });

  add({ id: 'funding', t0: 64.89, t1: 67.17, scene: 'brutal', p: { view: 'funding', t0: 64.89 }, look: { paper: 0.8, grain: 0.07 } });

  add({ id: 'planetwaits', t0: 67.17, t1: 69.53, scene: 'roto', p: R('se03', { mode: 'print' }), look: PRINT,
    type: (ty, t) => { ty.keyword(t, 'OUR PLANET', W(13, 3), { size: 150, y: 250, color: P }); ty.keyword(t, 'WAITS', W(13, 5), { size: 230, y: 470, color: PALE }); } });

  add({ id: 'transmission', t0: 69.53, t1: 71.14, scene: 'waterfall', p: { mode: 'light', signalAt: 69.6 }, look: LIGHT,
    type: (ty, t) => ty.decode(t, 'FOR YOUR TRANSMISSION', W(14, 0), { size: 100, y: 560, dur: 0.6 }) });

  add({ id: 'vision', t0: 71.14, t1: W(15, 1), scene: 'roto', p: R('sd10', { mode: 'light', bg: { scene: 'galaxy', p: { mode: 'light', view: 'bg' } } }), look: LIGHT,
    type: (ty, t) => ty.keyword(t, 'OUR', W(15, 0), { size: 200, y: 330, x: 420, color: P }) });
  add({ id: 'science', t0: W(15, 1), t1: W(15, 4) - 0.27, scene: 'split',
    p: { left: { scene: 'array', p: { mode: 'light', choreo: 'snap', cam: 'hero' } }, right: { scene: 'petals', p: { mode: 'light', choreo: 'snap', cam: 'high' } } },
    look: LIGHT3D, type: (ty, t) => { ty.keyword(t, 'SCIENCE', W(15, 1), { size: 230, y: 560, color: P }); ty.keyword(t, 'HAS A', W(15, 2), { size: 90, y: 700, color: YELLOW }); } });
  add({ id: 'vision2', t0: W(15, 4) - 0.27, t1: 75.36, scene: 'roto', p: R('sd10', { mode: 'light', lag: 3 / 24, bg: burstBG({ c1: INK.yellow, c2: INK.mint }) }),
    look: (t) => ({ ...LIGHT, flash: pulse(t - W(15, 4), 0.07) * 0.7 }),
    type: (ty, t) => ty.keyword(t, 'VISION', W(15, 4), { size: 330, y: 1000, color: YELLOW }) });

  // ================================================================ DROP 2a / V4 (call and response)
  add({ id: 'care2', t0: 75.36, t1: 77.66, scene: 'roto', p: R('sd11', { mode: 'light', rect: [0.17, 0, 1, 1], bg: burstBG({ c1: INK.mint, c2: INK.yellow, center: [1286, 620] }) }), look: LIGHT,
    type: (ty, t) => ty.stack(t, [16], { x: 70, y: 300, size: 168, lineH: 172, maxW: 700, accent: YELLOW, plate: css(INK.mint, 0.8) }) });

  // Echo's shots from here on are each their own plate, so no view of the other world plays twice
  const ECHO_LIGHT = { mode: 'light', inkA: INK.violet, inkB: INK.pink, inkC: INK.mint, glow: INK.pink, glow2: INK.mint,
    paper: [0.02, 0.01, 0.04], cell: 6, envFill: 0.9 };
  // their sky: the camera tilts from the sea up to the ring and the two moons
  add({ id: 'yearning2', t0: 77.66, t1: W(17, 5), scene: 'roto', p: R('se06', ECHO_LIGHT), look: LIGHT,
    type: (ty, t) => ty.decode(t, 'YOU\u2019RE YEARNING TO SEE', W(17, 0), { size: 84, y: 880 }) });
  // up their space elevator: mint climbers rising through the clouds past the ring
  add({ id: 'lifeoutthere', t0: W(17, 5), t1: 81.00, scene: 'roto', p: R('se07', ECHO_LIGHT), look: LIGHT,
    type: (ty, t) => ty.decode(t, 'THE LIFE OUT THERE', W(17, 5), { size: 120, y: 980, dur: 0.6 }) });

  // their side of "searching": the lone cliff dish opening (the same dish locks onto our Sun at 90.47)
  add({ id: 'searching2', t0: 81.00, t1: 82.20, scene: 'split', p: { left: { scene: 'array', p: { mode: 'light', choreo: 'sweep' } }, right: { scene: 'roto', p: R('se08b', ECHO_LIGHT) } },
    look: LIGHT3D, type: (ty, t) => ty.keyword(t, 'SEARCHING FOR ME', W(18, 0), { size: 130, y: 1000, color: P }) });

  add({ id: 'listen2', t0: 82.20, t1: 84.60, scene: 'roto', p: R('sd12', { mode: 'light', rect: [-0.15, 0, 1, 1], bg: burstBG({ c1: INK.pale, c2: INK.mint, center: [672, 620] }) }), look: LIGHT,
    type: (ty, t) => ty.stack(t, [19], { x: 1130, y: 330, size: 140, lineH: 140, maxW: 740, accent: YELLOW, plate: css(INK.mint, 0.8) }) });

  add({ id: 'journey', t0: 84.60, t1: 90.47, scene: 'journey', p: { t0: 84.60, t1: 90.47 }, look: LIGHT,
    type: (ty, t) => {
      ty.keyword(t, 'A RARE EARTH', W(20, 0), { size: 170, y: 230, color: P, t1: W(20, 3) });
      if (t < 88.4) ty.keyword(t, 'LOOKING FOR A FRIEND', W(20, 3), { size: 110, y: 230, maxW: 1700, color: P });
      else ty.decode(t, 'FRIEND', 88.4, { size: 220, y: 600, dur: 1.2, glyphColor: MINT, latinColor: P });
    } });

  // ================================================================ DROP 2b / V5 (arrival)
  // their side: a lone dish on a cliff above the clouds turns to one faint star, and that star is our Sun — the
  // pale-blue-dot annotation again, from the other side. The plate is mirrored (negative rect width) so the dish faces it.
  add({ id: 'dot2', t0: 90.47, t1: 93.59, scene: 'roto',
    p: (t) => { const z = 1 + 0.07 * smooth(range(t, 90.47, 93.59)); return R('se08', { ...ECHO_LIGHT, envFill: 0.8,
      rect: [0.5 + z / 2, 0.5 - z / 2, -z, z] }); },
    look: LIGHT,
    type: (ty, t) => {
      const c = ty.ctx, sx = 1510, sy = 250;
      const a = smooth(range(t, 90.7, 91.2));
      c.save(); c.globalCompositeOperation = 'lighter';
      const g = c.createRadialGradient(sx, sy, 0, sx, sy, 26);
      g.addColorStop(0, `rgba(190,225,255,${a})`); g.addColorStop(1, 'rgba(0,0,0,0)');
      c.fillStyle = g; c.fillRect(sx - 30, sy - 30, 60, 60); c.restore();
      if (a > 0) {
        c.globalAlpha = a; c.strokeStyle = MINT; c.lineWidth = 2.5;
        c.beginPath(); c.arc(sx, sy, 34 + 4 * Math.sin(t * 3), 0, Math.PI * 2 * a); c.stroke();
        c.beginPath(); c.moveTo(sx - 26, sy + 24); c.lineTo(sx - 110, sy + 110); c.lineTo(sx - 330, sy + 110); c.stroke();
        ty.glyphLine('YOU ARE HERE', sx - 330, sy + 96, 26, MINT);
        ty.hud('SOL  ·  217 LY  ·  3RD PLANET', sx - 330, sy + 146, { size: 22, color: MINT });
        c.globalAlpha = 1;
      }
      ty.decode(t, 'LIVED MY LIFE ON A', W(21, 0), { size: 70, x: 90, align: 'left', y: 170 });
      ty.decode(t, 'PALE BLUE DOT', W(21, 5), { size: 120, x: 90, align: 'left', y: 310, latinColor: PALE });   // clears the SOL label
    } });

  add({ id: 'reply', t0: 93.59, t1: W(22, 2), scene: 'waterfall', p: { mode: 'light', signalAt: 93.62 }, look: LIGHT,
    type: (ty, t) => ty.keyword(t, 'YOUR SIGNAL', W(22, 0), { size: 200, y: 600, color: MINT }) });
  // sd13 take 935323d481 is framed wider: pushed in 1.35x on her face
  add({ id: 'caught2', t0: W(22, 2), t1: 97.45, scene: 'roto', p: R('sd13', { mode: 'print', inkA: INK.klein, inkC: INK.mint, rect: [-0.182, -0.298, 1.35, 1.35] }), look: PRINT,
    type: (ty, t) => ty.stack(t, [22], { x: 90, y: 230, size: 104, lineH: 112, maxW: 700, accent: MINT, fromScale: 1.2, filter: (w) => w.t >= W(22, 2) - 0.05 }) });

  add({ id: 'blinkearth', t0: 97.45, t1: 98.80, scene: 'earth', p: { mode: 'light', blink: 1, view: 'night' }, look: LIGHT,
    type: (ty, t) => ty.keyword(t, 'BEATING', W(23, 1), { size: 200, y: 950, color: P, kickAmt: 0.15 }) });
  // Echo's night side from low orbit, the same framing as Earth's just before: two worlds blinking at each other
  add({ id: 'blinkecho', t0: 98.80, t1: 99.76, scene: 'planet',
    p: { mode: 'light', blink: 1, center: [960, 1060], radius: 900, zoomRate: 0.02, spin0: 0.6, sun: [-1.0, 0.15, -0.45], tilt: 0.5, cities: 'net' }, look: LIGHT,
    type: (ty, t) => ty.keyword(t, 'BLINKING', W(23, 2), { size: 200, y: 950, color: P, kickAmt: 0.15 }) });
  add({ id: 'blinkdance', t0: 99.76, t1: 100.75, scene: 'roto', p: R('sd14', { mode: 'light', rect: [0.1, 0, 0.8, 0.8], bg: burstBG({ c1: INK.yellow, c2: INK.pink, center: [960, 560] }) }), look: LIGHT,
    type: (ty, t) => ty.keyword(t, 'OF A STAR', W(23, 3), { size: 150, y: 190, color: YELLOW, maxW: 1500 }) });

  add({ id: 'mutual', t0: 100.75, t1: 104.34, scene: 'mutual', p: { t0: 100.75, t1: 104.34 }, look: LIGHT,
    type: (ty, t) => ty.stack(t, [24], { x: 90, y: 130, size: 76, lineH: 90, maxW: 1760, stretch: 'normal', accent: YELLOW, fromScale: 1.3, filter: (w) => w.t < 104.3 }) });

  add({ id: 'own', t0: 104.34, t1: 107.79, scene: 'roto', p: R('sd15'), look: PRINT,
    type: (ty, t) => ty.stack(t, [24], { x: 1450, y: 740, size: 80, lineH: 92, maxW: 450, accent: PALE, fromScale: 1.2, filter: (w) => w.t >= 104.3 }) });

  add({ id: 'alone2', t0: 107.79, t1: 112.02, scene: 'split',
    // a column of light comes down to DOT; on Echo their tower sends one up
    p: { left: { scene: 'roto', p: R('sd16', { mode: 'light' }) }, right: { scene: 'roto', p: R('se10', ECHO_LIGHT) } },
    look: (t) => ({ ...LIGHT, flash: range(t, 111.3, 112.02) * 0.9 }),
    type: (ty, t) => {
      ty.keyword(t, 'HOW COULD WE BE', W(25, 0), { size: 84, x: 480, y: 925, color: P, stretch: 'normal', maxW: 840 });
      ty.keyword(t, 'ALONE?', W(25, 4), { size: 150, x: 480, y: 1050, color: YELLOW, maxW: 840 });
      const gw = 'HOW COULD WE BE'.length * 46 * 0.9;
      if (t > W(25, 0)) ty.glyphLine('HOW COULD WE BE', 1440 - gw / 2, 905, 46, MINT);
      if (t > W(25, 4)) ty.glyphLine('ALONE', 1440 - 5 * 84 * 0.9 / 2, 1020, 84, YELLOW);
    } });

  // ================================================================ FINAL DROP (contact) — instrumental
  const fb = A.beats.filter((b) => b >= 112.0 && b < 123.5);
  const B2 = (i) => fb[i];                     // i-th beat of the final drop (0 = 112.02)
  const galaxyBG = { scene: 'galaxy', p: { mode: 'light', view: 'bg' } };
  add({ id: 'contact', t0: 112.02, t1: B2(2), scene: 'clash', p: {},
    look: (t) => ({ ...LIGHT, invert: t < 112.1 ? 1 : 0, flash: pulse(t - 112.02, 0.08) }),
    type: (ty, t) => ty.decode(t, 'CONTACT', 112.08, { size: 210, y: 330, dur: 0.32, stagger: 0.02, latinColor: YELLOW }) });
  add({ id: 'dance_split', t0: B2(2), t1: B2(4), scene: 'split', p: { left: { scene: 'array', p: { mode: 'light', choreo: 'dance', cam: 'low' } }, right: { scene: 'petals', p: { mode: 'light', choreo: 'dance' } } }, look: LIGHT3D });
  add({ id: 'dance2', t0: B2(4), t1: B2(6), scene: 'roto', p: R('sd17', { mode: 'light', bg: burstBG({ c1: INK.mint, c2: INK.yellow }) }), look: LIGHT });
  add({ id: 'lightsticks', t0: B2(6), t1: B2(8), scene: 'earth', p: { mode: 'light', blink: 2, view: 'night', blinkT0: B2(6) }, look: LIGHT });
  add({ id: 'dance3', t0: B2(8), t1: B2(10), scene: 'roto', p: R('sd17', { mode: 'light', bg: galaxyBG }), look: LIGHT });
  // their city at night, every terrace lighting up in a wave: Earth's light-stick ocean, from their side
  add({ id: 'echoblink', t0: B2(10), t1: B2(12), scene: 'roto', p: R('se09', { ...ECHO_LIGHT, glow: INK.mint, glow2: INK.pink, envFill: 1.5, lineGain: 1.6 }),
    look: (t) => ({ ...LIGHT, flash: A.kick(t, 0.12) * 0.12 }) });
  add({ id: 'galaxyweb', t0: B2(12), t1: 120.90, scene: 'galaxy', p: { mode: 'light', view: 'web', t0: B2(12), t1: 120.90 }, look: LIGHT,
    type: (ty, t) => { ty.hud('CONTACT GRAPH  ·  ' + Math.floor(1 + 640 * Math.min(1, Math.max(0, (t - 117.6) / 3.0))) + ' CIVILIZATIONS', 90, 1010, { size: 26, color: YELLOW }); } });
  add({ id: 'stillhere', t0: 120.90, t1: 123.40, scene: 'roto', p: R('sd18', { mode: 'light', bg: galaxyBG, rect: [0.25, 0, 0.88, 0.88] }),
    look: LIGHT, type: (ty, t) => {
      ty.decode(t, 'STILL', 121.0, { size: 220, x: 80, align: 'left', y: 470, dur: 1.0, latinColor: YELLOW });
      ty.decode(t, 'HERE.', 121.2, { size: 220, x: 80, align: 'left', y: 700, dur: 1.0, latinColor: YELLOW });
      ty.hud('BEACON  ·  ORIGIN ECHO  ·  SENT 1809  ·  217 YEARS IN FLIGHT', 86, 800, { size: 24, color: MINT, alpha: smooth(range(t, 121.9, 122.3)) });
    } });

  // ================================================================ OUTRO
  // the song ends at 127.96; the card holds for their beacon ("Still here." in the sound design) and fades out
  add({ id: 'end', t0: 123.40, t1: 129.7, scene: 'endcard', p: {}, look: (t) => ({ paper: 1, grain: 0.05, fade: 1 - range(t, 129.0, 129.6) }) });

  // sanity: contiguous, non-overlapping
  S.sort((a, b) => a.t0 - b.t0);
  for (let i = 1; i < S.length; i++) if (Math.abs(S[i].t0 - S[i - 1].t1) > 1e-6) console.warn('gap/overlap', S[i - 1].id, S[i - 1].t1, S[i].id, S[i].t0);
  return S;
}


// Global rhythm layer: every frame gets the song's pulse. Drops punch on kicks; section hits get impact frames.
export function buildGlobalPost(A) {
  const drops = [[54.76, 61.03], [61.45, 75.36], [75.36, 90.47], [90.47, 104.9], [112.02, 123.4]];
  const hits = [54.76, 61.45, 76.31, 90.63, 112.02];
  const inDrop = (t) => drops.some(([a, b]) => t >= a && t < b);
  return (t, shot) => {
    const g = {};
    const k = A.kick(t, 0.09);
    const sn = A.snare(t, 0.06);
    if (inDrop(t)) {
      g.zoom = 1 + 0.018 * k;
      g.ca = 2.5 * k;
      g.shakeX = (Math.sin(t * 97.0) * 2.2) * k; g.shakeY = (Math.cos(t * 83.0) * 1.6) * k;
    }
    g.misreg = 2.2 * sn;
    for (const h of hits) {
      const d = t - h;
      if (d >= 0 && d < 2 / 24) g.invert = 1;          // two-frame impact frame
      else if (d >= 2 / 24 && d < 0.25) g.flash = (1 - (d - 2 / 24) / 0.17) * 0.35;
    }
    return g;
  };
}
