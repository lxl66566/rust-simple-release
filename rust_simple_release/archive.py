import os
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

from .cargo import get_output_filenames
from .inputs import get_input_list
from .logutil import debug, info
from .system import Os, os_from_target


def _walk_entry(entry: Path) -> Iterator[tuple[str, str]]:
    """
    yield (absolute path, archive-relative name) pairs for a file-or-directory entry.
    a directory is walked recursively, named relative to the directory's parent;
    a file is added under its basename.
    """
    if os.path.isdir(entry):
        for foldername, _subfolders, filenames in os.walk(entry):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                yield file_path, os.path.relpath(file_path, os.path.dirname(entry))
    else:
        yield str(entry), os.path.basename(entry)


def create_zip_in_tmp(zip_name: str, files_to_add: list[Path]) -> Path:
    """
    create zip file in tmp with given name, and return the path.
    will add all files in `files_to_add` to the zip file.
    """
    zip_path = Path(tempfile.gettempdir()) / (zip_name + ".zip")
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zipf:
        for entry in files_to_add:
            for file_path, arcname in _walk_entry(entry):
                zipf.write(file_path, arcname)
    info(f"Created `{zip_path}` successfully!")
    return zip_path


def create_tar_gz_in_tmp(tar_name: str, files_to_add: list[Path]) -> Path:
    """
    create tar.gz file in tmp with given name, and return the path.
    will add all files in `files_to_add` to the tar file.
    """
    tar_path = Path(tempfile.gettempdir()) / (tar_name + ".tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        for entry in files_to_add:
            for file_path, arcname in _walk_entry(entry):
                tar.add(file_path, arcname=arcname)
    info(f"Created {tar_path} successfully!")
    return tar_path


def pack(
    name: str,
    target: str | None,
    package: str | None = None,
) -> Path:
    """
    compress the built files and return the archive path.

    `name`: the archive name (without extension). ex. `git-se-aarch64-apple-darwin.tar.gz`
    `target`: the build target
    `package`: the package name
    """
    archive_format = target_to_archive_format(target)

    if target is None:
        target = ""

    paths = list(map(Path, get_input_list("INPUT_FILES_TO_PACK") or []))
    paths.extend(
        map(
            lambda x: Path("target") / target / "release" / x,
            get_output_filenames(target, package=package),
        )
    )

    # dedup, preserving input order
    paths = list(dict.fromkeys(paths))
    info(f"packing paths: `{paths}`")
    assert len(paths) > 0, "no files to pack"

    if archive_format == "zip":
        artifact = create_zip_in_tmp(name, paths)
    else:
        artifact = create_tar_gz_in_tmp(name, paths)
    info("files packed")
    return artifact


def target_to_archive_format(target: str | None) -> str:
    """
    get archive format from a target. available format: ["zip", "tar"]
    """
    ext = "zip" if os_from_target(target) == Os.WINDOWS else "tar"
    debug(f"get format from target {target} : {ext}")
    return ext
