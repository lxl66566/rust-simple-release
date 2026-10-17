import json
from functools import cache
from typing import Any

from .inputs import get_input, get_input_bool, get_input_list
from .logutil import debug, warn
from .proc import rc
from .system import Os, os_from_target


@cache
def cargo_metadata(cwd: str = ".") -> dict[str, Any]:
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


def get_selected_package_metadata(package: str | None = None) -> dict[str, Any]:
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


def get_lib_meta(package: str | None = None) -> dict[str, Any] | None:
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


def get_bin_metas(package: str | None = None) -> list[dict[str, Any]]:
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

    target_os = os_from_target(target)
    lib_meta = get_lib_meta(package)
    bin_names = [x["name"] for x in get_bin_metas(package)]

    output_filenames: list[str] = []
    if bins := get_input_list("INPUT_BINS"):
        assert set(bins) <= set(bin_names), (
            "input bins must be a subset of actual bin names"
        )
        output_filenames.extend(dict.fromkeys(bins))
    else:
        output_filenames.extend(bin_names)
    if target_os == Os.WINDOWS:
        output_filenames = list(
            map(
                lambda x: x + ".exe" if not x.endswith(".exe") else x,
                output_filenames,
            )
        )

    if not output_filenames:
        warn("no bins got above, will try to add lib")

    # specified INPUT_LIB or no bins got above, then we need to add lib
    if get_input_bool("INPUT_LIB") or not output_filenames:
        assert lib_meta, "lib target not found in this package."
        lib_name = lib_meta["name"]
        lib_type = lib_meta["crate_types"][0]
        output_lib_name: str
        # ref:
        # - https://rustcc.cn/article?id=98b96e69-7a5f-4bba-a38e-35bdd7a0a7dd
        # - https://chatgpt.com/share/562dd3ab-7d92-48c0-bb0e-68e48c8f53c4
        match lib_type:
            case "staticlib":
                if target_os == Os.WINDOWS:
                    output_lib_name = f"{lib_name}.lib"
                else:
                    output_lib_name = f"lib{lib_name}.a"
            case "cdylib":
                if target_os == Os.WINDOWS:
                    output_lib_name = f"{lib_name}.dll"
                elif target_os == Os.LINUX:
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
