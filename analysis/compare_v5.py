"""Timing check Rewind (4) vs Rewind (5): onset-envelope cross-correlation (global + 10 s windows),
band-energy envelopes, level differences by section. Writes analysis/v5_compare.json"""
import os, subprocess, json, numpy as np, librosa
HERE = os.path.dirname(os.path.abspath(__file__)); SR = 48000
def dec(p):
    raw = subprocess.run(["ffmpeg","-v","error","-i",p,"-map","0:a","-f","f32le","-ac","2","-ar",str(SR),"-"],capture_output=True,check=True).stdout
    return np.frombuffer(raw,np.float32).reshape(-1,2).copy()
a = dec(os.path.join(HERE,'..','Rewind (4).mp3')); b = dec(os.path.join(HERE,'..','Rewind (5).mp3'))
print('len v4 %.4f v5 %.4f' % (len(a)/SR, len(b)/SR))
HOP = 480  # 100 Hz
def ons(x): return librosa.onset.onset_strength(y=x.mean(1), sr=SR, hop_length=HOP, n_mels=128, lag=1, max_size=1)
oa, ob = ons(a), ons(b)
def xc(u, v, maxlag):
    u = (u-u.mean())/(u.std()+1e-9); v = (v-v.mean())/(v.std()+1e-9)
    n = min(len(u),len(v)); u, v = u[:n], v[:n]
    lags = np.arange(-maxlag, maxlag+1); r = []
    for L in lags:
        if L >= 0: r.append(np.dot(u[L:], v[:n-L])/(n-L))
        else: r.append(np.dot(u[:n+L], v[-L:])/(n+L))
    r = np.array(r); k = int(np.argmax(r))
    # parabolic sub-sample
    if 0 < k < len(r)-1:
        d = 0.5*(r[k-1]-r[k+1])/(r[k-1]-2*r[k]+r[k+1])
    else: d = 0
    return (lags[k]+d)*10.0, float(r[k])   # ms; positive => v5 EARLIER than v4 (v4[t+L]=v5[t])
out = {}
g, rg = xc(oa, ob, 100); print('global onset xcorr lag %.2f ms r=%.3f' % (g, rg)); out['global'] = dict(lag_ms=g, r=rg)
win = []
for s in range(0, int(len(ob)/100)-5, 10):
    i0, i1 = s*100, min((s+10)*100, len(oa), len(ob))
    # local: correlate v5 window with v4 around the same position, lag +-300 ms
    u = ob[i0:i1]; best = None
    rs = []
    for L in range(-30, 31):
        if i0+L < 0 or i1+L > len(oa): rs.append(-1); continue
        v = oa[i0+L:i1+L]; rs.append(np.corrcoef(u, v)[0,1])
    rs = np.array(rs); k = int(np.argmax(rs))
    d = 0.5*(rs[k-1]-rs[k+1])/(rs[k-1]-2*rs[k]+rs[k+1]) if 0<k<len(rs)-1 else 0
    win.append(dict(t0=s, lag_ms=round((k-30+d)*10,2), r=round(float(rs[k]),3), r_at0=round(float(rs[30]),3)))
    print(win[-1])
out['windows'] = win
# fine: 1 ms resolution envelope xcorr per window (HF band onset) to get sub-10ms precision
H2 = 48
def ons2(x): return librosa.onset.onset_strength(y=x.mean(1), sr=SR, hop_length=H2, n_mels=64)
pa, pb = ons2(a), ons2(b)
fine = []
for s in range(0, 230, 10):
    i0, i1 = s*1000, min((s+10)*1000, len(pa), len(pb))
    u = pb[i0:i1]; rs = []
    for L in range(-20, 21):
        if i0+L < 0 or i1+L > len(pa): rs.append(-1); continue
        rs.append(np.corrcoef(u, pa[i0+L:i1+L])[0,1])
    rs = np.array(rs); k = int(np.argmax(rs)); fine.append(dict(t0=s, lag_ms=k-20, r=round(float(rs[k]),3)))
print('fine 1ms:', [(f['t0'], f['lag_ms'], f['r']) for f in fine])
out['fine_1ms'] = fine
np.save('/tmp/claude-0/sc/oa.npy', oa); np.save('/tmp/claude-0/sc/ob.npy', ob)
json.dump(out, open(os.path.join(HERE,'v5_compare.json'),'w'), indent=1)
