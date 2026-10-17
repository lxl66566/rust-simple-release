import logging as log
import os


def colored(msg: str, color: str) -> str:
    match color:
        case "red":
            prefix = "\033[0;31;31m"
        case "green":
            prefix = "\033[0;31;32m"
        case "yellow":
            prefix = "\033[0;31;33m"
        case "blue":
            prefix = "\033[0;31;34m"
        case _:
            prefix = ""
    return f"{prefix}{msg}\033[0m"


def _on_github_actions() -> bool:
    return os.getenv("GITHUB_ACTIONS") == "true"


def warn(s: str) -> None:
    if _on_github_actions():
        # workflow commands are only recognized at the start of a line, so they are
        # printed directly instead of going through the logging format.
        print(f"::warning:: {s}")
    else:
        log.warning(" " + colored(s, "yellow"))


def info(s: str) -> None:
    log.info(" " + colored(s, "green"))


def debug(s: str) -> None:
    log.debug(" " + colored(s, "blue"))


def error(s: str) -> None:
    if _on_github_actions():
        print(f"::error:: {s}")
    else:
        log.error(" " + colored(s, "red"))
