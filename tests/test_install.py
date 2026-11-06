import importlib.util
import json
from pathlib import Path


def test_install_and_backup_include_the_canonical_runtime(tmp_path):
    location = Path(__file__).resolve().parents[1] / "tools" / "install_skills.py"
    spec = importlib.util.spec_from_file_location("install_skills", location)
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    root = tmp_path / "skills"
    assert installer.main(["--dest", str(root)]) == 0
    assert (root / "穿越机调参" / "scripts" / "fpv_tune" / "cli.py").is_file()
    runtime = json.loads((root / "fpv-drone-tuning" / "scripts" / "runtime.json").read_text(encoding="utf-8"))
    assert runtime["command"][1:] == ["-m", "fpv_tune.cli"]
    assert installer.main(["--dest", str(root), "--update"]) == 0
    backups = list((tmp_path / "backups" / "fpv-tuning-skills").iterdir())
    assert len(backups) == 1
    assert (backups[0] / "穿越机调参" / "scripts" / "fpv_tune" / "cli.py").is_file()
