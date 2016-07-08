#!/usr/bin/python3

import unittest
import os
from gosa.common.env import *
from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import Session


# Todo: Mocking
class EnvTestCase(unittest.TestCase):

    def setUp(self):
        self.old_environ = os.environ.copy()
        virt_env = os.environ.get("VIRTUAL_ENV")
        
        if virt_env:
            os.environ.update({"GOSA_CONFIG_DIR": os.path.join(os.path.dirname(os.path.realpath(__file__)), "../test.conf")})

    def test_Environment(self):
        e = Environment.getInstance()
        
        e.requestRestart()
        self.assertTrue(e.reset_requested)
        
        self.assertIsInstance(e.getDatabaseEngine("backend-database"), Engine)
        self.assertIsInstance(e.getDatabaseEngine("backend-database", key="database"), Engine)
        if not e.config.get("notexistantsection"):
            self.assertRaises(Exception, e.getDatabaseEngine, "notexistantsection")
            self.assertRaises(Exception, e.getDatabaseEngine, "notexistantsection", key="db")
        self.assertIsInstance(e.getDatabaseSession("backend-database"), Session)
        
        self.assertEqual(e, Environment.getInstance())
        
        del e
        Environment.reset()
        
        Environment.getInstance()
        
        # Note: References of the Environment object may be hold by others.
        # An reset followed by getInstance would lead to multiple instances.
    
    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_environ)