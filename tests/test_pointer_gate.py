import threading,unittest
from unittest.mock import Mock
from follower.runtime import PointerController
from follower.tracker import TrackResult
from follower.license_core import LicenseError
class PointerGateTests(unittest.TestCase):
    def setUp(self):
        self.armed=threading.Event();self.enabled=threading.Event();self.armed.set();self.enabled.set()
        self.native=Mock();self.native.emergency.return_value=False;self.native.move.return_value=True
        self.licenses=Mock();self.gate=PointerController(self.licenses,self.native,self.armed,self.enabled)
        self.result=TrackResult((100,200),.9,'geometry')
    def test_valid_grant_can_move(self):
        self.assertTrue(self.gate.move(self.result,(100,200)));self.licenses.check.assert_called_once();self.native.move.assert_called_once_with(100,200)
    def test_preview_never_moves(self):
        self.enabled.clear();self.assertFalse(self.gate.move(self.result,(100,200)));self.native.move.assert_not_called()
    def test_disarmed_never_moves(self):
        self.armed.clear();self.assertFalse(self.gate.move(self.result,(100,200)));self.native.move.assert_not_called()
    def test_expired_license_never_moves(self):
        self.licenses.check.side_effect=LicenseError('expired')
        with self.assertRaises(LicenseError):self.gate.move(self.result,(100,200))
        self.native.move.assert_not_called()
    def test_emergency_after_slow_validation(self):
        self.native.emergency.side_effect=[False,True];self.assertFalse(self.gate.move(self.result,(100,200)));self.native.move.assert_not_called()
    def test_uncertain_or_low_score_never_moves(self):
        for result in [TrackResult((1,2),1.,'uncertain'),TrackResult((1,2),.3,'geometry')]:self.assertFalse(self.gate.move(result,(1,2)))
        self.native.move.assert_not_called()
