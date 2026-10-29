"""Background motion-field regression and binary shape registration.
No simulation IDs, manual target path, or future video frames are used here.
"""
import cv2,numpy as np

def regular_flow_residual(previous,current,valid,center,dis=None):
    h,w=current.shape;yy,xx=np.mgrid[:h,:w]
    if dis is None:dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    flow=dis.calc(previous,current,None)
    X=(xx-w/2)/(w/2);Y=(yy-h/2)/(h/2)
    design=np.stack([np.ones_like(X),X,Y,X*Y,X*X,Y*Y],axis=-1).astype(np.float32)
    bg=(valid>0)&((xx-center[0])**2+(yy-center[1])**2>115**2)&(xx%6==0)&(yy%6==0)
    a=design[bg];b=flow[bg];weight=np.ones(len(a),np.float32)
    if len(a)<20:return np.zeros_like(current,np.float32),{'flow_ok':False,'flow_threshold':0.}
    for _ in range(5):
        root=np.sqrt(weight[:,None]);coeff=np.linalg.lstsq(a*root,b*root,rcond=None)[0]
        error=np.linalg.norm(b-a@coeff,axis=1);scale=max(.15,float(np.median(error))*1.48)
        weight=np.minimum(1,1.5*scale/(error+1e-5))
    expected=design@coeff;residual=np.linalg.norm(flow-expected,axis=2)
    noise=float(np.median(residual[bg]));threshold=max(.45,noise+2.5*float(np.median(np.abs(residual[bg]-noise))))
    signal=np.maximum(0,residual-threshold);signal[valid==0]=0
    return cv2.GaussianBlur(signal,(0,0),3),{'flow_ok':True,'flow_threshold':threshold,'background_flow_error':noise}

class ShapeFitter:
    def __init__(self,initial_mask):
        self.templates=[]
        # Fixed first-frame shape prevents drift from progressively learning background.
        mask=(initial_mask>0).astype(np.uint8)
        side=int(np.ceil(np.hypot(*mask.shape)))+12
        canvas=np.zeros((side,side),np.uint8)
        y=(side-mask.shape[0])//2;x=(side-mask.shape[1])//2
        canvas[y:y+mask.shape[0],x:x+mask.shape[1]]=mask
        for scale in [.85,1.,1.15]:
            for angle in range(0,180,15):
                rotated=cv2.warpAffine(canvas,cv2.getRotationMatrix2D((side/2,side/2),angle,scale),(side,side))
                small=cv2.resize(rotated,(side//2,side//2),interpolation=cv2.INTER_AREA).astype(np.float32)
                small=cv2.GaussianBlur(small,(0,0),.6)
                self.templates.append((small,angle,scale))
        self.side=side
    def fit(self,evidence,prediction,radius=100,allowed_centers=None):
        h,w=evidence.shape
        # This binarization is deliberate: a brighter edge gets no extra voting power.
        binary=(evidence>0).astype(np.float32)
        x0=max(0,int(prediction[0]-radius-self.side/2));x1=min(w,int(prediction[0]+radius+self.side/2))
        y0=max(0,int(prediction[1]-radius-self.side/2));y1=min(h,int(prediction[1]+radius+self.side/2))
        roi=cv2.resize(binary[y0:y1,x0:x1],((x1-x0)//2,(y1-y0)//2),interpolation=cv2.INTER_AREA)
        if float(roi.sum())<25:return None
        best=None
        for template,angle,scale in self.templates:
            th,tw=template.shape
            if min(roi.shape)<max(template.shape):continue
            result=cv2.matchTemplate(roi,template,cv2.TM_CCORR_NORMED)
            yy,xx=np.mgrid[:result.shape[0],:result.shape[1]]
            cx=x0+(xx+tw/2)*2;cy=y0+(yy+th/2)*2
            distance=(cx-prediction[0])**2+(cy-prediction[1])**2
            result[distance>radius**2]=-1
            if allowed_centers is not None:
                valid_x=np.clip(cx.astype(int),0,w-1);valid_y=np.clip(cy.astype(int),0,h-1)
                result[allowed_centers[valid_y,valid_x]==0]=-1
            ranked=result-.035*distance/(radius**2)
            _,score,_,(ix,iy)=cv2.minMaxLoc(ranked)
            if result[iy,ix]<0:continue
            if best is None or score>best['score']:
                best={'center':np.array([x0+(ix+tw/2)*2,y0+(iy+th/2)*2]),'score':float(score),'match':float(result[iy,ix]),'angle':angle,'scale':scale}
        return best
