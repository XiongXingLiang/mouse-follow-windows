"""Private owner edition: intentionally not distributed to ordinary users."""
if __name__=='__main__':
    import sys
    from admin.owner_access import OwnerLicense
    if '--self-test' in sys.argv:
        from follower.detection import GameDetector,EndDetector
        from follower.tracker import VisualTracker
        grant=OwnerLicense().check()
        assert grant.plan=='permanent' and grant.expires_at is None
        GameDetector();EndDetector();VisualTracker()
        print('OWNER_CLIENT_SELF_TEST_OK')
    else:
        from follower.app import main
        main(license_factory=OwnerLicense,owner_edition=True)
