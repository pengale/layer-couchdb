#!/usr/bin/env python3

"""
Unit(ish) tests for our config helpers and handlers.

"""

import os
import sys

import mock
import unittest

# @HACK Since "charm test" does not appear to work with the current
# devel version of juju2, we are going to do terrible things to our
# environment and path in order to make the tests runnable in our
# devel dir. This hack should not make it into production code!
if not "reactive" in os.listdir() and not "tests" in os.listdir():
    # This is a hack, but that doesn't mean we shouldn't drop
    # any dev running this a polite hint about why the hack is
    # breaking, if it breaks.
    raise Exception(
        "This test will not run unless you start it from the root of the charm.")

sys.path.append(os.getcwd())
# END @HACK

from reactive import couchdb

class TestConfig(unittest.TestCase):
    """
    Test our config helper to verify that it does the right thing.

    """

    def setUp(self):
        self._expected_files = []  # tearDown will use this list. Any
                                   # tests that create files should
                                   # populate it.

    def tearDown(self):
        # Clean up any created files
        for path in self._expected_files:
            os.remove(path)

    @mock.patch('reactive.couchdb.leader_get')
    @mock.patch('reactive.couchdb.leader_set')
    def test_maybe_generate_passwords(self, mock_leader_set, mock_leader_get):
        """
        Basic tests for maybe_generate_passwords

        """
        # If we already have the passwords set, we shouldn't try to set them.
        mock_leader_get.return_value = True
        couchdb.maybe_generate_passwords()
        self.assertFalse(mock_leader_set.called)

        # If we don't have passwords set, we should set them.
        mock_leader_get.return_value = False
        couchdb.maybe_generate_passwords()
        self.assertTrue(mock_leader_get.called)

        # TODO: Mock out subprocess and verify that the password dict
        # gets populated properly.

    @mock.patch('reactive.couchdb.start')
    @mock.patch('reactive.couchdb.leader_get')
    def test_end_admin_party(self, mock_leader_get, mock_start):
        """
        Cursory test for end_admin_party -- just verify that it writes
        out a local.ini for now.

        """
        mock_leader_get.return_value = {
            'admin_pass': 'foo',
            'repl_pass': 'bar'
        }
        self._expected_files = ['/tmp/local.ini']
        with open('/tmp/local.ini', 'w') as f:
            f.write(';Test')

        couchdb.end_admin_party(config_path='/tmp')

        for path in self._expected_files:
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.isfile(path))

    @mock.patch('reactive.couchdb.config')
    def test_write_couch_configs(self, mock_config):
        """
        Test to verify that our _write_couch_configs routine writes files
        to the right place.

        """
        mock_config.return_value = 'foo'

        self._expected_files = ['/tmp/local.ini', '/tmp/default.ini']
        for path in self._expected_files:
            with open(path, 'w') as f:
                f.write(';Test')
        self._expected_files.append('/tmp/local.ini.bak')
        self._expected_files.append('/tmp/default.ini.bak')

        couchdb._write_couch_configs(config_path='/tmp')
        for path in self._expected_files:
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.isfile(path))

        # TODO: validate the contents of the config files


if __name__ == '__main__':
    unittest.main()
