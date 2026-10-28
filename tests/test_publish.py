import subprocess
import unittest
from pathlib import Path
from unittest import mock

from rust_simple_release.publish import Uploader, create_release

from .utils import set_env


class UploaderTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch(
            "rust_simple_release.publish.upload_one_file", return_value=True
        )
        self.upload_one_file = patcher.start()
        self.addCleanup(patcher.stop)

    def test_success_flow(self):
        uploader = Uploader()
        self.addCleanup(uploader.wait)
        files = [Path("a.zip"), Path("b.tar.gz")]
        for file in files:
            uploader.submit(file)
        uploader.wait()
        assert self.upload_one_file.call_args_list == [
            mock.call(files[0]),
            mock.call(files[1]),
        ]
        assert uploader.failed == []

    def test_failed_uploads_aggregated(self):
        self.upload_one_file.side_effect = lambda file: file.name == "good.zip"
        uploader = Uploader()
        self.addCleanup(uploader.wait)
        bad, good = Path("bad.zip"), Path("good.zip")
        uploader.submit(bad)
        uploader.submit(good)
        uploader.wait()
        assert uploader.failed == [bad]

    def test_submit_after_wait_raises(self):
        uploader = Uploader()
        uploader.wait()
        with self.assertRaises(RuntimeError):
            uploader.submit(Path("late.zip"))


class CreateReleaseTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(set_env("GITHUB_REF_NAME", "v1.0.0"))
        self.addCleanup(set_env("INPUT_RELEASE_OPTIONS", None))
        patcher = mock.patch("rust_simple_release.publish.rc")
        self.rc = patcher.start()
        self.addCleanup(patcher.stop)

    def test_existing_release_skips_create(self):
        self.rc.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        create_release()
        assert self.rc.call_count == 1
        assert 'gh release view "v1.0.0"' in self.rc.call_args.args[0]

    def test_creates_missing_release_with_options(self):
        self.addCleanup(set_env("INPUT_RELEASE_OPTIONS", "--title new"))
        created = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        self.rc.side_effect = [
            subprocess.CalledProcessError(1, "gh release view"),
            created,
        ]
        create_release()
        assert self.rc.call_count == 2
        create_cmd = self.rc.call_args_list[1].args[0]
        assert 'gh release create "v1.0.0"' in create_cmd
        assert "--title new" in create_cmd

    def test_create_failure_exits_with_captured_output(self):
        created = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="stdout msg", stderr="stderr msg"
        )
        self.rc.side_effect = [
            subprocess.CalledProcessError(1, "gh release view"),
            created,
            subprocess.CalledProcessError(1, "gh release view"),
        ]
        with self.assertRaises(SystemExit) as ctx:
            create_release()
        assert ctx.exception.code == 1

    def test_create_race_lost_to_concurrent_job_is_tolerated(self):
        lost = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Release.tag_name already exists"
        )
        self.rc.side_effect = [
            subprocess.CalledProcessError(1, "gh release view"),
            lost,
            subprocess.CompletedProcess(args=[], returncode=0),
        ]
        create_release()
        assert self.rc.call_count == 3
        assert 'gh release view "v1.0.0"' in self.rc.call_args_list[2].args[0]
