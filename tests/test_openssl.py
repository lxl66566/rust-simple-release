import tempfile
import unittest
from pathlib import Path
from unittest import mock

import toml

from rust_simple_release.openssl import lock_has_openssl, patch_manifests


class LockHasOpensslTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_missing_file(self):
        assert lock_has_openssl(self.root / "Cargo.lock") is False

    def test_no_openssl(self):
        lock = self.root / "Cargo.lock"
        lock.write_text('[[package]]\nname = "libc"\nversion = "0.2"\n')
        assert lock_has_openssl(lock) is False

    def test_openssl_present(self):
        lock = self.root / "Cargo.lock"
        lock.write_text('[[package]]\nname = "openssl"\nversion = "0.10.64"\n')
        assert lock_has_openssl(lock) is True


class PatchManifestsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write(self, rel: str, content: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def load(self, path: Path) -> dict:
        return toml.loads(path.read_text())

    def test_string_dep_rebuilt_as_table(self):
        path = self.write(
            "app/Cargo.toml",
            '[package]\nname = "app"\nversion = "0.1.0"\n\n[dependencies]\nopenssl = "0.10"\n',
        )
        patch_manifests(self.root)
        assert self.load(path)["dependencies"]["openssl"] == {
            "version": "0.10",
            "features": ["vendored"],
        }

    def test_workspace_dep_gets_features_but_no_version(self):
        path = self.write(
            "app/Cargo.toml",
            "[package]\n"
            'name = "app"\n'
            'version = "0.1.0"\n\n'
            "[dependencies]\n"
            "openssl = { workspace = true }\n",
        )
        patch_manifests(self.root)
        dep = self.load(path)["dependencies"]["openssl"]
        assert dep == {"workspace": True, "features": ["vendored"]}
        assert "version" not in dep

    def test_existing_features_union_preserved(self):
        path = self.write(
            "app/Cargo.toml",
            "[package]\n"
            'name = "app"\n'
            'version = "0.1.0"\n\n'
            "[dependencies]\n"
            'openssl = { version = "0.10", features = ["std"] }\n',
        )
        patch_manifests(self.root)
        dep = self.load(path)["dependencies"]["openssl"]
        assert dep["features"] == ["std", "vendored"]

    def test_manifest_without_openssl_untouched(self):
        self.write(
            "app/Cargo.toml",
            '[package]\nname = "app"\nversion = "0.1.0"\n\n[dependencies]\nopenssl = "0.10"\n',
        )
        plain_content = (
            "[package]\nname = \"plain\"\nversion = \"0.1.0\"\n\n[dependencies]\nserde = \"1\"\n"
        )
        plain = self.write("plain/Cargo.toml", plain_content)
        patch_manifests(self.root)
        assert plain.read_text() == plain_content

    def test_transitive_fallback_injects_into_every_package(self):
        workspace_content = '[workspace]\nmembers = ["a", "b"]\n'
        root = self.write("Cargo.toml", workspace_content)
        a = self.write(
            "a/Cargo.toml",
            '[package]\nname = "a"\nversion = "0.1.0"\n\n[dependencies]\nlibc = "0.2"\n',
        )
        b = self.write("b/Cargo.toml", '[package]\nname = "b"\nversion = "0.1.0"\n')
        patch_manifests(self.root)
        # workspace manifests are never injected
        assert root.read_text() == workspace_content
        injected = {"version": "*", "features": ["vendored"]}
        a_data = self.load(a)
        assert a_data["dependencies"]["libc"] == "0.2"
        assert a_data["dependencies"]["openssl"] == injected
        assert self.load(b)["dependencies"]["openssl"] == injected

    def test_workspace_dependencies_patched_members_untouched(self):
        root = self.write(
            "Cargo.toml",
            "[workspace]\n"
            'members = ["member"]\n\n'
            "[workspace.dependencies]\n"
            'openssl = "0.10"\n',
        )
        member_content = (
            "[package]\nname = \"member\"\nversion = \"0.1.0\"\n\n[dependencies]\nserde = \"1\"\n"
        )
        member = self.write("member/Cargo.toml", member_content)
        patch_manifests(self.root)
        assert self.load(root)["workspace"]["dependencies"]["openssl"] == {
            "version": "0.10",
            "features": ["vendored"],
        }
        assert member.read_text() == member_content

    def test_target_cfg_sections_scanned(self):
        path = self.write(
            "app/Cargo.toml",
            "[package]\n"
            'name = "app"\n'
            'version = "0.1.0"\n\n'
            "[target.'cfg(unix)'.dependencies]\n"
            'openssl = "0.10"\n',
        )
        patch_manifests(self.root)
        dep = self.load(path)["target"]["cfg(unix)"]["dependencies"]["openssl"]
        assert dep == {"version": "0.10", "features": ["vendored"]}

    def test_manifests_under_target_directory_skipped(self):
        pkg = self.write(
            "pkg/Cargo.toml",
            "[package]\nname = \"pkg\"\nversion = \"0.1.0\"\n\n[dependencies]\nserde = \"1\"\n",
        )
        artifact_content = (
            "[package]\nname = \"artifact\"\nversion = \"0.1.0\"\n\n[dependencies]\nopenssl = \"0.10\"\n"
        )
        artifact = self.write("pkg/target/debug/Cargo.toml", artifact_content)
        patch_manifests(self.root)
        assert artifact.read_text() == artifact_content
        # the openssl under target/ is invisible, so the fallback kicks in
        assert self.load(pkg)["dependencies"]["openssl"] == {
            "version": "*",
            "features": ["vendored"],
        }

    def test_idempotent_second_run_rewrites_nothing(self):
        path = self.write(
            "app/Cargo.toml",
            '[package]\nname = "app"\nversion = "0.1.0"\n\n[dependencies]\nopenssl = "0.10"\n',
        )
        patch_manifests(self.root)
        first = path.read_text()
        with mock.patch.object(Path, "write_text") as write:
            patch_manifests(self.root)
        write.assert_not_called()
        assert path.read_text() == first
