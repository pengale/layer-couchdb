#!/usr/bin/env python3

import os
import sys
import unittest

class TestConfig(unittest.TestCase):
    """
    Test our config helper to verify that it does the right thing.
    """

    def _temp_environ_hack(self):
        """
        @HACK Since "charm test" does not work with the current devel
        version of juju2, we are going to do terrible things to our
        environment and path in order to make the tests runnable in
        our devel dir. This hack should not make it into production
        code!
        """
        if not "reactive" in os.listdir() and not "tests" in os.listdir():
            # This is a hack, but that doesn't mean we shouldn't drop
            # any dev running this a polite hint about why the hack is
            # breaking, if it breaks.
            raise Exception(
                "This test will not run unless you start it from the root of the charm.")

        sys.path.append(os.getcwd())

        self._environ_hack = True  # Flag for our tearDown.

    def setUp(self):
        self._environ_hack = False
        self._temp_environ_hack()
        self._expected_files = []  # tearDown will use this list. Any
                                   # tests that create files should
                                   # populate it.

    def tearDown(self):
        # Clean up any created files
        for path in self._expected_files:
            os.remove(path)

        # Undo our path hacks
        if self._environ_hack:
            sys.path.pop()

    def test_config(self):
        """Test to verify that our _set_couch_config writes files to
        the right place.

        TODO: Test backup logic by created local.ini and default.ini
        first, and verifying that they get backed up.

        TODO: improve the patch of config in the body of this routine
        so that we get real values, and validate the the values wind
        up in the right place.

        """
        from reactive import couchdb as reactive_handlers  # This is what happens, Larry.
                                                           # This is what happens when you use
                                                           # a environ hack!
        reactive_handlers.config = lambda *args, **kwargs: "foo"  # TODO: using mock.patch would
                                                                  # be more polite.

        self._expected_files = [
            '/tmp/local.ini', '/tmp/default.ini', '/tmp/juju_generated.ini'
        ]

        reactive_handlers._set_couch_config(config_path="/tmp")
        for path in self._expected_files:
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.isfile(path))

if __name__ == '__main__':
    unittest.main()
