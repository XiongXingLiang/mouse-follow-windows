"""Local causal replay benchmark. Does not capture a screen or move the pointer."""
import argparse,json,time
from pathlib import Path
import cv2,numpy as np
from follower.detection import GameDetector,EndDetector,working_frame,Region
from follower.tracker import VisualTracker
p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('--output',required=True);p.add_argument('--crop',type=int,nargs=4);p.add_argument('--limit',type=int,default=0);p.add_argument('--threads',type=int);args=p.parse_args()
if args.threads is not None:cv2.setNumThreads(args.threads)
cap=cv2.VideoCapture(args.video);fps=cap.get(cv2.CAP_PROP_FPS);frames=[];i=0
while True:
    ok,frame=cap.read()
    if not ok:break
    if i%2==0:frames.append((i/fps,frame))
    i+=1
    if args.limit and len(frames)>=args.limit:break
cap.release();tracker=VisualTracker();detector=GameDetector();ending=EndDetector();match=None;roi=Region(*args.crop) if args.crop else None;records=[]
for t,frame in frames:
    start=time.perf_counter()
    if roi is None:
        match=detector.find(frame)
        if match:roi=match.roi
    result=None;mode='no_game'
    if roi:
        game=roi.crop(frame)
        if ending.detect(game):tracker.reset();mode='end'
        else:
            result=tracker.update(working_frame(game),t);mode=result.mode if result else 'waiting'
    ms=(time.perf_counter()-start)*1000
    records.append({'t':t,'ms':ms,'mode':mode,'center':list(result.center) if result else None,'score':result.score if result else None})
summary={'frames':len(records),'mean_ms':float(np.mean([r['ms'] for r in records])),'p95_ms':float(np.percentile([r['ms'] for r in records],95)),'modes':{m:sum(r['mode']==m for r in records) for m in set(r['mode'] for r in records)}}
Path(args.output).write_text(json.dumps({'summary':summary,'records':records},indent=2));print(json.dumps(summary),flush=True)
