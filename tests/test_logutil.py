import contextlib
import io
import logging
import unittest

from rust_simple_release.logutil import colored, error, warn

from .utils import set_env


class ColoredTest(unittest.TestCase):
    def test_prefix_and_suffix_per_color(self):
        for color, prefix in (
            ("red", "\033[0;31;31m"),
            ("green", "\033[0;31;32m"),
            ("yellow", "\033[0;31;33m"),
            ("blue", "\033[0;31;34m"),
        ):
            with self.subTest(color=color):
                assert colored("msg", color) == f"{prefix}msg\033[0m"

    def test_unknown_color_has_no_prefix(self):
        assert colored("msg", "purple") == "msg\033[0m"


class GithubActionsOutputTest(unittest.TestCase):
    """on GitHub Actions warn/error must emit plain workflow-command lines."""

    def test_warn(self):
        self.addCleanup(set_env("GITHUB_ACTIONS", "true"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            warn("careful")
        assert buf.getvalue() == "::warning:: careful\n"

    def test_error(self):
        self.addCleanup(set_env("GITHUB_ACTIONS", "true"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            error("broken")
        assert buf.getvalue() == "::error:: broken\n"

    def test_no_ansi_codes(self):
        self.addCleanup(set_env("GITHUB_ACTIONS", "true"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            warn("careful")
            error("broken")
        assert "\033" not in buf.getvalue()


class ColoredLoggingTest(unittest.TestCase):
    """outside GitHub Actions warn/error go through logging with ANSI colors."""

    def test_warn(self):
        self.addCleanup(set_env("GITHUB_ACTIONS", None))
        with self.assertLogs(level=logging.WARNING) as logs:
            warn("careful")
        assert colored("careful", "yellow") in logs.output[0]

    def test_error(self):
        self.addCleanup(set_env("GITHUB_ACTIONS", None))
        with self.assertLogs(level=logging.ERROR) as logs:
            error("broken")
        assert colored("broken", "red") in logs.output[0]
