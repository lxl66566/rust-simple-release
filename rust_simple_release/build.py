import os
import platform
from pathlib import Path

from .archive import pack
from .cargo import create_flags, get_selected_package_metadata
from .inputs import get_input, get_input_bool, get_input_list
from .logutil import info
from .proc import apt, binstall, rc
from .system import Os


def build_one_target(target: str) -> Path:
    """
    build one target and pack it.
    """
    cmd: list[str] = []
    build_env = os.environ.copy()
    rc(f"rustup target add {target}")

    if flag := create_flags(target):
        build_env["RUSTFLAGS"] = (
            (build_env.get("RUSTFLAGS") or "") + f" {flag}"
        ).strip()

    # do not use zigbuild on windows: unable to spawn zig.exe: InvalidWtf8 error: UnableToSpawnSelf
    # do not use zigbuild on macos: https://github.com/rust-cross/cargo-zigbuild/issues/275
    # do not use zigbuild on x86_64-unknown-linux-gnu: https://github.com/rust-cross/cargo-zigbuild/issues/327
    if (
        Os.from_host() != Os.WINDOWS
        and Os.from_host() != Os.MACOS
        and not (
            platform.architecture()[0] == "64bit"
            and target.startswith("x86_64")
            and target.endswith("gnu")
        )
    ):
        build_cmd = "zigbuild"
    else:
        build_cmd = "build"

    cmd.append(f"cargo {build_cmd} --release")
    cmd.append(f"--target {target}")
    if bins := get_input_list("INPUT_BINS"):
        for bin in bins:
            cmd.append(f"--bin {bin}")
    if get_input_bool("INPUT_LIB"):
        cmd.append("--lib")
    if features := get_input_list("INPUT_FEATURES"):
        cmd.append(f"--features {','.join(features)}")
    if package := get_input("INPUT_PACKAGE"):
        cmd.append(f"--package {package}")
    rc(" ".join(cmd), env=build_env)
    info(f"target {target} build success")

    archive_name = get_selected_package_metadata()["name"] + "-" + target
    artifact = pack(archive_name, target)

    info(f"target {target} packed")
    return artifact


def install_toolchain() -> None:
    input_targets = get_input("INPUT_TARGETS") or ""

    def find(s: str) -> bool:
        return s in input_targets

    if Os.from_host() != Os.WINDOWS:
        binstall("cargo-zigbuild")

    if Os.from_host() == Os.LINUX and find("musl"):
        info("install toolchain linkers")
        apt("musl-tools")
        info("installed musl-tools")
