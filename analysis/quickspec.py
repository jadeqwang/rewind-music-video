import librosa, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, soundfile as sf
y,sr=librosa.load('../Rewind (4).mp3',sr=22050)
v,_=librosa.load('stems/vocals.wav',sr=22050)
fig,ax=plt.subplots(8,1,figsize=(30,32))
for k in range(4):
  a,b=k*60,(k+1)*60
  for j,(sig,nm) in enumerate([(y,'mix'),(v,'voc')]):
    S=librosa.amplitude_to_db(np.abs(librosa.stft(sig[int(a*sr):int(b*sr)],n_fft=2048,hop_length=256)),ref=1.0)
    M=librosa.feature.melspectrogram(S=librosa.db_to_amplitude(S)**2,sr=sr,n_mels=128)
    axx=ax[2*k+j]
    axx.imshow(librosa.power_to_db(M),origin='lower',aspect='auto',extent=[a,b,0,128],cmap='magma',vmin=-60,vmax=30)
    axx.set_xticks(np.arange(a,b+1,1)); axx.grid(axis='x',alpha=.3); axx.set_ylabel(nm)
plt.tight_layout(); plt.savefig('/tmp/claude-0/-home-user-rewind-music-video/6b28fe5a-ebc4-5b63-aa64-c3b0ecf3f843/scratchpad/quick.png',dpi=40)
