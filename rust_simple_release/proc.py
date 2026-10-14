import shutil
import subprocess
import time
from collections.abc import Callable
from typing import Any

from .logutil import colored, error, info, warn


def rc(
    command: str, **kwargs: Any
) -> subprocess.CompletedProcess[bytes | str | None]:
    """
    rc means run with check.
    """
    info(colored(f"run: `{command}`", "green"))
    kwargs.setdefault("check", True)
    kwargs.setdefault("shell", True)
    try:
        result: Any = subprocess.run(command, **kwargs)
        return result
    except subprocess.CalledProcessError as e:
        error(f"Command '{e.cmd}' returned non-zero exit status {e.returncode}.")
        raise


def retry(func: Callable[[], Any], times: int = 5) -> bool:
    """
    retry function for a few times.

    Return `True` if `func` exec successfully, otherwise return `False`.
    """
    for attempt in range(1, times + 1):
        try:
            func()
            return True
        except Exception:
            warn(f"attempt {attempt}/{times} failed")
            if attempt < times:
                time.sleep(min(2 * attempt, 8))
    return False


def apt(*package: str) -> None:
    """
    install package with apt
    """
    assert shutil.which("sudo") and shutil.which("apt")
    rc("sudo apt install -y -q " + " ".join(package))


def binstall(*package: str) -> None:
    assert shutil.which("cargo")
    rc("cargo binstall -y --no-symlinks " + " ".join(package))
