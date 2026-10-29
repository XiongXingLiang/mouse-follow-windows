if __name__=='__main__':
    import sys
    if '--self-test' in sys.argv:
        from admin.issuer import issue,generate_keys
        print('ISSUER_SELF_TEST_OK')
    else:
        from admin.gui import main
        main()
