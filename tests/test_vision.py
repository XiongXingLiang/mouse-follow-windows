import unittest
import cv2,numpy as np
from follower.detection import GameDetector,EndDetector,Region,to_screen,working_frame
from follower.paths import ASSETS
from follower.motion_geometry import ShapeFitter
from follower.tracker import VisualTracker
class VisionTests(unittest.TestCase):
    def test_screen_mapping_and_negative_monitor_origin(self):
        roi=Region(252,98,678,450);monitor={'left':-1920,'top':0}
        self.assertEqual(to_screen((338,297),roi,monitor),(-1330,320))
    def test_scale_mapping(self):
        self.assertEqual(to_screen((339,300),Region(100,80,1356,900),{'left':0,'top':0}),(778,530))
    def test_plain_background_is_not_game(self):
        self.assertIsNone(GameDetector().find(np.full((720,1280,3),90,np.uint8)))
    def test_game_title_and_texture_required(self):
        frame=np.full((720,1280,3),40,np.uint8)
        # Synthetic brown viewport + real title asset; no private recording needed in CI.
        frame[98:548,252:930]=(45,105,150)
        title=cv2.imread(str(ASSETS/'game-title.png'));frame[70:98,244:444]=title
        detector=GameDetector();match=detector.find(frame)
        self.assertIsNotNone(match);self.assertEqual(match.roi,Region(252,98,678,450));self.assertTrue(detector.present(frame,match))
        frame[98:548,252:930]=0;self.assertFalse(detector.present(frame,match))
    def test_completion_caption(self):
        game=np.full((450,678,3),(45,105,150),np.uint8)
        detector=EndDetector();self.assertFalse(detector.detect(game))
        caption=cv2.imread(str(ASSETS/'finish-caption.png'));h,w=caption.shape[:2];game[170:170+h,230:230+w]=caption
        self.assertTrue(detector.detect(game))
    def test_white_shape_bootstrap_and_no_shape(self):
        tracker=VisualTracker();game=np.full((450,678,3),(45,105,150),np.uint8)
        self.assertIsNone(tracker.update(working_frame(game),0.))
        cv2.rectangle(game,(290,180),(370,260),(255,255,255),-1)
        result=tracker.update(working_frame(game),.1);self.assertEqual(result.mode,'white');self.assertLess(np.linalg.norm(np.array(result.center)-[330,295]),2)
    def test_geometry_ignores_brightness_bias(self):
        evidence=np.zeros((240,300),np.float32);evidence[85:155,115:185]=1;evidence[85:155,115:130]=100
        result=ShapeFitter(np.ones((70,70),np.uint8)).fit(evidence,np.array([150.,120.]),65)
        self.assertLess(np.linalg.norm(result['center']-[150,120]),5)
