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
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union

import toml

TARGET_DIR = "target/rust-release-action"
artifacts_path: list[Path] = []


def debug_mode():
    return os.getenv("debug") is not None or os.getenv("DEBUG") is not None or False


def get_input(name: str):
    temp = os.getenv(name.strip())
    if temp:
        return temp.strip()
    else:
        return None


def get_input_list(name: str) -> list[str]:
    r"""
    split input env name by comma or newline, and strip each item.
    >>> import os
    >>> os.environ["456123"] = "a\nb\n123,456"
    >>> get_input_list(" 456123  ")
    ['a', 'b', '123', '456']
    """
    temp = get_input(name)
    if temp:
        return list(map(lambda x: x.strip(), temp.replace("\n", ",").split(",")))
    else:
        return []


def warn(s: str):
    log.warning(" " + colored(s, "yellow"))


def info(s: str):
    log.info(" " + colored(s, "green"))


def debug(s: str):
    log.debug(" " + colored(s, "blue"))


def rc(
    s: str, **kwargs: Any
) -> subprocess.CompletedProcess[Optional[Union[bytes, str]]]:
    """
    rc means run with check.
    """
    info(colored(f"run: `{s}`", "green"))
    kwargs.setdefault("check", True)
    kwargs.setdefault("shell", True)
    try:
        result: Any = subprocess.run(s, **kwargs)
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


def once(func: Callable[..., Any]) -> Callable[..., Any]:
    """Runs a function only once."""
    results: Dict[Callable[..., Any], Any] = {}

    @wraps(func)
    def wrapper(*args: Tuple[Any, ...], **kwargs: Dict[str, Any]) -> Any:
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
    metadata = (
        rc(
            "cargo metadata --format-version 1 --no-deps", capture_output=True, cwd=cwd
        ).stdout
        or ""
    ).strip()
    return json.loads(metadata)


class System:
    """
    get system type from target triple or current platform
    """

    def __init__(self, target: str | None = None):
        if not target:
            self.target = platform.system().lower()
        else:
            self.target = target.rsplit("-", 2)[-2].lower()

    def is_windows(self) -> bool:
        return self.target == "windows"

    def is_macos(self) -> bool:
        return self.target in ["macos", "darwin", "apple"]

    def is_linux(self) -> bool:
        return self.target == "linux"

    def __eq__(self, value: object) -> bool:
        if isinstance(value, System):
            return (self.is_macos() and value.is_macos()) or self.target == value.target
        else:
            return self.target == value


def create_zip_in_tmp(zip_name: str, files_to_add: list[Path]) -> Path:
    """
    create zip file in tmp with given name, and return the path.
    will add all files in `files_to_add` to the zip file.
    """
    zip_path = Path(tempfile.gettempdir()) / (zip_name + ".zip")
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in files_to_add:
            if os.path.isdir(file):
                for foldername, _subfolders, filenames in os.walk(file):
                    for filename in filenames:
                        file_path = os.path.join(foldername, filename)
                        zipf.write(
                            file_path, os.path.relpath(file_path, os.path.dirname(file))
                        )
            else:
                zipf.write(file, os.path.basename(file))
    info(f"Created `{zip_path}` successfully!")
    return zip_path


def create_tar_gz_in_tmp(tar_name: str, files_to_add: list[Path]) -> Path:
    """
    create tar.gz file in tmp with given name, and return the path.
    will add all files in `files_to_add` to the tar file.
    """
    tar_path = Path(tempfile.gettempdir()) / (tar_name + ".tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        for file in files_to_add:
            if os.path.isdir(file):
                for foldername, _subfolders, filenames in os.walk(file):
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


def get_selected_package_metadata(package: str | None = None):
    """
    get the metadata of selected one package
    """
    package_name = package or get_input("INPUT_PACKAGE")
    package_meta = next(
        (
            x
            for x in cargo_metadata()["packages"]
            if not package_name or x["name"] == package_name
        ),
        None,
    )
    assert package_meta, "package meta could not be none"
    debug(f"get package meta: {package_meta}")
    return package_meta


def get_lib_meta(package: str | None = None) -> Any | None:
    """
    get the lib target metadata of selected one package
    """
    temp = next(
        filter(
            lambda x: "lib" in x["kind"][0],
            get_selected_package_metadata(package)["targets"],
        ),
        None,
    )
    return temp


def get_bin_metas(package: str | None = None) -> list[Any]:
    """
    get the bin target metadata of selected one package
    """
    temp = list(
        filter(
            lambda x: "bin" == x["kind"][0],
            get_selected_package_metadata(package)["targets"],
        )
    )
    return temp


def get_output_filenames(target: str, package: str | None = None) -> list[str]:
    """
    get the filenames of output files, including bins and lib.

    This function will deal with default, which the `INPUT_BINS` and `INPUT_LIB` are not set.
    In this case, it will only returns filenames of bins, and the lib will be ignored.

    For bins, it will append `.exe` to bin names if on windows.
    """

    lib_meta = get_lib_meta(package)
    bin_names = [x["name"] for x in get_bin_metas(package)]

    output_filenames = []
    if bins := get_input_list("INPUT_BINS"):
        assert set(bins) <= set(bin_names), (
            "input bins must be a subset of actual bin names"
        )
        output_filenames.extend(set(bins))
    else:
        output_filenames.extend(bin_names)
    if System(target).is_windows():
        output_filenames = list(
            map(
                lambda x: x + ".exe" if not x.endswith(".exe") else x,
                output_filenames,
            )
        )

    if not output_filenames:
        warn("no bins got above, will try to add lib")

    # specified INPUT_LIB or no bins got above, then we need to add lib
    if get_input("INPUT_LIB") or not output_filenames:
        assert lib_meta, "lib target not found in this package."
        lib_name = lib_meta["name"]
        lib_type = lib_meta["crate_types"][0]
        output_lib_name: str
        # ref:
        # - https://rustcc.cn/article?id=98b96e69-7a5f-4bba-a38e-35bdd7a0a7dd
        # - https://chatgpt.com/share/562dd3ab-7d92-48c0-bb0e-68e48c8f53c4
        match lib_type:
            case "staticlib":
                if System(target).is_windows():
                    output_lib_name = f"{lib_name}.lib"
                else:
                    output_lib_name = f"lib{lib_name}.a"
            case "cdylib":
                if System(target).is_windows():
                    output_lib_name = f"{lib_name}.dll"
                elif System(target).is_linux():
                    output_lib_name = f"lib{lib_name}.so"
                else:
                    output_lib_name = f"lib{lib_name}.dylib"
            case "rlib" | "lib":
                output_lib_name = f"{lib_name}.rlib"
            case _:
                raise ValueError(f"unknown lib type: {lib_type}")

        output_filenames.append(output_lib_name)

    debug(f"get output filenames: {output_filenames}")
    assert output_filenames, "output filenames could not be none or empty"
    return output_filenames


# def get_linker_flags_by_target(target: str):
#     """
#     currently not used :(
#     """
#     if "aarch" in target:
#         if "gnu" in target:
#             return "aarch64-linux-gnu-gcc"
#         if "musl" in target:
#             return "aarch64-linux-musl-gcc"
#     if "windows" in target:
#         return "x86_64-w64-mingw32-gcc"
#     if "x86_64" in target:
#         if "musl" in target:
#             return "musl-gcc"
#         else:
#             return "gcc"
#     if "darwin" in target:
#         return "rust-lld"


def create_flags(
    target: str,
    package: str | None = None,
) -> str | None:
    """
    create flags for cargo build
    """

    # https://github.com/rust-lang/cargo/issues/8607
    if meta := get_lib_meta(package):
        if "musl" in target and meta["crate_types"][0] in ["cdylib", "dylib"]:
            return "-C target-feature=-crt-static"

    return None


def build_one_target(target: str):
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
    if not System().is_windows() and not System().is_macos():
        build_cmd = "zigbuild"
    else:
        build_cmd = "build"

    cmd.append(f"cargo {build_cmd} --release")
    if target:
        rc(f"rustup target add {target}")
        cmd.append(f"--target {target}")
    if bins := get_input_list("INPUT_BINS"):
        for bin in bins:
            cmd.append(f"--bin {bin}")
    if _ := get_input("INPUT_LIB"):
        cmd.append("--lib")
    if features := get_input_list("INPUT_FEATURES"):
        cmd.append(f"--features {','.join(features)}")
    if package := get_input("INPUT_PACKAGE"):
        cmd.append(f"--package {package}")
    rc(" ".join(cmd), env=build_env)
    info(f"target {target} build success")

    archive_name = get_selected_package_metadata()["name"] + "-" + target
    pack(archive_name, target)

    info(f"target {target} packed")


def pack(
    name: str,
    target: str | None,
    package: str | None = None,
):
    """
    compress the binary.

    `name`: the archive name (without extension). ex. `git-se-aarch64-apple-darwin.tar.gz`
    `target`: the build target
    `package`: the package name
    """
    global artifacts_path
    format = target_to_archive_format(target)
    assert format in ["zip", "tar"], "unsupported format"

    if target is None:
        target = ""

    paths = list(map(Path, get_input_list("INPUT_FILES_TO_PACK") or []))
    paths.extend(
        map(
            lambda x: (Path("target") / target / "release" / x),
            get_output_filenames(target, package=package),
        )
    )

    # dedup
    paths: list[Path] = list(set(paths))
    info(f"packing paths: `{paths}`")
    assert len(paths) > 0, "no files to pack"

    if format == "zip":
        artifacts_path.append(create_zip_in_tmp(name, paths))
    else:
        artifacts_path.append(create_tar_gz_in_tmp(name, paths))
    info("files packed")


def target_to_archive_format(target: str | None):
    """
    get archive format from a target. available format: ["zip", "tar"]
    """
    if System(target).is_windows():
        ext = "zip"
    else:
        ext = "tar"
    debug(f"get format from target {target} : {ext}")
    return ext


def target_coresponding_to_platform(target: str):
    return System() == System(target)


def retry(func: Callable[..., Any], times: int = 5):
    """
    retry function for a few times.

    Return `True` if `func` exec successfully, otherwise return `False`.
    """
    for _ in range(0, times):
        try:
            func()
            return True
        except:
            pass
    return False


def upload_files_to_github_release(files: list[Path]):
    ref_name = get_input("GITHUB_REF_NAME")
    artifacts = " ".join(list(map(str, files)))

    # https://github.com/orgs/community/discussions/26686#discussioncomment-3396593
    res = retry(lambda: rc(f"""gh release upload "{ref_name}" {artifacts} --clobber"""))
    if res:
        info("file upload successfully")
    else:
        log.error(colored("cannot upload file.", "red"))
        exit(1)


def create_release():
    options = get_input("INPUT_RELEASE_OPTIONS")
    ref_name = get_input("GITHUB_REF_NAME")
    try:
        # https://cli.github.com/manual/gh_release_view
        rc(
            f"""gh release view "{ref_name}" """,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        cmd = f"""gh release create "{ref_name}" """
        if options:
            cmd += options
        rc(cmd, check=False)
    info(f"""release "{ref_name}" created""")


def fuck_openssl():
    lock = Path("Cargo.lock")
    if not (lock.exists() and "openssl" in lock.read_text()):
        return

    # add vendored feature
    # note: it will change your Cargo.toml in CI environment if openssl is in Cargo.lock
    # note: once it detects openssl in Cargo.lock, it will change your Cargo.toml in all workspace packages

    for file in Path(".").rglob("Cargo.toml"):
        data = toml.loads(file.read_text())
        if "workspace" in data:
            continue
        data.setdefault("dependencies", {}).setdefault("openssl", {})["features"] = [
            "vendored"
        ]
        if "version" not in data["dependencies"]["openssl"]:
            data["dependencies"]["openssl"]["version"] = "*"
        file.write_text(toml.dumps(data))

    # install openssl sys package
    if System().is_linux():
        apt("pkg-config", "libssl-dev")
    elif System().is_macos():
        rc("brew install openssl")
    else:
        # https://github.com/sfackler/rust-openssl/blob/master/.github/workflows/ci.yml
        os.environ["VCPKG_ROOT"] = os.environ["VCPKG_INSTALLATION_ROOT"]
        rc("vcpkg install openssl:x64-windows-static-md")
        # rc("choco install openssl strawberryperl")
        # perl_path = shutil.which("perl")
        # if perl_path:
        #     os.environ["PERL"] = perl_path
        #     os.environ["OPENSSL_SRC_PERL"] = perl_path


def install_toolchain():
    input_targets = get_input("INPUT_TARGETS") or ""

    def find(s: str):
        return s in input_targets

    if not System().is_windows():
        binstall("cargo-zigbuild")

    if System().is_linux() and find("musl"):
        info("install toolchain linkers")
        if find("musl"):
            apt("musl-tools")
            info("installed musl-tools")
    # https://github.com/rust-lang/rust/issues/112501#issuecomment-1682426620
    # apt("clang")
    # rc(
    #     "curl -L https://github.com/roblabla/MacOSX-SDKs/releases/download/13.3/MacOSX13.3.sdk.tar.xz | tar xJ",
    #     cwd="/tmp",
    # )
    # rc("export SDKROOT=$(pwd)/MacOSX13.3.sdk/", cwd="/tmp")
    # info("installed clang, MacOSX-SDKs")


# region run


def main():
    log.basicConfig(level=log.DEBUG if debug_mode() else log.INFO)
    create_release()
    install_toolchain()
    fuck_openssl()
    targets = get_input_list("INPUT_TARGETS")
    for target in targets:
        if not target_coresponding_to_platform(target):
            info("platform does not match, skip build target.")
            continue
        build_one_target(target)
    upload_files_to_github_release(artifacts_path)


if __name__ == "__main__":
    main()

# region test


class Test(unittest.TestCase):
    def test_cargo_metadata(self):
        assert cargo_metadata()["version"] == 1

    def test_get_input(self):
        os.environ["456123"] = " 1 "
        assert get_input(" 456123  ") == "1"

    def test_get_input_list(self):
        os.environ["456123"] = "a,b,123,456"
        assert get_input_list(" 456123  ") == ["a", "b", "123", "456"]

    def test_pack(self):
        if not (Path("target") / "release" / "my-action-test.exe").exists():
            return
        pack("123456", "", package="action-test")
        assert (Path(tempfile.gettempdir()) / "123456.zip").exists() or (
            Path(tempfile.gettempdir()) / "123456.tar.gz"
        ).exists()

    def test_get_selected_package_metadata(self):
        assert get_selected_package_metadata("action-test")["name"] == "action-test"

    def test_System(self):
        assert System("x86_64-unknown-linux-gnu").is_linux()
        assert System("x86_64-apple-darwin").is_macos()
        assert System("x86_64-pc-windows-msvc").is_windows()
        assert System("x86_64-pc-windows-msvc") == System("i686-pc-windows-msvc")
        assert System("x86_64-unknown-linux-gnu") == System("aarch64-unknown-linux-gnu")
        assert not System("x86_64-unknown-linux-gnu") == System("x86_64-apple-darwin")
        assert not System("x86_64-pc-windows-msvc") == System(
            "x86_64-unknown-linux-gnu"
        )

    def test_get_output_filename(self):
        assert get_output_filenames("x86_64-linux-musl", package="action-test") == [
            "my-action-test",
            "my-action-test2",
        ]
        assert get_output_filenames(
            "aarch64-unknown-linux-gnu", package="lib_test"
        ) == ["liblib_test.so"]
