from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path


class FilesystemSafetyError(RuntimeError):
    pass


def lexical_path(path: Path | str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _is_reparse(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    attributes = int(getattr(info, "st_file_attributes", 0))
    return bool(attributes & flag)


def assert_no_reparse_ancestors(path: Path | str) -> None:
    current = lexical_path(path)
    chain: list[Path] = []
    while True:
        chain.append(current)
        if current.parent == current:
            break
        current = current.parent
    for candidate in reversed(chain):
        if _lexists(candidate) and _is_reparse(candidate):
            raise FilesystemSafetyError(f"reparse-point-blocked:{candidate}")


def canonical_path(path: Path | str) -> Path:
    candidate = lexical_path(path)
    assert_no_reparse_ancestors(candidate)
    return candidate.resolve(strict=False)


def path_key(path: Path | str) -> str:
    return os.path.normcase(str(canonical_path(path)))


def _entry_is_reparse(entry: os.DirEntry[str]) -> bool:
    if entry.is_symlink():
        return True
    try:
        info = entry.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    attributes = int(getattr(info, "st_file_attributes", 0))
    return bool(attributes & flag)


def _walk_safe(root: Path) -> list[tuple[str, Path, bool]]:
    if not root.is_dir():
        raise FilesystemSafetyError(f"not-directory:{root}")
    assert_no_reparse_ancestors(root)
    rows: list[tuple[str, Path, bool]] = []

    def visit(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name.casefold())
        except OSError as exc:
            raise FilesystemSafetyError(
                f"scan-failed:{directory}:{type(exc).__name__}"
            ) from exc
        for entry in entries:
            candidate = Path(entry.path)
            if _entry_is_reparse(entry):
                raise FilesystemSafetyError(f"reparse-point-blocked:{candidate}")
            relative = candidate.relative_to(root).as_posix()
            if entry.is_dir(follow_symlinks=False):
                rows.append((relative, candidate, True))
                visit(candidate)
            elif entry.is_file(follow_symlinks=False):
                rows.append((relative, candidate, False))
            else:
                raise FilesystemSafetyError(f"unsupported-filesystem-entry:{candidate}")

    visit(root)
    return rows


def tree_digest(path: Path | str) -> str:
    root = canonical_path(path)
    if not (root / "SKILL.md").is_file():
        raise FilesystemSafetyError(f"skill-file-missing:{root}")
    digest = hashlib.sha256()
    digest.update(b"skill-control-plane-tree-v1\0")
    for relative, candidate, is_directory in _walk_safe(root):
        encoded = relative.encode("utf-8")
        if is_directory:
            digest.update(b"D\0" + encoded + b"\0")
            continue
        raw = candidate.read_bytes()
        digest.update(b"F\0" + encoded + b"\0")
        digest.update(str(len(raw)).encode("ascii") + b"\0")
        digest.update(hashlib.sha256(raw).digest())
    return digest.hexdigest()


def copy_tree(source: Path | str, destination: Path | str) -> Path:
    src = canonical_path(source)
    dst = lexical_path(destination)
    assert_no_reparse_ancestors(dst.parent)
    if _lexists(dst):
        raise FilesystemSafetyError(f"destination-exists:{dst}")
    _walk_safe(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, copy_function=shutil.copy2)
    _walk_safe(dst)
    return dst


def move_directory(source: Path | str, destination: Path | str) -> Path:
    src = lexical_path(source)
    dst = lexical_path(destination)
    assert_no_reparse_ancestors(src)
    assert_no_reparse_ancestors(dst.parent)
    if not _lexists(src):
        raise FilesystemSafetyError(f"source-missing:{src}")
    if _lexists(dst):
        raise FilesystemSafetyError(f"destination-exists:{dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)
    return dst


def remove_tree(path: Path | str) -> None:
    target = lexical_path(path)
    if not _lexists(target):
        return
    _walk_safe(target)
    shutil.rmtree(target)


def file_sha256(path: Path | str) -> str:
    target = canonical_path(path)
    assert_no_reparse_ancestors(target)
    return hashlib.sha256(target.read_bytes()).hexdigest()
