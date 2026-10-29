"""Local administrator key generation and offline grant issuance."""
from __future__ import annotations
import argparse,json,os,re,time,uuid
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from follower.license_core import PERIODS,PRODUCT,b64,canonical,key_id

def generate_keys(private_path:Path,public_path:Path):
    if private_path.exists() or public_path.exists():raise ValueError('密钥文件已存在，拒绝覆盖')
    private=Ed25519PrivateKey.generate()
    private_path.parent.mkdir(parents=True,exist_ok=True);public_path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(private_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    public_path.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))

def issue(private_path:Path,device:str,plan:str,now:int|None=None)->str:
    device=re.sub(r'\s+','',device).upper()
    if re.fullmatch(r'[0-9A-F]{64}',device) is None:raise ValueError('设备码必须为 64 位十六进制字符')
    if plan not in PERIODS:raise ValueError('授权类型应为 permanent、30d 或 3d')
    key=serialization.load_pem_private_key(private_path.read_bytes(),password=None)
    if not isinstance(key,Ed25519PrivateKey):raise ValueError('不是 Ed25519 私钥')
    issued=int(time.time()) if now is None else int(now);period=PERIODS[plan]
    pem=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    payload={'version':1,'product':PRODUCT,'key_id':key_id(pem),'license_id':str(uuid.uuid4()),'device':device,'plan':plan,'issued_at':issued,'expires_at':None if period is None else issued+period}
    data=canonical(payload);return 'MF1.'+b64(data)+'.'+b64(key.sign(data))

def main():
    parser=argparse.ArgumentParser();subs=parser.add_subparsers(dest='command',required=True)
    p=subs.add_parser('keygen');p.add_argument('--private',type=Path,required=True);p.add_argument('--public',type=Path,required=True)
    p=subs.add_parser('issue');p.add_argument('--private',type=Path,required=True);p.add_argument('--device',required=True);p.add_argument('--plan',choices=list(PERIODS),required=True);p.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.command=='keygen':generate_keys(args.private,args.public);print('密钥已生成。私钥仅留在签发者本机。')
    else:
        token=issue(args.private,args.device,args.plan)
        if args.output:args.output.write_text(token,encoding='utf-8');print('激活码已保存到指定文件。')
        else:print(token)
if __name__=='__main__':main()
