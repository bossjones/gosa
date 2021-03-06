import unittest
from gosa.backend.plugins.password.filter.detect_locking import *

class DetectAccountLockStatusTestCase(unittest.TestCase):

    def test_filter(self):
        filter = DetectAccountLockStatus(None)
        testDict = {
            "userPassword":{
                "in_value": ["{CRYPT}jsafdüudfopndv38"]
            },
            "attr": {
                "value": [True]
            }
        }
        (new_key, newDict) = filter.process(None, "attr", testDict)
        assert list(newDict["attr"]["value"])[0] == False

        testDict["userPassword"]["in_value"] = ["{CRYPT}!jsafdüudfopndv38"]
        (new_key, newDict) = filter.process(None, "attr", testDict)
        assert list(newDict["attr"]["value"])[0] == True