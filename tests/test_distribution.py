import ast,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
class DistributionTests(unittest.TestCase):
    def test_client_sources_never_import_admin(self):
        for path in (ROOT/'follower').glob('*.py'):
            tree=ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom):self.assertFalse((node.module or '').startswith('admin'))
                if isinstance(node,ast.Import):self.assertFalse(any(a.name.startswith('admin') for a in node.names))
    def test_no_private_key_in_assets(self):
        for path in (ROOT/'follower/assets').glob('*'):
            if path.is_file():self.assertNotIn(b'PRIVATE KEY',path.read_bytes())
    def test_public_key_valid(self):
        from follower.license_core import load_public_key
        load_public_key((ROOT/'follower/assets/license-public.pem').read_bytes())
