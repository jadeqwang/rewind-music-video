import librosa, numpy as np, sys, scipy.signal as ss
sr=22050
a,b=float(sys.argv[1]),float(sys.argv[2])
v,_=librosa.load('stems/vocals.wav',sr=sr,offset=a,duration=b-a)
hop=110
oe=librosa.onset.onset_strength(y=v,sr=sr,hop_length=hop,n_mels=64,fmax=8000)
r=20*np.log10(librosa.feature.rms(y=v,frame_length=882,hop_length=hop)[0]+1e-6)
f0,vf,_=librosa.pyin(v,fmin=80,fmax=800,sr=sr,frame_length=1764,hop_length=hop)
pk,_=ss.find_peaks(oe,prominence=np.percentile(oe,85),distance=8)
print('onsets:',' '.join(f'{a+p*hop/sr:.2f}' for p in pk))
s=''
for i in range(0,len(r),10):
    t=a+i*hop/sr
    s+=f"{t:.2f}:{r[i]:.0f}/{'' if np.isnan(f0[i]) else int(f0[i])} "
print(s)
