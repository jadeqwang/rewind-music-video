import librosa, numpy as np, scipy.stats as st
sr=22050; hop=64; fps=sr/hop
oe=np.load('oe_perc.npy')
# local tempo from comb fits every 2s with 8s windows
def score(T,ph,a,b):
    ts=np.arange(ph,b,T); ts=ts[ts>=a]; idx=(ts*fps).astype(int); idx=idx[idx<len(oe)-2]
    return np.mean([oe[max(0,i-1):i+2].max() for i in idx])
cent=[];Tl=[]
for a in np.arange(0,225,2.0):
    best=(0,0)
    for T in np.arange(0.455,0.482,0.0005):
        s=max(score(T,ph,a,a+8) for ph in np.arange(a,a+T,0.004))
        if s>best[0]: best=(s,T)
    cent.append(a+4); Tl.append(best[1])
cent=np.array(cent); Tl=np.array(Tl)
# median smooth
from scipy.ndimage import median_filter
Ts=median_filter(Tl,5,mode='nearest')
np.save('tempo_curve.npy',np.stack([cent,Tl,Ts]))
nfr=len(oe); tfr=np.arange(nfr)/fps
bpm=60/np.interp(tfr,cent,Ts)
tempo,beats=librosa.beat.beat_track(onset_envelope=oe,sr=sr,hop_length=hop,bpm=bpm,tightness=300,trim=False,units='time')
np.save('beats_raw.npy',beats)
d=np.diff(beats)
print(len(beats), beats[:10])
for i in range(0,len(beats)-1,4):
    print(f"{beats[i]:8.3f} {' '.join(f'{x:.3f}' for x in d[i:i+4])}")
