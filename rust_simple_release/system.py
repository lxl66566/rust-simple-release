import enum
import platform


class Os(enum.Enum):
    """
    operating system, parsed from a target triple or the host platform.
    """

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"

    @classmethod
    def from_triple(cls, target: str) -> "Os":
        """
        parse the os component of a target triple, e.g. "x86_64-pc-windows-msvc".
        """
        os_part = target.rsplit("-", 2)[-2].lower()
        if os_part in ("windows", "linux"):
            return cls(os_part)
        if os_part in ("macos", "darwin", "apple"):
            return cls.MACOS
        raise ValueError(f"unknown os in target triple: {target}")

    @classmethod
    def from_host(cls) -> "Os":
        system = platform.system().lower()
        if system == "darwin":
            system = "macos"
        try:
            return cls(system)
        except ValueError:
            raise ValueError(f"unknown host os: {system}") from None


def os_from_target(target: str | None) -> Os:
    """
    os of a target triple; an empty target refers to the host os.
    """
    if target:
        return Os.from_triple(target)
    return Os.from_host()


def target_corresponds_to_host(target: str) -> bool:
    """
    whether the os of a target triple matches the host os.
    """
    return os_from_target(target) == Os.from_host()
