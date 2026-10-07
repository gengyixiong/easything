"""Copy installed package copyright/license notices into the distribution."""

import importlib.metadata
import shutil
import sys
from pathlib import Path

destination = Path(sys.argv[1]) / "licenses"
destination.mkdir(parents=True, exist_ok=True)
for distribution in importlib.metadata.distributions():
    for file in distribution.files or []:
        if any(word in file.name.lower() for word in ("license", "copying", "notice", "copyright")):
            source = Path(distribution.locate_file(file))
            if source.is_file() and source.suffix.lower() not in {".py", ".pyc", ".pyd", ".dll"}:
                target = destination / distribution.metadata["Name"] / str(file).replace("..", "_")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
for name in ("LICENSE", "NOTICE", "THIRD_PARTY.md"):
    shutil.copyfile(name, destination / name)
