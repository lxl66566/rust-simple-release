import unittest
from unittest import mock

from rust_simple_release.system import (
    Os,
    os_from_target,
    target_corresponds_to_host,
)


class FromTripleTest(unittest.TestCase):
    def test_windows(self):
        assert Os.from_triple("x86_64-pc-windows-msvc") == Os.WINDOWS
        assert Os.from_triple("i686-pc-windows-gnu") == Os.WINDOWS
        assert Os.from_triple("aarch64-pc-windows-msvc") == Os.WINDOWS

    def test_linux(self):
        assert Os.from_triple("x86_64-unknown-linux-gnu") == Os.LINUX
        assert Os.from_triple("aarch64-unknown-linux-musl") == Os.LINUX

    def test_macos_darwin(self):
        assert Os.from_triple("x86_64-apple-darwin") == Os.MACOS
        assert Os.from_triple("aarch64-apple-darwin") == Os.MACOS

    def test_macos_apple(self):
        assert Os.from_triple("aarch64-apple-ios") == Os.MACOS

    def test_os_component_case_insensitive(self):
        assert Os.from_triple("x86_64-APPLE-DARWIN") == Os.MACOS

    def test_unknown_os_raises(self):
        for triple in ("x86_64-unknown-freebsd", "riscv64gc-unknown-none-elf"):
            with self.subTest(triple=triple):
                with self.assertRaises(ValueError):
                    Os.from_triple(triple)


class FromHostTest(unittest.TestCase):
    def test_windows(self):
        with mock.patch("platform.system", return_value="Windows"):
            assert Os.from_host() == Os.WINDOWS

    def test_linux(self):
        with mock.patch("platform.system", return_value="Linux"):
            assert Os.from_host() == Os.LINUX

    def test_darwin_maps_to_macos(self):
        with mock.patch("platform.system", return_value="Darwin"):
            assert Os.from_host() == Os.MACOS

    def test_unknown_host_raises(self):
        with mock.patch("platform.system", return_value="SunOS"):
            with self.assertRaises(ValueError):
                Os.from_host()


class OsFromTargetTest(unittest.TestCase):
    def test_triple_parsed(self):
        assert os_from_target("x86_64-pc-windows-msvc") == Os.WINDOWS

    def test_empty_or_none_refers_to_host(self):
        for target in ("", None):
            with self.subTest(target=target):
                with mock.patch("platform.system", return_value="Linux"):
                    assert os_from_target(target) == Os.LINUX


class TargetCorrespondsToHostTest(unittest.TestCase):
    def test_matching(self):
        for system, triple in (
            ("Windows", "aarch64-pc-windows-msvc"),
            ("Linux", "x86_64-unknown-linux-musl"),
            ("Darwin", "x86_64-apple-darwin"),
        ):
            with self.subTest(system=system):
                with mock.patch("platform.system", return_value=system):
                    assert target_corresponds_to_host(triple) is True

    def test_not_matching(self):
        with mock.patch("platform.system", return_value="Windows"):
            assert target_corresponds_to_host("x86_64-unknown-linux-gnu") is False
        with mock.patch("platform.system", return_value="Linux"):
            assert target_corresponds_to_host("x86_64-pc-windows-msvc") is False
