import librosa, numpy as np
sr=22050; hop=64
y,_=librosa.load('../Rewind (4).mp3',sr=sr,mono=True)
yh,yp=librosa.effects.hpss(y)
oe=librosa.onset.onset_strength(y=yp,sr=sr,hop_length=hop,n_mels=64)
oe=oe/np.percentile(oe,99)
np.save('oe_perc.npy',oe)
fps=sr/hop
def score(T,ph,a,b):
    ts=np.arange(ph,b,T); ts=ts[ts>=a]
    idx=(ts*fps).astype(int)
    # max in +-1 frame
    return np.mean([oe[max(0,i-1):i+2].max() for i in idx])
def fit(a,b,Ts=np.arange(0.44,0.50,0.0002)):
    best=(0,0,0)
    for T in Ts:
        for ph in np.arange(a,a+T,0.003):
            s=score(T,ph,a,b)
            if s>best[0]: best=(s,T,ph)
    return best
import sys
for a,b in [(7,43.3),(14.5,43.3),(45.1,102.5),(104.7,134.5),(104.7,148),(171.5,229),(163,171)]:
    s,T,ph=fit(a,b)
    print(f"seg {a}-{b}: T={T:.4f} bpm={60/T:.2f} phase={ph:.3f} score={s:.2f}")
