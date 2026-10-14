import logging as log
import sys

from rust_simple_release.build import build_one_target, install_toolchain
from rust_simple_release.inputs import debug_mode, get_input_list
from rust_simple_release.logutil import error, info
from rust_simple_release.openssl import vendor_openssl
from rust_simple_release.publish import Uploader, create_release
from rust_simple_release.system import target_corresponds_to_host


def main() -> None:
    log.basicConfig(level=log.DEBUG if debug_mode() else log.INFO)
    targets = get_input_list("INPUT_TARGETS")
    if not targets:
        error("no targets to build, set the `targets` input")
        raise SystemExit(1)
    create_release()
    install_toolchain()
    vendor_openssl()
    uploader = Uploader()
    try:
        for target in targets:
            if not target_corresponds_to_host(target):
                info("platform does not match, skip build target.")
                continue
            uploader.submit(build_one_target(target))
    finally:
        # queued artifacts are still uploaded when a later build fails
        uploader.wait()
    if uploader.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
