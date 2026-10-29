import unittest
from unittest.mock import patch
from admin.owner_access import OwnerLicense
from follower.license_store import LicenseManager
from follower.license_core import LicenseError
from pathlib import Path
import tempfile
class OwnerEditionTests(unittest.TestCase):
    def test_permanent_without_device_or_activation(self):
        with patch('follower.license_store.device_code',side_effect=AssertionError('must not read device')):
            access=OwnerLicense();grant=access.check()
            self.assertEqual(grant.plan,'permanent');self.assertIsNone(grant.expires_at)
    def test_still_permanent_in_future(self):
        access=OwnerLicense()
        with patch('time.time',return_value=4102444800):self.assertEqual(access.check().plan,'permanent')
    def test_regular_client_still_requires_activation(self):
        from follower.paths import ASSETS
        with tempfile.TemporaryDirectory() as tmp:
            access=LicenseManager((ASSETS/'license-public.pem').read_bytes(),'A'*64,Path(tmp)/'state.bin')
            with self.assertRaises(LicenseError):access.check()
    def test_no_client_cli_admin_switch(self):
        root=Path(__file__).resolve().parent.parent
        source=(root/'client_main.py').read_text()
        self.assertNotIn('OwnerLicense',source);self.assertNotIn('owner_edition',source)
