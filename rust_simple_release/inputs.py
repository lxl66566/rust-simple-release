import os


def debug_mode() -> bool:
    return os.getenv("debug") is not None or os.getenv("DEBUG") is not None


def get_input(name: str) -> str | None:
    """
    read an env var by `name` (surrounding whitespace stripped from both the name and the value).
    return None if the env var is unset or empty.
    """
    temp = os.getenv(name.strip())
    if temp:
        return temp.strip()
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
        return [x.strip() for x in temp.replace("\n", ",").split(",")]
    return []


def get_input_bool(name: str, default: bool = False) -> bool:
    """
    parse an env var as bool. return `default` when unset or empty;
    otherwise true unless the value is "false", "0" or "no" (case-insensitive).
    """
    temp = get_input(name)
    if temp is None:
        return default
    return temp.lower() not in ("false", "0", "no")
