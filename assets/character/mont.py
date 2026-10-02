import cv2,sys,numpy as np,os
W=int(os.environ.get("W",900)); fs=sys.argv[2:]; tiles=[]
for f in fs:
  im=cv2.imread(f); im=cv2.resize(im,(W,int(im.shape[0]*W/im.shape[1])))
  cv2.putText(im,os.path.basename(f),(8,28),0,0.8,(0,0,255),2); tiles.append(im)
H=max(t.shape[0] for t in tiles); tiles=[cv2.copyMakeBorder(t,0,H-t.shape[0],0,0,0) for t in tiles]
rows=[np.hstack(tiles[i:i+2] + ([np.zeros_like(tiles[0])] if len(tiles[i:i+2])==1 else [])) for i in range(0,len(tiles),2)]
cv2.imwrite(sys.argv[1],np.vstack(rows),[cv2.IMWRITE_JPEG_QUALITY,85])
