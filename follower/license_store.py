"""Device fingerprint and local activation state, DPAPI-protected on Windows."""
from __future__ import annotations
import ctypes,hashlib,json,os,platform,time
from pathlib import Path
from .license_core import LicenseError,verify_token

def data_dir()->Path:
    base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'MouseFollower'
    base.mkdir(parents=True,exist_ok=True);return base

def device_code()->str:
    if platform.system()!='Windows':raise LicenseError('本软件的设备授权仅支持 Windows')
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
            guid=str(winreg.QueryValueEx(key,'MachineGuid')[0]).strip().lower()
    except OSError as exc:raise LicenseError('无法读取本机设备标识') from exc
    return hashlib.sha256(('MouseFollower/v1/'+guid).encode()).hexdigest().upper()

class Blob(ctypes.Structure):
    _fields_=[('cbData',ctypes.c_uint32),('pbData',ctypes.POINTER(ctypes.c_ubyte))]

def protect(data:bytes,decrypt:bool=False)->bytes:
    if platform.system()!='Windows':return data
    raw=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(raw,ctypes.POINTER(ctypes.c_ubyte)));result=Blob()
    # CRYPTPROTECT_UI_FORBIDDEN; data is bound to the current Windows user.
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    crypt.CryptProtectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_wchar_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(Blob)]
    crypt.CryptProtectData.restype=ctypes.c_bool
    crypt.CryptUnprotectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype=ctypes.c_bool
    if decrypt:ok=crypt.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(result))
    else:ok=crypt.CryptProtectData(ctypes.byref(source),'MouseFollower',None,None,None,1,ctypes.byref(result))
    if not ok:raise LicenseError('本机授权存储不可读取，请重新激活')
    try:return ctypes.string_at(result.pbData,result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes=[ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(ctypes.cast(result.pbData,ctypes.c_void_p))

class LicenseManager:
    def __init__(self,public_pem:bytes,device:str,path:Path|None=None):
        self.public_pem=public_pem;self.device=device;self.path=path or data_dir()/'activation.bin'
        self.error='';self.token='';self.last_seen=0.;self.grant=None;self.started=time.monotonic();self.anchor=time.time();self.saved=0.
        if self.path.exists():
            try:
                state=json.loads(protect(self.path.read_bytes(),True));self.last_seen=float(state['last_seen']);self.token=state['token']
                self.grant=verify_token(self.token,public_pem,device,last_seen=self.last_seen)
            except LicenseError as exc:self.error=str(exc);self.grant=None
            except Exception:self.error='授权状态损坏，请重新激活';self.grant=None
    def activate(self,token:str):
        grant=verify_token(token,self.public_pem,self.device,last_seen=self.last_seen)
        self.token=token.strip();self.grant=grant;self.check();self.save();return grant
    def check(self):
        if self.grant is None:raise LicenseError('请先导入激活码')
        wall=time.time();effective=max(wall,self.anchor+time.monotonic()-self.started)
        self.grant.check_time(wall,self.last_seen);self.grant.check_time(effective)
        self.last_seen=max(self.last_seen,effective)
        if time.monotonic()-self.saved>60:self.save()
        return self.grant
    def save(self):
        if not self.token:return
        state=json.dumps({'token':self.token,'last_seen':self.last_seen}).encode()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_bytes(protect(state));os.replace(tmp,self.path);self.saved=time.monotonic()
