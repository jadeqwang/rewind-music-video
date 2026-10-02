import librosa, numpy as np, matplotlib, sys; matplotlib.use('Agg'); import matplotlib.pyplot as plt
a,b,out=float(sys.argv[1]),float(sys.argv[2]),sys.argv[3]
sr=22050
y,_=librosa.load('../Rewind (4).mp3',sr=sr,offset=a,duration=b-a)
v,_=librosa.load('stems/vocals.wav',sr=sr,offset=a,duration=b-a)
fig,ax=plt.subplots(2,1,figsize=(24,9),sharex=True)
for axx,sig,nm in [(ax[0],y,'mix'),(ax[1],v,'vocals')]:
    M=librosa.feature.melspectrogram(y=sig,sr=sr,n_fft=2048,hop_length=128,n_mels=128,fmax=11000)
    axx.imshow(librosa.power_to_db(M,ref=np.max),origin='lower',aspect='auto',extent=[a,a+len(sig)/sr,0,128],cmap='magma',vmin=-70)
    axx.set_ylabel(nm); axx.grid(axis='x',color='w',alpha=.3)
ax[1].set_xticks(np.arange(np.ceil(a),b,0.5 if b-a<25 else 1)); plt.xticks(rotation=90,fontsize=7)
beats=np.load('beats_raw.npy')
for t in beats[(beats>a)&(beats<b)]: ax[0].axvline(t,ymax=0.05,color='c')
plt.tight_layout(); plt.savefig(out,dpi=55)
