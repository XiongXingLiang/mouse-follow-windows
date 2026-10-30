"""Stateful live adapter of the tested causal geometry tracker."""
from dataclasses import dataclass
import time
import cv2,numpy as np
from .background import viewport_mask,compensated_residual
from .motion_geometry import ShapeFitter,regular_flow_residual

@dataclass
class TrackResult:
    center:tuple[float,float]
    score:float
    mode:str
    angle:float=0.
    scale:float=1.

def find_white(frame,allowed=None):
    hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,np.array([0,0,232]),np.array([180,45,255]))
    mask[:150]=0;mask[-80:]=0;mask[:,:45]=0;mask[:,-45:]=0
    if allowed is not None:mask[allowed==0]=0
    n,_,stats,centers=cv2.connectedComponentsWithStats(mask)
    choices=[]
    for j in range(1,n):
        x,y,w,h,area=stats[j]
        if 400<=area<=15000 and 28<=w<=180 and 28<=h<=180 and .4<w/h<2.5:
            choices.append(j)
    if not choices:return None
    j=max(choices,key=lambda j:stats[j,4]);x,y,w,h,_=stats[j]
    return (int(x),int(y),int(w),int(h)),mask[y:y+h,x:x+w],centers[j]

class VisualTracker:
    def __init__(self):self.reset()
    def reset(self):
        self.center=None;self.velocity=np.zeros(2);self.frames=[];self.started=None;self.missing=0;self.dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    def update(self,frame,timestamp=None):
        now=time.monotonic() if timestamp is None else timestamp
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY);hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
        if self.center is None:
            white=find_white(frame)
            if white is None:return None
            self.initial,mask,centroid=white;x,y,bw,bh=self.initial
            self.center=np.array([x+bw/2,y+bh/2],float);self.fitter=ShapeFitter(mask);self.valid=viewport_mask(gray.shape)
            self.yy,self.xx=np.mgrid[:gray.shape[0],:gray.shape[1]];self.started=now;self.frames=[gray];self.last_time=now
            return TrackResult(tuple(self.center),1.,'white')
        age=now-self.started;dt=max(.01,min(.2,now-self.last_time));self.last_time=now
        x,y,bw,bh=self.initial;previous=self.frames[max(0,len(self.frames)-3)]
        # While the initial bright target remains visible, expensive motion and
        # shape estimation cannot improve on its directly observed center.
        prediction=self.center+.5*self.velocity*min(2.,dt*30)
        distance=(self.xx-prediction[0])**2+(self.yy-prediction[1])**2
        nearby=self.valid.copy()
        nearby[distance>(max(bw,bh)*.8)**2]=0
        white=find_white(frame,nearby)
        if white is not None:
            box,_,_=white;wx,wy,ww,wh=box;old=self.center.copy()
            self.center=np.array([wx+ww/2,wy+wh/2],float)
            self.center=np.clip(self.center,[40,90],[gray.shape[1]-25,gray.shape[0]-80])
            self.velocity=.6*self.velocity+.4*np.clip((self.center-old)/max(.5,dt*30),-12,12)
            self.frames.append(gray)
            if len(self.frames)>4:self.frames.pop(0)
            self.missing=0
            return TrackResult(tuple(map(float,self.center)),1.,'white')
        signal,_,_,diag=compensated_residual(previous,gray,self.valid,self.center)
        flow,flowdiag=regular_flow_residual(previous,gray,self.valid,self.center,self.dis)
        prediction=self.center+.5*self.velocity*min(2.,dt*30)
        distance=(self.xx-prediction[0])**2+(self.yy-prediction[1])**2;local=(self.valid>0)&(distance<125**2)
        if not local.any():self.reset();return None
        threshold=max(5.,float(signal[local].max())*.28)
        photo=(signal>threshold).astype(np.uint8);motion=(flow>max(.35,float(np.percentile(flow[local],96))*.2)).astype(np.uint8)
        evidence=(photo&cv2.dilate(motion,np.ones((15,15),np.uint8)))*255
        evidence=cv2.morphologyEx(evidence,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8));evidence[~local]=0
        text=cv2.inRange(hsv,np.array([70,45,60]),np.array([125,255,255]));text=cv2.dilate(text,np.ones((27,27),np.uint8));evidence[text>0]=0
        allowed=self.valid.copy()
        if age<1.6:allowed[:int(y+bh/2-20)]=0;evidence[allowed==0]=0
        n,labels,stats,_=cv2.connectedComponentsWithStats(evidence);keep=np.zeros(n,np.uint8)
        for j in range(1,n):
            if stats[j,4]>=35:keep[j]=255
        evidence=keep[labels];fit=self.fitter.fit(evidence,prediction,100,allowed_centers=allowed)
        old=self.center.copy()
        if fit is not None and fit['match']>.35 and diag['ok'] and flowdiag['flow_ok']:
            self.center=.15*prediction+.85*fit['center'];score=fit['match'];mode='geometry';angle=fit['angle'];scale=fit['scale']
        else:
            self.center=prediction;self.velocity*=.7;score=0.;mode='uncertain';angle=0.;scale=1.
        self.center=np.clip(self.center,[40,90],[gray.shape[1]-25,gray.shape[0]-80]);self.velocity=.6*self.velocity+.4*np.clip((self.center-old)/max(.5,dt*30),-12,12)
        self.frames.append(gray)
        if len(self.frames)>4:self.frames.pop(0)
        self.missing=self.missing+1 if mode=='uncertain' else 0
        return TrackResult(tuple(map(float,self.center)),float(score),mode,angle,scale)
