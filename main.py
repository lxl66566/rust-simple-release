import json
import logging as log
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from functools import reduce
from pathlib import Path

TARGET_DIR = "target/rust-release-action"
artifacts_path = []


def debug_mode():
    return os.getenv("debug") is not None or os.getenv("DEBUG") is not None or False


def get_input(name: str):
    temp = os.getenv(name.strip())
    if temp:
        return temp.strip()
    else:
        return None


def get_input_list(name: str):
    """
    >>> import os
    >>> os.environ["456123"] = "a,b,123,456"
    >>> get_input_list(" 456123  ")
    ['a', 'b', '123', '456']
    """
    temp = get_input(name)
    if temp:
        return list(map(lambda x: x.strip(), temp.split(",")))
    else:
        return None


def info(s):
    log.info(" " + colored(s, "green"))


def debug(s):
    log.debug(" " + colored(s, "blue"))


def rc(s: str, **kwargs):
    """
    rc means run with check.
    """
    info(colored(f"run: `{s}`", "green"))
    kwargs.setdefault("check", True)
    kwargs.setdefault("shell", True)
    try:
        result = subprocess.run(s, **kwargs)
        return result
    except subprocess.CalledProcessError as e:
        log.error(
            colored(
                f"Command '{e.cmd}' returned non-zero exit status {e.returncode}.",
                "red",
            )
        )
        raise


def colored(msg: str, color: str):
    match color:
        case "red":
            prefix = "\033[0;31;31m"
        case "green":
            prefix = "\033[0;31;32m"
        case "yellow":
            prefix = "\033[0;31;33m"
        case "blue":
            prefix = "\033[0;31;36m"
        case _:
            prefix = ""
    return f"{prefix}{msg}\033[0m"


def once(func):
    """Runs a function only once."""
    results = {}

    def wrapper(*args, **kwargs):
        if func not in results:
            results[func] = func(*args, **kwargs)
        return results[func]

    return wrapper


def apt(*package: str):
    """
    install package with apt
    """
    assert shutil.which("sudo") and shutil.which("apt")
    rc("sudo apt install -y -q " + " ".join(package))


def binstall(*package: str):
    assert shutil.which("cargo")
    rc("cargo binstall -y --no-symlinks " + " ".join(package))


@once
def cargo_metadata(cwd: str = "."):
    """
    get metadata in Cargo.toml
    """
    metadata = rc(
        "cargo metadata --format-version 1 --no-deps", capture_output=True, cwd=cwd
    ).stdout.strip()
    return json.loads(metadata)


def create_zip_in_tmp(zip_name: str, files_to_add: list[str]):
    zip_path = Path(tempfile.gettempdir()) / (zip_name + ".zip")
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in files_to_add:
            if os.path.isdir(file):
                for foldername, subfolders, filenames in os.walk(file):
                    for filename in filenames:
                        file_path = os.path.join(foldername, filename)
                        zipf.write(
                            file_path, os.path.relpath(file_path, os.path.dirname(file))
                        )
            else:
                zipf.write(file, os.path.basename(file))
    info(f"Created `{zip_path}` successfully!")
    return zip_path


def create_tar_gz_in_tmp(tar_name: str, files_to_add: list[str]):
    tar_path = Path(tempfile.gettempdir()) / (tar_name + ".tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        for file in files_to_add:
            if os.path.isdir(file):
                for foldername, subfolders, filenames in os.walk(file):
                    for filename in filenames:
                        file_path = os.path.join(foldername, filename)
                        relative_path = os.path.relpath(
                            file_path, os.path.dirname(file)
                        )
                        tar.add(file_path, arcname=relative_path)
            else:
                tar.add(file, arcname=os.path.basename(file))
    info(f"Created {tar_path} successfully!")
    return tar_path


def get_output_bin_name(target: str):
    """
    get the name of output binary. target is to add `.exe` on windows target.
    """
    if bin := get_input("INPUT_BIN"):
        output_bin_name = bin
    else:
        package_name = get_input("INPUT_PACKAGE")
        package_meta = next(
            (
                x
                for x in cargo_metadata()["packages"]
                if package_name is None or x["name"] == package_name
            ),
            None,
        )
        assert package_meta, "package meta could not be none"
        assert package_meta["name"], "package name could not be none"
        output_bin_name = Path(package_meta["name"]).name
    if "windows" in target.lower():
        output_bin_name += ".exe"
    debug(f"get output bin name: {output_bin_name}")
    return output_bin_name


def get_linker_flags_by_target(target: str):
    if "aarch" in target:
        if "gnu" in target:
            return "aarch64-linux-gnu-gcc"
        if "musl" in target:
            return "aarch64-linux-musl-gcc"
    if "windows" in target:
        return "x86_64-w64-mingw32-gcc"
    if "x86_64" in target:
        if "musl" in target:
            return "musl-gcc"
        else:
            return "gcc"
    if "darwin" in target:
        return "rust-lld"


def build_one_target(target: str):
    cmd = []
    rc(f"rustup target add {target}")
    # cmd.append(f"""RUSTFLAGS="-C linker={get_linker_flags_by_target(target)}" """)

    cmd.append("cargo zigbuild --release")
    if target:
        rc(f"rustup target add {target}")
        cmd.append(f"--target {target}")
    if bin := get_input("INPUT_BIN"):
        cmd.append(f"--bin {bin}")
    if features := get_input("INPUT_FEATURES"):
        cmd.append(f"--features {features}")
    if package := get_input("INPUT_PACKAGE"):
        cmd.append(f"--package {package}")
    rc(" ".join(cmd))
    info(f"target {target} build success")


def pack(name: str, target: str):
    """
    compress the binary.

    `name`: the archive name (without extension). ex. `git-se-aarch64-apple-darwin.tar.gz`
    `target`: the build target
    """
    global artifacts_path
    format = target_to_archive_format(target)
    assert format in ["zip", "tar"], "unsupported format"

    # https://doc.rust-lang.org/cargo/guide/build-cache.html
    bin_path = Path("target") / target or "release" / get_output_bin_name(target)
    paths = get_input_list("INPUT_FILES_TO_PACK") or []
    paths.append(bin_path)
    # unique
    paths = reduce(lambda re, x: re + [x] if x not in re else re, paths, [])
    if format == "zip":
        artifacts_path.append(create_zip_in_tmp(name, paths))
    else:
        artifacts_path.append(create_tar_gz_in_tmp(name, paths))
    info("files packed")


def target_to_archive_format(target: str):
    """
    get archive format from a target. available format: ["zip", "tar"]
    """
    if "windows" in target.lower():
        ext = "zip"
    else:
        ext = "tar"
    debug(f"get format from target {target} : {ext}")
    return ext


def upload_files_to_github_release(files: list[Path]):
    token = get_input("INPUT_TOKEN")
    ref_name = get_input("GITHUB_REF_NAME")
    artifacts = " ".join(list(map(str, artifacts_path)))
    for retry in range(0, 5):
        try:
            # https://github.com/orgs/community/discussions/26686#discussioncomment-3396593
            if platform.system() != "Windows":
                rc(
                    f"""GITHUB_TOKEN="{token}" gh release upload "{ref_name}" {artifacts} --clobber"""
                )
            else:
                rc(
                    """pwsh -c '$env:GITHUB_TOKEN="{token}"; gh release upload "{ref_name}" {artifacts} --clobber'"""
                )
            info("file upload successfully")
            return
        except:
            pass
    log.error(colored("cannot upload file.", "red"))


def fuck_openssl():
    lock = Path("Cargo.lock")
    if (lock.exists() and "openssl" in lock.read_text()) or any(
        map(lambda x: "openssl" in x.read_text(), Path(".").rglob("Cargo.toml"))
    ):
        if shutil.which("apt"):
            apt("pkg-config", "libssl-dev")
        elif shutil.which("brew"):
            rc("brew install openssl")
        else:
            rc("choco install openssl")


def install_toolchain():
    input_targets = get_input("INPUT_TARGETS")

    def find(s):
        return s in input_targets

    binstall("cargo-zigbuild")

    if platform.system() != "Windows":
        info("install toolchain linkers")
        if find("musl"):
            apt("musl-tools")
            info("installed musl-tools")
        if find("darwin"):
            # https://github.com/rust-lang/rust/issues/112501#issuecomment-1682426620
            # apt("clang")
            rc(
                "curl -L https://github.com/roblabla/MacOSX-SDKs/releases/download/13.3/MacOSX13.3.sdk.tar.xz | tar xJ",
                cwd="/tmp",
            )
            rc("export SDKROOT=$(pwd)/MacOSX13.3.sdk/", cwd="/tmp")
            info("installed clang, MacOSX-SDKs")


# region run


def main():
    log.basicConfig(level=log.DEBUG if debug_mode() else log.INFO)
    install_toolchain()
    fuck_openssl()
    targets = get_input_list("INPUT_TARGETS")
    for target in targets:
        if ("windows" in target and platform.system() != "Windows") or (
            "windows" not in target and platform.system() == "Windows"
        ):
            info("platform does not match, skip build target.")
            continue
        archive_name = get_output_bin_name(target) + "-" + target
        build_one_target(target)
        pack(archive_name, target)
    upload_files_to_github_release(artifacts_path)


if __name__ == "__main__":
    main()

# region test


class Test(unittest.TestCase):
    def test_cargo_metadata(self):
        assert cargo_metadata()["packages"][0]["version"] == "0.0.1"

    def test_get_output_bin_name(self):
        assert get_output_bin_name("x86_64-linux-musl") == "action-test"
        # if you want to use `[[bin]] name = "my-action-test"`, please manually specify it.

    def test_get_input(self):
        os.environ["456123"] = " 1 "
        assert get_input(" 456123  ") == "1"

    def test_get_input_list(self):
        os.environ["456123"] = "a,b,123,456"
        assert get_input_list(" 456123  ") == ["a", "b", "123", "456"]

    def test_pack(self):
        os.environ["INPUT_BIN"] = "my-action-test"
        pack("123456", "x86_64-windows_msvc")
        assert (Path(tempfile.gettempdir()) / "123456.zip").exists()
