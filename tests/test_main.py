import unittest
from unittest import mock

import main

from .utils import set_env


class MainTest(unittest.TestCase):
    def setUp(self):
        for name in (
            "main.create_release",
            "main.install_toolchain",
            "main.vendor_openssl",
        ):
            patcher = mock.patch(name)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch("main.Uploader")
        self.uploader = patcher.start().return_value
        self.uploader.failed = []
        self.addCleanup(patcher.stop)
        patcher = mock.patch("main.build_one_target")
        self.build_one_target = patcher.start()
        self.build_one_target.side_effect = lambda target: mock.Mock(name=target)
        self.addCleanup(patcher.stop)
        self.addCleanup(set_env("INPUT_TARGETS", None))

    def test_unknown_os_target_skipped_with_warning(self):
        self.addCleanup(set_env("INPUT_TARGETS", "x86_64-unknown-freebsd,x86_64-unknown-linux-gnu"))
        # warn() must go through logging, not the ::warning:: workflow command
        self.addCleanup(set_env("GITHUB_ACTIONS", None))
        with mock.patch("platform.system", return_value="Linux"):
            with self.assertLogs(level="WARNING") as logs:
                main.main()
        self.build_one_target.assert_called_once_with("x86_64-unknown-linux-gnu")
        self.uploader.submit.assert_called_once()
        assert any("freebsd" in line for line in logs.output)

    def test_platform_mismatch_target_skipped(self):
        self.addCleanup(set_env("INPUT_TARGETS", "x86_64-pc-windows-msvc"))
        with mock.patch("platform.system", return_value="Linux"):
            main.main()
        self.build_one_target.assert_not_called()
        self.uploader.submit.assert_not_called()

    def test_empty_targets_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            main.main()
        assert ctx.exception.code == 1
