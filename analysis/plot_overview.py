import json, numpy as np, librosa, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
T=json.load(open('timing.json')); E=json.load(open('envelopes.json'))
sr=22050
y,_=librosa.load('../Rewind (4).mp3',sr=sr)
M=librosa.power_to_db(librosa.feature.melspectrogram(y=y,sr=sr,n_fft=2048,hop_length=512,n_mels=128,fmax=11000),ref=np.max)
dur=T['duration']
cols={'intro':'#555','verse1':'#2a7','build1':'#d90','tapestop1':'#f0f','silence1':'#fff','drop1':'#e22','verse3':'#2a7','build2':'#d90',
'tapestop2':'#f0f','silence2':'#fff','drop2':'#e22','breakdown':'#38f','build3':'#d90','silence3':'#fff','final_drop':'#e22','instrumental':'#a5f','end':'#555'}
rows=[(0,60),(60,120),(120,180),(180,dur)]
fig,axs=plt.subplots(len(rows)*2,1,figsize=(28,30),gridspec_kw=dict(height_ratios=[3,1]*len(rows)))
t_env=np.arange(E['n_frames'])/E['fps']
for r,(a,b) in enumerate(rows):
    ax=axs[2*r]; ax2=axs[2*r+1]
    i0,i1=int(a*sr/512),int(b*sr/512)
    ax.imshow(M[:,i0:i1],origin='lower',aspect='auto',extent=[a,b,0,128],cmap='magma',vmin=-70)
    for s in T['sections']:
        if s['end']<a or s['start']>b: continue
        ax.axvspan(max(a,s['start']),min(b,s['end']),ymin=0.93,ymax=1,color=cols.get(s['name'],'#888'),alpha=.9)
        ax.axvline(s['start'],color='w',lw=1.5)
        if a<=s['start']<b: ax.text(s['start']+0.1,119,s['name'],color='k',fontsize=11,weight='bold',va='center')
    for d in T['downbeats']:
        if a<=d<b: ax.axvline(d,ymax=0.04,color='c',lw=1)
    for e in T['events']:
        if a<=e['t']<b and e['type'] not in ('section',):
            c={'drop':'red','braam':'orange','tapestop':'magenta','silence':'white','shot':'yellow','shot_sfx':'yellow','inhale':'lime','end':'red'}.get(e['type'],'w')
            ax.axvline(e['t'],ymin=0.05,ymax=0.9,color=c,lw=1.2,ls='--')
            ax.text(e['t'],100 if e['type'] in('braam','drop') else 85,e['type'],color=c,fontsize=9,rotation=90)
    for l in T['lines']:
        if a<=l['start']<b:
            ax.plot([l['start'],l['end']],[6,6],color='lime',lw=4)
            ax.text(l['start'],9,l['text'][:38],color='lime',fontsize=9)
    ax.set_xlim(a,b); ax.set_xticks(np.arange(np.ceil(a),b,2)); ax.set_ylabel('mel')
    m=(t_env>=a)&(t_env<b)
    for k,c in [('low','r'),('mid','orange'),('high','c'),('vocal','lime'),('onset','w')]:
        ax2.plot(t_env[m],E[k][m] if isinstance(E[k],np.ndarray) else np.array(E[k])[m],color=c,lw=0.8,label=k)
    ax2.set_facecolor('#111'); ax2.set_xlim(a,b); ax2.set_ylim(0,1.05); ax2.set_xticks(np.arange(np.ceil(a),b,2))
    if r==0: ax2.legend(loc='upper left',ncol=5,fontsize=9)
plt.suptitle(f"Rewind - timing overview  ({T['bpm']} BPM median; cyan ticks = downbeats)",fontsize=16)
plt.tight_layout(); plt.savefig('overview.png',dpi=60)
