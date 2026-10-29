"""Causal background alignment and compensated differences."""
import cv2,numpy as np

def viewport_mask(shape):
    h,w=shape; mask=np.zeros(shape,np.uint8)
    mask[75:h-65,30:w-15]=255
    return mask

def estimate_background(previous,current,valid,exclude_center=None,exclude_radius=105):
    mask=valid.copy()
    if exclude_center is not None:
        cv2.circle(mask,tuple(np.rint(exclude_center).astype(int)),int(exclude_radius),0,-1)
    p=cv2.goodFeaturesToTrack(previous,500,.012,8,mask=mask)
    fail={'ok':False,'points':0,'inliers':0,'before_median':None,'after_median':None}
    if p is None or len(p)<10:return np.eye(2,3,dtype=np.float32),fail
    q,st,_=cv2.calcOpticalFlowPyrLK(previous,current,p,None,winSize=(27,27),maxLevel=4)
    back,bst,_=cv2.calcOpticalFlowPyrLK(current,previous,q,None,winSize=(27,27),maxLevel=4)
    good=(st.ravel()>0)&(bst.ravel()>0)&(np.linalg.norm(back-p,axis=2).ravel()<1.2)
    if good.sum()<10:return np.eye(2,3,dtype=np.float32),fail
    affine,inliers=cv2.estimateAffinePartial2D(p[good],q[good],method=cv2.RANSAC,ransacReprojThreshold=1.25,maxIters=2000)
    if affine is None or inliers.sum()<10:return np.eye(2,3,dtype=np.float32),fail
    h,w=previous.shape;aligned=cv2.warpAffine(previous,affine,(w,h))
    # Compare corresponding background pixels, excluding the target and invalid borders.
    overlap=cv2.warpAffine(mask,affine,(w,h),flags=cv2.INTER_NEAREST)&mask
    select=overlap>0
    before=cv2.absdiff(previous,current);after=cv2.absdiff(aligned,current)
    diagnostics={'ok':True,'points':int(good.sum()),'inliers':int(inliers.sum()),
      'before_median':float(np.median(before[select])),'after_median':float(np.median(after[select]))}
    return affine,diagnostics

def compensated_residual(previous,current,valid,center,exclude_radius=105):
    affine,diag=estimate_background(previous,current,valid,center,exclude_radius)
    h,w=previous.shape
    aligned=cv2.warpAffine(previous,affine,(w,h))
    overlap=cv2.warpAffine(valid,affine,(w,h),flags=cv2.INTER_NEAREST)&valid
    overlap=cv2.erode(overlap,np.ones((7,7),np.uint8))
    # Mild blur reduces codec noise and subpixel interpolation errors.
    a=cv2.GaussianBlur(aligned,(0,0),.8);b=cv2.GaussianBlur(current,(0,0),.8)
    residual=cv2.absdiff(a,b).astype(np.float32)
    residual[overlap==0]=0
    smoothed=cv2.GaussianBlur(residual,(0,0),8)
    bg=overlap.copy();cv2.circle(bg,tuple(np.rint(center).astype(int)),exclude_radius,0,-1)
    values=smoothed[bg>0]
    floor=float(np.median(values)) if len(values) else 0
    mad=float(np.median(np.abs(values-floor))) if len(values) else 0
    threshold=max(5.,floor+max(3.,3*mad))
    diag.update({'noise_floor':floor,'threshold':threshold})
    signal=np.maximum(smoothed-threshold,0)
    signal[overlap==0]=0
    return signal,residual,affine,diag

def locate_residual(signal,prediction,radius=120):
    yy,xx=np.mgrid[:signal.shape[0],:signal.shape[1]]
    distance=(xx-prediction[0])**2+(yy-prediction[1])**2
    weights=signal**2*np.exp(-distance/(2*(radius*.65)**2))
    weights[distance>radius**2]=0
    total=float(weights.sum())
    if total<50:return None,0.,weights
    point=np.array([(weights*xx).sum()/total,(weights*yy).sum()/total])
    peak=float(signal[distance<radius**2].max())
    return point,peak,weights

