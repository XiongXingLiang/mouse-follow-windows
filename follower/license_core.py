"""Ed25519-signed offline grants. No signing secret belongs in this package."""
from __future__ import annotations
import base64, hashlib, json, time
from dataclasses import dataclass
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
PRODUCT='mouse-follow-windows'
PERIODS={'3d':3*86400,'30d':30*86400,'permanent':None}
class LicenseError(ValueError): pass

def b64(data:bytes)->str:return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')
def unb64(value:str)->bytes:
    if len(value)>16384:raise LicenseError('激活码过长')
    try:return base64.b64decode(value+'='*((-len(value))%4),altchars=b'-_',validate=True)
    except Exception as exc:raise LicenseError('激活码编码无效') from exc

def canonical(payload:dict)->bytes:
    return json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')

def load_public_key(data:bytes)->Ed25519PublicKey:
    try:key=serialization.load_pem_public_key(data)
    except Exception as exc:raise LicenseError('授权公钥无效') from exc
    if not isinstance(key,Ed25519PublicKey):raise LicenseError('需要 Ed25519 公钥')
    return key

def key_id(data:bytes)->str:
    key=load_public_key(data)
    return hashlib.sha256(key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).hexdigest()[:16]

@dataclass(frozen=True)
class Grant:
    license_id:str
    device:str
    plan:str
    issued_at:int
    expires_at:int|None
    def check_time(self,now:float,last_seen:float=0.)->None:
        if now+300<last_seen:raise LicenseError('系统时间发生回拨，请校正时间')
        if self.issued_at>now+300:raise LicenseError('系统时间早于授权签发时间')
        if self.expires_at is not None and now>=self.expires_at:raise LicenseError('授权已到期，请向签发者申请新的激活码')
    @property
    def description(self)->str:
        names={'3d':'3 天体验','30d':'30 天授权','permanent':'永久授权'}
        if self.expires_at is None:return names[self.plan]
        return names[self.plan]+'，到期：'+time.strftime('%Y-%m-%d %H:%M',time.localtime(self.expires_at))

def verify_token(token:str,public_pem:bytes,device:str,now:float|None=None,last_seen:float=0.)->Grant:
    if not isinstance(token,str) or len(token)>20000:raise LicenseError('激活码无效')
    parts=token.strip().split('.')
    if len(parts)!=3 or parts[0]!='MF1':raise LicenseError('激活码格式无效')
    raw,signature=unb64(parts[1]),unb64(parts[2]);key=load_public_key(public_pem)
    try:key.verify(signature,raw)
    except (InvalidSignature,ValueError) as exc:raise LicenseError('激活码签名无效') from exc
    try:payload=json.loads(raw)
    except Exception as exc:raise LicenseError('授权内容无效') from exc
    if not isinstance(payload,dict):raise LicenseError('授权内容无效')
    if payload.get('product')!=PRODUCT or payload.get('version')!=1:raise LicenseError('激活码不适用于此软件')
    if payload.get('key_id')!=key_id(public_pem):raise LicenseError('激活码使用了其他签发密钥')
    if payload.get('device')!=device:raise LicenseError('激活码与本机设备码不匹配')
    plan=payload.get('plan');issued=payload.get('issued_at');expiry=payload.get('expires_at');lid=payload.get('license_id')
    if plan not in PERIODS or type(issued) is not int or not isinstance(lid,str) or not lid:raise LicenseError('授权字段无效')
    period=PERIODS[plan]
    if period is None:
        if expiry is not None:raise LicenseError('永久授权字段无效')
    elif type(expiry) is not int or expiry!=issued+period:raise LicenseError('限时授权字段无效')
    grant=Grant(lid,device,plan,issued,expiry)
    grant.check_time(time.time() if now is None else now,last_seen)
    return grant
