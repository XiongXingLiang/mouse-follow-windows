import base64,json,tempfile,unittest
from pathlib import Path
from admin.issuer import generate_keys,issue
from follower.license_core import LicenseError,verify_token,unb64,b64
from follower.license_store import LicenseManager
from unittest.mock import patch
class LicenseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.private=self.root/'owner-private.pem';self.public=self.root/'public.pem'
        generate_keys(self.private,self.public);self.device='A'*64;self.now=1800000000
    def tearDown(self):self.temp.cleanup()
    def token(self,plan='3d'):return issue(self.private,self.device,plan,self.now)
    def check(self,token,device=None,now=None,**kwargs):return verify_token(token,self.public.read_bytes(),device or self.device,self.now if now is None else now,**kwargs)
    def test_all_plans(self):
        for plan,days in [('3d',3),('30d',30),('permanent',None)]:
            grant=self.check(self.token(plan));self.assertEqual(grant.plan,plan)
            self.assertEqual(grant.expires_at,None if days is None else self.now+days*86400)
    def test_expiry_boundary(self):
        token=self.token();self.check(token,now=self.now+3*86400-1)
        with self.assertRaises(LicenseError):self.check(token,now=self.now+3*86400)
    def test_permanent_has_no_expiry(self):self.check(self.token('permanent'),now=self.now+20*365*86400)
    def test_wrong_device_rejected(self):
        with self.assertRaises(LicenseError):self.check(self.token(),device='B'*64)
    def test_tampered_payload_rejected(self):
        token=self.token().split('.');payload=json.loads(unb64(token[1]));payload['plan']='permanent';payload['expires_at']=None;token[1]=b64(json.dumps(payload).encode())
        with self.assertRaises(LicenseError):self.check('.'.join(token))
    def test_wrong_signing_key_rejected(self):
        p=self.root/'other-private.pem';u=self.root/'other.pem';generate_keys(p,u)
        with self.assertRaises(LicenseError):self.check(issue(p,self.device,'3d',self.now))
    def test_future_signature_rejected(self):
        with self.assertRaises(LicenseError):self.check(self.token(),now=self.now-301)
    def test_clock_rollback_rejected(self):
        with self.assertRaises(LicenseError):self.check(self.token(),last_seen=self.now+301)
    def test_malformed_tokens_rejected(self):
        for bad in ['', 'MF1.a.b','MF1.@@@@.x','X1.a.b','a'*20001]:
            with self.assertRaises(LicenseError):self.check(bad)
    def test_issuer_rejects_wrong_device_and_overwrite(self):
        with self.assertRaises(ValueError):issue(self.private,'short','3d',self.now)
        with self.assertRaises(ValueError):generate_keys(self.private,self.public)
    def test_expired_store_can_be_reactivated(self):
        path=self.root/'state.bin'
        with patch('time.time',return_value=self.now):
            manager=LicenseManager(self.public.read_bytes(),self.device,path);manager.activate(self.token())
        with patch('time.time',return_value=self.now+4*86400):
            expired=LicenseManager(self.public.read_bytes(),self.device,path)
            self.assertIsNone(expired.grant)
            token=issue(self.private,self.device,'30d',self.now+4*86400)
            expired.activate(token);self.assertEqual(expired.check().plan,'30d')
