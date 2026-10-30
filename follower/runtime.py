"""Capture worker with explicit arming, licensing and fail-closed pointer control."""
from __future__ import annotations
import logging,queue,threading,time
import cv2,numpy as np
from .detection import GameDetector,EndDetector,Region,brown_fraction,working_frame,to_screen
from .tracker import VisualTracker
from .windows_input import WindowsInput

def capture_region(capture,monitor,roi):
    """Grab only a monitor-relative game ROI, preserving negative monitor origins."""
    region={'left':monitor['left']+roi.left,'top':monitor['top']+roi.top,
            'width':roi.width,'height':roi.height}
    return np.asarray(capture.grab(region))[:,:,:3].copy()

class PointerController:
    def __init__(self,licenses,native,armed,enabled):
        self.licenses=licenses;self.native=native;self.armed=armed;self.enabled=enabled
    def move(self,result,point):
        if not self.armed.is_set() or not self.enabled.is_set() or result.mode=='uncertain' or result.score<.55 or self.native.emergency():return False
        self.licenses.check()
        if not self.armed.is_set() or self.native.emergency():return False
        return self.native.move(*point)

class Runtime:
    def __init__(self,licenses):
        self.licenses=licenses;self.events=queue.Queue(maxsize=4);self.shutdown=threading.Event();self.armed=threading.Event();self.move_enabled=threading.Event()
        self.monitor_index=1;self.manual=None;self.lock=threading.Lock();self.thread=None
    def publish(self,text,preview=None):
        event={'text':text,'preview':preview}
        try:self.events.put_nowait(event)
        except queue.Full:
            try:self.events.get_nowait()
            except queue.Empty:pass
            try:self.events.put_nowait(event)
            except queue.Full:pass
    def start(self):
        if self.thread is None:self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def arm(self):self.licenses.check();self.armed.set()
    def stop(self):self.armed.clear()
    def close(self):self.stop();self.shutdown.set()
    def configure(self,monitor_index,manual=None):
        self.stop()
        with self.lock:self.monitor_index=int(monitor_index);self.manual=manual
    def loop(self):
        from mss import mss
        try:
            native=WindowsInput();detector=GameDetector();ending=EndDetector();tracker=VisualTracker();controller=PointerController(self.licenses,native,self.armed,self.move_enabled)
            with mss(with_cursor=False) as capture:
                match=None;last_scan=0.;last_presence=0.;last_preview=0.;last_perf=None;perf_frames=0;perf_total=0.;actual_fps=0.;was_armed=False;stable=0;ended=False;roi=None
                while not self.shutdown.is_set():
                    tick=time.monotonic()
                    if native.emergency():self.armed.clear();tracker.reset();match=None;stable=0
                    if native.toggle_pressed():
                        if self.armed.is_set():self.stop()
                        else:
                            try:self.arm()
                            except Exception as exc:self.publish(str(exc))
                    armed=self.armed.is_set()
                    if not armed:
                        if was_armed:self.publish('已停止；F8 可重新开始');tracker.reset();match=None;stable=0
                        was_armed=False;last_perf=None;self.shutdown.wait(.03);continue
                    was_armed=True
                    try:self.licenses.check()
                    except Exception as exc:self.stop();self.publish('授权不可用：'+str(exc));continue
                    with self.lock:monitor_index=self.monitor_index;manual=self.manual
                    if monitor_index>=len(capture.monitors):self.stop();self.publish('所选显示器已断开');continue
                    monitor=capture.monitors[monitor_index]
                    # Full-monitor scans are needed only for discovery/presence.
                    # Between scans, capture the game directly instead of copying
                    # a potentially 4K desktop into Python on every update.
                    full=None;shape=(monitor['height'],monitor['width'])
                    if match is None and manual is None:
                        if tick-last_scan<.5:self.shutdown.wait(.03);continue
                        last_scan=tick;full=np.asarray(capture.grab(monitor))[:,:,:3].copy()
                        candidate=detector.find(full)
                        if candidate is None:stable=0;self.publish('正在等待小游戏画面');continue
                        stable+=1
                        if stable<2:continue
                        match=candidate;roi=match.roi;tracker.reset();ended=False;last_presence=tick
                    elif manual is not None:roi=manual
                    elif tick-last_presence>.3:
                        last_presence=tick;full=np.asarray(capture.grab(monitor))[:,:,:3].copy()
                        if not detector.present(full,match):
                            match=None;tracker.reset();stable=0;self.publish('游戏画面已离开，停止跟随');continue
                    if roi is None or not roi.valid_in(shape):match=None;tracker.reset();continue
                    game=roi.crop(full) if full is not None else capture_region(capture,monitor,roi)
                    if manual is not None and brown_fraction(game)<.40:
                        tracker.reset();self.publish('手动区域内未出现小游戏画面');self.shutdown.wait(.15);continue
                    if ending.detect(game):
                        tracker.reset();ended=True;self.publish('检测到结束提示，等待新回合');self.shutdown.wait(.1);continue
                    if ended:ended=False;tracker.reset()
                    work=working_frame(game);vision_start=time.monotonic();result=tracker.update(work)
                    vision_ms=(time.monotonic()-vision_start)*1000
                    if last_perf is None:last_perf=tick;perf_frames=0;perf_total=0.
                    perf_frames+=1;perf_total+=vision_ms
                    if time.monotonic()-last_perf>=1:
                        actual_fps=perf_frames/(time.monotonic()-last_perf)
                        logging.info("Tracking performance: %.1f FPS, mean vision %.0f ms, last mode %s",actual_fps,perf_total/perf_frames,result.mode if result else "waiting")
                        last_perf=time.monotonic();perf_frames=0;perf_total=0.
                    if result is None:text='小游戏已出现，等待初始白色目标'
                    else:
                        if result.mode=='uncertain' or result.score<.55:
                            text='目标证据不足，暂停移动鼠标'
                            if tracker.missing>=8:tracker.reset()
                        else:
                            text='跟随中' if self.move_enabled.is_set() else '预览中（未接管鼠标）'
                            if self.move_enabled.is_set() and self.armed.is_set():
                                point=to_screen(result.center,roi,monitor)
                                if not controller.move(result,point):self.stop()
                        x,y=np.rint(result.center).astype(int)
                        cv2.drawMarker(work,(int(x),int(y)),(255,210,60),cv2.MARKER_CROSS,18,2)
                        text+=f' · 匹配 {result.score:.2f} · 识别 {vision_ms:.0f} ms · {actual_fps:.0f} FPS'
                    if tick-last_preview>.10:
                        last_preview=tick;self.publish(text,cv2.resize(work,(508,442)))
                    self.shutdown.wait(max(0,1/60-(time.monotonic()-tick)))
        except Exception as exc:
            logging.exception('Runtime stopped');self.stop();self.publish('运行错误，已停止鼠标控制：'+str(exc))
