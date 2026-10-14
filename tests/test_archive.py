import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from rust_simple_release.archive import (
    create_tar_gz_in_tmp,
    create_zip_in_tmp,
    pack,
    target_to_archive_format,
)

from .utils import chdir, set_env


def normalized(names: list[str]) -> list[str]:
    """sorted forward-slash arcnames, so assertions hold on windows and posix."""
    return sorted(name.replace("\\", "/") for name in names)


class EntriesTest(unittest.TestCase):
    """a single-file entry and a nested-directory entry must land under the same
    relative arcnames in both the zip and the tar outputs."""

    expected = ["loose.txt", "pkg/sub/inner.txt", "pkg/top.txt"]

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "loose.txt").write_text("loose")
        nested = root / "pkg"
        (nested / "sub").mkdir(parents=True)
        (nested / "top.txt").write_text("top")
        (nested / "sub" / "inner.txt").write_text("inner")

        entries = [root / "loose.txt", nested]
        self.zip_path = create_zip_in_tmp("rsr-test-entries", entries)
        self.tar_path = create_tar_gz_in_tmp("rsr-test-entries", entries)
        self.addCleanup(lambda: self.zip_path.unlink(missing_ok=True))
        self.addCleanup(lambda: self.tar_path.unlink(missing_ok=True))

    def zip_names(self) -> list[str]:
        with zipfile.ZipFile(self.zip_path) as zf:
            return normalized(zf.namelist())

    def tar_names(self) -> list[str]:
        with tarfile.open(self.tar_path) as tar:
            return normalized(tar.getnames())

    def test_single_file_entry_named_by_basename(self):
        assert "loose.txt" in self.zip_names()
        assert "loose.txt" in self.tar_names()

    def test_nested_directory_entry_walked_relatively(self):
        assert self.zip_names() == self.expected
        assert self.tar_names() == self.expected

    def test_zip_and_tar_arcnames_consistent(self):
        assert self.zip_names() == self.tar_names()


class TargetToArchiveFormatTest(unittest.TestCase):
    def test_explicit_targets(self):
        assert target_to_archive_format("x86_64-pc-windows-msvc") == "zip"
        assert target_to_archive_format("aarch64-pc-windows-msvc") == "zip"
        assert target_to_archive_format("x86_64-unknown-linux-gnu") == "tar"
        assert target_to_archive_format("aarch64-apple-darwin") == "tar"

    def test_empty_target_uses_host(self):
        for system, expected in (("Windows", "zip"), ("Linux", "tar"), ("Darwin", "tar")):
            with self.subTest(system=system):
                with mock.patch("platform.system", return_value=system):
                    assert target_to_archive_format("") == expected
                    assert target_to_archive_format(None) == expected


class PackTest(unittest.TestCase):
    TRIPLE = "x86_64-pc-windows-msvc"  # zip format, independent of the host os

    def test_packs_extra_file_and_built_output_into_zip(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cwd = Path(tmp.name)
        self.addCleanup(chdir(cwd))  # keep target/ pollution out of the repo

        extra = cwd / "extra.txt"
        extra.write_text("extra")
        release_dir = cwd / "target" / self.TRIPLE / "release"
        release_dir.mkdir(parents=True)
        (release_dir / "fakebin").write_text("binary")
        self.addCleanup(set_env("INPUT_FILES_TO_PACK", str(extra)))

        with mock.patch(
            "rust_simple_release.archive.get_output_filenames",
            return_value=["fakebin"],
        ) as get_outputs:
            archive = pack("rsr-test-pack", self.TRIPLE, package="action-test")
        self.addCleanup(lambda: archive.unlink(missing_ok=True))

        assert archive == Path(tempfile.gettempdir()) / "rsr-test-pack.zip"
        assert archive.exists()
        get_outputs.assert_called_once_with(self.TRIPLE, package="action-test")
        with zipfile.ZipFile(archive) as zf:
            assert normalized(zf.namelist()) == ["extra.txt", "fakebin"]
