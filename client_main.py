if __name__=='__main__':
    import sys
    if '--self-test' in sys.argv:
        from follower.paths import ASSETS
        from follower.license_core import load_public_key
        from follower.detection import GameDetector,EndDetector
        from follower.tracker import VisualTracker
        load_public_key((ASSETS/'license-public.pem').read_bytes());GameDetector();EndDetector();VisualTracker()
        print('CLIENT_SELF_TEST_OK')
    else:
        from follower.app import main
        main()
