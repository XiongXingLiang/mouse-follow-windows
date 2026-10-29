"""Owner-only permanent entitlement, packaged only in the separate admin edition."""
from follower.license_core import Grant

class OwnerLicense:
    def __init__(self):
        self.grant=Grant('owner-edition','owner','permanent',0,None)
        self.error=''
    def check(self):
        return self.grant
