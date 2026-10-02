import librosa, numpy as np, scipy.signal as ss, json
sr=48000
y,_=librosa.load('../Rewind (4).mp3',sr=sr,mono=True)
sos=ss.butter(4,[35,130],'band',fs=sr,output='sos'); low=ss.sosfiltfilt(sos,y)
hop=96  # 2ms
env=np.sqrt(np.convolve(low**2,np.ones(240)/240,'same'))[::hop]
denv=np.maximum(0,np.diff(np.log(env+1e-5),prepend=0))
sm=np.convolve(denv,np.ones(3)/3,'same')
print(np.percentile(sm,[50,90,99,99.9]),flush=True)
pk,_=ss.find_peaks(sm,height=0.05,distance=int(0.25*sr/hop))
t=pk*hop/sr
# keep strong ones: env after onset large
lev=np.array([20*np.log10(env[min(p+10,len(env)-1)]+1e-9) for p in pk])
st=sm[pk]
np.save('kicks_raw.npy',np.stack([t,lev,st]))
for ti,l,s in zip(t,lev,st):
    print(f"{ti:8.3f} {l:6.1f} {s:5.2f}")
