"""Render current tracker against local recording, without pointer input."""
import argparse,json,time,subprocess
from pathlib import Path
import cv2,numpy as np,imageio_ffmpeg
from follower.detection import GameDetector,EndDetector,working_frame,to_screen
from follower.tracker import VisualTracker
parser=argparse.ArgumentParser();parser.add_argument('video');parser.add_argument('--output',required=True);args=parser.parse_args()
source=args.video;out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
cap=cv2.VideoCapture(source);fps=cap.get(cv2.CAP_PROP_FPS);w=int(cap.get(3));h=int(cap.get(4))
writer=cv2.VideoWriter(str(out/'raw.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps/2,(w,h))
tracker=VisualTracker();detector=GameDetector();ending=EndDetector();match=None;i=0;times=[];records=[]
while True:
    ok,frame=cap.read()
    if not ok:break
    if i%2:i+=1;continue
    start=time.perf_counter()
    if match is None:match=detector.find(frame)
    result=None;mode='waiting for game'
    if match:
        game=match.roi.crop(frame)
        if ending.detect(game):tracker.reset();mode='round complete'
        else:
            result=tracker.update(working_frame(game),i/fps)
            mode=result.mode if result else 'waiting for white target'
    ms=(time.perf_counter()-start)*1000;times.append(ms)
    if result and result.mode!='uncertain' and result.score>=.55:
        point=to_screen(result.center,match.roi,{'left':0,'top':0})
        cv2.circle(frame,point,18,(255,255,0),2);cv2.drawMarker(frame,point,(255,255,0),cv2.MARKER_CROSS,26,2)
    cv2.rectangle(frame,(0,0),(w,53),(25,25,25),-1)
    cv2.putText(frame,f'PERFORMANCE 10.30 REPLAY | {mode} | processing {ms:.0f} ms',(12,22),cv2.FONT_HERSHEY_SIMPLEX,.57,(255,255,255),1,cv2.LINE_AA)
    cv2.putText(frame,'Cyan marker = tracking output | source-speed playback, not live mouse',(12,43),cv2.FONT_HERSHEY_SIMPLEX,.52,(220,220,220),1,cv2.LINE_AA)
    writer.write(frame);records.append({'time':i/fps,'ms':ms,'mode':mode,'center':list(result.center) if result else None})
    if len(times)%90==0:print(f'{i/fps:.1f}s processed, mean {np.mean(times):.1f}ms',flush=True)
    i+=1
writer.release();cap.release()
report={'frames':len(times),'mean_processing_ms':float(np.mean(times)),'p95_processing_ms':float(np.percentile(times,95)),'note':'Mac local recorded-frame replay. Excludes live capture, pointer API, encoding. Playback uses source time; not a live throughput demonstration.','records':records}
(out/'report.json').write_text(json.dumps(report,indent=2))
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(out/'raw.mp4'),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'optimized-tracking.mp4')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print(json.dumps({k:v for k,v in report.items() if k!='records'}))
