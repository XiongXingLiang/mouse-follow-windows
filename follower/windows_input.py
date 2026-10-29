"""Minimal Windows input API; no keyboard injection, clicks or admin privileges."""
import ctypes,platform

def enable_dpi_awareness():
    if platform.system()!='Windows':return
    try:ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError,OSError):
        try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError,OSError):pass

class WindowsInput:
    def __init__(self):
        if platform.system()!='Windows':raise RuntimeError('鼠标控制仅可在 Windows 运行')
        self.api=ctypes.WinDLL('user32',use_last_error=True)
        self.api.GetAsyncKeyState.argtypes=[ctypes.c_int];self.api.GetAsyncKeyState.restype=ctypes.c_short
        self.api.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int];self.api.SetCursorPos.restype=ctypes.c_bool
        self.last_f8=False
    def emergency(self):return bool(self.api.GetAsyncKeyState(0x1B)&0x8000)
    def toggle_pressed(self):
        down=bool(self.api.GetAsyncKeyState(0x77)&0x8000);edge=down and not self.last_f8;self.last_f8=down;return edge
    def move(self,x,y):
        # Last-moment Esc check closes the race with a slow vision operation.
        if self.emergency():return False
        if not self.api.SetCursorPos(int(x),int(y)):raise OSError(ctypes.get_last_error(),'SetCursorPos failed')
        return True
