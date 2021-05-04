import os
from pathlib import Path
from typing import Any, List, Optional

from pdm.project import Project


def check_fingerprint(filename: Path) -> bool:
    return os.path.basename(filename) == "setup.py"


def convert(_project: Project, _filename: Path, _options: Optional[Any]) -> None:
    raise NotImplementedError()


def export(project: Project, _candidates: List, _options: Optional[Any]) -> str:
    from pdm.pep517.base import Builder

    builder = Builder(project.root)
    return builder.format_setup_py()
