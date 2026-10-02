import librosa, numpy as np
sr=22050
y,_=librosa.load('stems/no_vocals.wav',sr=sr)
r=np.load('mm_db_mix.npy'); beats=r[:,0]
hop=512
C=librosa.feature.chroma_cqt(y=y,sr=sr,hop_length=hop)
M=librosa.feature.mfcc(y=y,sr=sr,hop_length=hop,n_mfcc=20)
S=librosa.power_to_db(librosa.feature.melspectrogram(y=y,sr=sr,hop_length=hop,n_mels=40))
bf=librosa.time_to_frames(beats,sr=sr,hop_length=hop)
F=np.vstack([librosa.util.normalize(C,axis=0)*1.0, (M-M.mean(1,keepdims=True))/M.std(1,keepdims=True), (S-S.mean(1,keepdims=True))/S.std(1,keepdims=True)])
Fb=librosa.util.sync(F,bf,aggregate=np.median)
Fb=Fb/np.linalg.norm(Fb,axis=0,keepdims=True)
SSM=Fb.T@Fb
K=8
g=np.outer(np.r_[-np.ones(K),np.ones(K)],np.r_[-np.ones(K),np.ones(K)])*-1
n=SSM.shape[0]; nov=np.zeros(n)
for i in range(K,n-K):
    nov[i]=np.sum(SSM[i-K:i+K,i-K:i+K]*g)
nov=nov/nov.max()
bt=np.r_[0,beats]
import scipy.signal as ss
pk,_=ss.find_peaks(nov,height=0.25,distance=6)
for p in pk: print(f"{bt[p]:7.2f} nov {nov[p]:.2f}")
