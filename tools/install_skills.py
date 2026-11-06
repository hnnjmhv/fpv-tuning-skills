"""Install both language entrypoints, backing up an existing skill on explicit update."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, help="Skills directory; defaults to CODEX_HOME/skills or ~/.codex/skills")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    codex_root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    root = (args.dest or codex_root / "skills").resolve()
    names = ("穿越机调参", "fpv-drone-tuning")
    root.mkdir(parents=True, exist_ok=True)
    targets = [(repo / "skills" / name, root / name) for name in names]
    for source, target in targets:
        if target.resolve() == source.resolve():
            parser.error("Source and installation directory must differ.")
        if target.is_symlink() or target.resolve().parent != root:
            parser.error(f"Refusing target outside the skills directory: {target}")
        if target.exists() and not args.update:
            parser.error(f"Already installed: {target}; use --update to back it up before replacement.")
    backup_root = root.parent / "backups" / "fpv-tuning-skills"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
    backup = backup_root / stamp
    for source, target in targets:
        if target.exists():
            backup.mkdir(parents=True, exist_ok=True)
            archive = backup / target.name
            if archive.resolve().parent != backup.resolve():
                raise ValueError("Unexpected backup target")
            target.rename(archive)
            print(f"Backed up: {archive}")
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "fpv_tune", "runtime.json"))
        runtime = target / "scripts" / "runtime.json"
        runtime.parent.mkdir(exist_ok=True)
        if target.name == "穿越机调参":
            shutil.copytree(repo / "src" / "fpv_tune", runtime.parent / "fpv_tune",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        runtime.write_text(json.dumps({"python": sys.executable,
                                      "command": [sys.executable, "-m", "fpv_tune.cli"]}, indent=2) + "\n", encoding="utf-8")
        print(f"Installed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
