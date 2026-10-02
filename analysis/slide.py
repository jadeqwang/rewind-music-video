import numpy as np
oe=np.load('oe_perc.npy'); fps=22050/64
def score(T,ph,a,b):
    ts=np.arange(ph,b,T); ts=ts[ts>=a]; idx=(ts*fps).astype(int)
    return np.mean([oe[max(0,i-1):i+2].max() for i in idx])
def fit(a,b,Ts):
    best=(0,0,0)
    for T in Ts:
        for ph in np.arange(a,a+T,0.002):
            s=score(T,ph,a,b)
            if s>best[0]: best=(s,T,ph)
    return best
for a in np.arange(7,226,4.0):
    s,T,ph=fit(a,a+8,np.arange(0.455,0.48,0.0005))
    print(f"{a:6.1f} T={T:.4f} bpm={60/T:6.2f} ph={ph:.3f} s={s:.2f}")
