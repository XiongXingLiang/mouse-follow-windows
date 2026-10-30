"""Game UI discovery and end-caption detection. Assets contain game chrome only."""
from dataclasses import dataclass
import cv2,numpy as np
from .paths import ASSETS
@dataclass(frozen=True)
class Region:
    left:int
    top:int
    width:int
    height:int
    def as_dict(self):return {'left':self.left,'top':self.top,'width':self.width,'height':self.height}
    def valid_in(self,shape):
        h,w=shape[:2];return self.left>=0 and self.top>=0 and self.width>80 and self.height>80 and self.left+self.width<=w and self.top+self.height<=h
    def crop(self,frame):return frame[self.top:self.top+self.height,self.left:self.left+self.width]

@dataclass(frozen=True)
class GameMatch:
    roi:Region
    title:Region
    scale:float
    score:float

def brown_fraction(frame):
    if not frame.size:return 0.
    hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    return float(np.mean(cv2.inRange(hsv,np.array([8,50,35]),np.array([45,255,255]))>0))

class GameDetector:
    def __init__(self):
        self.title=cv2.imread(str(ASSETS/'game-title.png'),cv2.IMREAD_GRAYSCALE)
        if self.title is None:raise RuntimeError('缺少游戏标题栏识别模板')
        self.scales=[.6,.7,.8,.9,1.,1.1,1.25,1.5,1.75,2.]
    def find(self,frame):
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY);best=None
        for scale in self.scales:
            template=cv2.resize(self.title,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
            th,tw=template.shape
            if th>=gray.shape[0] or tw>=gray.shape[1]:continue
            scores=cv2.matchTemplate(gray,template,cv2.TM_CCOEFF_NORMED)
            _,value,_,(x,y)=cv2.minMaxLoc(scores)
            if value<.80:continue
            roi=Region(round(x+8*scale),round(y+28*scale),round(678*scale),round(450*scale))
            if not roi.valid_in(frame.shape) or brown_fraction(roi.crop(frame))<.42:continue
            candidate=GameMatch(roi,Region(x,y,tw,th),scale,float(value))
            if best is None or candidate.score>best.score:best=candidate
        return best
    def present(self,frame,match):
        if not match.roi.valid_in(frame.shape):return False
        if brown_fraction(match.roi.crop(frame))<.40:return False
        r=match.title
        h,w=frame.shape[:2]
        if r.left<0 or r.top<0 or r.left+r.width>w or r.top+r.height>h:return False
        patch=cv2.cvtColor(r.crop(frame),cv2.COLOR_BGR2GRAY)
        template=cv2.resize(self.title,(r.width,r.height))
        return float(cv2.matchTemplate(patch,template,cv2.TM_CCOEFF_NORMED)[0,0])>=.72

def caption_mask(frame):
    hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv,np.array([12,0,210]),np.array([48,175,255]))

class EndDetector:
    def __init__(self):
        image=cv2.imread(str(ASSETS/'finish-caption.png'))
        if image is None:raise RuntimeError('缺少结束提示识别模板')
        mask=caption_mask(image)
        points=cv2.findNonZero(mask)
        if points is None:raise RuntimeError('结束提示模板为空')
        x,y,w,h=cv2.boundingRect(points);self.mask=mask[y:y+h,x:x+w]
        self.templates=[cv2.resize(self.mask,None,fx=scale/2,fy=scale/2,interpolation=cv2.INTER_NEAREST) for scale in [.75,.9,1.,1.1,1.25]]
    def detect(self,game):
        normalized=cv2.resize(game,(678,450));mask=caption_mask(normalized)
        # Completion message belongs to the central game area, not chrome/score labels.
        search=cv2.resize(mask[90:370,100:590],(245,140),interpolation=cv2.INTER_NEAREST)
        for template in self.templates:
            if template.shape[0]>=search.shape[0] or template.shape[1]>=search.shape[1]:continue
            _,score,_,_=cv2.minMaxLoc(cv2.matchTemplate(search,template,cv2.TM_CCOEFF_NORMED))
            if score>.60:return True
        return False

def working_frame(game):
    return cv2.copyMakeBorder(cv2.resize(game,(678,450)),75,65,0,0,cv2.BORDER_CONSTANT,value=(20,24,33))

def to_screen(point,roi,monitor):
    x,y=point
    return (round(monitor['left']+roi.left+x/678*roi.width),round(monitor['top']+roi.top+(y-75)/450*roi.height))
