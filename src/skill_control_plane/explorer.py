from __future__ import annotations

import os
from pathlib import Path


class ExplorerOpenError(RuntimeError):
    pass


def open_explorer_folder(folder: Path) -> None:
    target = folder.expanduser().absolute()
    if os.name != "nt" or not target.is_dir():
        raise ExplorerOpenError("explorer-folder-unavailable")
    os.startfile(str(target))  # type: ignore[attr-defined]
