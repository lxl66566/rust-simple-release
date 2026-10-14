import shutil
import unittest

from rust_simple_release.cargo import (
    cargo_metadata,
    create_flags,
    get_output_filenames,
    get_selected_package_metadata,
)

from .utils import set_env

LINUX = "x86_64-unknown-linux-gnu"
WINDOWS = "x86_64-pc-windows-msvc"
MACOS = "aarch64-apple-darwin"


@unittest.skipUnless(shutil.which("cargo"), "cargo not available")
class CargoMetadataTest(unittest.TestCase):
    def setUp(self):
        cargo_metadata.cache_clear()
        self.addCleanup(cargo_metadata.cache_clear)

    def test_metadata_version(self):
        assert cargo_metadata()["version"] == 1

    def test_get_selected_package_metadata(self):
        assert get_selected_package_metadata("action-test")["name"] == "action-test"


@unittest.skipUnless(shutil.which("cargo"), "cargo not available")
class GetOutputFilenamesTest(unittest.TestCase):
    def setUp(self):
        cargo_metadata.cache_clear()
        self.addCleanup(cargo_metadata.cache_clear)
        for name in ("INPUT_BINS", "INPUT_LIB", "INPUT_PACKAGE"):
            self.addCleanup(set_env(name, None))

    def test_bins_without_exe_on_linux(self):
        assert get_output_filenames(LINUX, package="action-test") == [
            "my-action-test",
            "my-action-test2",
        ]

    def test_exe_appended_on_windows_and_not_double_appended(self):
        expected = ["my-action-test.exe", "my-action-test2.exe"]
        assert get_output_filenames(WINDOWS, package="action-test") == expected
        assert get_output_filenames(WINDOWS, package="action-test") == expected

    def test_cdylib_naming_per_os(self):
        assert get_output_filenames(LINUX, package="lib_test") == ["liblib_test.so"]
        assert get_output_filenames(WINDOWS, package="lib_test") == ["lib_test.dll"]
        assert get_output_filenames(MACOS, package="lib_test") == ["liblib_test.dylib"]

    def test_input_bins_filters_and_preserves_order(self):
        self.addCleanup(set_env("INPUT_BINS", "my-action-test2, my-action-test"))
        assert get_output_filenames(LINUX, package="action-test") == [
            "my-action-test2",
            "my-action-test",
        ]

    def test_input_bins_not_a_subset_raises(self):
        self.addCleanup(set_env("INPUT_BINS", "nonexistent-bin"))
        with self.assertRaises(AssertionError):
            get_output_filenames(LINUX, package="action-test")

    def test_input_lib_false_excludes_lib_when_bins_exist(self):
        # no fixture has both bins and a lib target; action-test is bins-only,
        # so INPUT_LIB=false must keep the lib path out entirely.
        self.addCleanup(set_env("INPUT_LIB", "false"))
        assert get_output_filenames(LINUX, package="action-test") == [
            "my-action-test",
            "my-action-test2",
        ]

    def test_input_lib_true_on_libless_package_raises(self):
        # INPUT_LIB=true takes the lib path on a bins-only package and must hit
        # the missing-lib-target assertion.
        self.addCleanup(set_env("INPUT_LIB", "true"))
        with self.assertRaises(AssertionError):
            get_output_filenames(LINUX, package="action-test")

    def test_lib_only_package_outputs_lib_even_with_input_lib_false(self):
        self.addCleanup(set_env("INPUT_LIB", "false"))
        assert get_output_filenames(LINUX, package="lib_test") == ["liblib_test.so"]


@unittest.skipUnless(shutil.which("cargo"), "cargo not available")
class CreateFlagsTest(unittest.TestCase):
    def setUp(self):
        cargo_metadata.cache_clear()
        self.addCleanup(cargo_metadata.cache_clear)

    def test_musl_cdylib_gets_crt_static_flag(self):
        assert (
            create_flags("x86_64-unknown-linux-musl", package="lib_test")
            == "-C target-feature=-crt-static"
        )

    def test_gnu_target_gets_no_flag(self):
        assert create_flags(LINUX, package="lib_test") is None

    def test_package_without_lib_gets_no_flag(self):
        assert create_flags("x86_64-unknown-linux-musl", package="action-test") is None
