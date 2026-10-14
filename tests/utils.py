import os
from collections.abc import Callable


def set_env(name: str, value: str | None) -> Callable[[], None]:
    """
    set the env var `name` to `value` (None removes it), and return a callable
    restoring the previous state, suitable for `addCleanup`.
    """
    old = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value

    def restore() -> None:
        if old is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old

    return restore


def chdir(path: str | os.PathLike[str]) -> Callable[[], None]:
    """
    change the working directory, and return a callable restoring the previous
    one, suitable for `addCleanup`.
    """
    old = os.getcwd()
    os.chdir(path)
    return lambda: os.chdir(old)
