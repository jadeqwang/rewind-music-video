// timeline.js: the shot registry. A shot fn(t, lt, dur, shot) paints the entire frame.
const SHOTS = [];
function shot(name, t0, t1, fn, opts = {}) { SHOTS.push({ name, t0, t1, fn, opts }); }
function shotAt(t) {
  for (let i = SHOTS.length - 1; i >= 0; i--) if (t >= SHOTS[i].t0 && t < SHOTS[i].t1) return SHOTS[i];
  return null;
}
// time helpers bound to the song
const B = n => beatTime(n);                         // time of beat n
const secT = name => TM.sections.find(s => s[0] === name);
