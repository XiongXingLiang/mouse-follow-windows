import unittest
from unittest.mock import Mock,patch
import cv2
import numpy as np
from follower.background import estimate_background,viewport_mask
from follower.detection import EndDetector,Region,working_frame
from follower.paths import ASSETS
from follower.runtime import capture_region
from follower.tracker import VisualTracker
from follower.motion_geometry import ShapeFitter

class PerformancePathTests(unittest.TestCase):
    def test_white_anchor_skips_expensive_motion_and_preserves_history(self):
        tracker=VisualTracker();game=np.full((450,678,3),(45,105,150),np.uint8)
        cv2.rectangle(game,(290,180),(370,260),(255,255,255),-1)
        tracker.update(working_frame(game),0.)
        moved=np.full_like(game,(45,105,150));cv2.rectangle(moved,(296,184),(376,264),(255,255,255),-1)
        with patch('follower.tracker.compensated_residual',side_effect=AssertionError('expensive path')):
            result=tracker.update(working_frame(moved),.033)
        self.assertEqual(result.mode,'white');self.assertEqual(len(tracker.frames),2)
        np.testing.assert_allclose(result.center,[336.5,299.5],atol=1)
        with patch('follower.tracker.compensated_residual',side_effect=RuntimeError('motion needed')):
            with self.assertRaisesRegex(RuntimeError,'motion needed'):
                tracker.update(working_frame(np.full_like(game,(45,105,150))),.066)
    def test_sparse_background_affine_returns_full_size_translation(self):
        rng=np.random.default_rng(123);a=rng.integers(0,255,(590,678),dtype=np.uint8)
        a=cv2.GaussianBlur(a,(5,5),.8)
        expected=np.array([[1.,0.,6.],[0.,1.,-4.]],np.float32)
        b=cv2.warpAffine(a,expected,(678,590))
        affine,diag=estimate_background(a,b,viewport_mask(a.shape),(339,295))
        self.assertTrue(diag['ok']);np.testing.assert_allclose(affine,expected,atol=.25)
    def test_roi_capture_adds_negative_monitor_origin(self):
        native=Mock();native.grab.return_value=np.zeros((100,120,4),np.uint8)
        image=capture_region(native,{'left':-1920,'top':-200},Region(30,40,120,100))
        native.grab.assert_called_once_with({'left':-1890,'top':-160,'width':120,'height':100})
        self.assertEqual(image.shape,(100,120,3))
    def test_completion_caption_survives_pixel_phase_and_scale(self):
        image=cv2.imread(str(ASSETS/'finish-caption.png'));detector=EndDetector()
        for scale in [.75,1.,1.25]:
            caption=cv2.resize(image,None,fx=scale,fy=scale)
            for dx,dy in [(0,0),(1,0),(0,1),(1,1)]:
                game=np.full((450,678,3),(45,105,150),np.uint8);h,w=caption.shape[:2]
                game[170+dy:170+dy+h,230+dx:230+dx+w]=caption
                with self.subTest(scale=scale,dx=dx,dy=dy):self.assertTrue(detector.detect(game))

    def test_shape_fitting_small_roi_fails_closed(self):
        fitter=ShapeFitter(np.ones((80,80),np.uint8))
        self.assertIsNone(fitter.fit(np.ones((40,40),np.uint8),(20,20),20))
    def test_fft_shape_registration_handles_edge_and_cache_size_changes(self):
        fitter=ShapeFitter(np.ones((50,50),np.uint8))
        for center in [(125,120),(35,40),(245,190),(125,120)]:
            frame=np.zeros((240,300),np.uint8);x,y=center
            frame[y-25:y+25,x-25:x+25]=255
            result=fitter.fit(frame,np.array(center,dtype=float),65)
            self.assertIsNotNone(result);self.assertLess(np.linalg.norm(result['center']-center),8)
            self.assertLessEqual(len(fitter.spectra),2)
