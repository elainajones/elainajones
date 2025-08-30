import logging
import unittest

import helpers

logging.disable(level='ERROR')


class TestHelpers(unittest.TestCase):
    def test_blackbox_dec(self):
        """Simple functional test for the blackbox_logger decorator.

        Ensures that args/kwargs/defaults are handled properly.

        Failure would be if things break or proper values aren't passed.
        """

        @helpers.blackbox_logger
        def a():
            """No args
            """
            return True

        @helpers.blackbox_logger
        def b(a, b):
            """Only args
            """
            return [a, b]

        @helpers.blackbox_logger
        def c(a, b=False):
            """Arg and default
            """
            return [a, b]

        @helpers.blackbox_logger
        def d(a=False, b=False):
            """Only defaults
            """
            return [a, b]

        # Should not break
        assert a() is True

        # Test args only
        assert all(b(True, True)) is True
        # Test arg and kwarg
        assert all(b(True, b=True)) is True
        # Test kwargs only
        assert all(b(a=True, b=True)) is True

        # Test args only
        assert all(c(True, True)) is True
        # Test arg and kwarg
        assert all(c(True, b=True)) is True
        # Test kwargs only
        assert all(c(a=True, b=True)) is True
        # Test arg and default
        assert any(c(True)) is True
        # Test kwarg and default
        assert any(c(a=True)) is True

        # Test args only
        assert all(d(True, True)) is True
        # Test arg and kwarg
        assert all(d(True, b=True)) is True
        # Test kwargs only
        assert all(d(a=True, b=True)) is True
        # Test arg and default
        assert any(d(True)) is True
        # Test kwarg and default
        assert any(d(a=True)) is True
        # Test default only
        assert any(d()) is False
