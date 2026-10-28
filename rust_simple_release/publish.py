import queue
import subprocess
import threading
from pathlib import Path

from .inputs import get_input
from .logutil import error, info
from .proc import rc, retry


def release_exists(ref_name: str) -> bool:
    try:
        # https://github.com/orgs/community/discussions/26686#discussioncomment-3396593
        rc(
            f"""gh release view "{ref_name}" """,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def create_release() -> None:
    options = get_input("INPUT_RELEASE_OPTIONS")
    ref_name = get_input("GITHUB_REF_NAME")
    if not release_exists(ref_name):
        cmd = f"""gh release create "{ref_name}" """
        if options:
            cmd += options
        res = rc(cmd, check=False, capture_output=True, text=True)
        if res.returncode != 0:
            # a concurrent job may create the release between the view and the create
            if not release_exists(ref_name):
                error(f"cannot create release, `{cmd}` exited with {res.returncode}")
                if res.stdout:
                    error(str(res.stdout).strip())
                if res.stderr:
                    error(str(res.stderr).strip())
                raise SystemExit(1)
            info(f'release "{ref_name}" already created by a concurrent job')
        elif res.stdout:
            info(str(res.stdout).strip())
    info(f"""release "{ref_name}" created""")


def upload_one_file(file: Path) -> bool:
    ref_name = get_input("GITHUB_REF_NAME")

    # https://github.com/orgs/community/discussions/26686#discussioncomment-3396593
    res = retry(lambda: rc(f"""gh release upload "{ref_name}" "{file}" --clobber"""))
    if res:
        info(f"file `{file}` uploaded successfully")
    else:
        error(f"cannot upload file: {file}")
    return res


class Uploader:
    """
    upload artifacts one by one in a single background thread, overlapped with the subsequent builds.
    """

    def __init__(self) -> None:
        self.queue: queue.Queue[Path | None] = queue.Queue()
        self.failed: list[Path] = []
        self.closed = False
        self.thread = threading.Thread(target=self._worker)
        self.thread.start()

    def _worker(self) -> None:
        while (file := self.queue.get()) is not None:
            if not upload_one_file(file):
                self.failed.append(file)

    def submit(self, file: Path) -> None:
        if self.closed:
            raise RuntimeError("cannot submit after wait()")
        self.queue.put(file)

    def wait(self) -> None:
        """
        block until every submitted file has been uploaded.
        """
        self.closed = True
        self.queue.put(None)
        self.thread.join()
