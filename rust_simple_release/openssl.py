import os
from pathlib import Path
from typing import Any

import toml

from .inputs import get_input_bool
from .logutil import info
from .proc import apt, rc
from .system import Os

_DEP_SECTION_NAMES = ("dependencies", "dev-dependencies", "build-dependencies")


def vendor_openssl() -> None:
    if not get_input_bool("INPUT_OPENSSL_VENDORED", default=True):
        info("openssl vendoring is disabled")
        return

    if not lock_has_openssl(Path("Cargo.lock")):
        return

    # add vendored feature
    # note: rewrites Cargo.toml files in the CI environment when openssl is in Cargo.lock
    # note: manifests with a direct openssl dependency gain the vendored feature;
    # a transitive-only openssl gets a direct dependency injected into every package
    patch_manifests(Path("."))

    install_openssl_packages()


def lock_has_openssl(lock: Path) -> bool:
    """
    whether the Cargo.lock file resolves an openssl package.
    """
    if not lock.exists():
        return False
    lock_data = toml.loads(lock.read_text())
    return any(pkg.get("name") == "openssl" for pkg in lock_data.get("package", []))


def patch_manifests(root: Path) -> None:
    """
    add the `vendored` feature to every direct openssl dependency in all
    Cargo.toml manifests under `root`.
    """
    parsed = [
        (path, toml.loads(path.read_text()))
        for path in root.rglob("Cargo.toml")
        # skip build artifacts nested under a target directory
        if "target" not in path.parts
    ]

    found_direct = False
    for path, data in parsed:
        if _patch_manifest(data):
            path.write_text(toml.dumps(data))
            info(f"patched openssl dependency in `{path}`")
        found_direct |= bool(_direct_openssl_sections(data))

    if found_direct:
        return
    # cargo only activates the `vendored` feature on the openssl crate when some
    # direct dependent in the resolve graph requests it, so a transitive-only
    # openssl still needs a direct dependency injected into every package.
    for path, data in parsed:
        if "workspace" in data or "package" not in data:
            continue
        data.setdefault("dependencies", {})["openssl"] = {
            "version": "*",
            "features": ["vendored"],
        }
        path.write_text(toml.dumps(data))
        info(f"added direct openssl dependency to `{path}`")


def install_openssl_packages() -> None:
    """
    install the openssl system package for the host os.
    """
    host = Os.from_host()
    if host == Os.LINUX:
        apt("pkg-config", "libssl-dev")
    elif host == Os.MACOS:
        rc("brew install openssl")
    else:
        # https://github.com/sfackler/rust-openssl/blob/master/.github/workflows/ci.yml
        if vcpkg_installation_root := os.environ.get("VCPKG_INSTALLATION_ROOT"):
            os.environ["VCPKG_ROOT"] = vcpkg_installation_root
        rc("vcpkg install openssl:x64-windows-static-md")


def _patch_manifest(data: dict[str, Any]) -> bool:
    """
    add the `vendored` feature to the direct openssl entries of one parsed
    manifest. return whether the manifest changed.
    """
    changed = False
    for section in _direct_openssl_sections(data):
        new_dep, dep_changed = _patch_dep(section["openssl"])
        if dep_changed:
            section["openssl"] = new_dep
            changed = True
    return changed


def _direct_openssl_sections(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    dependency tables holding a direct `openssl` entry:
    a manifest with a [workspace] table only exposes [workspace.dependencies];
    any other manifest exposes dependencies, dev-dependencies, build-dependencies
    and the same three sections under each target.* entry.
    """
    if "workspace" in data:
        section = data["workspace"].get("dependencies")
        if isinstance(section, dict) and "openssl" in section:
            return [section]
        return []
    return [s for s in _dependency_sections(data) if "openssl" in s]


def _dependency_sections(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    the dependency tables of a package manifest: dependencies, dev-dependencies,
    build-dependencies, and the same three under each target.* entry.
    """
    sections: list[dict[str, Any]] = []
    tables = [data, *(data.get("target") or {}).values()]
    for name in _DEP_SECTION_NAMES:
        for table in tables:
            if isinstance(section := table.get(name), dict):
                sections.append(section)
    return sections


def _patch_dep(dep: str | dict[str, Any]) -> tuple[str | dict[str, Any], bool]:
    """
    add the `vendored` feature to one openssl dependency spec.
    return the (possibly rebuilt) spec and whether it changed;
    the str form cannot carry the feature, so it is rebuilt as a table.
    """
    if isinstance(dep, str):
        return {"version": dep, "features": ["vendored"]}, True
    changed = False
    features = list(dep.get("features") or [])
    if "vendored" not in features:
        features.append("vendored")
        dep["features"] = features
        changed = True
    # `version` is required for a valid spec unless the source is already pinned
    if not any(key in dep for key in ("version", "workspace", "path", "git")):
        dep["version"] = "*"
        changed = True
    return dep, changed
