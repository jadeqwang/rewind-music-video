import librosa, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sr=22050
regs=[(41,46.5),(100.5,106),(132,138),(147,153),(168,173),(225.5,232.44)]
fig,ax=plt.subplots(len(regs),2,figsize=(26,4*len(regs)))
for r,(a,b) in enumerate(regs):
  for c,fn in enumerate(['stems/no_vocals.wav','stems/vocals.wav']):
    y,_=librosa.load(fn,sr=sr,offset=a,duration=b-a)
    S=librosa.amplitude_to_db(np.abs(librosa.stft(y,n_fft=4096,hop_length=64)),ref=np.max)
    f=librosa.fft_frequencies(sr=sr,n_fft=4096); m=f<4000
    ax[r,c].imshow(S[m],origin='lower',aspect='auto',extent=[a,b,0,4000],cmap='magma',vmin=-80)
    ax[r,c].set_xticks(np.arange(a,b,0.1),minor=True); ax[r,c].set_xticks(np.arange(np.ceil(a),b,0.5))
    ax[r,c].grid(which='both',axis='x',alpha=.25,color='w'); ax[r,c].set_title(fn+f' {a}-{b}')
plt.tight_layout(); plt.savefig('/tmp/claude-0/-home-user-rewind-music-video/6b28fe5a-ebc4-5b63-aa64-c3b0ecf3f843/scratchpad/gaps.png',dpi=45)
