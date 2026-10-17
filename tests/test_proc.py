import subprocess
import unittest
from unittest import mock

from rust_simple_release.proc import rc, retry


class RetryTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("rust_simple_release.proc.time.sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def test_success_first_try(self):
        func = mock.Mock()
        assert retry(func) is True
        assert func.call_count == 1
        self.sleep.assert_not_called()

    def test_success_on_third_try(self):
        attempts = 0

        def flaky() -> None:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("boom")

        assert retry(flaky, times=5) is True
        assert attempts == 3
        assert self.sleep.call_count == 2

    def test_all_failures_return_false(self):
        func = mock.Mock(side_effect=ValueError("boom"))
        assert retry(func, times=3) is False
        assert func.call_count == 3

    def test_base_exception_propagates(self):
        func = mock.Mock(side_effect=KeyboardInterrupt)
        with self.assertRaises(KeyboardInterrupt):
            retry(func, times=3)
        assert func.call_count == 1
        self.sleep.assert_not_called()

    def test_sleep_between_attempts_only(self):
        func = mock.Mock(side_effect=ValueError("boom"))
        assert retry(func, times=3) is False
        assert self.sleep.call_args_list == [mock.call(2), mock.call(4)]


class RcTest(unittest.TestCase):
    def test_check_true_by_default(self):
        with self.assertRaises(subprocess.CalledProcessError) as ctx:
            rc("exit 3")
        assert ctx.exception.returncode == 3

    def test_check_false_returns_completed_process(self):
        result = rc("exit 3", check=False)
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 3

    def test_success(self):
        assert rc("exit 0").returncode == 0

    def test_runs_through_shell(self):
        result = rc("echo hello", capture_output=True, text=True)
        assert "hello" in (result.stdout or "")
